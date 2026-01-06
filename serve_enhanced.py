"""
Enhanced Mock OpenAI-совместимый сервер с естественным взаимодействием
Запускает на http://localhost:8000
"""
import os
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time
import requests
import json
import uuid
import sys
import os
import asyncio
from typing import Optional

# Добавляем путь для импорта agent_system
sys.path.insert(0, os.path.dirname(__file__))

# Импортируем rate limiter
from rate_limiter import rate_limit_middleware

# Конфигурация безопасности
API_KEY = os.getenv("AGENT_API_KEY", "ea91c0c520c7eb4a9f4064421cae7ca8d120703b9890f35001ecfaa1645cf091")
security = HTTPBearer()


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка API ключа"""
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


try:
    from agent_system.conversation import conversation_manager
    from agent_system.proactive import proactive_agent

    ENHANCED_MODE = True
except ImportError:
    print("⚠️  Enhanced features not available, running in basic mode")
    ENHANCED_MODE = False

app = FastAPI()

# Rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# CORS middleware для безопасности
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://152.53.227.37.nip.io",
        "https://agent.152.53.227.37.nip.io",
        "https://api.152.53.227.37.nip.io",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

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
async def chat_completions(request: ChatRequest, api_key: str = Depends(verify_api_key)):
    # Имитируем обработку
    await asyncio.sleep(0.5)

    # Получаем последнее сообщение пользователя
    user_message = ""
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if ENHANCED_MODE:
        # Получаем или создаем сессию
        session_id = "default"  # В реальной системе это будет из заголовков/токенов

        # Добавляем сообщение в историю
        conversation_manager.add_message(session_id, "user", user_message)

        # Генерируем ответ с учетом контекста
        response = await generate_contextual_response(session_id, user_message)

        # Добавляем ответ в историю
        conversation_manager.add_message(session_id, "assistant", response)
    else:
        # Простой режим без контекста
        response = generate_smart_response(user_message)

    return {
        "id": "enhanced-" + str(int(time.time())),
        "object": "chat.completion",
        "model": request.model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": response}, "finish_reason": "stop"}],
    }


async def generate_contextual_response(session_id: str, user_message: str) -> str:
    """Генерация ответа с учетом контекста и проактивности"""

    # Получаем контекст диалога
    context = conversation_manager.get_or_create_context(session_id)
    context_summary = conversation_manager.get_context_summary(session_id)

    # Анализируем намерения
    should_be_proactive = proactive_agent.should_be_proactive(session_id, user_message)

    # Генерируем основной ответ
    main_response = generate_smart_response(user_message, context_summary)

    # Добавляем проактивные элементы
    if should_be_proactive:
        suggestions = proactive_agent.generate_suggestions(session_id, user_message)
        clarifying_questions = proactive_agent.generate_clarifying_questions(user_message)

        if suggestions:
            main_response += "\n\n💡 **Предложения:**\n" + "\n".join(f"• {s}" for s in suggestions)

        if clarifying_questions:
            main_response += "\n\n❓ **Уточняющие вопросы:**\n" + "\n".join(f"• {q}" for q in clarifying_questions)

    # Добавляем контекстную информацию если это первое сообщение
    if len(context.messages) <= 2:  # user + assistant
        main_response += "\n\n---\n💬 *Я запомню наш диалог и смогу ссылаться на предыдущие сообщения. Также я могу работать с файлами, анализировать код и помогать с разработкой.*"

    return main_response


def generate_smart_response(text: str, context_summary: str = "") -> str:
    """Генерирует умный ответ на основе ключевых слов и контекста"""
    text_lower = text.lower()

    # Учитываем контекст в ответе
    context_info = ""
    if context_summary and "активные файлы" in context_summary.lower():
        context_info = "\n\n📋 *Учитываю контекст нашего диалога и активные файлы.*"

    # Проверяем системные запросы
    if any(word in text_lower for word in ["диск", "disk", "drive", "hdd", "ssd"]):
        try:
            response = requests.post(f"{TOOL_SERVER_URL}/tools/system_info", json={"info_type": "disks"}, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and "disks" in data:
                    disks_info = []
                    for disk in data["disks"]:
                        if "status" in disk:
                            disks_info.append(
                                f"🔒 {disk['device']} ({disk['mountpoint']}) - {disk['fstype']} - Доступ ограничен"
                            )
                        else:
                            disks_info.append(
                                f"💾 {disk['device']} ({disk['mountpoint']}) - {disk['fstype']}\n"
                                f"   Размер: {disk['total_gb']} ГБ, Использовано: {disk['used_gb']} ГБ ({disk['percent_used']}%)\n"
                                f"   Свободно: {disk['free_gb']} ГБ"
                            )

                    return f"📊 Информация о дисках на вашем ПК:\n\n" + "\n\n".join(disks_info) + context_info
        except Exception:
            pass

        return "📊 Для получения информации о дисках нужен доступ к системным инструментам." + context_info
    # Остальные системные запросы (память, сеть, процессы)
    elif any(word in text_lower for word in ["память", "memory", "ram", "оперативн", "сколько памяти"]):
        try:
            response = requests.post(f"{TOOL_SERVER_URL}/tools/system_info", json={"info_type": "memory"}, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return f"""🧠 Информация о памяти:
                    
