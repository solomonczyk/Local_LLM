#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

EVAL_PATH = Path("data/eval/minimal_eval.jsonl")
DEFAULT_BASE_URL = "http://localhost:8010/v1"


def _call_llm(base_url: str, prompt: str) -> str:
    payload = {
        "model": "local",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 256,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
    parsed = json.loads(body.decode("utf-8", errors="ignore"))
    choices = parsed.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
    return ""


def main() -> None:
    if not EVAL_PATH.exists():
        print("EVAL: pass=0 fail=0")
        print("FAIL: none")
        return
    base_url = os.getenv("AGENT_LLM_URL", DEFAULT_BASE_URL).rstrip("/")
    pass_count = 0
    fail_ids = []
    for line in EVAL_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        case = json.loads(line)
        case_id = case.get("id", "unknown")
        risk_level = case.get("risk_level")
        prompt = case.get("input", "")
        expected = case.get("expected", "")
        print(f"CASE: {case_id} risk_level={risk_level}")
        try:
            response = _call_llm(base_url, prompt)
        except (urllib.error.URLError, ValueError) as exc:
            response = ""
            print(f"ERROR: {case_id} {exc}")
        if isinstance(expected, str) and expected and expected in response:
            pass_count += 1
        else:
            fail_ids.append(case_id)
    fail_count = len(fail_ids)
    print(f"EVAL: pass={pass_count} fail={fail_count}")
    if fail_ids:
        print(f"FAIL: {', '.join(fail_ids)}")
    else:
        print("FAIL: none")


if __name__ == "__main__":
    main()
