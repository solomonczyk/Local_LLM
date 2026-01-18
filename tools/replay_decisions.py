#!/usr/bin/env python3
import json
from pathlib import Path

LOG = Path("data/decision_events.log")

def main() -> None:
    if not LOG.exists():
        print("NO_LOG")
        return
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        ts = ev.get("ts")
        dtype = ev.get("type")
        decision = ev.get("decision", "")
        conf = ev.get("confidence")
        print(f"{ts} | {dtype} | conf={conf} | {decision}")

if __name__ == "__main__":
    main()
