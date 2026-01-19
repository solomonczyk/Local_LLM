#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from agent_system.decision_log import append_decision_event
LOG = Path("data/decision_events.log")
POLICY_RULES_PATH = Path("tools/policy_rules.json")
MIN_EVENTS = 5
POLICY_VERSION = "director_regressions_soften_v1"
RISK_LEVEL_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}
PENALTY_KEYWORDS = {
    "regressions": ("regression", "regressions", "regressed"),
    "coverage": ("coverage",),
    "insufficient": ("insufficient",),
}


def classify_penalty_reason(text: str) -> str:
    lowered = text.lower()
    for reason in ("regressions", "coverage", "insufficient"):
        if any(keyword in lowered for keyword in PENALTY_KEYWORDS[reason]):
            return reason
    return "other"


def extract_reason_text(event: dict) -> str:
    risks = event.get("risks")
    parts = []
    if isinstance(risks, list) and risks:
        parts.append("; ".join(str(r) for r in risks))
    decision = event.get("decision")
    if decision:
        parts.append(str(decision))
    next_step = event.get("next_step")
    if next_step:
        parts.append(str(next_step))
    return " ".join(parts)


def normalize_risk_level(value: object) -> Optional[str]:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in RISK_LEVEL_ORDER:
            return lowered
    return None


