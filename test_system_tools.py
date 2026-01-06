#!/usr/bin/env python3
"""
Тест системных инструментов через mock сервер
"""
import requests
import json


def test_disk_info():
    """Тест получения информации о дисках"""
    print("=== Testing Disk Info ===")

    # Тестируем через mock сервер
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "model": "mock-model",
            "messages": [
                {"role": "user", "content": "ты можешь посмотреть и сказать мне какие диски есть на моем пс?"}
            ],
        },
    )

    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print("✅ Mock сервер ответил:")
        print(content)

        # Проверяем, что ответ содержит реальную информацию о дисках
        if "C:\\" in content and "ГБ" in content:
            print("✅ Ответ содержит реальную информацию о дисках!")
            return True
        else:
            print("❌ Ответ не содержит информацию о дисках")
            return False
    else:
        print(f"❌ Ошибка запроса: {response.status_code}")
        return False


def test_memory_info():
    """Тест получения информации о памяти"""
    print("\n=== Testing Memory Info ===")

    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={"model": "mock-model", "messages": [{"role": "user", "content": "сколько памяти на моем компьютере?"}]},
    )

    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print("✅ Mock сервер ответил:")
        print(content)

        if "ГБ" in content and ("память" in content.lower() or "ram" in content.lower() or "объем" in content.lower()):
            print("✅ Ответ содержит информацию о памяти!")
            return True
        else:
            print("❌ Ответ не содержит информацию о памяти")
            return False
    else:
        print(f"❌ Ошибка запроса: {response.status_code}")
        return False


def test_network_info():
    """Тест получения сетевой информации"""
    print("\n=== Testing Network Info ===")

    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "model": "mock-model",
            "messages": [{"role": "user", "content": "какие сетевые интерфейсы есть на моем компьютере?"}],
        },
    )

    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print("✅ Mock сервер ответил:")
        print(content)

        if "интерфейс" in content.lower() or "ip" in content.lower():
            print("✅ Ответ содержит сетевую информацию!")
            return True
        else:
            print("❌ Ответ не содержит сетевую информацию")
            return False
    else:
        print(f"❌ Ошибка запроса: {response.status_code}")
        return False


def test_direct_tool_server():
    """Тест прямого обращения к tool серверу"""
    print("\n=== Testing Direct Tool Server ===")

    try:
        # Тест системной информации
        response = requests.post("http://localhost:8001/tools/system_info", json={"info_type": "disks"})

        if response.status_code == 200:
            data = response.json()
            print("✅ Tool сервер доступен")
            print(f"Найдено дисков: {len(data.get('disks', []))}")

            for disk in data.get("disks", []):
                print(f"  💾 {disk['device']} - {disk.get('total_gb', 'N/A')} ГБ")

            return True
        else:
            print(f"❌ Tool сервер недоступен: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Ошибка подключения к tool серверу: {e}")
        return False


def main():
    """Запуск всех тестов"""
    print("🔧 System Tools Integration Test")
    print("=" * 50)

    tests = [
        ("Direct Tool Server", test_direct_tool_server),
        ("Disk Info via Mock", test_disk_info),
        ("Memory Info via Mock", test_memory_info),
        ("Network Info via Mock", test_network_info),
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

    if passed == total:
        print("🎉 Все тесты прошли! Система умеет использовать инструменты!")
    else:
        print("⚠️  Некоторые тесты не прошли.")

    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
