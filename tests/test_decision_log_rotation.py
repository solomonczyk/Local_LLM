import json

from agent_system import decision_log


def test_decision_log_rotation(monkeypatch, tmp_path):
    log_path = tmp_path / "decision_events.log"
    metrics_path = tmp_path / "metrics.json"

    monkeypatch.setattr(decision_log, "METRICS_PATH", metrics_path)
    monkeypatch.setattr(decision_log, "MAX_LOG_BYTES", 1)

    log_path.write_text("xx", encoding="utf-8")

    payload = {
        "type": "director_decision",
        "decision": "Rotate log",
        "next_step": "Verify rotation",
        "confidence": 0.1,
        "risks": ["test"],
    }

    decision_log.append_decision_event(log_path, payload)

    rotated = list(tmp_path.glob("decision_events_*.log"))
    assert rotated, "rotation file not created"

    assert metrics_path.exists()
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert data.get("log_rotations", 0) >= 1