def load_policy_rules() -> dict:
    if not POLICY_RULES_PATH.exists():
        return {}
    try:
        raw_text = POLICY_RULES_PATH.read_text(encoding="utf-8")
        raw_text = raw_text.lstrip("\ufeff")
        print(f"POLICY_FILE_HEAD: {raw_text[:200]!r}")
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Decision trend summary.")
    parser.add_argument("--fail-below-avg", type=float, help="Fail if avg score drops below threshold.")
    parser.add_argument("--grace", type=float, help="Grace zone below threshold before failing.")
    parser.add_argument("--since-minutes", type=float, help="Only include events from the last N minutes.")
    parser.add_argument("--since-ts", type=float, help="Only include events with ts >= since-ts.")
    parser.add_argument("--exclude-class", action="append", default=[], help="Exclude decision_class values.")
    parser.add_argument("--debug-sample-excluded", type=int, help="Print raw samples of excluded events.")
    parser.add_argument(
        "--debug-sample-regressions-bad",
        type=int,
        help="Print samples of bad regressions with decision and next_step.",
    )
    parser.add_argument("--policy-off", action="store_true", help="Disable policy adjustments for this run.")
    parser.add_argument(
        "--policy-max-delta",
        type=float,
        help="Cap the total policy delta applied per event.",
    )
    parser.add_argument(
        "--debug-policy-apply",
        type=int,
        help="Print a sample of policy application details.",
    )
    parser.add_argument(
        "--debug-mitigated",
        type=int,
        help="Print a sample of regressions_mitigated normalization.",
    )
    parser.add_argument(
        "--print-bad-penalties",
        action="store_true",
        help="Print penalty_reason counts for bad events.",
    )
    parser.add_argument(
        "--print-bad-samples",
        type=int,
        help="Print up to N bad samples (decision/next_step/score/confidence).",
    )
    parser.add_argument(
        "--debug-window",
        action="store_true",
        help="Print per-event window details for kept events.",
    )
    parser.add_argument("--emit-json", action="store_true", help="Emit summary JSON output.")
    parser.add_argument("--ci", action="store_true", help="Use CI exit codes.")
    parser.add_argument("--min-count", type=int, help="Minimum events required to evaluate trend in CI.")
    parser.add_argument(
        "--adaptive-risk-thresholds",
        action="store_true",
        help="Adjust threshold based on high-risk share.",
    )
    parser.add_argument("--simulate-rollback", action="store_true", help="Simulate rollback plan effects.")
    parser.add_argument(
        "--retrofill-agent-director",
        action="store_true",
        help="Fill missing agent for director decisions.",
    )
    parser.add_argument(
        "--debug-sample-missing-agent",
        type=int,
        help="Print a sample bad event missing agent.",
    )
    parser.add_argument(
        "--windows-minutes",
        type=str,
        help="Comma-separated window sizes in minutes for multi-window summary.",
    )
    parser.add_argument("--drift-max", type=float, help="Maximum allowed drift between window averages.")
    parser.add_argument(
        "--policy-sensitivity",
        action="store_true",
        help="Calculate sensitivity by comparing policy ON vs OFF.",
    )
    parser.add_argument("--ci-multi", action="store_true", help="Use multi-window CI gate.")
    parser.add_argument(
        "--debug-policy-match",
        type=int,
        help="Print a sample policy match debug line.",
    )
    args = parser.parse_args()

    exclude_classes = args.exclude_class
    since_ts = args.since_ts
    print(
        f"FILTER_DEBUG: log={LOG} since_ts={since_ts} "
        f"since_minutes={args.since_minutes} windows={args.windows_minutes} "
        f"exclude={exclude_classes}"
    )

    def maybe_exit(code: int) -> None:
        if args.ci:
            sys.exit(code)

    if args.windows_minutes:
        windows = [int(v.strip()) for v in args.windows_minutes.split(",") if v.strip()]
        summaries = []
        exit_codes = []
        missing_agent_printed = False
        policy_applied_printed = False
        policy_delta_printed = False
        trend_printed = False
        policy_apply_printed = False
        avg_debug_printed = False
        adaptive_impact_printed = False
        adaptive_cooldown_printed = False
        adaptive_guard_printed = False
        adaptive_stability_printed = False
        adaptive_status_printed = False
        mitigated_printed = False
        for window in windows:
            effective_since_ts = args.since_ts
            effective_since_minutes = None
            if effective_since_ts is None:
                effective_since_minutes = window
            cmd = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--fail-below-avg",
                str(args.fail_below_avg),
                "--emit-json",
            ]
            if args.grace is not None:
                cmd.extend(["--grace", str(args.grace)])
            if effective_since_ts is not None:
                cmd.extend(["--since-ts", str(effective_since_ts)])
            elif effective_since_minutes is not None:
                cmd.extend(["--since-minutes", str(effective_since_minutes)])
            if args.exclude_class:
                for exclude_value in args.exclude_class:
                    cmd.extend(["--exclude-class", exclude_value])
            if args.policy_off:
                cmd.append("--policy-off")
            if args.ci:
                cmd.append("--ci")
            if args.min_count is not None:
                cmd.extend(["--min-count", str(args.min_count)])
            if args.adaptive_risk_thresholds:
                cmd.append("--adaptive-risk-thresholds")
            if args.debug_sample_missing_agent is not None:
                cmd.extend(["--debug-sample-missing-agent", str(args.debug_sample_missing_agent)])
            if args.retrofill_agent_director:
                cmd.append("--retrofill-agent-director")
            if args.debug_policy_match is not None:
                cmd.extend(["--debug-policy-match", str(args.debug_policy_match)])
            if args.policy_max_delta is not None:
                cmd.extend(["--policy-max-delta", str(args.policy_max_delta)])
            if args.debug_policy_apply is not None:
                cmd.extend(["--debug-policy-apply", str(args.debug_policy_apply)])
            if args.debug_mitigated is not None:
                cmd.extend(["--debug-mitigated", str(args.debug_mitigated)])
            result = subprocess.run(cmd, capture_output=True, text=True)
            exit_codes.append(result.returncode)
            for line in result.stdout.splitlines():
                if line.startswith("POLICY_MATCH_DEBUG:"):
                    print(line)
                if line.startswith("AVG_DEBUG:") and not avg_debug_printed:
                    print(line)
                    avg_debug_printed = True
                if line.startswith("ADAPTIVE_IMPACT:") and not adaptive_impact_printed:
                    print(line)
                    adaptive_impact_printed = True
                if line.startswith("ADAPTIVE_COOLDOWN:") and not adaptive_cooldown_printed:
                    print(line)
                    adaptive_cooldown_printed = True
                if line.startswith("ADAPTIVE_GUARD:") and not adaptive_guard_printed:
                    print(line)
                    adaptive_guard_printed = True
                if line.startswith("ADAPTIVE_STABILITY:") and not adaptive_stability_printed:
                    print(line)
                    adaptive_stability_printed = True
                if line.startswith("ADAPTIVE_STATUS:") and not adaptive_status_printed:
                    print(line)
                    adaptive_status_printed = True
                if line.startswith("TREND:") and not trend_printed:
                    print(line)
                    trend_printed = True
                if line.startswith("MITIGATED_SAMPLE:") and not mitigated_printed:
                    print(line)
                    mitigated_printed = True
                if line.startswith("POLICY_APPLY_SAMPLE:") and not policy_apply_printed:
                    print(line)
                    policy_apply_printed = True
                if line.startswith("POLICY_APPLIED_ALL:") and not policy_applied_printed:
                    print(line)
                    policy_applied_printed = True
                if line.startswith("POLICY_DELTA_CAPPED:") and not policy_delta_printed:
                    print(line)
                    policy_delta_printed = True
                if line.startswith("MISSING_AGENT_SAMPLE:") and not missing_agent_printed:
                    print(line)
                    missing_agent_printed = True
                if line.startswith("RCA_BAD_SAMPLE_KEYS:") or line.startswith("RCA_BAD_SAMPLE_AGENT:"):
                    print(line)
            summary_line = next(
                (
                    line
                    for line in result.stdout.splitlines()
                    if line.startswith("SUMMARY_JSON: ")
                ),
                None,
            )
            if not summary_line:
                raise RuntimeError("Missing SUMMARY_JSON output for window summary.")
            summary = json.loads(summary_line.replace("SUMMARY_JSON: ", "", 1))
            summary["window_minutes"] = window
            adaptive_line = next(
                (
                    line
                    for line in result.stdout.splitlines()
                    if line.startswith("ADAPTIVE_THRESHOLD:")
                ),
                None,
            )
            if adaptive_line:
                summary["adaptive_threshold_line"] = adaptive_line
            adaptive_status_line = next(
                (
                    line
                    for line in result.stdout.splitlines()
                    if line.startswith("ADAPTIVE_STATUS:")
                ),
                None,
            )
            if adaptive_status_line:
                summary["adaptive_status_line"] = adaptive_status_line
            if args.policy_sensitivity:
                cmd_off = cmd + ["--policy-off"]
                result_off = subprocess.run(cmd_off, capture_output=True, text=True)
                exit_codes.append(result_off.returncode)
                summary_line_off = next(
                    (
                        line
                        for line in result_off.stdout.splitlines()
                        if line.startswith("SUMMARY_JSON: ")
                    ),
                    None,
                )
                if not summary_line_off:
                    raise RuntimeError("Missing SUMMARY_JSON output for policy-off summary.")
                summary_off = json.loads(summary_line_off.replace("SUMMARY_JSON: ", "", 1))
                avg_on = summary.get("avg")
                avg_off = summary_off.get("avg")
                delta = None
                if isinstance(avg_on, (int, float)) and isinstance(avg_off, (int, float)):
                    delta = round(avg_on - avg_off, 6)
                sensitivity = {
                    "avg_on": avg_on,
                    "avg_off": avg_off,
                    "delta": delta,
                }
                if isinstance(delta, (int, float)):
                    sensitivity["policy_dependency"] = "HIGH" if delta > 0.05 else "LOW"
                summary["policy_sensitivity"] = sensitivity
            summaries.append(summary)
        summary_multi = {"windows": summaries}
        if args.drift_max is not None and len(summaries) >= 2:
            drift = abs(summaries[0]["avg"] - summaries[1]["avg"])
            summary_multi["drift"] = round(drift, 6)
            summary_multi["drift_status"] = "DRIFT" if drift > args.drift_max else "OK"
        retrofill_applied = 0
        for summary in summaries:
            retrofill_applied += summary.get("retrofill_applied", 0)
        outcomes = {
            "simulated": 0,
            "approved": 0,
            "applied": 0,
            "skipped": 0,
        }
        if summaries:
            outcomes.update(summaries[0].get("rollback_outcomes", {}))
        print(
            "ROLLBACK_OUTCOMES: "
            f"simulated={outcomes['simulated']} "
            f"approved={outcomes['approved']} "
            f"applied={outcomes['applied']} "
            f"skipped={outcomes['skipped']}"
        )
        pressure_high = outcomes["simulated"] >= 3
        if outcomes["simulated"] >= 3:
            print(f"ROLLBACK_PRESSURE: HIGH (simulated={outcomes['simulated']})")
        else:
            print(f"ROLLBACK_PRESSURE: OK (simulated={outcomes['simulated']})")
        print(f"RETROFILL_APPLIED: {retrofill_applied}")
        if summaries:
            rca_agents = summaries[0].get("rca_bad_by_agent", {})
        else:
            rca_agents = {}
        known_agents = ["director", "architect", "qa", "security", "dev", "unknown"]
        extra_agents = sorted(key for key in rca_agents.keys() if key not in known_agents)
        agent_keys = known_agents + extra_agents
        print(
            "RCA_BAD_BY_AGENT: "
            + " ".join(f"{key}={rca_agents.get(key, 0)}" for key in agent_keys)
        )
        rca_director = summaries[0].get("rca_bad_by_class_director", {}) if summaries else {}
        print(
            "RCA_BAD_BY_CLASS_DIRECTOR: "
            + " ".join(
                f"{key}={rca_director.get(key, 0)}"
                for key in ["process", "infra", "security", "product", "unknown"]
            )
        )
        rca_penalty_director_process = (
            summaries[0].get("rca_bad_penalty_director_process", {}) if summaries else {}
        )
        print(
            "RCA_BAD_PENALTY_DIRECTOR_PROCESS: "
            + " ".join(
                f"{key}={rca_penalty_director_process.get(key, 0)}"
                for key in ["regressions", "coverage", "insufficient", "other", "missing"]
            )
        )
        rca_debug = summaries[0].get("rca_bad_debug", {}) if summaries else {}
        print(
            "RCA_BAD_DEBUG: "
            f"kept_total={rca_debug.get('kept_total', 0)} "
            f"bad_total={rca_debug.get('bad_total', 0)} "
            f"bad_agent_field_present={rca_debug.get('bad_agent_field_present', 0)}"
        )
        if summaries:
            shadow_count = summaries[0].get("shadow_policy_candidates", {}).get(
                "director_regressions_soften_v2",
                0,
            )
            print(f"SHADOW_POLICY_CANDIDATES: director_regressions_soften_v2={shadow_count}")
            policy_dependency = summaries[0].get("policy_sensitivity", {}).get("policy_dependency")
            drift_status = summary_multi.get("drift_status")
            v2_ready = (
                shadow_count >= 5
                and policy_dependency == "LOW"
                and drift_status == "OK"
            )
            summary_multi["shadow"] = {
                "candidates": {"director_regressions_soften_v2": shadow_count},
                "ready": {"director_regressions_soften_v2": v2_ready},
            }
            shadow_entry = {
                "candidates": shadow_count,
                "ready": v2_ready,
                "window_minutes": summaries[0].get("window_minutes"),
                "drift_status": drift_status,
                "policy_dependency": policy_dependency,
            }
            summary_multi["shadow_history"] = {
                "director_regressions_soften_v2": shadow_entry
            }
            print(f"SHADOW_POLICY_READY: director_regressions_soften_v2={str(v2_ready).lower()}")
            rollback_suggested = False
            for summary in summaries:
                if summary.get("trend_status") == "FAIL":
                    dependency = summary.get("policy_sensitivity", {}).get("policy_dependency")
                    max_risk = summary.get("max_risk_level", "low")
                    if dependency == "HIGH" and max_risk in ("high", "critical"):
                        rollback_suggested = True
                        break
            if os.environ.get("FORCE_ROLLBACK_SUGGESTED") == "true":
                rollback_suggested = True
            print(f"ROLLBACK_SUGGESTED: {str(rollback_suggested).lower()}")
            feedback_line = "ROLLBACK_FEEDBACK: none"
            if pressure_high and any(
                summary.get("trend_status") == "FAIL" for summary in summaries
            ):
                feedback_line = "ROLLBACK_FEEDBACK: QUALITY_DEGRADATION_CONFIRMED"
                print(feedback_line)
            else:
                print(feedback_line)
            rollback_plan_path = Path("data/reports/rollback_plan.json")
            if rollback_suggested:
                print(
                    "ROLLBACK_PLAN: "
                    f"policy={POLICY_VERSION} "
                    "action=disable_in_policy_rules_json "
                    "branch=auto/policy-rollback "
                    f"title=\"Rollback {POLICY_VERSION}\""
                )
                rollback_plan_path.parent.mkdir(parents=True, exist_ok=True)
                rollback_plan = {
                    "policy": POLICY_VERSION,
                    "action": "disable_in_policy_rules_json",
                    "branch": "auto/policy-rollback",
                    "title": f"Rollback {POLICY_VERSION}",
                }
                rollback_plan_path.write_text(
                    json.dumps(rollback_plan, ensure_ascii=False),
                    encoding="utf-8",
                )
            else:
                print("ROLLBACK_PLAN: none")
            rollback_approved = os.environ.get("ROLLBACK_APPROVED") == "true"
            rollback_approval_line = "ROLLBACK_APPROVAL: OK"
            approval_exit_code = None
            if rollback_suggested and rollback_approved:
                print(rollback_approval_line)
                approval_exit_code = 0
            if rollback_suggested and not rollback_approved:
                rollback_approval_line = "ROLLBACK_APPROVAL: REQUIRED"
                print(rollback_approval_line)
                approval_exit_code = 2
            simulation_status = "none"
            if args.simulate_rollback:
                if rollback_plan_path.exists():
                    plan = json.loads(rollback_plan_path.read_text(encoding="utf-8"))
                    policy_val = plan.get("policy")
                    action_val = plan.get("action")
                    affected_rules = 1
                    expected_effect = "disable policy rule and revert adjustments"
                    print("ROLLBACK_SIMULATION:")
                    print(f"- policy: {policy_val}")
                    print(f"- action: {action_val}")
                    print(f"- affected_rules: {affected_rules}")
                    print(f"- expected_effect: {expected_effect}")
                    append_decision_event(
                        {
                            "type": "rollback_outcome",
                            "decision": "rollback_outcome",
                            "next_step": "none",
                            "status": "simulated",
                            "policy": policy_val or "",
                            "reason": "rollback simulation executed",
                        }
                    )
                    if (
                        not policy_val
                        or not action_val
                        or not isinstance(affected_rules, int)
                        or affected_rules < 1
                        or not expected_effect
                    ):
                        simulation_status = "FAIL"
                        print("ROLLBACK_SIMULATION: FAIL (invalid_simulation_output)")
                        sys.exit(2)
                    simulation_status = "PASS"
                    print("ROLLBACK_SIMULATION: PASS")
                    sys.exit(0)
                else:
                    print("ROLLBACK_SIMULATION: none")
            max_risk = summaries[0].get("max_risk_level", "low")
            readiness_status = "PASS"
            readiness_line = "ROLLBACK_READINESS: PASS"
            if max_risk in ("high", "critical") and rollback_suggested and not rollback_plan_path.exists():
                readiness_status = "FAIL"
                readiness_line = "ROLLBACK_READINESS: FAIL (missing rollback_plan.json)"
                print(readiness_line)
                sys.exit(2)
            print(readiness_line)
            summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary_path:
                if max_risk in ("low", "medium"):
                    rollback_line = "ROLLBACK: none (blocked_by_risk_level)"
                elif rollback_suggested:
                    rollback_line = f"ROLLBACK: prepared ({POLICY_VERSION})"
                else:
                    rollback_line = "ROLLBACK: none"
                allowed = max_risk not in ("low", "medium")
                approval_status = rollback_approval_line.split(": ", 1)[1] if rollback_approval_line else "none"
                if outcomes["simulated"] >= 3:
                    pressure_line = f"ROLLBACK_PRESSURE: HIGH (simulated={outcomes['simulated']})"
                else:
                    pressure_line = f"ROLLBACK_PRESSURE: OK (simulated={outcomes['simulated']})"
                adaptive_line = summaries[0].get("adaptive_threshold_line", "ADAPTIVE_THRESHOLD: none")
                adaptive_status_line = summaries[0].get("adaptive_status_line", "ADAPTIVE_STATUS: none")
                trend_line = f"TREND: {summaries[0].get('trend_status')}"
                simulation_line = (
                    f"ROLLBACK_SIMULATION: {simulation_status}"
                    if simulation_status != "none"
                    else "ROLLBACK_SIMULATION: none"
                )
                rollback_status = (
                    "ROLLBACK_STATUS: "
                    f"suggested={str(rollback_suggested).lower()} "
                    f"allowed={str(allowed).lower()} "
                    f"readiness={readiness_status} "
                    f"simulation={simulation_status} "
                    f"approval={approval_status}"
                )
                with Path(summary_path).open("a", encoding="utf-8") as summary_file:
                    summary_file.write(trend_line + "\n")
                    summary_file.write(adaptive_line + "\n")
                    summary_file.write(adaptive_status_line + "\n")
                    summary_file.write(rollback_line + "\n")
                    summary_file.write(readiness_line + "\n")
                    summary_file.write(simulation_line + "\n")
                    summary_file.write(rollback_approval_line + "\n")
                    summary_file.write(pressure_line + "\n")
                    summary_file.write(feedback_line + "\n")
                    summary_file.write(rollback_status + "\n")
            if approval_exit_code is not None:
                sys.exit(approval_exit_code)
            history = []
            baseline_paths = sorted(
                Path("data/reports").glob("decision_trend_baseline*.json"),
                key=lambda p: p.stat().st_mtime,
            )
            for path in baseline_paths:
                try:
                    for line in path.read_text(encoding="utf-8").splitlines():
                        if line.startswith("SUMMARY_JSON_MULTI: "):
                            baseline = json.loads(line.replace("SUMMARY_JSON_MULTI: ", "", 1))
                            entry = baseline.get("shadow_history", {}).get("director_regressions_soften_v2")
                            if entry:
                                history.append(entry)
                            break
                except json.JSONDecodeError:
                    continue
            history.append(shadow_entry)
            last_five = history[-5:]
            auto_promote_ready = (
                len(last_five) == 5
                and all(
                    entry.get("ready") is True
                    and entry.get("drift_status") == "OK"
                    and entry.get("policy_dependency") == "LOW"
                    for entry in last_five
                )
            )
            print(
                "AUTO_PROMOTE_READY: "
                f"director_regressions_soften_v2={str(auto_promote_ready).lower()}"
            )
            if auto_promote_ready:
                print(
                    "AUTO_PROMOTE_PLAN: "
                    "policy=director_regressions_soften_v2 "
                    "action=enable_in_policy_rules_json "
                    "branch=auto/policy-promote-v2 "
                    "title=\"Promote director_regressions_soften_v2\""
                )
            else:
                print("AUTO_PROMOTE_PLAN: none")
            streak = 0
            for entry in reversed(history):
                if entry.get("ready") is True:
                    streak += 1
                else:
                    break
            print(f"SHADOW_READY_STREAK: director_regressions_soften_v2={streak}/5")
        print(f"SUMMARY_JSON_MULTI: {json.dumps(summary_multi, ensure_ascii=False)}")
        if args.ci_multi:
            fail_gate = False
            for summary in summaries:
                if summary.get("trend_status") == "FAIL":
                    sensitivity = summary.get("policy_sensitivity", {})
                    if sensitivity.get("policy_dependency") == "LOW":
                        fail_gate = True
                        break
            maybe_exit(2 if fail_gate else 0)
        if args.ci:
            maybe_exit(max(exit_codes) if exit_codes else 0)
        return

    if not LOG.exists():
        print("NO_LOG")
        maybe_exit(0)
        return

    lines = [ln for ln in LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
    retrofill_applied = 0
    events = []
    for line in lines:
        event = json.loads(line)
        if args.retrofill_agent_director:
            if event.get("type") == "director_decision" and "agent" not in event:
                event["agent"] = "director"
                retrofill_applied += 1
        events.append(event)
    events = events[-50:]  # last 50

    stats = {
        "total": len(events),
        "kept": 0,
        "no_ts": 0,
        "older": 0,
        "excluded_class": 0,
        "missing_score": 0,
        "missing_class": 0,
    }
    rollback_outcomes = {
        "simulated": 0,
        "approved": 0,
        "applied": 0,
        "skipped": 0,
    }
    cutoff = None
    if args.since_ts is not None:
        cutoff = args.since_ts
    elif args.since_minutes is not None:
        cutoff = time.time() - (args.since_minutes * 60)

    policy_rules = load_policy_rules()
    defaults = policy_rules.get("defaults", {})
    if args.grace is None and isinstance(defaults, dict) and "grace" in defaults:
        args.grace = defaults.get("grace")
    policy_enabled = not args.policy_off
    enabled_list = [
        f"{key}:{bool(value.get('enabled'))}"
        for key, value in policy_rules.items()
        if key != "defaults"
    ]
    print(
        f"POLICY_LOADED: keys={list(policy_rules.keys())} "
        f"enabled={enabled_list} path={POLICY_RULES_PATH.as_posix()}"
    )
    policy_mode = "OFF (cli)" if args.policy_off else "ON (config)"
    print(f"POLICY_MODE: {policy_mode}")

    filtered = []
    excluded_samples = 0
    soften_applied = 0
    policy_applied = 0
    policy_applied_counts = {key: 0 for key in policy_rules.keys() if key != "defaults"}
    policy_delta_applied_events = 0
    policy_delta_capped_events = 0
    policy_apply_debugged = False
    mitigated_debugged = False
    policy_debugged = False
    shadow_counts = {"director_regressions_soften_v2": 0}
    max_risk_level = "low"
    max_risk_rank = RISK_LEVEL_ORDER[max_risk_level]
    for event in events:
        ts = event.get("ts")
        if not isinstance(ts, (int, float)):
            stats["no_ts"] += 1
            continue
        if cutoff is not None and ts < cutoff:
            stats["older"] += 1
            continue

        if event.get("type") == "rollback_outcome":
            status = event.get("status")
            if status in rollback_outcomes:
                rollback_outcomes[status] += 1
            continue

        decision_class = event.get("decision_class")
        if not decision_class:
            stats["missing_class"] += 1
            if event.get("type") == "director_decision":
                decision_class = "process"
            else:
                decision_class = "legacy_unknown"
            event["decision_class"] = decision_class
        elif decision_class == "unknown":
            decision_class = "legacy_unknown"
            event["decision_class"] = decision_class

        if args.exclude_class and decision_class in args.exclude_class:
            stats["excluded_class"] += 1
            if args.debug_sample_excluded and excluded_samples < args.debug_sample_excluded:
                print(f"EXCLUDED_SAMPLE: {json.dumps(event, ensure_ascii=False)}")
                excluded_samples += 1
            continue

        if "score" not in event:
            confidence = event.get("confidence")
            if isinstance(confidence, (int, float)) and 0 <= confidence <= 1:
                event["score"] = confidence

        score_value = event.get("score")
        if not isinstance(score_value, (int, float)):
            stats["missing_score"] += 1
            continue
        if "penalty_reason" not in event:
            reason_text = extract_reason_text(event)
            event["penalty_reason"] = classify_penalty_reason(reason_text)
        penalty_reason = event.get("penalty_reason")
        if penalty_reason == "regressions":
            mitigation_text = f"{event.get('decision', '')} {event.get('next_step', '')}".lower()
            mitigation_tokens = (
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
            )
            if any(token in mitigation_text for token in mitigation_tokens):
                penalty_reason = "regressions_mitigated"
                event["penalty_reason"] = penalty_reason
        score_before_mitigated = score_value
        if (
            penalty_reason == "regressions_mitigated"
            and event.get("agent") == "director"
            and event.get("decision_class") == "process"
        ):
            score_value = min(1.0, score_value + 0.05)
            event["score"] = score_value
            event["effective_score"] = score_value
        if (
            args.debug_policy_match
            and not policy_debugged
            and event.get("agent") == "director"
            and event.get("decision_class") == "process"
            and penalty_reason == "regressions"
        ):
            matched = []
            skipped = []
            mitigation_text = f"{event.get('decision', '')} {event.get('next_step', '')}".lower()
            for rule_key, rule in policy_rules.items():
                if rule_key == "defaults":
                    continue
                if not rule.get("enabled", False):
                    skipped.append(f"{rule_key}:disabled")
                    continue
                if rule.get("only_type") and event.get("type") != rule.get("only_type"):
                    skipped.append(f"{rule_key}:type_mismatch")
                    continue
                rule_penalty = rule.get("only_penalty_reason")
                if rule_penalty == "regressions":
                    if penalty_reason not in ("regressions", "regressions_mitigated"):
                        skipped.append(f"{rule_key}:penalty_mismatch")
                        continue
                elif rule_penalty is not None and penalty_reason != rule_penalty:
                    skipped.append(f"{rule_key}:penalty_mismatch")
                    continue
                if rule.get("only_decision_class") and event.get("decision_class") != rule.get("only_decision_class"):
                    skipped.append(f"{rule_key}:class_mismatch")
                    continue
                keywords = rule.get("mitigation_keywords", [])
                if keywords and not any(token in mitigation_text for token in keywords):
                    skipped.append(f"{rule_key}:no_keyword_match")
                    continue
                matched.append(rule_key)
            print(
                "POLICY_MATCH_DEBUG: "
                f"event_id={event.get('event_id')} "
                f"class={event.get('decision_class')} "
                f"penalty={penalty_reason} "
                f"matched={matched} "
                f"skipped={skipped}"
            )
            policy_debugged = True
        if penalty_reason == "regressions":
            mitigation_text = f"{event.get('decision', '')} {event.get('next_step', '')}".lower()
            shadow_tokens = (
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
            )
            confidence = event.get("confidence")
            if (
                isinstance(confidence, (int, float))
                and confidence >= 0.6
                and any(token in mitigation_text for token in shadow_tokens)
            ):
                shadow_counts["director_regressions_soften_v2"] += 1
        if policy_enabled:
            mitigation_text = f"{event.get('decision', '')} {event.get('next_step', '')}".lower()
            total_policy_delta = 0.0
            applied_rules = []
            score_before_policy = score_value
            for rule_key, rule in policy_rules.items():
                if rule_key == "defaults":
                    continue
                if not rule.get("enabled", False):
                    continue
                if rule.get("only_type") and event.get("type") != rule.get("only_type"):
                    continue
                rule_penalty = rule.get("only_penalty_reason")
                if rule_penalty == "regressions":
                    if penalty_reason not in ("regressions", "regressions_mitigated"):
                        continue
                elif rule_penalty is not None and penalty_reason != rule_penalty:
                    continue
                if rule.get("only_decision_class") and event.get("decision_class") != rule.get("only_decision_class"):
                    continue
                keywords = rule.get("mitigation_keywords", [])
                if keywords and not any(token in mitigation_text for token in keywords):
                    continue
                rule_delta = float(rule.get("delta", 0.05))
                total_policy_delta += rule_delta
                applied_rules.append(rule_key)
                soften_applied += 1
                if rule_key == POLICY_VERSION:
                    policy_applied += 1
                if rule_key in policy_applied_counts:
                    policy_applied_counts[rule_key] += 1
            if total_policy_delta > 0:
                applied_delta = total_policy_delta
                if args.policy_max_delta is not None:
                    applied_delta = min(applied_delta, float(args.policy_max_delta))
                    if total_policy_delta > float(args.policy_max_delta):
                        policy_delta_capped_events += 1
                policy_delta_applied_events += 1
                score_value = min(1.0, score_value + applied_delta)
                event["effective_score"] = score_value
                event["policy_version"] = applied_rules[-1]
                event["policy_adjustment"] = applied_delta
                if args.debug_policy_apply and not policy_apply_debugged:
                    print(
                        "POLICY_APPLY_SAMPLE: "
                        f"event_id={event.get('event_id')} "
                        f"score_before={score_before_policy:.3f} "
                        f"total_delta={applied_delta:.3f} "
                        f"score_after={score_value:.3f} "
                        f"rules={applied_rules}"
                    )
                    policy_apply_debugged = True
            else:
                event["effective_score"] = score_before_policy
            if (
                args.debug_mitigated
                and not mitigated_debugged
                and penalty_reason == "regressions_mitigated"
            ):
                print(
                    "MITIGATED_SAMPLE: "
                    f"event_id={event.get('event_id')} "
                    f"score_before={score_before_mitigated:.3f} "
                    f"score_after_norm={event.get('score'):.3f} "
                    f"used_for_avg={event.get('effective_score'):.3f}"
                )
                mitigated_debugged = True

        risk_level = normalize_risk_level(event.get("risk_level"))
        if risk_level:
            risk_rank = RISK_LEVEL_ORDER[risk_level]
            if risk_rank > max_risk_rank:
                max_risk_rank = risk_rank
                max_risk_level = risk_level
        filtered.append(event)

    kept_events = filtered
    stats["kept"] = len(kept_events)
    count_for_min_required = len(kept_events)
    events_for_scoring = [
        event for event in kept_events if event.get("synthetic") is not True
    ]
    events = events_for_scoring
    if args.debug_window:
        for event in events:
            score = event.get("score")
            effective_score = event.get("effective_score", score)
            used_for_avg = isinstance(effective_score, (int, float))
            print(
                "WINDOW_EVENT: "
                f"event_id={event.get('event_id')} "
                f"score={score} "
                f"effective_score={effective_score} "
                f"confidence={event.get('confidence')} "
                f"used_for_avg={str(used_for_avg).lower()}"
            )

    now = time.time()
    bucket_limits = [10, 30, 60, 120]
    bucket_counts = {limit: 0 for limit in bucket_limits}
    for event in events:
        ts = event.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        age_minutes = (now - ts) / 60
        for limit in bucket_limits:
            if age_minutes <= limit:
                bucket_counts[limit] += 1

    raw_scores = [e.get("score") for e in events if isinstance(e.get("score"), (int, float))]
    effective_scores = [
        e.get("effective_score", e.get("score"))
        for e in events
        if isinstance(e.get("effective_score", e.get("score")), (int, float))
    ]
    if not effective_scores:
        print("NO_SCORES")
        maybe_exit(0)
        return

    avg = sum(effective_scores) / len(effective_scores)
    avg_for_trend = avg
    mn = min(effective_scores)
    mx = max(effective_scores)
    bad = sum(1 for s in effective_scores if s < 0.6)
    ok = sum(1 for s in effective_scores if 0.6 <= s <= 0.8)
    good = sum(1 for s in effective_scores if s > 0.8)

    raw_avg = sum(raw_scores) / len(raw_scores) if raw_scores else None
    raw_avg_value = f"{raw_avg:.6f}" if raw_avg is not None else "NA"
    print(f"AVG_DEBUG: raw_avg={raw_avg_value} effective_avg={avg_for_trend:.6f}")
    print(
        f"DECISION_TREND last={len(effective_scores)} avg={avg_for_trend:.3f} "
        f"min={mn:.3f} max={mx:.3f}"
    )
    if args.fail_below_avg is not None or args.print_bad_penalties:
        base_threshold = args.fail_below_avg if args.fail_below_avg is not None else 0.6
        high_risk_count = 0
        for event in events:
            risk_level = normalize_risk_level(event.get("risk_level"))
            if risk_level in ("high", "critical"):
                high_risk_count += 1
        sample_count = len(events)
        high_risk_share = high_risk_count / sample_count if sample_count else 0.0
        hrs = round(high_risk_share, 2)
        effective_threshold = base_threshold
        min_samples_for_adaptive = 10
        adaptive_guard_status = "OK"
        if sample_count < min_samples_for_adaptive:
            adaptive_guard_status = "SKIP"
            print(f"ADAPTIVE_GUARD: SKIP (insufficient_samples={sample_count})")
        else:
            print(f"ADAPTIVE_GUARD: OK (samples={sample_count})")
            if hrs >= 0.8:
                effective_threshold = base_threshold + 0.10
            elif hrs >= 0.5:
                effective_threshold = base_threshold + 0.05
            elif hrs >= 0.4:
                effective_threshold = base_threshold + 0.03
        print(
            "ADAPTIVE_THRESHOLD: "
            f"base={base_threshold} effective={effective_threshold} "
            f"high_risk_share={hrs:.2f} "
            f"high_risk_count={high_risk_count} total={sample_count}"
        )
        cooldown_path = Path("data/reports/adaptive_threshold_state.json")
        cooldown_path.parent.mkdir(parents=True, exist_ok=True)
        now_ts = time.time()
        prev_effective = None
        adaptive_cooldown_mode = "INIT"
        if not cooldown_path.exists():
            cooldown_path.write_text(
                json.dumps(
                    {
                        "last_effective_threshold": effective_threshold,
                        "ts": now_ts,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            print(f"ADAPTIVE_COOLDOWN: INIT (effective={effective_threshold:.2f})")
            prev_effective = effective_threshold
        else:
            last_effective = None
            last_ts = None
            try:
                state = json.loads(cooldown_path.read_text(encoding="utf-8"))
                last_effective = state.get("last_effective_threshold")
                last_ts = state.get("ts")
            except json.JSONDecodeError:
                last_effective = None
                last_ts = None
            if isinstance(last_effective, (int, float)):
                prev_effective = last_effective
            hold_cooldown = False
            minutes_since_change = None
            if isinstance(last_effective, (int, float)) and isinstance(last_ts, (int, float)):
                minutes_since_change = (now_ts - last_ts) / 60
                if minutes_since_change < 60:
                    effective_threshold = last_effective
                    hold_cooldown = True
            if hold_cooldown:
                adaptive_cooldown_mode = "HOLD"
                minutes_value = int(minutes_since_change or 0)
                print(
                    "ADAPTIVE_COOLDOWN: HOLD "
                    f"(effective={effective_threshold:.2f} minutes_since_change={minutes_value})"
                )
            else:
                adaptive_cooldown_mode = "UPDATE"
                cooldown_path.write_text(
                    json.dumps(
                        {
                            "last_effective_threshold": effective_threshold,
                            "ts": now_ts,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                print(f"ADAPTIVE_COOLDOWN: UPDATE (effective={effective_threshold:.2f})")
        if prev_effective is None:
            prev_effective = effective_threshold
        delta = effective_threshold - prev_effective
        status = "STABLE" if abs(delta) < 1e-9 else "CHANGED"
        delta_str = f"{delta:+.2f}"
        print(
            "ADAPTIVE_STABILITY: "
            f"{status} (effective={effective_threshold:.2f} delta={delta_str})"
        )
        adaptive_status_line = (
            "ADAPTIVE_STATUS: "
            f"guard={adaptive_guard_status} "
            f"samples={sample_count} "
            f"hrs={hrs:.2f} "
            f"effective={effective_threshold:.2f} "
            f"cooldown={adaptive_cooldown_mode} "
            f"stability={status}"
        )
        print(adaptive_status_line)
        threshold = effective_threshold
        grace = args.grace or 0.0

        def classify_threshold(avg_value: float, threshold_value: float, grace_value: float) -> str:
            if avg_value < threshold_value - grace_value:
                return "FAIL"
            if avg_value < threshold_value:
                return "WARN"
            return "PASS"
        base_status = classify_threshold(avg_for_trend, base_threshold, grace)
        effective_status = classify_threshold(avg_for_trend, threshold, grace)
        impact = "none"
        if threshold > base_threshold and base_status == "PASS" and effective_status != "PASS":
            impact = "escalated"
        print(f"ADAPTIVE_IMPACT: {impact}")
        min_required = args.min_count or MIN_EVENTS
        if count_for_min_required < min_required:
            trend_status = "INSUFFICIENT_DATA"
            print(
                f"TREND: {trend_status} (count={count_for_min_required}, min_required={min_required})"
            )
            counts_line = "BUCKET_COUNTS: " + " ".join(
                f"{limit}m={bucket_counts[limit]}" for limit in bucket_limits
            )
            print(counts_line)
            print(
                "WHY_DROPPED: "
                f"total={stats['total']} "
                f"kept={stats['kept']} "
                f"no_ts={stats['no_ts']} "
                f"older={stats['older']} "
                f"excluded_class={stats['excluded_class']} "
                f"missing_score={stats['missing_score']} "
                f"missing_class={stats['missing_class']}"
            )
            print(
                "SHADOW_POLICY_CANDIDATES: "
                f"director_regressions_soften_v2={shadow_counts['director_regressions_soften_v2']}"
            )
            print(
                "ROLLBACK_OUTCOMES: "
                f"simulated={rollback_outcomes['simulated']} "
                f"approved={rollback_outcomes['approved']} "
                f"applied={rollback_outcomes['applied']} "
                f"skipped={rollback_outcomes['skipped']}"
            )
            if args.print_bad_samples:
                samples = 0
                for event in events:
                    score = event.get("effective_score", event.get("score"))
                    if isinstance(score, (int, float)) and score < threshold:
                        confidence = event.get("confidence")
                        decision = str(event.get("decision", ""))
                        next_step = str(event.get("next_step", ""))
                        print("BAD_SAMPLE:")
                        print(f"score={score} confidence={confidence}")
                        print(f"decision=\"{decision}\"")
                        print(f"next_step=\"{next_step}\"")
                        print("---")
                        samples += 1
                        if samples >= args.print_bad_samples:
                            break
            if args.print_bad_penalties:
                penalty_counts = {}
                for event in events:
                    score = event.get("effective_score", event.get("score"))
                    if isinstance(score, (int, float)) and score < threshold:
                        penalty = event.get("penalty_reason") or "other"
                        penalty_counts[penalty] = penalty_counts.get(penalty, 0) + 1
                if penalty_counts:
                    print(
                        "RCA_BAD_PENALTY: "
                        + " ".join(
                            f"{key}={penalty_counts.get(key, 0)}"
                            for key in sorted(penalty_counts.keys())
                        )
                    )
                else:
                    print("RCA_BAD_PENALTY: none")
            if args.emit_json:
                summary = {
                    "trend_status": trend_status,
                    "avg": round(avg_for_trend, 6),
                    "threshold": threshold,
                    "grace": args.grace or 0.0,
                    "counts": {
                        "bad": bad,
                        "ok": ok,
                        "good": good,
                        "total": len(effective_scores),
                    },
                    "policy_mode": "OFF" if args.policy_off else "ON",
                    "policy_applied": {"version": POLICY_VERSION, "count": policy_applied},
                    "policy_applied_counts": policy_applied_counts,
                    "since_minutes": args.since_minutes,
                    "exclude_class": args.exclude_class,
                    "min_count": min_required,
                    "insufficient_reason": (
                        f"total({count_for_min_required}) < min_count({min_required})"
                    ),
                    "max_risk_level": max_risk_level,
                    "shadow_policy_candidates": {
                        "director_regressions_soften_v2": shadow_counts["director_regressions_soften_v2"]
                    },
                    "rollback_outcomes": rollback_outcomes,
                    "rca_bad_debug": {
                        "kept_total": len(effective_scores),
                        "bad_total": bad,
                        "bad_agent_field_present": 0,
                    },
                    "rca_bad_by_agent": {},
                    "rca_bad_by_class_director": {},
                    "rca_bad_penalty_director_process": {},
                }
                print(f"SUMMARY_JSON: {json.dumps(summary, ensure_ascii=False)}")
            maybe_exit(0)
            return
        bad_by_class = {}
        bad_reason_tokens = {}
        penalty_sample = None
        penalty_counts = {key: 0 for key in PENALTY_KEYWORDS}
        penalty_counts["other"] = 0
        regressions_conf = []
        regressions_samples = 0
        rca_bad_by_agent = {}
        bad_agent_field_present = 0
        rca_sample_printed = False
        missing_agent_samples = 0
        rca_bad_by_class_director = {}
        rca_bad_penalty_director_process = {}
        mitigated_counts_director_process = {"regressions_mitigated": 0, "regressions": 0}
        if events:
            for event in events:
                if (
                    event.get("agent") == "director"
                    and event.get("decision_class") == "process"
                ):
                    penalty_bucket = event.get("penalty_reason")
                    if penalty_bucket in mitigated_counts_director_process:
                        mitigated_counts_director_process[penalty_bucket] += 1
                score = event.get("score")
                if isinstance(score, (int, float)) and score < threshold:
                    decision_class = event.get("decision_class")
                    if not decision_class or decision_class == "unknown":
                        decision_class = "legacy_unknown"
                    bad_by_class[decision_class] = bad_by_class.get(decision_class, 0) + 1
                    penalty_reason = event.get("penalty_reason") or "other"
                    penalty_counts[penalty_reason] = penalty_counts.get(penalty_reason, 0) + 1
                    if penalty_sample is None:
                        penalty_sample = (
                            f"PENALTY_SAMPLE: event_id={event.get('event_id')} "
                            f"penalty_reason={penalty_reason}"
                        )
                    if penalty_reason == "regressions":
                        confidence = event.get("confidence")
                        if isinstance(confidence, (int, float)):
                            regressions_conf.append(confidence)
                        if (
                            args.debug_sample_regressions_bad
                            and regressions_samples < args.debug_sample_regressions_bad
                        ):
                            decision = str(event.get("decision", ""))
                            next_step = str(event.get("next_step", ""))
                            print(
                                "REGRESSIONS_BAD_SAMPLE: "
                                f"event_id={event.get('event_id')} "
                                f"decision=\"{decision}\" "
                                f"next_step=\"{next_step}\""
                            )
                            regressions_samples += 1
                    reason_text = extract_reason_text(event)
                    for token in reason_text.lower().split():
                        token = token.strip(".,:;!?()[]{}<>\"'")
                        if len(token) < 4:
                            continue
                        bad_reason_tokens[token] = bad_reason_tokens.get(token, 0) + 1
                    if not rca_sample_printed:
                        e = event
                        print(f"RCA_BAD_SAMPLE_KEYS: {sorted(list(e.keys()))}")
                        print(f"RCA_BAD_SAMPLE_AGENT: {e.get('agent')}")
                        rca_sample_printed = True
                    if (
                        args.debug_sample_missing_agent
                        and event.get("agent") is None
                        and missing_agent_samples < args.debug_sample_missing_agent
                    ):
                        print(
                            "MISSING_AGENT_SAMPLE: "
                            f"type={event.get('type')} keys={sorted(event.keys())}"
                        )
                        missing_agent_samples += 1
                        break
                    agent_value = event.get("agent", "unknown")
                    if agent_value and agent_value != "unknown":
                        bad_agent_field_present += 1
                    rca_bad_by_agent[agent_value] = rca_bad_by_agent.get(agent_value, 0) + 1
                    if agent_value == "director":
                        director_class = event.get("decision_class") or "unknown"
                        rca_bad_by_class_director[director_class] = (
                            rca_bad_by_class_director.get(director_class, 0) + 1
                        )
                        if director_class == "process":
                            penalty_value = event.get("penalty_reason") or "missing"
                            rca_bad_penalty_director_process[penalty_value] = (
                                rca_bad_penalty_director_process.get(penalty_value, 0) + 1
                            )
        root_cause = "ROOT_CAUSE: " + " ".join(
            f"{key}={bad_by_class[key]}" for key in sorted(bad_by_class.keys())
        ) if bad_by_class else "ROOT_CAUSE: none"
        ordered_classes = ["process", "infra", "security", "product", "legacy_unknown"]
        bad_by_class_line = "BAD_BY_CLASS: " + " ".join(
            f"{key}={bad_by_class.get(key, 0)}" for key in ordered_classes
        )
        top_bad_reasons = sorted(
            bad_reason_tokens.items(),
            key=lambda item: (-item[1], item[0])
        )[:3]
        bad_reasons_line = (
            "BAD_REASONS_TOP3: "
            + " ".join(f"{token}({count})" for token, count in top_bad_reasons)
            if top_bad_reasons
            else "BAD_REASONS_TOP3: none"
        )
        penalty_counts_line = (
            "PENALTY_COUNTS_BAD: "
            + " ".join(
                f"{key}={penalty_counts.get(key, 0)}"
                for key in ["regressions", "coverage", "insufficient", "other"]
            )
        )
        if args.print_bad_penalties:
            if penalty_counts:
                print(
                    "RCA_BAD_PENALTY: "
                    + " ".join(
                        f"{key}={penalty_counts.get(key, 0)}"
                        for key in sorted(penalty_counts.keys())
                    )
                )
            else:
                print("RCA_BAD_PENALTY: none")
        rca_bad_debug_line = (
            "RCA_BAD_DEBUG: "
            f"kept_total={len(effective_scores)} "
            f"bad_total={bad} "
            f"bad_agent_field_present={bad_agent_field_present}"
        )
        director_class_keys = ["process", "infra", "security", "product", "unknown"]
        rca_bad_by_class_director_line = "RCA_BAD_BY_CLASS_DIRECTOR: " + " ".join(
            f"{key}={rca_bad_by_class_director.get(key, 0)}" for key in director_class_keys
        )
        penalty_keys = ["regressions", "coverage", "insufficient", "other", "missing"]
        rca_bad_penalty_director_process_line = (
            "RCA_BAD_PENALTY_DIRECTOR_PROCESS: "
            + " ".join(
                f"{key}={rca_bad_penalty_director_process.get(key, 0)}" for key in penalty_keys
            )
        )
        rca_mitigated_count_line = (
            "RCA_MITIGATED_COUNT_DIRECTOR_PROCESS: "
            f"regressions_mitigated={mitigated_counts_director_process['regressions_mitigated']} "
            f"regressions={mitigated_counts_director_process['regressions']}"
        )
        known_agents = ["director", "architect", "qa", "security", "dev", "unknown"]
        extra_agents = sorted(key for key in rca_bad_by_agent.keys() if key not in known_agents)
        agent_keys = known_agents + extra_agents
        rca_bad_by_agent_line = "RCA_BAD_BY_AGENT: " + " ".join(
            f"{key}={rca_bad_by_agent.get(key, 0)}" for key in agent_keys
        )
        policy_applied_line = f"POLICY_APPLIED: {POLICY_VERSION} count={policy_applied}"
        policy_applied_all_line = "POLICY_APPLIED_ALL: " + " ".join(
            f"{key}={policy_applied_counts.get(key, 0)}"
            for key in sorted(policy_applied_counts.keys())
        )
        policy_delta_capped_line = (
            "POLICY_DELTA_CAPPED: "
            f"applied={policy_delta_applied_events} "
            f"capped={policy_delta_capped_events} "
            f"max_delta={args.policy_max_delta if args.policy_max_delta is not None else 'none'}"
        )
        if regressions_conf:
            regressions_conf_line = (
                f"REGRESSIONS_CONF_RANGE_BAD: min={min(regressions_conf):.3f} "
                f"max={max(regressions_conf):.3f} count={len(regressions_conf)}"
            )
        else:
            regressions_conf_line = "REGRESSIONS_CONF_RANGE_BAD: min=NA max=NA count=0"

        grace = args.grace or 0.0
        if avg_for_trend < threshold - grace:
            trend_status = "FAIL"
            print(
                f"TREND: FAIL (avg={avg_for_trend:.3f}, threshold={threshold}, grace={grace}) "
                f"bad={bad} ok={ok} good={good}"
            )
            print(root_cause)
            print(bad_by_class_line)
            print(bad_reasons_line)
            print(penalty_counts_line)
            print(rca_bad_debug_line)
            print(rca_bad_by_agent_line)
            print(rca_bad_by_class_director_line)
            print(rca_bad_penalty_director_process_line)
            print(regressions_conf_line)
            print(policy_applied_line)
            print(policy_applied_all_line)
            print(policy_delta_capped_line)
            print(rca_mitigated_count_line)
            print(f"SOFTEN_APPLIED: {soften_applied}")
            if penalty_sample:
                print(penalty_sample)
            counts_line = "BUCKET_COUNTS: " + " ".join(
                f"{limit}m={bucket_counts[limit]}" for limit in bucket_limits
            )
            print(counts_line)
            print(
                "WHY_DROPPED: "
                f"total={stats['total']} "
                f"kept={stats['kept']} "
                f"no_ts={stats['no_ts']} "
                f"older={stats['older']} "
                f"excluded_class={stats['excluded_class']} "
                f"missing_score={stats['missing_score']} "
                f"missing_class={stats['missing_class']}"
            )
            print(
                "SHADOW_POLICY_CANDIDATES: "
                f"director_regressions_soften_v2={shadow_counts['director_regressions_soften_v2']}"
            )
            print(
                "ROLLBACK_OUTCOMES: "
                f"simulated={rollback_outcomes['simulated']} "
                f"approved={rollback_outcomes['approved']} "
                f"applied={rollback_outcomes['applied']} "
                f"skipped={rollback_outcomes['skipped']}"
            )
            if args.emit_json:
                summary = {
                    "trend_status": trend_status,
                    "avg": round(avg_for_trend, 6),
                    "threshold": threshold,
                    "grace": grace,
                    "counts": {
                        "bad": bad,
                        "ok": ok,
                        "good": good,
                        "total": len(effective_scores),
                    },
                    "policy_mode": "OFF" if args.policy_off else "ON",
                    "policy_applied": {"version": POLICY_VERSION, "count": policy_applied},
                    "policy_applied_counts": policy_applied_counts,
                    "policy_delta_capped": {
                        "applied": policy_delta_applied_events,
                        "capped": policy_delta_capped_events,
                        "max_delta": args.policy_max_delta,
                    },
                    "since_minutes": args.since_minutes,
                    "exclude_class": args.exclude_class,
                    "min_count": min_required,
                    "max_risk_level": max_risk_level,
                    "shadow_policy_candidates": {
                        "director_regressions_soften_v2": shadow_counts["director_regressions_soften_v2"]
                    },
                    "rollback_outcomes": rollback_outcomes,
                    "rca_bad_debug": {
                        "kept_total": len(effective_scores),
                        "bad_total": bad,
                        "bad_agent_field_present": bad_agent_field_present,
                    },
                    "rca_bad_by_agent": rca_bad_by_agent,
                    "rca_bad_by_class_director": rca_bad_by_class_director,
                    "rca_bad_penalty_director_process": rca_bad_penalty_director_process,
                    "retrofill_applied": retrofill_applied,
                }
                print(f"SUMMARY_JSON: {json.dumps(summary, ensure_ascii=False)}")
            maybe_exit(2)
            return
        if avg_for_trend < threshold:
            trend_status = "WARN"
            print(
                f"TREND: WARN (avg={avg_for_trend:.3f}, threshold={threshold}, grace={grace}) "
                f"bad={bad} ok={ok} good={good}"
            )
            print(policy_delta_capped_line)
        else:
            trend_status = "PASS"
            print(
                f"TREND: PASS (avg={avg_for_trend:.3f}, threshold={threshold}, grace={grace}) "
                f"bad={bad} ok={ok} good={good}"
            )
            print(root_cause)
            print(bad_by_class_line)
            print(bad_reasons_line)
            print(penalty_counts_line)
            print(rca_bad_debug_line)
            print(rca_bad_by_agent_line)
            print(rca_bad_by_class_director_line)
            print(rca_bad_penalty_director_process_line)
            print(regressions_conf_line)
            print(policy_applied_line)
            print(policy_applied_all_line)
            print(policy_delta_capped_line)
            print(rca_mitigated_count_line)
            print(f"SOFTEN_APPLIED: {soften_applied}")
        if penalty_sample:
            print(penalty_sample)
        counts_line = "BUCKET_COUNTS: " + " ".join(
            f"{limit}m={bucket_counts[limit]}" for limit in bucket_limits
        )
        print(counts_line)
        print(
            "WHY_DROPPED: "
            f"total={stats['total']} "
            f"kept={stats['kept']} "
            f"no_ts={stats['no_ts']} "
            f"older={stats['older']} "
            f"excluded_class={stats['excluded_class']} "
            f"missing_score={stats['missing_score']} "
            f"missing_class={stats['missing_class']}"
        )
        print(
            "SHADOW_POLICY_CANDIDATES: "
            f"director_regressions_soften_v2={shadow_counts['director_regressions_soften_v2']}"
        )
        print(
            "ROLLBACK_OUTCOMES: "
            f"simulated={rollback_outcomes['simulated']} "
            f"approved={rollback_outcomes['approved']} "
            f"applied={rollback_outcomes['applied']} "
            f"skipped={rollback_outcomes['skipped']}"
        )
        if args.emit_json:
            summary = {
                "trend_status": trend_status,
                "avg": round(avg_for_trend, 6),
                "threshold": threshold,
                "grace": grace,
                "counts": {
                    "bad": bad,
                    "ok": ok,
                    "good": good,
                    "total": len(effective_scores),
                },
                "policy_mode": "OFF" if args.policy_off else "ON",
                "policy_applied": {"version": POLICY_VERSION, "count": policy_applied},
                "policy_applied_counts": policy_applied_counts,
                "policy_delta_capped": {
                    "applied": policy_delta_applied_events,
                    "capped": policy_delta_capped_events,
                    "max_delta": args.policy_max_delta,
                },
                "since_minutes": args.since_minutes,
                "exclude_class": args.exclude_class,
                "min_count": min_required,
                "max_risk_level": max_risk_level,
                "shadow_policy_candidates": {
                    "director_regressions_soften_v2": shadow_counts["director_regressions_soften_v2"]
                },
                "rollback_outcomes": rollback_outcomes,
                "rca_bad_debug": {
                    "kept_total": len(effective_scores),
                    "bad_total": bad,
                    "bad_agent_field_present": bad_agent_field_present,
                },
                "rca_bad_by_agent": rca_bad_by_agent,
                "rca_bad_by_class_director": rca_bad_by_class_director,
                "rca_bad_penalty_director_process": rca_bad_penalty_director_process,
                "retrofill_applied": retrofill_applied,
            }
            print(f"SUMMARY_JSON: {json.dumps(summary, ensure_ascii=False)}")
        maybe_exit(0)
        return


if __name__ == "__main__":
    main()
