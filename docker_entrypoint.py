#!/usr/bin/env python3
"""
Docker entrypoint для агентской системы
Запускает все необходимые сервисы
"""
import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path

class ServiceManager:
    """Менеджер сервисов для Docker контейнера"""

    def __init__(self):
        self.services = {}
        self.running = True

    def start_service(self, name: str, command: list, cwd: str = None):
        """Запуск сервиса"""
        print(f"🚀 Starting {name}...")

        try:
            process = subprocess.Popen(
                command,
                cwd=cwd or "/app",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )

            self.services[name] = {"process": process, "command": command, "start_time": time.time()}

            # Запускаем мониторинг вывода в отдельном потоке
            threading.Thread(target=self._monitor_service_output, args=(name, process), daemon=True).start()

            print(f"✅ {name} started with PID {process.pid}")
            return True

        except Exception as e:
            print(f"❌ Failed to start {name}: {e}")
            return False

    def _monitor_service_output(self, name: str, process):
        """Мониторинг вывода сервиса"""
        try:
            for line in iter(process.stdout.readline, ""):
                if line.strip():
                    print(f"[{name}] {line.strip()}")
                    # Логируем в файл
                    with open(f"/app/logs/{name}.log", "a") as f:
                        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}")
        except Exception as e:
            print(f"❌ Error monitoring {name}: {e}")
            with open(f"/app/logs/{name}_error.log", "a") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} Monitor error: {e}\n")

    def check_services(self):
        """Проверка состояния сервисов"""
        for name, service in self.services.items():
            process = service["process"]
            if process.poll() is not None:
                print(f"⚠️  Service {name} stopped with code {process.returncode}")
                # Логируем ошибку
                with open(f"/app/logs/{name}_crash.log", "a") as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} Service crashed with code {process.returncode}\n")

                # Перезапуск сервиса только если он работал больше 30 секунд
                uptime = time.time() - service["start_time"]
                if uptime > 30:
                    print(f"🔄 Service {name} ran for {uptime:.1f}s, restarting...")
                    self.restart_service(name)
                else:
                    print(f"❌ Service {name} crashed too quickly ({uptime:.1f}s), not restarting")
                    self.running = False

    def restart_service(self, name: str):
        """Перезапуск сервиса"""
        if name in self.services:
            service = self.services[name]
            print(f"🔄 Restarting {name}...")

            # Останавливаем старый процесс
            try:
                service["process"].terminate()
                service["process"].wait(timeout=10)
            except:
                service["process"].kill()

            # Запускаем новый
            self.start_service(name, service["command"])

    def stop_all_services(self):
        """Остановка всех сервисов"""
        print("🛑 Stopping all services...")
        self.running = False

        for name, service in self.services.items():
            process = service["process"]
            print(f"Stopping {name}...")

            try:
                process.terminate()
                process.wait(timeout=10)
                print(f"✅ {name} stopped gracefully")
            except subprocess.TimeoutExpired:
                print(f"⚠️  Force killing {name}...")
                process.kill()
                process.wait()
            except Exception as e:
                print(f"❌ Error stopping {name}: {e}")

def setup_environment():
    """Настройка окружения"""
    print("🔧 Setting up environment...")

    # Создаем необходимые директории
    directories = ["/app/logs", "/app/data", "/app/.agent_conversations", "/app/.agent_db_configs"]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {directory}")

    # Устанавливаем переменные окружения
    env_vars = {
        "PYTHONPATH": "/app",
        "AGENT_WORKSPACE": "/app/data",
        "CONSILIUM_MODE": os.getenv("CONSILIUM_MODE", "FAST"),
        "KB_TOP_K": os.getenv("KB_TOP_K", "3"),
        "KB_MAX_CHARS": os.getenv("KB_MAX_CHARS", "6000"),
    }

    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"🔧 Set {key}={value}")

def wait_for_postgres():
    """Ожидание доступности PostgreSQL"""
    postgres_host = os.getenv("POSTGRES_HOST")
    if not postgres_host:
        print("⚠️  No PostgreSQL configured, skipping wait")
        return

    print(f"⏳ Waiting for PostgreSQL at {postgres_host}...")

    import psycopg2

    max_attempts = 30

    for attempt in range(max_attempts):
        try:
            conn = psycopg2.connect(
                host=postgres_host,
                port=os.getenv("POSTGRES_PORT", 5432),
                database=os.getenv("POSTGRES_DB", "agent_memory"),
                user=os.getenv("POSTGRES_USER", "agent_user"),
                password=os.getenv("POSTGRES_PASSWORD", "agent_password"),
                connect_timeout=5,
            )
            conn.close()
            print("✅ PostgreSQL is ready!")
            return
        except Exception as e:
            if attempt < max_attempts - 1:
                print(f"⏳ Attempt {attempt + 1}/{max_attempts}: {e}")
                time.sleep(2)
            else:
                print(f"❌ PostgreSQL not available after {max_attempts} attempts")

def main():
    """Главная функция"""
    print("🤖 Agent System Docker Container Starting...")
    print("=" * 50)

    # Настройка окружения
    setup_environment()

    # Ожидание PostgreSQL
    wait_for_postgres()

    # Создаем менеджер сервисов
    manager = ServiceManager()

    # Обработчик сигналов для graceful shutdown
    def signal_handler(signum, frame):
        print(f"\n📡 Received signal {signum}")
        manager.stop_all_services()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Запускаем сервисы
    services_to_start = [
        {"name": "tool_server", "command": ["python", "-m", "agent_system.tool_server", "--port", "8011"], "delay": 0},
        {"name": "llm_server", "command": ["python", (os.getenv("LLM_SERVER_IMPL") or "serve_enhanced.py"), "--port", "8010"], "delay": 3},
        {
            "name": "ui_server",
            "command": ["python", "ui.py", "--server_port", "7864", "--server_name", "0.0.0.0"],
            "delay": 6,
        },
    ]

    # Запускаем сервисы с задержками
    for service_config in services_to_start:
        if service_config["delay"] > 0:
            print(f"⏳ Waiting {service_config['delay']}s before starting {service_config['name']}...")
            time.sleep(service_config["delay"])

        success = manager.start_service(service_config["name"], service_config["command"])

        if not success:
            print(f"❌ Failed to start {service_config['name']}")
            # Не выходим сразу, пробуем запустить остальные сервисы
            continue

    print("\n🎉 All services started successfully!")
    print("🌐 Agent System is ready:")
    print("   - UI: http://localhost:7864")
    print("   - LLM API: http://localhost:8010")
    print("   - Tools API: http://localhost:8011")

    # Основной цикл мониторинга
    try:
        while manager.running:
            time.sleep(10)
            manager.check_services()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        manager.stop_all_services()

if __name__ == "__main__":
    main()
