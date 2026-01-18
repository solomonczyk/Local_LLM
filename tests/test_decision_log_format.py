from pathlib import Path

import pytest


def test_decision_log_no_blank_lines():
    log_path = Path("data/decision_events.log")
    if not log_path.exists():
        pytest.skip("decision_events.log not present")
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert all(line.strip() for line in lines)
