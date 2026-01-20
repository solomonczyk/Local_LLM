#!/usr/bin/env python3
import json
from pathlib import Path

SIGNAL_PATH = Path("data/reports/temporal_signal.json")
OUT_PATH = Path("data/reports/treatment_decision.json")


def main() -> None:
    trend = "insufficient_data"
    reason = "unknown"
    if SIGNAL_PATH.exists():
        try:
            data = json.loads(SIGNAL_PATH.read_text(encoding="utf-8"))
            trend = data.get("trend", trend)
            reason = data.get("reason", reason)
        except json.JSONDecodeError:
            pass

    action = "ignore"
    mode = "SILENT"
    if trend == "degrading":
        action = "prompt_patch"
        mode = "PREPARE_ONLY"
    elif trend == "drift":
        action = "expand_eval"
        mode = "PREPARE_ONLY"
    elif trend == "stale":
        action = "ignore"
        mode = "SILENT"

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "action": action,
        "mode": mode,
        "reason": reason,
        "source_trend": trend,
    }
    with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    if action == "expand_eval":
        plan_path = Path("data/reports/treatment_plan.md")
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_text = "\n".join(
            [
                "PLAN: expand_eval",
                "WHY: intelligence drift (backend/lora/git changed, metrics unchanged)",
                "NEXT: add 3 new HIGH-risk eval cases targeting backend differences",
            ]
        )
        with plan_path.open("w", encoding="utf-8", newline="\n") as f:
            f.write(plan_text)

        suggestions_path = Path("data/reports/eval_case_suggestions.json")
        suggestions_path.parent.mkdir(parents=True, exist_ok=True)
        suggestions = {
            "suggested_cases": [
                {
                    "id": "E11",
                    "risk_level": "HIGH",
                    "topic": "config precedence",
                    "goal": "detect backend selection conflicts",
                },
                {
                    "id": "E12",
                    "risk_level": "HIGH",
                    "topic": "timeout/latency mode",
                    "goal": "ensure conservative policy triggers",
                },
                {
                    "id": "E13",
                    "risk_level": "HIGH",
                    "topic": "token economy mode",
                    "goal": "ensure cost policy triggers",
                },
            ]
        }
        with suggestions_path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(suggestions, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
