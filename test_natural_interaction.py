#!/usr/bin/env python3
"""
Тест естественного взаимодействия с агентом
"""
import requests
import time

def test_conversation_memory():
    """Тест памяти диалога"""
    print("=== Testing Conversation Memory ===")

    # Первое сообщение
    response1 = requests.post(
        "http://localhost:8010/v1/chat/completions",
        json={
            "model": "enhanced-model",
            "messages": [{"role": "user", "content": "Привет! Меня зовут Алексей, я разрабатываю Python проект"}],
        },
    )

    if response1.status_code == 200:
        data1 = response1.json()
        content1 = data1["choices"][0]["message"]["content"]
        print(f"✅ Первый ответ: {content1[:200]}...")

        # Второе сообщение - проверяем память
        time.sleep(1)
        response2 = requests.post(
            "http://localhost:8010/v1/chat/completions",
            json={
                "model": "enhanced-model",
                "messages": [
                    {"role": "user", "content": "Привет! Меня зовут Алексей, я разрабатываю Python проект"},
                    {"role": "assistant", "content": content1},
                    {"role": "user", "content": "Как мне лучше организовать структуру проекта?"},
                ],
            },
        )

        if response2.status_code == 200:
            data2 = response2.json()
            content2 = data2["choices"][0]["message"]["content"]
            print(f"✅ Второй ответ: {content2[:200]}...")

            # Проверяем, что агент помнит контекст
            if "python" in content2.lower() or "проект" in content2.lower():
                print("✅ Агент помнит контекст диалога!")
                return True
            else:
                print("❌ Агент не использует контекст")
                return False
        else:
            print(f"❌ Ошибка второго запроса: {response2.status_code}")
            return False
    else:
        print(f"❌ Ошибка первого запроса: {response1.status_code}")
        return False

def test_proactive_suggestions():
    """Тест проактивных предложений"""
    print("\n=== Testing Proactive Suggestions ===")

    response = requests.post(
        "http://localhost:8010/v1/chat/completions",
        json={
            "model": "enhanced-model",
            "messages": [{"role": "user", "content": "Хочу создать новый проект, но не знаю с чего начать"}],
        },
    )

    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print(f"✅ Ответ: {content[:300]}...")

        # Проверяем наличие проактивных элементов
        proactive_indicators = ["💡", "предложения", "❓", "вопросы", "рекомендую"]
        found_indicators = [ind for ind in proactive_indicators if ind.lower() in content.lower()]

        if found_indicators:
            print(f"✅ Найдены проактивные элементы: {found_indicators}")
            return True
        else:
            print("❌ Проактивные элементы не найдены")
            return False
    else:
        print(f"❌ Ошибка запроса: {response.status_code}")
        return False

def test_file_operations_with_context():
    """Тест файловых операций с контекстом"""
    print("\n=== Testing File Operations with Context ===")

    response = requests.post(
        "http://localhost:8010/v1/chat/completions",
        json={
            "model": "enhanced-model",
            "messages": [{"role": "user", "content": "покажи список файлов в текущей папке"}],
        },
    )

    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print(f"✅ Ответ: {content[:300]}...")

        # Проверяем, что показаны файлы
        if "📄" in content and "📁" in content:
            print("✅ Агент показал список файлов с иконками!")
            return True
        else:
            print("❌ Список файлов не показан корректно")
            return False
    else:
        print(f"❌ Ошибка запроса: {response.status_code}")
        return False

def test_system_info_integration():
    """Тест интеграции системной информации"""
    print("\n=== Testing System Info Integration ===")

    response = requests.post(
        "http://localhost:8010/v1/chat/completions",
        json={
            "model": "enhanced-model",
            "messages": [{"role": "user", "content": "сколько памяти на моем компьютере?"}],
        },
    )

    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print(f"✅ Ответ: {content[:300]}...")

        # Проверяем наличие информации о памяти
        if "ГБ" in content and ("память" in content.lower() or "объем" in content.lower()):
            print("✅ Агент предоставил информацию о памяти!")
            return True
        else:
            print("❌ Информация о памяти не предоставлена")
            return False
    else:
        print(f"❌ Ошибка запроса: {response.status_code}")
        return False

def test_enhanced_mode():
    """Тест улучшенного режима"""
    print("\n=== Testing Enhanced Mode ===")

    response = requests.get("http://localhost:8010/health")

    if response.status_code == 200:
        data = response.json()
        enhanced_mode = data.get("enhanced_mode", False)

        if enhanced_mode:
            print("✅ Enhanced mode активен!")
            return True
        else:
            print("⚠️  Enhanced mode не активен, работает basic mode")
            return False
    else:
        print(f"❌ Ошибка проверки статуса: {response.status_code}")
        return False

def main():
    """Запуск всех тестов естественного взаимодействия"""
    print("🤖 Natural Interaction Test")
    print("=" * 50)

    tests = [
        ("Enhanced Mode Check", test_enhanced_mode),
        ("Conversation Memory", test_conversation_memory),
        ("Proactive Suggestions", test_proactive_suggestions),
        ("File Operations with Context", test_file_operations_with_context),
        ("System Info Integration", test_system_info_integration),
    ]

    passed = 0
    total = len(tests)

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {name}: PASSED")
            else:
                print(f"\n❌ {name}: FAILED")
        except Exception as e:
            print(f"\n💥 {name}: ERROR - {e}")

        time.sleep(1)  # Пауза между тестами

    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} tests passed")

    success_rate = (passed / total) * 100
    print(f"Success rate: {success_rate:.1f}%")

    if success_rate >= 80:
        print("\n🎉 ОТЛИЧНО! Естественное взаимодействие работает!")
        print("🤖 Агент может общаться как настоящий помощник")
        print("🌐 Откройте http://localhost:7864 для тестирования")
    elif success_rate >= 60:
        print("\n✅ ХОРОШО! Большинство функций естественного взаимодействия работает")
    else:
        print("\n❌ ТРЕБУЕТСЯ ДОРАБОТКА")
        print("🔧 Многие функции естественного взаимодействия не работают")

    return success_rate >= 80

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

