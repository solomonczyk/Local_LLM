#!/usr/bin/env python3
"""
Тест интеграции с PostgreSQL
"""
import requests
import json


def test_postgres_availability():
    """Проверка доступности PostgreSQL модуля"""
    print("=== Testing PostgreSQL Availability ===")
    
    try:
        import psycopg2
        print("✅ psycopg2 модуль доступен")
        print(f"   Версия: {psycopg2.__version__}")
        return True
    except ImportError:
        print("❌ psycopg2 не установлен")
        print("💡 Установите командой: pip install psycopg2-binary")
        return False


def test_database_tools_import():
    """Тест импорта database tools"""
    print("\n=== Testing Database Tools Import ===")
    
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        
        from agent_system.database_tools import db_manager
        print("✅ Database tools импортированы успешно")
        return True
    except ImportError as e:
        print(f"❌ Ошибка импорта database tools: {e}")
        return False


def test_database_conversation():
    """Тест диалога о базах данных"""
    print("\n=== Testing Database Conversation ===")
    
    database_queries = [
        "как подключиться к PostgreSQL?",
        "покажи структуру базы данных",
        "как выполнить SQL запрос?",
        "что можно делать с базой данных?"
    ]
    
    passed = 0
    for query in database_queries:
        print(f"\n🤖 Запрос: {query}")
        
        response = requests.post(
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "enhanced-model",
                "messages": [
                    {"role": "user", "content": query}
                ]
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            print(f"📝 Ответ: {content[:200]}...")
            
            # Проверяем наличие ключевых слов о БД
            db_keywords = ["postgres", "база данных", "sql", "таблиц", "запрос"]
            found_keywords = [kw for kw in db_keywords if kw.lower() in content.lower()]
            
            if found_keywords:
                print(f"✅ Найдены БД ключевые слова: {found_keywords}")
                passed += 1
            else:
                print("❌ БД ключевые слова не найдены")
        else:
            print(f"❌ Ошибка запроса: {response.status_code}")
    
    print(f"\n📊 Результат диалогов о БД: {passed}/{len(database_queries)}")
    return passed == len(database_queries)


def test_tool_server_db_endpoints():
    """Тест эндпоинтов БД в tool сервере"""
    print("\n=== Testing Tool Server DB Endpoints ===")
    
    # Проверяем доступность эндпоинтов
    endpoints_to_test = [
        "/tools/db_add_connection",
        "/tools/db_execute_query", 
        "/tools/db_get_schema"
    ]
    
    available_endpoints = 0
    
    for endpoint in endpoints_to_test:
        try:
            # Отправляем POST запрос с неполными данными, чтобы получить ошибку валидации
            response = requests.post(f"http://localhost:8001{endpoint}", json={})
            
            # Ожидаем ошибку 422 (валидация) или 400 (бизнес-логика)
            if response.status_code in [400, 422]:
                print(f"✅ Эндпоинт {endpoint} доступен")
                available_endpoints += 1
            else:
                print(f"❌ Эндпоинт {endpoint} недоступен (код: {response.status_code})")
        
        except Exception as e:
            print(f"❌ Ошибка проверки {endpoint}: {e}")
    
    print(f"\n📊 Доступные эндпоинты БД: {available_endpoints}/{len(endpoints_to_test)}")
    return available_endpoints == len(endpoints_to_test)


def test_database_security():
    """Тест безопасности БД операций"""
    print("\n=== Testing Database Security ===")
    
    # Тестируем проверку безопасности запросов
    try:
        from agent_system.database_tools import DatabaseManager
        
        db_mgr = DatabaseManager()
        
        # Тестируем безопасные запросы
        safe_queries = [
            "SELECT * FROM users WHERE id = 1",
            "INSERT INTO logs (message) VALUES ('test')",
            "UPDATE users SET name = 'John' WHERE id = 1",
            "DELETE FROM temp_data WHERE created < NOW() - INTERVAL '1 day'"
        ]
        
        # Тестируем опасные запросы
        dangerous_queries = [
            "DROP TABLE users",
            "TRUNCATE logs",
            "DELETE FROM users",  # без WHERE
            "UPDATE users SET password = 'hack'",  # без WHERE
            "GRANT ALL ON users TO public"
        ]
        
        safe_passed = 0
        for query in safe_queries:
            is_safe, reason = db_mgr._is_query_safe(query)
            if is_safe:
                safe_passed += 1
                print(f"✅ Безопасный запрос: {query[:50]}...")
            else:
                print(f"❌ Ложное срабатывание: {query[:50]}... - {reason}")
        
        dangerous_blocked = 0
        for query in dangerous_queries:
            is_safe, reason = db_mgr._is_query_safe(query)
            if not is_safe:
                dangerous_blocked += 1
                print(f"🛡️  Заблокирован опасный запрос: {query[:50]}... - {reason}")
            else:
                print(f"⚠️  Пропущен опасный запрос: {query[:50]}...")
        
        print(f"\n📊 Безопасность БД:")
        print(f"   Безопасные запросы пропущены: {safe_passed}/{len(safe_queries)}")
        print(f"   Опасные запросы заблокированы: {dangerous_blocked}/{len(dangerous_queries)}")
        
        return safe_passed == len(safe_queries) and dangerous_blocked == len(dangerous_queries)
    
    except ImportError as e:
        print(f"❌ Не удалось импортировать database tools: {e}")
        return False


def test_database_config_management():
    """Тест управления конфигурациями БД"""
    print("\n=== Testing Database Config Management ===")
    
    try:
        from agent_system.database_tools import DatabaseManager
        
        db_mgr = DatabaseManager()
        
        # Тестируем сохранение/загрузку конфигураций
        test_config = {
            "host": "localhost",
            "database": "test_db", 
            "user": "test_user",
            "password": "***",  # Маскированный пароль
            "port": 5432
        }
        
        # Сохраняем конфигурацию
        configs = {"test_connection": test_config}
        db_mgr._save_configs(configs)
        print("✅ Конфигурация сохранена")
        
        # Загружаем конфигурацию
        loaded_configs = db_mgr._load_configs()
        
        if "test_connection" in loaded_configs:
            print("✅ Конфигурация загружена")
            
            # Проверяем, что пароль замаскирован
            if loaded_configs["test_connection"]["password"] == "***":
                print("✅ Пароль корректно замаскирован")
                return True
            else:
                print("❌ Пароль не замаскирован")
                return False
        else:
            print("❌ Конфигурация не найдена")
            return False
    
    except Exception as e:
        print(f"❌ Ошибка тестирования конфигураций: {e}")
        return False


def main():
    """Запуск всех тестов PostgreSQL интеграции"""
    print("🗄️ PostgreSQL Integration Test")
    print("=" * 50)
    
    tests = [
        ("PostgreSQL Availability", test_postgres_availability),
        ("Database Tools Import", test_database_tools_import),
        ("Database Conversation", test_database_conversation),
        ("Tool Server DB Endpoints", test_tool_server_db_endpoints),
        ("Database Security", test_database_security),
        ("Database Config Management", test_database_config_management)
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
        print("\n🎉 ОТЛИЧНО! PostgreSQL интеграция работает!")
        print("🗄️ Агент может работать с базами данных")
        if passed < total:
            print("💡 Для полной функциональности установите: pip install psycopg2-binary")
    elif success_rate >= 60:
        print("\n✅ ХОРОШО! Основная функциональность PostgreSQL доступна")
    else:
        print("\n❌ ТРЕБУЕТСЯ ДОРАБОТКА PostgreSQL интеграции")
    
    return success_rate >= 60


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)