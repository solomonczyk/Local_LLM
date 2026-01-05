"""
Мультиагентный консилиум - несколько специализированных агентов голосуют
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from functools import lru_cache
from .agent import Agent
import json
import os
import sys
import hashlib

# Добавляем путь для импорта agent_system
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from agent_system.config import AgentConfig


class Consilium:
    """Консилиум специализированных агентов"""
    
    def __init__(
        self,
        llm_url: str = "http://localhost:8000/v1",
        tool_url: str = "http://localhost:8001"
    ):
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
        
        # Маппинг агентов к их KB файлам
        self.kb_mapping = {
            "security": "agent_runtime/kb/security_checklist.md",
            "architect": "agent_runtime/kb/architecture_review.md",
            "qa": "agent_runtime/kb/testing_strategy.md",
            "dev": "agent_runtime/kb/development_guide.md",
            "seo": "agent_runtime/kb/seo_guide.md",
            "ux": "agent_runtime/kb/ux_guide.md",
            "director": "agent_runtime/kb/architectural_programming.md",
        }
        
        # Кэш загруженных KB и версия
        self.kb_cache: Dict[str, str] = {}
        self.kb_version_hash: str = ""
        self._load_kb()
        
        # LRU кэш для retrieval результатов
        self._retrieval_cache: Dict[str, Tuple[str, dict]] = {}
        self._retrieval_cache_order: List[str] = []  # Для LRU
        self._retrieval_cache_size = AgentConfig.KB_CACHE_SIZE
        self._cache_hits = 0
        self._cache_misses = 0
        print(f"[*] Retrieval cache: size={self._retrieval_cache_size}")
        
        # Инициализируем специализированных агентов
        self.agents: Dict[str, Agent] = {
            "director": Agent(
                name="Director",
                role="Project Director - decides strategy and priorities",
                llm_url=llm_url,
                tool_url=tool_url
            ),
            "architect": Agent(
                name="Architect",
                role="Software Architect - evaluates structure and scalability",
                llm_url=llm_url,
                tool_url=tool_url
            ),
            "security": Agent(
                name="Security",
                role="Security Specialist - identifies risks and vulnerabilities",
                llm_url=llm_url,
                tool_url=tool_url
            ),
            "qa": Agent(
                name="QA",
                role="QA Engineer - checks for edge cases and test coverage",
                llm_url=llm_url,
                tool_url=tool_url
            ),
            "dev": Agent(
                name="Dev",
                role="Developer - implements solutions",
                llm_url=llm_url,
                tool_url=tool_url
            ),
            "seo": Agent(
                name="SEO Expert",
                role="SEO Specialist - optimizes for search engines and discoverability",
                llm_url=llm_url,
                tool_url=tool_url
            ),
            "ux": Agent(
                name="UX/UI Expert",
                role="UX/UI Designer - ensures user experience and interface quality",
                llm_url=llm_url,
                tool_url=tool_url
            ),
        }
    
    def _load_kb(self):
        """Загрузить KB файлы в кэш (разбитые на чанки с метаданными)"""
        from pathlib import Path
        import hashlib
        
        # Собираем контент для хэширования
        all_content = []
        
        for agent_name, kb_path in self.kb_mapping.items():
            try:
                kb_file = Path(kb_path)
                if kb_file.exists():
                    content = kb_file.read_text(encoding="utf-8")
                    all_content.append(f"{kb_path}:{content}")
                    doc_name = kb_file.name
                    # Разбиваем на чанки по секциям с метаданными
                    self.kb_cache[agent_name] = self._chunk_kb(content, doc_name)
                    total_chars = sum(len(c["content"]) for c in self.kb_cache[agent_name])
                    print(f"[OK] KB loaded for {agent_name}: {len(self.kb_cache[agent_name])} chunks, {total_chars} chars")
                else:
                    print(f"[WARN] KB not found for {agent_name}: {kb_path}")
                    self.kb_cache[agent_name] = []
            except Exception as e:
                print(f"[ERROR] Error loading KB for {agent_name}: {e}")
                self.kb_cache[agent_name] = []
        
        # Вычисляем хэш всех KB файлов (первые 8 символов)
        combined = "\n".join(sorted(all_content))
        self.kb_version_hash = hashlib.sha256(combined.encode()).hexdigest()[:8]
        print(f"[*] KB version: {self.kb_version_hash}")
    
    def _chunk_kb(self, content: str, doc_name: str) -> List[Dict[str, Any]]:
        """Разбить KB на чанки по секциям markdown с метаданными"""
        import re
        
        # Разбиваем по ## заголовкам
        sections = re.split(r'\n(?=##\s)', content)
        chunks = []
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            # Извлекаем заголовок секции
            title_match = re.match(r'^##\s+(.+?)(?:\n|$)', section)
            section_title = title_match.group(1).strip() if title_match else "Introduction"
            
            # Если секция слишком большая, разбиваем по параграфам
            if len(section) > 2000:
                paragraphs = section.split('\n\n')
                current_chunk = ""
                chunk_idx = 0
                for para in paragraphs:
                    if len(current_chunk) + len(para) < 1500:
                        current_chunk += para + "\n\n"
                    else:
                        if current_chunk:
                            chunks.append({
                                "content": current_chunk.strip(),
                                "doc": doc_name,
                                "section": f"{section_title} (part {chunk_idx + 1})"
                            })
                            chunk_idx += 1
                        current_chunk = para + "\n\n"
                if current_chunk:
                    chunks.append({
                        "content": current_chunk.strip(),
                        "doc": doc_name,
                        "section": f"{section_title} (part {chunk_idx + 1})" if chunk_idx > 0 else section_title
                    })
            else:
                chunks.append({
                    "content": section,
                    "doc": doc_name,
                    "section": section_title
                })
        
        # Fallback если ничего не нашли
        if not chunks:
            chunks.append({
                "content": content[:2000],
                "doc": doc_name,
                "section": "Full document"
            })
        
        return chunks
    
    # Балластные секции (максимум 1 в выдаче)
    BALLAST_SECTIONS = {"introduction", "scope", "overview", "about", "preface"}
    
    def _is_ballast_section(self, section_title: str) -> bool:
        """Проверить является ли секция балластной"""
        # Нормализуем: убираем номера, скобки, приводим к lowercase
        import re
        normalized = re.sub(r'^[\d\)\.\-\s]+', '', section_title)  # убираем "0) ", "1. " и т.д.
        normalized = normalized.lower().split("(")[0].strip()
        return normalized in self.BALLAST_SECTIONS
    
    def _normalize_query(self, query: str) -> str:
        """Нормализовать запрос для ключа кэша"""
        # Простая нормализация: lowercase, убираем лишние пробелы
        return " ".join(query.lower().split())
    
    def _get_cache_key(self, agent_name: str, task: str) -> str:
        """Сформировать ключ кэша"""
        normalized = self._normalize_query(task)
        query_hash = hashlib.md5(normalized.encode()).hexdigest()[:8]
        return f"{agent_name}:{query_hash}:{self.kb_version_hash}:{self.kb_top_k}:{self.kb_max_chars}"
    
    def _cache_get(self, key: str) -> Optional[Tuple[str, dict]]:
        """Получить из кэша (LRU)"""
        if key in self._retrieval_cache:
            # Перемещаем в конец (most recently used)
            self._retrieval_cache_order.remove(key)
            self._retrieval_cache_order.append(key)
            self._cache_hits += 1
            return self._retrieval_cache[key]
        self._cache_misses += 1
        return None
    
    def _cache_put(self, key: str, value: Tuple[str, dict]):
        """Положить в кэш (LRU eviction)"""
        if key in self._retrieval_cache:
            self._retrieval_cache_order.remove(key)
        elif len(self._retrieval_cache) >= self._retrieval_cache_size:
            # Удаляем oldest
            oldest = self._retrieval_cache_order.pop(0)
            del self._retrieval_cache[oldest]
        
        self._retrieval_cache[key] = value
        self._retrieval_cache_order.append(key)
    
    def _retrieve_kb(self, agent_name: str, task: str) -> tuple[str, dict]:
        """
        Получить релевантные чанки KB с учётом лимитов и анти-балласт правила.
        Использует LRU кэш для ускорения повторных запросов.
        
        Возвращает (kb_content, stats) где stats включает sources и cache status
        """
        # Проверяем кэш
        cache_key = self._get_cache_key(agent_name, task)
        cached = self._cache_get(cache_key)
        if cached is not None:
            content, stats = cached
            stats = stats.copy()
            stats["kb_cache"] = "HIT"
            print(f"  [CACHE] {agent_name}: kb_cache=HIT")
            return content, stats
        
        # Cache MISS - выполняем retrieval
        if agent_name not in self.kb_cache or not self.kb_cache[agent_name]:
            stats = {"chunks_used": 0, "chars_used": 0, "total_chunks": 0, "sources": [], "kb_cache": "MISS"}
            return "", stats
        
        chunks = self.kb_cache[agent_name]
        
        # Разделяем чанки на балластные и полезные
        ballast_chunks = []
        useful_chunks = []
        
        for chunk in chunks:
            if self._is_ballast_section(chunk["section"]):
                ballast_chunks.append(chunk)
            else:
                useful_chunks.append(chunk)
        
        # Собираем итоговый список: сначала полезные, потом максимум 1 балластный
        prioritized = useful_chunks[:self.kb_top_k]
        
        # Добавляем 1 балластный если есть место и он есть
        if len(prioritized) < self.kb_top_k and ballast_chunks:
            prioritized.append(ballast_chunks[0])
        
        # Теперь применяем лимиты
        selected_content = []
        sources = []
        chars_used = 0
        ballast_used = 0
        
        for chunk in prioritized[:self.kb_top_k]:
            content = chunk["content"]
            is_ballast = self._is_ballast_section(chunk["section"])
            
            if chars_used + len(content) <= self.kb_max_chars:
                selected_content.append(content)
                sources.append({
                    "doc": chunk["doc"], 
                    "section": chunk["section"],
                    "ballast": is_ballast
                })
                chars_used += len(content)
                if is_ballast:
                    ballast_used += 1
            else:
                # Обрезаем последний чанк если нужно
                remaining = self.kb_max_chars - chars_used
                if remaining > 200:
                    selected_content.append(content[:remaining] + "...")
                    sources.append({
                        "doc": chunk["doc"], 
                        "section": chunk["section"] + " (truncated)",
                        "ballast": is_ballast
                    })
                    chars_used += remaining
                break
        
        result_content = "\n\n---\n\n".join(selected_content)
        stats = {
            "chunks_used": len(selected_content),
            "chars_used": chars_used,
            "total_chunks": len(chunks),
            "ballast_used": ballast_used,
            "limit_top_k": self.kb_top_k,
            "limit_max_chars": self.kb_max_chars,
            "sources": sources
        }
        
        # Сохраняем в кэш
        self._cache_put(cache_key, (result_content, stats))
        stats = stats.copy()
        stats["kb_cache"] = "MISS"
        print(f"  [CACHE] {agent_name}: kb_cache=MISS")
        
        return result_content, stats
    
    def consult(self, task: str, use_smart_routing: bool = True) -> Dict[str, Any]:
        """
        Получить мнения агентов по задаче (параллельно)
        
        Параметры:
        - task: задача для анализа
        - use_smart_routing: использовать ли умный роутинг (по умолчанию True)
          Если False, используется статичный список из CONSILIUM_MODE
        
        Возвращает:
        - opinions: мнения каждого агента
        - director_decision: решение директора (только в CRITICAL)
        - recommendation: финальная рекомендация
        - routing: информация о роутинге (если use_smart_routing=True)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        
        start_time = time.time()
        opinions = {}
        kb_stats_all = {}
        routing_info = None
        
        # Smart routing: выбираем агентов по содержимому задачи
        if use_smart_routing:
            routing_info = route_agents(task)
            agent_names = [name for name in routing_info["agents"] 
                         if name != "director" and name in self.agents]
            effective_mode = routing_info["mode"]
            include_director = "director" in routing_info["agents"]
            
            print(f"[ROUTING] Smart routing: {routing_info['mode']}")
            print(f"[ROUTING] Confidence: {routing_info['confidence']}, Domains: {routing_info['domains_matched']}")
            if routing_info.get("downgraded"):
                print(f"[ROUTING] DOWNGRADED from CRITICAL to STANDARD (low confidence)")
            print(f"[ROUTING] Selected agents: {routing_info['agents']}")
        else:
            # Fallback на статичный список из конфига
            agent_names = [name for name in self.active_agents 
                         if name != "director" and name in self.agents]
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
            _, kb_stats = self._retrieve_kb(agent_name, task)
            
            try:
                opinion = agent.think(specialized_task)
                return agent_name, {
                    "role": agent.role,
                    "opinion": opinion[:500],
                    "confidence": self._extract_confidence(opinion),
                    "kb_stats": kb_stats
                }
            except Exception as e:
                return agent_name, {
                    "role": agent.role,
                    "opinion": f"Error: {e}",
                    "confidence": 0,
                    "kb_stats": kb_stats
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
                    "kb_version_hash": self.kb_version_hash
                },
                "per_agent": kb_stats_all
            },
            "timing": {
                "agents_parallel": round(agents_time, 2),
                "director": round(director_time, 2),
                "total": round(total_time, 2)
            }
        }
        
        # Добавляем routing info если использовался smart routing
        if routing_info:
            result["routing"] = {
                "smart_routing": True,
                "confidence": routing_info["confidence"],
                "domains_matched": routing_info["domains_matched"],
                "triggers_matched": routing_info["triggers_matched"],
                "downgraded": routing_info.get("downgraded", False),
                "reason": routing_info["reason"]
            }
        else:
            result["routing"] = {
                "smart_routing": False,
                "static_mode": self.mode
            }
        
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
            "dev": (
                f"As a Developer, provide a practical implementation perspective:\n\n{task}"
            ),
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
        kb_content, kb_stats = self._retrieve_kb(agent_name, task)
        
        if kb_content:
            print(f"  [KB] {agent_name}: kb_top_k={kb_stats['chunks_used']}/{kb_stats['total_chunks']}, "
                  f"kb_chars={kb_stats['chars_used']}/{self.kb_max_chars}")
            return f"""{base_task}

=== YOUR KNOWLEDGE BASE (top {kb_stats['chunks_used']} chunks, {kb_stats['chars_used']} chars) ===
{kb_content}

Use this knowledge base to inform your analysis."""
        
        return base_task
    
    def _extract_confidence(self, opinion: str) -> float:
        """Извлечь уровень уверенности из мнения (0-10)"""
        # Простая эвристика: ищем числа в тексте
        import re
        matches = re.findall(r'\b([0-9]|10)\b', opinion)
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
        
        avg_confidence = sum(
            op.get("confidence", 0.5) for op in opinions.values()
        ) / len(opinions) if opinions else 0.5
        
        decision_summary = decision[:300] if decision else "No director decision (FAST/STANDARD mode)"
        
        return {
            "confidence_level": avg_confidence,
            "team_consensus": avg_confidence > 0.7,
            "decision_summary": decision_summary,
            "agents_involved": list(opinions.keys())
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Статус консилиума с метриками времени"""
        total_cache_requests = self._cache_hits + self._cache_misses
        hit_rate = round(self._cache_hits / total_cache_requests, 2) if total_cache_requests > 0 else 0
        
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
        
        return {
            "consilium_mode": self.mode,
            "active_agents": self.active_agents,
            "kb_version_hash": self.kb_version_hash,
            # Ключевые метрики времени
            "avg_llm_ms": avg_llm_ms,
            "avg_retrieval_ms": avg_retrieval_ms,
            "retrieval_cache": {
                "size": len(self._retrieval_cache),
                "max_size": self._retrieval_cache_size,
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "hit_rate": hit_rate
            },
            "timing_per_agent": per_agent_timing,
            "agents": {
                name: {
                    "name": agent.name,
                    "role": agent.role,
                    "active": name in self.active_agents,
                    "repo_snapshot_cached": agent.repo_snapshot is not None,
                    "kb_loaded": name in self.kb_cache and bool(self.kb_cache[name])
                }
                for name, agent in self.agents.items()
            },
            "total_agents": len(self.agents),
            "active_count": len(self.active_agents),
            "kb_mapping": self.kb_mapping,
            "kb_loaded": {name: bool(kb) for name, kb in self.kb_cache.items()}
        }


# ========== SMART ROUTER ==========
# Триггеры для автоматического выбора режима и агентов

ROUTE_TRIGGERS = {
    # CRITICAL triggers - инциденты, аварии
    "critical": [
        "incident", "outage", "breach", "attack", "compromised",
        "emergency", "critical", "urgent", "production down"
    ],
    # Security triggers
    "security": [
        "security", "auth", "token", "secret", "vuln", "vulnerability",
        "password", "credential", "injection", "xss", "csrf", "encrypt",
        "permission", "access control", "oauth", "jwt"
    ],
    # Architecture triggers
    "architect": [
        "architecture", "migration", "database", "db", "scale", "scaling",
        "performance", "perf", "refactor", "design pattern", "microservice",
        "infrastructure", "deploy", "ci/cd", "load balancer"
    ],
    # QA triggers
    "qa": [
        "test", "qa", "regression", "coverage", "bug", "edge case",
        "unit test", "integration test", "e2e", "mock", "fixture"
    ],
    # SEO triggers
    "seo": [
        "seo", "search engine", "meta tag", "sitemap", "robots.txt",
        "canonical", "structured data", "schema.org", "lighthouse"
    ],
    # UX triggers
    "ux": [
        "ux", "ui", "user experience", "accessibility", "a11y", "wcag",
        "usability", "responsive", "mobile", "design system"
    ]
}

# Сильные триггеры (высокий confidence) vs слабые (низкий confidence)
# Сильные = специфичные термины, слабые = общие слова
STRONG_TRIGGERS = {
    "security": {"vulnerability", "injection", "xss", "csrf", "oauth", "jwt", "credential"},
    "architect": {"architecture", "microservice", "migration", "infrastructure", "ci/cd"},
    "qa": {"regression", "coverage", "integration test", "e2e", "unit test"},
    "seo": {"sitemap", "robots.txt", "schema.org", "canonical", "lighthouse"},
    "ux": {"accessibility", "a11y", "wcag", "design system"}
}

# Слабые триггеры (могут быть ложными срабатываниями)
WEAK_TRIGGERS = {
    "security": {"security", "auth", "token", "secret", "password"},
    "architect": {"database", "db", "scale", "performance", "perf", "refactor", "deploy"},
    "qa": {"test", "qa", "bug", "mock"},
    "seo": {"seo", "meta tag"},
    "ux": {"ux", "ui", "mobile", "responsive"}
}


def _calculate_confidence(
    matched_triggers: Dict[str, List[str]]
) -> Tuple[float, Dict[str, Any]]:
    """
    Рассчитать confidence (0-1) на основе силы триггеров.
    
    Returns:
        (confidence, breakdown) где breakdown содержит вклад каждого домена
    """
    if not matched_triggers:
        return 0.0, {}

    breakdown: Dict[str, Any] = {}
    domain_scores = []

    for domain, triggers in matched_triggers.items():
        if domain == "critical":
            domain_scores.append(1.0)
            breakdown[domain] = {
                "score": 1.0,
                "strong": triggers,
                "weak": [],
                "reason": "CRITICAL trigger always max"
            }
            continue

        strong = STRONG_TRIGGERS.get(domain, set())
        weak = WEAK_TRIGGERS.get(domain, set())

        strong_matched = [t for t in triggers if t in strong]
        weak_matched = [t for t in triggers if t in weak]
        strong_count = len(strong_matched)
        weak_count = len(weak_matched)

        # Базовый score домена
        if strong_count > 0:
            base_score = 0.8 + min(strong_count * 0.1, 0.2)  # 0.8-1.0
            reason = f"{strong_count} strong trigger(s)"
        elif weak_count > 0:
            base_score = 0.4 + min(weak_count * 0.1, 0.2)  # 0.4-0.6
            reason = f"{weak_count} weak trigger(s) only"
        else:
            base_score = 0.5
            reason = "unknown triggers"

        domain_scores.append(base_score)
        breakdown[domain] = {
            "score": round(base_score, 2),
            "strong": strong_matched,
            "weak": weak_matched,
            "reason": reason
        }

    # Итоговый confidence = среднее по доменам
    confidence = round(sum(domain_scores) / len(domain_scores), 2) if domain_scores else 0.0

    # Добавляем итоговую информацию
    breakdown["_summary"] = {
        "total_confidence": confidence,
        "domains_count": len(domain_scores),
        "formula": "avg(domain_scores)"
    }

    return confidence, breakdown


def route_agents(query: str) -> Dict[str, Any]:
    """
    Умный роутер: выбирает режим и агентов по содержимому запроса.
    
    Правила эскалации:
    - CRITICAL triggers (incident/breach/etc) → сразу CRITICAL + все агенты
    - 3+ доменов + confidence >= 0.7 → CRITICAL + director
    - 3+ доменов + confidence < 0.7 → STANDARD (понижение, без director)
    - 2 домена → STANDARD
    - 1 домен или 0 → FAST (только dev)
    
    Returns:
        {
            "mode": "FAST|STANDARD|CRITICAL",
            "agents": ["dev", ...],
            "triggers_matched": {"security": ["token", "auth"], ...},
            "domains_matched": 2,
            "confidence": 0.85,
            "reason": "..."
        }
    """
    query_lower = query.lower()
    matched_triggers: Dict[str, List[str]] = {}
    required_agents = {"dev"}  # dev всегда включён

    # Проверяем CRITICAL триггеры
    for trigger in ROUTE_TRIGGERS["critical"]:
        if trigger in query_lower:
            matched_triggers.setdefault("critical", []).append(trigger)

    # Если CRITICAL trigger - возвращаем сразу все агенты
    if "critical" in matched_triggers:
        _, breakdown = _calculate_confidence(matched_triggers)
        return {
            "mode": "CRITICAL",
            "agents": ["dev", "security", "qa", "architect", "seo", "ux", "director"],
            "triggers_matched": matched_triggers,
            "domains_matched": len(matched_triggers),
            "confidence": 1.0,
            "confidence_breakdown": breakdown,
            "downgraded": False,
            "reason": f"CRITICAL triggers: {matched_triggers['critical']}"
        }

    # Проверяем остальные триггеры (домены)
    for agent_type, triggers in ROUTE_TRIGGERS.items():
        if agent_type == "critical":
            continue
        for trigger in triggers:
            if trigger in query_lower:
                matched_triggers.setdefault(agent_type, []).append(trigger)
                required_agents.add(agent_type)

    # Считаем количество доменов и confidence
    domains_matched = len(required_agents) - 1  # минус dev
    confidence, confidence_breakdown = _calculate_confidence(matched_triggers)

    # Правила эскалации по количеству доменов + confidence
    downgraded = False
    if domains_matched >= 3:
        if confidence >= 0.7:
            # 3+ домена + высокий confidence → CRITICAL + director
            mode = "CRITICAL"
            agents = list(required_agents) + ["director"]
            reason = f"Escalation: {domains_matched} domains, confidence={confidence} → CRITICAL"
        else:
            # 3+ домена + низкий confidence → понижаем до STANDARD
            mode = "STANDARD"
            agents = list(required_agents)
            reason = f"Downgrade: {domains_matched} domains but confidence={confidence} < 0.7 → STANDARD"
            downgraded = True
    elif domains_matched == 2:
        mode = "STANDARD"
        agents = list(required_agents)
        reason = f"Escalation: {domains_matched} domains → STANDARD"
    elif domains_matched == 1:
        mode = "STANDARD"
        agents = list(required_agents)
        reason = f"Single domain matched → STANDARD"
    else:
        mode = "FAST"
        agents = ["dev"]
        confidence = 1.0  # FAST всегда уверен
        confidence_breakdown = {"_summary": {"total_confidence": 1.0, "reason": "FAST mode default"}}
        reason = "No specific triggers, using FAST mode"

    # Добавляем детали триггеров в reason
    if matched_triggers:
        trigger_summary = ", ".join(
            f"{k}: {v[:2]}" for k, v in matched_triggers.items()
        )
        reason = f"{reason} | Matched: {trigger_summary}"

    return {
        "mode": mode,
        "agents": agents,
        "triggers_matched": matched_triggers,
        "domains_matched": domains_matched,
        "confidence": confidence,
        "confidence_breakdown": confidence_breakdown,
        "downgraded": downgraded,
        "reason": reason
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
