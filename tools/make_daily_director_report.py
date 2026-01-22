#!/usr/bin/env python3
"""
Daily Director Report Generator
Читает логи и генерирует ежедневный отчёт в Markdown
"""

import json
import os
import statistics
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional


def load_jsonl(filepath: str) -> List[Dict]:
    """Загружает JSONL файл"""
    if not os.path.exists(filepath):
        return []
    
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return entries


def filter_by_date(entries: List[Dict], target_date: date) -> List[Dict]:
    """Фильтрует записи по дате"""
    filtered = []
    target_str = target_date.strftime("%Y-%m-%d")
    
    for entry in entries:
        timestamp = entry.get("timestamp", "")
        if timestamp.startswith(target_str):
            filtered.append(entry)
    
    return filtered


def calculate_percentile(values: List[float], percentile: int) -> float:
    """Вычисляет перцентиль"""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int(len(sorted_values) * percentile / 100)
    return sorted_values[min(index, len(sorted_values) - 1)]


def analyze_active_director_logs(entries: List[Dict]) -> Dict[str, Any]:
    """Анализирует логи active_director.jsonl"""
    
    stats = {
        "total_tasks": len(entries),
        "director_calls": 0,
        "overrides_applied": 0,
        "overrides_with_positive_diff": 0,  # For override_precision
        "missed_overrides": 0,  # For missed_override_rate
        "tokens_list": [],
        "costs_list": [],
        "latencies": [],
        "override_reasons": defaultdict(int),
        "domain_breakdown": defaultdict(lambda: {"calls": 0, "overrides": 0}),
        "errors": 0
    }
    
    for entry in entries:
        active = entry.get("active_director", {})
        
        if active.get("active_director_used"):
            stats["director_calls"] += 1
            
            # Метрики
            metrics = active.get("metrics", {})
            if metrics.get("total_tokens"):
                # Берём токены последнего вызова
                stats["tokens_list"].append(metrics.get("total_tokens", 0))
            if metrics.get("total_cost"):
                stats["costs_list"].append(metrics.get("total_cost", 0))
            
            timing = active.get("timing", {})
            if timing.get("director_call"):
                stats["latencies"].append(timing["director_call"])
            
            # Override
            if active.get("override_applied"):
                stats["overrides_applied"] += 1
                reason = active.get("override_reason", "unknown")
                main_reason = reason.split(" ")[0] if reason else "unknown"
                stats["override_reasons"][main_reason] += 1
                
                # Override precision: count overrides where director_confidence > consilium_confidence
                comparison = entry.get("comparison", {})
                conf_diff = comparison.get("confidence_diff", 0)
                if conf_diff is None:
                    conf_diff = 0
                if conf_diff > 0:
                    stats["overrides_with_positive_diff"] += 1
            else:
                # Missed override: director called but not applied, yet diff >= 0.10
                comparison = entry.get("comparison", {})
                conf_diff = comparison.get("confidence_diff", 0)
                if conf_diff is None:
                    conf_diff = 0
                if conf_diff >= 0.10:  # diff_gte threshold
                    stats["missed_overrides"] += 1
            
            # Domains
            agents = entry.get("consilium_agents", [])
            for domain in agents:
                stats["domain_breakdown"][domain]["calls"] += 1
                if active.get("override_applied"):
                    stats["domain_breakdown"][domain]["overrides"] += 1
        
        if active.get("error"):
            stats["errors"] += 1
    
    return stats


def analyze_circuit_breaker_logs(entries: List[Dict]) -> Dict[str, Any]:
    """Анализирует логи director_circuit_breaker.jsonl"""
    
    mode_changes = []
    
    for entry in entries:
        if entry.get("event") == "director_mode_change":
            mode_changes.append({
                "timestamp": entry.get("timestamp", ""),
                "from": entry.get("old_mode", ""),
                "to": entry.get("new_mode", ""),
                "reason": entry.get("reason", "")
            })
    
    return {
        "mode_changes": mode_changes,
        "mode_changes_count": len(mode_changes)
    }


def analyze_task_run_logs(entries: List[Dict]) -> Dict[str, Any]:
    """Анализирует логи task_run.jsonl для missed overrides by reason"""
    
    stats = {
        "total_tasks": len(entries),
        "director_calls": 0,
        "missed_shadow_mode": 0,
        "missed_risk_gate": 0,
        "soft_override_candidates": 0,
        "shadow_mode_calls": 0,  # count where override_reason == "shadow_mode"
        "shadow_soft_allow_candidates": 0  # count where shadow_soft_allow_candidate == true
    }
    
    for entry in entries:
        director = entry.get("director", {})
        
        if director.get("called"):
            stats["director_calls"] += 1
            
            override_reason = director.get("override_reason", "")
            
            # Count shadow_mode calls
            if override_reason == "shadow_mode":
                stats["shadow_mode_calls"] += 1
            
            # Count shadow_soft_allow_candidates
            if director.get("shadow_soft_allow_candidate"):
                stats["shadow_soft_allow_candidates"] += 1
            
            if director.get("soft_override_candidate"):
                stats["soft_override_candidates"] += 1
                
                if override_reason == "shadow_mode":
                    stats["missed_shadow_mode"] += 1
                elif "gate_denied" in override_reason or "risk_condition=false" in override_reason:
                    stats["missed_risk_gate"] += 1
    
    return stats


