#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path


LOG_PATH = Path("data/decision_events.log")
TMP_PATH = Path("data/decision_events.log.tmp")


def _compute_event_id(event: dict) -> str:
    parts = [
        str(event.get("type", "")),
        str(event.get("decision", "")),
        str(event.get("next_step", "")),
        str(event.get("confidence", "")),
    ]
    payload = "|".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    if not LOG_PATH.exists():
        return

    TMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("r", encoding="utf-8") as src, TMP_PATH.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                dst.write(line)
                continue
            if "event_id" not in event:
                event["event_id"] = _compute_event_id(event)
            if "schema_version" not in event:
                event["schema_version"] = "1.0"
            dst.write(json.dumps(event, ensure_ascii=False) + "\n")

    TMP_PATH.replace(LOG_PATH)


if __name__ == "__main__":
    main()
