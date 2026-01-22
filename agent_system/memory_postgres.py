"""
PostgreSQL-based память для агента
Замена файловой системы памяти на масштабируемую БД
"""
import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .audit import audit_logger
from .database_tools import db_manager


@dataclass
class MemoryMessage:
    """Сообщение в памяти агента"""

    id: str
    session_id: str
    role: str  # user, assistant, system, tool
    content: str
    timestamp: float
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class MemorySession:
    """Сессия в памяти агента"""

    session_id: str
    user_id: Optional[str]
    created_at: float
    last_activity: float
    metadata: Dict[str, Any]
    message_count: int

class PostgreSQLMemory:
    """Система памяти агента на PostgreSQL"""

    def __init__(self, connection_name: str = "agent_memory"):
        self.connection_name = connection_name
        self.agent_name = "memory_system"

    def initialize_schema(self) -> Dict[str, Any]:
        """Создание схемы БД для памяти агента"""
        try:
            # SQL для создания таблиц
            schema_sql = """
            -- Таблица сессий
            CREATE TABLE IF NOT EXISTS agent_sessions (
                session_id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                metadata JSONB DEFAULT '{}',
                message_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT true
            );
            
            -- Таблица сообщений
            CREATE TABLE IF NOT EXISTS agent_messages (
                id VARCHAR(255) PRIMARY KEY,
                session_id VARCHAR(255) REFERENCES agent_sessions(session_id) ON DELETE CASCADE,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            -- Таблица контекста проектов
            CREATE TABLE IF NOT EXISTS agent_project_context (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) REFERENCES agent_sessions(session_id) ON DELETE CASCADE,
                project_name VARCHAR(255),
                working_directory TEXT,
                active_files JSONB DEFAULT '[]',
                project_metadata JSONB DEFAULT '{}',
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            -- Таблица знаний и фактов
            CREATE TABLE IF NOT EXISTS agent_knowledge (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) REFERENCES agent_sessions(session_id),
                knowledge_type VARCHAR(100), -- fact, preference, skill, context
                key_name VARCHAR(255),
                value_data JSONB,
                confidence FLOAT DEFAULT 1.0,
                source VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                expires_at TIMESTAMP WITH TIME ZONE
            );
            
            -- Индексы для производительности
            CREATE INDEX IF NOT EXISTS idx_messages_session_timestamp 
                ON agent_messages(session_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_messages_role 
                ON agent_messages(role);
            CREATE INDEX IF NOT EXISTS idx_sessions_last_activity 
                ON agent_sessions(last_activity);
            CREATE INDEX IF NOT EXISTS idx_knowledge_session_type 
                ON agent_knowledge(session_id, knowledge_type);
            CREATE INDEX IF NOT EXISTS idx_knowledge_key 
                ON agent_knowledge(key_name);
            
            -- Полнотекстовый поиск
            CREATE INDEX IF NOT EXISTS idx_messages_content_fts 
                ON agent_messages USING gin(to_tsvector('russian', content));
            """

            # Выполняем создание схемы
            result = db_manager.execute_query(self.connection_name, schema_sql)

            if result["success"]:
                audit_logger.log_action(
                    agent=self.agent_name,
                    action="initialize_schema",
                    params={},
                    result="Schema created successfully",
                    success=True,
                )
                return {"success": True, "message": "Schema initialized"}
            else:
                return result

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name, action="initialize_schema", params={}, result=None, success=False, error=str(e)
            )
            return {"success": False, "error": str(e)}

    def create_session(self, session_id: str, user_id: str = None, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Создание новой сессии"""
        try:
            sql = """
            INSERT INTO agent_sessions (session_id, user_id, metadata)
            VALUES (%s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
                last_activity = NOW(),
                metadata = EXCLUDED.metadata
            """

            result = db_manager.execute_query(
                self.connection_name, sql, [session_id, user_id, json.dumps(metadata or {})]
            )

            if result["success"]:
                audit_logger.log_action(
                    agent=self.agent_name,
                    action="create_session",
                    params={"session_id": session_id},
                    result="Session created",
                    success=True,
                )
                return {"success": True, "session_id": session_id}
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Добавление сообщения в память"""
        try:
            message_id = str(uuid.uuid4())

            # Добавляем сообщение
            sql_message = """
            INSERT INTO agent_messages (id, session_id, role, content, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """

            result = db_manager.execute_query(
                self.connection_name, sql_message, [message_id, session_id, role, content, json.dumps(metadata or {})]
            )

            if not result["success"]:
                return result

            # Обновляем счетчик сообщений и активность сессии
            sql_update = """
            UPDATE agent_sessions 
            SET message_count = message_count + 1, last_activity = NOW()
            WHERE session_id = %s
            """

            db_manager.execute_query(self.connection_name, sql_update, [session_id])

            audit_logger.log_action(
                agent=self.agent_name,
                action="add_message",
                params={"session_id": session_id, "role": role},
                result=f"Message added: {message_id}",
                success=True,
            )

            return {"success": True, "message_id": message_id}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_conversation_history(self, session_id: str, limit: int = 50, role_filter: str = None) -> Dict[str, Any]:
        """Получение истории диалога"""
        try:
            sql = """
            SELECT id, role, content, timestamp, metadata
            FROM agent_messages
            WHERE session_id = %s
            """
            params = [session_id]

            if role_filter:
                sql += " AND role = %s"
                params.append(role_filter)

            sql += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)

            result = db_manager.execute_query(self.connection_name, sql, params)

            if result["success"]:
                # Переворачиваем порядок для хронологической последовательности
                messages = list(reversed(result["rows"]))

                return {"success": True, "messages": messages, "count": len(messages)}
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_messages(self, session_id: str, query: str, limit: int = 20) -> Dict[str, Any]:
        """Полнотекстовый поиск по сообщениям"""
        try:
            sql = """
            SELECT id, role, content, timestamp, metadata,
                   ts_rank(to_tsvector('russian', content), plainto_tsquery('russian', %s)) as rank
            FROM agent_messages
            WHERE session_id = %s 
                AND to_tsvector('russian', content) @@ plainto_tsquery('russian', %s)
            ORDER BY rank DESC, timestamp DESC
            LIMIT %s
            """

            result = db_manager.execute_query(self.connection_name, sql, [query, session_id, query, limit])

            if result["success"]:
                return {"success": True, "messages": result["rows"], "query": query, "count": len(result["rows"])}
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_project_context(self, session_id: str, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновление контекста проекта"""
        try:
            sql = """
            INSERT INTO agent_project_context 
                (session_id, project_name, working_directory, active_files, project_metadata)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
                project_name = EXCLUDED.project_name,
                working_directory = EXCLUDED.working_directory,
                active_files = EXCLUDED.active_files,
                project_metadata = EXCLUDED.project_metadata,
                updated_at = NOW()
            """

            result = db_manager.execute_query(
                self.connection_name,
                sql,
                [
                    session_id,
                    project_data.get("project_name"),
                    project_data.get("working_directory"),
                    json.dumps(project_data.get("active_files", [])),
                    json.dumps(project_data.get("metadata", {})),
                ],
            )

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def store_knowledge(
        self,
        session_id: str,
        knowledge_type: str,
        key: str,
        value: Any,
        confidence: float = 1.0,
        source: str = "user",
        expires_hours: int = None,
    ) -> Dict[str, Any]:
        """Сохранение знаний/фактов"""
        try:
            expires_at = None
            if expires_hours:
                expires_at = datetime.now() + timedelta(hours=expires_hours)

            sql = """
            INSERT INTO agent_knowledge 
                (session_id, knowledge_type, key_name, value_data, confidence, source, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id, key_name) DO UPDATE SET
                value_data = EXCLUDED.value_data,
                confidence = EXCLUDED.confidence,
                source = EXCLUDED.source,
                expires_at = EXCLUDED.expires_at,
                created_at = NOW()
            """

            result = db_manager.execute_query(
                self.connection_name,
                sql,
                [session_id, knowledge_type, key, json.dumps(value), confidence, source, expires_at],
            )

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_knowledge(self, session_id: str, knowledge_type: str = None, key: str = None) -> Dict[str, Any]:
        """Получение знаний"""
        try:
            sql = """
            SELECT knowledge_type, key_name, value_data, confidence, source, created_at
            FROM agent_knowledge
            WHERE session_id = %s 
                AND (expires_at IS NULL OR expires_at > NOW())
            """
            params = [session_id]

            if knowledge_type:
                sql += " AND knowledge_type = %s"
                params.append(knowledge_type)

            if key:
                sql += " AND key_name = %s"
                params.append(key)

            sql += " ORDER BY created_at DESC"

            result = db_manager.execute_query(self.connection_name, sql, params)

            if result["success"]:
                # Десериализуем JSON данные
                for row in result["rows"]:
                    row["value_data"] = json.loads(row["value_data"])

                return {"success": True, "knowledge": result["rows"], "count": len(result["rows"])}
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Получение сводки по сессии"""
        try:
            sql = """
            SELECT 
                s.session_id,
                s.user_id,
                s.created_at,
                s.last_activity,
                s.message_count,
                s.metadata as session_metadata,
                pc.project_name,
                pc.working_directory,
                pc.active_files,
                pc.project_metadata
            FROM agent_sessions s
            LEFT JOIN agent_project_context pc ON s.session_id = pc.session_id
            WHERE s.session_id = %s
            """

            result = db_manager.execute_query(self.connection_name, sql, [session_id])

            if result["success"] and result["rows"]:
                session_data = result["rows"][0]

                # Получаем последние сообщения
                recent_messages = self.get_conversation_history(session_id, limit=5)

                # Получаем знания
                knowledge = self.get_knowledge(session_id)

                return {
                    "success": True,
                    "session": session_data,
                    "recent_messages": recent_messages.get("messages", []),
                    "knowledge": knowledge.get("knowledge", []),
                }
            else:
                return {"success": False, "error": "Session not found"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def cleanup_old_sessions(self, days_old: int = 30) -> Dict[str, Any]:
        """Очистка старых сессий"""
        try:
            sql = """
            DELETE FROM agent_sessions 
            WHERE last_activity < NOW() - INTERVAL '%s days'
            """

            result = db_manager.execute_query(self.connection_name, sql, [days_old])

            if result["success"]:
                audit_logger.log_action(
                    agent=self.agent_name,
                    action="cleanup_sessions",
                    params={"days_old": days_old},
                    result=f"Cleaned {result.get('affected_rows', 0)} sessions",
                    success=True,
                )

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

# Глобальный экземпляр PostgreSQL памяти
postgres_memory = PostgreSQLMemory()
