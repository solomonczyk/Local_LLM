#!/usr/bin/env python3
import json
from pathlib import Path

LOG_PATH = Path("data/decision_events.log")
OUT_PATH = Path("data/reports/prompt_patch_plan.json")
TEMPORAL_FILE = Path("temporal.txt")


def _num(value):
    return value if isinstance(value, (int, float)) else None


def _is_low_or_bad(event: dict) -> bool:
    score = _num(event.get("score"))
    confidence = _num(event.get("confidence"))
    if score is not None and score < 0.6:
        return True
    if confidence is not None and confidence < 0.6:
        return True
    return False


def _load_latest_trigger():
    if not LOG_PATH.exists():
        return None
    lines = [
        ln for ln in LOG_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "director_decision":
            continue
        if _is_low_or_bad(event):
            return event
    return None


def _temporal_state():
    if TEMPORAL_FILE.exists():
        text = TEMPORAL_FILE.read_text(encoding="utf-8", errors="ignore")
        if "TEMPORAL_HOLD=true" in text:
            return "HOLD"
        return "OK"
    return "UNKNOWN"


def main() -> None:
    temporal_state = _temporal_state()
    trigger_event = _load_latest_trigger()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not trigger_event:
        payload = {
            "status": "NO_ACTION",
            "reason": "no_bad_or_low_decision",
            "temporal_state": temporal_state,
        }
        with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return

    trigger_id = (
        trigger_event.get("event_id")
        or trigger_event.get("id")
        or str(trigger_event.get("ts"))
    )
    reason = "Low confidence or bad decision detected"
    if temporal_state == "HOLD":
        status = "DEFERRED"
    else:
        status = "READY"

    payload = {
        "patch_type": "prompt_adjustment",
        "trigger_event_id": trigger_id,
        "reason": reason,
        "suggested_change": (
            "Increase requirement for explicit assumptions and edge-case enumeration"
        ),
        "mode": "SOFT",
        "apply": False,
        "temporal_state": temporal_state,
        "status": status,
    }
    with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
