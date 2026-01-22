#!/usr/bin/env python3
import json
import re
import time
from pathlib import Path

MANIFEST_PATH = Path("data/reports/intelligence_manifest.json")
EVAL_PATH = Path("data/reports/minimal_eval.txt")
OUT_PATH = Path("data/reports/intelligence_timeline.jsonl")


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _load_eval() -> tuple:
    if not EVAL_PATH.exists():
        return -1, -1
    text = EVAL_PATH.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"EVAL:\s*pass=(\d+)\s+fail=(\d+)", text)
    if not match:
        return -1, -1
    return int(match.group(1)), int(match.group(2))


def main() -> None:
    manifest = _load_manifest()
    eval_pass, eval_fail = _load_eval()
    record = {
        "ts_utc": int(time.time()),
        "git_sha": manifest.get("git_sha", "local"),
        "backend": manifest.get("llm_backend", "unknown"),
        "lora": manifest.get("lora_adapter_path", "none"),
        "eval_pass": eval_pass,
        "eval_fail": eval_fail,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
