#!/usr/bin/env python3
"""
Director Adapter - интерфейс для OpenAI Director
Реализует гибридную архитектуру: локальные workers + облачный director
"""

import os
import json
import time
import math
import re
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import openai
from openai import OpenAI
from agent_system.circuit_breaker import CircuitBreaker
from agent_system.decision_log import append_decision_event


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"


@dataclass
class DirectorRequest:
    """Строгий контракт входа для Director"""
    problem_summary: str  # 5-10 строк
    facts: List[str]
    agent_summaries: Dict[str, str]
    risk_level: RiskLevel
    confidence: float
    override_context: Optional[Dict[str, Any]] = None
    
    def validate(self) -> bool:
        """Валидация контракта"""
        if len(self.problem_summary) > 500:
            return False
        if self.confidence < 0 or self.confidence > 1:
            return False
        if len(self.facts) > 10:
            return False
        return True


@dataclass
class DirectorResponse:
    """Ответ от Director"""
    decision: str
    risks: List[str]
    recommendations: List[str]
    next_step: str
    confidence: float
    reasoning: str


_director_circuit_breaker: Optional[CircuitBreaker] = None


def _get_director_circuit_breaker() -> CircuitBreaker:
    global _director_circuit_breaker
    if _director_circuit_breaker is None:
        _director_circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
            success_threshold=1
        )
    return _director_circuit_breaker


class DirectorAdapter:
    """Адаптер для работы с OpenAI Director"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("DIRECTOR_LLM_URL")
        self.allow_fallback = os.getenv("DIRECTOR_ENABLED", "true").lower() == "false"
        self.enabled = bool(self.api_key) and not self.allow_fallback
        self.client = None
        if self.enabled:
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            self.client = OpenAI(**client_kwargs)
        self.model = os.getenv("DIRECTOR_MODEL", "gpt-5.2")
        self.metrics = {
            'calls_today': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'last_reset': time.strftime('%Y-%m-%d')
        }
        
        # Жёсткие триггеры для Director
        self.hard_triggers = {
            'security', 'auth', 'token', 'vuln', 'breach',
            'architecture', 'migration', 'scaling', 'payment',
            'pii', 'compliance', 'database', 'infrastructure'
        }
        self._circuit_breaker = _get_director_circuit_breaker()
    
    def should_use_director(self, task: str, confidence: float, 
                          active_domains: List[str]) -> bool:
        """Определяет нужен ли Director"""
        
        # Жёсткие триггеры
        task_lower = task.lower()
        if any(trigger in task_lower for trigger in self.hard_triggers):
            return True
        
        # Мягкие триггеры
        if confidence < 0.7:
            return True
        
        if len(active_domains) >= 3:
            return True
        
        return False
    
    def sanitize_for_openai(self, data: str) -> str:
        """Очистка данных перед отправкой в OpenAI"""
        
        # Удаляем токены и ключи
        patterns = [
            r'api[_-]?key["\s]*[:=]["\s]*[a-zA-Z0-9_-]+',
            r'token["\s]*[:=]["\s]*[a-zA-Z0-9_.-]+',
            r'password["\s]*[:=]["\s]*[^\s"]+',
            r'secret["\s]*[:=]["\s]*[^\s"]+',
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # emails
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        ]
        
        for pattern in patterns:
            data = re.sub(pattern, '[REDACTED]', data, flags=re.IGNORECASE)
        
        return data

    def _load_recent_insights(self) -> str:
        """Load recent insights from decision summary if available."""
        repo_root = Path(__file__).resolve().parents[1]
        summary_path = repo_root / "data" / "reports" / "decision_summary.json"
        script_path = repo_root / "tools" / "decision_insights.py"
        if not summary_path.exists() or not script_path.exists():
            return ""
        try:
            result = subprocess.run(
                [sys.executable, str(script_path), "--in", str(summary_path), "--lang", "en"],
                capture_output=True,
                text=True,
                cwd=str(repo_root),
                timeout=10,
            )
        except Exception:
            return ""
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def _compute_decision_score(self, confidence: Any, risk_level: RiskLevel, next_step: Any) -> float:
        score = 1.0
        if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
            if confidence < 0.6:
                score -= 0.3
        if risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}:
            score -= 0.2
        if isinstance(next_step, str):
            lowered = next_step.lower()
            if "expand smoke" in lowered or "expand ci" in lowered:
                score += 0.1
        return max(0.0, min(1.0, score))
    
    def create_director_prompt(self, request: DirectorRequest) -> str:
        """Создание промпта для Director"""
        
        summary_with_hint = f"{request.problem_summary}\nContext hint: decision_class=process"
        prompt = f"""You are the Director of a multi-agent AI system. Your role is to make final decisions based on agent summaries.

