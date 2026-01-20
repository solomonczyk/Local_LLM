import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple


TASKS: Dict[str, str] = {
    "where_used_agent_llm_url": "Find where AGENT_LLM_URL is used in code.",
    "todo_fixme": "Find TODO or FIXME in the repo.",
    "proxy_pass": "Find proxy_pass usage in nginx config.",
    "ports": "Show ports: mappings in docker-compose.",
}


def _ensure_utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _run_ui_task(task: str) -> Tuple[str, str]:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import ui

    last_output = ""
    last_pending = ""
    for last_output, last_pending in ui.run_task(
        task=task,
        mode="FAST",
        use_smart_routing=True,
        check_health=True,
        include_context=False,
        use_tools=True,
    ):
        pass
    return last_output, last_pending


def _validate_evidence_output(output: str) -> None:
    if "=== Evidence (tool output) ===" not in output:
        raise AssertionError("Missing Evidence section (expected === Evidence (tool output) ===)")

    if "=== Response ===" not in output:
        raise AssertionError("Missing === Response === section header")

    response = output.split("=== Response ===", 1)[1].lstrip()
    if not response.startswith("=== Evidence (tool output) ==="):
        raise AssertionError("Response is not evidence-only (expected response to start with Evidence)")

    banned = ["sk-", "Bearer", "OPENAI_API_KEY=", "AGENT_API_KEY="]
    for marker in banned:
        if marker in output:
            raise AssertionError(f"Banned marker found in output: {marker}")

    if re.search(r"\\b401\\b", output) or "not authenticated" in output.lower():
        raise AssertionError("Detected authentication failure in output (401 / not authenticated)")


def main() -> int:
    _ensure_utf8_stdout()

    parser = argparse.ArgumentParser(description="UI tool-mode smoke runner (host-side).")
    parser.add_argument("--task", required=True, choices=sorted(TASKS.keys()))
    parser.add_argument("--evidence", action="store_true", help="Assert evidence-only output (no LLM summary).")
    args = parser.parse_args()

    os.environ.setdefault("AGENT_LLM_URL", "http://localhost:8002/v1")
    os.environ.setdefault("TOOL_SERVER_URL", "http://localhost:8003")

    api_key = os.getenv("AGENT_API_KEY", "").strip()
    if not api_key:
        print("ERROR: AGENT_API_KEY is not set. Example (PowerShell):", file=sys.stderr)
        print("  Set-Item env:AGENT_API_KEY dev-local-key; python tools/ui_smoke_tools.py --task where_used_agent_llm_url --evidence", file=sys.stderr)
        return 2

    task_text = TASKS[args.task]
    started = datetime.now().isoformat(timespec="seconds")
    output, pending = _run_ui_task(task_text)

    print(output)
    if pending and pending.strip() and pending.strip().lower() != "no pending actions":
        print(f"\n[WARN] pending: {pending}", file=sys.stderr)

    if args.evidence:
        _validate_evidence_output(output)
        print("\n[OK] evidence smoke passed")

    print(f"[done] {args.task} at {started}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
