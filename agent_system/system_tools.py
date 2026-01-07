"""
System operations tools с безопасностью
"""
import subprocess
from typing import Any, Dict

from .audit import audit_logger
from .config import AgentConfig, SecurityConfig

class SystemTools:
    """Инструменты для системных операций"""

    def __init__(self, agent_name: str = "system"):
        self.agent_name = agent_name
        self.workspace = SecurityConfig.WORKSPACE_ROOT

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
                timeout=SecurityConfig.SHELL_TIMEOUT,
            )

            output = result.stdout + result.stderr

            audit_logger.log_action(
                agent=self.agent_name,
                action="git",
                params={"cmd": cmd},
                result=output[:500],
                success=result.returncode == 0,
            )

            return {"success": result.returncode == 0, "output": output, "returncode": result.returncode}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name, action="git", params={"cmd": cmd}, result=None, success=False, error=str(e)
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
                timeout=SecurityConfig.SHELL_TIMEOUT,
            )

            output = result.stdout + result.stderr

            audit_logger.log_action(
                agent=self.agent_name,
                action="shell",
                params={"command": command},
                result=output[:500],
                success=result.returncode == 0,
            )

            return {"success": result.returncode == 0, "output": output, "returncode": result.returncode}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="shell",
                params={"command": command},
                result=None,
                success=False,
                error=str(e),
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
                        disks.append(
                            {
                                "device": partition.device,
                                "mountpoint": partition.mountpoint,
                                "fstype": partition.fstype,
                                "total_gb": round(usage.total / (1024**3), 2),
                                "used_gb": round(usage.used / (1024**3), 2),
                                "free_gb": round(usage.free / (1024**3), 2),
                                "percent_used": round((usage.used / usage.total) * 100, 1),
                            }
                        )
                    except PermissionError:
                        # Некоторые диски могут быть недоступны
                        disks.append(
                            {
                                "device": partition.device,
                                "mountpoint": partition.mountpoint,
                                "fstype": partition.fstype,
                                "status": "access_denied",
                            }
                        )

                result = {"disks": disks}

            elif info_type == "system":
                result = {
                    "platform": platform.system(),
                    "platform_version": platform.version(),
                    "architecture": platform.architecture()[0],
                    "processor": platform.processor(),
                    "hostname": platform.node(),
                }

            elif info_type == "memory":
                memory = psutil.virtual_memory()
                result = {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "percent_used": memory.percent,
                }

            elif info_type == "processes":
                processes = []
                for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                # Сортируем по использованию CPU
                processes.sort(key=lambda x: x.get("cpu_percent", 0), reverse=True)
                result = {"processes": processes[:20]}  # Топ 20

            else:
                raise ValueError(f"Unknown info_type: {info_type}")

            audit_logger.log_action(
                agent=self.agent_name,
                action="system_info",
                params={"info_type": info_type},
                result=f"Retrieved {info_type} info",
                success=True,
            )

            return {"success": True, **result}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="system_info",
                params={"info_type": info_type},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    def network_info(self) -> Dict[str, Any]:
        """Получение сетевой информации"""
        try:
            import socket

            # Сетевые интерфейсы
            interfaces = []
            for interface, addrs in psutil.net_if_addrs().items():
                interface_info = {"name": interface, "addresses": []}
                for addr in addrs:
                    if addr.family == socket.AF_INET:  # IPv4
                        interface_info["addresses"].append(
                            {
                                "type": "IPv4",
                                "address": addr.address,
                                "netmask": addr.netmask,
                            }
                        )
                    elif addr.family == socket.AF_INET6:  # IPv6
                        interface_info["addresses"].append({"type": "IPv6", "address": addr.address})
                interfaces.append(interface_info)

            # Статистика сети
            net_stats = psutil.net_io_counters()
            stats = {
                "bytes_sent": net_stats.bytes_sent,
                "bytes_recv": net_stats.bytes_recv,
                "packets_sent": net_stats.packets_sent,
                "packets_recv": net_stats.packets_recv,
            }

            audit_logger.log_action(
                agent=self.agent_name,
                action="network_info",
                params={},
                result=f"Retrieved network info for {len(interfaces)} interfaces",
                success=True,
            )

            return {"success": True, "interfaces": interfaces, "statistics": stats}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name, action="network_info", params={}, result=None, success=False, error=str(e)
            )
            return {"success": False, "error": str(e)}

    def run_tests(self, test_path: str = "tests/") -> Dict[str, Any]:
        """Запуск тестов"""
        try:
            # Проверка уровня доступа
            if AgentConfig.CURRENT_ACCESS_LEVEL < AgentConfig.ACCESS_LEVEL_RUN_TESTS:
                raise PermissionError("Test execution denied at current level")

            # Определяем команду для запуска тестов
            test_commands = [
                ["python", "-m", "pytest", test_path, "-v"],
                ["python", "-m", "unittest", "discover", "-s", test_path],
                ["python", "-m", "pytest", ".", "-v"],
            ]

            for cmd in test_commands:
                try:
                    result = subprocess.run(cmd, cwd=self.workspace, capture_output=True, text=True, timeout=60)

                    output = result.stdout + result.stderr

                    audit_logger.log_action(
                        agent=self.agent_name,
                        action="run_tests",
                        params={"command": " ".join(cmd)},
                        result=f"Exit code: {result.returncode}",
                        success=result.returncode == 0,
                    )

                    return {
                        "success": True,
                        "command": " ".join(cmd),
                        "exit_code": result.returncode,
                        "output": output,
                        "tests_passed": result.returncode == 0,
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
                error=str(e),
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
                    "main.py": (
                        "#!/usr/bin/env python3\n\n"
                        "def main():\n"
                        "    print('Hello, World!')\n\n"
                        "if __name__ == '__main__':\n"
                        "    main()\n"
                    ),
                },
                "web": {
                    "src/": {},
                    "public/": {},
                    "tests/": {},
                    "README.md": "# Web Project\n\nDescription of the web project.\n",
                    "package.json": (
                        '{\n'
                        '  "name": "web-project",\n'
                        '  "version": "1.0.0",\n'
                        '  "description": ""\n'
                        '}\n'
                    ),
                    "index.html": "<!DOCTYPE html>\n<html>\n<head>\n    <title>Web Project</title>\n</head>\n<body>\n    <h1>Hello, World!</h1>\n</body>\n</html>\n",
                },
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
                success=True,
            )

            return {"success": True, "project_type": project_type, "created_items": created_items}

        except Exception as e:
            audit_logger.log_action(
                agent=self.agent_name,
                action="create_project_structure",
                params={"project_type": project_type},
                result=None,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}
