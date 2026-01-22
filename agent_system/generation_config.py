#!/usr/bin/env python3
"""
Оптимизированные настройки генерации для гибридной архитектуры
Основано на результатах eval: исправляем проблемы с отступами и обрывами
"""

from typing import Any, Dict


class GenerationConfig:
    """Конфигурация генерации для разных ролей"""
    
    @staticmethod
    def get_worker_config() -> Dict[str, Any]:
        """Настройки для локальных worker агентов"""
        return {
            "temperature": 0.1,           # Более детерминированная генерация
            "top_p": 0.9,
            "top_k": 50,
            "max_new_tokens": 1200,       # Увеличено для полных решений
            "min_new_tokens": 50,         # Минимум для избежания обрывов
            "do_sample": True,
            "pad_token_id": None,         # Устанавливается в runtime
            "eos_token_id": None,         # Устанавливается в runtime
            "repetition_penalty": 1.1,    # Избегаем повторений
            "length_penalty": 1.0,
            "no_repeat_ngram_size": 3,
            
            # Критично для исправления проблем форматирования
            "stop_sequences": [
                "\n\n\n",               # Избегаем лишних переносов
                "```\n\n",              # Правильное завершение code blocks
                "# End of",             # Избегаем комментариев завершения
                "def main():",          # Не генерируем main если не нужно
            ],
            
            # Принудительное форматирование
            "enforce_code_fences": True,
            "auto_indent": True,
        }
    
    @staticmethod
    def get_reviewer_config() -> Dict[str, Any]:
        """Настройки для reviewer агентов (проверка качества)"""
        return {
            "temperature": 0.05,          # Очень консервативно
            "top_p": 0.8,
            "max_new_tokens": 500,        # Короткие ответы для ревью
            "do_sample": False,           # Детерминированно
            "repetition_penalty": 1.2,
        }
    
    @staticmethod
    def get_director_config() -> Dict[str, Any]:
        """Настройки для OpenAI Director"""
        return {
            "model": "gpt-4o-mini",
            "temperature": 0.2,
            "max_tokens": 800,
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "response_format": {"type": "json_object"},
        }
    
    @staticmethod
    def apply_config(model, tokenizer, config: Dict[str, Any]) -> Dict[str, Any]:
        """Применяет конфигурацию с учётом модели и токенизатора"""
        
        # Устанавливаем токены если не заданы
        if config.get("pad_token_id") is None:
            config["pad_token_id"] = tokenizer.pad_token_id or tokenizer.eos_token_id
        
        if config.get("eos_token_id") is None:
            config["eos_token_id"] = tokenizer.eos_token_id
        
        # Удаляем кастомные параметры которые не поддерживает transformers
        transformers_config = {k: v for k, v in config.items() 
                             if k not in ["enforce_code_fences", "auto_indent", "stop_sequences"]}
        
        return transformers_config


class CodeFormatter:
    """Пост-обработка сгенерированного кода"""
    
    @staticmethod
    def fix_indentation(code: str) -> str:
        """Исправляет проблемы с отступами"""
        lines = code.split('\n')
        fixed_lines = []
        indent_level = 0
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                fixed_lines.append('')
                continue
            
            # Определяем нужный уровень отступов
            if stripped.endswith(':'):
                # Начало блока
                fixed_lines.append('    ' * indent_level + stripped)
                indent_level += 1
            elif stripped in ['else:', 'elif', 'except:', 'finally:']:
                # Специальные случаи
                indent_level = max(0, indent_level - 1)
                fixed_lines.append('    ' * indent_level + stripped)
                indent_level += 1
            elif stripped.startswith(('return', 'break', 'continue', 'pass', 'raise')):
                # Операторы в блоке
                fixed_lines.append('    ' * indent_level + stripped)
            else:
                # Обычная строка
                fixed_lines.append('    ' * indent_level + stripped)
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def ensure_code_fences(code: str) -> str:
        """Добавляет code fences если их нет"""
        if not code.strip().startswith('```'):
            code = f"```python\n{code}\n```"
        return code
    
    @staticmethod
    def remove_incomplete_lines(code: str) -> str:
        """Удаляет незавершённые строки в конце"""
        lines = code.split('\n')
        
        # Ищем последнюю завершённую строку
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line and not line.endswith(('\\', ',')):
                # Найдена завершённая строка
                return '\n'.join(lines[:i+1])
        
        return code
    
    @staticmethod
    def post_process(code: str, enforce_fences: bool = True) -> str:
        """Полная пост-обработка кода"""
        
        # 1. Удаляем незавершённые строки
        code = CodeFormatter.remove_incomplete_lines(code)
        
        # 2. Исправляем отступы
        code = CodeFormatter.fix_indentation(code)
        
        # 3. Добавляем code fences если нужно
        if enforce_fences:
            code = CodeFormatter.ensure_code_fences(code)
        
        return code


# Пример использования
def example_usage():
    """Пример использования конфигураций"""
    
    # Для worker агентов
    worker_config = GenerationConfig.get_worker_config()
    print("Worker config:", worker_config)
    
    # Для reviewer агентов  
    reviewer_config = GenerationConfig.get_reviewer_config()
    print("Reviewer config:", reviewer_config)
    
    # Для Director
    director_config = GenerationConfig.get_director_config()
    print("Director config:", director_config)
    
    # Пост-обработка кода
    broken_code = """def hello():
print("Hello")
    if True:
print("World")
return "Done"
    """
    
    fixed_code = CodeFormatter.post_process(broken_code)
    print("Fixed code:")
    print(fixed_code)


if __name__ == "__main__":
    example_usage()