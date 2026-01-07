#!/usr/bin/env python3
"""
Тест для генерации soft_override_candidate: true
"""

import os
import json
from agent_system.active_director import ActiveDirector, THRESHOLDS
from agent_system.director_circuit_breaker import DirectorCircuitBreaker


def main():
    # Сбрасываем
    cb = DirectorCircuitBreaker()
    cb.current_mode = "active"
    cb.metrics_history.clear()
    
    # Удаляем старый лог
    if os.path.exists("task_run.jsonl"):
        os.remove("task_run.jsonl")
    
    active_director = ActiveDirector(enabled=True)
    
    # Задача: low risk, high confidence (0.80) - не должен override
    # Но если Director вернёт 0.92 (diff=0.12 >= 0.10), это soft_override_candidate
    result = {
        "task": "Implement caching layer for API responses",
        "mode": "STANDARD",
        "opinions": {
            "dev": {"role": "Dev", "opinion": "Use Redis"},
            "architect": {"role": "Architect", "opinion": "Consider TTL strategy"}
        },
        "recommendation": "Implement Redis caching",
        "routing": {
            "smart_routing": True,
            "confidence": 0.80,  # High confidence
            "domains_matched": 2,
        },
        "timing": {"agents_parallel": 8.0, "total": 10.0},
        "kb_retrieval": {"per_agent": {"dev": {"chunks_used": 2}, "architect": {"chunks_used": 2}}}
    }
    
    print("Testing soft_override_candidate scenario:")
    print(f"  - risk_level: low (no security keywords)")
    print(f"  - consilium_confidence: 0.80 (>= 0.70, so no low_conf trigger)")
    print(f"  - domains: 2 (< 3, so no multi_domain trigger)")
    print()
    print("Expected: pre_filter should BLOCK (calm_task), no Director call")
    print()
    
    # Запускаем
    output = active_director.run_active_analysis(result)
    
    # Читаем лог
    with open("task_run.jsonl", "r") as f:
        log_entry = json.loads(f.readline())
    
    print("Result from task_run.jsonl:")
    print(json.dumps(log_entry, indent=2))
    
    # Для soft_override_candidate нужен Director call
    # Создадим задачу с low confidence чтобы Director вызвался
    print("\n" + "="*60)
    print("\nTest 2: Task that triggers Director but doesn't override")
    
    result2 = {
        "task": "Implement logging for API endpoints",  # No security keywords
        "mode": "STANDARD",
        "opinions": {
            "dev": {"role": "Dev", "opinion": "Use structured logging"},
            "architect": {"role": "Architect", "opinion": "Consider log aggregation"}
        },
        "recommendation": "Implement structured logging",
        "routing": {
            "smart_routing": True,
            "confidence": 0.72,  # Low enough to trigger pre-filter (< 0.75)
            "domains_matched": 2,
        },
        "timing": {"agents_parallel": 8.0, "total": 10.0},
        "kb_retrieval": {"per_agent": {"dev": {"chunks_used": 2}, "architect": {"chunks_used": 2}}}
    }
    
    print(f"  - risk_level: low")
    print(f"  - consilium_confidence: 0.72 (< 0.75, triggers pre-filter)")
    print(f"  - But >= 0.70, so no low_conf in override gate")
    print()
    
    output2 = active_director.run_active_analysis(result2)
    
    # Читаем последнюю строку
    with open("task_run.jsonl", "r") as f:
        lines = f.readlines()
        log_entry2 = json.loads(lines[-1])
    
    print("Result from task_run.jsonl (last entry):")
    print(json.dumps(log_entry2, indent=2))
    
    # Проверяем soft_override_candidate
    director = log_entry2.get("director", {})
    soft_candidate = director.get("soft_override_candidate", False)
    
    print()
    if soft_candidate:
        print("✅ soft_override_candidate: true found!")
    else:
        print(f"ℹ️ soft_override_candidate: {soft_candidate}")
        print("   (This is expected if Director wasn't called or diff < 0.10)")


if __name__ == "__main__":
    main()
