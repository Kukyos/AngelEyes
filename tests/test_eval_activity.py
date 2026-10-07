import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "angelseye" / "eval_activity.py"
spec = importlib.util.spec_from_file_location("eval_activity", MODULE)
eval_activity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_activity)
metrics, prepare = eval_activity.metrics, eval_activity.prepare
read_events, read_labels, score = eval_activity.read_events, eval_activity.read_labels, eval_activity.score


def activity(event_id, confidence, source="vision model", model="qwen3-vl"):
    return {"id": event_id, "type": "activity", "confidence": confidence,
            "evidence": {"keyframes": [f"run/keyframes/{event_id}.jpg"],
                         "series": {"source": source, "model": model, "caption": "reading a book"}}}


class ActivityConfidenceTest(unittest.TestCase):
    def test_prepare_and_score_only_model_activities(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            run.mkdir()
            events_path = run / "events.json"
            events_path.write_text(json.dumps({"events": [
                activity("good", 0.9), activity("wrong", 0.8),
                activity("entry", 1.0, source="tracker"),
                {"id": "fall", "type": "fall", "confidence": 0.9},
            ]}))
            events = read_events([events_path])
            self.assertEqual(set(events), {("run", "good"), ("run", "wrong")})

            labels_path = Path(tmp) / "labels.csv"
            prepare(events, labels_path)
            with labels_path.open(newline="") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                row["correct"] = "1" if row["event_id"] == "good" else "0"
            with labels_path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)

            result = score(events, read_labels(labels_path, events))
            self.assertEqual(result["coverage"], {"eligible": 2, "scored": 2, "missing": 0, "unclear": 0})
            self.assertEqual(result["overall"]["accuracy"], 0.5)
            self.assertEqual(result["overall"]["brier_score"], 0.325)
            self.assertEqual(result["overall"]["bins"][4]["count"], 2)

    def test_incomplete_labels_cannot_look_final(self):
        events = {("run", "a"): {"model": "qwen", "confidence": 0.9},
                  ("run", "b"): {"model": "qwen", "confidence": 0.2}}
        with self.assertRaisesRegex(ValueError, "missing"):
            score(events, {("run", "a"): "1"})
        result = score(events, {("run", "a"): "1"}, allow_incomplete=True)
        self.assertTrue(result["provisional"])
        self.assertEqual(result["coverage"]["missing"], 1)

    def test_bad_confidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.json"
            path.write_text(json.dumps({"events": [activity("x", float("nan"))]}))
            with self.assertRaisesRegex(ValueError, "invalid confidence"):
                read_events([path])

    def test_calibration_error_tracks_overconfidence(self):
        result = metrics([(0.9, 0), (0.9, 0)])
        self.assertEqual(result["expected_calibration_error"], 0.9)
        self.assertEqual(result["brier_score"], 0.81)


if __name__ == "__main__":
    unittest.main()