💾 Общий объем: {data['total_gb']} ГБ
✅ Доступно: {data['available_gb']} ГБ  
🔄 Используется: {data['used_gb']} ГБ ({data['percent_used']}%){context_info}"""
        except Exception:
            pass
        return "🧠 Для получения информации о памяти нужен доступ к системным инструментам." + context_info

    # Файловые операции
    elif any(word in text_lower for word in ["прочитай файл", "read file", "покажи содержимое", "открой файл"]):
        import re

        file_patterns = [
            r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']',
            r"файл\s+([^\s]+\.[a-zA-Z0-9]+)",
            r"([^\s]+\.(?:py|txt|md|json|yaml|yml|js|ts|html|css))",
        ]

        file_path = None
        for pattern in file_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                file_path = match.group(1)
                break

        if file_path:
            try:
                response = requests.post(f"{TOOL_SERVER_URL}/tools/read_file", json={"path": file_path}, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        content = data["content"]
                        if len(content) > 1000:
                            content = content[:1000] + "\n... (файл обрезан, показаны первые 1000 символов)"
                        return f"📄 Содержимое файла {file_path}:\n\n```\n{content}\n```{context_info}"
                else:
                    return f"❌ Не удалось прочитать файл {file_path}: {response.text}{context_info}"
            except Exception as e:
                return f"❌ Ошибка при чтении файла: {e}{context_info}"
        else:
            return "❓ Укажите путь к файлу, например: 'прочитай файл test.py'" + context_info

    # Работа с базами данных
    elif any(word in text_lower for word in ["база данных", "database", "sql", "postgres", "таблица", "запрос"]):
        # Определяем тип операции с БД
        if any(word in text_lower for word in ["подключи", "connect", "настрой"]):
            return (
                """🗄️ Для подключения к PostgreSQL нужны параметры:

📋 **Обязательные параметры:**
• host - адрес сервера (например: localhost)
• database - имя базы данных
• user - имя пользователя
• password - пароль

📋 **Дополнительные:**
• port - порт (по умолчанию 5432)

💡 **Пример команды:**
"подключи базу данных test_db на localhost с пользователем postgres"

⚠️ **Безопасность:** Пароли не сохраняются в файлах конфигурации."""
                + context_info
            )

        elif any(word in text_lower for word in ["таблицы", "схема", "структура"]):
            return (
                """📊 Для просмотра структуры БД могу показать:

🗂️ **Список таблиц:**
"покажи все таблицы в базе данных"

