#!/usr/bin/env python3
import argparse
import json
import time
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_LOG = Path("data/decision_events.log")
ALL_LOG_GLOB = "data/decision_events*.log"
TOP_N = 5
CONF_BUCKETS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def _iter_logs(include_all: bool) -> List[Path]:
    if include_all:
        return sorted(Path(".").glob(ALL_LOG_GLOB))
    return [DEFAULT_LOG]


def _load_events(paths: Iterable[Path], tail_lines: Optional[int]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if tail_lines is not None:
            lines = lines[-tail_lines:]
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    return events


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _bucketize(confidence: float) -> str:
    for low, high in zip(CONF_BUCKETS, CONF_BUCKETS[1:]):
        if confidence <= high:
            return f"{low:.1f}-{high:.1f}"
    return f">{CONF_BUCKETS[-1]:.1f}"


def _top_items(counter: Counter) -> List[Dict[str, Any]]:
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [{"text": value, "count": count} for value, count in ordered[:TOP_N]]


def _print_top(counter: Counter, label: str) -> None:
    print(label)
    items = _top_items(counter)
    if not items:
        print("  (none)")
        return
    for item in items:
        print(f"  {item['count']} | {item['text']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Decision event reader (JSONL).")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include rotated logs (data/decision_events_*.log).",
    )
    parser.add_argument("--type", dest="type_filter", help="Filter events by type.")
    parser.add_argument("--tail", type=int, help="Only read the last N lines from each log.")
    parser.add_argument("--since", type=float, help="Only include events from the last N hours.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument("--out", help="Write JSON report to a file (requires --json).")
    args = parser.parse_args()

    paths = _iter_logs(args.all)
    events = _load_events(paths, args.tail)
    if not events:
        print("NO_EVENTS")
        return

    decisions = Counter()
    next_steps = Counter()
    confidences: List[float] = []

    now = time.time()
    cutoff = None
    if args.since is not None:
        cutoff = now - (args.since * 3600)
    for event in events:
        if args.type_filter and event.get("type") != args.type_filter:
            continue
        if cutoff is not None:
            ts = event.get("ts")
            if not _is_number(ts) or float(ts) < cutoff:
                continue
        decision = event.get("decision")
        if isinstance(decision, str) and decision.strip():
            decisions[decision.strip()] += 1

        next_step = event.get("next_step")
        if isinstance(next_step, str) and next_step.strip():
            next_steps[next_step.strip()] += 1

        confidence = event.get("confidence")
        if _is_number(confidence):
            confidences.append(float(confidence))

    top_decisions = _top_items(decisions)
    top_next_steps = _top_items(next_steps)

    confidence_summary = None
    confidence_buckets = None
    if confidences:
        buckets = Counter(_bucketize(value) for value in confidences)
        confidence_summary = {
            "min": round(min(confidences), 2),
            "max": round(max(confidences), 2),
            "mean": round(mean(confidences), 2),
            "median": round(median(confidences), 2),
        }
        confidence_buckets = {key: buckets[key] for key in sorted(buckets.keys())}

    if args.json:
        payload = {
            "events": len(events),
            "top_decisions": top_decisions,
            "top_next_steps": top_next_steps,
            "confidence": confidence_summary,
            "confidence_buckets": confidence_buckets,
        }
        output = json.dumps(payload, ensure_ascii=False)
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output, encoding="utf-8")
        print(output)
        return

    print(f"events: {len(events)}")
    _print_top(decisions, "top decisions:")
    _print_top(next_steps, "top next_step:")
    if confidences:
        print(
            "confidence: "
            f"min={confidence_summary['min']:.2f} "
            f"max={confidence_summary['max']:.2f} "
            f"mean={confidence_summary['mean']:.2f} "
            f"median={confidence_summary['median']:.2f}"
        )
        print("confidence buckets:")
        for bucket in sorted(confidence_buckets.keys()):
            print(f"  {bucket}: {confidence_buckets[bucket]}")
    else:
        print("confidence: (none)")


if __name__ == "__main__":
    main()
