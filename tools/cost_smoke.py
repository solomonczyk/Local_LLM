#!/usr/bin/env python3
import json
import math
from pathlib import Path

LOG_PATH = Path("data/decision_events.log")
TARGET_TYPE = "director_decision"
WINDOW = 20


def main() -> None:
    if not LOG_PATH.exists():
        print("TOKENS_P95: NA")
        print("TOKENS_STATUS: SKIP")
        print("TOKENS_GATE: PASS")
        return
    tokens = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != TARGET_TYPE:
            continue
        total_tokens = event.get("total_tokens")
        if isinstance(total_tokens, (int, float)) and total_tokens > 0:
            tokens.append(total_tokens)
    if not tokens:
        print("TOKENS_P95: NA")
        print("TOKENS_STATUS: SKIP")
        print("TOKENS_GATE: PASS")
        return
    window = tokens[-WINDOW:]
    window.sort()
    idx = max(0, math.ceil(0.95 * len(window)) - 1)
    p95 = window[idx]
    if isinstance(p95, float) and p95.is_integer():
        p95 = int(p95)
    print(f"TOKENS_P95: {p95}")
    if p95 <= 1200:
        print("TOKENS_STATUS: OK")
        print("TOKENS_GATE: PASS")
    elif p95 <= 2500:
        print("TOKENS_STATUS: WARN")
        print("TOKENS_GATE: PASS")
    else:
        print("TOKENS_STATUS: BAD")
        print("TOKENS_GATE: SOFT (high_tokens)")


if __name__ == "__main__":
    main()
