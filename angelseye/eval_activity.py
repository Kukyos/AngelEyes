"""Evaluate the confidence shown on vision-model activity events.

Prepare a review sheet from one or more runs, label whether each caption is visibly
correct (1), incorrect (0), or unclear (?), then score it. This reads event output;
it does not call a model or alter the engine.

    python -m angelseye.eval_activity prepare runs/phone/events.json --out runs/activity_labels.csv
    python -m angelseye.eval_activity score runs/phone/events.json --labels runs/activity_labels.csv
"""

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


FIELDS = ("run", "event_id", "model", "caption", "confidence", "keyframe", "correct")


def read_events(paths):
    """Return vision-model activity events, keyed by (run directory, event ID)."""
    events = {}
    seen_runs = set()
    for path in map(Path, paths):
        run = path.parent.name
        if run in seen_runs:
            raise ValueError(f"duplicate run name {run!r}; pass one events.json per run directory")
        seen_runs.add(run)
        data = json.loads(path.read_text())
        for event in data["events"]:
            if event.get("type") != "activity":
                continue
            series = event.get("evidence", {}).get("series", {})
            if series.get("source") != "vision model":
                continue  # tracker entry/exit confidence is not a model prediction
            key = (run, event["id"])
            if key in events:
                raise ValueError(f"duplicate event {key}")
            confidence = float(event["confidence"])
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError(f"invalid confidence for {key}: {confidence}")
            events[key] = {
                "model": series.get("model") or "unknown",
                "caption": series.get("caption") or "",
                "confidence": confidence,
                "keyframe": (event.get("evidence", {}).get("keyframes") or [""])[0],
            }
    if not events:
        raise ValueError("no vision-model activity events found")
    return events


def prepare(events, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", newline="") as f:  # never erase existing human labels
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for (run, event_id), event in sorted(events.items()):
            writer.writerow({"run": run, "event_id": event_id, **event, "correct": ""})


def read_labels(path, events):
    labels = {}
    with Path(path).open(newline="") as f:
        reader = csv.DictReader(f)
        if not {"run", "event_id", "correct"} <= set(reader.fieldnames or []):
            raise ValueError("labels CSV needs run, event_id, correct columns")
        for row in reader:
            key = (row["run"], row["event_id"])
            if key not in events:
                raise ValueError(f"label references an unknown event: {key}")
            if key in labels:
                raise ValueError(f"duplicate label: {key}")
            value = row["correct"].strip()
            if value not in {"0", "1", "?", ""}:
                raise ValueError(f"{key}: correct must be 1, 0, ?, or blank")
            labels[key] = value
    return labels


def metrics(items):
    """Accuracy, Brier score and calibration error for (confidence, correct) pairs."""
    if not items:
        raise ValueError("no labelled activity events to score")
    n = len(items)
    bins = []
    ece = 0.0
    for i in range(5):
        group = [(p, y) for p, y in items if min(int(p * 5), 4) == i]
        count = len(group)
        mean_conf = sum(p for p, _ in group) / count if count else None
        accuracy = sum(y for _, y in group) / count if count else None
        if count:
            ece += count / n * abs(mean_conf - accuracy)
        bins.append({"range": f"[{i / 5:.1f}, {(i + 1) / 5:.1f}{']' if i == 4 else ')'}",
                     "count": count, "mean_confidence": _round(mean_conf), "accuracy": _round(accuracy)})
    return {
        "count": n,
        "accuracy": _round(sum(y for _, y in items) / n),
        "mean_confidence": _round(sum(p for p, _ in items) / n),
        "brier_score": _round(sum((p - y) ** 2 for p, y in items) / n),
        "expected_calibration_error": _round(ece),
        "bins": bins,
    }


def _round(value):
    return round(value, 4) if value is not None else None


def score(events, labels, allow_incomplete=False):
    missing = [key for key in events if labels.get(key, "") == ""]
    unclear = [key for key in events if labels.get(key) == "?"]
    if (missing or unclear) and not allow_incomplete:
        raise ValueError(f"{len(missing)} missing and {len(unclear)} unclear labels; "
                         "complete the sheet or use --allow-incomplete for a provisional report")
    groups = defaultdict(list)
    for key, event in events.items():
        label = labels.get(key)
        if label in {"0", "1"}:
            groups[event["model"]].append((event["confidence"], int(label)))
    if not groups:
        raise ValueError("no labelled activity events to score")
    all_items = [item for group in groups.values() for item in group]
    return {
        "coverage": {"eligible": len(events), "scored": len(all_items),
                     "missing": len(missing), "unclear": len(unclear)},
        "provisional": bool(missing or unclear),
        "overall": metrics(all_items),
        "by_model": {model: metrics(items) for model, items in sorted(groups.items())},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="make a CSV for human review")
    prep.add_argument("events", nargs="+", help="runs/<name>/events.json files")
    prep.add_argument("--out", required=True, help="new labels CSV; existing files are never overwritten")
    report = commands.add_parser("score", help="score completed human labels")
    report.add_argument("events", nargs="+", help="the same runs/<name>/events.json files")
    report.add_argument("--labels", required=True)
    report.add_argument("--out", help="optional JSON report path")
    report.add_argument("--allow-incomplete", action="store_true", help="mark output provisional")
    args = parser.parse_args()
    try:
        events = read_events(args.events)
        if args.command == "prepare":
            prepare(events, args.out)
            print(f"{len(events)} vision-model activity events -> {args.out}")
        else:
            result = score(events, read_labels(args.labels, events), args.allow_incomplete)
            encoded = json.dumps(result, indent=2)
            if args.out:
                out = Path(args.out)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(encoded + "\n")
            print(encoded)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"eval_activity: {exc}\n")


if __name__ == "__main__":
    main()
