#!/usr/bin/env python3
import json
import sqlite3
from pathlib import Path


LOG_PATH = Path("data/decision_events.log")
DB_PATH = Path("data/decision_events.db")


def main() -> None:
    if not LOG_PATH.exists():
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_events (
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
        conn.execute("BEGIN")
        insert_sql = (
            "INSERT OR IGNORE INTO decision_events "
            "(event_id, ts, type, decision, next_step, confidence, score, risk_level, schema_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_id = event.get("event_id")
            if not event_id:
                continue
            conn.execute(
                insert_sql,
                (
                    event_id,
                    event.get("ts"),
                    event.get("type"),
                    event.get("decision"),
                    event.get("next_step"),
                    event.get("confidence"),
                    event.get("score"),
                    event.get("risk_level"),
                    event.get("schema_version"),
                ),
            )
        conn.commit()

        row_count = conn.execute("SELECT COUNT(*) FROM decision_events").fetchone()[0]
        unique_count = conn.execute("SELECT COUNT(DISTINCT event_id) FROM decision_events").fetchone()[0]
        print(f"rows={row_count}, unique_event_id={unique_count}")

        for ts, event_id, score, decision in conn.execute(
            "SELECT ts, event_id, score, decision FROM decision_events ORDER BY ts DESC LIMIT 2"
        ):
            print(f"{ts} {event_id} {score} {decision}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
