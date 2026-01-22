#!/usr/bin/env python3
import json
from pathlib import Path

LOG_PATH = Path("data/decision_events.log")


def _num(value):
    return value if isinstance(value, (int, float)) else None


def _event_score(event: dict):
    score = _num(event.get("effective_score"))
    if score is not None:
        return score
    return _num(event.get("score"))


def main() -> None:
    if not LOG_PATH.exists():
        print("TEMPORAL: w5=NA w20=NA stability=SKIP anti_flap=SKIP")
        return

    values = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "director_decision":
            continue
        if event.get("synthetic") is True:
            continue
        score = _event_score(event)
        if score is None:
            continue
        values.append(score)

    if len(values) < 5:
        print("TEMPORAL: w5=NA w20=NA stability=SKIP anti_flap=SKIP")
        return

    w5_vals = values[-5:]
    w20_vals = values[-min(20, len(values)) :]

    w5 = sum(w5_vals) / len(w5_vals)
    w20 = sum(w20_vals) / len(w20_vals)

    stability = "STABLE" if abs(w5 - w20) <= 0.03 else "UNSTABLE"
    anti_flap = "OK" if stability == "STABLE" else "HOLD"

    print(
        f"TEMPORAL: w5={w5:.2f} w20={w20:.2f} stability={stability} anti_flap={anti_flap}"
    )
    if anti_flap == "HOLD":
        print("TEMPORAL_HOLD=true")


if __name__ == "__main__":
    main()
