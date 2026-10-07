# Angel's Eye

**CCTV that understands what people are doing, and says who, when and why.**
HackNex 2026 Internal Qualifier · **HNX26PSI07 — Autonomous Vision & Behaviour Understanding** ·
Scenario: public-safety CCTV (campus, streets, crowds).

Every person in a feed is detected, tracked under an anonymous ID and given a pose. Rules over
those tracks flag falls, sudden runs, loitering, following, a distress pose and any watch rule the
operator types in plain English. Each flag names **who** (track ID), **when** (start/end time) and
**why** (the measured values against their limits, keyframes, a clip). A vision-language model adds
an open-vocabulary caption of what each person is doing ("holding a scrambled puzzle cube") and
answers questions about the footage, citing event IDs. Heads are blurred on every frame that leaves
the engine. There is no face recognition and no gender inference.

- [What it does](#what-it-does) · [Results](#results) · [How it works](#how-it-works) ·
  [Sample input → output](#sample-input--output)
- [Technologies, libraries and models](#technologies-libraries-and-models) · [Install](#install) ·
  [Configure](#configure) · [Run](#run) · [Reproduce the results](#reproduce-the-results)
- [Live demonstration](#live-demonstration) · [Scope note](#scope-note) · [Known limits](#known-limits) ·
  [Declared resources](#declared-resources) · [Team](#team)

## What it does

The problem statement asks for a system that tracks people, understands what they are doing, tells
normal from unusual, and points every flag at an entity and a time. Here is how Angel's Eye meets
each judging point:

| Judged on | What Angel's Eye does |
|---|---|
| What people are doing | Per-person label on every frame (standing / walking / running / down) plus open-vocabulary captions from a vision-language model |
| Meaningful events | Fall, sudden run, loitering, following, raised-arms distress pose, and admin watch rules (pose, two-person contact such as a hand on someone's neck, or anything visible on one person) |
| Normal vs abnormal | Rules with explicit limits in [`config.yaml`](config.yaml). A walker is normal; a person whose box drops to 38% of its upright height in 1.5 s and stays down is a fall |
| Same object across the video | ByteTrack IDs plus track repair, which rejoins a broken ID by position and clothing colour. The live view keeps one tile per person across ID switches |
| Detection accuracy and timing | Scored on 59 labelled public clips: precision, recall, start-time error and temporal IoU ([Results](#results)) |
| "Who and when" for every flag | Every event carries `track_ids`, `camera`, `t_start`, `t_end`, `confidence` and `evidence`. The hub rejects any event without them |

**The screens** (one page served by the hub at http://localhost:8000):

| Tab | What it shows |
|---|---|
| **Camera** | Live cameras as CCTV tiles: **Use webcam** (this laptop), a phone (IP Webcam app) or any stream URL. Annotated, face-blurred feed; one tile per person with what they are doing now; a log with **Refresh**; **watch rules** typed in plain English; **Ask about this camera** |
| **Incidents** | Detections that match labelled ground truth (falls, sudden runs) plus live watch-rule hits. Each shows the clip, the measured curve against its limit, **the rule it broke** check by check, who/when/confidence, and **Ask about this footage** |
| **Site** | 9 real, synchronised MEVA cameras of one town on a grid. A map shows their calibrated positions and view cones, people as dots and events as pins, all on one clock |
| **Clips** | Recorded clips and **drop-in upload**: any video comes back annotated, with its events |
| **SafeWalk** | Fastest vs safest walk between two clicked points on the site's streets. A street costs more when a camera sees few people or an alert nearby, or when no camera watches it |
| **World** | 12 public livestreams on a world map. **Analyse** runs the engine on one; **Captions** adds the vision model |

There is also a phone page for responders at `/responder`.

## Results

Every number here comes from `angelseye.eval` or `angelseye.bench` output. The full table and
caveats are in [`docs/EVALUATION.md`](docs/EVALUATION.md).

**Accuracy** (`python -m angelseye.eval`, 59 public clips, 12.4 min). The clips are UR Fall cam0
(30 falls and 20 everyday-activity negatives), the UMN crowd video (11 crowd runs) and CAVIAR INRIA
(5 runs, 3 negatives). A detection counts when it overlaps the true interval within 1 s.

| Behaviour | Truth | Detected | Precision | Recall | Start error | Temporal IoU | False alarms / hour |
|---|---|---|---|---|---|---|---|
| Fall | 30 | 10 | 0.80 | 0.27 | 0.63 s | 0.73 | 9.7 |
| Sudden run | 16 | 15 | 0.60 | 0.56 | 0.51 s | 0.19 | 29.1 |

The thresholds were tuned on these same clips and there is no held-out split, so the numbers are
optimistic. The false-alarm fixes cost fall recall: before them, the same clips scored fall
P 0.67 / R 0.53 with 38.8 false alarms per hour. Following, loitering and the distress pose have no
scored ground truth.

**Efficiency** (`python -m angelseye.bench`, MEVA camera G506, 60 s, CPU only). 1.33 frames
analysed per second, 0% of frames sent to the vision model. The vision model is called only
for live or `--describe` runs: one call costs $0.000348 (746 tokens, measured), with 3–14 s latency
in live use.

**Watch rules on two staged clips** (not formal ground truth; [`docs/EVALUATION.md`](docs/EVALUATION.md)):
- Raised hands: fired in both clips.
- A pen as a "sharp object": fired when the API answered within 6–11 s, missed when it was slower.
- A hand on another person's neck: fired in clip 1, missed in clip 2 (the hand was at the side of
  the neck, at the frame edge).

## How it works

### Data pipeline

```
video file | laptop webcam | phone / IP camera (MJPEG) | YouTube livestream (HLS, via yt-dlp)
  → frames: sampled at model.sample_fps (files) or newest-frame-only at live_sample_fps (live)
  → YOLO11m-pose: person boxes + 17 body keypoints
  → ByteTrack IDs → track repair (rejoins a lost ID within 1.5 s by position + clothing colour)
  → ground plane: MEVA camera homography → metres and lat/lon; uncalibrated video → pixels
    scaled by body height (person_height_m), so a judge's own video still works
  → per-person label + behaviour rules + watch rules  (angelseye/behaviours.py, rules.py)
  → events {who, when, confidence, evidence} · tracks.jsonl · head-blurred annotated video
  → hub: FastAPI + SQLite + REST + WebSocket + MJPEG relay  (angelseye/hub.py)
  → the web page (web/index.html)

live, every 2.5 s:  head-blurred composite (whole view + each person's close-up, 1 s ago and now)
                    → Qwen3-VL → "activity" captions and yes/no answers for vision watch rules
```

Intermediate outputs are written per run in `runs/<name>/`:
- `tracks.jsonl`: every person in every frame, with box, keypoints, label, speed and position.
- `events.json`: the events and the run's metadata.
- `keyframes/` and `clips/`: the evidence.
- `annotated.mp4`: the H.264 annotated video.

### Core model and reasoning

- **Perception:** Ultralytics YOLO11m-pose at 1280 px for CCTV (small, distant people) and 640 px
  for close live cameras, with ByteTrack tracking.
- **Behaviour rules** ([`angelseye/behaviours.py`](angelseye/behaviours.py)) are explicit state
  machines over the tracks, with every limit in [`config.yaml`](config.yaml):
  - **Fall:** upright, then down within 2.0 s; box height drops to ≤ 65% of upright; lying shape
    (wide box or torso ≥ 55° from vertical with hips low); stays down ≥ 1.0 s.
  - **Sudden run:** speed ≥ 2.5 m/s (calibrated) from walking pace, and ≥ 2.5× the person's own
    prior pace, held 0.6 s.
  - **Loitering:** stays within 3 m for 60 s (calibrated cameras only).
  - **Following:** the follower's path matches the leader's path delayed 1–10 s, 2–10 m apart,
    for 8 s, with a shared turn. Side by side counts as companions.
  - **Distress pose:** both wrists above the head for 1.5 s, standing upright.
- **Watch rules** ([`angelseye/rules.py`](angelseye/rules.py)): the operator types a rule; one model
  call compiles it into fixed checks and reads it back ("Will flag: …") before it is confirmed. The
  checks are `hand_up`, `bent_over`, `jump`, pair `near`, pair `hand_on_neck`, or a yes/no question
  about one person that the vision model must answer yes to twice in a row. Rules about gender, age,
  faces or identity are refused.
- **Vision-language model** (Qwen3-VL through an OpenAI-compatible API,
  [`angelseye/describe.py`](angelseye/describe.py)): open-vocabulary activity captions on live
  cameras. It never sees our labels, so it can't echo them. Its confidence is self-reported and
  marked so; it is not calibrated.
- **Ask** ([`angelseye/ask.py`](angelseye/ask.py)): one model call per question, scoped to one
  incident's run or one live session. It sees the blurred picture plus that run's events, and must
  cite event IDs; unknown IDs are dropped. Questions about gender, age, face or identity are refused
  before any call.

### Evidence and explanation

Every event follows one record, stored in SQLite and pushed over WebSocket
([`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) → Event record):

```json
{"id": "...", "type": "fall", "camera": "...", "track_ids": [1], "t_start": "...", "t_end": "...",
 "confidence": 0.75, "evidence": {"keyframes": ["..."], "series": {"...": "curves", "video_s": [2.0, 3.5]}},
 "clip_path": "...", "geo": [lat, lon] or null}
```

The **Incidents** tab turns `evidence.series` into "the rule it broke": each check as the measured
value against its `config.yaml` limit (`behaviours.explain`). The hub serves this at
`/api/showcase`. Watch-rule events carry the measured signals, such as `wrists_up`, `torso_deg` and
`distance_m`, and how long the rule held.

## Sample input → output

Input: `fall-02` from the UR Fall Detection dataset (3.6 s, one person). After
`python -m angelseye.eval --build-gt` has cropped the dataset's videos to their RGB half (see
[Reproduce](#reproduce-the-results)):

```bash
python -m angelseye.engine data/urfd/rgb/fall-02.mp4 --out runs/eval/fall-02
```

Output in `runs/eval/fall-02/`:
- `annotated.mp4`: boxes, labels and a blurred head.
- `tracks.jsonl`: every person in every frame.
- `clips/` and `keyframes/`: the evidence.
- `events.json`, with this event (curve shortened):

```json
{"id": "fall-02-fall-001", "type": "fall", "camera": "fall-02", "track_ids": [1],
 "t_start": "...", "t_end": "...", "confidence": 0.75,
 "evidence": {"keyframes": ["fall-02/keyframes/fall-02-fall-001-0.jpg"],
              "series": {"box_height_ratio": [[0.5, 1.0], [2.0, 0.761], [2.3, 0.46], [3.1, 0.376]],
                         "upright_at_s": 0.5, "video_s": [2.0, 3.5]}},
 "clip_path": "fall-02/clips/fall-02-fall-001.mp4", "geo": null}
```

- **Who:** P1.
- **When:** 2.0–3.5 s. The labelled truth is 1.3–3.63 s.
- **Why** (the Incidents tab): upright at 0.5 s; went down 1.5 s later (limit ≤ 2.0 s); height fell
  to 38% of upright (limit ≤ 65%); stayed down 1.5 s (limit ≥ 1.0 s).

## Technologies, libraries and models

| Part | What we use |
|---|---|
| Language | Python 3.12; plain HTML/JS for the page (no build step) |
| Pose + detection model | **Ultralytics YOLO11m-pose** (`yolo11m-pose.pt`, AGPL-3.0) on **PyTorch** (CUDA 12.8 wheels; CPU works) |
| Tracking | **ByteTrack** through Ultralytics (`bytetrack.yaml`; `trackers/live.yaml` for live cameras), `lap` |
| Vision-language model | **Qwen3-VL** (`alibaba/qwen3-vl-instruct`) via the **Airouter** OpenAI-compatible API. Any OpenAI-compatible vision endpoint works |
| Video | OpenCV (with Ultralytics), **FFmpeg** (H.264 output, dataset cropping), **yt-dlp** (livestream → HLS) |
| Hub | **FastAPI**, Uvicorn, SQLite (stdlib), WebSocket, python-multipart, PyYAML, NumPy |
| Map | **CesiumJS** 1.146 (CDN) with Cesium ion terrain, or Esri World Imagery without a token |
| Calibration | MEVA KRTD camera models → homographies (`angelseye/geo.py`, stdlib + NumPy) |
| SafeWalk | OpenStreetMap streets exported once to `data/street_graph.json`; Dijkstra on the standard library |
| Datasets | MEVA, UR Fall Detection, UMN crowd, CAVIAR ([Declared resources](#declared-resources)) |

## Install

Windows, Python 3.12, FFmpeg on PATH. An NVIDIA GPU is optional: CPU works, but slower.

```bash
git clone https://github.com/Kukyos/AngelEyes.git
cd AngelEyes
python -m venv .venv
.venv\Scripts\activate             # PowerShell / cmd.   Git Bash: source .venv/Scripts/activate.   macOS/Linux: source .venv/bin/activate

# PowerShell refuses activate with "running scripts is disabled"? Run first:
#   Set-ExecutionPolicy -Scope Process Bypass

# NVIDIA GPU: install torch from the CUDA index first (skip for CPU)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
```

The pose weights (`models/yolo11m-pose.pt`, 42 MB) download on the first engine run. To fetch them
ahead of time:

```bash
curl.exe -L --create-dirs -o models/yolo11m-pose.pt https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11m-pose.pt
```

### Screens only (no GPU, no torch)

This is enough to see the Site, SafeWalk and World tabs and work on the page. The hub serves a
recorded snapshot of the 9 MEVA cameras (`data/samples/site/`: events, tracks, keyframes) instead
of running the engine.

```bash
pip install -r requirements-hub.txt
mkdir runs
cp -r data/samples/site/. runs/            # PowerShell: Copy-Item -Recurse data\samples\site\* runs\
python -m angelseye.hub --port 8000
```

The camera videos are not in the repo (too large), so the Site tiles stay black. The map, people
dots and event pins still play. Camera, upload and rule compiling need the full install.

## Configure

```bash
cp .env.example .env     # then fill it in; .env is gitignored
```

| Variable | Needed for | |
|---|---|---|
| `VISION_BASE_URL` | Captions, vision watch rules, compiling typed rules, Ask | e.g. `https://api.airouter.in/v1` |
| `VISION_API_KEY` | same | your key |
| `VISION_MODEL` | same | e.g. `alibaba/qwen3-vl-instruct` |
| `CESIUM_ION_TOKEN` | Optional: 3D terrain on the map | without it the map uses Esri imagery |
| `HUB_TOKEN` | Optional: required when the hub is reached from another machine | see [Remote cameras](#remote-cameras-and-teammates) |

Without the `VISION_*` variables everything else runs: detection, tracking, behaviours, pose and
pair watch rules, the screens. Only captions, vision rules, rule compiling and Ask need them.

Every threshold is in [`config.yaml`](config.yaml), with a comment saying where its value came from.
Nothing is hard-coded.

## Run

```bash
# 1. the hub and the page: open http://localhost:8000
python -m angelseye.hub --port 8000

# 2. a camera (or press "Use webcam" on the Camera tab, which starts this for you)
python -m angelseye.engine 0 --live --name laptop --hub http://127.0.0.1:8000
python -m angelseye.engine http://PHONE_IP:8080/video --live --name phone --rotate 90 --hub http://127.0.0.1:8000

# 3. any video file -> runs/<name>/ and the Clips tab (--describe adds vision-model captions)
python -m angelseye.engine my_video.mp4 --hub http://127.0.0.1:8000

# 4. the MEVA site: one run per camera (clips: see Reproduce). data/cameras.json is committed;
#    python -m angelseye.geo rebuilds it from MEVA's calibration files
python -m angelseye.engine data/meva/2018-03-07.11-00-01.11-05-01.bus.G506.r13.avi --camera G506
```

- `--live`: a live source. Newest frame only, the vision model on.
- `--describe` / `--no-describe`: switch the vision model on or off.
- `--rotate 90`: for a phone held upright. IP Webcam streams it sideways, and sideways people read
  as lying down.
- `--max-s N`: stop after N seconds of video.
- `--imgsz`: override the model input size.

On the Camera tab, **Add camera** takes a name and a stream URL, and the hub starts the engine
itself. `hub.max_engines` caps how many engines run at once. **Refresh**, above the log, clears the
log and the people tiles; the engine ends the current activities and re-learns who is in view.

### Remote cameras and teammates

The host machine runs the hub; a tunnel gives other people an https link. Their browser webcam
frames go to the host's engine, and they see the face-blurred result.

```bash
HUB_TOKEN=pick-a-long-random-string python -m angelseye.hub --port 8000   # PowerShell: $env:HUB_TOKEN="..."; python -m angelseye.hub --port 8000
ngrok http 8000
```

1. Send each person `https://<ngrok-host>/webcam?token=<HUB_TOKEN>&name=theirname`.
2. They press Start, then open `/` → **Camera**.

Rules for remote access:
- With `HUB_TOKEN` set, every non-loopback client needs the token.
- Without `HUB_TOKEN` the gate is off, so never tunnel without it.
- Adding camera sources and reading raw frames work only from the host itself.

## Reproduce the results

**1. Get the datasets** (free for research; see [Declared resources](#declared-resources)). This is
the layout `angelseye/eval.py` expects:

| Folder | Files | From |
|---|---|---|
| `data/urfd/` | `fall-01-cam0.mp4` … `fall-30-cam0.mp4`, `adl-01-cam0.mp4` … `adl-20-cam0.mp4`, `urfall-cam0-falls.csv`, `urfall-cam0-adls.csv` | [UR Fall Detection](https://fenix.ur.edu.pl/~mkepski/ds/uf.html): the cam0 RGB+depth videos and the per-frame label CSVs |
| `data/umn/` | `Crowd-Activity-All.avi` | [UMN Unusual Crowd Activity](https://mha.cs.umn.edu/proj_events.shtml) |
| `data/caviar/` | `Browse_WhileWaiting1`, `Fight_Chase`, `Fight_OneManDown`, `Fight_RunAway1`, `Meet_WalkTogether1`, `Rest_FallOnFloor`, `Rest_SlumpOnFloor`, `Walk1`: each `.mpg` with its ground-truth `.xml` saved under the same name | [CAVIAR](https://homepages.inf.ed.ac.uk/rbf/CAVIARDATA1/), INRIA lobby set |
| `data/meva/` (bench and Site only) | the 9 clips of 2018-03-07 11:00 | MEVA on AWS, no account (below) |

```bash
# MEVA (Git Bash / macOS / Linux shell): about 120 MB per clip
for f in 11-00-00.11-05-00.hospital.G436 11-00-01.11-05-01.bus.G505 11-00-01.11-05-01.bus.G506 \
         11-00-01.11-05-01.school.G328 11-00-04.11-05-04.hospital.G341 11-00-05.11-05-05.school.G424 \
         11-00-06.11-05-05.school.G336 11-00-06.11-05-06.bus.G340 11-00-07.11-05-07.school.G339; do
  curl -L --create-dirs -o data/meva/2018-03-07.$f.r13.avi \
    https://mevadata-public-01.s3.amazonaws.com/drops-123-r13/2018-03-07/11/2018-03-07.$f.r13.avi
done
```

**2. Score**

```bash
python -m angelseye.eval --build-gt   # data/ground_truth.csv from the datasets' own labels (crops UR Fall to RGB)
python -m angelseye.eval --run        # the engine on all 59 clips -> runs/eval/
python -m angelseye.eval              # scores -> runs/eval.json  (the Results table)
python -m angelseye.bench data/meva/2018-03-07.11-00-01.11-05-01.bus.G506.r13.avi --camera G506 --max-s 60
```

**3. Self-checks and tests** (no data, GPU or network needed)

```bash
python -m angelseye.behaviours
python -m angelseye.rules
python -m angelseye.ask
python -m angelseye.safewalk
python -m unittest discover -s tests
```

## Live demonstration

Steps, in dependency order:

1. Start the hub (`python -m angelseye.hub --port 8000`) and open http://localhost:8000.
   **Incidents** needs `runs/eval/` from [Reproduce](#reproduce-the-results) step 2.
2. **Camera** → **Use webcam**. People get boxes, blurred heads and a tile each, and a caption
   arrives every few seconds.
3. Type a watch rule ("flag if a person raises their hand"), read the "Will flag: …" read-back,
   press Confirm, and act it out. The hit shows in the log and on **Incidents** as "not scored".
4. **Incidents** → open a fall → the clip, the curve against its limit and the rule it broke →
   **Ask about this footage**.
5. **Site** → play the 9 MEVA cameras on the map. **SafeWalk** → click two points.
6. **Clips** → drop any video. It comes back annotated with its events.

## Scope note

**Minimum viable (built and scored):**
- Detect and track people: YOLO11m-pose, ByteTrack and track repair.
- Say what each person is doing: standing / walking / running / down, plus open-vocabulary captions.
- Flag abnormal behaviour with who, when and evidence.
- Fall and sudden run are scored against labelled public clips.

**Stretch (built, not scored on labelled data):**
- Loitering, following and the raised-arms distress pose (self-checks only).
- Watch rules typed in plain English (checked on two staged clips only).
- Ask: questions about the footage with cited events.
- The 9-camera MEVA site on a map.
- SafeWalk routes.
- Public livestreams.
- Remote webcams through a tunnel.
- An offline scorer for the vision model's self-reported confidence (no labelled runs yet).

**Not built:** the amber-alert person search, the offender-registry layer, and the Signal-for-Help
hand sign.

## Known limits

- **Blur follows detection.** A person the detector misses is not blurred (seen on fast runners in
  the UMN clip).
- **World embeds are not blurred.** Before **Analyse** is pressed, a World tile is YouTube's own
  player, so faces show as the channel publishes them. Only the analysed picture is ours and blurred.
- **Falls still have false alarms on real CCTV.** A person half-hidden behind a pillar on MEVA G506
  still fires.
- **Loitering** is the rule as written: someone sitting at a desk for 60 s loiters. It is limited
  to calibrated cameras until there are zones.
- **Vision-model rules depend on the API's speed** that minute: 5.5–17 s per call during the staged
  tests. Pose and pair rules don't depend on it.
- **MEVA has no staged falls or runs,** so the Site view mostly shows loitering, which is true to
  the footage.

## Privacy

- Heads are blurred on every frame that leaves the engine (`output.head_blur`, never off).
- No face recognition and no gender or age inference. Rules and questions that ask for them are
  refused.
- Raw frames are readable only from the host machine.
- Keys live only in `.env`.
- Footage with real faces is not committed. Only the `data/samples/` snapshot is: MEVA, CC-BY-4.0.

## Declared resources

- **Datasets:**
  - MEVA (CC-BY-4.0; "MEVA dataset, Kitware/IARPA DIVA, mevadata.org") and its KRTD camera models
  - UR Fall Detection (Kwolek & Kepski, CMPB 2014)
  - UMN Unusual Crowd Activity
  - CAVIAR (EC Funded CAVIAR project/IST 2001 37540)
- **Models:** Ultralytics YOLO11m-pose (AGPL-3.0); Qwen3-VL through the Airouter API.
- **Libraries:** PyTorch, Ultralytics, ByteTrack, OpenCV, NumPy, FastAPI, Uvicorn, PyYAML,
  python-multipart, lap, yt-dlp.
- **Tools:** FFmpeg, ngrok (optional, host side).
- **Map:** CesiumJS + Cesium ion, Esri World Imagery, OpenStreetMap (SafeWalk streets, ODbL).
- **Live sources:** public YouTube livestreams (World tab, standard embeds). Volve Vision was used
  for camera coordinates, read by hand.
- **AI tools:** AI coding assistants helped write this code. The team reviewed it and is
  responsible for it, as the rules require.

Full list with terms and what each is used for: [`docs/RESOURCES.md`](docs/RESOURCES.md).

## Team

| Who | Part |
|---|---|
| **Armaan** ([@Kukyos](https://github.com/Kukyos)) | Side A: the perception and behaviour engine end to end (detection, tracking, behaviour and watch rules, vision-model captions), the hub and the evaluation |
| **Jonathan** ([@jonathan-16bit](https://github.com/jonathan-16bit)) | Side A: engine accuracy improvements (activity-confidence evaluation, vision-rule and hub-access guards), and linking Side A's output to Side B |
| **Jerem Jebaz** ([@Jerem-Jebaz](https://github.com/Jerem-Jebaz)) | Side B: the globe and map view, and SafeWalk routing |
| **Pooja Shree** | Side B: the data: datasets, links and livestreams, our own recorded footage, and API keys |

## Docs

[`STATE`](docs/STATE.md) (where the project is) · [`PRODUCT`](docs/PRODUCT.md) ·
[`ARCHITECTURE`](docs/ARCHITECTURE.md) · [`EVALUATION`](docs/EVALUATION.md) ·
[`DATA`](docs/DATA.md) · [`DECISIONS`](docs/DECISIONS.md) · [`RESOURCES`](docs/RESOURCES.md) ·
[`TASKS`](docs/TASKS.md) · [`HACKATHON_PLAN`](docs/HACKATHON_PLAN.md)
