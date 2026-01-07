#!/usr/bin/env python3
"""
Test Decision Capsule: 20 задач для проверки ужатого контракта
"""

import os
import json
import random
from datetime import datetime
from collections import defaultdict
from agent_system.active_director import ActiveDirector
from agent_system.director_circuit_breaker import DirectorCircuitBreaker


# 20 разнообразных задач
TEST_TASKS = [
    {"task": "Implement JWT authentication with refresh tokens", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Add CSRF protection to all forms", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Create database migration for user roles", "domains": ["architect", "dev", "security"], "risk": "high"},
    {"task": "Implement rate limiting for API", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Design caching strategy", "domains": ["architect", "dev"], "risk": "medium"},
    {"task": "Add input validation", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Write unit tests for auth service", "domains": ["qa", "dev"], "risk": "low"},
    {"task": "Fix button alignment on mobile", "domains": ["ux", "dev"], "risk": "low"},
    {"task": "Implement file upload with security checks", "domains": ["dev", "security"], "risk": "medium"},
    {"task": "Add SEO meta tags", "domains": ["seo", "dev"], "risk": "low"},
    {"task": "Create admin dashboard API", "domains": ["dev", "security"], "risk": "medium"},
    {"task": "Implement password hashing", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Add pagination to list endpoints", "domains": ["dev"], "risk": "low"},
    {"task": "Design microservices architecture", "domains": ["architect"], "risk": "medium"},
    {"task": "Implement audit logging", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Create email notification service", "domains": ["dev"], "risk": "low"},
    {"task": "Add two-factor authentication", "domains": ["security", "dev", "ux"], "risk": "high"},
    {"task": "Implement webhook handlers", "domains": ["dev", "security"], "risk": "medium"},
    {"task": "Create integration tests", "domains": ["qa", "dev"], "risk": "low"},
    {"task": "Add API key rotation", "domains": ["security", "architect"], "risk": "high"},
]


def create_consilium_result(task_info: dict, task_id: int) -> dict:
    """Создаёт реалистичный результат consilium"""
    
    domains = task_info["domains"]
    risk = task_info["risk"]
    
    base_confidence = {"low": 0.85, "medium": 0.75, "high": 0.65}[risk]
    confidence = base_confidence + random.uniform(-0.05, 0.05)
    confidence = max(0.5, min(0.95, confidence))
    
    opinions = {}
    for domain in domains:
        opinions[domain] = {
            "role": f"{domain.title()} Specialist",
            "opinion": f"Analysis for: {task_info['task']}. Recommendation: implement with best practices and proper testing."
        }
    
    return {
        "task": task_info["task"],
        "mode": "STANDARD",
        "opinions": opinions,
        "recommendation": f"Consilium: {task_info['task'][:30]}...",
        "routing": {
            "smart_routing": True,
            "confidence": round(confidence, 2),
            "domains_matched": len(domains),
        },
        "timing": {"agents_parallel": 10.0, "total": 12.0},
        "kb_retrieval": {"per_agent": {d: {"chunks_used": 2} for d in domains}}
    }


def main():
    print("="*60)
    print("DECISION CAPSULE TEST: 20 Tasks")
    print("="*60)
    
    # Сбрасываем circuit breaker для чистого теста
    cb = DirectorCircuitBreaker()
    cb.current_mode = "active"
    cb.metrics_history.clear()
    
    active_director = ActiveDirector(enabled=True)
    
    stats = {
        "total": 0,
        "director_calls": 0,
        "overrides": 0,
        "tokens_total": 0,
        "cost_total": 0.0,
        "latencies": []
    }
    
    for i, task_info in enumerate(TEST_TASKS, 1):
        print(f"\n[{i}/20] {task_info['task'][:45]}...")
        
        consilium_result = create_consilium_result(task_info, i)
        result = active_director.run_active_analysis(consilium_result)
        
        stats["total"] += 1
        
        active_info = result.get("active_director", {})
        
        if active_info.get("active_director_used"):
            stats["director_calls"] += 1
            
            metrics = active_info.get("metrics", {})
            tokens = metrics.get("total_tokens", 0)
            cost = metrics.get("total_cost", 0)
            
            # Вычисляем токены этого вызова
            if stats["director_calls"] > 1:
                prev_tokens = stats["tokens_total"]
                call_tokens = tokens - prev_tokens if tokens > prev_tokens else tokens
            else:
                call_tokens = tokens
            
            stats["tokens_total"] = tokens
            stats["cost_total"] = cost
            
            timing = active_info.get("timing", {})
            if timing.get("director_call"):
                stats["latencies"].append(timing["director_call"])
            
            if active_info.get("override_applied"):
                stats["overrides"] += 1
                print(f"   ✅ Override ({active_info.get('override_reason', '')[:30]})")
            else:
                print(f"   📝 Review only")
            
            # Показываем размер запроса
            request = active_info.get("director_request", {})
            summary_len = len(request.get("problem_summary", ""))
            facts_count = len(request.get("facts", []))
            agents_len = sum(len(v) for v in request.get("agent_summaries", {}).values())
            print(f"   📦 Capsule: summary={summary_len}ch, facts={facts_count}, agents={agents_len}ch")
        else:
            print(f"   ⏭️ Skipped")
    
    # Результаты
    print(f"\n{'='*60}")
    print("DECISION CAPSULE TEST RESULTS")
    print("="*60)
    
    avg_tokens = stats["tokens_total"] / max(stats["director_calls"], 1)
    avg_cost = stats["cost_total"] / max(stats["director_calls"], 1)
    avg_latency = sum(stats["latencies"]) / max(len(stats["latencies"]), 1)
    override_rate = stats["overrides"] / max(stats["director_calls"], 1)
    
    print(f"\n📊 KEY METRICS:")
    print(f"   Total tasks: {stats['total']}")
    print(f"   Director calls: {stats['director_calls']}")
    print(f"   Overrides: {stats['overrides']} ({override_rate:.1%})")
    print(f"   Avg tokens/call: {avg_tokens:.0f}")
    print(f"   Avg cost/call: ${avg_cost:.6f}")
    print(f"   Total cost: ${stats['cost_total']:.6f}")
    print(f"   Avg latency: {avg_latency:.2f}s")
    
    # Сравнение с предыдущим
    print(f"\n📈 COMPARISON (vs previous run):")
    print(f"   Tokens: 3114 → {avg_tokens:.0f} (target: 1200-1500)")
    print(f"   Cost/call: $0.000871 → ${avg_cost:.6f}")
    
    # Сохраняем результат
    summary = {
        "test_date": datetime.now().isoformat(),
        "test_type": "decision_capsule_validation",
        "total_tasks": stats["total"],
        "director_calls": stats["director_calls"],
        "overrides_applied": stats["overrides"],
        "override_rate": override_rate,
        "avg_tokens_per_call": round(avg_tokens, 0),
        "avg_cost_per_call": round(avg_cost, 6),
        "total_cost": round(stats["cost_total"], 6),
        "avg_latency": round(avg_latency, 2),
        "improvement": {
            "tokens_before": 3114,
            "tokens_after": round(avg_tokens, 0),
            "reduction_pct": round((1 - avg_tokens/3114) * 100, 1)
        }
    }
    
    os.makedirs("reports", exist_ok=True)
    with open("reports/capsule_test_20.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✅ Report saved to reports/capsule_test_20.json")


if __name__ == "__main__":
    main()