# Agent System - Локальная агентная система

## Архитектура

```
┌─────────────────┐
│   Continue UI   │ (VS Code)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Orchestrator   │ (управление агентами)
└────┬───────┬────┘
     │       │
     ▼       ▼
┌─────────┐ ┌──────────┐
│ LLM     │ │ Tool     │
│ Server  │ │ Server   │
│ :8010   │ │ :8011    │
└─────────┘ └──────────┘
```

## Компоненты

### 1. LLM Server (serve_lora.py)
- Локальная модель Qwen2.5 Coder + LoRA
- OpenAI-compatible API
- Порт: 8010

### 2. Tool Server (tool_server.py)
- Безопасное выполнение файловых операций
- Git команды
- Shell команды (ограниченно)
- Audit logging
- Порт: 8011

### 3. Orchestrator (в разработке)
- Управление мультиагентным консилиумом
- Планирование и выполнение задач
- Интеграция с Continue

## Уровни доступа

- **Level 0**: Read-only (чтение файлов, поиск)
- **Level 1**: Safe write (правки через patch, backup)
- **Level 2**: Run tests (pytest, npm test)
- **Level 3**: Git commit (только после проверок)
- **Level 4**: Shell extended (вручную)

## Безопасность

### Политики:
- ✅ Все операции только внутри workspace
- ✅ Allowlist для shell команд
- ✅ Backup перед перезаписью файлов
- ✅ Audit log всех действий
- ✅ Лимиты размера файлов и таймауты
- ✅ Запрет сетевых команд

### Audit Log:
Все действия записываются в `.agent_audit.log`:
```json
{
  "timestamp": "2026-01-04T12:00:00",
  "agent": "dev",
  "action": "write_file",
  "params": {"path": "test.py"},
  "result": "Written 150 chars",
  "success": true
}
```

## Запуск

### 1. Tool Server
```bash
python -m agent_system.tool_server
```

### 2. LLM Server (уже запущен)
```bash
python serve_lora.py
```

## API Endpoints

### Tool Server (http://localhost:8011)

#### POST /tools/read_file
```json
{"path": "src/main.py"}
```

#### POST /tools/write_file
```json
{
  "path": "src/new.py",
  "content": "print('hello')",
  "mode": "overwrite"
}
```

#### POST /tools/list_dir
```json
{"path": "src", "pattern": "*.py"}
```

#### POST /tools/search
```json
{
  "query": "def main",
  "globs": ["**/*.py"]
}
```

#### POST /tools/git
```json
{"cmd": "status"}
```

#### POST /tools/shell
```json
{"command": "pytest tests/"}
```

#### GET /audit/recent?limit=100
Получить последние действия

#### GET /config
Текущая конфигурация

## Следующие шаги

1. ✅ **Этап 0-1**: Tool Server с безопасностью
2. ⏳ **Этап 2**: Orchestrator (единый цикл работы)
3. ⏳ **Этап 3**: Мультиагентный консилиум
4. ⏳ **Этап 4**: Интеграция с Continue
5. ⏳ **Этап 5**: Режимы доступа
6. ⏳ **Этап 6**: Streaming и UX
7. ⏳ **Этап 7**: Надежность и контроль качества

## Тестирование

```bash
# Запустить Tool Server
python -m agent_system.tool_server

# В другом терминале - тесты
curl http://localhost:8011/
curl -X POST http://localhost:8011/tools/list_dir -H "Content-Type: application/json" -d '{"path": "."}'
```
