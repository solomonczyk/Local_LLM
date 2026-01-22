# Decision Event Schema

This schema defines the JSONL event written to `data/decision_events.log`.

Required fields:
- `event_id` (string)
- `schema_version` (string)
- `ts` (number)
- `type` (string)
- `decision` (string)
- `next_step` (string)

Optional fields:
- `confidence` (number)
- `risks` (array of strings)
- `score` (number)

Deduplication checks only the last tail_n lines for performance; duplicates older than the tail window may be re-appended.
