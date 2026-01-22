#!/usr/bin/env python3
"""
Shadow Director - тестирование Director в shadow mode
Логирует решения Director без влияния на основной результат
"""

import json
import os
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .director_adapter import DirectorAdapter, DirectorRequest, RiskLevel


class ShadowDirector:
    """Shadow режим для безопасного тестирования Director"""
    
    def __init__(self, enabled: bool = None):
        self.enabled = enabled if enabled is not None else os.getenv("SHADOW_DIRECTOR_ENABLED", "false").lower() == "true"
        self.director_adapter = DirectorAdapter() if self.enabled else None
        self.log_file = "shadow_director.jsonl"
        
        if self.enabled:
            print(f"[SHADOW] Director enabled, logging to {self.log_file}")
        else:
            print("[SHADOW] Director disabled")
    
    def create_summary_from_consilium_result(self, result: Dict[str, Any]) -> Optional[DirectorRequest]:
        """
        Создаёт Decision Capsule для Director из результата consilium
        
        ЖЁСТКИЕ ЛИМИТЫ (Decision Capsule Contract):
        - problem_summary: ≤400 tokens (~300 chars)
        - facts: ≤8 bullets
        - agent_summaries: security ≤120 tokens, остальные ≤80 tokens
        - НИКАКОГО кода, только ссылки/идентификаторы
        """
        
        if not self.enabled:
            return None
        
        try:
            # Извлекаем основную информацию
            task = result.get("task", "")
            opinions = result.get("opinions", {})
            routing = result.get("routing", {})
            
            # Определяем risk level
            confidence = routing.get("confidence", 1.0)
            domains_count = routing.get("domains_matched", 0)
            
            if confidence < 0.5 or "security" in opinions or "critical" in task.lower():
                risk_level = RiskLevel.HIGH
            elif confidence < 0.7 or domains_count >= 3:
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW
            
            # === DECISION CAPSULE: Ужатые саммари агентов ===
            agent_summaries = {}
            for agent, data in opinions.items():
                opinion = data.get("opinion", "")
                
                # Лимиты: security=120 chars, остальные=80 chars
                char_limit = 120 if agent == "security" else 80
                
                # Извлекаем только ключевую рекомендацию (без кода!)
                summary = self._extract_key_recommendation(opinion, char_limit)
                agent_summaries[agent] = summary
            
            # === DECISION CAPSULE: Краткое описание проблемы (≤300 chars) ===
            problem_summary = self._create_compact_problem_summary(task, routing)
            
            # === DECISION CAPSULE: Факты (≤8 bullets) ===
            facts = self._create_compact_facts(routing, opinions, result)
            
            # === OVERRIDE CONTEXT: Обогащение сигнала ===
            override_context = {
                "present": True,
                "source": "human",
                "reason": "temporal_hard_gate_bypassed",
                "temporal_state": "HARD",
                "escalation_window_hours": 72,
                "override_decision": "allow",
                "override_kind": "noise"
            }
            
            return DirectorRequest(
                problem_summary=problem_summary,
                facts=facts[:8],  # Жёсткий лимит: 8 фактов
                agent_summaries=agent_summaries,
                risk_level=risk_level,
                confidence=confidence,
                override_context=override_context
            )
            
        except Exception as e:
            print(f"[SHADOW] Error creating summary: {e}")
            return None
    
    def _extract_key_recommendation(self, opinion: str, char_limit: int) -> str:
        """Извлекает ключевую рекомендацию без кода"""
        
        # Удаляем код и технические детали
        clean_opinion = opinion
        
        # Удаляем блоки кода
        import re
        clean_opinion = re.sub(r'```[\s\S]*?```', '[code]', clean_opinion)
        clean_opinion = re.sub(r'`[^`]+`', '[ref]', clean_opinion)
        
        # Удаляем пути файлов и технические идентификаторы
        clean_opinion = re.sub(r'[/\\][\w/\\.-]+\.\w+', '[file]', clean_opinion)
        
        # Ищем ключевые фразы рекомендаций
        recommendation_markers = ['recommend', 'suggest', 'should', 'must', 'need to', 'important']
        
        sentences = clean_opinion.replace('\n', ' ').split('.')
        key_sentence = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if any(marker in sentence.lower() for marker in recommendation_markers):
                key_sentence = sentence
                break
        
        if not key_sentence and sentences:
            key_sentence = sentences[0]
        
        # Обрезаем до лимита
        result = key_sentence.strip()[:char_limit]
        if len(key_sentence) > char_limit:
            result = result.rsplit(' ', 1)[0] + "..."
        
        return result if result else "No specific recommendation"
    
    def _create_compact_problem_summary(self, task: str, routing: dict) -> str:
        """Создаёт компактное описание проблемы (≤300 chars)"""
        
        # Базовое описание задачи
        task_short = task[:150]
        if len(task) > 150:
            task_short = task_short.rsplit(' ', 1)[0] + "..."
        
        # Добавляем контекст роутинга
        confidence = routing.get("confidence", 0)
        domains = routing.get("domains_matched", 0)
        
        summary = f"Task: {task_short}"
        
        # Добавляем критичную информацию если есть место
        if len(summary) < 250:
            summary += f" [conf:{confidence:.2f}, domains:{domains}]"
        
        return summary[:300]
    
    def _create_compact_facts(self, routing: dict, opinions: dict, result: dict) -> list:
        """Создаёт компактный список фактов (≤8 items)"""
        
        facts = []
        
        # Факт 1: Confidence и routing
        confidence = routing.get("confidence", 0)
        facts.append(f"Confidence: {confidence:.2f}")
        
        # Факт 2: Количество агентов
        facts.append(f"Agents: {len(opinions)}")
        
        # Факт 3: Домены
        domains = list(opinions.keys())
        facts.append(f"Domains: {', '.join(domains[:4])}")
        
        # Факт 4: Downgrade если был
        if routing.get("downgraded"):
            facts.append("⚠️ Task downgraded")
        
        # Факт 5: KB usage (компактно)
        kb_info = result.get("kb_retrieval", {})
        if kb_info.get("per_agent"):
            total_chunks = sum(s.get("chunks_used", 0) for s in kb_info["per_agent"].values())
            if total_chunks > 0:
                facts.append(f"KB refs: {total_chunks}")
        
        # Факт 6-8: Ключевые риски из агентов (если security)
        if "security" in opinions:
            facts.append("🔒 Security review required")
        
        return facts[:8]
    
    def run_shadow_analysis(self, consilium_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Запускает shadow анализ Director"""
        
        if not self.enabled:
            return None
        
        # Проверяем нужен ли Director для этой задачи
        task = consilium_result.get("task", "")
        routing = consilium_result.get("routing", {})
        confidence = routing.get("confidence", 1.0)
        domains = list(consilium_result.get("opinions", {}).keys())
        
        should_use = self.director_adapter.should_use_director(task, confidence, domains)
        
        if not should_use:
            return {
                "shadow_director_used": False,
                "reason": "No triggers activated",
                "confidence": confidence,
                "domains": len(domains)
            }
        
        # Создаём саммари
        director_request = self.create_summary_from_consilium_result(consilium_result)
        if not director_request:
            return {
                "shadow_director_used": False,
                "reason": "Failed to create summary",
                "error": "Summary creation failed"
            }
        
        # Вызываем Director
        start_time = time.time()
        try:
            director_response = self.director_adapter.call_director(director_request)
            director_time = time.time() - start_time
            
            shadow_result = {
                "shadow_director_used": True,
                "director_request": asdict(director_request),
                "director_response": asdict(director_response),
                "timing": {
                    "director_call": round(director_time, 2)
                },
                "metrics": self.director_adapter.get_metrics()
            }
            
            # Логируем результат
            self.log_shadow_result(consilium_result, shadow_result)
            
            return shadow_result
            
        except Exception as e:
            return {
                "shadow_director_used": False,
                "reason": "Director call failed",
                "error": str(e),
                "timing": {
                    "director_call": round(time.time() - start_time, 2)
                }
            }
    
    def log_shadow_result(self, consilium_result: Dict[str, Any], shadow_result: Dict[str, Any]):
        """Логирует результат shadow анализа"""
        
        log_entry = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "task": consilium_result.get("task", "")[:100],  # Первые 100 символов
            "consilium_mode": consilium_result.get("mode"),
            "consilium_confidence": consilium_result.get("routing", {}).get("confidence"),
            "consilium_agents": list(consilium_result.get("opinions", {}).keys()),
            "consilium_timing": consilium_result.get("timing", {}),
            "shadow_director": shadow_result,
            "comparison": self.compare_results(consilium_result, shadow_result)
        }
        
        # Конвертируем RiskLevel в строку для JSON сериализации
        if "director_request" in shadow_result:
            director_request = shadow_result["director_request"]
            if "risk_level" in director_request:
                director_request["risk_level"] = director_request["risk_level"].value if hasattr(director_request["risk_level"], 'value') else str(director_request["risk_level"])
        
        # Записываем в файл
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[SHADOW] Failed to log: {e}")
    
    def compare_results(self, consilium_result: Dict[str, Any], shadow_result: Dict[str, Any]) -> Dict[str, Any]:
        """Сравнивает результаты consilium и shadow director"""
        
        if not shadow_result.get("shadow_director_used"):
            return {"comparison": "director_not_used"}
        
        try:
            # Извлекаем ключевые элементы для сравнения
            consilium_recommendation = consilium_result.get("recommendation", "")
            director_decision = shadow_result.get("director_response", {}).get("decision", "")
            
            # Простое сравнение длины и ключевых слов
            comparison = {
                "consilium_length": len(consilium_recommendation),
                "director_length": len(director_decision),
                "director_confidence": shadow_result.get("director_response", {}).get("confidence", 0),
                "director_risks_count": len(shadow_result.get("director_response", {}).get("risks", [])),
                "director_recommendations_count": len(shadow_result.get("director_response", {}).get("recommendations", []))
            }
            
            # Проверяем наличие ключевых слов безопасности
            security_keywords = ["security", "auth", "token", "password", "vulnerability", "risk"]
            consilium_has_security = any(kw in consilium_recommendation.lower() for kw in security_keywords)
            director_has_security = any(kw in director_decision.lower() for kw in security_keywords)
            
            comparison["security_focus"] = {
                "consilium": consilium_has_security,
                "director": director_has_security,
                "alignment": consilium_has_security == director_has_security
            }
            
            return comparison
            
        except Exception as e:
            return {"comparison_error": str(e)}
    
    def get_shadow_stats(self) -> Dict[str, Any]:
        """Получает статистику shadow тестирования"""
        
        if not os.path.exists(self.log_file):
            return {"total_logs": 0}
        
        try:
            stats = {
                "total_logs": 0,
                "director_used": 0,
                "director_not_used": 0,
                "avg_director_confidence": 0,
                "total_cost": 0
            }
            
            confidences = []
            
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    stats["total_logs"] += 1
                    
                    shadow = entry.get("shadow_director", {})
                    if shadow.get("shadow_director_used"):
                        stats["director_used"] += 1
                        
                        director_response = shadow.get("director_response", {})
                        confidence = director_response.get("confidence", 0)
                        if confidence > 0:
                            confidences.append(confidence)
                        
                        # Добавляем стоимость если есть
                        metrics = shadow.get("metrics", {})
                        stats["total_cost"] += metrics.get("total_cost", 0)
                    else:
                        stats["director_not_used"] += 1
            
            if confidences:
                stats["avg_director_confidence"] = sum(confidences) / len(confidences)
            
            return stats
            
        except Exception as e:
            return {"error": str(e)}


# Глобальный экземпляр для использования в consilium
shadow_director = ShadowDirector()