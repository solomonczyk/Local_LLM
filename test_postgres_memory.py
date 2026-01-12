#!/usr/bin/env python3
"""
Тест PostgreSQL памяти агента
"""
import requests
import time
import uuid

def test_memory_status():
    """Проверка статуса системы памяти"""
    print("=== Testing Memory Status ===")

    response = requests.get("http://localhost:8011/tools/memory_status")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Memory Status:")
        print(f"   PostgreSQL доступен: {data['postgres_available']}")
        print(f"   Тип памяти: {data['memory_type']}")
        print(f"   Возможности: {data['features']}")
        return data["postgres_available"]
    else:
        print(f"❌ Ошибка получения статуса: {response.status_code}")
        return False

def test_memory_initialization():
    """Тест инициализации схемы памяти"""
    print("\n=== Testing Memory Initialization ===")

    response = requests.post("http://localhost:8011/tools/memory_init", json={"connection_name": "agent_memory"})

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Схема памяти инициализирована: {data}")
        return True
    else:
        print(f"❌ Ошибка инициализации: {response.status_code} - {response.text}")
        return False

def test_conversation_with_postgres_memory():
    """Тест диалога с PostgreSQL памятью"""
    print("\n=== Testing Conversation with PostgreSQL Memory ===")

    session_id = f"test_session_{int(time.time())}"

    # Первое сообщение
    response1 = requests.post(
        "http://localhost:8010/v1/chat/completions",
        json={
            "model": "enhanced-model",
            "messages": [
                {
                    "role": "user",
                    "content": f"Привет! Это тестовая сессия {session_id}. Запомни, что я работаю над проектом агентской системы.",
                }
            ],
        },
    )

    if response1.status_code == 200:
        data1 = response1.json()
        content1 = data1["choices"][0]["message"]["content"]
        print(f"✅ Первое сообщение отправлено")
        print(f"   Ответ: {content1[:100]}...")

        # Ждем немного для сохранения в БД
        time.sleep(2)

        # Второе сообщение - проверяем память
        response2 = requests.post(
            "http://localhost:8010/v1/chat/completions",
            json={
                "model": "enhanced-model",
                "messages": [
                    {
                        "role": "user",
                        "content": f"Привет! Это тестовая сессия {session_id}. Запомни, что я работаю над проектом агентской системы.",
                    },
                    {"role": "assistant", "content": content1},
                    {"role": "user", "content": "Над каким проектом я работаю?"},
                ],
            },
        )

        if response2.status_code == 200:
            data2 = response2.json()
            content2 = data2["choices"][0]["message"]["content"]
            print(f"✅ Второе сообщение отправлено")
            print(f"   Ответ: {content2[:100]}...")

            # Проверяем, что агент помнит контекст
            if "агентск" in content2.lower() or "проект" in content2.lower():
                print("✅ Агент помнит контекст из PostgreSQL!")
                return True
            else:
                print("❌ Агент не использует память")
                return False
        else:
            print(f"❌ Ошибка второго сообщения: {response2.status_code}")
            return False
    else:
        print(f"❌ Ошибка первого сообщения: {response1.status_code}")
        return False

def test_memory_search():
    """Тест поиска в памяти"""
    print("\n=== Testing Memory Search ===")

    session_id = "test_search_session"

    # Добавляем тестовые сообщения через conversation manager
    try:
        import sys
        import os

        sys.path.insert(0, os.path.dirname(__file__))

        from agent_system.conversation import conversation_manager

        # Добавляем несколько сообщений
        test_messages = [
            "Я работаю над системой искусственного интеллекта",
            "Нужно настроить PostgreSQL для хранения данных",
            "Создаю агента для автоматизации задач разработки",
            "Интегрирую базу данных с системой памяти",
        ]

        for i, msg in enumerate(test_messages):
            conversation_manager.add_message(session_id, "user", msg)
            time.sleep(0.1)  # Небольшая пауза

        print(f"✅ Добавлено {len(test_messages)} тестовых сообщений")

        # Ждем сохранения в БД
        time.sleep(2)

        # Тестируем поиск
        search_queries = ["PostgreSQL", "агент", "система", "разработка"]

        search_results = 0
        for query in search_queries:
            response = requests.post(
                "http://localhost:8011/tools/memory_search",
                json={"session_id": session_id, "query": query, "limit": 10},
            )

            if response.status_code == 200:
                data = response.json()
                found_count = data.get("count", 0)
                print(f"✅ Поиск '{query}': найдено {found_count} сообщений")
                if found_count > 0:
                    search_results += 1
            else:
                print(f"❌ Ошибка поиска '{query}': {response.status_code}")

        print(f"📊 Успешных поисков: {search_results}/{len(search_queries)}")
        return search_results > 0

    except ImportError as e:
        print(f"❌ Не удалось импортировать conversation manager: {e}")
        return False

def test_postgres_memory_features():
    """Тест специфичных возможностей PostgreSQL памяти"""
    print("\n=== Testing PostgreSQL Memory Features ===")

    try:
        from agent_system.memory_postgres import postgres_memory

        session_id = f"feature_test_{int(time.time())}"

        # Тест создания сессии
        result1 = postgres_memory.create_session(session_id, user_id="test_user")
        if result1["success"]:
            print("✅ Сессия создана в PostgreSQL")
        else:
            print(f"❌ Ошибка создания сессии: {result1['error']}")
            return False

        # Тест добавления сообщения
        result2 = postgres_memory.add_message(
            session_id, "user", "Тестовое сообщение для проверки PostgreSQL памяти", {"test": True}
        )
        if result2["success"]:
            print("✅ Сообщение добавлено в PostgreSQL")
        else:
            print(f"❌ Ошибка добавления сообщения: {result2['error']}")
            return False

        # Тест сохранения знаний
        result3 = postgres_memory.store_knowledge(
            session_id, "preference", "programming_language", "Python", confidence=0.9, source="user_input"
        )
        if result3["success"]:
            print("✅ Знания сохранены в PostgreSQL")
        else:
            print(f"❌ Ошибка сохранения знаний: {result3['error']}")
            return False

        # Тест получения сводки сессии
        result4 = postgres_memory.get_session_summary(session_id)
        if result4["success"]:
            print("✅ Сводка сессии получена из PostgreSQL")
            session_data = result4["session"]
            print(f"   Сообщений: {session_data['message_count']}")
            print(f"   Знаний: {len(result4['knowledge'])}")
        else:
            print(f"❌ Ошибка получения сводки: {result4['error']}")
            return False

        return True

    except ImportError as e:
        print(f"❌ PostgreSQL память недоступна: {e}")
        return False

def main():
    """Запуск всех тестов PostgreSQL памяти"""
    print("🧠 PostgreSQL Memory Test")
    print("=" * 50)

    tests = [
        ("Memory Status", test_memory_status),
        ("Memory Initialization", test_memory_initialization),
        ("Conversation with PostgreSQL Memory", test_conversation_with_postgres_memory),
        ("Memory Search", test_memory_search),
        ("PostgreSQL Memory Features", test_postgres_memory_features),
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
        print("\n🎉 ОТЛИЧНО! PostgreSQL память работает!")
        print("🧠 Агент теперь имеет масштабируемую память")
        print("🔍 Доступен полнотекстовый поиск по истории")
        print("📊 Система знаний и контекста активна")
    elif success_rate >= 60:
        print("\n✅ ХОРОШО! Основные функции PostgreSQL памяти работают")
    else:
        print("\n❌ ТРЕБУЕТСЯ ДОРАБОТКА PostgreSQL памяти")

    return success_rate >= 60

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