def generate_markdown_report(
    report_date: date,
    active_stats: Dict[str, Any],
    cb_stats: Dict[str, Any],
    task_run_stats: Dict[str, Any]
) -> str:
    """Генерирует Markdown отчёт"""
    
    # Вычисляем агрегаты
    total_tasks = active_stats["total_tasks"]
    director_calls = active_stats["director_calls"]
    overrides = active_stats["overrides_applied"]
    override_rate = overrides / max(director_calls, 1)
    
    # Override precision: % overrides where director was actually more confident
    overrides_positive = active_stats.get("overrides_with_positive_diff", 0)
    override_precision = overrides_positive / max(overrides, 1)
    
    # Missed override rate: % calls where director was better but we didn't override
    missed_overrides = active_stats.get("missed_overrides", 0)
    missed_override_rate = missed_overrides / max(director_calls, 1)
    
    # Missed overrides by reason (from task_run.jsonl)
    missed_shadow = task_run_stats.get("missed_shadow_mode", 0)
    missed_risk_gate = task_run_stats.get("missed_risk_gate", 0)
    task_run_director_calls = task_run_stats.get("director_calls", 1)
    missed_shadow_pct = missed_shadow / max(task_run_director_calls, 1) * 100
    missed_risk_gate_pct = missed_risk_gate / max(task_run_director_calls, 1) * 100
    
    # Shadow soft-allow rate
    shadow_mode_calls = task_run_stats.get("shadow_mode_calls", 0)
    shadow_soft_allow = task_run_stats.get("shadow_soft_allow_candidates", 0)
    shadow_soft_allow_rate = shadow_soft_allow / max(shadow_mode_calls, 1) * 100
    
    tokens = active_stats["tokens_list"]
    avg_tokens = statistics.mean(tokens) if tokens else 0
    p50_tokens = calculate_percentile(tokens, 50)
    p95_tokens = calculate_percentile(tokens, 95)
    
    costs = active_stats["costs_list"]
    daily_cost = max(costs) if costs else 0  # Берём последнее значение (кумулятивное)
    avg_cost = daily_cost / max(director_calls, 1)
    
    latencies = active_stats["latencies"]
    avg_latency = statistics.mean(latencies) if latencies else 0
    p50_latency = calculate_percentile(latencies, 50)
    p95_latency = calculate_percentile(latencies, 95)
    
    # Топ-5 причин override
    top_reasons = sorted(
        active_stats["override_reasons"].items(),
        key=lambda x: -x[1]
    )[:5]
    
    # Domain breakdown
    domains = dict(active_stats["domain_breakdown"])
    
    # Mode changes
    mode_changes = cb_stats.get("mode_changes", [])
    
    # Генерируем отчёт
    report = f"""# 📊 Director Daily Report: {report_date.strftime("%Y-%m-%d")}

## 📈 Summary

| Metric | Value |
|--------|-------|
| Total Tasks | {total_tasks} |
| Director Calls | {director_calls} ({director_calls/max(total_tasks,1)*100:.1f}% usage) |
| Overrides Applied | {overrides} |
| Override Rate | {override_rate:.1%} |
| Override Precision | {override_precision:.1%} |
| Missed Override Rate | {missed_override_rate:.1%} |
| Missed Overrides (shadow_mode) | {missed_shadow} ({missed_shadow_pct:.1f}%) |
| Missed Overrides (risk_gate) | {missed_risk_gate} ({missed_risk_gate_pct:.1f}%) |
| Shadow Soft-Allow Rate | {shadow_soft_allow}/{shadow_mode_calls} ({shadow_soft_allow_rate:.1f}%) |
| Errors | {active_stats['errors']} |

## 💰 Economics

| Metric | Value |
|--------|-------|
| Daily Cost | ${daily_cost:.6f} |
| Avg Cost/Call | ${avg_cost:.6f} |
| Budget Status | {'✅ Under $0.01' if daily_cost < 0.01 else '⚠️ Over budget'} |

## 🎯 Tokens

| Metric | Value |
|--------|-------|
| Avg Tokens/Call | {avg_tokens:.0f} |
| P50 Tokens | {p50_tokens:.0f} |
| P95 Tokens | {p95_tokens:.0f} |
| Target | 1200-1500 |
| Status | {'✅ Under target' if avg_tokens < 1500 else '⚠️ Over target'} |

## ⏱️ Latency

| Metric | Value |
|--------|-------|
| Avg Latency | {avg_latency:.2f}s |
| P50 Latency | {p50_latency:.2f}s |
| P95 Latency | {p95_latency:.2f}s |
| Limit | 6.0s |
| Status | {'✅ OK' if avg_latency < 6 else '⚠️ High'} |

## 🔄 Mode Changes ({len(mode_changes)})

"""
    
    if mode_changes:
        report += "| Time | From | To | Reason |\n|------|------|----|---------|\n"
        for mc in mode_changes:
            time_short = mc["timestamp"].split("T")[-1][:8] if "T" in mc["timestamp"] else mc["timestamp"][-8:]
            reason_short = mc["reason"][:40] + "..." if len(mc["reason"]) > 40 else mc["reason"]
            report += f"| {time_short} | {mc['from']} | {mc['to']} | {reason_short} |\n"
    else:
        report += "_No mode changes today_\n"
    
    report += """
## 🎯 Top Override Reasons

"""
    
    if top_reasons:
        report += "| Reason | Count | % |\n|--------|-------|---|\n"
        for reason, count in top_reasons:
            pct = count / max(overrides, 1) * 100
            report += f"| {reason} | {count} | {pct:.0f}% |\n"
    else:
        report += "_No overrides today_\n"
    
    report += """
## 📁 Domain Breakdown

| Domain | Calls | Overrides | Override Rate |
|--------|-------|-----------|---------------|
"""
    
    for domain in sorted(domains.keys()):
        data = domains[domain]
        calls = data["calls"]
        ovr = data["overrides"]
        rate = ovr / max(calls, 1)
        report += f"| {domain} | {calls} | {ovr} | {rate:.0%} |\n"
    
    report += f"""
---

## 🔒 Health Status

"""
    
    # Health checks
    health_issues = []
    if override_rate > 0.75:
        health_issues.append("⚠️ Override rate > 75%")
    if daily_cost > 0.01:
        health_issues.append("⚠️ Daily cost > $0.01")
    if avg_latency > 6:
        health_issues.append("⚠️ Avg latency > 6s")
    if active_stats["errors"] > 0:
        health_issues.append(f"⚠️ {active_stats['errors']} errors")
    if len(mode_changes) > 2:
        health_issues.append(f"⚠️ {len(mode_changes)} mode changes (possible flapping)")
    
    if health_issues:
        report += "### Issues Detected:\n"
        for issue in health_issues:
            report += f"- {issue}\n"
    else:
        report += "### ✅ All systems healthy\n"
    
    report += f"""
---
_Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}_
"""
    
    return report


