#!/usr/bin/env python3
"""
Мок-тест для демонстрации soft_override_candidate: true
"""

import os
import json
from datetime import datetime
from agent_system.active_director import THRESHOLDS

def main():
    # Создаём мок-запись напрямую в task_run.jsonl
    # Симулируем: Director вызван, conf_diff=0.15, но override не применён (risk=low, conf>=0.70)
    
    entry = {
        "task_id": "task_20260107_mock_001",
        "timestamp": datetime.now().isoformat(),
        "task_summary": "Implement API rate limiting with Redis",
        "domains": ["dev", "architect"],
        "risk_level": "low",
        "consilium_confidence": 0.72,
        "pre_filter": {
            "passed": True,
            "reason_tokens": ["conf<0.75(0.72)"],
            "thresholds": THRESHOLDS
        },
        "director": {
            "called": True,
            "override_applied": False,
            "soft_override_candidate": True,  # diff=0.15 >= 0.10, but no override (risk=low, conf>=0.70)
            "override_reason": "gate_denied (risk=low,conf=0.72; diff=+0.15>=0.10 but risk_condition=false)",
            "director_confidence": 0.87,
            "confidence_diff": 0.15,
            "tokens": 412,
            "cost": 0.000082,
            "latency_s": 2.34
        }
    }
    
    # Записываем
    with open("task_run.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    print("Mock entry with soft_override_candidate: true")
    print(json.dumps(entry, indent=2))


if __name__ == "__main__":
    main()
