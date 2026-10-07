# Improvements — known issues, open to claim

Problems seen in the first build, with the evidence, the cause in the code, and a
suggested fix. To work on one: claim its row in `TASKS.md` (section "Improvements"),
push the claim, then build. Measure before and after; numbers come from engine /
`angelseye.eval` / `angelseye.bench` output, never estimates.

Written 2026-10-07 from the live phone-camera sessions and the code at commit `834b2b7`.

---

## I6 — One person drawn as several people (live camera) — FIXED on `mvp1`

**Seen** (laptop webcam, 2026-10-07, `runs/laptop/tracks.jsonl`): one person at a desk came
out as 3 boxes in 56% of frames; 2,851 of 3,189 boxes sat >60% inside another box; 18 track
IDs for one person. Each fake person got its own "entered/left", its own vision-model
description and its own loitering alarm. The phone run (`runs/phone`) shows the same: 2
nested boxes in 63 of 78 frames. **This was the biggest source of I1's false enters/leaves.**

**Cause:** `imgsz: 1280` upscales a 640×480 webcam frame 2×; the pose model then finds
3–5 "people" per frame, all fragments of one, at confidence up to 0.94, so no confidence
threshold removes them. Measured on 60 webcam frames: 1280 → 2–5 boxes per frame; 640 →
exactly 1 box in 60/60 frames. Dropping nested boxes at 1280 only got 24–44 of 60 frames
right.

**Fix:** `model.live_imgsz: 640` for live cameras; file runs keep 1280 (small far people,
e.g. UMN, need it; eval numbers unchanged). Live webcam after the fix: 1 box and 1 track ID
per frame. Still to check on the phone stream.

## I7 — The log was full of non-events — FIXED on `mvp1`

"standing still, no visible object or motion", "holding a lanyard" (worn, not held), and
LOITERING for someone sitting at a desk. Fixes: the vision model answers `idle` when
nothing is going on and idle answers are not logged; the prompt forbids describing absence
or clothing; loitering needs a calibrated camera (`loitering.require_calibrated`); a box
cut off by the frame is labelled `still`/`moving`, not `standing`.

## I1 — False "entered the frame" / "left the frame" (live camera)

**Seen.** Watching the phone camera live, people were reported entering and leaving while
they stayed in view. The hub (`data/hub.sqlite`) holds, for the 7 live phone sessions so far
(~15 min in total), **36 "entered" and 21 "left"** events against 57 vision-model activity
events. The worst session, `phone-000427`, has 13 entered and 10 left in 220 s.

**Causes in the code** (`angelseye/engine.py`, `describe_step`, and `config.yaml`):

1. **The tracker drops a person after 2 s.** ByteTrack's default `track_buffer` is 30 frames
   (`ultralytics/cfg/trackers/bytetrack.yaml`); at `live_sample_fps: 15` that is 2 s. Any miss
   longer than that (turning away, hand over the face, leaning out of the box, detector dip)
   gives the same person a new ID.
2. **The ID-switch merge has a 0.5 s margin.** A new ID is merged into a lost one only if the
   new track qualifies as "entered" (`enter_s: 2.5` s old **and** `enter_strong: 12` detections at
   conf ≥ 0.5) before the lost one is declared gone (`leave_s: 3.0`). So the new ID must appear
   within ~0.5 s of the loss and be confident at once. Close-ups and half-out-of-frame people
   often score under 0.5, so `strong` grows slowly and the merge misses → "left" + "entered".
3. **The merge ignores where and who.** It joins the new track to the most recently lost one
   (`max(self.missing, key=...)`) without checking position or clothing colour. With two or
   more people it can swap identities and captions.
4. **Lost mid-frame is treated as left.** Someone occluded in the middle of the view is
   declared "left" after 3 s, though nobody can leave the frame from the middle.
5. **Track repair is off for close-ups.** Pixel-space repair (`repair`, `Track.scale`) converts
   pixels to metres assuming the box is a whole 1.7 m body. At a desk the box is half a body,
   so distances come out about twice too large and `max_dist_m` rejects valid joins.

**Suggested fixes** (cheapest first; check each against a recorded clip):
- Live tracker config with a longer buffer: a project `trackers/live.yaml` with
  `track_buffer: 90` (6 s at 15 fps), selected by `config.yaml` → `model.tracker`.
  Or Ultralytics' built-in `botsort.yaml` with `with_reid: True` (appearance re-ID, no new pip
  package; check speed with `angelseye.bench`).
