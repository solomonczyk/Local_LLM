"""
Инструменты для работы с базами данных (PostgreSQL)
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from .config import AgentConfig, SecurityConfig
from .audit import audit_logger

try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False


class DatabaseManager:
    """Менеджер для работы с базами данных"""
    
    def __init__(self, agent_name: str = "db_agent"):
        self.agent_name = agent_name
        self.connections = {}  # Кэш подключений
        self.config_file = Path(".agent_db_config.json")
        
    def add_connection(self, name: str, connection_params: Dict[str, Any]) -> Dict[str, Any]:
        """Добавить конфигурацию подключения к БД"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_SAFE_WRITE:
                raise PermissionError("Database configuration access denied")
            
            # Валидация параметров
            required_params = ["host", "database", "user", "password"]
            for param in required_params:
                if param not in connection_params:
                    raise ValueError(f"Missing required parameter: {param}")
            
            # Загружаем существующие конфигурации
            configs = self._load_configs()
            
            # Добавляем новую конфигурацию (пароль не сохраняем в файл)
            safe_params = connection_params.copy()
            safe_params["password"] = "***"  # Маскируем пароль
            configs[name] = safe_params
            
            # Сохраняем конфигурации
            self._save_configs(configs)
            
            # Тестируем подключение
            test_result = self._test_connection(connection_params)
            
            audit_logger.log_action(
                agent=self.agent_name,
                action="add_db_connection",
                params={"name": name, "host": connection_params["host"]},
                result=f"Connection added, test: {test_result['status']}",
                success=test_result["success"]
            )
            
            return {
                "success": True,
                "name": name,
                "test_result": test_result
            }
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="add_db_connection",
                params={"name": name},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
    
    def execute_query(self, connection_name: str, query: str, params: List = None) -> Dict[str, Any]:
        """Выполнить SQL запрос"""
        try:
            if not POSTGRES_AVAILABLE:
                raise ImportError("psycopg2 not installed. Install with: pip install psycopg2-binary")
            
            # Проверка безопасности запроса
            is_safe, reason = self._is_query_safe(query)
            if not is_safe:
                raise PermissionError(f"Unsafe query: {reason}")
            
            # Получаем подключение
            conn = self._get_connection(connection_name)
            if not conn:
                raise ConnectionError(f"No connection found: {connection_name}")
            
            # Выполняем запрос
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params or [])
                
                # Определяем тип операции
                query_type = query.strip().upper().split()[0]
                
                if query_type in ["SELECT", "SHOW", "DESCRIBE", "EXPLAIN"]:
                    # Запросы на чтение
                    results = cursor.fetchall()
                    result_data = [dict(row) for row in results]
                    
                    audit_logger.log_action(
                        agent=self.agent_name,
                        action="execute_query",
                        params={"connection": connection_name, "type": "SELECT"},
                        result=f"Retrieved {len(result_data)} rows",
                        success=True
                    )
                    
                    return {
                        "success": True,
                        "query_type": "SELECT",
                        "rows": result_data,
                        "row_count": len(result_data)
                    }
                
                else:
                    # Запросы на изменение
                    conn.commit()
                    affected_rows = cursor.rowcount
                    
                    audit_logger.log_action(
                        agent=self.agent_name,
                        action="execute_query",
                        params={"connection": connection_name, "type": query_type},
                        result=f"Affected {affected_rows} rows",
                        success=True
                    )
                    
                    return {
                        "success": True,
                        "query_type": query_type,
                        "affected_rows": affected_rows
                    }
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="execute_query",
                params={"connection": connection_name, "query": query[:100]},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
    
    def get_schema_info(self, connection_name: str, table_name: str = None) -> Dict[str, Any]:
        """Получить информацию о схеме БД"""
        try:
            if table_name:
                # Информация о конкретной таблице
                query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
                """
                result = self.execute_query(connection_name, query, [table_name])
                
                if result["success"]:
                    return {
                        "success": True,
                        "table": table_name,
                        "columns": result["rows"]
                    }
                else:
                    return result
            
            else:
                # Список всех таблиц
                query = """
                SELECT 
                    table_name,
                    table_type
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
                result = self.execute_query(connection_name, query)
                
                if result["success"]:
                    return {
                        "success": True,
                        "tables": result["rows"]
                    }
                else:
                    return result
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_connection(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Тестирование подключения к БД"""
        try:
            if not POSTGRES_AVAILABLE:
                return {
                    "success": False,
                    "status": "psycopg2 not available",
                    "error": "Install with: pip install psycopg2-binary"
                }
            
            conn = psycopg2.connect(
                host=params["host"],
                database=params["database"],
                user=params["user"],
                password=params["password"],
                port=params.get("port", 5432),
                connect_timeout=5
            )
            
            # Тестовый запрос
            with conn.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "success": True,
                "status": "connected",
                "version": version
            }
        
        except Exception as e:
            return {
                "success": False,
                "status": "connection_failed",
                "error": str(e)
            }
    
    def _get_connection(self, name: str):
        """Получить подключение к БД"""
        if name in self.connections:
            return self.connections[name]
        
        # Загружаем конфигурацию (пароль нужно будет запросить отдельно)
        configs = self._load_configs()
        if name not in configs:
            return None
        
        # В реальной системе пароль должен запрашиваться безопасно
        # Пока используем заглушку
        return None
    
    def _is_query_safe(self, query: str) -> Tuple[bool, str]:
        """Проверка безопасности SQL запроса"""
        query_upper = query.upper().strip()
        
        # Разрешенные операции
        safe_operations = [
            "SELECT", "SHOW", "DESCRIBE", "EXPLAIN",
            "INSERT", "UPDATE", "DELETE"  # Только с WHERE
        ]
        
        # Запрещенные операции
        dangerous_operations = [
            "DROP", "TRUNCATE", "ALTER", "CREATE",
            "GRANT", "REVOKE", "SHUTDOWN"
        ]
        
        # Проверяем на опасные операции
        for op in dangerous_operations:
            if query_upper.startswith(op):
                return False, f"Dangerous operation: {op}"
        
        # Проверяем DELETE/UPDATE без WHERE
        if query_upper.startswith(("DELETE", "UPDATE")):
            if "WHERE" not in query_upper:
                return False, "DELETE/UPDATE without WHERE clause"
        
        return True, "OK"
    
    def _load_configs(self) -> Dict[str, Any]:
        """Загрузить конфигурации подключений"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_configs(self, configs: Dict[str, Any]):
        """Сохранить конфигурации подключений"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(configs, f, indent=2, ensure_ascii=False)


# Глобальный менеджер БД
db_manager = DatabaseManager()