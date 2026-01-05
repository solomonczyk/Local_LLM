"""
Enhanced Mock OpenAI-совместимый сервер с естественным взаимодействием
Запускает на http://localhost:8000
"""
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import time
import requests
import json
import uuid
import sys
import os

# Добавляем путь для импорта agent_system
sys.path.insert(0, os.path.dirname(__file__))

from agent_system.conversation import conversation_manager
from agent_system.proactive import proactive_agent

app = FastAPI()

# URL tool сервера
TOOL_SERVER_URL = "http://localhost:8001"

class ChatRequest(BaseModel):
    model: str
    messages: list
    temperature: float = 0.7
    max_tokens: int = 512

class CompletionRequest(BaseModel):
    model: str
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 512

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    # Имитируем обработку
    await asyncio.sleep(0.5)
    
    # Получаем последнее сообщение пользователя
    user_message = ""
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break
    
    # Простые ответы на основе ключевых слов
    response = generate_mock_response(user_message)
    
    return {
        "id": "mock-" + str(int(time.time())),
        "object": "chat.completion",
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response
            },
            "finish_reason": "stop"
        }]
    }

@app.post("/v1/completions")
async def completions(request: CompletionRequest):
    await asyncio.sleep(0.5)
    response = generate_mock_response(request.prompt)
    
    return {
        "id": "mock-" + str(int(time.time())),
        "object": "text_completion",
        "model": request.model,
        "choices": [{
            "text": response,
            "index": 0,
            "finish_reason": "stop"
        }]
    }

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{
            "id": "mock-model",
            "object": "model",
            "owned_by": "local"
        }]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint для проверки доступности сервера"""
    return {
        "status": "healthy",
        "model_loaded": True,
        "model_name": "mock-model"
    }

@app.get("/v1/health")
async def health_check_v1():
    """Health check endpoint (OpenAI-style path)"""
    return await health_check()

def generate_mock_response(text: str) -> str:
    """Генерирует mock ответ на основе ключевых слов"""
    text_lower = text.lower()
    
    # Проверяем системные запросы
    if any(word in text_lower for word in ["диск", "disk", "drive", "hdd", "ssd"]):
        try:
            # Пытаемся получить реальную информацию о дисках
            response = requests.post(
                f"{TOOL_SERVER_URL}/tools/system_info",
                json={"info_type": "disks"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and "disks" in data:
                    disks_info = []
                    for disk in data["disks"]:
                        if "status" in disk:
                            disks_info.append(f"🔒 {disk['device']} ({disk['mountpoint']}) - {disk['fstype']} - Доступ ограничен")
                        else:
                            disks_info.append(
                                f"💾 {disk['device']} ({disk['mountpoint']}) - {disk['fstype']}\n"
                                f"   Размер: {disk['total_gb']} ГБ, Использовано: {disk['used_gb']} ГБ ({disk['percent_used']}%)\n"
                                f"   Свободно: {disk['free_gb']} ГБ"
                            )
                    
                    return f"📊 Информация о дисках на вашем ПК:\n\n" + "\n\n".join(disks_info)
        except Exception as e:
            pass
        
        # Fallback если tool сервер недоступен
        return """📊 Для получения информации о дисках нужен доступ к системным инструментам.
        
Обычно на Windows ПК есть:
- C: - основной системный диск
- D: - дополнительный диск для данных (если есть)
- Возможны другие диски (E:, F: и т.д.)

Для точной информации запустите tool сервер командой:
python -m agent_system.tool_server"""

    elif any(word in text_lower for word in ["память", "memory", "ram", "оперативн", "сколько памяти"]):
        try:
            response = requests.post(
                f"{TOOL_SERVER_URL}/tools/system_info",
                json={"info_type": "memory"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return f"""🧠 Информация о памяти:
                    
