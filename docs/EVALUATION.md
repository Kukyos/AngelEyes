# Evaluation and submission evidence

The evaluation harness is built **first** in lane B, so every claim in the showcase
is a number we measured. Judges may bring their own video or hidden test cases;
anything that only shines on our curated clips is a trap.

## What we measure

- **Accuracy.** `python -m angelseye.eval --gt data/ground_truth.csv` reports, per behaviour:
  precision, recall, start-time error, overlap with the true time window (temporal IoU),
  and false alarms per hour on the normal (negative) clips.
- **Efficiency.** `python -m angelseye.bench` reports streams × fps on one laptop and the
  % of frames sent to the vision model.
- **End to end.** Hub plus engine on 3 recorded streams and 1 live stream: pins land on
  the globe, fly-to works, clips play.
- **Amber.** The query returns the staged child's 4 sightings, in order, at the right
  times (and, on MEVA, matches the actors' GPS).
- **Judge's own video.** An uncalibrated upload still returns an events JSON and an
  annotated video.
- **Fresh clone.** A teammate who didn't write the README follows it on a clean machine.

Ground truth format (`data/ground_truth.csv`):
`clip, event_type, who, true_start, true_end` — written right after recording.

## Results (2026-10-07, `python -m angelseye.eval`, final config)

59 public clips, 12.4 min: UR Fall cam0 (30 falls, 20 everyday-activity negatives), UMN
crowd video (11 crowd runs), CAVIAR INRIA (5 runs, 3 negatives; its overhead-camera falls
are unscored). YOLO11m-pose @1280, ByteTrack, rules in `config.yaml`. A detection counts if
it overlaps the true interval within 1 s; extra detections of an already-matched event
(several people in one crowd run) are counted as duplicates, not false alarms.

| Behaviour | Truth | Detected | Precision | Recall | Start error | Temporal IoU | False alarms / hour |
|---|---|---|---|---|---|---|---|
| Fall | 30 | 10 | 0.80 | 0.27 | 0.63 s | 0.73 | 9.7 |
| Sudden run | 16 | 15 | 0.60 | 0.56 | 0.51 s | 0.19 | 29.1 |

**Read these with care.**
- **The thresholds were set while looking at these same clips.** The pixel-space run
  speeds came from UMN scene 1; the fall timing, hip drop and track-repair joins came
  from UR Fall. There is no held-out split, so the numbers are optimistic.
- **The false-alarm fixes cost fall recall.** Before them (lying shape required,
  bending told apart by hip height, cut-off boxes ignored) the same set scored fall P 0.67 / R 0.53
  with 38.8 false alarms per hour. We kept the fixes because they removed real
  false alarms on MEVA CCTV and on the live phone, but the trade-off is real.
- **Most missed falls are in UR Fall clips 15–30,** which end 1–2 s after the person lands,
  often with the person half out of frame.
- **CAVIAR's runners are overhead and are not seen by the pose model,** so 5 of the 16
  run truths are close to unreachable for this setup.
- **Following, loitering and SOS have no scored ground truth yet**, only self-checks.

Vision model (live activity): measured $0.000348 for one 746-token composite call
(`runs/phone/events.json` → `vlm`), with latency 3–14 s per call in live use.

Activity-confidence calibration is **not measured yet**. `angelseye/eval_activity.py` has a
label-sheet generator and offline scorer, but there are no labelled activity runs.
`docs/IMPROVEMENTS.md` I5 lists the remaining evidence and the distinction between final-event
and raw-call confidence.

## Staged clips: watch rules (2026-10-07, not formal ground truth)

Two clips recorded by the team (`test4u.mp4` 31 s, `anothertest4u.mp4` 55 s; not in the repo: real faces), replayed
as live cameras at real speed (`angelseye.engine <clip> --live`). Truth is what the team staged, with times read off
the video by hand. Rules: "flag if a person raises their hand", "flag anyone holding a sharp object", "flag if
someone is choking or strangling another person".

| Staged action | Clip 1 | Clip 2 |
|---|---|---|
| Two people raise a hand | ✓ P1 3.2 s, P2 7.8 s | ✓ P1 2.8 s, P2 5.1 s, P1 9.5 s |
| A capless pen held up ("sharp object", vision model) | ✓ on the run where calls returned in 6-11 s; ✗ on a run with 3 calls (slow API) | ✓ same; ✗ with 4 timeouts |
| A bottle held up (should not fire; captioned) | ✓ captioned, not flagged | ✓ captioned, not flagged |
| Hand on the other's neck (`hand_on_neck`) | ✓ P1→P2 26.1-27.4 s, 0.36 shoulder widths | ✗ missed: wrist 0.8 from the third person's neck (side of the neck, person at the frame edge) |

The vision model's latency was 5.5-17 s per call during these runs (Airouter), so any rule that needs it is only as
good as the API that minute. Pose and pair rules do not depend on it.

## Benchmark (2026-10-07, `python -m angelseye.bench data/meva/G506.avi --camera G506 --max-s 60`)

| Metric | Value |
|---|---|
| Video | G506 (bus camera), 60.1 s |
| Frames analysed | 601 |
| Analysed fps | 1.33 |
| Sample fps (config) | 10 |
| Streams at sample_fps | 0.1 |
| Motion gate skipped | 0.0% |
| Frames to VLM | 0.0% |
| Model | yolo11m-pose.pt @ 1280 |
| Device | CPU |
| GPU | N/A |

**Note:** Running on CPU only. GPU (RTX 4060) available but PyTorch CUDA not utilized in this run.

## Submission checklist, mapped to what we hand in

| Required (booklet) | What we provide |
|---|---|
| Working system | Live showcase at the table (`PRODUCT.md`) |
| Source code + README | Public GitHub repo; setup, run and reproduce steps |
| Data pipeline | Camera → motion gate → pose → tracker → behaviours → events, with intermediate files (`tracks.jsonl`, events JSON) |
| Core model / reasoning | YOLO11n-pose + ByteTrack + behaviour rules; config thresholds documented |
| Evidence and explanation | Per-event keyframes, speed and path series, confidence, timestamps |
| Sample input and output | One staged clip in `data/samples/` with its events JSON and annotated video |
| Scope note | MVP vs stretch, from `PRODUCT.md` |
| Declared resources | `RESOURCES.md`, copied into the README |
| Submission | Repo link in the [Google Form](https://forms.gle/KGjkU5u66Va1MDhu5) before evaluation ends |

## The README is a deliverable (lesson from DayFlowOdoo)

A judge often opens it before anything else. Top: name, one-line pitch, a hero
screenshot of the globe with an alert. Then: what it does, the numbers table from the
eval and bench, architecture, scope note, declared resources (fork declared first),
team roles by name. Setup and env vars at the bottom. Screenshots of animated UI need a
human at a visible browser.
