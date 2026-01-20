#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

EVAL_PATH = Path("data/eval/minimal_eval.jsonl")
DEFAULT_BASE_URL = "http://localhost:8010/v1"
MAX_RESPONSE_CHARS = 2000


def _truncate(text: str, limit: int = MAX_RESPONSE_CHARS) -> str:
    if not isinstance(text, str):
        return ""
    if len(text) <= limit:
        return text
    return text[:limit]


def _call_llm(base_url: str, prompt: str) -> str:
    payload = {
        "model": "local",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 256,
    }
    data = json.dumps(payload).encode("utf-8")
    token = os.getenv("AGENT_AUTH_TOKEN", "dev-local-key")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=data,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = resp.read()
    parsed = json.loads(body.decode("utf-8", errors="ignore"))
    choices = parsed.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
    return ""


def _preflight(base_url: str) -> bool:
    token = os.getenv("AGENT_AUTH_TOKEN", "dev-local-key")
    headers = {"Authorization": f"Bearer {token}"}
    req = urllib.request.Request(
        f"{base_url}/models",
        headers=headers,
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            resp.read(1)
        return True
    except Exception:
        return False


def main() -> None:
    print("RUN_MINIMAL_EVAL: START")
    if not EVAL_PATH.exists():
        print("EVAL: pass=0 fail=0")
        print("FAIL: none")
        return
    base_url = os.getenv("AGENT_LLM_URL", DEFAULT_BASE_URL).rstrip("/")
    if not _preflight(base_url):
        decision_path = Path("data/reports/training_decision.txt")
        decision_path.parent.mkdir(parents=True, exist_ok=True)
        decision_path.write_text(
            "TRAINING_STATUS=BLOCKED_INFRA\n",
            encoding="utf-8",
        )
        infra_path = Path("data/reports/infra_status.txt")
        infra_path.parent.mkdir(parents=True, exist_ok=True)
        infra_path.write_text("INFRA_STATUS=DOWN\n", encoding="utf-8")
        print("EVAL: pass=0 fail=0")
        print("TRAINING_STATUS=BLOCKED_INFRA")
        return
    pass_count = 0
    fail_ids = []
    fail_records = []
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
        ok = False
        if isinstance(expected, list):
            ok = any(e in response for e in expected)
        elif isinstance(expected, str) and expected:
            ok = expected in response
        if ok:
            pass_count += 1
        else:
            fail_ids.append(case_id)
            fail_records.append({
                "id": case_id,
                "risk_level": risk_level,
                "input": prompt,
                "expected": expected,
                "match_mode": "any" if isinstance(expected, list) else "substring",
                "response": _truncate(response),
            })
    fail_count = len(fail_ids)
    print(f"EVAL: pass={pass_count} fail={fail_count}")
    report_path = Path("data/reports/minimal_eval.txt")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        f"EVAL: pass={pass_count} fail={fail_count}\n",
        encoding="utf-8",
    )
    if fail_ids:
        print(f"FAIL: {', '.join(fail_ids)}")
    else:
        print("FAIL: none")

    fail_path = Path("data/reports/eval_fails.jsonl")
    fail_path.parent.mkdir(parents=True, exist_ok=True)
    with fail_path.open("w", encoding="utf-8", newline="\n") as f:
        for rec in fail_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    decision_path = Path("data/reports/training_decision.txt")
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    status = "PREPARE" if fail_count > 0 else "SKIP"
    decision_path.write_text(f"TRAINING_STATUS={status}\n", encoding="utf-8")

    debug_path = Path("data/reports/training_pack_debug.json")
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    sample_ids = [rec.get("id", "") for rec in fail_records[:3]]
    empty_response_count = sum(
        1 for rec in fail_records if not str(rec.get("response", "")).strip()
    )
    debug_data = {
        "fails_count": fail_count,
        "sample_ids": sample_ids,
        "empty_response_count": empty_response_count,
    }
    with debug_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(debug_data, f, ensure_ascii=False, indent=2)

    training_pack_path = Path("data/reports/training_pack.json")
    taxonomy_path = Path("data/reports/eval_fails_taxonomy.jsonl")
    filtered_fails = []
    if taxonomy_path.exists():
        for line in taxonomy_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("treatment_hint") == "lora_candidate":
                filtered_fails.append(rec)
    if filtered_fails:
        training_pack_path.parent.mkdir(parents=True, exist_ok=True)
        pack = {
            "base_url": base_url,
            "fails_count": len(filtered_fails),
            "fails": filtered_fails,
        }
        with training_pack_path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(pack, f, ensure_ascii=False, indent=2)
    else:
        if training_pack_path.exists():
            training_pack_path.unlink()

    print(f"EVAL: pass={pass_count} fail={fail_count}")


if __name__ == "__main__":
    main()
