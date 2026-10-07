"""Score engine events against ground truth.

    python -m angelseye.eval --build-gt     # data/ground_truth.csv from CAVIAR XML + UR Fall CSV labels
    python -m angelseye.eval --run          # run the engine on every clip in the ground truth -> runs/eval/
    python -m angelseye.eval --gt data/ground_truth.csv

Sources (docs/RESOURCES.md): CAVIAR INRIA lobby (sudden run; walking/meeting negatives) and
UR Fall Detection cam0 (falls; everyday-activity negatives). CAVIAR's own falls are not scored:
its camera is an overhead fisheye, outside the oblique CCTV view the fall rule is built for.

ground_truth.csv: clip, event_type, who, true_start, true_end (seconds into the clip).
Extra detections of an already-matched true event are counted as duplicates, not
false alarms (several people in a crowd run at once). A clip with no events has one row with event_type "none" (it still counts for false alarms);
event_type "unscored" with a behaviour in "who" skips that behaviour for that clip.
Engine output is read from runs/eval/<clip>/events.json (kept apart from the demo runs so the
hub does not load them). Writes runs/eval.json.
"""
import argparse
import csv
import json
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict

from angelseye import ROOT

CAVIAR_FPS = 25.0
URFD_FPS = 30.0
TYPES = ["fall", "sudden_run", "loitering", "following", "sos"]
SLACK_S = 1.0  # a detection counts if it overlaps the true interval within this slack
EVAL_RUNS = ROOT / "runs" / "eval"
SOURCES = ("data/caviar", "data/urfd/rgb", "data/umn")


def run_all(gt_path):
    from angelseye.engine import Engine
    clips = sorted({r["clip"] for r in csv.DictReader(open(gt_path))})
    for clip in clips:
        video = next((p for d in SOURCES for p in (ROOT / d).glob(clip + ".*")), None)
        if video is None:
            print(f"no video for {clip}")
            continue
        Engine(str(video), out=EVAL_RUNS / clip).run()


def caviar_truth(xml_path):
    """sudden_run: any person whose movement label is 'running'."""
    spans = defaultdict(list)  # (type, who) -> [frames]
    for fr in ET.parse(xml_path).getroot().iter("frame"):
        n = int(fr.get("number"))
        for o in fr.iter("object"):
            h = o.find("hypothesislist/hypothesis")
            if h is None:
                continue
            who = o.get("id")
            if h.findtext("movement") == "running":
                spans[("sudden_run", who)].append(n)
    rows = []
    for (typ, who), frames in spans.items():
        frames.sort()
        start = prev = frames[0]
        for f in frames[1:] + [None]:
            if f is None or f - prev > CAVIAR_FPS:  # a gap over 1 s splits the event
                if prev - start >= CAVIAR_FPS * 0.5:
                    rows.append((typ, who, round(start / CAVIAR_FPS, 2), round(prev / CAVIAR_FPS, 2)))
                start = f
            prev = f if f is not None else prev
    return rows


def urfd_truth():
    """Crop UR Fall cam0 videos to their RGB half (data/urfd/rgb/) and read the per-frame labels:
    -1 upright, 0 falling, 1 lying. A fall runs from the first 0 to the last 1."""
    d = ROOT / "data/urfd"
    (d / "rgb").mkdir(exist_ok=True)
    labels = defaultdict(list)
    for name in ("urfall-cam0-falls.csv", "urfall-cam0-adls.csv"):
        for r in csv.reader(open(d / name)):
            labels[r[0]].append((int(r[1]), int(r[2])))
    rows = []
    for v in sorted(d.glob("*-cam0.mp4")):
        clip = v.name[:-len("-cam0.mp4")]
        out = d / "rgb" / f"{clip}.mp4"
        if not out.exists():  # the right half is RGB, the left half is depth
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(v), "-vf", "crop=iw/2:ih:iw/2:0",
                            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(out)], check=True)
        fr = [f for f, lab in labels.get(clip, []) if lab >= 0]
        if clip.startswith("fall") and fr:
            rows.append((clip, "fall", "1", round((min(fr) - 1) / URFD_FPS, 2), round((max(fr) - 1) / URFD_FPS, 2)))
        else:
            rows.append((clip, "none", "", "", ""))
    return rows


def umn_truth():
    """UMN 'Crowd Activity All': the dataset burns its own label into the frame, red
    'Abnormal Crowd Activity' text top-left. Each span of it is one crowd sudden-run."""
    import cv2
    v = ROOT / "data/umn/Crowd-Activity-All.avi"
    cap = cv2.VideoCapture(str(v))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    on = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        roi = f[0:20, 0:160].astype(int)
        on.append(((roi[:, :, 2] > 150) & (roi[:, :, 1] < 90) & (roi[:, :, 0] < 90)).sum() > 40)
    rows, start = [], None
    for k, flag in enumerate(on + [False]):
        if flag and start is None:
            start = k
        elif not flag and start is not None:
            if (k - start) / fps >= 0.5:  # shorter blips are red clothing, not the label
                rows.append((v.stem, "sudden_run", "crowd", round(start / fps, 2), round((k - 1) / fps, 2)))
            start = None
    return rows


