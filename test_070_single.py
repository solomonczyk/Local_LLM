#!/usr/bin/env python3
"""
Тест одной задачи с confidence=0.70
"""

import os
import json
from agent_system.active_director import ActiveDirector
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
    
    # Задача с точно 0.70 confidence (без security)
    result = {
        "task": "Implement rate limiting for API endpoints",
        "mode": "STANDARD",
        "opinions": {
            "dev": {"role": "Dev", "opinion": "Implement with Redis"},
            "architect": {"role": "Architect", "opinion": "Use token bucket"}
        },
        "recommendation": "Implement rate limiting",
        "routing": {
            "smart_routing": True,
            "confidence": 0.70,  # Точно 0.70
            "domains_matched": 2,
        },
        "timing": {"agents_parallel": 10.0, "total": 12.0},
        "kb_retrieval": {"per_agent": {"dev": {"chunks_used": 2}, "architect": {"chunks_used": 2}}}
    }
    
    print("Testing task with confidence=0.70 (no security domain)")
    print("Expected: pre_filter passes with 'conf<0.75(0.70)', NOT 'low_conf'")
    print()
    
    # Запускаем
    output = active_director.run_active_analysis(result)
    
    # Читаем лог
    with open("task_run.jsonl", "r") as f:
        log_entry = json.loads(f.readline())
    
    print("Result from task_run.jsonl:")
    print(json.dumps(log_entry, indent=2))
    
    # Проверяем
    pre_filter = log_entry["pre_filter"]
    reason_tokens = pre_filter.get("reason_tokens", [])
    reason_str = " ".join(reason_tokens)
    has_low_conf = any("low_conf" in token for token in reason_tokens)
    
    print()
    if has_low_conf:
        print("❌ FAIL: 'low_conf' found in reason_tokens (should not be there for 0.70)")
    else:
        print("✅ PASS: No 'low_conf' in reason_tokens for confidence=0.70")
    
    print(f"   pre_filter.reason_tokens: {reason_tokens}")
    print(f"   pre_filter.passed: {pre_filter.get('passed')}")
    print(f"   thresholds: {pre_filter.get('thresholds')}")


if __name__ == "__main__":
    main()