#!/usr/bin/env python3
import hashlib
import json
import os
import time
from pathlib import Path

REPORTS_DIR = Path("data/reports")
MANIFEST_PATH = REPORTS_DIR / "intelligence_manifest.json"
REMEDIATION_PATH = REPORTS_DIR / "remediation_plan.json"
EVAL_PATH = Path("data/eval/minimal_eval.jsonl")


def _sha256(path: Path) -> str:
    if not path.exists():
        return "none"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    manifest = {
        "ts_utc": int(time.time()),
        "git_sha": os.getenv("GITHUB_SHA", "local"),
        "llm_backend": os.getenv("LLM_BACKEND", "unknown"),
        "llm_server_impl": os.getenv("LLM_SERVER_IMPL", "unknown"),
        "lora_adapter_path": os.getenv("LORA_ADAPTER_PATH", "none"),
        "remediation_plan_sha256": _sha256(REMEDIATION_PATH),
        "minimal_eval_sha256": _sha256(EVAL_PATH),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
