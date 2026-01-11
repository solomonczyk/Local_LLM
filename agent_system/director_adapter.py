#!/usr/bin/env python3
"""
Director Adapter - интерфейс для OpenAI Director
Реализует гибридную архитектуру: локальные workers + облачный director
"""

import os
import json
import time
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import openai
from openai import OpenAI


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


class DirectorAdapter:
    """Адаптер для работы с OpenAI Director"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("DIRECTOR_LLM_URL")
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
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
    
    def create_director_prompt(self, request: DirectorRequest) -> str:
        """Создание промпта для Director"""
        
        prompt = f"""You are the Director of a multi-agent AI system. Your role is to make final decisions based on agent summaries.

TASK SUMMARY:
{request.problem_summary}

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
  "reasoning": "Brief explanation of decision logic"
}}

Focus on:
1. Architecture and security implications
2. Risk mitigation
3. One clear next step
4. Practical recommendations"""

        return prompt
    
    def call_director(self, request: DirectorRequest) -> DirectorResponse:
        """Вызов OpenAI Director"""
        
        if not request.validate():
            raise ValueError("Invalid DirectorRequest")
        
        # Обновляем метрики
        today = time.strftime('%Y-%m-%d')
        if self.metrics['last_reset'] != today:
            self.metrics['calls_today'] = 0
            self.metrics['last_reset'] = today
        
        self.metrics['calls_today'] += 1
        
        # Создаём промпт
        prompt = self.create_director_prompt(request)
        sanitized_prompt = self.sanitize_for_openai(prompt)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert AI Director making architectural decisions."},
                    {"role": "user", "content": sanitized_prompt}
                ],
                temperature=0.2,
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            
            # Обновляем метрики
            usage = response.usage
            self.metrics['total_tokens'] += usage.total_tokens
            
            cost = (usage.prompt_tokens * 0.00015 + usage.completion_tokens * 0.0006) / 1000
            self.metrics['total_cost'] += cost
            
            # Парсим ответ
            result = json.loads(response.choices[0].message.content)
            
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
            return DirectorResponse(
                decision="OpenAI Director unavailable - proceed with local decision",
                risks=["Director service unavailable", "Decision made locally"],
                recommendations=["Manual review recommended", "Retry Director call later"],
                next_step="Proceed with caution using local agents",
                confidence=0.3,
                reasoning=f"Director call failed: {str(e)}"
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить метрики использования"""
        return {
            **self.metrics,
            'cost_per_call': self.metrics['total_cost'] / max(1, self.metrics['calls_today']),
            'avg_tokens_per_call': self.metrics['total_tokens'] / max(1, self.metrics['calls_today'])
        }
    
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
