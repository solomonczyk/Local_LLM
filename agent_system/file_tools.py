"""
File operations tools с безопасностью
"""
import difflib
import fnmatch
import hashlib
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

    _MAX_DIFF_CHARS = 8000
    _MAX_PREVIEW_CHARS = 2000

    def _truncate_text(self, text: str, limit: int) -> Tuple[str, bool]:
        if len(text) <= limit:
            return text, False
        return text[:limit] + "\n...[truncated]...", True

    def _build_diff(self, before: str, after: str, path: str) -> Tuple[str, bool]:
        diff_lines = list(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=path,
                tofile=path,
                lineterm="",
            )
        )
        diff_text = "\n".join(diff_lines)
        return self._truncate_text(diff_text, self._MAX_DIFF_CHARS)

    def _hash_file(self, file_path: Path) -> str:
        sha = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def _ensure_expected_state(
        self,
        file_path: Path,
        expected_sha256: Optional[str],
        expected_exists: Optional[bool],
        action: str,
    ) -> None:
        if expected_exists is not None:
            exists = file_path.exists()
            if exists != expected_exists:
                raise ValueError(f"{action} blocked: expected exists={expected_exists}, found {exists}")

        if expected_sha256:
            if not file_path.exists() or not file_path.is_file():
                raise FileNotFoundError(f"{action} blocked: file not found for hash check")
            current_hash = self._hash_file(file_path)
            if current_hash != expected_sha256:
                raise ValueError(f"{action} blocked: file changed since preview")

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

        normalized_path = path.replace("\\", "/")
        try:
            file_path = (self.workspace / normalized_path).resolve()

            # Проверка безопасности
            if not SecurityConfig.is_path_safe(file_path):
                raise PermissionError(f"Path outside workspace: {normalized_path}")

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {normalized_path}")

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
                params={"path": normalized_path, "size": len(content)},
                result=f"Read {len(content)} chars",
                success=True,
            )

            return {"success": True, "content": content, "path": str(file_path), "size": len(content)}

        except (PermissionError, FileNotFoundError, ValueError) as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="read_file",
                params={"path": normalized_path},
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
                params={"path": normalized_path},
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
                params={"path": normalized_path},
                result=None,
                success=False,
                error=error_msg,
            )
            return {"success": False, "error": error_msg}

    def write_file(
        self,
        path: str,
        content: str,
        mode: str = "overwrite",
        dry_run: bool = False,
        expected_sha256: Optional[str] = None,
        expected_exists: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Запись файла"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_SAFE_WRITE:
                raise PermissionError("Write access denied at current level")

            file_path = (self.workspace / path).resolve()

            if not SecurityConfig.is_path_safe(file_path):
                raise PermissionError(f"Path outside workspace: {path}")

            # Создаем директории если нужно
            if not dry_run:
                self._ensure_expected_state(file_path, expected_sha256, expected_exists, "write_file")

            if dry_run:
                parent_exists = file_path.parent.exists()
                file_exists = file_path.exists()
                existing = ""
                if file_exists:
                    if not file_path.is_file():
                        raise ValueError(f"Path is not a file: {path}")
                    try:
                        existing = file_path.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        existing = file_path.read_text(encoding="utf-8", errors="ignore")

                if mode == "append":
                    new_content = existing + content
                else:
                    new_content = content

                diff_text, truncated = self._build_diff(existing, new_content, path)
                if mode == "append":
                    summary = f"Would append {len(content)} chars to {path}"
                elif file_exists:
                    summary = f"Would overwrite {path} with {len(content)} chars"
                else:
                    summary = f"Would create {path} with {len(content)} chars"
                if not parent_exists:
                    summary += " (parent dirs missing)"

                sha256 = self._hash_file(file_path) if file_exists else None
                try:
                    rel_path = str(file_path.relative_to(self.workspace))
                except ValueError:
                    rel_path = path

                audit_logger.log_action(
                    agent=self.agent_name,
                    action="write_file_dry_run",
                    params={"path": path, "mode": mode, "size": len(content), "dry_run": True},
                    result=summary,
                    success=True,
                )

                return {
                    "success": True,
                    "dry_run": True,
                    "action": "write_file",
                    "path": str(file_path),
                    "mode": mode,
                    "size": len(content),
                    "parent_exists": parent_exists,
                    "exists": file_exists,
                    "sha256": sha256,
                    "path_relative": rel_path,
                    "summary": summary,
                    "diff": diff_text,
                    "diff_truncated": truncated,
                }

            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Backup если файл существует
            if file_path.exists() and mode == "overwrite":
                backup_path = file_path.with_suffix(file_path.suffix + ".backup")
                backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")

            if mode == "append":
                with file_path.open("a", encoding="utf-8") as handle:
                    handle.write(content)
            else:
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

    def delete_file(
        self,
        path: str,
        dry_run: bool = False,
        expected_sha256: Optional[str] = None,
        expected_exists: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Удаление файла"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_SAFE_WRITE:
                raise PermissionError("Delete access denied at current level")

            file_path = (self.workspace / path).resolve()

            if not SecurityConfig.is_path_safe(file_path):
                raise PermissionError(f"Path outside workspace: {path}")

            if not dry_run:
                self._ensure_expected_state(file_path, expected_sha256, expected_exists, "delete_file")

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            if file_path.is_dir():
                raise IsADirectoryError(f"Path is a directory, not a file: {path}")

            if dry_run:
                size = file_path.stat().st_size
                try:
                    preview_text = file_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    preview_text = file_path.read_text(encoding="utf-8", errors="ignore")

                preview, truncated = self._truncate_text(preview_text, self._MAX_PREVIEW_CHARS)
                backup_path = file_path.with_suffix(file_path.suffix + ".deleted_backup")
                summary = f"Would delete {path} ({size} bytes)"
                sha256 = self._hash_file(file_path)
                try:
                    rel_path = str(file_path.relative_to(self.workspace))
                except ValueError:
                    rel_path = path

                audit_logger.log_action(
                    agent=self.agent_name,
                    action="delete_file_dry_run",
                    params={"path": path, "dry_run": True},
                    result=summary,
                    success=True,
                )

                return {
                    "success": True,
                    "dry_run": True,
                    "action": "delete_file",
                    "path": str(file_path),
                    "backup": str(backup_path),
                    "size": size,
                    "exists": True,
                    "sha256": sha256,
                    "path_relative": rel_path,
                    "summary": summary,
                    "preview": preview,
                    "preview_truncated": truncated,
                }

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

    def edit_file(
        self,
        path: str,
        old_text: str,
        new_text: str,
        dry_run: bool = False,
        expected_sha256: Optional[str] = None,
        expected_exists: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Редактирование части файла (замена текста)"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_SAFE_WRITE:
                raise PermissionError("Edit access denied at current level")

            file_path = (self.workspace / path).resolve()

            if not SecurityConfig.is_path_safe(file_path):
                raise PermissionError(f"Path outside workspace: {path}")

            if not dry_run:
                self._ensure_expected_state(file_path, expected_sha256, expected_exists, "edit_file")

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

            if dry_run:
                diff_text, truncated = self._build_diff(content, new_content, path)
                summary = f"Would replace {len(old_text)} chars with {len(new_text)} chars in {path}"
                sha256 = self._hash_file(file_path)
                try:
                    rel_path = str(file_path.relative_to(self.workspace))
                except ValueError:
                    rel_path = path

                audit_logger.log_action(
                    agent=self.agent_name,
                    action="edit_file_dry_run",
                    params={"path": path, "dry_run": True},
                    result=summary,
                    success=True,
                )

                return {
                    "success": True,
                    "dry_run": True,
                    "action": "edit_file",
                    "path": str(file_path),
                    "old_size": len(content),
                    "new_size": len(new_content),
                    "exists": True,
                    "sha256": sha256,
                    "path_relative": rel_path,
                    "summary": summary,
                    "diff": diff_text,
                    "diff_truncated": truncated,
                }

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

    def copy_file(
        self,
        source_path: str,
        dest_path: str,
        dry_run: bool = False,
        expected_source_sha256: Optional[str] = None,
        expected_dest_sha256: Optional[str] = None,
        expected_source_exists: Optional[bool] = None,
        expected_dest_exists: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Копирование файла"""
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

            if not dry_run:
                self._ensure_expected_state(source, expected_source_sha256, expected_source_exists, "move_file")
                self._ensure_expected_state(dest, expected_dest_sha256, expected_dest_exists, "move_file")

            if not source.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")

            if source.is_dir():
                raise IsADirectoryError(f"Source is a directory: {source_path}")

            if dry_run:
                dest_exists = dest.exists()
                size = source.stat().st_size
                summary = f"Would move {source_path} to {dest_path} ({size} bytes)"
                if dest_exists:
                    summary += " (overwrite)"
                source_sha256 = self._hash_file(source)
                dest_sha256 = self._hash_file(dest) if dest_exists and dest.is_file() else None
                try:
                    source_rel = str(source.relative_to(self.workspace))
                except ValueError:
                    source_rel = source_path
                try:
                    dest_rel = str(dest.relative_to(self.workspace))
                except ValueError:
                    dest_rel = dest_path

                audit_logger.log_action(
                    agent=self.agent_name,
                    action="move_file_dry_run",
                    params={"source": source_path, "dest": dest_path, "dry_run": True},
                    result=summary,
                    success=True,
                )

                return {
                    "success": True,
                    "dry_run": True,
                    "action": "move_file",
                    "source": str(source),
                    "dest": str(dest),
                    "size": size,
                    "dest_exists": dest_exists,
                    "source_exists": True,
                    "source_sha256": source_sha256,
                    "dest_sha256": dest_sha256,
                    "source_relative": source_rel,
                    "dest_relative": dest_rel,
                    "summary": summary,
                }

            # Создаем директории если нужно
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Копируем файл
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
                action="copy_file",
                params={"source": source_path, "dest": dest_path},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    def move_file(
        self,
        source_path: str,
        dest_path: str,
        dry_run: bool = False,
        expected_source_sha256: Optional[str] = None,
        expected_dest_sha256: Optional[str] = None,
        expected_source_exists: Optional[bool] = None,
        expected_dest_exists: Optional[bool] = None,
    ) -> Dict[str, Any]:
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

            if not dry_run:
                self._ensure_expected_state(source, expected_source_sha256, expected_source_exists, "copy_file")
                self._ensure_expected_state(dest, expected_dest_sha256, expected_dest_exists, "copy_file")

            if not source.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")

            if dry_run:
                dest_exists = dest.exists()
                size = source.stat().st_size
                summary = f"Would move {source_path} to {dest_path} ({size} bytes)"
                if dest_exists:
                    summary += " (overwrite)"

                audit_logger.log_action(
                    agent=self.agent_name,
                    action="move_file_dry_run",
                    params={"source": source_path, "dest": dest_path, "dry_run": True},
                    result=summary,
                    success=True,
                )

                return {
                    "success": True,
                    "dry_run": True,
                    "action": "move_file",
                    "source": source_path,
                    "dest": str(dest),
                    "size": size,
                    "dest_exists": dest_exists,
                    "summary": summary,
                }

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

    def search(
        self,
        query: str,
        globs: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        max_files: Optional[int] = None,
    ) -> Dict[str, Any]:
        """????? ? ??????"""
        try:
            if not isinstance(query, str) or not query.strip():
                return {"success": False, "error": "Query must be a non-empty string"}

            if globs is None:
                globs = [
                    "**/*.py",
                    "**/*.js",
                    "**/*.ts",
                    "**/*.md",
                    "**/*.yml",
                    "**/*.yaml",
                    "**/*.json",
                    "**/*.toml",
                    "**/*.conf",
                    "**/*.ini",
                    "**/*.env",
                    "**/*.sh",
                    "**/*.ps1",
                    "Dockerfile",
                    "docker-compose*.yml",
                ]

            # Treat `a|b|c` as simple OR (not full regex) to support common queries like TODO|FIXME.
            needles = [part.strip() for part in query.split("|")] if "|" in query else [query.strip()]
            needles = [n for n in needles if n]
            needles_lower = [n.lower() for n in needles]

            max_hits = max_results or int(os.getenv("SEARCH_MAX_HITS", "200"))
            max_files_limit = max_files or int(os.getenv("SEARCH_MAX_FILES", "5000"))
            max_scanned = int(os.getenv("SEARCH_MAX_SCANNED", str(max_files_limit)))
            max_seconds = float(os.getenv("SEARCH_MAX_SECONDS", "10"))
            deadline = time.monotonic() + max_seconds

            exclude_dirs_raw = os.getenv(
                "SEARCH_EXCLUDE_DIRS",
                ".git,.venv,.venv312,__pycache__,models,codesearchnet_python_1pct,"
                "codesearchnet_python_1pct_filtered,lora_qwen2_5_coder_1_5b_python,"
                ".agent_conversations,agent_data,agent_logs,reports,ssl",
            )
            exclude_dirs = {part.strip() for part in exclude_dirs_raw.split(",") if part.strip()}

            def _git_ls_files() -> Optional[List[str]]:
                if not (self.workspace / ".git").exists():
                    return None
                try:
                    out = subprocess.check_output(
                        ["git", "-C", str(self.workspace), "ls-files"],
                        text=True,
                        stderr=subprocess.STDOUT,
                        timeout=10,
                    )
                    return [line.strip() for line in out.splitlines() if line.strip()]
                except Exception:
                    return None

            def _matches_any_glob(rel_path: str) -> bool:
                for pattern in globs or []:
                    if fnmatch.fnmatch(rel_path, pattern):
                        return True
                    if pattern.startswith("**/") and fnmatch.fnmatch(rel_path, pattern[3:]):
                        return True
                return False

            def _is_excluded(rel_path: Path) -> bool:
                for part in rel_path.parts:
                    if part in exclude_dirs:
                        return True
                return False

            def _time_exceeded() -> bool:
                return time.monotonic() > deadline

            matches: List[Dict[str, Any]] = []
            files_with_hits: List[str] = []
            scanned_files = 0
            candidates_truncated = False
            timed_out = False

            tracked = _git_ls_files()
            candidates: List[Path] = []
            if tracked is None:
                for root, dirs, files in os.walk(self.workspace):
                    rel_root = Path(root).relative_to(self.workspace)
                    dirs[:] = [d for d in dirs if not _is_excluded(rel_root / d)]
                    if _time_exceeded():
                        timed_out = True
                        break
                    for name in files:
                        if len(candidates) >= max_files_limit:
                            candidates_truncated = True
                            break
                        rel_path = (rel_root / name).as_posix()
                        if _matches_any_glob(rel_path):
                            candidates.append(self.workspace / rel_path)
                    if candidates_truncated:
                        break
            else:
                for rel in tracked:
                    if len(candidates) >= max_files_limit:
                        candidates_truncated = True
                        break
                    rel_path = Path(rel)
                    if _is_excluded(rel_path):
                        continue
                    if _matches_any_glob(rel_path.as_posix()):
                        candidates.append(self.workspace / rel_path)
                    if _time_exceeded():
                        timed_out = True
                        break

            for file_path in candidates:
                if not file_path.is_file():
                    continue
                try:
                    if file_path.stat().st_size > SecurityConfig.MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue

                scanned_files += 1
                if scanned_files > max_scanned:
                    candidates_truncated = True
                    break
                if _time_exceeded():
                    timed_out = True
                    break

                rel_path = str(file_path.relative_to(self.workspace))
                rel_path_lower = rel_path.lower()
                path_query = any(ch in query for ch in (".", "/", "\\"))
                if any(needle in rel_path_lower for needle in needles_lower):
                    if rel_path not in files_with_hits:
                        files_with_hits.append(rel_path)
                    matches.append({"path": rel_path, "line": 0, "text": "(path match)"})
                    if len(matches) >= max_hits:
                        break
                    if path_query:
                        continue

                try:
                    with file_path.open("r", encoding="utf-8") as handle:
                        for line_no, line in enumerate(handle, start=1):
                            hay = line.lower()
                            if any(needle in hay for needle in needles_lower):
                                if rel_path not in files_with_hits:
                                    files_with_hits.append(rel_path)
                                matches.append({"path": rel_path, "line": line_no, "text": line.strip()[:200]})
                                if len(matches) >= max_hits:
                                    break
                except (UnicodeDecodeError, PermissionError, OSError):
                    continue

                if len(matches) >= max_hits:
                    break

            audit_logger.log_action(
                agent=self.agent_name,
                action="search",
                params={"query": query, "globs": globs},
                result=f"hits={len(matches)} files={len(files_with_hits)} scanned={scanned_files}",
                success=True,
            )

            return {
                "success": True,
                "files": files_with_hits,
                "count": len(files_with_hits),
                "matches": matches,
                "match_count": len(matches),
                "scanned_files": scanned_files,
                "hit_limit": max_hits,
                "candidates_truncated": candidates_truncated,
                "timed_out": timed_out,
            }
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