TASK SUMMARY:
{summary_with_hint}

FACTS:
{chr(10).join(f"- {fact}" for fact in request.facts)}

AGENT SUMMARIES:
{chr(10).join(f"{domain}: {summary}" for domain, summary in request.agent_summaries.items())}

RISK LEVEL: {request.risk_level.value}
CONFIDENCE: {request.confidence:.2f}

Please provide your decision in this EXACT JSON format:
{{
  "decision": "Clear, actionable decision (max 200 chars)",
  "risks": ["Risk 1", "Risk 2"],
  "recommendations": ["Rec 1", "Rec 2", "Rec 3"],
  "next_step": "One specific next action (max 100 chars)",
  "confidence": 0.85,
  "reasoning": "Brief explanation of decision logic",
  "decision_class": "infra|security|product|process|unknown"
}}

Focus on:
1. Architecture and security implications
2. Risk mitigation
3. One clear next step
4. Practical recommendations"""

        insights = self._load_recent_insights() or "(no insights available)"
        if len(insights) > 1200:
            insights = insights[:1200] + "\n...(truncated)"
        guardrails = (
            "## Guardrails\n"
            "If insights mention low confidence or 0.0-0.2 bucket, you MUST set "
            "risk_level>=medium and include expanding smoke/CI in next_step."
        )
        prompt = prompt.replace(
            "\n\nAGENT SUMMARIES:\n",
            f"\n\n## Recent Insights\n{insights}\n\n{guardrails}\n\n"
            "You MUST assign decision_class.\n\n"
            "Choose exactly one:\n"
            "- infra: architecture, CI/CD, runtime, performance, scalability\n"
            "- security: auth, permissions, secrets, data exposure, threat mitigation\n"
            "- product: user-facing behavior, UX, features, business logic\n"
            "- process: workflows, reviews, policies, team/process decisions\n\n"
            "Use \"unknown\" ONLY if none clearly apply.\n\nAGENT SUMMARIES:\n",
        )

        return prompt

    def healthcheck(self) -> bool:
        """Check Director availability with a short ping."""
        if not self.enabled or self.client is None:
            if self.allow_fallback:
                return False
            raise RuntimeError("Director disabled: OPENAI_API_KEY is not set")

        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_completion_tokens=16,
            )
            return True
        except Exception:
            if self.allow_fallback:
                return False
            raise
    
    def call_director(self, request: DirectorRequest) -> DirectorResponse:
        """Вызов OpenAI Director"""
        def _fallback_response(reason: str) -> DirectorResponse:
            return DirectorResponse(
                decision="OpenAI Director unavailable - proceed with local decision",
                risks=["Director service unavailable", "Decision made locally"],
                recommendations=["Manual review recommended", "Retry Director call later"],
                next_step="Proceed with caution using local agents",
                confidence=0.3,
                reasoning=reason
            )

        if not self.enabled or self.client is None:
            if self.allow_fallback:
                return _fallback_response("Director disabled via DIRECTOR_ENABLED=false")
            raise RuntimeError("Director disabled: OPENAI_API_KEY is not set")
        
        if not request.validate():
            raise ValueError("Invalid DirectorRequest")

        if not self._circuit_breaker.can_execute():
            if self.allow_fallback:
                return _fallback_response("Director circuit OPEN")
            raise RuntimeError("Director circuit OPEN")
        
        # Обновляем метрики
        today = time.strftime('%Y-%m-%d')
        if self.metrics['last_reset'] != today:
            self.metrics['calls_today'] = 0
            self.metrics['last_reset'] = today
        
        self.metrics['calls_today'] += 1
        
        # Создаём промпт
        prompt = self.create_director_prompt(request)
        sanitized_prompt = self.sanitize_for_openai(prompt)
        
        messages = [
            {"role": "system", "content": "You are an expert AI Director making architectural decisions."},
            {"role": "user", "content": sanitized_prompt},
        ]
        max_completion_tokens = 600
        cost_policy = "OFF"
        cost_mode = os.getenv("COST_MODE")
        cost_p95_tokens = (
            self._get_tokens_p95()
            if request.risk_level == RiskLevel.LOW
            else None
        )
        if (
            not cost_mode
            and os.getenv("COST_AUTOLINK") == "1"
            and request.risk_level == RiskLevel.LOW
        ):
            if cost_p95_tokens is not None and cost_p95_tokens > 2500:
                cost_mode = "ECONOMY"
                cost_policy = "ECONOMY_AUTO"
        messages[-1]["content"] = messages[-1]["content"][:12000]
        latency_policy = "OFF"
        latency_mode = os.getenv("LATENCY_MODE")
        latency_p95_ms = (
            self._get_latency_p95()
            if request.risk_level == RiskLevel.LOW
            else None
        )
        if (
            not latency_mode
            and os.getenv("LATENCY_AUTOLINK") == "1"
            and request.risk_level == RiskLevel.LOW
        ):
            if latency_p95_ms is not None and latency_p95_ms > 6000:
                latency_mode = "CONSERVATIVE"
                latency_policy = "CONSERVATIVE_AUTO"
        if (
            latency_mode == "CONSERVATIVE"
            and request.risk_level == RiskLevel.LOW
        ):
            max_completion_tokens = max_completion_tokens // 2
            if latency_policy == "OFF":
                latency_policy = "CONSERVATIVE"
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": (
                        "You are in LATENCY_CONSERVATIVE mode. Be concise. "
                        "Output only: (1) decision, (2) next_step. No extra explanation."
                    ),
                },
            )
        if (
            cost_mode == "ECONOMY"
            and request.risk_level == RiskLevel.LOW
        ):
            max_completion_tokens = max_completion_tokens // 2
            messages[-1]["content"] = messages[-1]["content"][:6000]
            if cost_policy == "OFF":
                cost_policy = "ECONOMY"

        try:
            t0 = time.perf_counter()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                max_completion_tokens=max_completion_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "director_decision",
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "decision": {"type": "string"},
                                "risks": {"type": "array", "items": {"type": "string"}},
                                "recommendations": {"type": "array", "items": {"type": "string"}},
                                "next_step": {"type": "string"},
                                "confidence": {"type": "number"},
                                "reasoning": {"type": "string"},
                                "decision_class": {
                                    "type": "string",
                                    "enum": ["infra", "security", "product", "process", "unknown"]
                                }
                            },
                            "required": [
                                "decision",
                                "risks",
                                "recommendations",
                                "next_step",
                                "confidence",
                                "reasoning",
                                "decision_class"
                            ]
                        }
                    }
                }
            )
            latency_ms = int((time.perf_counter() - t0) * 1000)
            
            # Обновляем метрики
            usage = response.usage
            self.metrics['total_tokens'] += usage.total_tokens
            
            cost = (usage.prompt_tokens * 0.00015 + usage.completion_tokens * 0.0006) / 1000
            self.metrics['total_cost'] += cost
            
            # Парсим ответ
            result = json.loads(response.choices[0].message.content)

            self._circuit_breaker.record_success()
            risk_multiplier = 1.0
            if request.risk_level == RiskLevel.MEDIUM:
                risk_multiplier = 0.9
            elif request.risk_level == RiskLevel.HIGH:
                risk_multiplier = 0.8
            elif str(request.risk_level).lower() == "critical":
                risk_multiplier = 0.7
            decision = result["decision"]
            next_step = result["next_step"]
            confidence = result["confidence"]
            mit_text = f"{decision} {next_step}".lower()
            mitigation_keywords = [
                "smoke",
                "ci",
                "coverage",
                "test",
                "tests",
                "auth",
                "secrets",
                "gate",
                "gates",
                "rerun",
                "pr",
            ]
            has_mitigation = any(kw in mit_text for kw in mitigation_keywords)
            if has_mitigation:
                confidence = min(1.0, (confidence or 0.0) + 0.05)
            override_signal_weight = 0.0
            if request.override_context and request.override_context.get("override_kind") == "noise":
                override_signal_weight = 0.0
            uncertainty = "high" if (request.override_context and request.override_context.get("present")) else "unknown"
            if uncertainty == "high":
                confidence = max(0.0, confidence - 0.15)
            score = confidence * risk_multiplier
            append_decision_event({
                "type": "director_decision",
                "agent": "director",
                "decision": decision,
                "confidence": confidence,
                "score": score,
                "latency_ms": latency_ms,
                "latency_policy": latency_policy,
                "latency_p95_ms": latency_p95_ms,
                "cost_policy": cost_policy,
                "cost_p95_tokens": cost_p95_tokens,
                "why_now": "unknown",
                "what_to_fix": "unknown",
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
                "risk_level": request.risk_level.value,
                "decision_class": result["decision_class"],
                "risks": result["risks"],
                "next_step": next_step,
                "override_context": request.override_context,
                "override_signal_weight": override_signal_weight,
                "uncertainty": uncertainty,
            })
            return DirectorResponse(
                decision=result['decision'],
                risks=result['risks'],
                recommendations=result['recommendations'],
                next_step=result['next_step'],
                confidence=result['confidence'],
                reasoning=result['reasoning']
            )
            
        except Exception as e:
            # Fallback при ошибке
            print("DIRECTOR_ERR:", repr(e))
            print("DIRECTOR_INPUT_LEN:", len(messages[-1]["content"]))
            self._circuit_breaker.record_failure(e)
            if self.allow_fallback:
                return _fallback_response(f"Director call failed: {str(e)}")
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить метрики использования"""
        return {
            **self.metrics,
            'cost_per_call': self.metrics['total_cost'] / max(1, self.metrics['calls_today']),
            'avg_tokens_per_call': self.metrics['total_tokens'] / max(1, self.metrics['calls_today'])
        }
    
    def _get_tokens_p95(self, limit: int = 20) -> Optional[int]:
        log_path = Path("data/decision_events.log")
        if not log_path.exists():
            return None
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        tokens = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "director_decision":
                continue
            if event.get("synthetic") is True:
                continue
            total_tokens = event.get("total_tokens")
            if not isinstance(total_tokens, (int, float)) or total_tokens <= 0:
                continue
            tokens.append(int(total_tokens))
        if not tokens:
            return None
        window = tokens[-limit:]
        window.sort()
        idx = max(0, math.ceil(0.95 * len(window)) - 1)
        return window[idx]

    def _get_latency_p95(self, limit: int = 20) -> Optional[int]:
        log_path = Path("data/decision_events.log")
        if not log_path.exists():
            return None
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        latencies = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "director_decision":
                continue
            if event.get("synthetic") is True:
                continue
            latency = event.get("latency_ms")
            if not isinstance(latency, (int, float)) or latency <= 0:
                continue
            latencies.append(int(latency))
        if not latencies:
            return None
        window = latencies[-limit:]
        window.sort()
        idx = max(0, math.ceil(0.95 * len(window)) - 1)
        return window[idx]

    def reset_daily_metrics(self):
        """Сброс дневных метрик"""
        self.metrics['calls_today'] = 0
        self.metrics['last_reset'] = time.strftime('%Y-%m-%d')


