"""
Базовый агент с доступом к LLM и tools
"""
import json
import re
import time
from collections import deque
from typing import Any, Dict, List, Optional

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

    def _build_tool_messages(self, task: str) -> List[Dict[str, str]]:
        self._ensure_repo_snapshot()
        return [
            {"role": "system", "content": self._build_tool_system_prompt()},
            {"role": "system", "content": "Repository snapshot:\n" + (self.repo_snapshot or "")},
            {"role": "user", "content": task},
        ]

    def _extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []

        array_match = re.search(r"TOOL_CALLS:\s*(\[[\s\S]+?\])", text)
        if array_match:
            try:
                parsed = json.loads(array_match.group(1))
                if isinstance(parsed, list):
                    calls.extend(parsed)
            except json.JSONDecodeError:
                pass

        if not calls:
            for match in re.finditer(r"TOOL_CALL:\s*({[\s\S]+?})", text):
                try:
                    parsed = json.loads(match.group(1))
                    if isinstance(parsed, dict):
                        calls.append(parsed)
                except json.JSONDecodeError:
                    continue

        cleaned = []
        for call in calls:
            if not isinstance(call, dict):
                continue
            tool = call.get("tool")
            args = call.get("args", {})
            if tool in TOOL_SPECS and isinstance(args, dict):
                cleaned.append({"tool": tool, "args": args})

        return cleaned[:5]

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

    def _execute_tool_calls(self, calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
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
            payload = item.get("result") or {"error": item.get("error")}
            payload_text = json.dumps(payload, ensure_ascii=True)[:2000]
            lines.append(f"{tool}: {payload_text}")
        return "\n".join(lines)

    def _finalize_with_tool_results(
        self, messages: List[Dict[str, str]], first_response: str, results: List[Dict[str, Any]]
    ) -> str:
        tool_summary = self._format_tool_results(results)
        messages_pass2 = [
            *messages,
            {"role": "assistant", "content": first_response},
            {"role": "system", "content": "Tool results:\n" + tool_summary},
            {"role": "user", "content": "Provide the final answer. Do not request more tools."},
        ]
        return self._call_llm(messages_pass2)

    def think_with_tools(self, task: str, require_confirmation: bool = True) -> Dict[str, Any]:
        messages = self._build_tool_messages(task)
        first = self._call_llm(messages)

        tool_calls = self._extract_tool_calls(first)
        if not tool_calls:
            return {"status": "final", "response": first, "tool_calls": []}

        if require_confirmation and any(self._tool_call_requires_confirmation(c) for c in tool_calls):
            return {
                "status": "confirmation_required",
                "response": first,
                "tool_calls": tool_calls,
                "task": task,
            }

        tool_results = self._execute_tool_calls(tool_calls)
        final = self._finalize_with_tool_results(messages, first, tool_results)
        return {
            "status": "final",
            "response": final,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
        }

    def approve_tool_calls(self, pending_action: Dict[str, Any]) -> Dict[str, Any]:
        task = pending_action.get("task", "")
        tool_calls = pending_action.get("tool_calls", [])
        first_response = pending_action.get("response", "")

        messages = self._build_tool_messages(task)
        tool_results = self._execute_tool_calls(tool_calls)
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
            security_kw = ["security", "vulnerability", "auth", "token", "jwt", "injection", "xss", "csrf"]
            arch_kw = ["migration", "architecture", "scaling", "refactor", "database"]
            incident_kw = ["incident", "outage", "breach", "attack", "production down"]

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
