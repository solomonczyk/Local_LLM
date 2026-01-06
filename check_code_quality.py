#!/usr/bin/env python3
"""
Скрипт для проверки и исправления качества кода
"""
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Выполнить команду и показать результат"""
    print(f"\n🔧 {description}")
    print("=" * 60)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
            
        if result.returncode != 0:
            print(f"❌ Команда завершилась с кодом {result.returncode}")
            return False
        else:
            print("✅ Успешно выполнено")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
        return False


def main():
    """Основная функция проверки качества кода"""
    print("🚀 Проверка и исправление качества кода")
    print("=" * 60)
    
    # Список команд для выполнения
    commands = [
        (
            "python -m black agent_runtime/ agent_system/ *.py --line-length=120 --exclude='/(codesearchnet_python_1pct|lora_qwen2_5_coder_1_5b_python)/'",
            "Форматирование кода с помощью Black"
        ),
        (
            "python -m isort agent_runtime/ agent_system/ *.py --skip-glob='**/codesearchnet_python_1pct*' --skip-glob='**/lora_qwen2_5_coder_1_5b_python*'",
            "Сортировка импортов с помощью isort"
        ),
        (
            "python -m flake8 agent_runtime/ agent_system/ --max-line-length=120 --extend-ignore=E203,W503 --exclude=codesearchnet_python_1pct,lora_qwen2_5_coder_1_5b_python",
            "Проверка стиля кода с помощью flake8"
        ),
        (
            "python code_quality_analyzer.py",
            "Анализ качества кода"
        )
    ]
    
    success_count = 0
    total_count = len(commands)
    
    for cmd, description in commands:
        if run_command(cmd, description):
            success_count += 1
    
    print(f"\n📊 Результат: {success_count}/{total_count} команд выполнено успешно")
    
    if success_count == total_count:
        print("🎉 Все проверки пройдены успешно!")
        return True
    else:
        print("⚠️ Некоторые проверки не прошли. Проверьте вывод выше.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)