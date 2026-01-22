import json
from collections import Counter, defaultdict
from pathlib import Path

CANDIDATE_LOGS = [
    Path("data/decision_events.log"),
    Path("data/reports/decision_events.log"),
    Path("data/decision_events.jsonl"),
    Path("data/reports/decision_events.jsonl"),
]

# add dashboard artifact locations (unpacked from Actions)
CANDIDATE_LOGS += sorted(Path("data/reports").glob("decision-dashboard-*/intelligence_timeline.jsonl"))
CANDIDATE_LOGS += sorted(Path("data/reports").glob("decision-dashboard-*/decision_events.log"))
CANDIDATE_LOGS += sorted(Path("data/reports").glob("decision-dashboard-*/decision_events.jsonl"))

OUT_JSON = Path("data/reports/override_uncertainty_corr.json")


def _iter_events(path: Path):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except Exception:
            # skip non-JSON lines
            continue


def _pick_log_path() -> Path:
    for p in CANDIDATE_LOGS:
        if p.exists() and p.stat().st_size > 0:
            return p
    raise FileNotFoundError(
        "No decision events log found. Tried: " + ", ".join(str(p) for p in CANDIDATE_LOGS)
    )


def main() -> int:
    log_path = _pick_log_path()

    total = 0
    override_total = 0

    # correlation counters
    by_uncertainty = Counter()
    by_reason = Counter()
    by_kind = Counter()
    by_reason_unc = Counter()

    samples = defaultdict(list)

    for e in _iter_events(log_path):
        total += 1
        oc = e.get("override_context") or {}
        present = bool(oc.get("present"))
        if not present:
            continue

        override_total += 1
        unc = (e.get("uncertainty") or "unknown").lower()
        reason = (oc.get("reason") or "unknown")
        kind = (oc.get("override_kind") or "unknown")

        by_uncertainty[unc] += 1
        by_reason[reason] += 1
        by_kind[kind] += 1
        by_reason_unc[(reason, unc)] += 1

        if len(samples[(reason, unc)]) < 3:
            samples[(reason, unc)].append({
                "decision": e.get("decision"),
                "confidence": e.get("confidence"),
                "score": e.get("score"),
                "risk_level": e.get("risk_level"),
                "decision_class": e.get("decision_class"),
            })

    report = {
        "log_path": str(log_path),
        "events_total": total,
        "override_events_total": override_total,
        "override_rate": (override_total / total) if total else 0.0,
        "by_uncertainty": dict(by_uncertainty.most_common()),
        "by_override_reason": dict(by_reason.most_common()),
        "by_override_kind": dict(by_kind.most_common()),
        "top_reason_x_uncertainty": [
            {"reason": r, "uncertainty": u, "count": c, "samples": samples[(r, u)]}
            for (r, u), c in by_reason_unc.most_common(10)
        ],
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    top = ", ".join([f"{k}={v}" for k, v in by_uncertainty.most_common()])
    print(f"OVERRIDE_UNCERTAINTY_CORR: overrides={override_total}/{total} by_uncertainty[{top}] saved={OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
