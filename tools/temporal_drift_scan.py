#!/usr/bin/env python3
import json
from pathlib import Path

TIMELINE_PATH = Path("data/reports/intelligence_timeline.jsonl")
OUT_PATH = Path("data/reports/temporal_signal.json")


def _load_timeline() -> list:
    if not TIMELINE_PATH.exists():
        return []
    lines = [
        ln for ln in TIMELINE_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _num(value):
    return value if isinstance(value, (int, float)) else None


def _num_int(value):
    return value if isinstance(value, int) else None


def _get_metric(event: dict, key: str):
    value = event.get(key)
    if value is None:
        metrics = event.get("metrics")
        if isinstance(metrics, dict):
            value = metrics.get(key)
    return _num(value)


def main() -> None:
    timeline = _load_timeline()
    if len(timeline) < 2:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "prev_event_id": "unknown",
            "curr_event_id": "unknown",
            "delta_confidence": None,
            "delta_score": None,
            "delta_latency_ms": None,
            "delta_prompt_tokens": None,
            "delta_completion_tokens": None,
            "trend": "insufficient_data",
        }
        with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return

    timeline.sort(key=lambda r: r.get("ts_utc", 0))
    prev = timeline[-2]
    curr = timeline[-1]
    prev_ts = prev.get("ts_utc")
    curr_ts = curr.get("ts_utc")
    prev_id = prev.get("event_id") or prev.get("id") or str(prev_ts)
    curr_id = curr.get("event_id") or curr.get("id") or str(curr_ts)
    backend_changed = prev.get("backend") != curr.get("backend")
    lora_changed = prev.get("lora") != curr.get("lora")
    git_changed = prev.get("git_sha") != curr.get("git_sha")
    intelligence_changed = backend_changed or lora_changed or git_changed
    delta_seconds = (
        curr_ts - prev_ts
        if isinstance(prev_ts, (int, float)) and isinstance(curr_ts, (int, float))
        else None
    )
    if prev_id == "unknown" or curr_id == "unknown":
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "prev_event_id": prev_id,
            "curr_event_id": curr_id,
            "delta_confidence": None,
            "delta_score": None,
            "delta_latency_ms": None,
            "delta_prompt_tokens": None,
            "delta_completion_tokens": None,
            "trend": "insufficient_data",
        }
        with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return

    prev_conf = _get_metric(prev, "confidence")
    curr_conf = _get_metric(curr, "confidence")
    prev_score = _get_metric(prev, "score")
    curr_score = _get_metric(curr, "score")
    prev_latency = _get_metric(prev, "latency_ms")
    curr_latency = _get_metric(curr, "latency_ms")
    prev_prompt = _get_metric(prev, "prompt_tokens")
    curr_prompt = _get_metric(curr, "prompt_tokens")
    prev_completion = _get_metric(prev, "completion_tokens")
    curr_completion = _get_metric(curr, "completion_tokens")
    prev_eval_pass = _num_int(prev.get("eval_pass"))
    curr_eval_pass = _num_int(curr.get("eval_pass"))
    prev_eval_fail = _num_int(prev.get("eval_fail"))
    curr_eval_fail = _num_int(curr.get("eval_fail"))
    delta_eval_pass = (
        curr_eval_pass - prev_eval_pass
        if prev_eval_pass is not None and curr_eval_pass is not None
        else None
    )
    delta_eval_fail = (
        curr_eval_fail - prev_eval_fail
        if prev_eval_fail is not None and curr_eval_fail is not None
        else None
    )

    delta_conf = curr_conf - prev_conf if prev_conf is not None and curr_conf is not None else None
    delta_score = curr_score - prev_score if prev_score is not None and curr_score is not None else None
    delta_latency = (
        curr_latency - prev_latency
        if prev_latency is not None and curr_latency is not None
        else None
    )
    delta_prompt = (
        curr_prompt - prev_prompt
        if prev_prompt is not None and curr_prompt is not None
        else None
    )
    delta_completion = (
        curr_completion - prev_completion
        if prev_completion is not None and curr_completion is not None
        else None
    )

    deltas = [
        delta_conf,
        delta_score,
        delta_latency,
        delta_prompt,
        delta_completion,
    ]
    trend = "stable"
    reason = None
    if all(d is None for d in deltas):
        if delta_eval_fail is not None:
            if delta_eval_fail > 0:
                trend = "degrading"
            elif delta_eval_fail < 0:
                trend = "improving"
            elif delta_eval_pass is not None and delta_eval_pass != 0:
                trend = "improving"
            else:
                trend = "stable"
            reason = "eval_drift"
        else:
            trend = "insufficient_data"
            reason = "no_numeric_fields"
    elif (delta_conf is not None and delta_conf < -0.1) or (
        delta_score is not None and delta_score < -0.1
    ):
        trend = "degrading"
    elif (delta_conf is not None and delta_conf > 0.1) or (
        delta_score is not None and delta_score > 0.1
    ):
        trend = "improving"

    if (
        intelligence_changed
        and delta_eval_fail == 0
        and delta_eval_pass == 0
        and trend in ("stable", "improving")
    ):
        trend = "drift"
        reason = "intelligence_changed_no_metric_change"
    elif trend == "stable" and delta_seconds is not None and delta_seconds >= 3600:
        trend = "stale"
        reason = "no_change_over_time"

    payload = {
        "prev_event_id": prev_id,
        "curr_event_id": curr_id,
        "delta_confidence": delta_conf,
        "delta_score": delta_score,
        "delta_latency_ms": delta_latency,
        "delta_prompt_tokens": delta_prompt,
        "delta_completion_tokens": delta_completion,
        "delta_eval_pass": delta_eval_pass,
        "delta_eval_fail": delta_eval_fail,
        "delta_seconds": delta_seconds,
        "backend_changed": backend_changed,
        "lora_changed": lora_changed,
        "git_changed": git_changed,
        "trend": trend,
    }
    if reason is not None:
        payload["reason"] = reason
    if trend == "degrading":
        gate = "TEMPORAL_GATE: SOFT (regression_detected)"
    elif trend == "drift":
        gate = "TEMPORAL_GATE: SOFT (intelligence_drift)"
    elif trend == "stale":
        gate = "TEMPORAL_GATE: PASS (stale)"
    else:
        gate = "TEMPORAL_GATE: PASS"
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(gate)


if __name__ == "__main__":
    main()