def write_gt(path):
    rows = []
    for x in sorted((ROOT / "data/caviar").glob("*.xml")):
        clip = x.stem
        found = caviar_truth(x)
        rows += [(clip, *r) for r in found] or [(clip, "none", "", "", "")]
        rows.append((clip, "unscored", "fall", "", ""))  # overhead fisheye: out of the fall rule's envelope
    if (ROOT / "data/urfd").exists():
        rows += urfd_truth()
    if (ROOT / "data/umn").exists():
        rows += umn_truth()
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["clip", "event_type", "who", "true_start", "true_end"])
        w.writerows(rows)
    print(f"{len(rows)} rows -> {path}")


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def tiou(a0, a1, b0, b1):
    u = max(a1, b1) - min(a0, b0)
    return overlap(a0, a1, b0, b1) / u if u > 0 else 0.0


def evaluate(gt_path):
    truth = defaultdict(list)
    clips, unscored = set(), set()
    for r in csv.DictReader(open(gt_path)):
        clips.add(r["clip"])
        if r["event_type"] == "unscored":
            unscored.add((r["clip"], r["who"]))
        elif r["event_type"] != "none":
            truth[(r["clip"], r["event_type"])].append((float(r["true_start"]), float(r["true_end"])))
    stats = {t: {"tp": 0, "fp": 0, "fn": 0, "dup": 0, "start_err": [], "tiou": []} for t in TYPES}
    hours, missing = 0.0, []
    for clip in sorted(clips):
        f = EVAL_RUNS / clip / "events.json"
        if not f.exists():
            missing.append(clip)
            continue
        run = json.loads(f.read_text())
        hours += run["duration_s"] / 3600
        for typ in TYPES:
            if (clip, typ) in unscored:
                continue
            dets = [tuple(e["evidence"]["series"]["video_s"]) for e in run["events"] if e["type"] == typ]
            gts = list(truth.get((clip, typ), []))
            used = set()
            for d0, d1 in sorted(dets):
                hits = [(overlap(d0, d1, g0 - SLACK_S, g1 + SLACK_S), i) for i, (g0, g1) in enumerate(gts)]
                hits = [h for h in hits if h[0] > 0]
                free = [h for h in hits if h[1] not in used]
                if free:
                    bi = max(free)[1]
                elif hits:  # a second person flagged for the same true event (a crowd running)
                    stats[typ]["dup"] += 1
                    continue
                else:
                    stats[typ]["fp"] += 1
                    continue
                used.add(bi)
                g0, g1 = gts[bi]
                stats[typ]["tp"] += 1
                stats[typ]["start_err"].append(abs(d0 - g0))
                stats[typ]["tiou"].append(tiou(d0, d1, g0, g1))
            stats[typ]["fn"] += len(gts) - len(used)
    out = {"gt": str(gt_path), "clips": len(clips) - len(missing), "missing_runs": missing,
           "video_hours": round(hours, 4), "types": {}}
    print(f"\n{out['clips']} clips, {hours * 60:.1f} min of video" + (f"; no run for {missing}" if missing else ""))
    print("| behaviour | truth | detected | TP | FP | FN | duplicates | precision | recall | start error (s) | temporal IoU | false alarms/hour |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for typ, s in stats.items():
        n_gt, n_det = s["tp"] + s["fn"], s["tp"] + s["fp"]
        if not n_gt and not n_det:
            continue
        r = {"truth": n_gt, "detected": n_det, "tp": s["tp"], "fp": s["fp"], "fn": s["fn"], "duplicates": s["dup"],
             "precision": round(s["tp"] / n_det, 3) if n_det else None,
             "recall": round(s["tp"] / n_gt, 3) if n_gt else None,
             "start_error_s": round(sum(s["start_err"]) / len(s["start_err"]), 2) if s["start_err"] else None,
             "temporal_iou": round(sum(s["tiou"]) / len(s["tiou"]), 3) if s["tiou"] else None,
             "false_alarms_per_hour": round(s["fp"] / hours, 1) if hours else None}
        out["types"][typ] = r
        print(f"| {typ} | {n_gt} | {n_det} | {s['tp']} | {s['fp']} | {s['fn']} | {s['dup']} | {r['precision']} | {r['recall']} | "
              f"{r['start_error_s']} | {r['temporal_iou']} | {r['false_alarms_per_hour']} |")
    (ROOT / "runs" / "eval.json").write_text(json.dumps(out, indent=1))
    return out


def demo():
    assert tiou(0, 10, 5, 15) == 5 / 15 and overlap(0, 1, 2, 3) == 0


if __name__ == "__main__":
    demo()
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default=str(ROOT / "data/ground_truth.csv"))
    ap.add_argument("--build-gt", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.build_gt:
        write_gt(a.gt)
    elif a.run:
        run_all(a.gt)
    else:
        evaluate(a.gt)
