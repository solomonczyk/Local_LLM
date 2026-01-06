#!/usr/bin/env python3
"""
Тест качества работы мультиагентной системы
Оценивает: полноту, точность, релевантность, консистентность ответов
"""
import json
import time
from typing import Dict, List, Any
from agent_runtime.orchestrator import get_orchestrator


class MultiAgentQualityTester:
    """Тестер качества мультиагентной системы"""

    def __init__(self):
        self.orchestrator = get_orchestrator()
        self.test_results = []

    def evaluate_response_quality(
        self, task: str, response: Dict[str, Any], expected_elements: List[str] = None
    ) -> Dict[str, Any]:
        """Оценка качества ответа"""

        if not response.get("success", False):
            return {
                "overall_score": 0,
                "completeness": 0,
                "accuracy": 0,
                "relevance": 0,
                "consistency": 0,
                "error": response.get("error", "Unknown error"),
            }

        # Получаем текст ответа
        if response.get("mode") == "consilium":
            # Консилиум - анализируем мнения агентов
            opinions = response.get("opinions", {})
            response_text = "\n".join([f"{agent}: {data.get('opinion', '')}" for agent, data in opinions.items()])
            director_decision = response.get("director_decision", "")
            if director_decision:
                response_text += f"\nDirector: {director_decision}"
        else:
            # Одиночный агент
            response_text = response.get("response", "")

        # Метрики качества
        completeness = self._evaluate_completeness(task, response_text, expected_elements)
        accuracy = self._evaluate_accuracy(task, response_text)
        relevance = self._evaluate_relevance(task, response_text)
        consistency = self._evaluate_consistency(response)

        overall_score = (completeness + accuracy + relevance + consistency) / 4

        return {
            "overall_score": round(overall_score, 2),
            "completeness": round(completeness, 2),
            "accuracy": round(accuracy, 2),
            "relevance": round(relevance, 2),
            "consistency": round(consistency, 2),
            "response_length": len(response_text),
            "response_text": response_text[:200] + "..." if len(response_text) > 200 else response_text,
        }

    def _evaluate_completeness(self, task: str, response: str, expected_elements: List[str] = None) -> float:
        """Оценка полноты ответа (0-10)"""
        if not response or len(response) < 50:
            return 2.0  # Слишком короткий ответ

        score = 5.0  # Базовая оценка

        # Проверяем наличие ожидаемых элементов
        if expected_elements:
            found_elements = sum(1 for elem in expected_elements if elem.lower() in response.lower())
            element_score = (found_elements / len(expected_elements)) * 3.0
            score += element_score

        # Проверяем структурированность ответа
        if any(marker in response for marker in ["1.", "2.", "3.", "•", "-", "**", "##"]):
            score += 1.0  # Структурированный ответ

        # Проверяем наличие примеров или деталей
        if any(word in response.lower() for word in ["например", "example", "пример", "детали"]):
            score += 1.0

        return min(score, 10.0)

    def _evaluate_accuracy(self, task: str, response: str) -> float:
        """Оценка точности ответа (0-10)"""
        score = 7.0  # Базовая оценка (предполагаем корректность)

        # Проверяем на наличие ошибок или неточностей
        error_indicators = ["[error]", "[llm_error]", "[connection_error]", "не могу", "не знаю", "ошибка", "error"]

        for indicator in error_indicators:
            if indicator.lower() in response.lower():
                score -= 2.0
                break

        # Проверяем техническую корректность для разных типов задач
        if "security" in task.lower():
            security_terms = ["vulnerability", "authentication", "authorization", "encryption"]
            if any(term in response.lower() for term in security_terms):
                score += 1.0

        if "architecture" in task.lower():
            arch_terms = ["scalability", "design", "pattern", "component"]
            if any(term in response.lower() for term in arch_terms):
                score += 1.0

        return max(min(score, 10.0), 0.0)

    def _evaluate_relevance(self, task: str, response: str) -> float:
        """Оценка релевантности ответа (0-10)"""
        if not response:
            return 0.0

        # Извлекаем ключевые слова из задачи
        task_words = set(task.lower().split())
        response_words = set(response.lower().split())

        # Пересечение ключевых слов
        common_words = task_words.intersection(response_words)
        relevance_ratio = len(common_words) / len(task_words) if task_words else 0

        base_score = relevance_ratio * 6.0

        # Бонусы за контекстную релевантность
        if len(response) > 100:  # Достаточно подробный ответ
            base_score += 2.0

        if any(word in response.lower() for word in ["рекомендую", "предлагаю", "следует", "recommend"]):
            base_score += 1.0  # Практические рекомендации

        if any(word in response.lower() for word in ["потому что", "так как", "because", "since"]):
            base_score += 1.0  # Объяснения

        return min(base_score, 10.0)

    def _evaluate_consistency(self, response: Dict[str, Any]) -> float:
        """Оценка консистентности ответа (0-10)"""
        score = 8.0  # Базовая оценка

        # Для консилиума проверяем согласованность мнений
        if response.get("mode") == "consilium":
            opinions = response.get("opinions", {})
            if len(opinions) > 1:
                # Проверяем наличие противоречий
                opinion_texts = [data.get("opinion", "") for data in opinions.values()]

                # Простая проверка на противоречия
                positive_indicators = ["хорошо", "отлично", "рекомендую", "good", "excellent"]
                negative_indicators = ["плохо", "не рекомендую", "проблема", "bad", "issue"]

                positive_count = sum(
                    1 for text in opinion_texts for indicator in positive_indicators if indicator in text.lower()
                )
                negative_count = sum(
                    1 for text in opinion_texts for indicator in negative_indicators if indicator in text.lower()
                )

                if positive_count > 0 and negative_count > 0:
                    score -= 1.0  # Есть противоречия, но это может быть нормально

        # Проверяем структурную консистентность
        if response.get("success") and not response.get("response", "").strip():
            score -= 3.0  # Успех, но пустой ответ

        return max(score, 0.0)

    def run_quality_tests(self) -> Dict[str, Any]:
        """Запуск тестов качества"""

        test_cases = [
            {
                "name": "Simple Question",
                "task": "What is Python?",
                "mode": "single",
                "expected_elements": ["programming", "language", "high-level"],
                "expected_score_range": (6.0, 9.0),
            },
            {
                "name": "Security Analysis",
                "task": "Review JWT authentication security",
                "mode": "consilium",
                "expected_elements": ["security", "token", "authentication", "vulnerability"],
                "expected_score_range": (7.0, 10.0),
            },
            {
                "name": "Architecture Design",
                "task": "Design microservice architecture for e-commerce",
                "mode": "consilium",
                "expected_elements": ["microservice", "architecture", "scalability", "design"],
                "expected_score_range": (7.0, 10.0),
            },
            {
                "name": "Code Review",
                "task": "Review this code for best practices and potential issues",
                "mode": "single",
                "expected_elements": ["code", "review", "best practices", "issues"],
                "expected_score_range": (6.0, 9.0),
            },
            {
                "name": "Two-pass Triage",
                "task": "Create a simple hello world function",
                "mode": "twopass",
                "expected_elements": ["function", "hello", "world"],
                "expected_score_range": (6.0, 9.0),
            },
        ]

        results = []

        print("🧪 Запуск тестов качества мультиагентной системы")
        print("=" * 60)

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📋 Тест {i}/{len(test_cases)}: {test_case['name']}")
            print(f"   Задача: {test_case['task'][:50]}...")
            print(f"   Режим: {test_case['mode']}")

            start_time = time.time()

            # Выполняем тест
            if test_case["mode"] == "consilium":
                response = self.orchestrator.execute_task(test_case["task"], use_consilium=True)
            elif test_case["mode"] == "twopass":
                response = self.orchestrator.execute_task(test_case["task"], two_pass=True)
            else:
                response = self.orchestrator.execute_task(test_case["task"])

            execution_time = time.time() - start_time

            # Оценка качества
            quality = self.evaluate_response_quality(test_case["task"], response, test_case["expected_elements"])

            # Проверка соответствия ожидаемому диапазону
            expected_min, expected_max = test_case["expected_score_range"]
            score_in_range = expected_min <= quality["overall_score"] <= expected_max

            result = {
                "test_name": test_case["name"],
                "task": test_case["task"],
                "mode": test_case["mode"],
                "execution_time": round(execution_time, 2),
                "quality_metrics": quality,
                "expected_range": test_case["expected_score_range"],
                "score_in_range": score_in_range,
                "success": response.get("success", False),
            }

            results.append(result)

            # Вывод результатов
            print(f"   ⏱️  Время выполнения: {execution_time:.2f}с")
            print(f"   📊 Общая оценка: {quality['overall_score']}/10")
            print(f"   📋 Полнота: {quality['completeness']}/10")
            print(f"   🎯 Точность: {quality['accuracy']}/10")
            print(f"   🔗 Релевантность: {quality['relevance']}/10")
            print(f"   🔄 Консистентность: {quality['consistency']}/10")
            print(f"   ✅ В ожидаемом диапазоне: {'Да' if score_in_range else 'Нет'}")

            if not response.get("success", False):
                print(f"   ❌ Ошибка: {response.get('error', 'Unknown')}")

        return {"test_results": results, "summary": self._generate_summary(results)}

    def _generate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Генерация сводки результатов"""

        total_tests = len(results)
        successful_tests = sum(1 for r in results if r["success"])
        tests_in_range = sum(1 for r in results if r["score_in_range"])

        if successful_tests > 0:
            avg_overall = sum(r["quality_metrics"]["overall_score"] for r in results if r["success"]) / successful_tests
            avg_completeness = (
                sum(r["quality_metrics"]["completeness"] for r in results if r["success"]) / successful_tests
            )
            avg_accuracy = sum(r["quality_metrics"]["accuracy"] for r in results if r["success"]) / successful_tests
            avg_relevance = sum(r["quality_metrics"]["relevance"] for r in results if r["success"]) / successful_tests
            avg_consistency = (
                sum(r["quality_metrics"]["consistency"] for r in results if r["success"]) / successful_tests
            )
            avg_execution_time = sum(r["execution_time"] for r in results if r["success"]) / successful_tests
        else:
            avg_overall = avg_completeness = avg_accuracy = avg_relevance = avg_consistency = avg_execution_time = 0

        return {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": round((successful_tests / total_tests) * 100, 1) if total_tests > 0 else 0,
            "tests_in_expected_range": tests_in_range,
            "range_accuracy": round((tests_in_range / total_tests) * 100, 1) if total_tests > 0 else 0,
            "average_metrics": {
                "overall_score": round(avg_overall, 2),
                "completeness": round(avg_completeness, 2),
                "accuracy": round(avg_accuracy, 2),
                "relevance": round(avg_relevance, 2),
                "consistency": round(avg_consistency, 2),
                "execution_time": round(avg_execution_time, 2),
            },
        }


def main():
    """Основная функция тестирования"""

    tester = MultiAgentQualityTester()
    results = tester.run_quality_tests()

    print("\n" + "=" * 60)
    print("📊 СВОДКА РЕЗУЛЬТАТОВ ТЕСТИРОВАНИЯ КАЧЕСТВА")
    print("=" * 60)

    summary = results["summary"]

    print(f"📋 Всего тестов: {summary['total_tests']}")
    print(f"✅ Успешных: {summary['successful_tests']} ({summary['success_rate']}%)")
    print(f"🎯 В ожидаемом диапазоне: {summary['tests_in_expected_range']} ({summary['range_accuracy']}%)")

    print(f"\n📊 Средние метрики качества:")
    avg = summary["average_metrics"]
    print(f"   🏆 Общая оценка: {avg['overall_score']}/10")
    print(f"   📋 Полнота: {avg['completeness']}/10")
    print(f"   🎯 Точность: {avg['accuracy']}/10")
    print(f"   🔗 Релевантность: {avg['relevance']}/10")
    print(f"   🔄 Консистентность: {avg['consistency']}/10")
    print(f"   ⏱️  Среднее время: {avg['execution_time']}с")

    # Оценка общего качества системы
    overall_quality = avg["overall_score"]
    if overall_quality >= 8.0:
        quality_level = "ОТЛИЧНО"
        emoji = "🏆"
    elif overall_quality >= 7.0:
        quality_level = "ХОРОШО"
        emoji = "✅"
    elif overall_quality >= 6.0:
        quality_level = "УДОВЛЕТВОРИТЕЛЬНО"
        emoji = "⚠️"
    else:
        quality_level = "ТРЕБУЕТ УЛУЧШЕНИЯ"
        emoji = "❌"

    print(f"\n{emoji} ОБЩАЯ ОЦЕНКА КАЧЕСТВА: {quality_level} ({overall_quality}/10)")

    # Сохранение результатов
    with open("multiagent_quality_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Детальные результаты сохранены в: multiagent_quality_results.json")

    return overall_quality >= 6.0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
