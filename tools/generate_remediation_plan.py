#!/usr/bin/env python3
import json
import os
from pathlib import Path
from typing import List, Tuple

CATALOG_PATH = Path("tools/remediation_catalog.json")
OUTPUT_PATH = Path("data/reports/remediation_plan.json")


def parse_priority(text: str) -> List[Tuple[str, float]]:
    parts = [p for p in text.split() if p.strip()]
    items: List[Tuple[str, float]] = []
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if not key:
            continue
        try:
            impact = float(value)
        except ValueError:
            continue
        items.append((key, impact))
    items.sort(key=lambda item: (-item[1], item[0]))
    return items


def main() -> None:
    priority_raw = os.getenv("RCA_ACTION_PRIORITY", "").strip()
    plan = {"generated_from": "RCA_ACTION_PRIORITY", "items": []}
    if not priority_raw or not CATALOG_PATH.exists():
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
    for key, impact in parse_priority(priority_raw)[:2]:
        entry = catalog.get(key)
        if not isinstance(entry, dict):
            continue
        plan["items"].append(
            {
                "key": key,
                "impact": impact,
                "type": entry.get("type"),
                "title": entry.get("title"),
                "actions": entry.get("actions") or [],
                "owner": entry.get("owner"),
            }
        )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