# Пример использования
def example_usage():
    """Пример использования Director Adapter"""
    
    adapter = DirectorAdapter()
    
    # Создаём запрос
    request = DirectorRequest(
        problem_summary="Need to implement user authentication with JWT tokens for the agent system API",
        facts=[
            "Current system has no authentication",
            "Multiple agents access sensitive operations", 
            "API endpoints are currently open",
            "Security audit identified this as high risk"
        ],
        agent_summaries={
            "security": "Recommends JWT with refresh tokens, rate limiting, and audit logging",
            "dev": "Suggests FastAPI dependency injection for auth middleware",
            "architect": "Proposes centralized auth service with role-based access"
        },
        risk_level=RiskLevel.HIGH,
        confidence=0.65
    )
    
    # Проверяем нужен ли Director
    if adapter.should_use_director("authentication security", 0.65, ["security", "dev", "architect"]):
        response = adapter.call_director(request)
        print(f"Director Decision: {response.decision}")
        print(f"Next Step: {response.next_step}")
        print(f"Confidence: {response.confidence}")
    
    # Метрики
    metrics = adapter.get_metrics()
    print(f"Calls today: {metrics['calls_today']}")
    print(f"Total cost: ${metrics['total_cost']:.4f}")


if __name__ == "__main__":
    example_usage()



