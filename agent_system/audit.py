"""
Audit logging для отслеживания всех действий агентов
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .config import SecurityConfig

class AuditLogger:
    """Логирование всех действий агентов"""

    def __init__(self, log_path: Path = None):
        self.log_path = log_path or SecurityConfig.AUDIT_LOG_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_action(
        self, agent: str, action: str, params: Dict[str, Any], result: str, success: bool, error: str = None
    ):
        """Записать действие в audit log"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "action": action,
            "params": params,
            "result": result[:500] if result else None,  # ограничиваем размер
            "success": success,
            "error": error,
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_recent_actions(self, limit: int = 100) -> list:
        """Получить последние N действий"""
        if not self.log_path.exists():
            return []

        with open(self.log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        actions = []
        for line in lines[-limit:]:
            try:
                actions.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        return actions

# Глобальный экземпляр
audit_logger = AuditLogger()
