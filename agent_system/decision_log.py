import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union, Tuple

DECISION_LOG_PATH = Path("data/decision_events.log")
METRICS_PATH = Path("data/metrics.json")
_TAIL_CHECK_LINES = 200
MAX_LOG_BYTES = 5 * 1024 * 1024
logger = logging.getLogger(__name__)

def append_decision_event(
    log_path_or_event: Union[str, Path, Dict[str, Any]],
    event: Optional[Dict[str, Any]] = None,
) -> bool:
    if event is None:
        log_path = DECISION_LOG_PATH
        event = log_path_or_event  # type: ignore[assignment]
    else:
        log_path = Path(log_path_or_event)  # type: ignore[arg-type]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_log_if_needed(log_path)
    event_id = event.get("event_id") or _compute_event_id(event)
    schema_version = event.get("schema_version") or "1.0"
    record = {
        **event,
        "event_id": event_id,
        "schema_version": schema_version,
        "ts": time.time(),
    }
    valid, reason = _validate_record(record)
    if not valid:
        logger.warning("decision_event invalid, not written: %s", reason)
        return False
    if _event_exists(log_path, event_id):
        logger.debug("decision_event skipped (duplicate): event_id=%s", event_id)
        _increment_metric("skipped_duplicates")
        return False
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True


def _compute_event_id(event: Dict[str, Any]) -> str:
    parts = [
        _normalize_text(event.get("type", "")),
        _normalize_text(event.get("decision", "")),
        _normalize_text(event.get("next_step", "")),
        _normalize_confidence(event.get("confidence", "")),
    ]
    payload = "|".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_text(value: Any) -> str:
    text = str(value).strip()
    return " ".join(text.split())


def _normalize_confidence(value: Any) -> str:
    try:
        return "{:.4f}".format(float(value))
    except (TypeError, ValueError):
        return str(value)


def _event_exists(log_path: Path, event_id: str) -> bool:
    if not log_path.exists():
        return False
    try:
        tail = log_path.read_text(encoding="utf-8").splitlines()[-_TAIL_CHECK_LINES:]
    except OSError:
        return False
    for line in tail:
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("event_id") == event_id:
            return True
    return False


def _rotate_log_if_needed(log_path: Path) -> None:
    if not log_path.exists():
        return
    try:
        size = log_path.stat().st_size
    except OSError:
        return
    if size <= MAX_LOG_BYTES:
        return
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    rotated = log_path.with_name(f"decision_events_{timestamp}.log")
    log_path.replace(rotated)
    _increment_metric("log_rotations")


def _validate_record(record: Dict[str, Any]) -> Tuple[bool, str]:
    missing = [key for key in ("event_id", "ts", "type", "decision", "next_step", "schema_version") if key not in record]
    if missing:
        return False, f"missing={missing}"

    for key in ("event_id", "type", "decision", "next_step", "schema_version"):
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            return False, f"invalid_{key}={value!r}"

    ts = record.get("ts")
    if not isinstance(ts, (int, float)) or isinstance(ts, bool):
        return False, f"invalid_ts={ts!r}"

    return True, "ok"


def _increment_metric(name: str) -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: Dict[str, Any] = {}
    if METRICS_PATH.exists():
        try:
            data = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data[name] = int(data.get(name, 0)) + 1
    tmp_path = METRICS_PATH.with_suffix(METRICS_PATH.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(METRICS_PATH)