💾 Общий объем: {data['total_gb']} ГБ
✅ Доступно: {data['available_gb']} ГБ  
🔄 Используется: {data['used_gb']} ГБ ({data['percent_used']}%)"""
        except Exception:
            pass
            
        return "🧠 Для получения информации о памяти нужен доступ к системным инструментам."

    elif any(word in text_lower for word in ["сеть", "network", "ip", "интерфейс"]):
        try:
            response = requests.post(
                f"{TOOL_SERVER_URL}/tools/network_info",
                json={},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    interfaces_info = []
                    for iface in data["interfaces"]:
                        if iface["addresses"]:
                            addr_list = []
                            for addr in iface["addresses"]:
                                addr_list.append(f"{addr['type']}: {addr['address']}")
                            interfaces_info.append(f"🌐 {iface['name']}: {', '.join(addr_list)}")
                    
                    stats = data["statistics"]
                    return f"""🌐 Сетевая информация:

{chr(10).join(interfaces_info)}

📊 Статистика:
📤 Отправлено: {stats['bytes_sent']:,} байт ({stats['packets_sent']:,} пакетов)
📥 Получено: {stats['bytes_recv']:,} байт ({stats['packets_recv']:,} пакетов)"""
        except Exception:
            pass
            
        return "🌐 Для получения сетевой информации нужен доступ к системным инструментам."

    elif any(word in text_lower for word in ["процесс", "process", "задач", "task"]):
        try:
            response = requests.post(
                f"{TOOL_SERVER_URL}/tools/system_info",
                json={"info_type": "processes"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    processes_info = []
                    for proc in data["processes"][:10]:  # Топ 10
                        processes_info.append(
                            f"⚡ {proc['name']} (PID: {proc['pid']}) - "
                            f"CPU: {proc.get('cpu_percent', 0):.1f}%, "
                            f"RAM: {proc.get('memory_percent', 0):.1f}%"
                        )
                    
                    return f"🔄 Топ процессов по использованию CPU:\n\n" + "\n".join(processes_info)
        except Exception:
            pass
            
        return "🔄 Для получения информации о процессах нужен доступ к системным инструментам."

    # Файловые операции
    elif any(word in text_lower for word in ["прочитай файл", "read file", "покажи содержимое", "открой файл"]):
        # Ищем путь к файлу в тексте
        import re
        file_patterns = [
            r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']',  # "file.txt"
            r'файл\s+([^\s]+\.[a-zA-Z0-9]+)',      # файл test.py
            r'([^\s]+\.(?:py|txt|md|json|yaml|yml|js|ts|html|css))',  # расширения файлов
        ]
        
        file_path = None
        for pattern in file_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                file_path = match.group(1)
                break
        
        if file_path:
            try:
                response = requests.post(
                    f"{TOOL_SERVER_URL}/tools/read_file",
                    json={"path": file_path},
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        content = data["content"]
                        if len(content) > 1000:
                            content = content[:1000] + "\n... (файл обрезан, показаны первые 1000 символов)"
                        return f"📄 Содержимое файла {file_path}:\n\n```\n{content}\n```"
                else:
                    return f"❌ Не удалось прочитать файл {file_path}: {response.text}"
            except Exception as e:
                return f"❌ Ошибка при чтении файла: {e}"
        else:
            return "❓ Укажите путь к файлу, например: 'прочитай файл test.py'"

    elif any(word in text_lower for word in ["создай файл", "create file", "напиши файл", "сохрани в файл"]):
        return """📝 Для создания файла используйте команду вида:
        
'создай файл example.py с содержимым:
print("Hello World")'

Или: 'напиши в файл config.json следующее: {"debug": true}'"""

    elif any(word in text_lower for word in ["удали файл", "delete file", "remove file"]):
        import re
        file_patterns = [
            r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']',
            r'файл\s+([^\s]+\.[a-zA-Z0-9]+)',
            r'([^\s]+\.(?:py|txt|md|json|yaml|yml|js|ts|html|css))',
        ]
        
        file_path = None
        for pattern in file_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                file_path = match.group(1)
                break
        
        if file_path:
            try:
                response = requests.post(
                    f"{TOOL_SERVER_URL}/tools/delete_file",
                    json={"path": file_path},
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return f"✅ Файл {file_path} удален. Создан backup: {data.get('backup', 'N/A')}"
                else:
                    return f"❌ Не удалось удалить файл {file_path}: {response.text}"
            except Exception as e:
                return f"❌ Ошибка при удалении файла: {e}"
        else:
            return "❓ Укажите путь к файлу для удаления, например: 'удали файл test.py'"

    elif any(word in text_lower for word in ["список файлов", "list files", "покажи файлы", "что в папке"]):
        try:
            response = requests.post(
                f"{TOOL_SERVER_URL}/tools/list_dir",
                json={"path": ".", "pattern": "*"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    files_info = []
                    for file_info in data["files"][:20]:  # Показываем первые 20
                        icon = "📁" if file_info["is_dir"] else "📄"
                        size = f" ({file_info['size']} байт)" if not file_info["is_dir"] else ""
                        files_info.append(f"{icon} {file_info['name']}{size}")
                    
                    return f"📂 Файлы в текущей директории:\n\n" + "\n".join(files_info)
            else:
                return f"❌ Не удалось получить список файлов: {response.text}"
        except Exception as e:
            return f"❌ Ошибка при получении списка файлов: {e}"

    elif any(word in text_lower for word in ["api", "rest", "endpoint"]):
        return """Для создания REST API рекомендую:

