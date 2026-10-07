# Angel's Eye

CCTV that understands what people are doing. HackNex 2026 · HNX26PSI07 — Autonomous Vision & Behaviour Understanding.

Every person in a feed is tracked anonymously (heads blurred, no face recognition, no
gender inference). Behaviours are flagged with **who** (track ID), **when** (start/end)
and **evidence** (keyframes, curves, a clip). A vision-language model also says, in open
vocabulary, what each person is doing ("holding a scrambled puzzle cube", "left the frame").

> Status and next steps: [`docs/STATE.md`](docs/STATE.md).

## The screens (`python -m angelseye.hub`, then http://localhost:8000)

| Tab | What it shows |
|---|---|
| **Camera** | Live cameras as CCTV tiles: a phone (IP Webcam), **Use webcam** (this laptop's camera), or any stream. Annotated, face-blurred feed; what each person is doing now; watch rules typed in plain English; **Ask about this camera** |
| **Site** | 9 real, synchronised MEVA cameras of one town on a grid, their calibrated positions and view cones on a map, people as dots, events on a timeline |
| **Incidents** | Detections that match labelled ground truth (falls, sudden runs) and live watch-rule hits. Each one shows the clip, the measured curve against its limit, **the rule it broke** check by check (measured vs `config.yaml` limit), who/when/confidence, and **Ask about this footage** |
| **Clips** | Recorded clips and **drop-in upload**: any video comes back annotated with events |
| **SafeWalk** | Fastest vs safest walk between two clicked points on the site's streets; streets cost more when a camera sees few people, an alert nearby, or no camera at all |
| **World** | 12 public livestreams on a world map; **Analyse** runs the engine on one, **Captions** adds the vision model |

Phone page for responders: http://localhost:8000/responder

## Screens only (no GPU, no CUDA)

For work on the map and the web page. The hub serves a recorded snapshot of the 9 MEVA site
cameras (`data/samples/site/`: events, tracks, keyframes) instead of running the engine.

```bash
python -m venv .venv            # Python 3.12
.venv/Scripts/python.exe -m pip install -r requirements-hub.txt
cp .env.example .env            # CESIUM_ION_TOKEN optional; without it the map uses Esri imagery
mkdir runs; cp -r data/samples/site/. runs/        # PowerShell: Copy-Item -Recurse data\samples\site\* runs\
.venv/Scripts/python.exe -m angelseye.hub --port 8000
```

Open http://localhost:8000 → **Site**: map, camera cones, people dots and event pins all play
on the page clock. Not available in this mode: the camera videos (tiles stay black; the mp4s
are too big for the repo), upload, the live Camera feed and rule compiling (those need the
full install below and `VISION_*` in `.env`). The page talks to the hub only through
`/api/cameras`, `/api/events`, `/api/tracks/{camera}`, `/api/config` and `/ws`.

## Teammates test through the host (no install)

The host (GPU machine) runs the hub, and a tunnel gives everyone else an https link. Their webcam
frames go to the host's engine; they see the annotated, face-blurred result on **Camera**.

```bash
# host: any long random string as the token
HUB_TOKEN=pick-a-long-random-string .venv/Scripts/python.exe -m angelseye.hub --port 8000   # PowerShell: $env:HUB_TOKEN="..."
ngrok http 8000
```

Send each teammate `https://<ngrok-host>/webcam?token=<HUB_TOKEN>&name=theirname`. They press Start, allow
the camera, then open `/` → **Camera** and pick their name. Only 2 webcams run at once (one GPU).
Without `HUB_TOKEN` the gate is off, so never tunnel without it. With the token set, direct LAN clients
also need it; only loopback traffic is exempt. Raw frames are readable only from the host itself; the
tunnel sees only blurred output. Each person's vision-model captions use the host's key.

## IP cameras (CCTV grid)

On the host's own browser (http://localhost:8000, not through the tunnel), **Camera** → type a name and a
camera URL (IP Webcam app: `http://PHONE_IP:8080/video`) → **Add camera**. The hub starts one engine for it.
Every live camera, including teammates' webcams, shows as a tile in one grid; click a tile to see its
people and log on the right, **Remove** to stop it. The phone must be reachable from the host
(same Wi-Fi; campus Wi-Fi blocks it, use a hotspot). `hub.max_engines` in `config.yaml` caps how many run.
**Phone held upright?** IP Webcam streams it sideways: pick **90°** next to the URL (the engine's `--rotate`).
Sideways people read as lying down (false falls), track badly, and hand-up rules can't fire.
The right panel shows one tile per person in view, kept across tracker ID switches.
Watch rules can be poses ("raises a hand"), two people ("choking someone": one person's wrist at the other's
neck) or anything visible on one person ("anyone holding a sharp object", "someone in a red jacket"): the last kind
becomes a yes/no question for the vision model and fires after 2 yes in a row.

## Run it

Windows, Python 3.12, an NVIDIA GPU (CPU works, slower), ffmpeg on PATH.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe torch torchvision --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
cp .env.example .env            # fill in VISION_* (vision model) and CESIUM_ION_TOKEN (optional)
```

Pose weights go in `models/` (`yolo11m-pose.pt` from the Ultralytics v8.4.0 release).

```bash
# hub + web
.venv/Scripts/python.exe -m angelseye.hub --port 8000

# live phone camera (Android "IP Webcam" app -> Start server)
.venv/Scripts/python.exe -m angelseye.engine http://PHONE_IP:8080/video --live --name phone --hub http://127.0.0.1:8000

# any video file (add --describe for the vision model's descriptions)
.venv/Scripts/python.exe -m angelseye.engine my_video.mp4 --hub http://127.0.0.1:8000

# the MEVA site: camera registry from MEVA's calibration, then one run per camera
.venv/Scripts/python.exe -m angelseye.geo
.venv/Scripts/python.exe -m angelseye.engine data/meva/<clip>.avi --camera G506
```

The map uses Cesium ion terrain when `CESIUM_ION_TOKEN` is valid for the page's address,
otherwise grayscale Esri imagery.

## Sample input → output

Input: `fall-02` from the UR Fall Detection dataset (3.6 s, one person). Command:
`python -m angelseye.engine data/urfd/rgb/fall-02.mp4 --out runs/eval/fall-02`. Output in `runs/eval/fall-02/`:
`annotated.mp4` (boxes, labels, blurred head), `tracks.jsonl` (every person, every frame), `clips/` and
`keyframes/` (evidence), and `events.json` with this event (curve shortened):

```json
{"id": "fall-02-fall-001", "type": "fall", "camera": "fall-02", "track_ids": [1],
 "t_start": "...", "t_end": "...", "confidence": 0.75,
 "evidence": {"keyframes": ["fall-02/keyframes/fall-02-fall-001-0.jpg"],
              "series": {"box_height_ratio": [[0.5, 1.0], [2.0, 0.761], [2.3, 0.46], [3.1, 0.376]],
                         "upright_at_s": 0.5, "video_s": [2.0, 3.5]}},
 "clip_path": "fall-02/clips/fall-02-fall-001.mp4", "geo": null}
```

Who: P1. When: 2.0–3.5 s (labelled truth: 1.3–3.63 s). Why (Incidents tab): upright at 0.5 s; went down 1.5 s
later (limit ≤ 2.0 s); height fell to 38% of upright (limit ≤ 65%); stayed down 1.5 s (limit ≥ 1.0 s).

## Reproduce the numbers

```bash
python -m angelseye.eval --build-gt   # data/ground_truth.csv from the datasets' own labels (docs/DATA.md: downloads)
python -m angelseye.eval --run        # engine on all 59 clips -> runs/eval/
python -m angelseye.eval              # scores -> runs/eval.json (the table in docs/EVALUATION.md)
python -m angelseye.bench data/meva/<clip>.avi --camera G506 --max-s 60
```

Self-checks: `python -m angelseye.behaviours`, `angelseye.rules`, `angelseye.ask`, `angelseye.safewalk`.

## Scope note

**Minimum viable (built and scored):** detect and track people (YOLO11m-pose + ByteTrack + track repair), say what
each is doing (standing / walking / running / down, plus open-vocabulary captions from a vision model), and flag
abnormal behaviour with who, when and evidence. Fall and sudden run are scored against labelled public clips
(`docs/EVALUATION.md`).

**Stretch (built, not scored on labelled data):** loitering, following, raised-arms SOS; watch rules typed in
plain English (pose, two-person contact, vision-model questions); questions about the footage answered by the
vision model with cited events; the 9-camera MEVA site on a map; SafeWalk routes; public livestreams; remote
webcams through a tunnel. Watch rules were checked on staged clips only (`docs/EVALUATION.md`).

**Not built:** amber-alert person search, offender-registry layer, the Signal-for-Help hand sign.

## Measured

Every number comes from `angelseye.eval` or `angelseye.bench`; see
[`docs/EVALUATION.md`](docs/EVALUATION.md) for the table and its caveats (thresholds were
tuned on the same clips; no held-out split).

## How it works

Pose (YOLO11m-pose) → tracker (ByteTrack) + track repair → ground-plane positions (homography,
or pixel space scaled by body height) → rules for fall, sudden run, loitering, following and a
raised-arms distress pose, plus the admin's watch rules → events (who, when, evidence) → hub (SQLite,
WebSocket) → the page. Every few seconds, a face-blurred composite (whole view +
close-ups of each person, a moment ago and now) goes to a vision-language model for the
open-ended description. Thresholds: [`config.yaml`](config.yaml). Detail:
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Known limits

- People the detector misses are not blurred (blur follows detection).
- The SOS rule is a whole-body pose; the Signal-for-Help hand sign needs our own footage.
- Following and loitering are built and self-checked but have no scored ground truth yet.
- MEVA has no staged falls or runs; the site view mostly shows loitering, which is true to the footage.

## Declared resources

MEVA (CC-BY-4.0), CAVIAR, UR Fall Detection, UMN crowd video, Ultralytics YOLO11-pose
(AGPL-3.0), ByteTrack, CesiumJS, Esri imagery, Airouter / Qwen3-VL, FastAPI, FFmpeg, OpenStreetMap (SafeWalk
streets), yt-dlp and public YouTube livestreams (World), Volve Vision (camera list).
Full list with terms: [`docs/RESOURCES.md`](docs/RESOURCES.md).

## Docs

[`STATE`](docs/STATE.md) · [`HACKATHON_PLAN`](docs/HACKATHON_PLAN.md) · [`PRODUCT`](docs/PRODUCT.md) ·
[`ARCHITECTURE`](docs/ARCHITECTURE.md) · [`DATA`](docs/DATA.md) · [`EVALUATION`](docs/EVALUATION.md) ·
[`DECISIONS`](docs/DECISIONS.md) · [`RESOURCES`](docs/RESOURCES.md) · [`TASKS`](docs/TASKS.md)
