#!/usr/bin/env python3
import json
from pathlib import Path

TIMELINE_PATH = Path("data/reports/intelligence_timeline.jsonl")
TAXONOMY_PATH = Path("data/reports/eval_fails_taxonomy.jsonl")
TREND_PATH = Path("data/reports/decision_trend.txt")
ADAPTIVE_PATH = Path("data/reports/adaptive_threshold_state.json")
OUT_PATH = Path("data/reports/intelligence_report.md")


def _load_json_lines(path: Path) -> list:
    if not path.exists():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").rstrip("\n")


def main() -> None:
    timeline = _load_json_lines(TIMELINE_PATH)
    total_events = len(timeline)
    first_ts = timeline[0].get("ts_utc") if timeline else "unknown"
    last_ts = timeline[-1].get("ts_utc") if timeline else "unknown"
    arrow = "\u2192"

    taxonomy = _load_json_lines(TAXONOMY_PATH)
    fail_counts = {
        "infra": 0,
        "safety": 0,
        "instruction": 0,
        "reasoning": 0,
        "unknown": 0,
    }
    treatment_counts = {
        "lora_candidate": 0,
        "prompt_patch": 0,
        "infra_fix": 0,
        "ignore": 0,
    }
    for rec in taxonomy:
        ftype = rec.get("fail_type", "unknown")
        if ftype in fail_counts:
            fail_counts[ftype] += 1
        else:
            fail_counts["unknown"] += 1
        thint = rec.get("treatment_hint")
        if thint in treatment_counts:
            treatment_counts[thint] += 1

    trend_text = _load_text(TREND_PATH)
    if not trend_text.strip():
        trend_text = "unknown"

    adaptive_summary = {"base": "unknown", "effective": "unknown", "status": "unknown"}
    if ADAPTIVE_PATH.exists():
        try:
            adaptive = json.loads(ADAPTIVE_PATH.read_text(encoding="utf-8"))
            adaptive_summary = {
                "base": adaptive.get("base", "unknown"),
                "effective": adaptive.get("effective", "unknown"),
                "status": adaptive.get("status", "unknown"),
            }
        except json.JSONDecodeError:
            pass

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Intelligence Report",
        "",
        "## Summary",
        f"- total_events: {total_events}",
        f"- window: {first_ts} {arrow} {last_ts}",
        "",
        "## Decision Trend",
        trend_text,
        "",
        "## Fail Taxonomy (current window)",
        f"- infra: {fail_counts['infra']}",
        f"- safety: {fail_counts['safety']}",
        f"- instruction: {fail_counts['instruction']}",
        f"- reasoning: {fail_counts['reasoning']}",
        f"- unknown: {fail_counts['unknown']}",
        "",
        "## Treatment Signals",
        f"- lora_candidate: {treatment_counts['lora_candidate']}",
        f"- prompt_patch: {treatment_counts['prompt_patch']}",
        f"- infra_fix: {treatment_counts['infra_fix']}",
        f"- ignore: {treatment_counts['ignore']}",
        "",
        "## Adaptive Threshold",
        f"base={adaptive_summary['base']} effective={adaptive_summary['effective']} status={adaptive_summary['status']}",
        "",
        "## Notes",
        "- Generated automatically from intelligence timeline",
        "",
    ]
    report = "\n".join(lines)
    with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
        f.write(report)


if __name__ == "__main__":
    main()
