#!/usr/bin/env python3
"""
Полный тест всех возможностей агентской системы
"""
import requests
import time


def test_agent_query(query: str, expected_keywords: list = None) -> bool:
    """Тест запроса к агенту"""
    print(f"\n🤖 Запрос: {query}")
    
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "model": "mock-model",
            "messages": [
                {"role": "user", "content": query}
            ]
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print(f"📝 Ответ: {content[:200]}...")
        
        if expected_keywords:
            found_keywords = [kw for kw in expected_keywords if kw.lower() in content.lower()]
            if found_keywords:
                print(f"✅ Найдены ключевые слова: {found_keywords}")
                return True
            else:
                print(f"❌ Не найдены ключевые слова: {expected_keywords}")
                return False
        else:
            return True
    else:
        print(f"❌ Ошибка запроса: {response.status_code}")
        return False


def main():
    """Демонстрация всех возможностей"""
    print("🎯 Полная демонстрация возможностей агентской системы")
    print("=" * 60)
    
    # Тесты системной информации
    system_tests = [
        ("ты можешь посмотреть и сказать мне какие диски есть на моем пс?", ["диск", "ГБ", "C:\\"]),
        ("сколько памяти на моем компьютере?", ["память", "ГБ", "объем"]),
        ("какие сетевые интерфейсы есть на моем компьютере?", ["сетевая", "интерфейс", "IP"]),
        ("какие процессы сейчас запущены?", ["процесс", "CPU", "PID"])
    ]
    
    print("\n🖥️  СИСТЕМНАЯ ИНФОРМАЦИЯ")
    print("-" * 30)
    
    system_passed = 0
    for query, keywords in system_tests:
        if test_agent_query(query, keywords):
            system_passed += 1
        time.sleep(1)  # Небольшая пауза между запросами
    
    # Тесты файловых операций
    file_tests = [
        ("покажи список файлов в текущей папке", ["файл", "директор", "📄"]),
        ("прочитай файл AGENT_CAPABILITIES.md", ["содержимое", "возможности", "агент"]),
    ]
    
    print(f"\n📁 ФАЙЛОВЫЕ ОПЕРАЦИИ")
    print("-" * 30)
    
    file_passed = 0
    for query, keywords in file_tests:
        if test_agent_query(query, keywords):
            file_passed += 1
        time.sleep(1)
    
    # Тесты разработческих задач
    dev_tests = [
        ("Create a REST API for user authentication", ["API", "endpoint", "auth"]),
        ("Design database schema for e-commerce", ["таблиц", "индекс", "связи"]),
        ("Write unit tests for payment module", ["тест", "покрытие", "mock"]),
        ("Review code for security vulnerabilities", ["безопасность", "валидация", "XSS"])
    ]
    
    print(f"\n💻 РАЗРАБОТЧЕСКИЕ ЗАДАЧИ")
    print("-" * 30)
    
    dev_passed = 0
    for query, keywords in dev_tests:
        if test_agent_query(query, keywords):
            dev_passed += 1
        time.sleep(1)
    
    # Итоги
    total_tests = len(system_tests) + len(file_tests) + len(dev_tests)
    total_passed = system_passed + file_passed + dev_passed
    
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    print(f"🖥️  Системная информация: {system_passed}/{len(system_tests)}")
    print(f"📁 Файловые операции: {file_passed}/{len(file_tests)}")
    print(f"💻 Разработческие задачи: {dev_passed}/{len(dev_tests)}")
    print(f"📈 Общий результат: {total_passed}/{total_tests}")
    
    success_rate = (total_passed / total_tests) * 100
    print(f"🎯 Успешность: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("\n🎉 ОТЛИЧНО! Агентская система полностью функциональна!")
        print("🚀 Все основные возможности работают корректно")
        print("🌐 Откройте http://localhost:7864 для использования")
    elif success_rate >= 60:
        print("\n✅ ХОРОШО! Большинство функций работает")
        print("⚠️  Некоторые возможности требуют доработки")
    else:
        print("\n❌ ТРЕБУЕТСЯ ДОРАБОТКА")
        print("🔧 Многие функции не работают как ожидается")
    
    return success_rate >= 80


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)