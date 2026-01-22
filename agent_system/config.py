"""
Конфигурация и политики безопасности для агентной системы
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Set, Tuple


class SecurityConfig:
    """Политики безопасности для tool execution"""

    # Рабочая директория (все операции только внутри)
    WORKSPACE_ROOT = Path(os.getenv("AGENT_WORKSPACE", os.getcwd())).resolve()

    # Максимальный размер файла для чтения/записи (10 MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # Таймаут для shell команд (секунды)
    SHELL_TIMEOUT = 30

    # Allowlist для shell команд
    ALLOWED_SHELL_COMMANDS: Set[str] = {
        "ls",
        "dir",
        "cat",
        "type",
        "echo",
        "python",
        "pip",
        "pytest",
        "npm",
        "node",
        "git",  # git обрабатывается отдельно
    }

    # Запрещенные паттерны в командах
    FORBIDDEN_PATTERNS: List[str] = [
        "rm -rf /",
        "del /f /s /q",
        "format",
        "curl",
        "wget",
        "nc",
        "netcat",  # сетевые команды
        "sudo",
        "su",  # повышение прав
        ">",
        ">>",
        "|",  # перенаправление (пока запрещено)
    ]

    # Безопасные git команды
    SAFE_GIT_COMMANDS: Set[str] = {"status", "diff", "log", "show", "branch", "add", "commit", "checkout", "stash"}

    # Опасные git команды (требуют подтверждения)
    DANGEROUS_GIT_COMMANDS: Set[str] = {"push", "pull", "reset --hard", "clean -fd"}

    # Audit log
    AUDIT_LOG_PATH = WORKSPACE_ROOT / ".agent_audit.log"

    @classmethod
    def is_path_safe(cls, path: Path) -> bool:
        """Проверка что путь внутри workspace"""
        try:
            resolved = path.resolve()
            # Для совместимости с Python < 3.9
            try:
                return resolved.is_relative_to(cls.WORKSPACE_ROOT)
            except AttributeError:
                # Fallback для старых версий Python
                try:
                    resolved.relative_to(cls.WORKSPACE_ROOT)
                    return True
                except ValueError:
                    return False
        except (ValueError, OSError):
            return False

    @classmethod
    def is_command_safe(cls, command: str) -> Tuple[bool, str]:
        """Проверка безопасности команды"""
        cmd_lower = command.lower()

        # Проверка запрещенных паттернов
        for pattern in cls.FORBIDDEN_PATTERNS:
            if pattern in cmd_lower:
                return False, f"Forbidden pattern: {pattern}"

        # Проверка allowlist
        cmd_parts = command.split()
        if not cmd_parts:
            return False, "Empty command"

        base_cmd = cmd_parts[0]
        if base_cmd not in cls.ALLOWED_SHELL_COMMANDS:
            return False, f"Command not in allowlist: {base_cmd}"

        return True, "OK"

class AgentConfig:
    """Конфигурация агентов"""

    # Уровни доступа
    ACCESS_LEVEL_READ_ONLY = 0
    ACCESS_LEVEL_SAFE_WRITE = 1
    ACCESS_LEVEL_RUN_TESTS = 2
    ACCESS_LEVEL_GIT_COMMIT = 3
    ACCESS_LEVEL_SHELL_EXTENDED = 4

    # Текущий уровень (по умолчанию - безопасный)
    _access_level_env = os.getenv("AGENT_ACCESS_LEVEL", str(ACCESS_LEVEL_SAFE_WRITE))
    try:
        CURRENT_ACCESS_LEVEL = max(ACCESS_LEVEL_READ_ONLY, min(ACCESS_LEVEL_SHELL_EXTENDED, int(_access_level_env)))
    except ValueError:
        CURRENT_ACCESS_LEVEL = ACCESS_LEVEL_SAFE_WRITE

    # LLM endpoints
    LLM_BASE_URL = "http://localhost:8010/v1"
    LLM_MODEL = "qwen2.5-coder-lora"

    # Tool server
    TOOL_SERVER_PORT = 8011

    # ========== CONSILIUM MODE ==========
    # FAST     → 1 агент (dev или router→dev/security) - быстрый режим
    # STANDARD → 2-3 агента (dev + security + qa) - баланс скорости и качества
    # CRITICAL → все 6 агентов + director - полный анализ
    CONSILIUM_MODE = os.getenv("CONSILIUM_MODE", "FAST").upper()

    # Пресеты агентов для каждого режима
    CONSILIUM_PRESETS = {
        "FAST": ["dev"],  # Минимум - только dev
        "STANDARD": ["dev", "security", "qa"],  # Баланс
        "CRITICAL": ["dev", "security", "qa", "architect", "seo", "ux", "director"],  # Все
    }

    @classmethod
    def get_consilium_agents(cls) -> list:
        """Получить список агентов для текущего режима"""
        mode = cls.CONSILIUM_MODE
        if mode not in cls.CONSILIUM_PRESETS:
            print(f"⚠️  Unknown CONSILIUM_MODE '{mode}', falling back to FAST")
            mode = "FAST"
        return cls.CONSILIUM_PRESETS[mode]

    # ========== KB RETRIEVAL LIMITS ==========
    # Ограничения для предотвращения "контекстной инфляции"
    KB_TOP_K = int(os.getenv("KB_TOP_K", "3"))  # Сколько чанков из KB
    KB_MAX_CHARS = int(os.getenv("KB_MAX_CHARS", "6000"))  # Макс символов из KB
    KB_CACHE_SIZE = int(os.getenv("KB_CACHE_SIZE", "256"))  # Размер LRU кэша retrieval
