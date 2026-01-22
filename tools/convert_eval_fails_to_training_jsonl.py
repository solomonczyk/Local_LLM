#!/usr/bin/env python3
import json
from pathlib import Path

FAILS_PATH = Path("data/reports/eval_fails.jsonl")
OUT_PATH = Path("data/reports/training_dataset.jsonl")


def _normalize_expected(expected) -> str:
    if isinstance(expected, list):
        return " OR ".join(str(e) for e in expected)
    if isinstance(expected, str):
        return expected
    return ""


def main() -> None:
    if not FAILS_PATH.exists():
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
            f.write("")
        return

    lines = [
        ln for ln in FAILS_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    if not lines:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
            f.write("")
        return

    records = []
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        prompt = rec.get("input", "")
        expected = _normalize_expected(rec.get("expected"))
        records.append(
            {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a coding assistant. Fix the failure by producing "
                            "an answer that satisfies the expected criteria."
                        ),
                    },
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": expected},
                ]
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
