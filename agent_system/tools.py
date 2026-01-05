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
    
    def system_info(self, info_type: str = "disks") -> Dict[str, Any]:
        """Получение системной информации"""
        try:
            import platform
            import psutil
            
            if info_type == "disks":
                # Получаем информацию о дисках
                disks = []
                for partition in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        disks.append({
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype,
                            "total_gb": round(usage.total / (1024**3), 2),
                            "used_gb": round(usage.used / (1024**3), 2),
                            "free_gb": round(usage.free / (1024**3), 2),
                            "percent_used": round((usage.used / usage.total) * 100, 1)
                        })
                    except PermissionError:
                        # Некоторые диски могут быть недоступны
                        disks.append({
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype,
                            "status": "access_denied"
                        })
                
                result = {"disks": disks}
            
            elif info_type == "system":
                result = {
                    "platform": platform.system(),
                    "platform_version": platform.version(),
                    "architecture": platform.architecture()[0],
                    "processor": platform.processor(),
                    "hostname": platform.node()
                }
            
            elif info_type == "memory":
                memory = psutil.virtual_memory()
                result = {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "percent_used": memory.percent
                }
            
            elif info_type == "processes":
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                # Сортируем по использованию CPU
                processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
                result = {"processes": processes[:20]}  # Топ 20
            
            else:
                raise ValueError(f"Unknown info_type: {info_type}")
            
            audit_logger.log_action(
                agent=self.agent_name,
                action="system_info",
                params={"info_type": info_type},
                result=f"Retrieved {info_type} info",
                success=True
            )
            
            return {"success": True, **result}
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="system_info",
                params={"info_type": info_type},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
    
    def network_info(self) -> Dict[str, Any]:
        """Получение сетевой информации"""
        try:
            import psutil
            import socket
            
            # Сетевые интерфейсы
            interfaces = []
            for interface, addrs in psutil.net_if_addrs().items():
                interface_info = {"name": interface, "addresses": []}
                for addr in addrs:
                    if addr.family == socket.AF_INET:  # IPv4
                        interface_info["addresses"].append({
                            "type": "IPv4",
                            "address": addr.address,
                            "netmask": addr.netmask
                        })
                    elif addr.family == socket.AF_INET6:  # IPv6
                        interface_info["addresses"].append({
                            "type": "IPv6", 
                            "address": addr.address
                        })
                interfaces.append(interface_info)
            
            # Статистика сети
            net_stats = psutil.net_io_counters()
            stats = {
                "bytes_sent": net_stats.bytes_sent,
                "bytes_recv": net_stats.bytes_recv,
                "packets_sent": net_stats.packets_sent,
                "packets_recv": net_stats.packets_recv
            }
            
            audit_logger.log_action(
                agent=self.agent_name,
                action="network_info",
                params={},
                result=f"Retrieved network info for {len(interfaces)} interfaces",
                success=True
            )
            
            return {
                "success": True,
                "interfaces": interfaces,
                "statistics": stats
            }
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="network_info",
                params={},
                result=None,
                success=False,
                error=str(e)
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
                success=True
            )
            
            return {
                "success": True, 
                "path": str(file_path),
                "backup": str(backup_path)
            }
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="delete_file",
                params={"path": path},
                result=None,
                success=False,
                error=str(e)
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
                params={
                    "path": path, 
                    "old_length": len(old_text),
                    "new_length": len(new_text)
                },
                result=f"Replaced text, backup: {backup_path.name}",
                success=True
            )
            
            return {
                "success": True,
                "path": str(file_path),
                "backup": str(backup_path),
                "old_size": len(content),
                "new_size": len(new_content)
            }
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="edit_file",
                params={"path": path},
                result=None,
                success=False,
                error=str(e)
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
                success=True
            )
            
            return {
                "success": True,
                "source": str(source),
                "dest": str(dest),
                "size": dest.stat().st_size
            }
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="copy_file",
                params={"source": source_path, "dest": dest_path},
                result=None,
                success=False,
                error=str(e)
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
                success=True
            )
            
            return {
                "success": True,
                "source": source_path,
                "dest": str(dest)
            }
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="move_file",
                params={"source": source_path, "dest": dest_path},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
    
    def analyze_code(self, path: str) -> Dict[str, Any]:
        """Анализ кода (синтаксис, стиль, сложность)"""
        try:
            file_path = (self.workspace / path).resolve()
            
            if not SecurityConfig.is_path_safe(file_path):
                raise PermissionError(f"Path outside workspace: {path}")
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            content = file_path.read_text(encoding="utf-8")
            
            analysis = {
                "file_info": {
                    "path": str(file_path),
                    "size": len(content),
                    "lines": len(content.splitlines()),
                    "extension": file_path.suffix
                },
                "syntax_check": self._check_syntax(content, file_path.suffix),
                "style_check": self._check_style(content, file_path.suffix),
                "complexity": self._analyze_complexity(content, file_path.suffix),
                "security": self._check_security_issues(content, file_path.suffix)
            }
            
            audit_logger.log_action(
                agent=self.agent_name,
                action="analyze_code",
                params={"path": path},
                result=f"Analyzed {analysis['file_info']['lines']} lines",
                success=True
            )
            
            return {"success": True, **analysis}
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="analyze_code",
                params={"path": path},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
    
    def _check_syntax(self, content: str, extension: str) -> Dict[str, Any]:
        """Проверка синтаксиса"""
        if extension == ".py":
            try:
                import ast
                ast.parse(content)
                return {"valid": True, "errors": []}
            except SyntaxError as e:
                return {
                    "valid": False,
                    "errors": [f"Line {e.lineno}: {e.msg}"]
                }
        
        return {"valid": True, "errors": [], "note": f"Syntax check not implemented for {extension}"}
    
    def _check_style(self, content: str, extension: str) -> Dict[str, Any]:
        """Проверка стиля кода"""
        issues = []
        
        if extension == ".py":
            lines = content.splitlines()
            for i, line in enumerate(lines, 1):
                # Проверка длины строки
                if len(line) > 120:
                    issues.append(f"Line {i}: Line too long ({len(line)} > 120)")
                
                # Проверка trailing whitespace
                if line.endswith(' ') or line.endswith('\t'):
                    issues.append(f"Line {i}: Trailing whitespace")
                
                # Проверка импортов
                if line.strip().startswith('import ') and ',' in line:
                    issues.append(f"Line {i}: Multiple imports on one line")
        
        return {
            "issues_count": len(issues),
            "issues": issues[:10]  # Первые 10 проблем
        }
    
    def _analyze_complexity(self, content: str, extension: str) -> Dict[str, Any]:
        """Анализ сложности кода"""
        if extension == ".py":
            lines = content.splitlines()
            
            # Подсчет функций и классов
            functions = len([line for line in lines if line.strip().startswith('def ')])
            classes = len([line for line in lines if line.strip().startswith('class ')])
            
            # Подсчет уровня вложенности
            max_indent = 0
            for line in lines:
                if line.strip():
                    indent = len(line) - len(line.lstrip())
                    max_indent = max(max_indent, indent // 4)
            
            return {
                "functions": functions,
                "classes": classes,
                "max_nesting_level": max_indent,
                "complexity_score": functions + classes + max_indent
            }
        
        return {"note": f"Complexity analysis not implemented for {extension}"}
    
    def _check_security_issues(self, content: str, extension: str) -> Dict[str, Any]:
        """Проверка проблем безопасности"""
        issues = []
        
        # Общие проблемы безопасности
        security_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
            (r'eval\s*\(', "Use of eval() function"),
            (r'exec\s*\(', "Use of exec() function"),
        ]
        
        if extension == ".py":
            security_patterns.extend([
                (r'subprocess\.call\([^)]*shell=True', "Shell injection risk"),
                (r'os\.system\(', "OS command injection risk"),
            ])
        
        import re
        for pattern, description in security_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                issues.append(f"Line {line_num}: {description}")
        
        return {
            "issues_count": len(issues),
            "issues": issues
        }
    
    def run_tests(self, test_path: str = "tests/") -> Dict[str, Any]:
        """Запуск тестов"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_RUN_TESTS:
                raise PermissionError("Test execution denied at current level")
            
            import subprocess
            
            # Определяем команду для запуска тестов
            test_commands = [
                ["python", "-m", "pytest", test_path, "-v"],
                ["python", "-m", "unittest", "discover", "-s", test_path],
                ["python", "-m", "pytest", ".", "-v"]
            ]
            
            for cmd in test_commands:
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=self.workspace,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    output = result.stdout + result.stderr
                    
                    audit_logger.log_action(
                        agent=self.agent_name,
                        action="run_tests",
                        params={"command": " ".join(cmd)},
                        result=f"Exit code: {result.returncode}",
                        success=result.returncode == 0
                    )
                    
                    return {
                        "success": True,
                        "command": " ".join(cmd),
                        "exit_code": result.returncode,
                        "output": output,
                        "tests_passed": result.returncode == 0
                    }
                
                except subprocess.TimeoutExpired:
                    continue
                except FileNotFoundError:
                    continue
            
            return {"success": False, "error": "No test runner found (pytest, unittest)"}
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="run_tests",
                params={"test_path": test_path},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
    
    def create_project_structure(self, project_type: str = "python") -> Dict[str, Any]:
        """Создание структуры проекта"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_SAFE_WRITE:
                raise PermissionError("Project creation denied at current level")
            
            structures = {
                "python": {
                    "src/": {},
                    "tests/": {},
                    "docs/": {},
                    "README.md": "# Project Title\n\nDescription of the project.\n",
                    "requirements.txt": "# Add your dependencies here\n",
                    ".gitignore": "__pycache__/\n*.pyc\n.env\nvenv/\n.venv/\n",
                    "main.py": "#!/usr/bin/env python3\n\ndef main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()\n"
                },
                "web": {
                    "src/": {},
                    "public/": {},
                    "tests/": {},
                    "README.md": "# Web Project\n\nDescription of the web project.\n",
                    "package.json": '{\n  "name": "web-project",\n  "version": "1.0.0",\n  "description": ""\n}\n',
                    "index.html": "<!DOCTYPE html>\n<html>\n<head>\n    <title>Web Project</title>\n</head>\n<body>\n    <h1>Hello, World!</h1>\n</body>\n</html>\n"
                }
            }
            
            if project_type not in structures:
                return {"success": False, "error": f"Unknown project type: {project_type}"}
            
            structure = structures[project_type]
            created_items = []
            
            for path, content in structure.items():
                full_path = self.workspace / path
                
                if path.endswith("/"):  # Директория
                    full_path.mkdir(parents=True, exist_ok=True)
                    created_items.append(f"📁 {path}")
                else:  # Файл
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    if not full_path.exists():  # Не перезаписываем существующие файлы
                        full_path.write_text(content, encoding="utf-8")
                        created_items.append(f"📄 {path}")
            
            audit_logger.log_action(
                agent=self.agent_name,
                action="create_project_structure",
                params={"project_type": project_type},
                result=f"Created {len(created_items)} items",
                success=True
            )
            
            return {
                "success": True,
                "project_type": project_type,
                "created_items": created_items
            }
        
        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="create_project_structure",
                params={"project_type": project_type},
                result=None,
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}
