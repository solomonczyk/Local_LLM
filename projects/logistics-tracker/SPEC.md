# Логистический Трекер - Спецификация

## Цель
Автоматическая проверка статусов доставки в транспортных компаниях (СДЭК, ПЭК) с уведомлением клиентов о прибытии товара.

## Бизнес-метрики
- Снижение нагрузки на колл-центр на 40%
- Автоматическое уведомление клиента в течение 15 минут после изменения статуса

## MVP Scope (3 дня)

### День 1: Ядро системы
- [ ] Интеграция с API СДЭК (получение статуса по трек-номеру)
- [ ] Модель данных (заказы, статусы, клиенты)
- [ ] Базовый polling механизм

### День 2: Уведомления + ПЭК
- [ ] Интеграция с API ПЭК
- [ ] Telegram бот для уведомлений
- [ ] Логика определения "важных" изменений статуса

### День 3: UI + Деплой
- [ ] Админ-панель (добавление трек-номеров, просмотр статусов)
- [ ] Деплой на прод сервер
- [ ] Тестирование end-to-end

## Архитектура

```
┌─────────────────┐     ┌─────────────────┐
│   Admin UI      │     │  Telegram Bot   │
│   (Gradio)      │     │  (уведомления)  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│           Tracker Service               │
│  - Order management                     │
│  - Status polling (cron)                │
│  - Notification dispatcher              │
└────────┬───────────────────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   СДЭК API      │     │    ПЭК API      │
│   (REST)        │     │    (REST)       │
└─────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│   PostgreSQL    │
│   (orders,      │
│    statuses)    │
└─────────────────┘
```

## Модель данных

### orders
- id (UUID)
- track_number (string)
- carrier (enum: cdek, pek)
- client_name (string)
- client_phone (string)
- client_telegram_id (bigint, nullable)
- current_status (string)
- last_checked_at (timestamp)
- created_at (timestamp)

### status_history
- id (UUID)
- order_id (FK)
- status (string)
- status_date (timestamp)
- location (string, nullable)
- notified (boolean)
- created_at (timestamp)

## API Интеграции

### СДЭК
- Endpoint: https://api.cdek.ru/v2/
- Auth: OAuth2 (client_id + client_secret)
- Метод: GET /orders?cdek_number={track}

### ПЭК
- Endpoint: https://kabinet.pecom.ru/api/v1/
- Auth: API Key
- Метод: GET /tracking/{track}

## Уведомления

### Триггеры уведомлений
1. "Прибыл в пункт выдачи" → Telegram + SMS
2. "Передан курьеру" → Telegram
3. "Доставлен" → Telegram

### Шаблон сообщения
```
📦 Ваш заказ {track_number}

Статус: {status}
{location}

Ожидаемая дата: {expected_date}
```

## Технологии
- Python 3.11
- FastAPI (API)
- Gradio (Admin UI)
- PostgreSQL (хранение)
- python-telegram-bot (уведомления)
- APScheduler (polling)

## Конфигурация (.env)
```
# СДЭК
CDEK_CLIENT_ID=xxx
CDEK_CLIENT_SECRET=xxx

# ПЭК
PEK_API_KEY=xxx

# Telegram
TELEGRAM_BOT_TOKEN=xxx

# Database
DATABASE_URL=postgresql://...

# Polling
POLL_INTERVAL_MINUTES=15
```
