#!/usr/bin/env python3
"""
Docker entrypoint for the Agent System container.

Starts:
- Tool server (FastAPI) on :8011
- LLM server (OpenAI-compatible adapter/proxy) on :8010
- UI server (Gradio) on :7864
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

MOCK_LLM_IMPLS = {"serve_enhanced.py", "serve_mock.py", "serve_raw.py"}


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _llm_backend_urls() -> Tuple[str, str]:
    v1 = os.getenv("LLM_PROXY_V1") or os.getenv("AGENT_LLM_URL") or "http://llm:8000/v1"
    v1 = v1.rstrip("/")
    base = v1[:-3] if v1.endswith("/v1") else v1
    return base, v1


def wait_for_llm_backend(max_attempts: int = 60) -> None:
    """
    Ensure the configured LLM backend is reachable before bringing up the UI.

    Without this, the stack can look "alive" while silently serving mock/fallback responses.
    """
    strict = _truthy(os.getenv("LLM_STRICT_STARTUP", "true"))
    if not strict:
        print("⚠️  LLM_STRICT_STARTUP=false: skipping LLM backend preflight")
        return

    base, v1 = _llm_backend_urls()
    allow_mock = _truthy(os.getenv("ALLOW_MOCK_LLM"))
    print(f"⏳ Waiting for LLM backend: {v1}")

    try:
        import requests  # type: ignore
    except Exception as exc:  # pragma: no cover
        print(f"❌ Cannot import requests for LLM preflight: {exc}")
        sys.exit(1)

    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            # Some backends (e.g., Ollama) may not expose /health. Treat it as best-effort.
            try:
                health = requests.get(f"{base}/health", timeout=3)
                if health.status_code not in {200, 404}:
                    raise RuntimeError(f"health HTTP {health.status_code}: {health.text[:200]}")
            except Exception:
                pass

            model_ids = []
            try:
                models = requests.get(f"{v1}/models", timeout=5)
                if not models.ok:
                    raise RuntimeError(f"models HTTP {models.status_code}: {models.text[:200]}")
                payload = models.json()
                model_ids = [m.get("id") for m in payload.get("data", []) if isinstance(m, dict)]
                model_ids = [m for m in model_ids if isinstance(m, str)]
            except Exception:
                # Fallback for Ollama native API
                tags = requests.get(f"{base}/api/tags", timeout=5)
                if not tags.ok:
                    raise RuntimeError(f"LLM backend unreachable (no /v1/models, no /api/tags): {tags.text[:200]}")
                payload = tags.json()
                model_ids = [m.get("name") for m in payload.get("models", []) if isinstance(m, dict)]
                model_ids = [m for m in model_ids if isinstance(m, str)]

            if ({"enhanced-model", "mock-model", "raw-llm"} & set(model_ids)) and not allow_mock:
                raise RuntimeError(f"mock backend detected via /v1/models: {model_ids}")

            print(f"✅ LLM backend ready (models={model_ids[:3]})")
            return
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                time.sleep(2)
                continue
            break

    print(f"❌ LLM backend not ready after {max_attempts} attempts: {last_error}")
    sys.exit(1)


class ServiceManager:
    """Start/monitor multiple services inside the container."""

    def __init__(self):
        self.services = {}
        self.running = True

    def start_service(self, name: str, command: list, cwd: str = None):
        print(f"Starting {name}...")
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
            threading.Thread(target=self._monitor_service_output, args=(name, process), daemon=True).start()

            print(f"{name} started with PID {process.pid}")
            return True
        except Exception as e:
            print(f"Failed to start {name}: {e}")
            return False

    def _monitor_service_output(self, name: str, process):
        try:
            for line in iter(process.stdout.readline, ""):
                if line.strip():
                    print(f"[{name}] {line.strip()}")
                    with open(f"/app/logs/{name}.log", "a", encoding="utf-8") as f:
                        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}")
        except Exception as e:
            print(f"Error monitoring {name}: {e}")
            with open(f"/app/logs/{name}_error.log", "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} Monitor error: {e}\n")

    def check_services(self):
        for name, service in self.services.items():
            process = service["process"]
            if process.poll() is not None:
                print(f"Service {name} stopped with code {process.returncode}")
                with open(f"/app/logs/{name}_crash.log", "a", encoding="utf-8") as f:
                    f.write(
                        f"{time.strftime('%Y-%m-%d %H:%M:%S')} Service crashed with code {process.returncode}\n"
                    )

                uptime = time.time() - service["start_time"]
                if uptime > 30:
                    print(f"Service {name} ran for {uptime:.1f}s, restarting...")
                    self.restart_service(name)
                else:
                    print(f"Service {name} crashed too quickly ({uptime:.1f}s), not restarting")
                    self.running = False

    def restart_service(self, name: str):
        if name not in self.services:
            return
        service = self.services[name]
        print(f"Restarting {name}...")
        try:
            service["process"].terminate()
            service["process"].wait(timeout=10)
        except Exception:
            service["process"].kill()
        self.start_service(name, service["command"])

    def stop_all_services(self):
        print("Stopping all services...")
        self.running = False
        for name, service in self.services.items():
            process = service["process"]
            print(f"Stopping {name}...")
            try:
                process.terminate()
                process.wait(timeout=10)
            except Exception:
                process.kill()


def setup_environment():
    directories = ["/app/logs", "/app/data", "/app/.agent_conversations", "/app/.agent_db_configs"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

    env_vars = {
        "PYTHONPATH": "/app",
        "AGENT_WORKSPACE": "/app/data",
        "CONSILIUM_MODE": os.getenv("CONSILIUM_MODE", "FAST"),
        "KB_TOP_K": os.getenv("KB_TOP_K", "3"),
        "KB_MAX_CHARS": os.getenv("KB_MAX_CHARS", "6000"),
    }
    for key, value in env_vars.items():
        os.environ.setdefault(key, value)


def wait_for_postgres():
    postgres_host = os.getenv("POSTGRES_HOST")
    if not postgres_host:
        print("No PostgreSQL configured, skipping wait")
        return

    print(f"Waiting for PostgreSQL at {postgres_host}...")

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
            print("PostgreSQL is ready!")
            return
        except Exception as e:
            if attempt < max_attempts - 1:
                print(f"Attempt {attempt + 1}/{max_attempts}: {e}")
                time.sleep(2)
            else:
                print(f"PostgreSQL not available after {max_attempts} attempts")


def main():
    print("Agent System Docker Container Starting...")
    print("=" * 50)

    setup_environment()
    wait_for_postgres()

    # Fail fast if the configured backend is unreachable (or is a mock unless explicitly allowed).
    wait_for_llm_backend()

    manager = ServiceManager()

    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}")
        manager.stop_all_services()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    llm_backend = os.getenv("LLM_BACKEND", "llama_cpp")
    llm_impl = os.getenv("LLM_SERVER_IMPL") or "serve_proxy.py"
    if llm_backend == "peft":
        llm_impl = "serve_lora.py"
    if llm_impl in MOCK_LLM_IMPLS and not _truthy(os.getenv("ALLOW_MOCK_LLM")):
        print(f"❌ Refusing to start with mock LLM server ({llm_impl}). Set ALLOW_MOCK_LLM=true to override.")
        sys.exit(1)

    services_to_start = [
        {"name": "tool_server", "command": ["python", "-m", "agent_system.tool_server", "--port", "8011"], "delay": 0},
        {"name": "llm_server", "command": ["python", llm_impl, "--port", "8010"], "delay": 3},
        {
            "name": "ui_server",
            "command": ["python", "ui.py", "--server_port", "7864", "--server_name", "0.0.0.0"],
            "delay": 6,
        },
    ]

    for service_config in services_to_start:
        if service_config["delay"] > 0:
            time.sleep(service_config["delay"])

        success = manager.start_service(service_config["name"], service_config["command"])
        if not success:
            print(f"Failed to start {service_config['name']}")
            continue

    print("\nAll services started.")
    print("Agent System is ready:")
    print("  - UI: http://localhost:7864")
    print("  - LLM API: http://localhost:8010")
    print("  - Tools API: http://localhost:8011")

    try:
        while manager.running:
            time.sleep(10)
            manager.check_services()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        manager.stop_all_services()


if __name__ == "__main__":
    main()
