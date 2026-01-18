"""
Базовый агент с доступом к LLM и tools
"""
import ast
import json
import os
import re
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import requests

TOOL_SPECS = {
    "read_file": {"endpoint": "/tools/read_file", "confirm": False},
    "write_file": {"endpoint": "/tools/write_file", "confirm": True},
    "edit_file": {"endpoint": "/tools/edit_file", "confirm": True},
    "delete_file": {"endpoint": "/tools/delete_file", "confirm": True},
    "copy_file": {"endpoint": "/tools/copy_file", "confirm": True},
    "move_file": {"endpoint": "/tools/move_file", "confirm": True},
    "list_dir": {"endpoint": "/tools/list_dir", "confirm": False},
    "search": {"endpoint": "/tools/search", "confirm": False},
    "git": {"endpoint": "/tools/git", "confirm": False},
    "shell": {"endpoint": "/tools/shell", "confirm": True},
    "system_info": {"endpoint": "/tools/system_info", "confirm": False},
    "network_info": {"endpoint": "/tools/network_info", "confirm": False},
    "db_add_connection": {"endpoint": "/tools/db_add_connection", "confirm": True},
    "db_execute_query": {"endpoint": "/tools/db_execute_query", "confirm": True},
    "db_get_schema": {"endpoint": "/tools/db_get_schema", "confirm": False},
    "memory_init": {"endpoint": "/tools/memory_init", "confirm": True},
    "memory_search": {"endpoint": "/tools/memory_search", "confirm": False},
}

READ_ONLY_SQL_PREFIXES = ("select", "show", "describe", "explain", "with")

class CircuitBreakerError(Exception):
    """Исключение когда Circuit Breaker открыт"""

    pass