def main():
    """Main entry point"""
    
    # Определяем дату отчёта (сегодня)
    report_date = date.today()
    
    print(f"📊 Generating Director Daily Report for {report_date}")
    
    # Загружаем логи
    active_logs = load_jsonl("active_director.jsonl")
    cb_logs = load_jsonl("director_circuit_breaker.jsonl")
    task_run_logs = load_jsonl("task_run.jsonl")
    
    print(f"   Loaded {len(active_logs)} active director entries")
    print(f"   Loaded {len(cb_logs)} circuit breaker entries")
    print(f"   Loaded {len(task_run_logs)} task run entries")
    
    # Фильтруем по дате
    active_today = filter_by_date(active_logs, report_date)
    cb_today = filter_by_date(cb_logs, report_date)
    task_run_today = filter_by_date(task_run_logs, report_date)
    
    print(f"   Today's entries: {len(active_today)} active, {len(cb_today)} circuit breaker, {len(task_run_today)} task run")
    
    if not active_today:
        print("⚠️ No entries for today, using all available data")
        active_today = active_logs
        cb_today = cb_logs
        task_run_today = task_run_logs
    
    # Анализируем
    active_stats = analyze_active_director_logs(active_today)
    cb_stats = analyze_circuit_breaker_logs(cb_today)
    task_run_stats = analyze_task_run_logs(task_run_today)
    
    # Генерируем отчёт
    report = generate_markdown_report(report_date, active_stats, cb_stats, task_run_stats)
    
    # Сохраняем
    os.makedirs("reports", exist_ok=True)
    report_path = f"reports/director_daily_{report_date.strftime('%Y-%m-%d')}.md"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ Report saved to {report_path}")
    
    # Выводим отчёт
    print("\n" + "="*60)
    print(report)
    
    return report_path


if __name__ == "__main__":
    main()