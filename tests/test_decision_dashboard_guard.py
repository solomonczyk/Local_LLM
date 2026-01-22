import sqlite3
import subprocess
import sys


def test_decision_dashboard_guard_exits_on_low_avg_score(tmp_path):
    db_path = tmp_path / "decision_events.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE decision_events (
                event_id TEXT PRIMARY KEY,
                ts REAL,
                type TEXT,
                decision TEXT,
                next_step TEXT,
                confidence REAL,
                score REAL,
                risk_level TEXT,
                schema_version TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO decision_events
            (event_id, ts, type, decision, next_step, confidence, score, risk_level, schema_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("e1", 1.0, "director_decision", "test", "next", 0.5, 0.5, "low", "1.0"),
        )
        conn.commit()
    finally:
        conn.close()

    result = subprocess.run(
        [
            sys.executable,
            "tools/decision_dashboard.py",
            "--db",
            str(db_path),
            "--fail-below-score",
            "0.6",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
