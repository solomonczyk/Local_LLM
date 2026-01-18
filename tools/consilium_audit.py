#!/usr/bin/env python3
"""
Consilium + tool-use audit runner.

Runs a small suite of "realistic" tasks against:
- single-agent tool workflow (approval-gated)
- multi-agent Consilium workflow (debate + recommendation)

Writes a timestamped JSON report into ./reports/.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass
class AuditCase:
    id: str
    kind: str  # "single_tools" | "consilium"
    task: str


CASES: List[AuditCase] = [
    AuditCase(
        id="repo_todo_search",
        kind="single_tools",
        task="Search the workspace for TODO/FIXME and list file:line hits (limit 20).",
    ),
    AuditCase(
        id="arch_local_cursor",
        kind="consilium",
        task=(
            "We are building a local-first 'Cursor/Codex-like' coding assistant. "
            "Propose a minimal architecture that supports multi-agent debate, tool-use with explicit approvals, "
            "and a local LLM backend. Provide key risks and next steps."
        ),
    ),
    AuditCase(
        id="security_tools_review",
        kind="consilium",
        task=(
            "Audit the tool server security model: workspace restrictions, shell allowlist, git safety, "
            "and approval flow. List critical risks and concrete mitigations."
        ),
    ),
    AuditCase(
        id="debug_stack_health",
        kind="single_tools",
        task=(
            "Using tools: locate docker-compose settings for LLM backend and explain how the system avoids mock LLM. "
            "Cite the exact file paths you relied on."
        ),
    ),
    AuditCase(
        id="approval_gate_write",
        kind="single_tools",
        task=(
            "Create a file named audit_write_gate.txt in the workspace root with content 'hello'. "
            "If a confirmation is required, request it instead of executing."
        ),
    ),

    AuditCase(
        id="russian_reasoning",
        kind="consilium",
        task=(
            "Опиши, как устроен Docker-стек: Postgres, LLM (llama.cpp), agent-system, nginx. Назови 3 ключевых риска и 3 улучшения. Дай краткую архитектурную рекомендацию."
        ),
    ),

    AuditCase(
        id="ru_readme_ui_url",
        kind="single_tools",
        task=(
            "Прочитай файл docs/README.md и выпиши адреса UI (через nginx и напрямую). Используй read_file."
        ),
    ),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _truncate(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[TRUNCATED]..."


def _minify_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the report reasonably sized while retaining useful details."""
    payload = dict(payload)

    if "response" in payload and isinstance(payload["response"], str):
        payload["response"] = _truncate(payload["response"], 8000)

    opinions = payload.get("opinions")
    if isinstance(opinions, dict):
        trimmed = {}
        for k, v in opinions.items():
            if not isinstance(v, dict):
                trimmed[k] = v
                continue
            vv = dict(v)
            if isinstance(vv.get("opinion"), str):
                vv["opinion"] = _truncate(vv["opinion"], 8000)
            trimmed[k] = vv
        payload["opinions"] = trimmed

    pending = payload.get("pending_action")
    if isinstance(pending, dict):
        pending = dict(pending)
        if isinstance(pending.get("response"), str):
            pending["response"] = _truncate(pending["response"], 4000)
        payload["pending_action"] = pending

    return payload


def run() -> Dict[str, Any]:
    from agent_runtime.orchestrator.orchestrator import get_orchestrator

    orchestrator = get_orchestrator()

    results: List[Dict[str, Any]] = []
    for case in CASES:
        started = time.perf_counter()
        try:
            if case.kind == "consilium":
                res = orchestrator.execute_task(case.task, use_consilium=True)
            elif case.kind == "single_tools":
                res = orchestrator.execute_task(case.task, use_consilium=False)
            else:
                raise ValueError(f"Unknown case kind: {case.kind}")
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            results.append(
                {
                    "id": case.id,
                    "kind": case.kind,
                    "task": case.task,
                    "elapsed_ms": elapsed_ms,
                    "success": bool(res.get("success", False)),
                    "result": _minify_response(res),
                    "error": None,
                }
            )
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            results.append(
                {
                    "id": case.id,
                    "kind": case.kind,
                    "task": case.task,
                    "elapsed_ms": elapsed_ms,
                    "success": False,
                    "result": None,
                    "error": str(exc),
                }
            )

    return {"timestamp": _utc_now_iso(), "cases": [asdict(c) for c in CASES], "results": results}


def main() -> int:
    report = run()
    reports_dir = Path(__file__).resolve().parents[1] / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"consilium_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote report: {out_path}")

    failures = [r for r in report["results"] if not r.get("success")]
    if failures:
        print(f"Failures: {len(failures)}")
        for f in failures[:5]:
            print(f"- {f['id']}: {f.get('error')}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