class CircuitBreaker:
    """
    Circuit Breaker pattern для защиты от cascade failures.

    Состояния:
    - CLOSED: нормальная работа, запросы проходят
    - OPEN: сервис недоступен, запросы блокируются
    - HALF_OPEN: пробный режим, один запрос для проверки

    Параметры:
    - failure_threshold: количество ошибок для перехода в OPEN
    - recovery_timeout: время в секундах до перехода в HALF_OPEN
    - success_threshold: количество успехов в HALF_OPEN для перехода в CLOSED
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60, success_threshold: int = 1):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = "CLOSED"
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None

        # Метрики
        self.total_calls = 0
        self.total_failures = 0
        self.total_blocked = 0
        self.state_changes: List[Dict[str, Any]] = []

    def _record_state_change(self, old_state: str, new_state: str, reason: str):
        """Записать изменение состояния"""
        self.state_changes.append({"timestamp": time.time(), "from": old_state, "to": new_state, "reason": reason})
        # Храним только последние 10 изменений
        if len(self.state_changes) > 10:
            self.state_changes.pop(0)

    def can_execute(self) -> bool:
        """Проверить можно ли выполнить запрос"""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # Проверяем прошло ли время recovery
            if self.last_failure_time and time.time() - self.last_failure_time >= self.recovery_timeout:
                old_state = self.state
                self.state = "HALF_OPEN"
                self.success_count = 0
                self._record_state_change(old_state, "HALF_OPEN", "Recovery timeout elapsed")
                return True
            return False

        if self.state == "HALF_OPEN":
            return True

        return False

    def record_success(self):
        """Записать успешный вызов"""
        self.total_calls += 1

        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                old_state = self.state
                self.state = "CLOSED"
                self.failure_count = 0
                self._record_state_change(old_state, "CLOSED", f"{self.success_count} successful calls")
        elif self.state == "CLOSED":
            # Сбрасываем счётчик ошибок при успехе
            self.failure_count = 0

    def record_failure(self, error: Exception = None):
        """Записать неудачный вызов"""
        self.total_calls += 1
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == "HALF_OPEN":
            # Одна ошибка в HALF_OPEN → сразу OPEN
            old_state = self.state
            self.state = "OPEN"
            self._record_state_change(old_state, "OPEN", f"Failure in HALF_OPEN: {error}")
        elif self.state == "CLOSED":
            if self.failure_count >= self.failure_threshold:
                old_state = self.state
                self.state = "OPEN"
                self._record_state_change(
                    old_state, "OPEN", f"Failure threshold reached ({self.failure_count}/{self.failure_threshold})"
                )

    def get_status(self) -> Dict[str, Any]:
        """Получить статус Circuit Breaker"""
        time_until_retry = None
        if self.state == "OPEN" and self.last_failure_time:
            elapsed = time.time() - self.last_failure_time
            time_until_retry = max(0, self.recovery_timeout - elapsed)

        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_blocked": self.total_blocked,
            "time_until_retry": round(time_until_retry, 1) if time_until_retry else None,
            "config": {
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "success_threshold": self.success_threshold,
            },
            "recent_state_changes": self.state_changes[-3:],  # последние 3
        }

# Глобальный Circuit Breaker для LLM (shared между всеми агентами)
_llm_circuit_breaker: Optional[CircuitBreaker] = None

def get_llm_circuit_breaker() -> CircuitBreaker:
    """Получить singleton Circuit Breaker для LLM"""
    global _llm_circuit_breaker
    if _llm_circuit_breaker is None:
        _llm_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60, success_threshold=1)
    return _llm_circuit_breaker

class Agent:
    """Базовый агент для работы с LLM и tools"""

    # Размер окна для скользящего среднего
    TIMING_WINDOW = 20
    PREVIEW_TOOLS = {"write_file", "edit_file", "delete_file", "copy_file", "move_file"}

    def __init__(self, name: str = "Agent", role: str = "Generic Agent", 
                 llm_url: str = None, 
                 tool_url: str = None):
        """Инициализация агента
        
        Hybrid Architecture:
        - Agents use AGENT_LLM_URL (local Qwen via ngrok)
        - Director uses DIRECTOR_LLM_URL (GPT-5.2 via OpenAI)
        """
        import os
        self.name = name
        self.role = role
        # Use env var or fallback to default
        self.llm_url = llm_url or os.getenv("AGENT_LLM_URL", "http://localhost:8010/v1")
        self.tool_url = tool_url or os.getenv("TOOL_SERVER_URL", "http://localhost:8011")
        self.model = os.getenv("AGENT_LLM_MODEL", "qwen2.5-coder-lora")
        self.llm_api_key = os.getenv("AGENT_LLM_API_KEY") or os.getenv("AGENT_API_KEY")
        self.tool_api_key = os.getenv("AGENT_API_KEY")
        self.is_director = "director" in self.name.lower()

        if self.is_director and os.getenv("DIRECTOR_AGENT_USE_LLM", "false").lower() == "true":
            self.llm_url = os.getenv("DIRECTOR_LLM_URL", self.llm_url)
            self.model = os.getenv("DIRECTOR_MODEL", self.model)
            self.llm_api_key = os.getenv("OPENAI_API_KEY", self.llm_api_key)
        
        # Метрики LLM
        self._llm_times = deque(maxlen=self.TIMING_WINDOW)
        self._llm_call_count = 0
        self._retry_count = 0
        self._max_retries = 3
        self._retry_base_delay = 1.0
        self._retry_max_delay = 10.0
        
        # Метрики retrieval
        self._retrieval_times = deque(maxlen=self.TIMING_WINDOW)
        self._retrieval_call_count = 0
        
        # Repo snapshot cache
        self.repo_snapshot = None
        self.conversation_history = []

    def _call_llm_once(self, messages: List[Dict[str, str]], max_tokens: int = 512) -> str:
        """Один вызов LLM без retry (внутренний метод)"""
        # Add ngrok header to bypass browser warning for free tier
        headers = {}
        if "ngrok" in self.llm_url:
            headers["ngrok-skip-browser-warning"] = "true"
        if self.llm_api_key:
            headers["Authorization"] = f"Bearer {self.llm_api_key}"
        response = requests.post(
            f"{self.llm_url}/chat/completions",
            json={"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
            headers=headers,
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _call_llm(self, messages: List[Dict[str, str]], max_tokens: int = 512) -> str:
        """
        Internal LLM call with:
        - Circuit Breaker protection
        - Exponential backoff retry for transient errors
        - Timing metrics
        """
        circuit_breaker = get_llm_circuit_breaker()

        # Проверяем Circuit Breaker
        if not circuit_breaker.can_execute():
            circuit_breaker.total_blocked += 1
            status = circuit_breaker.get_status()
            return (
                f"[CIRCUIT_BREAKER_OPEN] LLM service unavailable. "
                f"State: {status['state']}, retry in {status['time_until_retry']}s"
            )

        start = time.perf_counter()
        last_error = None

        for attempt in range(self._max_retries):
            try:
                result = self._call_llm_once(messages, max_tokens)

                # Track timing
                elapsed_ms = (time.perf_counter() - start) * 1000
                self._llm_times.append(elapsed_ms)
                self._llm_call_count += 1

                # Успех - записываем в Circuit Breaker
                circuit_breaker.record_success()

                # Логируем если был retry
                if attempt > 0:
                    print(f"[RETRY] LLM call succeeded after {attempt} retries")

                return result

            except requests.exceptions.Timeout as e:
                # Timeout - можно retry
                last_error = e
                self._retry_count += 1

                if attempt < self._max_retries - 1:
                    delay = min(self._retry_base_delay * (2**attempt), self._retry_max_delay)
                    print(f"[RETRY] LLM timeout, attempt {attempt + 1}/{self._max_retries}, waiting {delay}s...")
                    time.sleep(delay)
                else:
                    # Последняя попытка - записываем failure в CB
                    circuit_breaker.record_failure(e)
                    return f"[LLM_TIMEOUT] {e} (after {self._max_retries} attempts)"

            except requests.exceptions.ConnectionError as e:
                # Connection error - НЕ retry (сервер недоступен)
                circuit_breaker.record_failure(e)
                return f"[LLM_CONNECTION_ERROR] {e}"

            except requests.exceptions.HTTPError as e:
                # HTTP error - retry только для 5xx
                if hasattr(e, "response") and e.response is not None:
                    status_code = e.response.status_code
                    if 500 <= status_code < 600:
                        # Server error - можно retry
                        last_error = e
                        self._retry_count += 1

                        if attempt < self._max_retries - 1:
                            delay = min(self._retry_base_delay * (2**attempt), self._retry_max_delay)
                            print(
                                f"[RETRY] LLM HTTP {status_code}, attempt {attempt + 1}/{self._max_retries}, "
                                f"waiting {delay}s..."
                            )
                            time.sleep(delay)
                        else:
                            circuit_breaker.record_failure(e)
                            return f"[LLM_HTTP_ERROR] {e} (after {self._max_retries} attempts)"
                    else:
                        # Client error (4xx) - не retry
                        circuit_breaker.record_failure(e)
                        return f"[LLM_HTTP_ERROR] {e}"
                else:
                    circuit_breaker.record_failure(e)
                    return f"[LLM_HTTP_ERROR] {e}"

            except Exception as e:
                # Другие ошибки - не retry
                circuit_breaker.record_failure(e)
                return f"[LLM_ERROR] {e}"

        # Не должны сюда попасть, но на всякий случай
        circuit_breaker.record_failure(last_error)
        return f"[LLM_ERROR] Max retries exceeded: {last_error}"

    def call_llm(self, messages: List[Dict[str, str]], max_tokens: int = 512) -> str:
        """Вызов LLM (публичный метод для обратной совместимости)"""
        return self._call_llm(messages, max_tokens)

    def check_llm_health(self, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Проверить доступность LLM сервера.

        Returns:
            {
                "healthy": bool,
                "status": str,
                "response_time_ms": float (если healthy),
                "error": str (если не healthy)
            }
        """
        start = time.perf_counter()
        headers = {}
        if "ngrok" in self.llm_url:
            headers["ngrok-skip-browser-warning"] = "true"
        if self.llm_api_key:
            headers["Authorization"] = f"Bearer {self.llm_api_key}"
        try:
            # Пробуем /health endpoint
            response = requests.get(f"{self.llm_url.rstrip('/v1')}/health", headers=headers, timeout=timeout)
            elapsed_ms = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                return {
                    "healthy": True,
                    "status": data.get("status", "ok"),
                    "response_time_ms": round(elapsed_ms, 1),
                    "model_loaded": data.get("model_loaded", True),
                }
            else:
                return {"healthy": False, "status": f"HTTP {response.status_code}", "error": response.text[:200]}
        except requests.exceptions.ConnectionError as e:
            return {"healthy": False, "status": "connection_error", "error": str(e)[:200]}
        except requests.exceptions.Timeout:
            return {"healthy": False, "status": "timeout", "error": f"Health check timed out after {timeout}s"}
        except Exception as e:
            return {"healthy": False, "status": "error", "error": str(e)[:200]}

    def _tool_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.tool_api_key:
            headers["Authorization"] = f"Bearer {self.tool_api_key}"
        return headers

    def _ensure_repo_snapshot(self) -> None:
        if self.repo_snapshot is not None:
            return

        retrieval_start = time.perf_counter()
        try:
            r = requests.post(
                f"{self.tool_url}/tools/list_dir",
                json={"path": "."},
                headers=self._tool_headers(),
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            items = data.get("items")
            if items is None and "files" in data:
                items = [
                    {"name": f["name"], "type": "dir" if f.get("is_dir") else "file"}
                    for f in data["files"]
                ]
            if items is None:
                items = []
            lines = []
            for it in items:
                prefix = "[DIR]" if it["type"] == "dir" else "[FILE]"
                lines.append(f"{prefix} {it['name']}")
            self.repo_snapshot = "\n".join(lines)
        except Exception as e:
            self.repo_snapshot = f"[ERROR loading repo snapshot: {e}]"
        finally:
            elapsed_ms = (time.perf_counter() - retrieval_start) * 1000
            self._retrieval_times.append(elapsed_ms)
            self._retrieval_call_count += 1

    def _build_tool_system_prompt(self) -> str:
        tool_lines = []
        for name, spec in TOOL_SPECS.items():
            hint = {
                "read_file": '{"path": "..."}',
                "write_file": '{"path": "...", "content": "...", "mode": "overwrite|append"}',
                "edit_file": '{"path": "...", "old_text": "...", "new_text": "..."}',
                "delete_file": '{"path": "..."}',
                "copy_file": '{"source_path": "...", "dest_path": "..."}',
                "move_file": '{"source_path": "...", "dest_path": "..."}',
                "list_dir": '{"path": ".", "pattern": "*"}',
                "search": '{"query": "...", "globs": ["**/*.py"]}',
                "git": '{"cmd": "status"}',
                "shell": '{"command": "..."}',
                "system_info": '{"info_type": "disks|memory|system|processes"}',
                "network_info": "{}",
                "db_add_connection": '{"name": "...", "host": "...", "database": "...", "user": "...", "password": "...", "port": 5432}',
                "db_execute_query": '{"connection_name": "...", "query": "...", "params": []}',
                "db_get_schema": '{"connection_name": "...", "table_name": "..."}',
                "memory_init": '{"connection_name": "..."}',
                "memory_search": '{"session_id": "...", "query": "...", "limit": 20}',
            }.get(name, "{}")
            confirm_tag = " (confirm)" if spec.get("confirm") else ""
            tool_lines.append(f"- {name}{confirm_tag}: {hint}")

        return (
            "You are a coding agent with access to tools.\n"
            "When a tool is needed, respond ONLY with TOOL_CALLS JSON.\n"
            "Format:\n"
            "TOOL_CALLS: [{\"tool\": \"name\", \"args\": {...}}]\n"
            "Do not include any other text when issuing tool calls.\n\n"
            "Available tools:\n" + "\n".join(tool_lines)
        )

    def _build_tool_messages(
        self,
        task: str,
        required_tools: Optional[List[str]] = None,
        force_tools: bool = False,
    ) -> List[Dict[str, str]]:
        self._ensure_repo_snapshot()
        messages = [
            {"role": "system", "content": self._build_tool_system_prompt()},
            {"role": "system", "content": "Repository snapshot:\n" + (self.repo_snapshot or "")},
        ]
        if required_tools:
            requirement = "This task requires tool usage before answering."
            if force_tools:
                requirement = "You MUST call the required tools before answering."
            requirement += f" Required tool(s): {', '.join(required_tools)}."
            if "search" in required_tools and "read_file" in required_tools:
                requirement += " Use search first, then read_file for the located path."
            elif "search" in required_tools:
                requirement += " If unsure, start with search."
            messages.append({"role": "system", "content": requirement})
        messages.append({"role": "user", "content": task})
        return messages

    def _required_tools_for_task(self, task: str) -> List[str]:
        lower = task.lower()
        required: List[str] = []

        if re.search(r"\b(search|find|locate|grep|поиск|найти|найди|искать)\b", lower):
            required.append("search")

        file_hint = re.search(
            r"\b(docker-compose|nginx|config|конфиг|настройк|yaml|yml|json|toml|ini|env|\.conf)\b",
            lower,
        )
        file_path_match = re.search(
            r"\b[\w./-]+\.(py|js|ts|md|yml|yaml|json|toml|ini|conf|env|sh|ps1)\b",
            task,
        )
        has_explicit_path = False
        if file_path_match:
            token = file_path_match.group(0)
            has_explicit_path = "/" in token or "\\" in token

        if file_hint or file_path_match:
            if not has_explicit_path:
                required.append("search")
            required.append("read_file")

        if not required and re.search(r"\b(list|dir|directory|folders|список\w*|папк\w*|каталог\w*|директори\w*)\b", lower):
            required.append("list_dir")

        return list(dict.fromkeys(required))

    def _missing_required_tools(self, calls: List[Dict[str, Any]], required: List[str]) -> List[str]:
        used = {call.get("tool") for call in calls if isinstance(call.get("tool"), str)}
        return [tool for tool in required if tool not in used]

    def _normalize_path(self, path: str) -> str:
        value = path.strip().replace("\\", "/")
        return os.path.normpath(value)

    def _validate_path_value(self, path: Any, allow_dot: bool) -> Tuple[bool, str, str]:
        if not isinstance(path, str):
            return False, "", "path must be a string"
        raw = path.strip()
        if not raw:
            return False, "", "path is empty"

        normalized = self._normalize_path(raw)
        if normalized in {"/"}:
            return False, normalized, "absolute root is not allowed"
        if not allow_dot and normalized in {".", ""}:
            return False, normalized, "path cannot be the workspace root"
        if normalized.startswith(".."):
            return False, normalized, "path traversal is not allowed"
        if re.match(r"^[A-Za-z]:", normalized):
            return False, normalized, "absolute Windows path is not allowed"

        return True, normalized, ""

    def _validate_tool_args(self, tool: str, args: Any) -> Tuple[bool, Dict[str, Any], str]:
        if tool not in TOOL_SPECS:
            return False, {}, "unknown tool"
        if not isinstance(args, dict):
            return False, {}, "args must be an object"

        cleaned: Dict[str, Any] = dict(args)

        if tool == "read_file":
            ok, norm, err = self._validate_path_value(cleaned.get("path"), allow_dot=False)
            return ok, {"path": norm} if ok else {}, err

        if tool == "list_dir":
            path_value = cleaned.get("path", ".")
            ok, norm, err = self._validate_path_value(path_value, allow_dot=True)
            if not ok:
                return False, {}, err
            pattern = cleaned.get("pattern", "*")
            if not isinstance(pattern, str) or not pattern.strip():
                return False, {}, "pattern must be a non-empty string"
            return True, {"path": norm, "pattern": pattern}, ""

        if tool == "search":
            query = cleaned.get("query")
            if not isinstance(query, str) or not query.strip():
                return False, {}, "query must be a non-empty string"
            globs = cleaned.get("globs")
            if globs is None:
                return True, {"query": query}, ""
            if isinstance(globs, list) and all(isinstance(g, str) for g in globs):
                return True, {"query": query, "globs": globs}, ""
            return False, {}, "globs must be a list of strings"

        if tool == "write_file":
            ok, norm, err = self._validate_path_value(cleaned.get("path"), allow_dot=False)
            if not ok:
                return False, {}, err
            content = cleaned.get("content")
            if not isinstance(content, str):
                return False, {}, "content must be a string"
            mode = cleaned.get("mode", "overwrite")
            if mode not in {"overwrite", "append"}:
                return False, {}, "mode must be overwrite or append"
            expected_sha256 = cleaned.get("expected_sha256")
            if expected_sha256 is not None and not isinstance(expected_sha256, str):
                return False, {}, "expected_sha256 must be a string"
            expected_exists = cleaned.get("expected_exists")
            if expected_exists is not None and not isinstance(expected_exists, bool):
                return False, {}, "expected_exists must be a boolean"
            payload = {"path": norm, "content": content, "mode": mode}
            if expected_sha256 is not None:
                payload["expected_sha256"] = expected_sha256
            if expected_exists is not None:
                payload["expected_exists"] = expected_exists
            return True, payload, ""

        if tool == "edit_file":
            ok, norm, err = self._validate_path_value(cleaned.get("path"), allow_dot=False)
            if not ok:
                return False, {}, err
            old_text = cleaned.get("old_text")
            new_text = cleaned.get("new_text")
            if not isinstance(old_text, str) or not isinstance(new_text, str):
                return False, {}, "old_text and new_text must be strings"
            expected_sha256 = cleaned.get("expected_sha256")
            if expected_sha256 is not None and not isinstance(expected_sha256, str):
                return False, {}, "expected_sha256 must be a string"
            expected_exists = cleaned.get("expected_exists")
            if expected_exists is not None and not isinstance(expected_exists, bool):
                return False, {}, "expected_exists must be a boolean"
            payload = {"path": norm, "old_text": old_text, "new_text": new_text}
            if expected_sha256 is not None:
                payload["expected_sha256"] = expected_sha256
            if expected_exists is not None:
                payload["expected_exists"] = expected_exists
            return True, payload, ""

        if tool == "delete_file":
            ok, norm, err = self._validate_path_value(cleaned.get("path"), allow_dot=False)
            if not ok:
                return False, {}, err
            expected_sha256 = cleaned.get("expected_sha256")
            if expected_sha256 is not None and not isinstance(expected_sha256, str):
                return False, {}, "expected_sha256 must be a string"
            expected_exists = cleaned.get("expected_exists")
            if expected_exists is not None and not isinstance(expected_exists, bool):
                return False, {}, "expected_exists must be a boolean"
            payload = {"path": norm}
            if expected_sha256 is not None:
                payload["expected_sha256"] = expected_sha256
            if expected_exists is not None:
                payload["expected_exists"] = expected_exists
            return True, payload, ""

        if tool in {"copy_file", "move_file"}:
            src_key = "source_path"
            dst_key = "dest_path"
            ok_src, src_norm, err_src = self._validate_path_value(cleaned.get(src_key), allow_dot=False)
            if not ok_src:
                return False, {}, f"source_path invalid: {err_src}"
            ok_dst, dst_norm, err_dst = self._validate_path_value(cleaned.get(dst_key), allow_dot=False)
            if not ok_dst:
                return False, {}, f"dest_path invalid: {err_dst}"
            expected_source_sha256 = cleaned.get("expected_source_sha256")
            if expected_source_sha256 is not None and not isinstance(expected_source_sha256, str):
                return False, {}, "expected_source_sha256 must be a string"
            expected_dest_sha256 = cleaned.get("expected_dest_sha256")
            if expected_dest_sha256 is not None and not isinstance(expected_dest_sha256, str):
                return False, {}, "expected_dest_sha256 must be a string"
            expected_source_exists = cleaned.get("expected_source_exists")
            if expected_source_exists is not None and not isinstance(expected_source_exists, bool):
                return False, {}, "expected_source_exists must be a boolean"
            expected_dest_exists = cleaned.get("expected_dest_exists")
            if expected_dest_exists is not None and not isinstance(expected_dest_exists, bool):
                return False, {}, "expected_dest_exists must be a boolean"
            payload = {src_key: src_norm, dst_key: dst_norm}
            if expected_source_sha256 is not None:
                payload["expected_source_sha256"] = expected_source_sha256
            if expected_dest_sha256 is not None:
                payload["expected_dest_sha256"] = expected_dest_sha256
            if expected_source_exists is not None:
                payload["expected_source_exists"] = expected_source_exists
            if expected_dest_exists is not None:
                payload["expected_dest_exists"] = expected_dest_exists
            return True, payload, ""

        if tool == "git":
            cmd = cleaned.get("cmd")
            if not isinstance(cmd, str) or not cmd.strip():
                return False, {}, "cmd must be a non-empty string"
            return True, {"cmd": cmd}, ""

        if tool == "shell":
            command = cleaned.get("command")
            if not isinstance(command, str) or not command.strip():
                return False, {}, "command must be a non-empty string"
            return True, {"command": command}, ""

        if tool == "system_info":
            info_type = cleaned.get("info_type", "disks")
            if not isinstance(info_type, str) or not info_type.strip():
                return False, {}, "info_type must be a string"
            if info_type not in {"disks", "memory", "system", "processes"}:
                return False, {}, "info_type must be one of: disks, memory, system, processes"
            return True, {"info_type": info_type}, ""

        if tool == "network_info":
            return True, {}, ""

        if tool == "db_add_connection":
            required = ["name", "host", "database", "user", "password"]
            for key in required:
                if not isinstance(cleaned.get(key), str) or not cleaned[key].strip():
                    return False, {}, f"{key} must be a non-empty string"
            port = cleaned.get("port", 5432)
            try:
                port = int(port)
            except (TypeError, ValueError):
                return False, {}, "port must be an integer"
            if not (1 <= port <= 65535):
                return False, {}, "port must be in 1..65535"
            return True, {**{k: cleaned[k] for k in required}, "port": port}, ""

        if tool == "db_execute_query":
            connection_name = cleaned.get("connection_name")
            query = cleaned.get("query")
            if not isinstance(connection_name, str) or not connection_name.strip():
                return False, {}, "connection_name must be a non-empty string"
            if not isinstance(query, str) or not query.strip():
                return False, {}, "query must be a non-empty string"
            params = cleaned.get("params")
            if params is not None and not isinstance(params, list):
                return False, {}, "params must be a list"
            return True, {"connection_name": connection_name, "query": query, "params": params or []}, ""

        if tool == "db_get_schema":
            connection_name = cleaned.get("connection_name")
            if not isinstance(connection_name, str) or not connection_name.strip():
                return False, {}, "connection_name must be a non-empty string"
            table_name = cleaned.get("table_name")
            if table_name is not None and (not isinstance(table_name, str) or not table_name.strip()):
                return False, {}, "table_name must be a string"
            if table_name:
                return True, {"connection_name": connection_name, "table_name": table_name}, ""
            return True, {"connection_name": connection_name}, ""

        if tool == "memory_init":
            connection_name = cleaned.get("connection_name", "agent_memory")
            if not isinstance(connection_name, str) or not connection_name.strip():
                return False, {}, "connection_name must be a non-empty string"
            return True, {"connection_name": connection_name}, ""

        if tool == "memory_search":
            session_id = cleaned.get("session_id")
            query = cleaned.get("query")
            if not isinstance(session_id, str) or not session_id.strip():
                return False, {}, "session_id must be a non-empty string"
            if not isinstance(query, str) or not query.strip():
                return False, {}, "query must be a non-empty string"
            limit = cleaned.get("limit", 20)
            try:
                limit = int(limit)
            except (TypeError, ValueError):
                return False, {}, "limit must be an integer"
            if not (1 <= limit <= 100):
                return False, {}, "limit must be in 1..100"
            return True, {"session_id": session_id, "query": query, "limit": limit}, ""

        return False, {}, "unsupported tool"

    def _validate_tool_calls(self, calls: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        valid_calls: List[Dict[str, Any]] = []
        invalid_results: List[Dict[str, Any]] = []

        for call in calls:
            tool = call.get("tool")
            args = call.get("args", {})
            ok, cleaned, err = self._validate_tool_args(tool, args)
            if ok:
                valid_calls.append({"tool": tool, "args": cleaned})
            else:
                invalid_results.append(
                    {
                        "tool": tool or "unknown",
                        "success": False,
                        "error": f"Invalid tool args: {err}",
                        "args": args,
                    }
                )

        return valid_calls, invalid_results

    def _build_dry_run_calls(self, calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        preview_calls: List[Dict[str, Any]] = []
        for call in calls:
            tool = call.get("tool")
            if tool in self.PREVIEW_TOOLS:
                args = dict(call.get("args", {}))
                args["dry_run"] = True
                preview_calls.append({"tool": tool, "args": args})
        return preview_calls

    def _normalize_match_path(self, value: Optional[str]) -> str:
        if not value:
            return ""
        return str(value).replace("\\", "/").strip("/")

    def _path_matches(self, preview_path: Optional[str], call_path: Optional[str]) -> bool:
        if not preview_path or not call_path:
            return False
        preview_norm = self._normalize_match_path(preview_path)
        call_norm = self._normalize_match_path(call_path)
        return preview_norm.endswith(call_norm)

    def _find_preview_result(
        self,
        tool: str,
        args: Dict[str, Any],
        dry_run_results: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        for item in dry_run_results:
            if item.get("tool") != tool or not item.get("success", False):
                continue
            result = item.get("result", {}) or {}
            if tool in {"write_file", "edit_file", "delete_file"}:
                preview_path = result.get("path_relative") or result.get("path")
                if self._path_matches(preview_path, args.get("path")):
                    return result
            else:
                preview_src = result.get("source_relative") or result.get("source")
                preview_dst = result.get("dest_relative") or result.get("dest")
                if self._path_matches(preview_src, args.get("source_path")) and self._path_matches(
                    preview_dst, args.get("dest_path")
                ):
                    return result
        return None

    def _attach_expectations(
        self, calls: List[Dict[str, Any]], dry_run_results: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        updated: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        for call in calls:
            tool = call.get("tool")
            args = dict(call.get("args", {}))
            if tool not in self.PREVIEW_TOOLS:
                updated.append(call)
                continue

            preview = self._find_preview_result(tool, args, dry_run_results)
            if not preview:
                errors.append({"tool": tool or "unknown", "success": False, "error": "Dry-run preview missing"})
                continue

            if tool in {"write_file", "edit_file", "delete_file"}:
                if "sha256" in preview:
                    args["expected_sha256"] = preview.get("sha256")
                if "exists" in preview:
                    args["expected_exists"] = preview.get("exists")
            else:
                if "source_sha256" in preview:
                    args["expected_source_sha256"] = preview.get("source_sha256")
                if "dest_sha256" in preview:
                    args["expected_dest_sha256"] = preview.get("dest_sha256")
                if "source_exists" in preview:
                    args["expected_source_exists"] = preview.get("source_exists")
                if "dest_exists" in preview:
                    args["expected_dest_exists"] = preview.get("dest_exists")

            updated.append({"tool": tool, "args": args})

        return updated, errors

    def _looks_like_tool_calls(self, text: str) -> bool:
        return "TOOL_CALL" in text

    def _find_json_block(self, text: str, marker: str, open_char: str, close_char: str) -> Optional[str]:
        """Find a JSON-like block after marker, handling nested braces and quoted strings."""
        start_marker = text.find(marker)
        if start_marker == -1:
            return None

        start = text.find(open_char, start_marker)
        if start == -1:
            return None

        depth = 0
        in_str = False
        escape = False

        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue

            if ch == '"':
                in_str = True
                continue
            if ch == open_char:
                depth += 1
                continue
            if ch == close_char:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        return None

    def _parse_tool_calls_payload(self, payload: str) -> List[Dict[str, Any]]:
        parsed = None
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(payload)
                break
            except Exception:
                continue

        if parsed is None:
            return []

        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            return parsed
        return []

    def _extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []

        array_block = self._find_json_block(text, "TOOL_CALLS", "[", "]")
        if array_block:
            calls.extend(self._parse_tool_calls_payload(array_block))

        if not calls and "TOOL_CALL:" in text:
            search_from = 0
            while True:
                idx = text.find("TOOL_CALL:", search_from)
                if idx == -1:
                    break
                block = self._find_json_block(text[idx:], "TOOL_CALL:", "{", "}")
                if block:
                    calls.extend(self._parse_tool_calls_payload(block))
                search_from = idx + len("TOOL_CALL:")

        cleaned: List[Dict[str, Any]] = []
        for call in calls:
            if not isinstance(call, dict):
                continue
            tool = call.get("tool")
            args = call.get("args", {})
            if not isinstance(tool, str) or not tool.strip():
                continue
            if args is None:
                args = {}
            if not isinstance(args, dict):
                continue
            cleaned.append({"tool": tool.strip(), "args": args})

        return cleaned[:5]

    _TOOL_ALIASES = {
        # Model-friendly aliases -> supported tools (read-only conversions only).
        "locate_file": "search",
        "find_file": "search",
        "find_files": "search",
        "grep": "search",
        "ripgrep": "search",
        "rg": "search",
    }

    def _extract_named_file_target(self, task: str) -> Optional[str]:
        """Extract a single explicit filename target from common prompts (English/RU)."""
        if not isinstance(task, str) or not task.strip():
            return None

        patterns = [
            r"\bcreate a file named\s+([^\s\"']+)\b",
            r"\bcreate a file called\s+([^\s\"']+)\b",
            r"\bcreate file\s+([^\s\"']+)\b",
            r"\bсоздай файл\s+([^\s\"']+)\b",
            r"\bсоздать файл\s+([^\s\"']+)\b",
        ]
        matches: List[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, task, flags=re.IGNORECASE):
                candidate = match.group(1).strip().strip(".,;:")
                if candidate:
                    matches.append(candidate)
        if len(matches) != 1:
            return None
        return matches[0]

    def _extract_filename_token(self, task: str) -> Optional[str]:
        """Extract a filename token when only the name (no path) is mentioned."""
        if not isinstance(task, str) or not task.strip():
            return None
        match = re.search(
            r"\b[\w.-]+\.(py|js|ts|md|yml|yaml|json|toml|ini|conf|env|sh|ps1)\b",
            task,
        )
        if not match:
            return None
        token = match.group(0)
        if "/" in token or "\\" in token:
            return None
        return token

    def _derive_search_query(self, task: str) -> Optional[str]:
        if not isinstance(task, str):
            return None
        lowered = task.lower()
        has_todo = "todo" in lowered
        has_fixme = "fixme" in lowered
        if has_todo and has_fixme:
            return "TODO|FIXME"
        if has_todo:
            return "TODO"
        if has_fixme:
            return "FIXME"
        return None

    def _default_search_query_for_task(self, task: str) -> Optional[str]:
        token = self._extract_filename_token(task)
        if token:
            return token
        derived = self._derive_search_query(task)
        if derived:
            return derived
        if not isinstance(task, str):
            return None
        lowered = task.lower()
        if "proxy_pass" in lowered:
            return "proxy_pass"
        if "ports:" in lowered:
            return "ports:"
        if re.search(r"\bports?\b", lowered) or re.search(r"\bport\s+\\d+\b", lowered):
            return "ports"
        if re.search(r"\b(порт|порты|проброшен|проброс)\b", lowered):
            return "ports"
        if "nginx" in lowered:
            return "nginx.conf"
        if "docker-compose" in lowered or ("docker" in lowered and "compose" in lowered):
            return "docker-compose.yml"
        env_match = re.search(r"\b[A-Z][A-Z0-9_]{2,}\b", task)
        if env_match:
            return env_match.group(0)
        return None

    def _fallback_search_queries(self, task: str, current_query: Optional[str]) -> List[str]:
        queries: List[str] = []
        if isinstance(task, str):
            if "/v1" in task:
                queries.append("/v1")
            if "/tools" in task:
                queries.append("/tools")
        default = self._default_search_query_for_task(task)
        if default:
            queries.append(default)
        deduped: List[str] = []
        for query in queries:
            if query and query != current_query and query not in deduped:
                deduped.append(query)
        return deduped

    def _should_use_search_then_read_top_n(self, task: str) -> bool:
        if not isinstance(task, str) or not task.strip():
            return False
        lower = task.lower()
        if "todo" in lower or "fixme" in lower:
            return True
        if "proxy_pass" in lower:
            return True
        if "ports:" in lower or re.search(r"\bports?\b", lower):
            return True
        if re.search(r"\b(порт|порты|проброшен|проброс)\b", lower):
            return True

        token = self._default_search_query_for_task(task)
        if token and re.match(r"^[A-Z][A-Z0-9_]{2,}$", token):
            if re.search(r"\b(used|usage|where)\b", lower) or re.search(r"\b(где|использ)\w*\b", lower):
                return True
        return False

    def _is_sensitive_path_for_evidence(self, path: str) -> bool:
        if not isinstance(path, str) or not path.strip():
            return True
        value = path.strip().replace("\\", "/").lower()
        if value in {".env"} or value.endswith("/.env"):
            return True
        if value.endswith((".key", ".pem", ".p12", ".pfx")):
            return True
        if value.endswith(("id_rsa", "id_ed25519")):
            return True
        if value.endswith((".safetensors", ".gguf", ".bin")):
            return True
        return False

    def _evidence_search_globs(self, task: str, query: str) -> Optional[List[str]]:
        if not isinstance(task, str) or not isinstance(query, str):
            return None
        lower = task.lower()
        q = query.lower()
        if q in {"proxy_pass"} or "nginx" in lower:
            return ["nginx*.conf", "**/*.conf"]
        if q.startswith("ports") or "docker-compose" in lower or "compose" in lower:
            return ["docker-compose*.yml", "docker-compose*.yaml"]
        if q in {"todo", "fixme", "todo|fixme"}:
            return None
        if re.match(r"^[A-Z][A-Z0-9_]{2,}$", query):
            return ["**/*.py", "**/*.yml", "**/*.yaml", "**/*.md", "**/*.env.example", "Dockerfile"]
        return None

    def _evidence_file_sort_key(self, task: str, query: str, path: str) -> Tuple[int, str]:
        p = (path or "").replace("\\", "/").lower()
        score = 0
        q = (query or "").lower()
        lower = (task or "").lower()

        if q == "proxy_pass" or "nginx" in lower:
            if p in {"nginx.conf", "nginx-https-local.conf", "nginx-https.conf"}:
                score -= 20
            elif p.startswith("nginx") and p.endswith(".conf"):
                score -= 10
            elif "nginx" in p and p.endswith(".conf"):
                score -= 6
            elif p.endswith(".conf"):
                score -= 2

        if q.startswith("ports") or "docker-compose" in lower or "compose" in lower:
            if p == "docker-compose.yml":
                score -= 20
            elif p.startswith("docker-compose"):
                score -= 10
            elif p.endswith((".yml", ".yaml")):
                score -= 2

        if re.match(r"^[A-Z][A-Z0-9_]{2,}$", query):
            if p in {"docker-compose.yml", "docker-compose-prod.yml", ".env.example"}:
                score -= 10
            elif p.startswith("docker-compose"):
                score -= 6
            elif p.startswith("agent_runtime/orchestrator/"):
                score -= 4
            elif p.endswith(".py"):
                score -= 2

        return (score, p)

    _SENSITIVE_KV_KEYS = re.compile(r"(api[_-]?key|token|secret|password|passwd|pass|private[_-]?key)", re.IGNORECASE)

    def _redact_sensitive_line(self, line: str) -> str:
        if not isinstance(line, str) or not line:
            return ""

        # Redact any literal OpenAI-style key fragments.
        line = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", line)

        # Redact private key blocks lines (full block handling happens in `_redact_sensitive_text`).
        if "BEGIN PRIVATE KEY" in line or "BEGIN RSA PRIVATE KEY" in line:
            return "[REDACTED PRIVATE KEY BLOCK]"

        # Key-value patterns like FOO=bar or FOO: bar.
        kv = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*[:=]\s*)(.*)$", line)
        if kv:
            key = kv.group(2)
            value = kv.group(4)
            if self._SENSITIVE_KV_KEYS.search(key):
                stripped = value.strip()
                # Keep env references like ${VAR} / ${VAR:-default}.
                if stripped.startswith("${"):
                    return line
                # Use ":" to avoid leaking "KEY=" patterns in evidence output.
                return f"{kv.group(1)}{key}: [REDACTED]"

        # Authorization headers
        line = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)(\S+)", r"\1[REDACTED]", line)
        # Also remove the Bearer scheme word to avoid leaking it verbatim in evidence output.
        line = re.sub(r"(?i)\bbearer\b", "[REDACTED_SCHEME]", line)
        return line

    def _redact_sensitive_text(self, text: str) -> str:
        if not isinstance(text, str) or not text:
            return ""
        lines: List[str] = []
        in_key_block = False
        for raw in text.splitlines():
            line = raw
            if re.search(r"-----BEGIN (RSA )?PRIVATE KEY-----", line):
                in_key_block = True
                lines.append("[REDACTED PRIVATE KEY BLOCK]")
                continue
            if in_key_block:
                if re.search(r"-----END (RSA )?PRIVATE KEY-----", line):
                    in_key_block = False
                continue
            lines.append(self._redact_sensitive_line(line))
        return "\n".join(lines)

    def _format_evidence_block(
        self,
        query: str,
        search_payload: Dict[str, Any],
        tool_results: List[Dict[str, Any]],
        read_results: List[Dict[str, Any]],
        max_lines: int,
        fallback_used: bool,
        skipped_files: Optional[List[str]] = None,
    ) -> str:
        max_total_chars = int(os.getenv("EVIDENCE_MAX_CHARS", "60000"))

        lines: List[str] = []
        lines.append("=== Evidence (tool output) ===")
        lines.append(f"query: {query}")
        if fallback_used:
            lines.append("search: fallback globs used")

        errors: List[str] = []
        for item in tool_results:
            tool = item.get("tool") or "tool"
            if item.get("success"):
                continue
            payload = item.get("result")
            if isinstance(payload, dict):
                detail = payload.get("detail") or payload.get("error")
                if isinstance(detail, str) and detail.strip():
                    errors.append(f"{tool}: {detail.strip()}")
                    continue
            error_text = item.get("error")
            if isinstance(error_text, str) and error_text.strip():
                errors.append(f"{tool}: {error_text.strip()}")
        if errors:
            lines.append("")
            lines.append("--- errors ---")
            lines.extend(errors[:10])

        count = search_payload.get("count")
        match_count = search_payload.get("match_count")
        if isinstance(count, int):
            lines.append(f"files_found: {count}")
        if isinstance(match_count, int):
            lines.append(f"matches_found: {match_count}")

        if skipped_files:
            listed = [f for f in skipped_files if isinstance(f, str)]
            if listed:
                lines.append("")
                lines.append("--- skipped (sensitive) ---")
                lines.extend(listed[:10])

        matches = search_payload.get("matches")
        if isinstance(matches, list) and matches:
            lines.append("")
            lines.append("--- matches (top) ---")
            shown = 0
            for match in matches:
                if not isinstance(match, dict):
                    continue
                path = match.get("path")
                line_no = match.get("line")
                text = match.get("text")
                if not isinstance(path, str):
                    continue
                if not isinstance(line_no, int):
                    line_no = 0
                if not isinstance(text, str):
                    text = ""
                lines.append(f"{path}:{line_no} {self._redact_sensitive_line(text)}")
                shown += 1
                if shown >= 40:
                    break

        for item in read_results:
            tool = item.get("tool")
            success = item.get("success", False)
            payload = item.get("result") or {}
            if tool != "read_file" or not success or not isinstance(payload, dict):
                continue
            path = payload.get("path_relative") or payload.get("path") or "unknown"
            content = payload.get("content") or ""
            if not isinstance(content, str):
                continue
            redacted = self._redact_sensitive_text(content)
            raw_lines = redacted.splitlines()
            snippet_lines = raw_lines[:max_lines]
            trimmed_lines: List[str] = []
            for line in snippet_lines:
                if len(line) > 250:
                    trimmed_lines.append(line[:250] + "…[TRUNCATED]")
                else:
                    trimmed_lines.append(line)
            snippet = "\n".join(trimmed_lines)
            truncated = len(raw_lines) > max_lines
            lines.append("")
            header = f"--- file: {path} (first {max_lines} lines){' [TRUNCATED]' if truncated else ''} ---"

            current_len = sum(len(l) + 1 for l in lines)
            projected = current_len + len(header) + 1 + len(snippet) + 1
            if projected > max_total_chars:
                remaining = max_total_chars - current_len - len(header) - 1 - len("\n...[EVIDENCE TRUNCATED]...\n")
                if remaining <= 0:
                    lines.append("...[EVIDENCE TRUNCATED]...")
                    break
                lines.append(header)
                lines.append(snippet[:remaining].rstrip() + "\n...[EVIDENCE TRUNCATED]...")
                break

            lines.append(header)
            lines.append(snippet)

        return "\n".join(lines).strip()

    def search_then_read_top_n(
        self,
        task: str,
        query: Optional[str] = None,
        top_n: int = 5,
        max_lines: int = 200,
    ) -> Dict[str, Any]:
        query_value = (query or self._default_search_query_for_task(task) or "").strip()
        if not query_value:
            return {
                "success": False,
                "tool_calls": [],
                "tool_results": [],
                "evidence": "=== Evidence (tool output) ===\nerror: unable to derive search query",
            }

        globs = self._evidence_search_globs(task, query_value)
        search_args: Dict[str, Any] = {"query": query_value}
        if globs:
            search_args["globs"] = globs
        search_calls = [{"tool": "search", "args": search_args}]
        search_results = self._execute_tool_calls(search_calls)
        search_payload: Dict[str, Any] = {}
        files: List[str] = []
        fallback_used = False
        if search_results and search_results[0].get("success") and isinstance(search_results[0].get("result"), dict):
            search_payload = search_results[0]["result"]
            files = search_payload.get("files") or []
            if not isinstance(files, list):
                files = []

        if not files:
            fallback_used = True
            fallback_globs = [
                "docker-compose*.yml",
                "nginx*.conf",
                "**/*.env",
                "agent_runtime/orchestrator/agent.py",
            ]
            fallback_calls = [{"tool": "search", "args": {"query": query_value, "globs": fallback_globs}}]
            search_results = self._execute_tool_calls(fallback_calls)
            search_calls = fallback_calls
            if search_results and search_results[0].get("success") and isinstance(search_results[0].get("result"), dict):
                search_payload = search_results[0]["result"]
                files = search_payload.get("files") or []
                if not isinstance(files, list):
                    files = []

        files = [f for f in files if isinstance(f, str)]
        files.sort(key=lambda p: self._evidence_file_sort_key(task, query_value, p))
        selected_files: List[str] = []
        skipped_files: List[str] = []
        for path in files:
            if len(selected_files) >= max(1, top_n):
                break
            if self._is_sensitive_path_for_evidence(path):
                skipped_files.append(path)
                continue
            selected_files.append(path)
        top_files = selected_files
        read_calls = [{"tool": "read_file", "args": {"path": path}} for path in top_files]
        read_results = self._execute_tool_calls(read_calls) if read_calls else []
        tool_results = search_results + read_results
        evidence = self._format_evidence_block(
            query=query_value,
            search_payload=search_payload if isinstance(search_payload, dict) else {},
            tool_results=tool_results,
            read_results=read_results,
            max_lines=max_lines,
            fallback_used=fallback_used,
            skipped_files=skipped_files,
        )
        return {"success": True, "tool_calls": search_calls + read_calls, "tool_results": tool_results, "evidence": evidence}

    def _apply_tool_arg_fallbacks(self, task: str, calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not calls:
            return calls
        query = self._default_search_query_for_task(task)
        file_token = self._extract_filename_token(task)
        updated: List[Dict[str, Any]] = []
        for call in calls:
            if not isinstance(call, dict):
                continue
            tool = call.get("tool")
            args = call.get("args")
            if not isinstance(args, dict):
                args = {}
            if tool == "search":
                current = args.get("query")
                if not isinstance(current, str) or not current.strip():
                    if query:
                        args["query"] = query
            elif tool == "read_file":
                current = args.get("path")
                if not isinstance(current, str) or not current.strip():
                    if file_token:
                        args["path"] = file_token
            call["args"] = args
            updated.append(call)
        return updated

    def _build_fallback_tool_calls(self, task: str, required: List[str]) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        query = self._default_search_query_for_task(task)
        if "search" in required and query:
            calls.append({"tool": "search", "args": {"query": query}})
        if "read_file" in required and "search" not in required:
            token = self._extract_filename_token(task)
            if token:
                calls.append({"tool": "read_file", "args": {"path": token}})
        return calls

    def _normalize_tool_calls(self, task: str, calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize tool calls for better reliability (safe, deterministic transforms)."""
        target_file = self._extract_named_file_target(task)
        normalized: List[Dict[str, Any]] = []

        for call in calls:
            if not isinstance(call, dict):
                continue
            tool = call.get("tool")
            args = call.get("args") or {}
            if not isinstance(tool, str) or not isinstance(args, dict):
                normalized.append(call)
                continue

            tool_name = tool.strip()
            tool_key = tool_name.lower()

            # Apply safe aliases (read-only only).
            if tool_name not in TOOL_SPECS:
                alias = self._TOOL_ALIASES.get(tool_key)
                if alias == "search":
                    query = args.get("query")
                    if not isinstance(query, str) or not query.strip():
                        query = args.get("path") if isinstance(args.get("path"), str) else ""
                    if not query:
                        query = self._default_search_query_for_task(task) or ""
                    new_args: Dict[str, Any] = {"query": query}
                    globs = args.get("globs")
                    if isinstance(globs, list):
                        new_args["globs"] = globs
                    normalized.append({"tool": "search", "args": new_args})
                    continue

            # Fill missing args for safe read-only calls.
            if tool_name == "search":
                query = args.get("query")
                if not isinstance(query, str) or not query.strip():
                    derived = self._default_search_query_for_task(task)
                    if derived:
                        new_args = dict(args)
                        new_args["query"] = derived
                        normalized.append({"tool": tool_name, "args": new_args})
                        continue

            # If task clearly names a target file, prevent (or correct) mismatched writes.
            if target_file and tool_name == "write_file":
                path = args.get("path")
                if isinstance(path, str) and path.strip() and path.strip() != target_file:
                    new_args = dict(args)
                    new_args["path"] = target_file
                    normalized.append({"tool": tool_name, "args": new_args})
                    continue

            normalized.append({"tool": tool_name, "args": args})

        return normalized

    def _repair_tool_calls(self, text: str) -> Optional[str]:
        """Ask the model to re-emit valid TOOL_CALLS JSON if parsing failed."""
        if not self._looks_like_tool_calls(text):
            return None

        system = (
            "You must output ONLY valid TOOL_CALLS JSON. "
            "Do not include any other text. Use this exact format:\n"
            "TOOL_CALLS: [{\"tool\": \"name\", \"args\": {...}}]"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Fix this into valid TOOL_CALLS JSON:\n{text}"},
        ]
        try:
            return self._call_llm(messages, max_tokens=200)
        except Exception:
            return None

    def _tool_call_requires_confirmation(self, call: Dict[str, Any]) -> bool:
        tool = call.get("tool")
        args = call.get("args", {})
        if tool not in TOOL_SPECS:
            return False
        if not TOOL_SPECS[tool].get("confirm"):
            return False
        if tool == "db_execute_query":
            query = str(args.get("query", "")).strip().lower()
            return not query.startswith(READ_ONLY_SQL_PREFIXES)
        return True

    def _execute_tool_calls(
        self, calls: List[Dict[str, Any]], invalid_results: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        results = list(invalid_results or [])
        for call in calls:
            tool = call.get("tool")
            args = call.get("args", {})
            spec = TOOL_SPECS.get(tool)
            if not spec:
                results.append({"tool": tool, "success": False, "error": "Unknown tool"})
                continue
            try:
                response = requests.post(
                    f"{self.tool_url}{spec['endpoint']}",
                    json=args,
                    headers=self._tool_headers(),
                    timeout=30,
                )
                data = response.json()
                results.append({"tool": tool, "success": response.ok, "result": data})
            except Exception as e:
                results.append({"tool": tool, "success": False, "error": str(e)})
        return results

    def _format_tool_results(self, results: List[Dict[str, Any]]) -> str:
        lines = []
        for item in results:
            tool = item.get("tool")
            success = item.get("success", False)
            payload = item.get("result") or {"error": item.get("error")}

            if tool == "read_file" and success and isinstance(payload, dict):
                path = payload.get("path_relative") or payload.get("path") or "unknown"
                content = payload.get("content", "")
                if isinstance(content, str):
                    if len(content) > 6000:
                        content = content[:6000] + "\n...[TRUNCATED]..."
                    lines.append(f"read_file ({path}):\n{content}")
                    continue

            if tool == "search" and success and isinstance(payload, dict):
                files = payload.get("files")
                if isinstance(files, list) and files:
                    listed = "\n".join(f"- {f}" for f in files[:20])
                    lines.append("search results:\n" + listed)
                    continue

            payload_text = json.dumps(payload, ensure_ascii=True)[:2000]
            status = "ok" if success else "error"
            lines.append(f"{tool} ({status}): {payload_text}")
        return "\n".join(lines)

    def _tool_focus_instructions(self, task: str) -> str:
        lower = task.lower()
        if "docker-compose" in lower or "compose" in lower:
            return "Answer the question using exact port mappings from docker-compose.yml."
        if "nginx" in lower:
            return "Name the file and the exact location blocks for /v1 and /tools."
        if "agent_llm_url" in lower:
            return "List files and describe how AGENT_LLM_URL is used in each."
        if "todo" in lower or "fixme" in lower:
            return "List file:line hits from search results."
        return "Use tool results only; do not guess."

    def _finalize_with_tool_results(
        self, messages: List[Dict[str, str]], first_response: str, results: List[Dict[str, Any]]
    ) -> str:
        tool_summary = self._format_tool_results(results)
        task_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                task_text = msg.get("content", "") or ""
                break
        focus = self._tool_focus_instructions(task_text)
        messages_pass2 = [
            *messages,
            {"role": "assistant", "content": first_response},
            {"role": "system", "content": "Tool results:\n" + tool_summary},
            {"role": "system", "content": "Use tool results only. " + focus},
            {"role": "user", "content": "Provide the final answer. Do not request more tools."},
        ]
        final = self._call_llm(messages_pass2)
        if self._extract_tool_calls(final):
            messages_pass3 = [
                *messages_pass2,
                {"role": "assistant", "content": final},
                {"role": "system", "content": "Tool calls are NOT allowed now. Respond with the final answer only."},
            ]
            retry = self._call_llm(messages_pass3)
            if not self._extract_tool_calls(retry):
                return retry
            return "Final response blocked: model kept requesting tools after results."
        return final

    def think_with_tools(self, task: str, require_confirmation: bool = True) -> Dict[str, Any]:
        if self._should_use_search_then_read_top_n(task):
            evidence = self.search_then_read_top_n(task)
            return {
                "status": "final",
                "response": evidence.get("evidence", ""),
                "tool_calls": evidence.get("tool_calls", []),
                "tool_results": evidence.get("tool_results", []),
            }

        required_tools = self._required_tools_for_task(task)
        messages = self._build_tool_messages(task, required_tools=required_tools)
        first = self._call_llm(messages)

        def _extract_calls(text: str) -> Tuple[str, List[Dict[str, Any]]]:
            calls = self._normalize_tool_calls(task, self._extract_tool_calls(text))
            if not calls and self._looks_like_tool_calls(text):
                repaired = self._repair_tool_calls(text)
                if repaired:
                    repaired_calls = self._normalize_tool_calls(task, self._extract_tool_calls(repaired))
                    if repaired_calls:
                        return repaired, repaired_calls
            return text, calls

        first, tool_calls = _extract_calls(first)

        if required_tools:
            missing = self._missing_required_tools(tool_calls, required_tools)
            if missing:
                forced_messages = self._build_tool_messages(task, required_tools=required_tools, force_tools=True)
                forced = self._call_llm(forced_messages)
                forced, tool_calls = _extract_calls(forced)
                missing = self._missing_required_tools(tool_calls, required_tools)
                if missing:
                    fallback_calls = self._build_fallback_tool_calls(task, required_tools)
                    if fallback_calls:
                        tool_calls = fallback_calls
                        first = forced
                    else:
                        return {
                            "status": "final",
                            "response": f"Tool use required: {', '.join(missing)}.",
                            "tool_calls": [],
                        }
                else:
                    first = forced

        tool_calls = self._apply_tool_arg_fallbacks(task, tool_calls)

        file_token = self._extract_filename_token(task)
        if file_token:
            for call in tool_calls:
                if call.get("tool") == "search":
                    args = call.get("args") or {}
                    if isinstance(args, dict):
                        args = dict(args)
                        args["query"] = file_token
                        call["args"] = args

        if not tool_calls:
            return {"status": "final", "response": first, "tool_calls": []}

        valid_calls, invalid_results = self._validate_tool_calls(tool_calls)
        if not valid_calls and invalid_results:
            # One more repair pass for common failure modes: unknown tool names / missing required args.
            repaired = self._repair_tool_calls(first)
            if repaired and repaired != first:
                repaired_calls = self._normalize_tool_calls(task, self._extract_tool_calls(repaired))
                if repaired_calls:
                    repaired_valid, repaired_invalid = self._validate_tool_calls(repaired_calls)
                    if repaired_valid:
                        first = repaired
                        tool_calls = repaired_calls
                        valid_calls, invalid_results = repaired_valid, repaired_invalid

            if not valid_calls and invalid_results:
                return {
                    "status": "final",
                    "response": f"Invalid tool call(s): {', '.join(r['error'] for r in invalid_results)}",
                    "tool_calls": [],
                    "tool_results": invalid_results,
                }

        search_first = "search" in required_tools and "read_file" in required_tools
        if search_first:
            search_calls = [c for c in valid_calls if c.get("tool") == "search"]
            other_calls = [c for c in valid_calls if c.get("tool") not in {"search", "read_file"}]
            search_results = self._execute_tool_calls(search_calls)

            allowed_paths: List[str] = []
            for item in search_results:
                payload = item.get("result") or {}
                files = payload.get("files") or []
                if isinstance(files, list):
                    allowed_paths.extend([f for f in files if isinstance(f, str)])
            allowed_paths = list(dict.fromkeys(allowed_paths))

            if not allowed_paths:
                current_query = None
                if search_calls:
                    current_args = search_calls[0].get("args")
                    if isinstance(current_args, dict):
                        value = current_args.get("query")
                        if isinstance(value, str):
                            current_query = value
                for fallback_query in self._fallback_search_queries(task, current_query):
                    fallback_calls = [{"tool": "search", "args": {"query": fallback_query}}]
                    fallback_results = self._execute_tool_calls(fallback_calls)
                    fallback_paths: List[str] = []
                    for item in fallback_results:
                        payload = item.get("result") or {}
                        files = payload.get("files") or []
                        if isinstance(files, list):
                            fallback_paths.extend([f for f in files if isinstance(f, str)])
                    fallback_paths = list(dict.fromkeys(fallback_paths))
                    if fallback_paths:
                        search_calls = fallback_calls
                        search_results = fallback_results
                        allowed_paths = fallback_paths
                        break
            if not allowed_paths:
                return {
                    "status": "final",
                    "response": "Search returned no files to read. Refine the query.",
                    "tool_calls": search_calls,
                    "tool_results": search_results + list(invalid_results or []),
                }

            if file_token and file_token in allowed_paths:
                read_calls = [{"tool": "read_file", "args": {"path": file_token}}]
                read_results = self._execute_tool_calls(read_calls)
                tool_results = search_results + read_results + list(invalid_results or [])
                if other_calls:
                    tool_results += self._execute_tool_calls(other_calls)
                final = self._finalize_with_tool_results(messages, first, tool_results)
                return {
                    "status": "final",
                    "response": final,
                    "tool_calls": search_calls + read_calls + other_calls,
                    "tool_results": tool_results,
                }

            max_listed = 20
            listed = "\n".join(f"- {p}" for p in allowed_paths[:max_listed])
            followup_messages = self._build_tool_messages(
                task,
                required_tools=["read_file"],
                force_tools=True,
            )
            followup_messages.append(
                {
                    "role": "system",
                    "content": "Search results files (use read_file only for these paths):\n" + listed,
                }
            )
            followup = self._call_llm(followup_messages)
            followup, followup_calls = _extract_calls(followup)

            read_calls = [c for c in followup_calls if c.get("tool") == "read_file"]
            if not read_calls:
                return {
                    "status": "final",
                    "response": "read_file required after search. Re-run and select a file from search results.",
                    "tool_calls": search_calls,
                    "tool_results": search_results,
                }

            invalid_read = [
                c for c in read_calls if c.get("args", {}).get("path") not in set(allowed_paths)
            ]
            if invalid_read:
                return {
                    "status": "final",
                    "response": "read_file path must be selected from search results.",
                    "tool_calls": search_calls,
                    "tool_results": search_results,
                }

            read_results = self._execute_tool_calls(read_calls)
            tool_results = search_results + read_results + list(invalid_results or [])
            if other_calls:
                tool_results += self._execute_tool_calls(other_calls)

            final = self._finalize_with_tool_results(followup_messages, followup, tool_results)
            return {
                "status": "final",
                "response": final,
                "tool_calls": search_calls + read_calls + other_calls,
                "tool_results": tool_results,
            }

        if require_confirmation and any(self._tool_call_requires_confirmation(c) for c in valid_calls):
            dry_run_results: List[Dict[str, Any]] = []
            preview_calls = self._build_dry_run_calls(valid_calls)
            if preview_calls:
                dry_run_results = self._execute_tool_calls(preview_calls)
            return {
                "status": "confirmation_required",
                "response": first,
                "tool_calls": valid_calls,
                "task": task,
                "validation_errors": invalid_results,
                "dry_run_results": dry_run_results,
            }

        tool_results = self._execute_tool_calls(valid_calls, invalid_results)
        final = self._finalize_with_tool_results(messages, first, tool_results)
        return {
            "status": "final",
            "response": final,
            "tool_calls": valid_calls,
            "tool_results": tool_results,
        }

    def approve_tool_calls(self, pending_action: Dict[str, Any]) -> Dict[str, Any]:
        task = pending_action.get("task", "")
        tool_calls = pending_action.get("tool_calls", [])
        first_response = pending_action.get("response", "")
        dry_run_results = pending_action.get("dry_run_results", []) or []

        messages = self._build_tool_messages(task)
        valid_calls, invalid_results = self._validate_tool_calls(tool_calls)
        if not valid_calls and invalid_results:
            return {
                "status": "final",
                "response": f"Invalid tool call(s): {', '.join(r['error'] for r in invalid_results)}",
                "tool_results": invalid_results,
            }
        if any(call.get("tool") in self.PREVIEW_TOOLS for call in valid_calls):
            if not dry_run_results:
                return {
                    "status": "final",
                    "response": "Dry-run preview missing. Re-run the task to regenerate previews.",
                    "tool_results": [{"success": False, "error": "Missing dry-run preview"}],
                }
            updated_calls, preview_errors = self._attach_expectations(valid_calls, dry_run_results)
            if preview_errors:
                return {
                    "status": "final",
                    "response": "Dry-run preview mismatch. Re-run the task to regenerate previews.",
                    "tool_results": preview_errors,
                }
            valid_calls, invalid_results = self._validate_tool_calls(updated_calls)
            if not valid_calls and invalid_results:
                return {
                    "status": "final",
                    "response": f"Invalid tool call(s): {', '.join(r['error'] for r in invalid_results)}",
                    "tool_results": invalid_results,
                }
        tool_results = self._execute_tool_calls(valid_calls, invalid_results)
        final = self._finalize_with_tool_results(messages, first_response, tool_results)
        return {"status": "final", "response": final, "tool_results": tool_results}

    def read_file(self, path: str) -> Dict[str, Any]:
        """Чтение файла через tool server"""
        try:
            response = requests.post(
                f"{self.tool_url}/tools/read_file",
                json={"path": path},
                headers=self._tool_headers(),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file_patch(self, path: str, patch: str) -> Dict[str, Any]:
        """Запись файла через patch"""
        try:
            response = requests.post(
                f"{self.tool_url}/tools/write_file_patch",
                json={"path": path, "patch": patch},
                headers=self._tool_headers(),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def think_triage(self, task: str, max_tokens: int = 350) -> Dict[str, Any]:
        """
        Pass 1 (Triage): быстрый анализ с флагом needs_consilium.

        Возвращает:
        {
            "response": str,
            "needs_consilium": bool,
            "reason": str,  # почему нужен/не нужен consilium
            "suggested_agents": List[str]  # какие агенты нужны если escalate
        }
        """
        import re

        system = (
            "You are a triage agent. Analyze tasks and decide if consilium (multiple experts) is needed.\n\n"
            "ALWAYS use this EXACT format:\n"
            "ANSWER: <brief answer OR 'ESCALATE'>\n"
            "NEEDS_CONSILIUM: <yes OR no>\n"
            "REASON: <one sentence>\n"
            "SUGGESTED_AGENTS: <if yes: security,architect,qa etc OR if no: none>\n\n"
            "Examples:\n\n"
            "Task: What is Python?\n"
            "ANSWER: Python is a high-level programming language.\n"
            "NEEDS_CONSILIUM: no\n"
            "REASON: Simple informational question.\n"
            "SUGGESTED_AGENTS: none\n\n"
            "Task: Review JWT token security\n"
            "ANSWER: ESCALATE\n"
            "NEEDS_CONSILIUM: yes\n"
            "REASON: Security review requires security expert.\n"
            "SUGGESTED_AGENTS: security,dev\n\n"
            "Task: Migrate database to PostgreSQL\n"
            "ANSWER: ESCALATE\n"
            "NEEDS_CONSILIUM: yes\n"
            "REASON: Architecture change needs architect and qa.\n"
            "SUGGESTED_AGENTS: architect,qa,dev"
        )

        messages = [{"role": "system", "content": system}, {"role": "user", "content": f"Task: {task}"}]

        response = self._call_llm(messages, max_tokens=max_tokens)

        # Parse response with robust fallbacks
        needs_consilium = False
        reason = "No reason provided"
        suggested_agents = []
        answer = response.strip()

        # Extract NEEDS_CONSILIUM
        match = re.search(r"NEEDS_CONSILIUM:\s*(yes|no)", response, re.IGNORECASE)
        if match:
            needs_consilium = match.group(1).lower() == "yes"
        else:
            # Fallback: keyword detection
            lower_resp = response.lower()
            security_kw = [
                "security",
                "vulnerability",
                "auth",
                "token",
                "jwt",
                "injection",
                "xss",
                "csrf",
                # RU stems
                "безопас",
                "уязвим",
                "аутентиф",
                "авторизац",
                "токен",
                "секрет",
                "парол",
                "инъекц",
            ]
            arch_kw = [
                "migration",
                "architecture",
                "scaling",
                "refactor",
                "database",
                # RU stems
                "архитект",
                "миграц",
                "масштаб",
                "рефактор",
                "база данных",
                "бд",
            ]
            incident_kw = [
                "incident",
                "outage",
                "breach",
                "attack",
                "production down",
                # RU stems
                "инцидент",
                "атака",
                "взлом",
                "утечк",
                "прод упал",
                "прод лежит",
                "простой",
            ]

            if any(kw in lower_resp for kw in security_kw + arch_kw + incident_kw):
                needs_consilium = True
                reason = "Detected security/architecture/incident keywords"

        # Extract REASON
        match = re.search(r"REASON:\s*(.+?)(?:\n|$)", response, re.IGNORECASE)
        if match:
            reason = match.group(1).strip()

        # Extract SUGGESTED_AGENTS
        match = re.search(r"SUGGESTED_AGENTS:\s*(.+?)(?:\n|$)", response, re.IGNORECASE)
        if match:
            agents_str = match.group(1).strip()
            if agents_str and agents_str.lower() not in ["none", "empty", "-", "n/a"]:
                suggested_agents = [a.strip() for a in agents_str.split(",") if a.strip()]

        # Extract ANSWER
        match = re.search(r"ANSWER:\s*(.+?)(?:\nNEEDS_CONSILIUM|$)", response, re.IGNORECASE | re.DOTALL)
        if match:
            answer = match.group(1).strip()

        return {
            "response": answer,
            "needs_consilium": needs_consilium,
            "reason": reason,
            "suggested_agents": suggested_agents,
            "raw_response": response,
        }

    def think(self, task: str) -> str:
        """
        Optimized thinking loop:
        - Inject repo snapshot if available
        - Only do 2-pass if READ_FILE is really needed
        """
        if self.is_director:
            messages = [
                {
                    "role": "system",
                    "content": "You are the Project Director. Do not request files or tools. Provide concise decisions.",
                },
                {"role": "user", "content": task},
            ]
            return self._call_llm(messages)

        system = (
            "You are an autonomous software agent.\n"
            "You are given a repository snapshot (file tree).\n"
            "First write PLAN.\n"
            "If and only if necessary, request files using:\n"
            "READ_FILE: <relative_path>\n"
            "Do not hallucinate file contents.\n"
            "If files are provided, produce FINAL answer.\n"
            "Otherwise answer directly."
        )

        # ---- Load repo snapshot once (track as retrieval) ----
        if self.repo_snapshot is None:
            self._ensure_repo_snapshot()

        messages = [
            {"role": "system", "content": system},
            {
                "role": "system",
                "content": "Repository snapshot:\n" + self.repo_snapshot,
            },
            {"role": "user", "content": task},
        ]

        # ---- PASS 1 ----
        first = self._call_llm(messages)

        # Check for READ_FILE
        paths = re.findall(r"READ_FILE:\s*(.+)", first)
        paths = [p.strip() for p in paths if p.strip()]
        paths = list(dict.fromkeys(paths))

        if not paths:
            return first

        # ---- PASS 2 (only if needed) ----
        files_blob = []
        retrieval_start = time.perf_counter()
        for p in paths[:6]:
            try:
                r = requests.post(
                    f"{self.tool_url}/tools/read_file",
                    json={"path": p},
                    headers=self._tool_headers(),
                    timeout=15,
                )
                r.raise_for_status()
                content = r.json().get("content", "")
                if len(content) > 15000:
                    content = content[:15000] + "\n\n...[TRUNCATED]..."
                files_blob.append(f"=== FILE: {p} ===\n{content}\n")
            except Exception as e:
                files_blob.append(f"=== FILE: {p} ===\n[ERROR: {e}]\n")

        # Track retrieval timing for file reads
        if paths:
            elapsed_ms = (time.perf_counter() - retrieval_start) * 1000
            self._retrieval_times.append(elapsed_ms)
            self._retrieval_call_count += 1

        messages_pass2 = [
            {"role": "system", "content": system},
            {
                "role": "system",
                "content": "Repository snapshot:\n" + self.repo_snapshot,
            },
            {"role": "user", "content": task},
            {"role": "assistant", "content": first},
            {
                "role": "system",
                "content": "Requested file contents:\n\n" + "\n".join(files_blob),
            },
            {
                "role": "user",
                "content": "Provide the FINAL answer. Do not request more files.",
            },
        ]

        final = self._call_llm(messages_pass2)
        return final

    def analyze_code(self, file_path: str, question: str) -> str:
        """Анализ кода из файла"""
        # Читаем файл
        file_data = self.read_file(file_path)

        if not file_data.get("success", True):
            return f"Error reading file: {file_data.get('error')}"

        content = file_data.get("content", "")

        # Формируем запрос к LLM
        prompt = f"""Analyze this code and answer the question.

File: {file_path}
```
{content[:2000]}  # ограничиваем для контекста
```

Question: {question}

Provide a clear, concise answer."""

        return self.think(prompt)

    def get_timing_stats(self) -> Dict[str, Any]:
        """Получить статистику времени выполнения (скользящее среднее)"""
        avg_llm_ms = round(sum(self._llm_times) / len(self._llm_times), 1) if self._llm_times else 0
        avg_retrieval_ms = (
            round(sum(self._retrieval_times) / len(self._retrieval_times), 1) if self._retrieval_times else 0
        )

        # Добавляем статус Circuit Breaker
        circuit_breaker = get_llm_circuit_breaker()

        return {
            "avg_llm_ms": avg_llm_ms,
            "avg_retrieval_ms": avg_retrieval_ms,
            "llm_calls": self._llm_call_count,
            "retrieval_calls": self._retrieval_call_count,
            "retry_count": self._retry_count,
            "window_size": self.TIMING_WINDOW,
            "llm_samples": len(self._llm_times),
            "retrieval_samples": len(self._retrieval_times),
            "retry_config": {
                "max_retries": self._max_retries,
                "base_delay": self._retry_base_delay,
                "max_delay": self._retry_max_delay,
            },
            "circuit_breaker": circuit_breaker.get_status(),
        }