📋 **Структура таблицы:**
"покажи структуру таблицы users"

🔍 **Информация о колонках:**
• Типы данных
• Ограничения (NOT NULL, DEFAULT)
• Максимальная длина

💡 Сначала нужно настроить подключение к БД."""
                + context_info
            )

        elif any(word in text_lower for word in ["select", "выбери", "найди", "покажи данные"]):
            return (
                """🔍 Для выполнения SQL запросов:

✅ **Разрешенные операции:**
• SELECT - чтение данных
• INSERT - добавление записей
• UPDATE - обновление (только с WHERE)
• DELETE - удаление (только с WHERE)

❌ **Запрещенные операции:**
• DROP, TRUNCATE - удаление структур
• ALTER, CREATE - изменение схемы
• Операции без WHERE для UPDATE/DELETE

💡 **Пример:**
"выполни запрос SELECT * FROM users WHERE active = true"

🔒 Все запросы проверяются на безопасность."""
                + context_info
            )

        else:
            return (
                """🗄️ Работа с PostgreSQL базами данных:

🔧 **Доступные операции:**
• Подключение к БД
• Просмотр схемы и таблиц
• Выполнение безопасных SQL запросов
• Анализ структуры данных

💡 **Начните с:**
"подключи базу данных [имя] на [хост]"

📚 **Примеры команд:**
• "покажи все таблицы"
• "структура таблицы users"
• "выполни SELECT * FROM products LIMIT 10"

🔒 Система обеспечивает безопасность через валидацию запросов."""
                + context_info
            )
        return (
            """🔧 Для создания REST API рекомендую:

1. **Архитектура**:
   - FastAPI или Flask для Python
   - Express.js для Node.js
   - Структура: routes/, models/, middleware/

2. **Основные эндпоинты**:
   - `POST /api/auth/login` - авторизация
   - `GET /api/users/profile` - профиль пользователя
   - `PUT /api/users/profile` - обновление профиля

3. **Безопасность**:
   - JWT токены для аутентификации
   - Валидация входных данных
   - Rate limiting и CORS

💡 Хотите, чтобы я создал базовую структуру API для вас?"""
            + context_info
        )

    else:
        # Общий ответ с проактивностью
        return f"""Понял задачу: "{text[:100]}..."

Это интересная задача! Рекомендую разбить её на этапы:

1. **Анализ требований** - определить ключевые функции
2. **Архитектурное решение** - выбрать технологии и подходы  
3. **Поэтапная реализация** - начать с MVP
4. **Тестирование** - покрыть тестами критичный функционал
5. **Документация** - описать API и процессы

Нужны дополнительные детали по какому-то из этапов?{context_info}"""


@app.post("/v1/completions")
async def completions(request: CompletionRequest, api_key: str = Depends(verify_api_key)):
    await asyncio.sleep(0.5)
    response = generate_smart_response(request.prompt)

    return {
        "id": "enhanced-" + str(int(time.time())),
        "object": "text_completion",
        "model": request.model,
        "choices": [{"text": response, "index": 0, "finish_reason": "stop"}],
    }


@app.get("/v1/models")
async def list_models():
    return {"object": "list", "data": [{"id": "enhanced-model", "object": "model", "owned_by": "local"}]}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": True,
        "model_name": "enhanced-model",
        "enhanced_mode": ENHANCED_MODE,
        "authentication": "enabled",
        "rate_limiting": "enabled",
    }


@app.get("/v1/health")
async def health_check_v1():
    return await health_check()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000, help="Port to run on")
    args = parser.parse_args()

    print(f"\n🚀 Enhanced Mock сервер запущен на http://localhost:{args.port}")
    print(f"📝 OpenAI API endpoint: http://localhost:{args.port}/v1")
    if ENHANCED_MODE:
        print("🧠 Enhanced mode: контекст диалога, проактивность, память")
    else:
        print("⚠️  Basic mode: простые ответы без контекста")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
