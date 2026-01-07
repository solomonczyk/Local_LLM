"""
Мультиагентный консилиум - несколько специализированных агентов голосуют
"""
from __future__ import annotations

import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from .agent import Agent
from .kb_manager import KnowledgeBaseManager
from .smart_routing import route_agents

# Добавляем путь для импорта agent_system
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from agent_system.config import AgentConfig
from agent_system.shadow_director import shadow_director

class Consilium:
    """Консилиум специализированных агентов"""

    def __init__(self, llm_url: str = "http://localhost:8010/v1", tool_url: str = "http://localhost:8011"):
        self.llm_url = llm_url
        self.tool_url = tool_url

        # Режим консилиума из конфига
        self.mode = AgentConfig.CONSILIUM_MODE
        self.active_agents = AgentConfig.get_consilium_agents()

        # KB retrieval лимиты
        self.kb_top_k = AgentConfig.KB_TOP_K
        self.kb_max_chars = AgentConfig.KB_MAX_CHARS

        print(f"[*] CONSILIUM_MODE: {self.mode}")
        print(f"[*] Active agents: {self.active_agents}")
        print(f"[*] KB limits: top_k={self.kb_top_k}, max_chars={self.kb_max_chars}")

        # Инициализируем KB manager
        self.kb_manager = KnowledgeBaseManager(
            kb_top_k=self.kb_top_k, kb_max_chars=self.kb_max_chars, cache_size=AgentConfig.KB_CACHE_SIZE
        )

        # Инициализируем специализированных агентов
        self.agents: Dict[str, Agent] = {
            "director": Agent(
                name="Director",
                role="Project Director - decides strategy and priorities",
                llm_url=llm_url,
                tool_url=tool_url,
            ),
            "architect": Agent(
                name="Architect",
                role="Software Architect - evaluates structure and scalability",
                llm_url=llm_url,
                tool_url=tool_url,
            ),
            "security": Agent(
                name="Security",
                role="Security Specialist - identifies risks and vulnerabilities",
                llm_url=llm_url,
                tool_url=tool_url,
            ),
            "qa": Agent(
                name="QA",
                role="QA Engineer - checks for edge cases and test coverage",
                llm_url=llm_url,
                tool_url=tool_url,
            ),
            "dev": Agent(name="Dev", role="Developer - implements solutions", llm_url=llm_url, tool_url=tool_url),
            "seo": Agent(
                name="SEO Expert",
                role="SEO Specialist - optimizes for search engines and discoverability",
                llm_url=llm_url,
                tool_url=tool_url,
            ),
            "ux": Agent(
                name="UX/UI Expert",
                role="UX/UI Designer - ensures user experience and interface quality",
                llm_url=llm_url,
                tool_url=tool_url,
            ),
        }

    def check_llm_health(self, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Проверить доступность LLM сервера перед запуском агентов.
        Использует первого доступного агента для проверки.
        """
        if self.agents:
            first_agent = list(self.agents.values())[0]
            return first_agent.check_llm_health(timeout)
        return {"healthy": False, "status": "no_agents", "error": "No agents available"}

    def consult(self, task: str, use_smart_routing: bool = True, check_health: bool = True) -> Dict[str, Any]:
        """
        Получить мнения агентов по задаче (параллельно)

        Параметры:
        - task: задача для анализа
        - use_smart_routing: использовать ли умный роутинг (по умолчанию True)
          Если False, используется статичный список из CONSILIUM_MODE
        - check_health: проверять ли доступность LLM перед запуском (по умолчанию True)

        Возвращает:
        - opinions: мнения каждого агента
        - director_decision: решение директора (только в CRITICAL)
        - recommendation: финальная рекомендация
        - routing: информация о роутинге (если use_smart_routing=True)
        - health_check: результат проверки здоровья (если check_health=True)
        """
        start_time = time.time()
        opinions = {}
        kb_stats_all = {}
        routing_info = None
        health_result = None

        # Health check перед запуском
        if check_health:
            health_result = self.check_llm_health(timeout=5.0)
            if not health_result["healthy"]:
                print(f"[HEALTH] LLM health check FAILED: {health_result.get('error', 'unknown')}")
                return {
                    "success": False,
                    "error": "LLM service unavailable",
                    "health_check": health_result,
                    "task": task,
                }
            print(f"[HEALTH] LLM healthy, response_time={health_result.get('response_time_ms', 0)}ms")

        # Smart routing: выбираем агентов по содержимому задачи
        if use_smart_routing:
            routing_info = route_agents(task)
            agent_names = [name for name in routing_info["agents"] if name != "director" and name in self.agents]
            effective_mode = routing_info["mode"]
            include_director = "director" in routing_info["agents"]

            print(f"[ROUTING] Smart routing: {routing_info['mode']}")
            print(f"[ROUTING] Confidence: {routing_info['confidence']}, Domains: {routing_info['domains_matched']}")
            if routing_info.get("downgraded"):
                print(f"[ROUTING] DOWNGRADED from CRITICAL to STANDARD (low confidence)")
            print(f"[ROUTING] Selected agents: {routing_info['agents']}")
        else:
            # Fallback на статичный список из конфига
            agent_names = [name for name in self.active_agents if name != "director" and name in self.agents]
            effective_mode = self.mode
            include_director = "director" in self.active_agents
            print(f"[*] Static routing: {self.mode}")

        print(f"[*] Consulting {len(agent_names)} agents: {agent_names}")
        print(f"[*] KB retrieval: top_k={self.kb_top_k}, max_chars={self.kb_max_chars}")

        def _run_agent(agent_name: str):
            """Запустить одного агента"""
            agent = self.agents[agent_name]
            specialized_task = self._specialize_task(task, agent_name)

            # Собираем KB stats
            _, kb_stats = self.kb_manager.retrieve_kb(agent_name, task)

            try:
                opinion = agent.think(specialized_task)
                return agent_name, {
                    "role": agent.role,
                    "opinion": opinion[:500],
                    "confidence": self._extract_confidence(opinion),
                    "kb_stats": kb_stats,
                }
            except Exception as e:
                return agent_name, {
                    "role": agent.role,
                    "opinion": f"Error: {e}",
                    "confidence": 0,
                    "kb_stats": kb_stats,
                }

        # Параллельный запуск агентов
        with ThreadPoolExecutor(max_workers=min(len(agent_names), 6)) as executor:
            futures = [executor.submit(_run_agent, name) for name in agent_names]

            for future in as_completed(futures):
                agent_name, opinion_data = future.result()
                kb_stats_all[agent_name] = opinion_data.pop("kb_stats", {})
                opinions[agent_name] = opinion_data

        agents_time = time.time() - start_time

        # Director принимает решение только если включён (smart routing или CRITICAL mode)
        director_decision = None
        director_time = 0

        if include_director:
            director_start = time.time()
            director_prompt = self._build_director_prompt(task, opinions)
            director_decision = self.agents["director"].think(director_prompt)
            director_time = time.time() - director_start

        total_time = time.time() - start_time

        result = {
            "task": task,
            "mode": effective_mode,
            "opinions": opinions,
            "director_decision": director_decision,
            "recommendation": self._build_recommendation(opinions, director_decision),
            "kb_retrieval": {
                "config": {
                    "top_k": self.kb_top_k,
                    "max_chars": self.kb_max_chars,
                    "kb_version_hash": self.kb_manager.kb_version_hash,
                },
                "per_agent": kb_stats_all,
            },
            "timing": {
                "agents_parallel": round(agents_time, 2),
                "director": round(director_time, 2),
                "total": round(total_time, 2),
            },
        }

        # Добавляем routing info если использовался smart routing
        if routing_info:
            result["routing"] = {
                "smart_routing": True,
                "confidence": routing_info["confidence"],
                "domains_matched": routing_info["domains_matched"],
                "triggers_matched": routing_info["triggers_matched"],
                "downgraded": routing_info.get("downgraded", False),
                "reason": routing_info["reason"],
            }
        else:
            result["routing"] = {"smart_routing": False, "static_mode": self.mode}

        # Добавляем health check результат
        if health_result:
            result["health_check"] = health_result

        # 🎯 ACTIVE DIRECTOR - с override gating
        from agent_system.active_director import active_director
        result = active_director.run_active_analysis(result)
        
        if result.get("active_director", {}).get("active_director_used"):
            override_applied = result.get("active_director", {}).get("override_applied", False)
            override_reason = result.get("active_director", {}).get("override_reason", "")
            print(f"[ACTIVE] Director used, override: {override_applied} ({override_reason})")

        return result

    def _specialize_task(self, task: str, agent_name: str) -> str:
        """Адаптировать задачу для конкретного агента с KB (с лимитами)"""

        # Базовые специализации
        specializations = {
            "architect": (
                f"As a Software Architect, analyze this from the perspective of "
                f"system design, scalability, and maintainability:\n\n{task}"
            ),
            "security": (
                f"As a Security Specialist, analyze this for potential security risks, "
                f"vulnerabilities, and best practices:\n\n{task}"
            ),
            "qa": (
                f"As a QA Engineer, analyze this for edge cases, test coverage, "
                f"and potential bugs:\n\n{task}"
            ),
            "dev": f"As a Developer, provide a practical implementation perspective:\n\n{task}",
            "seo": (
                f"As an SEO Expert, analyze this for search engine optimization, "
                f"discoverability, metadata, and content strategy:\n\n{task}"
            ),
            "ux": (
                f"As a UX/UI Designer, analyze this for user experience, interface design, "
                f"accessibility, and usability:\n\n{task}"
            ),
        }

        base_task = specializations.get(agent_name, task)

        # Добавляем KB с лимитами
        kb_content, kb_stats = self.kb_manager.retrieve_kb(agent_name, task)

        if kb_content:
            print(
                f"  [KB] {agent_name}: kb_top_k={kb_stats['chunks_used']}/{kb_stats['total_chunks']}, "
                f"kb_chars={kb_stats['chars_used']}/{self.kb_max_chars}"
            )
            return f"""{base_task}

=== YOUR KNOWLEDGE BASE (top {kb_stats['chunks_used']} chunks, {kb_stats['chars_used']} chars) ===
{kb_content}

Use this knowledge base to inform your analysis."""

        return base_task

    def _extract_confidence(self, opinion: str) -> float:
        """Извлечь уровень уверенности из мнения (0-10)"""
        # Простая эвристика: ищем числа в тексте
        matches = re.findall(r"\b([0-9]|10)\b", opinion)
        if matches:
            try:
                return float(matches[-1]) / 10.0
            except:
                return 0.5
        return 0.5

    def _build_director_prompt(self, task: str, opinions: Dict[str, Any]) -> str:
        """Построить промпт для директора"""

        opinions_text = "\n\n".join([
            f"=== {name.upper()} ({data['role']}) ===\n{data['opinion']}"
            for name, data in opinions.items()
        ])

        return f"""You are the Project Director. You have received opinions from your team:

{opinions_text}

Original task: {task}

Based on these opinions, provide:
1. DECISION: Your strategic decision
2. RATIONALE: Why you chose this approach
3. RISKS: Key risks to monitor
4. NEXT_STEPS: Recommended next actions

Be concise and decisive."""

    def _build_recommendation(self, opinions: Dict[str, Any], decision: Optional[str]) -> str:
        """Построить финальную рекомендацию"""

        avg_confidence = sum(op.get("confidence", 0.5) for op in opinions.values()) / len(opinions) if opinions else 0.5

        decision_summary = decision[:300] if decision else "No director decision (FAST/STANDARD mode)"

        return {
            "confidence_level": avg_confidence,
            "team_consensus": avg_confidence > 0.7,
            "decision_summary": decision_summary,
            "agents_involved": list(opinions.keys()),
        }

    def get_status(self) -> Dict[str, Any]:
        """Статус консилиума с метриками времени"""
        # Собираем timing stats по всем агентам
        all_llm_ms = []
        all_retrieval_ms = []
        per_agent_timing = {}

        for name, agent in self.agents.items():
            stats = agent.get_timing_stats()
            per_agent_timing[name] = stats
            if stats["llm_samples"] > 0:
                all_llm_ms.append(stats["avg_llm_ms"])
            if stats["retrieval_samples"] > 0:
                all_retrieval_ms.append(stats["avg_retrieval_ms"])

        # Глобальные средние
        avg_llm_ms = round(sum(all_llm_ms) / len(all_llm_ms), 1) if all_llm_ms else 0
        avg_retrieval_ms = round(sum(all_retrieval_ms) / len(all_retrieval_ms), 1) if all_retrieval_ms else 0

        # Получаем статистику KB manager
        kb_stats = self.kb_manager.get_cache_stats()

        return {
            "consilium_mode": self.mode,
            "active_agents": self.active_agents,
            # Ключевые метрики времени
            "avg_llm_ms": avg_llm_ms,
            "avg_retrieval_ms": avg_retrieval_ms,
            "timing_per_agent": per_agent_timing,
            "agents": {
                name: {
                    "name": agent.name,
                    "role": agent.role,
                    "active": name in self.active_agents,
                    "repo_snapshot_cached": agent.repo_snapshot is not None,
                }
                for name, agent in self.agents.items()
            },
            "total_agents": len(self.agents),
            "active_count": len(self.active_agents),
            **kb_stats,  # Добавляем статистику KB
        }

# Lazy singleton - создаётся один раз при первом вызове get_consilium()
_consilium_instance: Optional[Consilium] = None

def get_consilium() -> Consilium:
    """Получить singleton экземпляр консилиума (lazy init)"""
    global _consilium_instance
    if _consilium_instance is None:
        _consilium_instance = Consilium()
    return _consilium_instance

# Для обратной совместимости - property-like доступ
# Использовать get_consilium() вместо consilium напрямую
consilium = None  # Будет None до первого вызова get_consilium()