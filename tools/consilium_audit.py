#!/usr/bin/env python3
"""
Consilium + tool-use audit runner.

Runs a small suite of "realistic" tasks against:
- single-agent tool workflow (approval-gated)
- multi-agent Consilium workflow (debate + recommendation)

Writes a timestamped JSON report into ./reports/.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
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
            "Опиши этот Docker-стек: Postgres, LLM (llama.cpp), agent-system, nginx. "
            "Дай 3 ключевых риска и 3 улучшения. Поясни роли и связи компонентов."
        ),
    ),

    AuditCase(
        id="ru_readme_ui_url",
        kind="single_tools",
        task=(
            "Прочитай docs/README.md и назови адрес UI (nginx и прямой порт). "
            "Используй read_file."
        ),
    ),
]

_CYRILLIC_RE = re.compile("[\u0410-\u044F\u0401\u0451]")
_RU_CASES = {"russian_reasoning", "ru_readme_ui_url"}
for case in CASES:
    if case.id in _RU_CASES and not _CYRILLIC_RE.search(case.task):
        raise ValueError(f"Russian audit case '{case.id}' is missing Cyrillic text")


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


def _load_env_if_missing(keys: List[str]) -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    existing = {key for key in keys if os.getenv(key)}
    if len(existing) == len(keys):
        return
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name in keys and not os.getenv(name):
            os.environ[name] = value.strip().strip('"').strip("'")


def _hash_file(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _detect_backend_meta() -> Dict[str, Any]:
    backend = os.getenv("LLM_BACKEND")
    gguf_path = Path(os.getenv("LLM_GGUF_PATH", "models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"))
    lora_path = Path(os.getenv("LORA_ADAPTER_PATH", "lora_qwen2_5_coder_1_5b_python/adapter_model.safetensors"))

    if backend not in {"peft", "llama_cpp"}:
        if gguf_path.exists():
            backend = "llama_cpp"
        elif lora_path.exists():
            backend = "peft"
        else:
            backend = "unknown"

    lora_attached = backend == "peft" and lora_path.exists()
    model_version = os.getenv("AGENT_LLM_MODEL") or os.getenv("LLM_MODEL") or ""
    model_hash = None
    model_path: Optional[Path] = None
    if backend == "llama_cpp":
        model_path = gguf_path
    elif backend == "peft":
        model_path = lora_path
    if model_path:
        model_hash = _hash_file(model_path)
        if not model_version:
            model_version = model_path.name

    return {
        "backend_active": backend,
        "lora_attached": lora_attached,
        "model_version": model_version,
        "model_hash": model_hash,
    }


def _extract_risks(results: List[Dict[str, Any]]) -> List[str]:
    risks: List[str] = []
    for entry in results:
        if entry.get("kind") != "consilium":
            continue
        result = entry.get("result") or {}
        opinions = result.get("opinions") or {}
        if not isinstance(opinions, dict):
            continue
        for opinion in opinions.values():
            text = opinion.get("opinion") if isinstance(opinion, dict) else None
            if not isinstance(text, str):
                continue
            for line in text.splitlines():
                if re.search(r"\b(risk|risks|\u0440\u0438\u0441\u043a|\u0440\u0438\u0441\u043a\u0438)\b", line, re.IGNORECASE):
                    snippet = line.strip()
                    if snippet and snippet not in risks:
                        risks.append(snippet[:200])
    return risks[:10]


def _build_agents_summary(
    status: Dict[str, Any],
    risks: List[str],
    blocking_issues: List[str],
    recommended_next_step: str,
) -> List[Dict[str, Any]]:
    consilium_status = status.get("consilium") or {}
    agents = consilium_status.get("agents") or {}
    kb_loaded = consilium_status.get("kb_loaded") or {}
    timing = consilium_status.get("timing_per_agent") or {}
    summary: List[Dict[str, Any]] = []
    for name, meta in agents.items():
        timing_stats = timing.get(name) or {}
        summary.append(
            {
                "name": name,
                "role": meta.get("role"),
                "kb_loaded": bool(kb_loaded.get(name)),
                "avg_llm_latency_ms": timing_stats.get("avg_llm_ms", 0),
                "risks_detected": risks,
                "blocking_issues": blocking_issues,
                "recommended_next_step": recommended_next_step,
            }
        )
    return summary


def _recommended_next_step(blocking_issues: List[str]) -> str:
    if blocking_issues:
        return "Resolve blocking issues and rerun the audit."
    return "Align inference server config as single source of truth (set LLM_BACKEND + model path) and rerun audit."


def run() -> Dict[str, Any]:
    from agent_runtime.orchestrator.orchestrator import get_orchestrator
    from agent_system.director_adapter import DirectorAdapter

    _load_env_if_missing(
        ["OPENAI_API_KEY", "AGENT_API_KEY", "AGENT_LLM_URL", "TOOL_SERVER_URL", "DIRECTOR_FORCE"]
    )
    if os.getenv("OPENAI_API_KEY") and not os.getenv("DIRECTOR_FORCE"):
        os.environ["DIRECTOR_FORCE"] = "true"

    director_adapter = DirectorAdapter()
    director_healthcheck = director_adapter.healthcheck()
    director_cb = getattr(director_adapter, "_circuit_breaker", None)
    director_circuit = None
    if director_cb:
        director_circuit = {
            "state": director_cb.state,
            "failure_count": director_cb.failure_count,
            "success_count": director_cb.success_count,
            "total_calls": director_cb.total_calls,
            "total_failures": director_cb.total_failures,
            "total_blocked": director_cb.total_blocked,
        }
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

    status = orchestrator.get_agent_status()
    meta = _detect_backend_meta()
    blocking = [f"{r['id']}: {r.get('error')}" for r in results if not r.get("success")]
    if not os.getenv("OPENAI_API_KEY"):
        blocking.append("director_disabled: OPENAI_API_KEY not set")

    risks = _extract_risks(results)
    next_step = _recommended_next_step(blocking)

    report = {
        "timestamp": _utc_now_iso(),
        "metadata": {
            "director_healthcheck": director_healthcheck,
            "director_circuit": director_circuit,
        },
        **meta,
        "agents": _build_agents_summary(status, risks, blocking, next_step),
        "risks_detected": risks,
        "blocking_issues": blocking,
        "recommended_next_step": next_step,
        "cases": [asdict(c) for c in CASES],
        "results": results,
    }
    return report


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
