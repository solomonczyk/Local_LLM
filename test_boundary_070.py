#!/usr/bin/env python3
"""
Тест граничного случая confidence=0.70
"""

import os
from agent_system.active_director import ActiveDirector
from agent_system.director_circuit_breaker import DirectorCircuitBreaker


def create_test_result(confidence: float, domains: list, has_security: bool = False):
    """Создаёт тестовый результат с заданным confidence"""
    
    opinions = {}
    for domain in domains:
        opinions[domain] = {
            "role": f"{domain.title()} Specialist",
            "opinion": f"Test opinion for domain {domain}"
        }
    
    if has_security and "security" not in opinions:
        opinions["security"] = {"role": "Security", "opinion": "Security review"}
    
    return {
        "task": "Test task for boundary check",
        "mode": "STANDARD",
        "opinions": opinions,
        "recommendation": "Test recommendation",
        "routing": {
            "smart_routing": True,
            "confidence": confidence,  # Не округляем!
            "domains_matched": len(opinions),
        },
        "timing": {"agents_parallel": 10.0, "total": 12.0},
        "kb_retrieval": {"per_agent": {d: {"chunks_used": 2} for d in opinions}}
    }


def test_boundary():
    print("="*60)
    print("Testing Boundary Case: confidence=0.70")
    print("="*60)
    
    # Сбрасываем circuit breaker
    cb = DirectorCircuitBreaker()
    cb.current_mode = "active"
    cb.metrics_history.clear()
    
    active_director = ActiveDirector(enabled=True)
    
    test_cases = [
        # (confidence, domains, has_security, expected_pre_filter_pass, expected_low_conf_in_reason)
        (0.69, ["dev"], False, True, True),    # < 0.70 → low_conf
        (0.70, ["dev"], False, True, False),   # = 0.70 → НЕ low_conf (граница)
        (0.71, ["dev"], False, True, False),   # > 0.70 → НЕ low_conf
        (0.74, ["dev"], False, True, False),   # < 0.75 → pre_filter pass, но не low_conf
        (0.75, ["dev"], False, False, False),  # >= 0.75 → calm_task
        (0.70, ["dev", "security"], True, True, False),  # 0.70 + security → high_risk, не low_conf
    ]
    
    print("\nPre-filter threshold: 0.75")
    print("Override gate low_conf threshold: < 0.70 (strictly less)")
    print()
    
    for conf, domains, has_sec, exp_pass, exp_low_conf in test_cases:
        result = create_test_result(conf, domains, has_sec)
        
        # Тестируем pre_filter напрямую
        should_call, reason = active_director._pre_director_filter(result)
        
        # Проверяем
        has_low_conf = "low_conf" in reason
        
        status = "✅" if (should_call == exp_pass and has_low_conf == exp_low_conf) else "❌"
        
        print(f"{status} conf={conf:.2f}, security={has_sec}")
        print(f"   pre_filter: passed={should_call}, reason='{reason}'")
        print(f"   expected: passed={exp_pass}, low_conf_in_reason={exp_low_conf}")
        print()


if __name__ == "__main__":
    test_boundary()