1. **Структура проекта**:
   - `/routes` - маршруты API
   - `/models` - модели данных
   - `/middleware` - промежуточное ПО
   - `/controllers` - контроллеры

2. **Основные эндпоинты**:
   - `POST /api/auth/login` - авторизация
   - `GET /api/users/profile` - профиль пользователя
   - `PUT /api/users/profile` - обновление профиля

3. **Безопасность**:
   - JWT токены для аутентификации
   - Валидация входных данных
   - Rate limiting
   - CORS настройки"""

    elif any(word in text_lower for word in ["database", "schema", "db"]):
        return """Рекомендации по проектированию БД:

1. **Основные таблицы**:
   - `users` - пользователи
   - `roles` - роли
   - `sessions` - сессии

2. **Индексы**:
   - Первичные ключи (id)
   - Уникальные поля (email)
   - Часто используемые в WHERE

3. **Связи**:
   - Внешние ключи с CASCADE
   - Промежуточные таблицы для many-to-many"""

    elif any(word in text_lower for word in ["test", "testing", "unit"]):
        return """Стратегия тестирования:

1. **Unit тесты**:
   - Тестируем отдельные функции
   - Мокаем внешние зависимости
   - Покрытие > 80%

2. **Integration тесты**:
   - Тестируем API эндпоинты
   - Проверяем взаимодействие с БД
   - Тестовая база данных

3. **Инструменты**:
   - Jest/Mocha для JavaScript
   - pytest для Python
   - Postman для API"""

    elif any(word in text_lower for word in ["performance", "optimize", "speed"]):
        return """Оптимизация производительности:

1. **Frontend**:
   - Минификация CSS/JS
   - Сжатие изображений
   - Lazy loading
   - CDN для статики

2. **Backend**:
   - Кэширование (Redis)
   - Оптимизация запросов к БД
   - Connection pooling
   - Асинхронная обработка

3. **Мониторинг**:
   - Логирование медленных запросов
   - Метрики производительности
   - Профилирование кода"""

    elif any(word in text_lower for word in ["security", "secure", "vulnerability"]):
        return """Аудит безопасности:

1. **Аутентификация**:
   - Сильные пароли
   - 2FA где возможно
   - Безопасное хранение токенов

2. **Валидация данных**:
   - Санитизация входных данных
   - Защита от SQL injection
   - XSS защита

3. **Инфраструктура**:
   - HTTPS везде
   - Обновление зависимостей
   - Регулярные бэкапы"""

    else:
        return f"""Понял задачу: "{text[:100]}..."

Это интересная задача! Рекомендую разбить её на этапы:

1. **Анализ требований** - определить ключевые функции
2. **Архитектурное решение** - выбрать технологии и подходы  
3. **Поэтапная реализация** - начать с MVP
4. **Тестирование** - покрыть тестами критичный функционал
5. **Документация** - описать API и процессы

Нужны дополнительные детали по какому-то из этапов?"""

if __name__ == "__main__":
    import asyncio
    print("\n🚀 Mock сервер запущен на http://localhost:8000")
    print("📝 OpenAI API endpoint: http://localhost:8000/v1")
    print("⚠️  Это тестовый сервер с заготовленными ответами")
    uvicorn.run(app, host="0.0.0.0", port=8000)