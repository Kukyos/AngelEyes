# Angel's Eye

CCTV that understands what people are doing. HackNex 2026 · HNX26PSI07 — Autonomous Vision & Behaviour Understanding.

Every person in a feed is tracked anonymously (heads blurred, no face recognition, no
gender inference). Behaviours are flagged with **who** (track ID), **when** (start/end)
and **evidence** (keyframes, curves, a clip). A vision-language model also says, in open
vocabulary, what each person is doing ("holding a scrambled puzzle cube", "left the frame").

> Status and next steps: [`docs/STATE.md`](docs/STATE.md).

## Three views (`python -m angelseye.hub`, then http://localhost:8000)

| View | What it shows |
|---|---|
| **Camera** | A phone as a live CCTV camera: annotated feed, what each person is doing now, a running log |
| **Site** | 9 real, synchronised MEVA cameras of one town on a grid, their calibrated positions and view cones on a map, people as dots, events on a timeline |
| **Clips** | Recorded clips (a crowd breaking into a run, a fall) and **drop-in upload**: any video comes back annotated with events |

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
Without `HUB_TOKEN` the gate is off, so never tunnel without it. Raw frames are readable only from the
host itself; the tunnel sees only blurred output. Each person's vision-model captions use the host's key.

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

## Measured

Every number comes from `angelseye.eval` or `angelseye.bench`; see
[`docs/EVALUATION.md`](docs/EVALUATION.md) for the table and its caveats (thresholds were
tuned on the same clips; no held-out split).

## How it works

Pose (YOLO11m-pose) → tracker (ByteTrack) + track repair → ground-plane positions (homography,
or pixel space scaled by body height) → rules for fall, sudden run, loitering, following and a
raised-arms distress pose → events. Every few seconds, a face-blurred composite (whole view +
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
(AGPL-3.0), ByteTrack, CesiumJS, Esri imagery, Airouter / Qwen3-VL, FastAPI, FFmpeg.
Full list with terms: [`docs/RESOURCES.md`](docs/RESOURCES.md).

## Docs

[`STATE`](docs/STATE.md) · [`HACKATHON_PLAN`](docs/HACKATHON_PLAN.md) · [`PRODUCT`](docs/PRODUCT.md) ·
[`ARCHITECTURE`](docs/ARCHITECTURE.md) · [`DATA`](docs/DATA.md) · [`EVALUATION`](docs/EVALUATION.md) ·
[`DECISIONS`](docs/DECISIONS.md) · [`RESOURCES`](docs/RESOURCES.md) · [`TASKS`](docs/TASKS.md)
