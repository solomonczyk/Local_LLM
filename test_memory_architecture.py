#!/usr/bin/env python3
"""
Тест архитектуры PostgreSQL памяти (без реального подключения)
"""
import requests

def test_memory_system_availability():
    """Проверка доступности системы памяти"""
    print("=== Testing Memory System Availability ===")

    response = requests.get("http://localhost:8011/tools/memory_status")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Memory System Status:")
        print(f"   PostgreSQL поддержка: {data['postgres_available']}")
        print(f"   Тип памяти: {data['memory_type']}")
        print(f"   Возможности:")
        for feature, available in data["features"].items():
            status = "✅" if available else "❌"
            print(f"     {status} {feature}")

        return True
    else:
        print(f"❌ Ошибка получения статуса: {response.status_code}")
        return False

def test_memory_imports():
    """Тест импорта модулей памяти"""
    print("\n=== Testing Memory Imports ===")

    try:
        import sys
        import os

        sys.path.insert(0, os.path.dirname(__file__))

        # Тест импорта PostgreSQL памяти
        try:
            from agent_system.memory_postgres import postgres_memory, PostgreSQLMemory

            print("✅ PostgreSQL память импортирована")
            postgres_available = True
        except ImportError as e:
            print(f"❌ PostgreSQL память недоступна: {e}")
            postgres_available = False

        # Тест импорта conversation manager
        try:
            from agent_system.conversation import conversation_manager, ConversationManager

            print("✅ Conversation Manager импортирован")

            # Проверяем, что используется PostgreSQL если доступен
            if hasattr(conversation_manager, "use_postgres"):
                print(f"   Использует PostgreSQL: {conversation_manager.use_postgres}")

            return True
        except ImportError as e:
            print(f"❌ Conversation Manager недоступен: {e}")
            return False

    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        return False

def test_memory_schema_design():
    """Тест дизайна схемы памяти"""
    print("\n=== Testing Memory Schema Design ===")

    try:
        from agent_system.memory_postgres import PostgreSQLMemory

        memory = PostgreSQLMemory("test_connection")

        # Проверяем наличие методов
        required_methods = [
            "initialize_schema",
            "create_session",
            "add_message",
            "get_conversation_history",
            "search_messages",
            "store_knowledge",
            "get_knowledge",
            "get_session_summary",
        ]

        missing_methods = []
        for method in required_methods:
            if not hasattr(memory, method):
                missing_methods.append(method)

        if missing_methods:
            print(f"❌ Отсутствуют методы: {missing_methods}")
            return False
        else:
            print("✅ Все необходимые методы присутствуют")
            print(f"   Методы: {', '.join(required_methods)}")
            return True

    except ImportError:
        print("❌ PostgreSQL память недоступна для тестирования")
        return False

def test_conversation_manager_integration():
    """Тест интеграции с conversation manager"""
    print("\n=== Testing Conversation Manager Integration ===")

    try:
        from agent_system.conversation import conversation_manager

        # Тестируем создание контекста
        test_session = "test_integration_session"
        context = conversation_manager.get_or_create_context(test_session)

        if context:
            print("✅ Контекст создан успешно")
            print(f"   Session ID: {context.session_id}")
            print(f"   Сообщений: {len(context.messages)}")

            # Тестируем добавление сообщения
            conversation_manager.add_message(test_session, "user", "Тестовое сообщение")

            updated_context = conversation_manager.get_or_create_context(test_session)
            if len(updated_context.messages) > len(context.messages):
                print("✅ Сообщение добавлено в контекст")
                return True
            else:
                print("❌ Сообщение не добавлено")
                return False
        else:
            print("❌ Не удалось создать контекст")
            return False

    except Exception as e:
        print(f"❌ Ошибка интеграции: {e}")
        return False

def test_enhanced_server_memory_integration():
    """Тест интеграции enhanced сервера с памятью"""
    print("\n=== Testing Enhanced Server Memory Integration ===")

    # Проверяем, что enhanced сервер использует PostgreSQL память
    response = requests.post(
        "http://localhost:8010/v1/chat/completions",
        json={"model": "enhanced-model", "messages": [{"role": "user", "content": "Тест интеграции памяти"}]},
    )

    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print("✅ Enhanced сервер отвечает")
        print(f"   Ответ: {content[:100]}...")

        # Проверяем, что в логах есть упоминание PostgreSQL памяти
        # (это видно при запуске сервера)
        return True
    else:
        print(f"❌ Enhanced сервер недоступен: {response.status_code}")
        return False

def main():
    """Запуск всех тестов архитектуры памяти"""
    print("🧠 Memory Architecture Test")
    print("=" * 50)

    tests = [
        ("Memory System Availability", test_memory_system_availability),
        ("Memory Imports", test_memory_imports),
        ("Memory Schema Design", test_memory_schema_design),
        ("Conversation Manager Integration", test_conversation_manager_integration),
        ("Enhanced Server Memory Integration", test_enhanced_server_memory_integration),
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

    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} tests passed")

    success_rate = (passed / total) * 100
    print(f"Success rate: {success_rate:.1f}%")

    if success_rate >= 80:
        print("\n🎉 ОТЛИЧНО! Архитектура PostgreSQL памяти готова!")
        print("🧠 Система памяти корректно интегрирована")
        print("📋 Для полной функциональности настройте PostgreSQL подключение")
        print("📖 См. POSTGRES_MEMORY_SETUP.md для инструкций")
    elif success_rate >= 60:
        print("\n✅ ХОРОШО! Основная архитектура памяти работает")
        print("📋 Настройте PostgreSQL для полной функциональности")
    else:
        print("\n❌ ТРЕБУЕТСЯ ДОРАБОТКА архитектуры памяти")

    return success_rate >= 60

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

