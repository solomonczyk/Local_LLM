#!/usr/bin/env python3
"""
Production Run: 50 задач с Active Director и Circuit Breaker
Генерирует агрегированный отчёт в reports/director_day1_summary.json
"""

import os
import json
import random
from datetime import datetime
from collections import defaultdict
from agent_system.active_director import ActiveDirector
from agent_system.director_circuit_breaker import circuit_breaker


# 50 реалистичных задач разных доменов
PRODUCTION_TASKS = [
    # Security (10 задач)
    {"task": "Implement JWT authentication with refresh tokens", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Add CSRF protection to all forms", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Implement rate limiting for login endpoint", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Add input validation for user registration", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Implement password hashing with bcrypt", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Add SQL injection protection", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Implement XSS sanitization", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Add API key rotation mechanism", "domains": ["security", "architect"], "risk": "high"},
    {"task": "Implement audit logging for sensitive operations", "domains": ["security", "dev"], "risk": "high"},
    {"task": "Add two-factor authentication", "domains": ["security", "dev", "ux"], "risk": "high"},
    
    # Architecture (8 задач)
    {"task": "Design microservices communication pattern", "domains": ["architect", "dev"], "risk": "medium"},
    {"task": "Create database migration for user roles", "domains": ["architect", "dev", "security"], "risk": "high"},
    {"task": "Design caching strategy for API responses", "domains": ["architect", "dev"], "risk": "medium"},
    {"task": "Plan horizontal scaling architecture", "domains": ["architect"], "risk": "medium"},
    {"task": "Design event-driven notification system", "domains": ["architect", "dev"], "risk": "medium"},
    {"task": "Create data backup and recovery plan", "domains": ["architect", "security"], "risk": "high"},
    {"task": "Design API versioning strategy", "domains": ["architect", "dev"], "risk": "medium"},
    {"task": "Plan database sharding approach", "domains": ["architect", "dev"], "risk": "high"},
    
    # Dev (15 задач)
    {"task": "Implement user profile CRUD operations", "domains": ["dev"], "risk": "low"},
    {"task": "Add pagination to list endpoints", "domains": ["dev"], "risk": "low"},
    {"task": "Implement file upload functionality", "domains": ["dev", "security"], "risk": "medium"},
    {"task": "Create email notification service", "domains": ["dev"], "risk": "low"},
    {"task": "Add search functionality with filters", "domains": ["dev"], "risk": "low"},
    {"task": "Implement webhook handlers", "domains": ["dev", "security"], "risk": "medium"},
    {"task": "Create data export to CSV/Excel", "domains": ["dev"], "risk": "low"},
    {"task": "Add real-time updates with WebSocket", "domains": ["dev", "architect"], "risk": "medium"},
    {"task": "Implement batch processing for reports", "domains": ["dev"], "risk": "low"},
    {"task": "Create admin dashboard API", "domains": ["dev", "security"], "risk": "medium"},
    {"task": "Add logging and monitoring endpoints", "domains": ["dev"], "risk": "low"},
    {"task": "Implement data import from external API", "domains": ["dev"], "risk": "low"},
    {"task": "Create scheduled task runner", "domains": ["dev"], "risk": "low"},
    {"task": "Add configuration management", "domains": ["dev"], "risk": "low"},
    {"task": "Implement feature flags system", "domains": ["dev", "architect"], "risk": "medium"},
    
    # QA (8 задач)
    {"task": "Write unit tests for user service", "domains": ["qa", "dev"], "risk": "low"},
    {"task": "Create integration tests for API", "domains": ["qa", "dev"], "risk": "low"},
    {"task": "Add end-to-end tests for checkout flow", "domains": ["qa", "dev"], "risk": "low"},
    {"task": "Implement load testing suite", "domains": ["qa", "architect"], "risk": "medium"},
    {"task": "Create test data generators", "domains": ["qa", "dev"], "risk": "low"},
    {"task": "Add code coverage reporting", "domains": ["qa", "dev"], "risk": "low"},
    {"task": "Implement smoke tests for deployment", "domains": ["qa", "dev"], "risk": "low"},
    {"task": "Create regression test suite", "domains": ["qa", "dev"], "risk": "low"},
    
    # UX (5 задач)
    {"task": "Fix button alignment on mobile", "domains": ["ux", "dev"], "risk": "low"},
    {"task": "Improve form validation UX", "domains": ["ux", "dev"], "risk": "low"},
    {"task": "Add loading states to async operations", "domains": ["ux", "dev"], "risk": "low"},
    {"task": "Create user onboarding flow", "domains": ["ux", "dev", "qa"], "risk": "medium"},
    {"task": "Improve error messages clarity", "domains": ["ux", "dev"], "risk": "low"},
    
    # SEO (4 задачи)
    {"task": "Add meta tags for SEO", "domains": ["seo", "dev"], "risk": "low"},
    {"task": "Create sitemap generator", "domains": ["seo", "dev"], "risk": "low"},
    {"task": "Implement structured data markup", "domains": ["seo", "dev"], "risk": "low"},
    {"task": "Add canonical URLs", "domains": ["seo", "dev"], "risk": "low"},
]


def create_consilium_result(task_info: dict, task_id: int) -> dict:
    """Создаёт реалистичный результат consilium"""
    
    domains = task_info["domains"]
    risk = task_info["risk"]
    
    # Confidence зависит от риска и количества доменов
    base_confidence = {"low": 0.85, "medium": 0.75, "high": 0.65}[risk]
    confidence = base_confidence + random.uniform(-0.05, 0.05)
    confidence = max(0.5, min(0.95, confidence))
    
    opinions = {}
    for domain in domains:
        opinions[domain] = {
            "role": f"{domain.title()} Specialist",
            "opinion": f"Analysis for task: {task_info['task'][:40]}... Recommendation: proceed with standard practices."
        }
    
    return {
        "task": task_info["task"],
        "mode": "STANDARD" if len(domains) > 1 else "FAST",
        "opinions": opinions,
        "director_decision": None,
        "recommendation": f"Consilium recommendation for: {task_info['task'][:30]}...",
        "routing": {
            "smart_routing": True,
            "confidence": round(confidence, 2),
            "domains_matched": len(domains),
            "triggers_matched": {d: ["task_trigger"] for d in domains},
            "downgraded": False,
            "reason": f"Task involves {', '.join(domains)}"
        },
        "timing": {
            "agents_parallel": 8.0 + random.uniform(0, 4),
            "director": 0.0,
            "total": 10.0 + random.uniform(0, 5)
        },
        "kb_retrieval": {
            "config": {"top_k": 3, "max_chars": 6000},
            "per_agent": {d: {"chunks_used": 2, "chars_used": 800} for d in domains}
        }
    }


def run_production_50():
    """Запускает 50 production задач"""
    
    print("="*60)
    print("PRODUCTION RUN: 50 Tasks with Active Director")
    print("="*60)
    
    # Проверяем настройки
    director_mode = os.getenv("DIRECTOR_MODE", "off")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    
    print(f"Director Mode: {director_mode}")
    print(f"OpenAI Key: {'Set' if openai_key else 'Missing'}")
    print(f"Circuit Breaker Mode: {circuit_breaker.current_mode}")
    
    if not openai_key:
        print("❌ OpenAI API key not set")
        return None
    
    # Инициализируем Active Director
    active_director = ActiveDirector(enabled=True)
    
    # Статистика
    stats = {
        "total_tasks": 0,
        "director_calls": 0,
        "overrides_applied": 0,
        "mode_changes": [],
        "tokens_total": 0,
        "cost_total": 0.0,
        "override_reasons": defaultdict(int),
        "domain_breakdown": defaultdict(lambda: {"tasks": 0, "director_calls": 0, "overrides": 0}),
        "errors": 0,
        "latencies": []
    }
    
    # Перемешиваем задачи для реалистичности
    tasks = PRODUCTION_TASKS.copy()
    random.shuffle(tasks)
    
    initial_mode = circuit_breaker.current_mode
    
    for i, task_info in enumerate(tasks, 1):
        print(f"\n[{i}/50] {task_info['task'][:50]}...")
        
        try:
            # Создаём consilium результат
            consilium_result = create_consilium_result(task_info, i)
            
            # Запускаем active director
            result = active_director.run_active_analysis(consilium_result)
            
            stats["total_tasks"] += 1
            
            # Обновляем domain breakdown
            for domain in task_info["domains"]:
                stats["domain_breakdown"][domain]["tasks"] += 1
            
            # Анализируем результат
            active_info = result.get("active_director", {})
            
            if active_info.get("active_director_used"):
                stats["director_calls"] += 1
                
                for domain in task_info["domains"]:
                    stats["domain_breakdown"][domain]["director_calls"] += 1
                
                # Метрики
                metrics = active_info.get("metrics", {})
                stats["tokens_total"] += metrics.get("total_tokens", 0)
                stats["cost_total"] += metrics.get("total_cost", 0)
                
                timing = active_info.get("timing", {})
                if timing.get("director_call"):
                    stats["latencies"].append(timing["director_call"])
                
                # Override
                if active_info.get("override_applied"):
                    stats["overrides_applied"] += 1
                    reason = active_info.get("override_reason", "unknown")
                    # Извлекаем основную причину
                    main_reason = reason.split(" ")[0] if reason else "unknown"
                    stats["override_reasons"][main_reason] += 1
                    
                    for domain in task_info["domains"]:
                        stats["domain_breakdown"][domain]["overrides"] += 1
                    
                    print(f"   ✅ Override: {reason[:40]}")
                else:
                    print(f"   📝 Review only")
            else:
                reason = active_info.get("reason", "unknown")
                print(f"   ⏭️ Skipped: {reason}")
            
            # Проверяем mode changes
            current_mode = circuit_breaker.current_mode
            if current_mode != initial_mode:
                stats["mode_changes"].append({
                    "task_id": i,
                    "from": initial_mode,
                    "to": current_mode,
                    "reason": "circuit_breaker_triggered"
                })
                initial_mode = current_mode
                print(f"   ⚠️ MODE CHANGE: {stats['mode_changes'][-1]}")
                
        except Exception as e:
            stats["errors"] += 1
            print(f"   ❌ Error: {e}")
    
    return stats


def generate_summary_report(stats: dict) -> dict:
    """Генерирует агрегированный отчёт"""
    
    if not stats:
        return None
    
    # Вычисляем средние значения
    avg_tokens = stats["tokens_total"] / max(stats["director_calls"], 1)
    avg_cost = stats["cost_total"] / max(stats["director_calls"], 1)
    avg_latency = sum(stats["latencies"]) / max(len(stats["latencies"]), 1)
    override_rate = stats["overrides_applied"] / max(stats["director_calls"], 1)
    
    # Топ-3 причины override
    top_reasons = sorted(stats["override_reasons"].items(), key=lambda x: -x[1])[:3]
    
    # Domain breakdown
    domain_stats = {}
    for domain, data in stats["domain_breakdown"].items():
        domain_stats[domain] = {
            "tasks": data["tasks"],
            "director_calls": data["director_calls"],
            "overrides": data["overrides"],
            "override_rate": data["overrides"] / max(data["director_calls"], 1)
        }
    
    summary = {
        "report_date": datetime.now().isoformat(),
        "report_type": "director_day1_summary",
        
        "totals": {
            "total_tasks": stats["total_tasks"],
            "director_calls": stats["director_calls"],
            "overrides_applied": stats["overrides_applied"],
            "errors": stats["errors"]
        },
        
        "rates": {
            "director_usage_rate": stats["director_calls"] / max(stats["total_tasks"], 1),
            "override_rate": override_rate
        },
        
        "mode_changes": {
            "count": len(stats["mode_changes"]),
            "events": stats["mode_changes"]
        },
        
        "economics": {
            "total_tokens": stats["tokens_total"],
            "avg_tokens_per_call": round(avg_tokens, 1),
            "total_cost_usd": round(stats["cost_total"], 6),
            "avg_cost_per_call_usd": round(avg_cost, 6),
            "daily_cost_projection_usd": round(stats["cost_total"], 4)
        },
        
        "performance": {
            "avg_latency_sec": round(avg_latency, 2),
            "min_latency_sec": round(min(stats["latencies"]) if stats["latencies"] else 0, 2),
            "max_latency_sec": round(max(stats["latencies"]) if stats["latencies"] else 0, 2)
        },
        
        "top_override_reasons": [
            {"reason": r[0], "count": r[1]} for r in top_reasons
        ],
        
        "domain_breakdown": domain_stats,
        
        "circuit_breaker": {
            "final_mode": circuit_breaker.current_mode,
            "status": circuit_breaker.get_current_status()
        }
    }
    
    return summary


def main():
    """Main entry point"""
    
    # Запускаем production run
    stats = run_production_50()
    
    if not stats:
        print("❌ Production run failed")
        return
    
    # Генерируем отчёт
    summary = generate_summary_report(stats)
    
    # Создаём директорию reports
    os.makedirs("reports", exist_ok=True)
    
    # Сохраняем отчёт
    report_path = "reports/director_day1_summary.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print("PRODUCTION RUN COMPLETE")
    print("="*60)
    print(f"Report saved to: {report_path}")
    
    # Выводим ключевые метрики
    print(f"\n📊 KEY METRICS:")
    print(f"   Total tasks: {summary['totals']['total_tasks']}")
    print(f"   Director calls: {summary['totals']['director_calls']}")
    print(f"   Override rate: {summary['rates']['override_rate']:.1%}")
    print(f"   Mode changes: {summary['mode_changes']['count']}")
    print(f"   Avg tokens/call: {summary['economics']['avg_tokens_per_call']}")
    print(f"   Avg cost/call: ${summary['economics']['avg_cost_per_call_usd']:.6f}")
    print(f"   Daily cost: ${summary['economics']['daily_cost_projection_usd']:.4f}")
    print(f"   Avg latency: {summary['performance']['avg_latency_sec']}s")
    
    print(f"\n🎯 TOP OVERRIDE REASONS:")
    for r in summary['top_override_reasons']:
        print(f"   {r['reason']}: {r['count']}")
    
    print(f"\n📁 DOMAIN BREAKDOWN:")
    for domain, data in sorted(summary['domain_breakdown'].items()):
        print(f"   {domain}: {data['tasks']} tasks, {data['director_calls']} calls, {data['overrides']} overrides")
    
    print(f"\n🔒 CIRCUIT BREAKER: {summary['circuit_breaker']['final_mode']}")


if __name__ == "__main__":
    main()