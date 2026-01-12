#!/usr/bin/env python3
"""
Тест файловых операций через агентскую систему
"""
import requests
import json
import os

def test_create_file():
    """Тест создания файла"""
    print("=== Testing File Creation ===")

    # Создаем тестовый файл через tool сервер
    test_content = """# Тестовый файл
print("Hello from agent system!")

def test_function():
    return "This file was created by an agent"
"""

    response = requests.post(
        "http://localhost:8011/tools/write_file",
        json={"path": "test_agent_file.py", "content": test_content, "mode": "overwrite"},
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Файл создан: {data['path']}")
        print(f"   Размер: {data['size']} символов")
        return True
    else:
        print(f"❌ Ошибка создания файла: {response.text}")
        return False

def test_read_file_via_agent():
    """Тест чтения файла через агента"""
    print("\n=== Testing File Reading via Agent ===")

    response = requests.post(
        "http://localhost:8010/v1/chat/completions",
        json={"model": "mock-model", "messages": [{"role": "user", "content": "прочитай файл test_agent_file.py"}]},
    )

    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print("✅ Агент ответил:")
        print(content)

        if "test_agent_file.py" in content and "Hello from agent system" in content:
            print("✅ Агент успешно прочитал файл!")
            return True
        else:
            print("❌ Агент не смог прочитать файл")
            return False
    else:
        print(f"❌ Ошибка запроса к агенту: {response.status_code}")
        return False

def test_list_files_via_agent():
    """Тест получения списка файлов через агента"""
    print("\n=== Testing File Listing via Agent ===")

    response = requests.post(
        "http://localhost:8010/v1/chat/completions",
        json={"model": "mock-model", "messages": [{"role": "user", "content": "покажи список файлов в текущей папке"}]},
    )

    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print("✅ Агент ответил:")
        print(content)

        if "test_agent_file.py" in content and "📄" in content:
            print("✅ Агент показал список файлов!")
            return True
        else:
            print("❌ Агент не показал список файлов")
            return False
    else:
        print(f"❌ Ошибка запроса к агенту: {response.status_code}")
        return False

def test_edit_file():
    """Тест редактирования файла"""
    print("\n=== Testing File Editing ===")

    response = requests.post(
        "http://localhost:8011/tools/edit_file",
        json={
            "path": "test_agent_file.py",
            "old_text": "Hello from agent system!",
            "new_text": "Hello from EDITED agent system!",
        },
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Файл отредактирован: {data['path']}")
        print(f"   Backup: {data['backup']}")
        print(f"   Размер: {data['old_size']} → {data['new_size']}")
        return True
    else:
        print(f"❌ Ошибка редактирования: {response.text}")
        return False

def test_copy_file():
    """Тест копирования файла"""
    print("\n=== Testing File Copying ===")

    response = requests.post(
        "http://localhost:8011/tools/copy_file",
        json={"source_path": "test_agent_file.py", "dest_path": "test_agent_file_copy.py"},
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Файл скопирован:")
        print(f"   Источник: {data['source']}")
        print(f"   Копия: {data['dest']}")
        print(f"   Размер: {data['size']} байт")
        return True
    else:
        print(f"❌ Ошибка копирования: {response.text}")
        return False

def test_delete_file_via_agent():
    """Тест удаления файла через агента"""
    print("\n=== Testing File Deletion via Agent ===")

    response = requests.post(
        "http://localhost:8010/v1/chat/completions",
        json={"model": "mock-model", "messages": [{"role": "user", "content": "удали файл test_agent_file_copy.py"}]},
    )

    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print("✅ Агент ответил:")
        print(content)

        if "удален" in content.lower() and "backup" in content.lower():
            print("✅ Агент успешно удалил файл!")
            return True
        else:
            print("❌ Агент не смог удалить файл")
            return False
    else:
        print(f"❌ Ошибка запроса к агенту: {response.status_code}")
        return False

def cleanup():
    """Очистка тестовых файлов"""
    print("\n=== Cleanup ===")

    test_files = ["test_agent_file.py", "test_agent_file_copy.py"]

    for file_path in test_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️  Удален: {file_path}")
        except Exception as e:
            print(f"⚠️  Не удалось удалить {file_path}: {e}")

    # Удаляем backup файлы
    for file in os.listdir("."):
        if file.endswith((".backup", ".deleted_backup")):
            try:
                os.remove(file)
                print(f"🗑️  Удален backup: {file}")
            except Exception as e:
                print(f"⚠️  Не удалось удалить backup {file}: {e}")

def main():
    """Запуск всех тестов"""
    print("📁 File Operations Test")
    print("=" * 50)

    tests = [
        ("Create File", test_create_file),
        ("Read File via Agent", test_read_file_via_agent),
        ("List Files via Agent", test_list_files_via_agent),
        ("Edit File", test_edit_file),
        ("Copy File", test_copy_file),
        ("Delete File via Agent", test_delete_file_via_agent),
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
        print("🎉 Все файловые операции работают!")
    else:
        print("⚠️  Некоторые операции не работают.")

    # Очистка
    cleanup()

    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

