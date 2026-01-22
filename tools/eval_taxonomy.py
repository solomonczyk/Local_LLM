#!/usr/bin/env python3
import json
from pathlib import Path

FAILS_PATH = Path("data/reports/eval_fails.jsonl")
OUT_PATH = Path("data/reports/eval_fails_taxonomy.jsonl")


def _is_empty_response(response) -> bool:
    return not str(response or "").strip()


def _looks_like_instruction_anchor(expected) -> bool:
    if not isinstance(expected, str):
        return False
    anchor = expected.strip().lower()
    if anchor.startswith("def ") or anchor.startswith("class "):
        return True
    return "import " in anchor


def _is_safety_response(response: str) -> bool:
    text = response.lower()
    markers = [
        "i can't",
        "i cannot",
        "can't help",
        "not able to",
        "i won’t",
        "policy",
        "safety",
    ]
    return any(m in text for m in markers)


def main() -> None:
    if not FAILS_PATH.exists():
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text("", encoding="utf-8", newline="\n")
        print("TAXONOMY: infra=0 safety=0 instruction=0 reasoning=0 unknown=0")
        return

    lines = [
        ln for ln in FAILS_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    results = []
    counts = {
        "infra": 0,
        "safety": 0,
        "instruction": 0,
        "reasoning": 0,
        "unknown": 0,
    }
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = rec.get("response", "")
        expected = rec.get("expected", "")
        match_mode = rec.get("match_mode", "")

        fail_type = "unknown"
        fail_signal = "unclassified"
        if _is_empty_response(response):
            fail_type = "infra"
            fail_signal = "empty_response"
        elif _is_safety_response(str(response)):
            fail_type = "safety"
            fail_signal = "safety_marker"
        elif match_mode == "substring" and _looks_like_instruction_anchor(expected):
            fail_type = "instruction"
            fail_signal = "instruction_anchor"
        else:
            fail_type = "reasoning"
            fail_signal = "default_reasoning"

        if fail_type == "infra":
            treatment_hint = "infra_fix"
        elif fail_type in ("safety", "instruction"):
            treatment_hint = "prompt_patch"
        elif fail_type == "reasoning":
            treatment_hint = "lora_candidate"
        else:
            treatment_hint = "ignore"
        rec["fail_type"] = fail_type
        rec["fail_signal"] = fail_signal
        rec["treatment_hint"] = treatment_hint
        results.append(rec)
        counts[fail_type] += 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
        for rec in results:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(
        "TAXONOMY: "
        f"infra={counts['infra']} "
        f"safety={counts['safety']} "
        f"instruction={counts['instruction']} "
        f"reasoning={counts['reasoning']} "
        f"unknown={counts['unknown']}"
    )


if __name__ == "__main__":
    main()
