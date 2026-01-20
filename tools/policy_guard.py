#!/usr/bin/env python3
import json
from pathlib import Path

TEMPORAL_FILES = [
    Path("temporal.txt"),
    Path("data/reports/temporal.txt"),
]
PROMPT_PLAN = Path("data/reports/prompt_patch_plan.json")


def _temporal_hold() -> bool:
    for path in TEMPORAL_FILES:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "TEMPORAL_HOLD=true" in text:
                return True
            return False
    return False


def _prompt_deferred() -> bool:
    if not PROMPT_PLAN.exists():
        return False
    try:
        data = json.loads(PROMPT_PLAN.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return data.get("status") == "DEFERRED"


def main() -> None:
    temporal_hold = _temporal_hold()
    prompt_deferred = _prompt_deferred()

    if temporal_hold or prompt_deferred:
        print("PROMOTE_GATE: HOLD reason=temporal_or_deferred_patch")
        return

    if not any(p.exists() for p in TEMPORAL_FILES) and not PROMPT_PLAN.exists():
        print("PROMOTE_GATE: OK reason=missing_inputs")
        return

    print("PROMOTE_GATE: OK reason=stable")


if __name__ == "__main__":
    main()
