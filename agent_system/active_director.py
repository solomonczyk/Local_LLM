#!/usr/bin/env python3
"""
Active Director с PRE-FILTER, override gating и circuit breaker
+ Unified Task Run Logging (task_run.jsonl)
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .director_circuit_breaker import circuit_breaker
from .shadow_director import ShadowDirector

logger = logging.getLogger(__name__)

# Глобальный счётчик задач для task_id
_task_counter = 0

# === THRESHOLD CONSTANTS ===
# FROZEN: 2026-01-07 — не менять до 2026-01-10 (3-дневная заморозка)
DECISION_POLICY_VERSION = "pf_v2.2_gate_v1.0_cb_v1.1"

THRESHOLDS = {
    "version": DECISION_POLICY_VERSION,
    "prefilter_conf_lt": 0.75,   # Pre-filter: вызываем Director если conf < этого
    "low_conf_lt": 0.70,         # Override gate: low_conf если conf < этого
    "diff_gte": 0.10,            # Override gate: требуемый confidence diff
    "multi_domain_gte": 3        # Multi-domain trigger
}


class ActiveDirector:
    """
    Active Director с умным override gating
    
    Заменяет consilium ответ только при выполнении строгих условий:
    - risk_level == "high" ИЛИ
    - consilium_confidence < 0.7 ИЛИ  
    - domains_matched >= 3 И director_confidence - consilium_confidence >= 0.10
    
    Во всех остальных случаях consilium остаётся основным,
    Director сохраняется как review.
    """
    
    def __init__(self, enabled: bool = None):
        self.enabled = enabled if enabled is not None else self._check_enabled()
        self.shadow_director = ShadowDirector(enabled=self.enabled)
        self.log_file = "active_director.jsonl"
        self.task_run_log = "task_run.jsonl"  # Unified task log
        
        if self.enabled:
            logger.info(f"[ACTIVE] Director enabled, logging to {self.log_file}")
        else:
            logger.info("[ACTIVE] Director disabled")
    
    def _check_enabled(self) -> bool:
        """Проверяет включён ли Active Director"""
        return os.getenv("DIRECTOR_ACTIVE_MODE", "false").lower() == "true"
    
    def _get_next_task_id(self) -> str:
        """Генерирует уникальный task_id"""
        global _task_counter
        _task_counter += 1
        return f"task_{datetime.now().strftime('%Y%m%d')}_{_task_counter:04d}"
    
    def _determine_risk_level(self, consilium_result: Dict[str, Any]) -> str:
        """Определяет risk_level задачи"""
        opinions = consilium_result.get("opinions", {})
        task = consilium_result.get("task", "").lower()
        routing = consilium_result.get("routing", {})
        confidence = routing.get("confidence", 1.0)
        
        # High risk keywords
        high_risk_keywords = ["auth", "token", "password", "payment", "migration", "vulnerability", "security"]
        
        if "security" in opinions or any(kw in task for kw in high_risk_keywords):
            return "high"
        elif confidence < 0.7 or routing.get("domains_matched", 0) >= 3:
            return "medium"
        else:
            return "low"
    
    def _log_task_run(self, consilium_result: Dict[str, Any], 
                      pre_filter_passed: bool,
                      pre_filter_reasons: List[str],
                      director_called: bool, override_applied: bool,
                      director_tokens: Optional[int], director_cost: Optional[float], 
                      director_latency: Optional[float],
                      override_reason: Optional[str] = None,
                      director_confidence: Optional[float] = None):
        """Логирует каждую задачу в task_run.jsonl"""
        
        task_id = self._get_next_task_id()
        routing = consilium_result.get("routing", {})
        opinions = consilium_result.get("opinions", {})
        consilium_conf = routing.get("confidence", 0)
        
        # Calculate confidence diff
        conf_diff = round(director_confidence - consilium_conf, 2) if director_confidence else None
        
        # Soft override candidate: director called, not applied, but diff >= threshold
        soft_override_candidate = (
            director_called and 
            not override_applied and 
            conf_diff is not None and 
            conf_diff >= THRESHOLDS["diff_gte"]
        )
        
        # Shadow soft allow candidate: would have overridden if not in shadow mode
        shadow_soft_allow_candidate = (
            soft_override_candidate and 
            override_reason == "shadow_mode"
        )
        
        entry = {
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "task_summary": consilium_result.get("task", "")[:100],
            "domains": list(opinions.keys()),
            "risk_level": self._determine_risk_level(consilium_result),
            "consilium_confidence": consilium_conf,
            "pre_filter": {
                "passed": pre_filter_passed,
                "reason_tokens": pre_filter_reasons,
                "thresholds": THRESHOLDS
            },
            "director": {
                "called": director_called,
                "override_applied": override_applied,
                "soft_override_candidate": soft_override_candidate,
                "shadow_soft_allow_candidate": shadow_soft_allow_candidate if director_called else None,
                "override_reason": override_reason,
                "director_confidence": director_confidence,
                "confidence_diff": conf_diff,
                "tokens": director_tokens,
                "cost": round(director_cost, 6) if director_cost else None,
                "latency_s": round(director_latency, 2) if director_latency else None
            }
        }
        
        try:
            with open(self.task_run_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"[ACTIVE] Error logging task run: {e}")
    
    def _should_override(self, consilium_result: Dict[str, Any], director_response: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Определяет нужно ли заменить consilium ответ на director
        
        STRICT OVERRIDE GATE (безопасный Active Mode):
        Override разрешён ТОЛЬКО если:
        - (risk_level == "high" OR consilium_confidence < 0.70)
        - AND (director_confidence - consilium_confidence) >= 0.10
        
        Returns:
            (should_override: bool, reason: str)
        """
        routing = consilium_result.get("routing", {})
        consilium_confidence = routing.get("confidence", 1.0)
        domains_matched = routing.get("domains_matched", 1)
        
        director_confidence = director_response.get("confidence", 0.0)
        confidence_diff = director_confidence - consilium_confidence
        
        # Определяем risk_level
        risk_level = self._determine_risk_level(consilium_result)
        
        # === STRICT OVERRIDE GATE ===
        # Условие 1: Должен быть high-risk ИЛИ низкая уверенность consilium (строго < 0.70)
        low_conf_threshold = THRESHOLDS["low_conf_lt"]
        diff_threshold = THRESHOLDS["diff_gte"]
        
        risk_condition = (risk_level == "high" or consilium_confidence < low_conf_threshold)
        
        # Условие 2: Director должен быть значительно увереннее (+0.10)
        confidence_condition = (confidence_diff >= diff_threshold)
        
        # Оба условия должны выполняться
        if risk_condition and confidence_condition:
            reasons = []
            if risk_level == "high":
                reasons.append("high_risk")
            if consilium_confidence < low_conf_threshold:  # Строго меньше
                reasons.append(f"low_conf({consilium_confidence:.2f})")
            reasons.append(f"diff=+{confidence_diff:.2f}")
            
            return True, " + ".join(reasons)
            
            return True, " + ".join(reasons)
        
        # Override не разрешён - объясняем почему
        deny_reasons = []
        if not risk_condition:
            deny_reasons.append(f"risk={risk_level},conf={consilium_confidence:.2f}")
        if not confidence_condition:
            deny_reasons.append(f"diff={confidence_diff:+.2f}<0.10")
        
        return False, f"gate_denied ({'; '.join(deny_reasons)})"
    
    def run_active_analysis(self, consilium_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Запускает Active Director анализ с PRE-FILTER, override gating и circuit breaker
        + Unified Task Run Logging
        
        PRE-DIRECTOR FILTER (cheap gate):
        Director НЕ вызывается если одновременно:
        - risk_level != high
        - consilium_confidence >= 0.75
        - domains_matched < 3
        
        Returns:
            Обновлённый consilium_result с возможной заменой на director решение
        """
        if not self.enabled:
            return consilium_result
        
        # === PRE-DIRECTOR FILTER (cheap gate) ===
        should_call, filter_reasons = self._pre_director_filter(consilium_result)
        
        if not should_call:
            consilium_result["active_director"] = {
                "active_director_used": False,
                "reason": f"pre_filter: {' + '.join(filter_reasons)}",
                "override_applied": False,
                "circuit_breaker_mode": circuit_breaker.current_mode
            }
            # Log task run (Director not called due to pre-filter)
            self._log_task_run(
                consilium_result, 
                pre_filter_passed=False,
                pre_filter_reasons=filter_reasons,
                director_called=False, 
                override_applied=False,
                director_tokens=None, 
                director_cost=None, 
                director_latency=None
            )
            return consilium_result
        
        # Проверяем circuit breaker (с контекстом для security/high bypass)
        task_context = {
            "risk_level": self._determine_risk_level(consilium_result),
            "domains": list(consilium_result.get("opinions", {}).keys())
        }
        use_director, mode_reason = circuit_breaker.should_use_director(context=task_context)
        
        if not use_director:
            consilium_result["active_director"] = {
                "active_director_used": False,
                "reason": mode_reason,
                "override_applied": False,
                "circuit_breaker_mode": circuit_breaker.current_mode
            }
            # Log task run (Director disabled by circuit breaker)
            self._log_task_run(
                consilium_result,
                pre_filter_passed=True,
                pre_filter_reasons=filter_reasons,
                director_called=False,
                override_applied=False,
                director_tokens=None,
                director_cost=None,
                director_latency=None
            )
            return consilium_result
        
        try:
            # Получаем shadow анализ (тот же процесс)
            shadow_result = self.shadow_director.run_shadow_analysis(consilium_result)
            
            if not shadow_result or not shadow_result.get("shadow_director_used"):
                # Director не был вызван - возвращаем как есть
                if shadow_result:
                    consilium_result["active_director"] = {
                        "active_director_used": False,
                        "reason": shadow_result.get("reason", "No triggers activated"),
                        "override_applied": False,
                        "circuit_breaker_mode": circuit_breaker.current_mode
                    }
                # Log task run (Director skipped by shadow logic)
                self._log_task_run(
                    consilium_result,
                    pre_filter_passed=True,
                    pre_filter_reasons=filter_reasons,
                    director_called=False,
                    override_applied=False,
                    director_tokens=None,
                    director_cost=None,
                    director_latency=None
                )
                return consilium_result
            
            director_response = shadow_result.get("director_response", {})
            director_timing = shadow_result.get("timing", {})
            director_metrics = shadow_result.get("metrics", {})
            
            # Извлекаем РЕАЛЬНЫЕ токены этого вызова (не кумулятивные)
            # metrics содержит кумулятивные данные, нужно вычислить дельту
            call_tokens = director_metrics.get("total_tokens", 0)
            calls_today = director_metrics.get("calls_today", 1)
            if calls_today > 1:
                # Приблизительно: avg_tokens * 1 call
                call_tokens = int(director_metrics.get("avg_tokens_per_call", call_tokens))
            
            call_cost = director_metrics.get("cost_per_call", director_metrics.get("total_cost", 0))
            
            # Записываем метрики в circuit breaker
            director_cost = director_metrics.get("total_cost", 0.0)
            director_latency = director_timing.get("director_call", 0.0)
            director_error = "error" in director_response
            
            # Проверяем нужно ли override (только в active mode)
            should_override = False
            override_reason = "shadow_mode"
            
            if circuit_breaker.current_mode == "active":
                should_override, override_reason = self._should_override(consilium_result, director_response)
            
            # Записываем метрики в circuit breaker
            confidence_diff = director_response.get("confidence", 0) - consilium_result.get("routing", {}).get("confidence", 0)
            circuit_breaker.record_director_call(
                override_applied=should_override,
                director_cost=director_cost,
                director_latency=director_latency,
                director_error=director_error,
                confidence_diff=confidence_diff
            )
            
            # Создаём active director результат
            active_result = {
                "active_director_used": True,
                "override_applied": should_override,
                "override_reason": override_reason,
                "circuit_breaker_mode": circuit_breaker.current_mode,
                "director_request": shadow_result.get("director_request"),
                "director_response": director_response,
                "timing": director_timing,
                "metrics": director_metrics,
                "original_consilium": {
                    "recommendation": consilium_result.get("recommendation", ""),
                    "confidence": consilium_result.get("routing", {}).get("confidence", 0),
                    "agents": list(consilium_result.get("opinions", {}).keys())
                }
            }
            
            if should_override and circuit_breaker.current_mode == "active":
                # Заменяем основной ответ на director
                original_recommendation = consilium_result.get("recommendation", "")
                consilium_result["recommendation"] = director_response.get("decision", "")
                
                # Добавляем director данные
                consilium_result["director_decision"] = {
                    "decision": director_response.get("decision"),
                    "risks": director_response.get("risks", []),
                    "recommendations": director_response.get("recommendations", []),
                    "next_step": director_response.get("next_step"),
                    "confidence": director_response.get("confidence"),
                    "reasoning": director_response.get("reasoning")
                }
                
                active_result["override_details"] = {
                    "original_length": len(original_recommendation),
                    "director_length": len(director_response.get("decision", "")),
                    "confidence_improvement": confidence_diff
                }
                
                logger.info(f"[ACTIVE] Override applied: {override_reason}")
            else:
                # Consilium остаётся основным, director как review
                active_result["director_review"] = {
                    "decision": director_response.get("decision"),
                    "risks": director_response.get("risks", []),
                    "recommendations": director_response.get("recommendations", []),
                    "confidence": director_response.get("confidence")
                }
                
                mode_info = f" (mode: {circuit_breaker.current_mode})" if circuit_breaker.current_mode != "active" else ""
                logger.info(f"[ACTIVE] No override: {override_reason}{mode_info}")
            
            consilium_result["active_director"] = active_result
            
            # Логируем результат (legacy)
            self._log_active_result(consilium_result, active_result)
            
            # Log task run (Director called)
            self._log_task_run(
                consilium_result,
                pre_filter_passed=True,
                pre_filter_reasons=filter_reasons,
                director_called=True,
                override_applied=should_override,
                director_tokens=call_tokens,
                director_cost=call_cost,
                director_latency=director_latency,
                override_reason=override_reason,
                director_confidence=director_response.get("confidence")
            )
            
            return consilium_result
            
        except Exception as e:
            logger.error(f"[ACTIVE] Error in active analysis: {e}")
            
            # Записываем ошибку в circuit breaker
            circuit_breaker.record_director_call(
                override_applied=False,
                director_cost=0.0,
                director_latency=0.0,
                director_error=True,
                confidence_diff=0.0
            )
            
            consilium_result["active_director"] = {
                "active_director_used": False,
                "error": str(e),
                "override_applied": False,
                "circuit_breaker_mode": circuit_breaker.current_mode
            }
            
            # Log task run (error)
            self._log_task_run(
                consilium_result,
                pre_filter_passed=True,
                pre_filter_reasons=filter_reasons,
                director_called=False,
                override_applied=False,
                director_tokens=None,
                director_cost=None,
                director_latency=None
            )
            
            return consilium_result
    
    def _pre_director_filter(self, consilium_result: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        PRE-DIRECTOR FILTER (cheap gate)
        
        Director НЕ вызывается если одновременно:
        - risk_level != high
        - consilium_confidence >= 0.75
        - domains_matched < 3
        
        Returns:
            (should_call_director: bool, reason_tokens: List[str])
        """
        routing = consilium_result.get("routing", {})
        opinions = consilium_result.get("opinions", {})
        
        confidence = routing.get("confidence", 1.0)
        domains_matched = routing.get("domains_matched", len(opinions))
        
        # Определяем risk_level
        is_high_risk = "security" in opinions or any(
            kw in consilium_result.get("task", "").lower() 
            for kw in ["auth", "token", "password", "payment", "migration", "vulnerability"]
        )
        
        # PRE-FILTER: Если всё спокойно — не зовём Director
        if not is_high_risk and confidence >= THRESHOLDS["prefilter_conf_lt"] and domains_matched < THRESHOLDS["multi_domain_gte"]:
            return False, ["calm_task", f"risk=low", f"conf={confidence:.2f}", f"domains={domains_matched}"]
        
        # Иначе — зовём Director
        reasons = []
        if is_high_risk:
            reasons.append("high_risk")
        if confidence < THRESHOLDS["prefilter_conf_lt"]:  # Pre-filter threshold: < 0.75
            reasons.append(f"conf<{THRESHOLDS['prefilter_conf_lt']}({confidence:.2f})")
        if domains_matched >= THRESHOLDS["multi_domain_gte"]:
            reasons.append(f"multi_domain({domains_matched})")
        
        return True, reasons if reasons else ["triggered"]
    
    def _log_active_result(self, consilium_result: Dict[str, Any], active_result: Dict[str, Any]):
        """Логирует результат active director"""
        try:
            log_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "task": "[TASK_REDACTED_FOR_PRIVACY]",
                "consilium_mode": consilium_result.get("mode", "UNKNOWN"),
                "consilium_confidence": consilium_result.get("routing", {}).get("confidence"),
                "consilium_agents": list(consilium_result.get("opinions", {}).keys()),
                "consilium_timing": consilium_result.get("timing", {}),
                "active_director": active_result,
                "comparison": {
                    "override_applied": active_result.get("override_applied", False),
                    "override_reason": active_result.get("override_reason", ""),
                    "director_confidence": active_result.get("director_response", {}).get("confidence"),
                    "confidence_diff": (
                        active_result.get("director_response", {}).get("confidence", 0) - 
                        consilium_result.get("routing", {}).get("confidence", 0)
                    ) if active_result.get("director_response") else 0
                }
            }
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
        except Exception as e:
            logger.error(f"[ACTIVE] Error logging result: {e}")


# Глобальный экземпляр для использования в consilium
active_director = ActiveDirector()