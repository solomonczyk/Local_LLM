"""
Базовый агент с доступом к LLM и tools
"""
import requests
import time
from typing import Dict, Any, List, Optional
from collections import deque


class Agent:
    """Базовый агент для работы с LLM и tools"""
    
    # Размер окна для скользящего среднего
    TIMING_WINDOW = 20
    
    def __init__(
        self,
        name: str,
        role: str,
        llm_url: str = "http://localhost:8000/v1",
        tool_url: str = "http://localhost:8001"
    ):
        self.name = name
        self.role = role
        self.llm_url = llm_url
        self.tool_url = tool_url
        self.conversation_history: List[Dict[str, str]] = []
        self.repo_snapshot = None
        
        # Timing metrics (скользящее окно)
        self._llm_times: deque = deque(maxlen=self.TIMING_WINDOW)
        self._retrieval_times: deque = deque(maxlen=self.TIMING_WINDOW)
        self._llm_call_count = 0
        self._retrieval_call_count = 0
    
    def _call_llm(self, messages: List[Dict[str, str]], max_tokens: int = 512) -> str:
        """Internal LLM call with timing"""
        start = time.perf_counter()
        try:
            response = requests.post(
                f"{self.llm_url}/chat/completions",
                json={
                    "model": "qwen2.5-coder-lora",
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.7
                },
                timeout=180
            )
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"]
            
            # Track timing
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._llm_times.append(elapsed_ms)
            self._llm_call_count += 1
            
            return result
        except Exception as e:
            return f"Error calling LLM: {e}"
    
    def call_llm(self, messages: List[Dict[str, str]], max_tokens: int = 512) -> str:
        """Вызов LLM (публичный метод для обратной совместимости)"""
        return self._call_llm(messages, max_tokens)
    
    def read_file(self, path: str) -> Dict[str, Any]:
        """Чтение файла через tool server"""
        try:
            response = requests.post(
                f"{self.tool_url}/tools/read_file",
                json={"path": path},
                timeout=10
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
                timeout=10
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
        
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Task: {task}"}
        ]
        
        response = self._call_llm(messages, max_tokens=max_tokens)
        
        # Parse response with robust fallbacks
        needs_consilium = False
        reason = "No reason provided"
        suggested_agents = []
        answer = response.strip()
        
        # Extract NEEDS_CONSILIUM
        match = re.search(r'NEEDS_CONSILIUM:\s*(yes|no)', response, re.IGNORECASE)
        if match:
            needs_consilium = match.group(1).lower() == 'yes'
        else:
            # Fallback: keyword detection
            lower_resp = response.lower()
            security_kw = ['security', 'vulnerability', 'auth', 'token', 'jwt', 'injection', 'xss', 'csrf']
            arch_kw = ['migration', 'architecture', 'scaling', 'refactor', 'database']
            incident_kw = ['incident', 'outage', 'breach', 'attack', 'production down']
            
            if any(kw in lower_resp for kw in security_kw + arch_kw + incident_kw):
                needs_consilium = True
                reason = "Detected security/architecture/incident keywords"
        
        # Extract REASON
        match = re.search(r'REASON:\s*(.+?)(?:\n|$)', response, re.IGNORECASE)
        if match:
            reason = match.group(1).strip()
        
        # Extract SUGGESTED_AGENTS
        match = re.search(r'SUGGESTED_AGENTS:\s*(.+?)(?:\n|$)', response, re.IGNORECASE)
        if match:
            agents_str = match.group(1).strip()
            if agents_str and agents_str.lower() not in ['none', 'empty', '-', 'n/a']:
                suggested_agents = [a.strip() for a in agents_str.split(',') if a.strip()]
        
        # Extract ANSWER
        match = re.search(r'ANSWER:\s*(.+?)(?:\nNEEDS_CONSILIUM|$)', response, re.IGNORECASE | re.DOTALL)
        if match:
            answer = match.group(1).strip()
        
        return {
            "response": answer,
            "needs_consilium": needs_consilium,
            "reason": reason,
            "suggested_agents": suggested_agents,
            "raw_response": response
        }
    
    def think(self, task: str) -> str:
        """
        Optimized thinking loop:
        - Inject repo snapshot if available
        - Only do 2-pass if READ_FILE is really needed
        """
        import re
        
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
            retrieval_start = time.perf_counter()
            try:
                r = requests.post(
                    f"{self.tool_url}/tools/list_dir",
                    json={"path": "."},
                    timeout=10,
                )
                r.raise_for_status()
                items = r.json().get("items", [])
                lines = []
                for it in items:
                    prefix = "[DIR]" if it["type"] == "dir" else "[FILE]"
                    lines.append(f"{prefix} {it['name']}")
                self.repo_snapshot = "\n".join(lines)
            except Exception as e:
                self.repo_snapshot = f"[ERROR loading repo snapshot: {e}]"
            
            # Track retrieval timing
            elapsed_ms = (time.perf_counter() - retrieval_start) * 1000
            self._retrieval_times.append(elapsed_ms)
            self._retrieval_call_count += 1
        
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
        avg_retrieval_ms = round(sum(self._retrieval_times) / len(self._retrieval_times), 1) if self._retrieval_times else 0
        
        return {
            "avg_llm_ms": avg_llm_ms,
            "avg_retrieval_ms": avg_retrieval_ms,
            "llm_calls": self._llm_call_count,
            "retrieval_calls": self._retrieval_call_count,
            "window_size": self.TIMING_WINDOW,
            "llm_samples": len(self._llm_times),
            "retrieval_samples": len(self._retrieval_times)
        }
