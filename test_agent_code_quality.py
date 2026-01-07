"""
Тестирование качества кода, генерируемого агентами
"""
import ast
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Any
import requests
import time

class AgentCodeQualityTester:
    """Тестер качества кода, генерируемого агентами"""
    
    def __init__(self, llm_url: str = "http://localhost:8002", tool_url: str = "http://localhost:8003"):
        self.llm_url = llm_url
        self.tool_url = tool_url
        self.test_results = []
        
    def test_agent_code_generation(self) -> Dict[str, Any]:
        """Основной тест генерации кода агентами"""
        print("🧪 Тестирование качества кода, генерируемого агентами")
        print("=" * 60)
        
        # Тестовые задачи разной сложности
        test_tasks = [
            {
                "name": "simple_function",
                "description": "Создай простую функцию для вычисления факториала числа",
                "complexity": "simple",
                "expected_elements": ["def", "factorial", "return", "if", "else"]
            },
            {
                "name": "class_with_methods",
                "description": "Создай класс Calculator с методами add, subtract, multiply, divide",
                "complexity": "medium",
                "expected_elements": ["class", "Calculator", "def add", "def subtract", "def multiply", "def divide"]
            },
            {
                "name": "api_endpoint",
                "description": "Создай FastAPI endpoint для создания пользователя с валидацией данных",
                "complexity": "complex",
                "expected_elements": ["FastAPI", "POST", "Pydantic", "BaseModel", "validation"]
            },
            {
                "name": "async_function",
                "description": "Создай асинхронную функцию для загрузки данных из API с обработкой ошибок",
                "complexity": "complex",
                "expected_elements": ["async def", "await", "aiohttp", "try", "except"]
            },
            {
                "name": "data_processing",
                "description": "Создай функцию для обработки CSV файла с pandas и возвратом статистики",
                "complexity": "medium",
                "expected_elements": ["pandas", "read_csv", "describe", "return"]
            }
        ]
        
        results = {
            "total_tests": len(test_tasks),
            "passed_tests": 0,
            "failed_tests": 0,
            "quality_scores": [],
            "detailed_results": []
        }
        
        for task in test_tasks:
            print(f"\n📝 Тестирование: {task['name']} ({task['complexity']})")
            print(f"Задача: {task['description']}")
            
            # Генерируем код через агента
            generated_code = self._request_code_from_agent(task['description'])
            
            if generated_code:
                # Анализируем качество сгенерированного кода
                quality_score = self._analyze_code_quality(generated_code, task)
                
                results["quality_scores"].append(quality_score)
                results["detailed_results"].append({
                    "task": task['name'],
                    "complexity": task['complexity'],
                    "code_length": len(generated_code),
                    "quality_score": quality_score,
                    "generated_code": generated_code[:500] + "..." if len(generated_code) > 500 else generated_code
                })
                
                if quality_score["total_score"] >= 7.0:
                    results["passed_tests"] += 1
                    print(f"✅ PASSED - Качество: {quality_score['total_score']:.1f}/10")
                else:
                    results["failed_tests"] += 1
                    print(f"❌ FAILED - Качество: {quality_score['total_score']:.1f}/10")
            else:
                results["failed_tests"] += 1
                results["detailed_results"].append({
                    "task": task['name'],
                    "complexity": task['complexity'],
                    "error": "Не удалось получить код от агента"
                })
                print("❌ FAILED - Агент не сгенерировал код")
        
        # Вычисляем общую оценку
        if results["quality_scores"]:
            avg_score = sum(score["total_score"] for score in results["quality_scores"]) / len(results["quality_scores"])
            results["average_quality"] = avg_score
            results["success_rate"] = (results["passed_tests"] / results["total_tests"]) * 100
        else:
            results["average_quality"] = 0.0
            results["success_rate"] = 0.0
        
        return results
    
    def _request_code_from_agent(self, task_description: str) -> str:
        """Запрос кода от агента"""
        try:
            # Формируем запрос к агенту
            prompt = f"""
            Напиши Python код для следующей задачи: {task_description}
            
            Требования:
            - Код должен быть чистым и читаемым
            - Добавь docstrings и комментарии
            - Используй type hints где возможно
            - Следуй PEP 8
            - Добавь обработку ошибок где нужно
            
            Верни только код без дополнительных объяснений.
            """
            
            # Запрос к LLM API
            response = requests.post(
                f"{self.llm_url}/v1/chat/completions",
                json={
                    "model": "enhanced-model",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.1
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    generated_text = data["choices"][0]["message"]["content"]
                    # Извлекаем код из ответа (убираем markdown форматирование)
                    code = self._extract_code_from_response(generated_text)
                    return code
            
            print(f"⚠️ Ошибка запроса к LLM: {response.status_code}")
            return ""
            
        except Exception as e:
            print(f"⚠️ Ошибка при запросе кода: {e}")
            return ""
    
    def _extract_code_from_response(self, response_text: str) -> str:
        """Извлекает Python код из ответа агента"""
        # Ищем код в markdown блоках
        code_blocks = re.findall(r'```python\n(.*?)\n```', response_text, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()
        
        # Ищем код в обычных блоках
        code_blocks = re.findall(r'```\n(.*?)\n```', response_text, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()
        
        # Если нет блоков, возвращаем весь текст
        return response_text.strip()
    
    def _analyze_code_quality(self, code: str, task: Dict) -> Dict[str, Any]:
        """Анализирует качество сгенерированного кода"""
        quality_metrics = {
            "syntax_valid": 0,
            "has_docstrings": 0,
            "has_type_hints": 0,
            "follows_pep8": 0,
            "has_error_handling": 0,
            "meets_requirements": 0,
            "code_complexity": 0,
            "readability": 0,
            "total_score": 0
        }
        
        # 1. Проверка синтаксиса (2 балла)
        try:
            ast.parse(code)
            quality_metrics["syntax_valid"] = 2.0
            print("  ✅ Синтаксис корректен")
        except SyntaxError as e:
            quality_metrics["syntax_valid"] = 0.0
            print(f"  ❌ Синтаксическая ошибка: {e}")
        
        # 2. Проверка docstrings (1 балл)
        if '"""' in code or "'''" in code:
            quality_metrics["has_docstrings"] = 1.0
            print("  ✅ Есть docstrings")
        else:
            print("  ⚠️ Нет docstrings")
        
        # 3. Проверка type hints (1 балл)
        if "->" in code or ": " in code:
            quality_metrics["has_type_hints"] = 1.0
            print("  ✅ Есть type hints")
        else:
            print("  ⚠️ Нет type hints")
        
        # 4. Проверка PEP 8 (1 балл)
        pep8_score = self._check_pep8_compliance(code)
        quality_metrics["follows_pep8"] = pep8_score
        if pep8_score > 0.5:
            print(f"  ✅ PEP 8 соблюдается ({pep8_score:.1f}/1.0)")
        else:
            print(f"  ⚠️ PEP 8 нарушается ({pep8_score:.1f}/1.0)")
        
        # 5. Проверка обработки ошибок (1 балл)
        if "try:" in code and "except" in code:
            quality_metrics["has_error_handling"] = 1.0
            print("  ✅ Есть обработка ошибок")
        elif task["complexity"] == "simple":
            quality_metrics["has_error_handling"] = 0.5  # Для простых задач не критично
            print("  ⚠️ Нет обработки ошибок (но для простой задачи допустимо)")
        else:
            print("  ❌ Нет обработки ошибок")
        
        # 6. Соответствие требованиям (2 балла)
        requirements_score = self._check_requirements_compliance(code, task)
        quality_metrics["meets_requirements"] = requirements_score
        if requirements_score >= 1.5:
            print(f"  ✅ Требования выполнены ({requirements_score:.1f}/2.0)")
        else:
            print(f"  ⚠️ Требования выполнены частично ({requirements_score:.1f}/2.0)")
        
        # 7. Сложность кода (1 балл)
        complexity_score = self._analyze_code_complexity(code)
        quality_metrics["code_complexity"] = complexity_score
        if complexity_score > 0.7:
            print(f"  ✅ Хорошая сложность кода ({complexity_score:.1f}/1.0)")
        else:
            print(f"  ⚠️ Проблемы со сложностью ({complexity_score:.1f}/1.0)")
        
        # 8. Читаемость (1 балл)
        readability_score = self._analyze_readability(code)
        quality_metrics["readability"] = readability_score
        if readability_score > 0.7:
            print(f"  ✅ Хорошая читаемость ({readability_score:.1f}/1.0)")
        else:
            print(f"  ⚠️ Проблемы с читаемостью ({readability_score:.1f}/1.0)")
        
        # Общий балл
        total = sum(quality_metrics.values()) - quality_metrics["total_score"]  # Исключаем total_score из суммы
        quality_metrics["total_score"] = total
        
        return quality_metrics
    
    def _check_pep8_compliance(self, code: str) -> float:
        """Проверка соответствия PEP 8"""
        score = 1.0
        
        # Проверяем основные правила PEP 8
        lines = code.split('\n')
        
        for line in lines:
            # Длинные строки
            if len(line) > 120:
                score -= 0.1
            
            # Trailing whitespace
            if line.endswith(' ') or line.endswith('\t'):
                score -= 0.05
        
        # Проверяем именование
        if not re.search(r'def [a-z_][a-z0-9_]*\(', code):
            if 'def ' in code:  # Есть функции, но именование неправильное
                score -= 0.2
        
        return max(0.0, score)
    
    def _check_requirements_compliance(self, code: str, task: Dict) -> float:
        """Проверка соответствия требованиям задачи"""
        expected_elements = task.get("expected_elements", [])
        found_elements = 0
        
        for element in expected_elements:
            if element.lower() in code.lower():
                found_elements += 1
        
        if expected_elements:
            return (found_elements / len(expected_elements)) * 2.0
        else:
            return 1.0  # Если нет конкретных требований
    
    def _analyze_code_complexity(self, code: str) -> float:
        """Анализ сложности кода"""
        try:
            tree = ast.parse(code)
            
            # Подсчитываем различные элементы
            functions = len([node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)])
            classes = len([node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)])
            loops = len([node for node in ast.walk(tree) if isinstance(node, (ast.For, ast.While))])
            conditions = len([node for node in ast.walk(tree) if isinstance(node, ast.If)])
            
            # Простая оценка сложности
            complexity = functions + classes * 2 + loops + conditions
            
            # Нормализуем (оптимальная сложность 2-8)
            if 2 <= complexity <= 8:
                return 1.0
            elif complexity < 2:
                return 0.5  # Слишком простой
            else:
                return max(0.1, 1.0 - (complexity - 8) * 0.1)  # Слишком сложный
                
        except:
            return 0.5  # Если не можем проанализировать
    
    def _analyze_readability(self, code: str) -> float:
        """Анализ читаемости кода"""
        score = 1.0
        lines = code.split('\n')
        
        # Проверяем комментарии
        comment_lines = [line for line in lines if line.strip().startswith('#')]
        if len(comment_lines) / max(len(lines), 1) < 0.1:
            score -= 0.2  # Мало комментариев
        
        # Проверяем пустые строки для разделения логических блоков
        empty_lines = [line for line in lines if not line.strip()]
        if len(empty_lines) / max(len(lines), 1) < 0.05:
            score -= 0.1  # Мало пустых строк
        
        # Проверяем длину функций
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 10
                    if func_lines > 50:
                        score -= 0.2  # Слишком длинная функция
        except:
            pass
        
        return max(0.0, score)
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Генерирует отчет о качестве кода агентов"""
        report = f"""
# 🧪 Отчет о качестве кода, генерируемого агентами

## 📊 Общие результаты
- **Всего тестов:** {results['total_tests']}
- **Пройдено:** {results['passed_tests']}
- **Провалено:** {results['failed_tests']}
- **Процент успеха:** {results['success_rate']:.1f}%
- **Средняя оценка качества:** {results['average_quality']:.1f}/10

## 🎯 Оценка качества

"""
        
        if results['average_quality'] >= 8.0:
            report += "### ✅ ОТЛИЧНО (8.0+)\nАгенты генерируют высококачественный код!\n"
        elif results['average_quality'] >= 7.0:
            report += "### ✅ ХОРОШО (7.0-7.9)\nАгенты генерируют качественный код с небольшими недочетами.\n"
        elif results['average_quality'] >= 5.0:
            report += "### ⚠️ УДОВЛЕТВОРИТЕЛЬНО (5.0-6.9)\nАгенты генерируют приемлемый код, но есть проблемы.\n"
        else:
            report += "### ❌ НЕУДОВЛЕТВОРИТЕЛЬНО (<5.0)\nКачество кода агентов требует значительного улучшения.\n"
        
        report += "\n## 📋 Детальные результаты\n\n"
        
        for result in results['detailed_results']:
            if 'error' in result:
                report += f"### ❌ {result['task']} ({result['complexity']})\n"
                report += f"**Ошибка:** {result['error']}\n\n"
            else:
                score = result['quality_score']
                report += f"### {'✅' if score['total_score'] >= 7.0 else '❌'} {result['task']} ({result['complexity']})\n"
                report += f"**Общая оценка:** {score['total_score']:.1f}/10\n"
                report += f"**Длина кода:** {result['code_length']} символов\n\n"
                
                report += "**Детальные метрики:**\n"
                report += f"- Синтаксис: {score['syntax_valid']:.1f}/2.0\n"
                report += f"- Docstrings: {score['has_docstrings']:.1f}/1.0\n"
                report += f"- Type hints: {score['has_type_hints']:.1f}/1.0\n"
                report += f"- PEP 8: {score['follows_pep8']:.1f}/1.0\n"
                report += f"- Обработка ошибок: {score['has_error_handling']:.1f}/1.0\n"
                report += f"- Соответствие требованиям: {score['meets_requirements']:.1f}/2.0\n"
                report += f"- Сложность: {score['code_complexity']:.1f}/1.0\n"
                report += f"- Читаемость: {score['readability']:.1f}/1.0\n\n"
                
                report += "**Сгенерированный код:**\n```python\n"
                report += result['generated_code']
                report += "\n```\n\n"
        
        return report

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования качества кода агентов")
    
    tester = AgentCodeQualityTester()
    results = tester.test_agent_code_generation()
    
    # Генерируем отчет
    report = tester.generate_report(results)
    
    # Сохраняем отчет
    report_file = f"AGENT_CODE_QUALITY_REPORT_{time.strftime('%Y-%m-%d')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📄 Отчет сохранен в файл: {report_file}")
    
    # Выводим краткие результаты
    print(f"\n🎯 ИТОГОВАЯ ОЦЕНКА КАЧЕСТВА КОДА АГЕНТОВ: {results['average_quality']:.1f}/10")
    print(f"📊 Процент успешных тестов: {results['success_rate']:.1f}%")
    
    if results['average_quality'] >= 7.0:
        print("✅ Агенты генерируют качественный код!")
    else:
        print("⚠️ Качество кода агентов требует улучшения")
    
    return results

if __name__ == "__main__":
    main()