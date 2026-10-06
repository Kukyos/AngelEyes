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
