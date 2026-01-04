"""
Tool implementations с безопасностью
"""
import subprocess
from pathlib import Path
from typing import Dict, Any, List
from .config import SecurityConfig, AgentConfig
from .audit import audit_logger


class ToolExecutor:
    """Безопасное выполнение инструментов"""
    
    def __init__(self, agent_name: str = "system"):
        self.agent_name = agent_name
        self.workspace = SecurityConfig.WORKSPACE_ROOT
    
    def read_file(self, path: str) -> Dict[str, Any]:
        """Чтение файла"""
        try:
            file_path = (self.workspace / path).resolve()
            
            # Проверка безопасности
            if not SecurityConfig.is_path_safe(file_path):
                raise PermissionError(f"Path outside workspace: {path}")
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            # Проверка размера
            if file_path.stat().st_size > SecurityConfig.MAX_FILE_SIZE:
                raise ValueError(f"File too large: {path}")
            
            content = file_path.read_text(encoding="utf-8")
            
            audit_logger.log_action(
                agent=self.agent_name,
                action="read_file",
                params={"path": path},
                result=f"Read {len(content)} chars",
                success=True
            )
            
            return {"success": True, "content": content, "path": str(file_path)}
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="read_file",
                params={"path": path},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
    
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
                success=True
            )
            
            return {"success": True, "path": str(file_path), "size": len(content)}
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="write_file",
                params={"path": path, "mode": mode},
                result=None,
                success=False,
                error=str(e)
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
                files.append({
                    "path": str(rel_path),
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else 0
                })
            
            audit_logger.log_action(
                agent=self.agent_name,
                action="list_dir",
                params={"path": path, "pattern": pattern},
                result=f"Found {len(files)} items",
                success=True
            )
            
            return {"success": True, "files": files}
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="list_dir",
                params={"path": path},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
    
    def search(self, query: str, globs: List[str] = None) -> Dict[str, Any]:
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
                success=True
            )
            
            return {"success": True, "files": results, "count": len(results)}
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="search",
                params={"query": query},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
    
    def git(self, cmd: str) -> Dict[str, Any]:
        """Выполнение git команд"""
        try:
            # Проверка уровня доступа
            if "commit" in cmd and AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_GIT_COMMIT:
                raise PermissionError("Git commit access denied at current level")
            
            # Проверка безопасности команды
            cmd_parts = cmd.split()
            if not cmd_parts:
                raise ValueError("Empty git command")
            
            base_cmd = cmd_parts[0]
            if base_cmd not in SecurityConfig.SAFE_GIT_COMMANDS:
                if base_cmd in SecurityConfig.DANGEROUS_GIT_COMMANDS:
                    raise PermissionError(f"Dangerous git command requires manual approval: {base_cmd}")
                raise PermissionError(f"Git command not allowed: {base_cmd}")
            
            # Выполнение
            result = subprocess.run(
                ["git"] + cmd_parts,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=SecurityConfig.SHELL_TIMEOUT
            )
            
            output = result.stdout + result.stderr
            
            audit_logger.log_action(
                agent=self.agent_name,
                action="git",
                params={"cmd": cmd},
                result=output[:500],
                success=result.returncode == 0
            )
            
            return {
                "success": result.returncode == 0,
                "output": output,
                "returncode": result.returncode
            }
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="git",
                params={"cmd": cmd},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
    
    def shell(self, command: str) -> Dict[str, Any]:
        """Выполнение shell команд (ограниченно)"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_RUN_TESTS:
                raise PermissionError("Shell access denied at current level")
            
            # Проверка безопасности
            is_safe, reason = SecurityConfig.is_command_safe(command)
            if not is_safe:
                raise PermissionError(f"Unsafe command: {reason}")
            
            # Выполнение
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=SecurityConfig.SHELL_TIMEOUT
            )
            
            output = result.stdout + result.stderr
            
            audit_logger.log_action(
                agent=self.agent_name,
                action="shell",
                params={"command": command},
                result=output[:500],
                success=result.returncode == 0
            )
            
            return {
                "success": result.returncode == 0,
                "output": output,
                "returncode": result.returncode
            }
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="shell",
                params={"command": command},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
