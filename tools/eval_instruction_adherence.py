import json
import os
import sys
import time
from typing import Dict, List, Tuple

DEFAULT_MODEL = os.getenv("IA_MODEL", "gpt-5.2")
CASES_PATH = os.getenv("IA_CASES_PATH", "eval/instruction_adherence_cases.jsonl")
TIMEOUT_S = int(os.getenv("IA_TIMEOUT_S", "60"))
MAX_OUTPUT_TOKENS = int(os.getenv("IA_MAX_OUTPUT_TOKENS", "80"))
TEMPERATURE = float(os.getenv("IA_TEMPERATURE", "0"))


def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"FAIL: missing env {name}")
        sys.exit(2)
    return v


def _nonempty_lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip() != ""]


def _check_format(text: str) -> Tuple[bool, str]:
    lines = _nonempty_lines(text)
    if len(lines) != 4:
        return False, f"line_count={len(lines)} expected=4"
    if lines[0] != "OK":
        return False, f"first_line={lines[0]!r} expected='OK'"
    bullets = lines[1:]
    if len(bullets) != 3:
        return False, f"bullet_count={len(bullets)} expected=3"
    for i, b in enumerate(bullets, 1):
        if not b.startswith("-"):
            return False, f"bullet_{i}_does_not_start_with_dash={b!r}"
    return True, "ok"


def _load_cases(path: str) -> List[Dict]:
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            cases.append(json.loads(ln))
    return cases


def _openai_call(prompt: str) -> str:
    # Uses OpenAI Responses API via the official SDK.
    # Requirements: pip install openai
    from openai import OpenAI

    client = OpenAI(api_key=_require_env("OPENAI_API_KEY"))

    t0 = time.time()
    resp = client.responses.create(
        model=DEFAULT_MODEL,
        input=prompt,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        timeout=TIMEOUT_S,
    )
    # text output
    out = resp.output_text or ""
    dt = int((time.time() - t0) * 1000)
    return out.strip(), dt


def main() -> int:
    cases = _load_cases(CASES_PATH)
    violations: List[Dict] = []

    total = len(cases)
    for c in cases:
        cid = c.get("id", "UNKNOWN")
        prompt = c.get("prompt", "")
        if not prompt:
            violations.append({"id": cid, "reason": "missing_prompt"})
            continue

        try:
            text, latency_ms = _openai_call(prompt)
        except Exception as e:
            violations.append({"id": cid, "reason": f"llm_error:{type(e).__name__}"})
            continue

        ok, reason = _check_format(text)
        if not ok:
            violations.append(
                {"id": cid, "reason": reason, "sample": text[:300], "latency_ms": latency_ms}
            )

    if violations:
        print("instruction_adherence_eval: FAIL")
        print(f"violations_count: {len(violations)} / {total}")
        print("violating_case_ids:", ",".join(v["id"] for v in violations))
        # Optional detail file for artifacts/debug
        os.makedirs("data/reports", exist_ok=True)
        with open(
            "data/reports/instruction_adherence_violations.json", "w", encoding="utf-8"
        ) as f:
            json.dump({"total": total, "violations": violations}, f, ensure_ascii=False, indent=2)
        return 1

    print("instruction_adherence_eval: PASS")
    print(f"violations_count: 0 / {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
