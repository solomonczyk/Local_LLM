"""
Система управления контекстом диалога и памятью
Теперь с поддержкой PostgreSQL
"""
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .memory_postgres import postgres_memory

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False


@dataclass
class Message:
    """Сообщение в диалоге"""

    role: str  # user, assistant, system, tool
    content: str
    timestamp: float
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationContext:
    """Контекст диалога"""

    session_id: str
    messages: List[Message]
    user_preferences: Dict[str, Any]
    working_directory: str
    active_files: List[str]  # Файлы, с которыми работаем
    project_context: Dict[str, Any]  # Информация о проекте
    last_activity: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "user_preferences": self.user_preferences,
            "working_directory": self.working_directory,
            "active_files": self.active_files,
            "project_context": self.project_context,
            "last_activity": self.last_activity,
        }


class ConversationManager:
    """Управление диалогами и контекстом с поддержкой PostgreSQL"""

    def __init__(self, storage_path: str = ".agent_conversations", use_postgres: bool = True):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.active_contexts: Dict[str, ConversationContext] = {}
        self.max_context_messages = 50
        self.use_postgres = use_postgres and POSTGRES_AVAILABLE

        if self.use_postgres:
            print("💾 Using PostgreSQL for agent memory")
        else:
            print("📁 Using file-based memory (PostgreSQL not available)")

    def get_or_create_context(self, session_id: str) -> ConversationContext:
        """Получить или создать контекст диалога"""
        if session_id in self.active_contexts:
            return self.active_contexts[session_id]

        if self.use_postgres:
            return self._get_context_from_postgres(session_id)
        else:
            return self._get_context_from_file(session_id)

    def _get_context_from_postgres(self, session_id: str) -> ConversationContext:
        """Получить контекст из PostgreSQL"""
        try:
            # Создаем сессию если не существует
            postgres_memory.create_session(session_id)

            # Получаем сводку сессии
            summary = postgres_memory.get_session_summary(session_id)

            if summary["success"]:
                session_data = summary["session"]
                recent_messages = summary["recent_messages"]

                # Конвертируем сообщения
                messages = []
                for msg in recent_messages:
                    messages.append(
                        Message(
                            role=msg["role"],
                            content=msg["content"],
                            timestamp=msg["timestamp"].timestamp()
                            if hasattr(msg["timestamp"], "timestamp")
                            else time.time(),
                            metadata=msg.get("metadata", {}),
                        )
                    )

                # Создаем контекст
                context = ConversationContext(
                    session_id=session_id,
                    messages=messages,
                    user_preferences={},
                    working_directory=session_data.get("working_directory", "."),
                    active_files=json.loads(session_data.get("active_files", "[]"))
                    if session_data.get("active_files")
                    else [],
                    project_context=json.loads(session_data.get("project_metadata", "{}"))
                    if session_data.get("project_metadata")
                    else {},
                    last_activity=time.time(),
                )

                self.active_contexts[session_id] = context
                return context

        except Exception as e:
            print(f"Error loading from PostgreSQL: {e}")

        # Fallback к созданию нового контекста
        return self._create_new_context(session_id)

    def _get_context_from_file(self, session_id: str) -> ConversationContext:
        """Получить контекст из файла (fallback)"""
        context_file = self.storage_path / f"{session_id}.json"
        if context_file.exists():
            try:
                with open(context_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                context = ConversationContext(
                    session_id=data["session_id"],
                    messages=[Message(**msg) for msg in data["messages"]],
                    user_preferences=data["user_preferences"],
                    working_directory=data["working_directory"],
                    active_files=data["active_files"],
                    project_context=data["project_context"],
                    last_activity=data["last_activity"],
                )
                self.active_contexts[session_id] = context
                return context
            except Exception as e:
                print(f"Error loading context from file: {e}")

        return self._create_new_context(session_id)

    def _create_new_context(self, session_id: str) -> ConversationContext:
        """Создать новый контекст"""
        context = ConversationContext(
            session_id=session_id,
            messages=[],
            user_preferences={},
            working_directory=".",
            active_files=[],
            project_context={},
            last_activity=time.time(),
        )
        self.active_contexts[session_id] = context
        return context

    def add_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None):
        """Добавить сообщение в диалог"""
        context = self.get_or_create_context(session_id)

        message = Message(role=role, content=content, timestamp=time.time(), metadata=metadata or {})

        context.messages.append(message)
        context.last_activity = time.time()

        # Сохраняем в PostgreSQL если доступен
        if self.use_postgres:
            try:
                postgres_memory.add_message(session_id, role, content, metadata)
            except Exception as e:
                print(f"Error saving to PostgreSQL: {e}")

        # Ограничиваем размер контекста
        if len(context.messages) > self.max_context_messages:
            system_messages = [msg for msg in context.messages if msg.role == "system"]
            recent_messages = [msg for msg in context.messages if msg.role != "system"][-self.max_context_messages :]
            context.messages = system_messages + recent_messages

        # Сохраняем в файл как backup
        self.save_context(context)

    def get_conversation_history(self, session_id: str, last_n: int = 10) -> List[Message]:
        """Получить историю диалога"""
        context = self.get_or_create_context(session_id)
        return context.messages[-last_n:] if context.messages else []

    def update_project_context(self, session_id: str, project_info: Dict[str, Any]):
        """Обновить контекст проекта"""
        context = self.get_or_create_context(session_id)
        context.project_context.update(project_info)
        context.last_activity = time.time()
        self.save_context(context)

    def add_active_file(self, session_id: str, file_path: str):
        """Добавить файл в активные"""
        context = self.get_or_create_context(session_id)
        if file_path not in context.active_files:
            context.active_files.append(file_path)
            # Ограничиваем количество активных файлов
            if len(context.active_files) > 10:
                context.active_files = context.active_files[-10:]
        context.last_activity = time.time()
        self.save_context(context)

    def save_context(self, context: ConversationContext):
        """Сохранить контекст в файл"""
        context_file = self.storage_path / f"{context.session_id}.json"
        try:
            with open(context_file, "w", encoding="utf-8") as f:
                json.dump(context.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения контекста: {e}")

    def get_context_summary(self, session_id: str) -> str:
        """Получить краткое описание контекста для LLM"""
        context = self.get_or_create_context(session_id)

        summary_parts = []

        # Информация о проекте
        if context.project_context:
            summary_parts.append("=== Контекст проекта ===")
            for key, value in context.project_context.items():
                summary_parts.append(f"{key}: {value}")

        # Активные файлы
        if context.active_files:
            summary_parts.append("\n=== Активные файлы ===")
            summary_parts.extend(context.active_files)

        # Рабочая директория
        summary_parts.append(f"\n=== Рабочая директория ===\n{context.working_directory}")

        # Последние сообщения
        recent_messages = context.messages[-5:] if context.messages else []
        if recent_messages:
            summary_parts.append("\n=== Последние сообщения ===")
            for msg in recent_messages:
                timestamp = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M")
                summary_parts.append(f"[{timestamp}] {msg.role}: {msg.content[:100]}...")

        return "\n".join(summary_parts)


# Глобальный менеджер диалогов
conversation_manager = ConversationManager()
