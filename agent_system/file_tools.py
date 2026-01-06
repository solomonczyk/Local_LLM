"""
File operations tools с безопасностью
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audit import audit_logger
from .config import AgentConfig, SecurityConfig


class FileTools:
    """
    Безопасные инструменты для работы с файлами.
    
    Предоставляет защищенные операции с файловой системой с:
    - Проверкой безопасности путей (sandbox в workspace)
    - Контролем доступа по уровням безопасности
    - Автоматическим созданием backup'ов
    - Аудитом всех операций
    - Валидацией размеров файлов
    
    Все операции записи требуют соответствующего уровня доступа
    и автоматически создают резервные копии перед изменениями.
    
    Attributes:
        agent_name: Имя агента для аудита операций
        workspace: Корневая директория workspace (sandbox)
        
    Example:
        >>> file_tools = FileTools("my_agent")
        >>> result = file_tools.read_file("config.json")
        >>> if result["success"]:
        ...     print(f"File content: {result['content']}")
    """

    def __init__(self, agent_name: str = "system") -> None:
        """
        Инициализация инструментов для работы с файлами.
        
        Args:
            agent_name: Имя агента для аудита операций
        """
        self.agent_name = agent_name
        self.workspace = SecurityConfig.WORKSPACE_ROOT

    def read_file(self, path: str) -> Dict[str, Any]:
        """
        Безопасное чтение файла с проверками.
        
        Args:
            path: Относительный путь к файлу от workspace
            
        Returns:
            Dict с результатом операции: success, content, path или error
            
        Raises:
            PermissionError: Если путь вне workspace
            FileNotFoundError: Если файл не найден
            ValueError: Если файл слишком большой
        """
        # Input validation
        if not path or not isinstance(path, str):
            return {"success": False, "error": "Path must be a non-empty string"}
        
        if path.strip() != path:
            return {"success": False, "error": "Path contains leading/trailing whitespace"}
        
        if len(path) > 1000:
            return {"success": False, "error": "Path too long (max 1000 characters)"}
        
        try:
            file_path = (self.workspace / path).resolve()

            # Проверка безопасности
            if not SecurityConfig.is_path_safe(file_path):
                raise PermissionError(f"Path outside workspace: {path}")

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            if not file_path.is_file():
                raise ValueError(f"Path is not a file: {path}")

            # Проверка размера
            file_size = file_path.stat().st_size
            if file_size > SecurityConfig.MAX_FILE_SIZE:
                raise ValueError(f"File too large: {file_size} bytes > {SecurityConfig.MAX_FILE_SIZE}")

            content = file_path.read_text(encoding="utf-8")

            audit_logger.log_action(
                agent=self.agent_name,
                action="read_file",
                params={"path": path, "size": len(content)},
                result=f"Read {len(content)} chars",
                success=True,
            )

            return {"success": True, "content": content, "path": str(file_path), "size": len(content)}

        except (PermissionError, FileNotFoundError, ValueError) as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="read_file",
                params={"path": path},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}
        except UnicodeDecodeError as e:
            error_msg = f"File encoding error: {e}"
            audit_logger.log_action(
                agent=self.agent_name,
                action="read_file",
                params={"path": path},
                result=None,
                success=False,
                error=error_msg,
            )
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error reading file: {e}"
            audit_logger.log_action(
                agent=self.agent_name,
                action="read_file",
                params={"path": path},
                result=None,
                success=False,
                error=error_msg,
            )
            return {"success": False, "error": error_msg}

    def write_file(self, path: str, content: str, mode: str = "overwrite") -> Dict[str, Any]:
        """Запись файла"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_SAFE_WRITE:
                raise PermissionError("Write access denied at current level")

            file_path = (self.workspace / path).resolve()

            if not SecurityConfig.is_path_safe(file_path):
                raise PermissionError(f"Path outside workspace: {path}")

            # Создаем директории если нужно
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Backup если файл существует
            if file_path.exists() and mode == "overwrite":
                backup_path = file_path.with_suffix(file_path.suffix + ".backup")
                backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")

            file_path.write_text(content, encoding="utf-8")

            audit_logger.log_action(
                agent=self.agent_name,
                action="write_file",
                params={"path": path, "mode": mode, "size": len(content)},
                result=f"Written {len(content)} chars",
                success=True,
            )

            return {"success": True, "path": str(file_path), "size": len(content)}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="write_file",
                params={"path": path, "mode": mode},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    def delete_file(self, path: str) -> Dict[str, Any]:
        """Удаление файла"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_SAFE_WRITE:
                raise PermissionError("Delete access denied at current level")

            file_path = (self.workspace / path).resolve()

            if not SecurityConfig.is_path_safe(file_path):
                raise PermissionError(f"Path outside workspace: {path}")

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            if file_path.is_dir():
                raise IsADirectoryError(f"Path is a directory, not a file: {path}")

            # Создаем backup перед удалением
            backup_path = file_path.with_suffix(file_path.suffix + ".deleted_backup")
            backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")

            # Удаляем файл
            file_path.unlink()

            audit_logger.log_action(
                agent=self.agent_name,
                action="delete_file",
                params={"path": path},
                result=f"Deleted file, backup: {backup_path.name}",
                success=True,
            )

            return {"success": True, "path": str(file_path), "backup": str(backup_path)}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="delete_file",
                params={"path": path},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    def edit_file(self, path: str, old_text: str, new_text: str) -> Dict[str, Any]:
        """Редактирование части файла (замена текста)"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_SAFE_WRITE:
                raise PermissionError("Edit access denied at current level")

            file_path = (self.workspace / path).resolve()

            if not SecurityConfig.is_path_safe(file_path):
                raise PermissionError(f"Path outside workspace: {path}")

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            # Читаем содержимое
            content = file_path.read_text(encoding="utf-8")

            # Проверяем, что старый текст есть в файле
            if old_text not in content:
                raise ValueError(f"Text not found in file: {old_text[:50]}...")

            # Создаем backup
            backup_path = file_path.with_suffix(file_path.suffix + ".backup")
            backup_path.write_text(content, encoding="utf-8")

            # Заменяем текст
            new_content = content.replace(old_text, new_text)

            # Записываем обновленное содержимое
            file_path.write_text(new_content, encoding="utf-8")

            audit_logger.log_action(
                agent=self.agent_name,
                action="edit_file",
                params={"path": path, "old_length": len(old_text), "new_length": len(new_text)},
                result=f"Replaced text, backup: {backup_path.name}",
                success=True,
            )

            return {
                "success": True,
                "path": str(file_path),
                "backup": str(backup_path),
                "old_size": len(content),
                "new_size": len(new_content),
            }

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="edit_file",
                params={"path": path},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    def copy_file(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """Копирование файла"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_SAFE_WRITE:
                raise PermissionError("Copy access denied at current level")

            source = (self.workspace / source_path).resolve()
            dest = (self.workspace / dest_path).resolve()

            if not SecurityConfig.is_path_safe(source):
                raise PermissionError(f"Source path outside workspace: {source_path}")

            if not SecurityConfig.is_path_safe(dest):
                raise PermissionError(f"Destination path outside workspace: {dest_path}")

            if not source.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")

            if source.is_dir():
                raise IsADirectoryError(f"Source is a directory: {source_path}")

            # Создаем директории если нужно
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Копируем файл
            import shutil

            shutil.copy2(source, dest)

            audit_logger.log_action(
                agent=self.agent_name,
                action="copy_file",
                params={"source": source_path, "dest": dest_path},
                result=f"Copied {source.stat().st_size} bytes",
                success=True,
            )

            return {"success": True, "source": str(source), "dest": str(dest), "size": dest.stat().st_size}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="copy_file",
                params={"source": source_path, "dest": dest_path},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    def move_file(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """Перемещение/переименование файла"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_SAFE_WRITE:
                raise PermissionError("Move access denied at current level")

            source = (self.workspace / source_path).resolve()
            dest = (self.workspace / dest_path).resolve()

            if not SecurityConfig.is_path_safe(source):
                raise PermissionError(f"Source path outside workspace: {source_path}")

            if not SecurityConfig.is_path_safe(dest):
                raise PermissionError(f"Destination path outside workspace: {dest_path}")

            if not source.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")

            # Создаем директории если нужно
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Перемещаем файл
            source.rename(dest)

            audit_logger.log_action(
                agent=self.agent_name,
                action="move_file",
                params={"source": source_path, "dest": dest_path},
                result=f"Moved to {dest_path}",
                success=True,
            )

            return {"success": True, "source": source_path, "dest": str(dest)}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="move_file",
                params={"source": source_path, "dest": dest_path},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    def list_dir(self, path: str = ".", pattern: str = "*") -> Dict[str, Any]:
        """Список файлов в директории"""
        try:
            dir_path = (self.workspace / path).resolve()

            if not SecurityConfig.is_path_safe(dir_path):
                raise PermissionError(f"Path outside workspace: {path}")

            if not dir_path.exists():
                raise FileNotFoundError(f"Directory not found: {path}")

            files = []
            for item in dir_path.glob(pattern):
                rel_path = item.relative_to(self.workspace)
                files.append(
                    {
                        "path": str(rel_path),
                        "name": item.name,
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else 0,
                    }
                )

            audit_logger.log_action(
                agent=self.agent_name,
                action="list_dir",
                params={"path": path, "pattern": pattern},
                result=f"Found {len(files)} items",
                success=True,
            )

            return {"success": True, "files": files}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="list_dir",
                params={"path": path},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    def search(self, query: str, globs: Optional[List[str]] = None) -> Dict[str, Any]:
        """Поиск в файлах"""
        try:
            if globs is None:
                globs = ["**/*.py", "**/*.js", "**/*.ts", "**/*.md"]

            results = []
            for glob_pattern in globs:
                for file_path in self.workspace.glob(glob_pattern):
                    if not file_path.is_file():
                        continue

                    try:
                        content = file_path.read_text(encoding="utf-8")
                        if query.lower() in content.lower():
                            rel_path = file_path.relative_to(self.workspace)
                            results.append(str(rel_path))
                    except (UnicodeDecodeError, PermissionError):
                        continue

            audit_logger.log_action(
                agent=self.agent_name,
                action="search",
                params={"query": query, "globs": globs},
                result=f"Found in {len(results)} files",
                success=True,
            )

            return {"success": True, "files": results, "count": len(results)}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="search",
                params={"query": query},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}
