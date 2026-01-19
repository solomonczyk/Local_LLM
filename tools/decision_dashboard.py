#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys
from pathlib import Path


DB_PATH = Path("data/decision_events.db")
TOP_N = 5
LOW_SCORE_LIMIT = 0.6


def main() -> None:
    parser = argparse.ArgumentParser(description="Decision dashboard (SQLite).")
    parser.add_argument("--out", help="Write report to a markdown file.")
    parser.add_argument("--fail-below-score", type=float, help="Fail if score drops below threshold.")
    parser.add_argument("--db", default=str(DB_PATH), help="SQLite database path.")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print("NO_DB")
        return

    conn = sqlite3.connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM decision_events").fetchone()[0]
        avg_score = conn.execute(
            "SELECT AVG(score) FROM decision_events WHERE score IS NOT NULL"
        ).fetchone()[0]
        avg_confidence = conn.execute(
            "SELECT AVG(confidence) FROM decision_events WHERE confidence IS NOT NULL"
        ).fetchone()[0]

        lines = []
        lines.append(f"events_total: {total}")
        lines.append(f"avg_score: {avg_score:.2f}" if avg_score is not None else "avg_score: N/A")
        lines.append(
            f"avg_confidence: {avg_confidence:.2f}" if avg_confidence is not None else "avg_confidence: N/A"
        )
        lines.append("top_next_steps:")
        rows = conn.execute(
            """
            SELECT next_step, COUNT(*) as cnt
            FROM decision_events
            WHERE next_step IS NOT NULL AND TRIM(next_step) != ''
            GROUP BY next_step
            ORDER BY cnt DESC, next_step ASC
            LIMIT ?
            """,
            (TOP_N,),
        ).fetchall()
        if not rows:
            lines.append("  (none)")
        else:
            for next_step, count in rows:
                lines.append(f"  {count} | {next_step}")

        lines.append("low_score_events:")
        low_rows = conn.execute(
            """
            SELECT ts, event_id, score, decision
            FROM decision_events
            WHERE score IS NOT NULL AND score < ?
            ORDER BY ts DESC
            LIMIT 3
            """,
            (LOW_SCORE_LIMIT,),
        ).fetchall()
        threshold = args.fail_below_score
        low_score_exists = False
        if threshold is not None:
            low_score_exists = conn.execute(
                "SELECT 1 FROM decision_events WHERE score IS NOT NULL AND score < ? LIMIT 1",
                (threshold,),
            ).fetchone() is not None
        if not low_rows:
            lines.append("  (none)")
        else:
            for ts, event_id, score, decision in low_rows:
                lines.append(f"  {ts} | {event_id} | {score:.2f} | {decision}")
    finally:
        conn.close()

    output = "\n".join(lines)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        md_lines = [
            "# Decision Dashboard — Daily Report",
            "",
            "## Summary",
            f"- events_total: {total}",
            f"- avg_score: {avg_score:.2f}" if avg_score is not None else "- avg_score: N/A",
            f"- avg_confidence: {avg_confidence:.2f}" if avg_confidence is not None else "- avg_confidence: N/A",
            "",
            "## Top Next Steps",
        ]
        if not rows:
            md_lines.append("- (none)")
        else:
            for next_step, count in rows:
                md_lines.append(f"- ({count}) {next_step}")
        md_lines.extend(["", "## Low Score Events"])
        if not low_rows:
            md_lines.append("- (none)")
        else:
            for ts, event_id, score, decision in low_rows:
                md_lines.append(f"- {ts} | {event_id} | {score:.2f} | {decision}")
        out_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(output)
    if threshold is not None:
        avg_display = f"{avg_score:.2f}" if avg_score is not None else "N/A"
        auto_guard_line = "AUTO-GUARD: PASS"
        if avg_score is not None and avg_score < threshold:
            auto_guard_line = f"AUTO-GUARD: FAIL (avg_score={avg_display}, threshold={threshold})"
            print(auto_guard_line)
            print(f"AUTO-GUARD FAIL: avg_score={avg_score} < threshold={threshold}")
            summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary_path:
                with Path(summary_path).open("a", encoding="utf-8") as summary_file:
                    summary_file.write(auto_guard_line + "\n")
            sys.exit(2)
        if low_score_exists:
            auto_guard_line = f"AUTO-GUARD: FAIL (avg_score={avg_display}, threshold={threshold})"
            print(auto_guard_line)
            print("AUTO-GUARD FAIL: low_score_event detected")
            summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary_path:
                with Path(summary_path).open("a", encoding="utf-8") as summary_file:
                    summary_file.write(auto_guard_line + "\n")
            sys.exit(2)
        print(auto_guard_line)
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with Path(summary_path).open("a", encoding="utf-8") as summary_file:
                summary_file.write(auto_guard_line + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
