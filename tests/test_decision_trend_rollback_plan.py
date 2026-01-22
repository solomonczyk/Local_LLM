import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional


def _write_events(log_path: Path, count: int, risk_level: str) -> None:
    now = time.time()
    events = []
    for _ in range(count):
        events.append(
            {
                "ts": now,
                "type": "director_decision",
                "decision": "Run smoke tests to avoid regression.",
                "next_step": "Run smoke test in CI.",
                "confidence": 0.5,
                "risks": ["regression risk"],
                "risk_level": risk_level,
            }
        )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _write_policy_rules(path: Path, delta: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "director_regressions_soften_v1": {
                    "enabled": True,
                    "delta": delta,
                    "only_type": "director_decision",
                    "only_penalty_reason": "regressions",
                    "mitigation_keywords": [
                        "smoke",
                        "ci",
                        "coverage",
                        "test",
                        "tests",
                        "auth",
                        "secrets",
                        "gate",
                        "gates",
                        "rerun",
                        "pr",
                    ],
                }
            }
        ),
        encoding="utf-8",
    )


def _run_trend(tmp_path: Path, args: List[str], env_override: Optional[Dict[str, str]] = None) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "tools" / "decision_trend.py"
    env = dict(os.environ)
    if env_override:
        env.update(env_override)
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return result.stdout


def test_rollback_plan_when_suggested(tmp_path: Path) -> None:
    _write_events(tmp_path / "data" / "decision_events.log", count=3, risk_level="high")
    _write_policy_rules(tmp_path / "tools" / "policy_rules.json", delta=0.2)
    output = _run_trend(
        tmp_path,
        [
            "--fail-below-avg",
            "0.9",
            "--grace",
            "0.0",
            "--exclude-class",
            "legacy_unknown",
            "--emit-json",
            "--windows-minutes",
            "1440,10080",
            "--drift-max",
            "0.05",
            "--policy-sensitivity",
            "--ci-multi",
            "--min-count",
            "1",
        ],
        env_override={"FORCE_ROLLBACK_SUGGESTED": "true", "ROLLBACK_APPROVED": "true"},
    )
    plan_line = next(
        line for line in output.splitlines() if line.startswith("ROLLBACK_PLAN:")
    )
    assert plan_line.startswith("ROLLBACK_PLAN: policy=")
    assert "action=disable_in_policy_rules_json" in plan_line


def test_rollback_plan_when_not_suggested(tmp_path: Path) -> None:
    _write_events(tmp_path / "data" / "decision_events.log", count=3, risk_level="medium")
    _write_policy_rules(tmp_path / "tools" / "policy_rules.json", delta=0.2)
    output = _run_trend(
        tmp_path,
        [
            "--fail-below-avg",
            "0.9",
            "--grace",
            "0.0",
            "--exclude-class",
            "legacy_unknown",
            "--emit-json",
            "--windows-minutes",
            "1440,10080",
            "--drift-max",
            "0.05",
            "--policy-sensitivity",
            "--ci-multi",
            "--min-count",
            "1",
        ],
    )
    plan_line = next(
        line for line in output.splitlines() if line.startswith("ROLLBACK_PLAN:")
    )
    assert plan_line == "ROLLBACK_PLAN: none"


def test_rollback_approval_ok(tmp_path: Path) -> None:
    _write_events(tmp_path / "data" / "decision_events.log", count=3, risk_level="high")
    _write_policy_rules(tmp_path / "tools" / "policy_rules.json", delta=0.2)
    output = _run_trend(
        tmp_path,
        [
            "--fail-below-avg",
            "0.9",
            "--grace",
            "0.0",
            "--exclude-class",
            "legacy_unknown",
            "--emit-json",
            "--windows-minutes",
            "1440,10080",
            "--drift-max",
            "0.05",
            "--policy-sensitivity",
            "--ci-multi",
            "--min-count",
            "1",
        ],
        env_override={"FORCE_ROLLBACK_SUGGESTED": "true", "ROLLBACK_APPROVED": "true"},
    )
    approval_line = next(
        line for line in output.splitlines() if line.startswith("ROLLBACK_APPROVAL:")
    )
    assert approval_line == "ROLLBACK_APPROVAL: OK"
