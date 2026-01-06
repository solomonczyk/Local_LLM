"""
Agent System - Локальная агентная система с безопасностью и инструментами
"""
from .audit import audit_logger
from .config import AgentConfig, SecurityConfig
from .tools import ToolExecutor

__version__ = "1.0.0"
__all__ = ["SecurityConfig", "AgentConfig", "ToolExecutor", "audit_logger"]
