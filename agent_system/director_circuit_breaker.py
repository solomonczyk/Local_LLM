#!/usr/bin/env python3
"""
Director Circuit Breaker - авто-rollback по метрикам для защиты от деградации
"""

import json
import logging
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DirectorMetrics:
    """Метрики для одного вызова Director"""
    timestamp: datetime
    override_applied: bool
    director_cost: float
    director_latency: float
    director_error: bool
    confidence_diff: float


class DirectorCircuitBreaker:
    """
    Circuit Breaker для Director с rolling метриками
    
    Автоматически переключает режимы:
    - active → shadow при превышении лимитов
    - shadow → active при стабилизации метрик
    
    Условия rollback:
    - override_rate_last_20 > 0.75
    - avg_director_cost_day > 0.01  
    - director_error_rate_last_20 > 0.10
    - avg_latency_director > 6s (за последние 20)
    """
    
    def __init__(self):
        self.metrics_history: deque = deque(maxlen=100)  # Последние 100 вызовов
        self.log_file = "director_circuit_breaker.jsonl"
        self.current_mode = self._get_current_mode()
        
        # Лимиты для rollback
        self.limits = {
            "override_rate_max": 0.75,
            "daily_cost_max": 0.01,
            "error_rate_max": 0.10,
            "latency_max": 6.0
        }
        
        # Ослабленные лимиты для security/high (менее чувствительный breaker)
        self.limits_security_high = {
            "override_rate_max": 0.90,  # +20% от базового 0.75
            "daily_cost_max": 0.012,    # +20% от базового 0.01
            "error_rate_max": 0.12,     # +20% от базового 0.10
            "latency_max": 7.2          # +20% от базового 6.0
        }
        
        logger.info(f"[CIRCUIT] Director mode: {self.current_mode}")
    
    def _get_current_mode(self) -> str:
        """Получает текущий режим Director"""
        mode = os.getenv("DIRECTOR_MODE", "").lower()
        if mode in ["off", "shadow", "active"]:
            return mode
        
        # Fallback на старые переменные
        if os.getenv("DIRECTOR_ACTIVE_MODE", "false").lower() == "true":
            return "active"
        elif os.getenv("SHADOW_DIRECTOR_ENABLED", "false").lower() == "true":
            return "shadow"
        else:
            return "off"
    
    def _set_director_mode(self, new_mode: str, reason: str):
        """Устанавливает новый режим Director"""
        old_mode = self.current_mode
        self.current_mode = new_mode
        
        # Логируем переключение
        event = {
            "timestamp": datetime.now().isoformat(),
            "event": "director_mode_change",
            "old_mode": old_mode,
            "new_mode": new_mode,
            "reason": reason,
            "triggered_by": "circuit_breaker"
        }
        
        self._log_event(event)
        logger.warning(f"[CIRCUIT] Mode changed: {old_mode} → {new_mode} ({reason})")
        
        # TODO: В реальной системе здесь нужно обновить переменные окружения
        # или конфигурационный файл для персистентности
    
    def record_director_call(self, 
                           override_applied: bool,
                           director_cost: float,
                           director_latency: float,
                           director_error: bool = False,
                           confidence_diff: float = 0.0):
        """Записывает метрики вызова Director"""
        
        metrics = DirectorMetrics(
            timestamp=datetime.now(),
            override_applied=override_applied,
            director_cost=director_cost,
            director_latency=director_latency,
            director_error=director_error,
            confidence_diff=confidence_diff
        )
        
        self.metrics_history.append(metrics)
        
        # Проверяем нужен ли rollback
        self._check_circuit_breaker()
    
    def _check_circuit_breaker(self):
        """Проверяет условия для circuit breaker"""
        
        if len(self.metrics_history) < 5:  # Минимум данных для анализа
            return
        
        # Вычисляем rolling метрики
        rolling_metrics = self._calculate_rolling_metrics()
        
        # Проверяем каждое условие rollback
        violations = []
        
        if rolling_metrics["override_rate_20"] > self.limits["override_rate_max"]:
            violations.append(f"override_rate={rolling_metrics['override_rate_20']:.2f} > {self.limits['override_rate_max']}")
        
        if rolling_metrics["daily_cost"] > self.limits["daily_cost_max"]:
            violations.append(f"daily_cost=${rolling_metrics['daily_cost']:.4f} > ${self.limits['daily_cost_max']}")
        
        if rolling_metrics["error_rate_20"] > self.limits["error_rate_max"]:
            violations.append(f"error_rate={rolling_metrics['error_rate_20']:.2f} > {self.limits['error_rate_max']}")
        
        if rolling_metrics["avg_latency_20"] > self.limits["latency_max"]:
            violations.append(f"latency={rolling_metrics['avg_latency_20']:.1f}s > {self.limits['latency_max']}s")
        
        # Логируем текущее состояние
        status_log = {
            "timestamp": datetime.now().isoformat(),
            "event": "circuit_breaker_check",
            "current_mode": self.current_mode,
            "rolling_metrics": rolling_metrics,
            "violations": violations,
            "decision": "maintain" if not violations else "trigger_rollback"
        }
        
        self._log_event(status_log)
        
        # Принимаем решение
        if violations and self.current_mode == "active":
            # Rollback в shadow mode
            reason = f"Circuit breaker triggered: {'; '.join(violations)}"
            self._set_director_mode("shadow", reason)
            
        elif not violations and self.current_mode == "shadow":
            # Восстановление с гистерезисом (защита от флапа)
            # Требования: 10+ вызовов, override_rate < 0.65, error_rate == 0
            if (rolling_metrics["calls_count_20"] >= 10 and 
                rolling_metrics["override_rate_20"] < 0.65 and
                rolling_metrics["error_rate_20"] == 0):
                reason = "Metrics stabilized (override<0.65, errors=0, 10+ calls)"
                self._set_director_mode("active", reason)
    
    def _calculate_rolling_metrics(self) -> Dict[str, float]:
        """Вычисляет rolling метрики за последние 20 вызовов и день"""
        
        now = datetime.now()
        last_20 = list(self.metrics_history)[-20:]  # Последние 20
        last_day = [m for m in self.metrics_history if now - m.timestamp <= timedelta(days=1)]
        
        # Метрики за последние 20 вызовов
        override_count_20 = sum(1 for m in last_20 if m.override_applied)
        error_count_20 = sum(1 for m in last_20 if m.director_error)
        total_latency_20 = sum(m.director_latency for m in last_20)
        
        # Метрики за день
        daily_cost = sum(m.director_cost for m in last_day)
        
        return {
            "calls_count_20": len(last_20),
            "calls_count_day": len(last_day),
            "override_rate_20": override_count_20 / max(len(last_20), 1),
            "error_rate_20": error_count_20 / max(len(last_20), 1),
            "avg_latency_20": total_latency_20 / max(len(last_20), 1),
            "daily_cost": daily_cost,
            "avg_confidence_diff_20": sum(m.confidence_diff for m in last_20) / max(len(last_20), 1)
        }
    
    def get_current_status(self) -> Dict[str, Any]:
        """Возвращает текущий статус circuit breaker"""
        
        rolling_metrics = self._calculate_rolling_metrics() if self.metrics_history else {}
        
        return {
            "current_mode": self.current_mode,
            "total_calls": len(self.metrics_history),
            "rolling_metrics": rolling_metrics,
            "limits": self.limits,
            "health": "healthy" if self.current_mode == "active" else "degraded"
        }
    
    def _log_event(self, event: Dict[str, Any]):
        """Логирует событие circuit breaker"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False, default=str) + '\n')
        except Exception as e:
            logger.error(f"[CIRCUIT] Error logging event: {e}")
    
    def should_use_director(self, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Определяет нужно ли использовать Director в текущем режиме
        
        Args:
            context: Опциональный контекст задачи с полями:
                     - risk_level: "low" | "medium" | "high"
                     - domains: List[str] (например ["security", "dev"])
        
        Returns:
            (use_director: bool, mode_reason: str)
        """
        
        if self.current_mode == "off":
            return False, "director_disabled"
        elif self.current_mode == "shadow":
            # Исключение: security/high остаётся в active даже когда breaker в shadow
            if context and self._is_security_high(context):
                return True, "active_mode"  # Bypass shadow для security/high
            return True, "shadow_mode"  # Director вызывается но не влияет
        elif self.current_mode == "active":
            return True, "active_mode"  # Director может заменять ответы
        else:
            return False, f"unknown_mode_{self.current_mode}"
    
    def _is_security_high(self, context: Dict[str, Any]) -> bool:
        """Проверяет является ли задача security/high"""
        risk_level = context.get("risk_level", "").lower()
        domains = context.get("domains", [])
        
        return risk_level == "high" and "security" in domains


# Глобальный экземпляр
circuit_breaker = DirectorCircuitBreaker()