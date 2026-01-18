import json

from agent_system import decision_log


def test_dedupe_checks_tail_only(monkeypatch, tmp_path):
    log_path = tmp_path / "decision_events.log"
    metrics_path = tmp_path / "metrics.json"

    monkeypatch.setattr(decision_log, "METRICS_PATH", metrics_path)
    monkeypatch.setattr(decision_log, "_TAIL_CHECK_LINES", 200)

    payload = {
        "type": "director_decision",
        "decision": "Tail check behavior",
        "next_step": "Append anyway",
        "confidence": 0.42,
        "risks": ["tail-only check"],
    }
    target_event_id = decision_log._compute_event_id(payload)

    total_lines = 205  # N + 5 where N=200
    lines = []
    for idx in range(total_lines):
        event_id = target_event_id if idx == 0 else f"dummy-{idx}"
        lines.append(json.dumps({"event_id": event_id}))
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    decision_log.append_decision_event(log_path, payload)

    updated = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(updated) == total_lines + 1
    last = json.loads(updated[-1])
    assert last.get("event_id") == target_event_id
