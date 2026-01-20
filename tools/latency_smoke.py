#!/usr/bin/env python3
import json
import math
from pathlib import Path

LOG_PATH = Path("data/decision_events.log")
TARGET_TYPE = "director_decision"
WINDOW = 20


def main() -> None:
    if not LOG_PATH.exists():
        print("LATENCY_P95_MS: NA")
        return
    latencies = []
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
        latency = event.get("latency_ms")
        if isinstance(latency, (int, float)):
            latencies.append(latency)
    if not latencies:
        print("LATENCY_P95_MS: NA")
        return
    window = latencies[-WINDOW:]
    window.sort()
    idx = max(0, math.ceil(0.95 * len(window)) - 1)
    p95 = window[idx]
    if isinstance(p95, float) and p95.is_integer():
        p95 = int(p95)
    print(f"LATENCY_P95_MS: {p95}")


if __name__ == "__main__":
    main()