- "Left" only when the last box touched a frame edge (the `edge` flag already exists on `Obs`);
  lost mid-frame → wait a much longer `occluded_s` (e.g. 15 s) before saying left.
- Merge by position + colour histogram (reuse `repair`'s scoring), not "most recent".
- Make the windows consistent: `leave_s` must exceed `enter_s` by more than the time a new
  ID takes to appear; or merge first, qualify after.
- Scale from shoulder width or keypoint spans when the box is cut off, not box height.
- **Ground truth first:** record a 3–5 min phone clip with known enters/leaves (write them in
  `ground_truth.csv`) and add an entered/left score to `angelseye.eval`. Today nothing scores it.

## I2 — Vision-model token use

**Measured** (`runs/phone/events.json` → `vlm`): one call with one person = **746 prompt
tokens + 31 completion tokens, $0.000348** reported by the provider (Airouter,
`alibaba/qwen3-vl-instruct`).

**Why it adds up:** `describe.interval_s: 4.0` sends a call every 4 s whenever anyone is in
view, **whether or not anything changed**. That is a ceiling of 900 calls per hour per camera;
at the measured per-call cost, about $0.31 per camera-hour with one person, more per extra
person (each close-up adds a 288 px row to the image). Every false enter/leave (I1) also marks
the next call "urgent", which may go out only 1.5 s (`min_interval_s`) after the last one. A person sitting still is re-described every 4 s with the same
words.

**Suggested fixes:**
- **Send only on change.** Per person, compare keypoints (normalised by box size) or the crop's
  pixels against the last described sample; skip people who have not moved. Skip the call
  entirely if nobody changed.
- **Back off on repeats.** When the answer is the same activity again (`same_activity`),
  double that person's interval, up to e.g. 30 s; reset on change.
- **Smaller image.** With one person, drop the whole-view context strip (the close-ups carry
  the detail); lower `context_w`. Measure token count before/after from `vlm` stats.
- **Fix I1 first:** fewer false enters/leaves means fewer urgent calls.
- Log `vlm` stats per live session to the hub so cost per hour is a measured number.

**What can proceed now:** change detection and backoff logic can be built and checked
with synthetic sequences without touching the unpushed I1/I3 work. Final token,
cost and caption-quality comparisons need the same recorded input before and after
I1/I3 integration; false entries currently add urgent calls. I2 remains unclaimed.

## I3 — Ghost subjects

**Seen:** coats on hooks and chair backs briefly tracked as people (noted in `config.yaml`).
`model.conf: 0.1` feeds low-score boxes to ByteTrack on purpose (keeps blurred runners on their
track); new tracks start at ByteTrack's `new_track_thresh: 0.25`. The `enter_strong` filter only
gates the "entered" caption: ghost tracks are still drawn and still feed the behaviour rules.

**Suggested fix:** a track is shown and used by behaviours only after N strong detections
(reuse `Track.strong`) **and** enough visible keypoints (e.g. ≥ 6 at conf ≥ 0.5: a coat has no
wrists or knees). Score it on the negative CAVIAR/UR Fall ADL clips with `angelseye.eval`
(false alarms per hour must not rise).

## I4 — Vision-model latency

3–14 s per call, measured live; longer when the GPU is shared. Captions lag the action.
Options: a smaller/faster hosted VL model; a local small VLM on the 4060; only ask about the
people who changed (I2), which also shrinks the image.

## I5 — Self-reported confidence

`activity` confidence is what the model says about itself (`confidence_is: self-reported`).
It is not calibrated. Don't threshold alerts on it until it is checked against labelled clips.

**Progress:** branch `eval/activity-confidence-i5` contains an offline label-sheet
generator, scorer (accuracy, Brier score and confidence-range calibration), focused
checks, and a human-review protocol in `docs/I5_CONFIDENCE_EVALUATION.md` on that
branch. It reads existing `events.json` output; it does not change live alerts.

**To finish:** collect consented activity runs using the final model/prompt, label
every vision-model caption against the visible action (including errors and ambiguous
cases), run the scorer, and record a decision to keep, recalibrate or remove the
displayed confidence. No activity footage or labels are committed in this repo, so
there is no measured calibration result yet. The scorer evaluates the *final event*
confidence: repeated matching captions are merged by the engine using the maximum
reported confidence. Raw per-call calibration would require saving each reply with
its exact input image.

## Already listed in `STATE.md` → Known problems

- Blur follows detection: a person the detector misses is not blurred.
- `fall` still has measurable false alarms (`EVALUATION.md`).
- Loitering fires on someone sitting at a desk for 60 s (needs zones).
