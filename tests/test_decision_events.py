import json

from agent_system.decision_log import append_decision_event


def _read_lines(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_append_decision_event_idempotent(tmp_path):
    log_path = tmp_path / "decision_events.log"
    payload = {
        "type": "director_decision",
        "decision": "Approve smoke test",
        "confidence": 0.5,
        "risks": ["test risk"],
        "next_step": "Run smoke",
    }

    append_decision_event(log_path, payload)
    append_decision_event(log_path, payload)

    lines = _read_lines(log_path)
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record.get("decision") == payload["decision"]


def test_append_decision_event_invalid_next_step(tmp_path):
    log_path = tmp_path / "decision_events.log"
    payload = {
        "type": "director_decision",
        "decision": "Approve smoke test",
        "confidence": 0.5,
        "risks": ["test risk"],
        "next_step": "",
    }

    result = append_decision_event(log_path, payload)
    assert result is False
    assert _read_lines(log_path) == []
