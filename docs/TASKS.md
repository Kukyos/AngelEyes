# Tasks

Claim by putting your name in the **Owner** column and **push that claim before you
implement**. First to claim owns it. Tick the box in the same push as the code — a
push that changes code but not this file is an incomplete push.

Tick only your own rows. Do not start a stage until the one above is genuinely done;
Stage 4 does not start until the Stage 3 gate passes.

**Markers:** ☐ not started · ◐ partly done, with what remains stated in the row ·
☑ done and verified · ✖ dropped, with the reason in the row. Never tick ☑ for
something only verified in theory.

---

## Stage 0 — Decide

| # | Task | Owner | Done |
|---|---|---|---|
| 0.1 | Assign lanes A–D and the integrator; fill `HACKATHON_PLAN.md` §1 and §11 | team | ☐ |
| 0.2 | Ask organisers whether code written before the clock is allowed; decide whether to start early | team | ☐ |
| 0.3 | GPU laptop? Router/hotspot? Record answers in `STATE.md` | team | ☐ |
| 0.4 | Pick the 5 km route to draw on the map | team | ☐ |
| 0.5 | Pick the responder alert channel (ntfy.sh or Telegram) | team | ☐ |
| 0.6 | Confirm stack and repo shape; record in `DECISIONS.md` | team | ☐ |
| 0.7 | Each builder copies `docs/BUILD_RULES.md` into a local, gitignored `CLAUDE.md` | all | ☐ |
| 0.8 | Pre-planning phase: list what the problem statement REQUIRES (must), then what is possible (could), before any build; record in `STATE.md` | | ◐ map written in `CAPABILITY_MAP.md`; promotion into scope still to decide |

## Stage 1 — Data and setup

| # | Task | Owner | Done |
|---|---|---|---|
| 1.1 | Record the shot list in `DATA.md` with 3–4 high-mounted phones, incl. night clips | | ☐ |
| 1.2 | Survey each camera: GPS, heading, 4 ground points → `data/cameras.json` | | ☐ |
| 1.3 | Write `data/ground_truth.csv` right after recording | | ☐ |
| 1.4 | Compress clips < 50 MB; pick one sample clip for `data/samples/` | | ☐ |
| 1.5 | Pull 20–40 MEVA clips (`aws s3 ... --no-sign-request`) into `data/meva/` | | ☐ |
| 1.6 | Keys working: Gemini, Groq, Airouter, Cesium ion; `.env.example` complete | | ☐ |
| 1.7 | Pass/fail: gods-eye-view runs on Windows with Node 24.14+ | | ☐ |
| 1.8 | Pass/fail: Google 3D coverage over Karunya | | ☐ |
| 1.9 | Pass/fail: SOS gesture range at 2/3/4 m, with and without crop upscaling | | ☐ |
| 1.10 | Pass/fail: YOLO11n-pose fps per laptop (CPU/GPU, 640 px) | | ☐ |
| 1.11 | Pass/fail: phone streams reach the laptop over our own network | | ☐ |
| 1.12 | Python env + weights + campus street graph (OSMnx) downloaded | | ☐ |

## Stage 2 — Side A, in parallel lanes

| # | Task | Owner | Done |
|---|---|---|---|
| 2.A1 | Ingest from files and streams; motion gate | | ☐ |
| 2.A2 | YOLO11n-pose + ByteTrack → `tracks.jsonl` | | ☐ |
| 2.A3 | Homography per camera; pixel-space fallback for uncalibrated video | | ☐ |
| 2.A4 | Track repair (gap ~1.5 s, position, colour) | | ☐ |
| 2.A5 | Head blur on every output frame; rolling buffer, event clips ±5 s | | ☐ |
| 2.B1 | Eval harness: precision, recall, start-time error, temporal IoU, false alarms/hour | | ☐ |
| 2.B2 | Behaviour: SOS gesture (MediaPipe on upscaled hand crop + state machine) | | ☐ |
| 2.B3 | Behaviour: following (vs companions) | | ☐ |
| 2.B4 | Behaviour: loitering | | ☐ |
| 2.B5 | Behaviour: fall | | ☐ |
| 2.B6 | Behaviour: sudden run | | ☐ |
| 2.B7 | `config.yaml` with every threshold | | ☐ |
| 2.C1 | Fork gods-eye-view into `globe/`; running locally; upstream layers and voice off | | ☐ |
| 2.C2 | Cameras with view cones; fly-to | | ☐ |
| 2.D1 | Hub: FastAPI + SQLite event store + WebSocket + clip serving | | ☐ |
| 2.D2 | Alert card; responder phone page | | ☐ |
| 2.D3 | Upload-a-video mode → events JSON + annotated video | | ☐ |

## Stage 3 — The gate

| # | Task | Owner | Done |
|---|---|---|---|
| 3.1 | End to end on staged clips: events with who/when/evidence → hub → pins on globe | | ☐ |
| 3.2 | One live phone stream end to end | | ☐ |
| 3.3 | People dots on the globe from homography | | ☐ |
| 3.4 | First eval numbers and `angelseye.bench` numbers recorded | | ☐ |

## Stage 4 — Side B

| # | Task | Owner | Done |
|---|---|---|---|
| 4.1 | Amber: per-track crops, CLIP embeddings, colours, height (A) | | ☐ |
| 4.2 | Amber: search API, case ID, audit log, path + next-camera prediction (D) | | ☐ |
| 4.3 | Amber: path on the globe (C) | | ☐ |
| 4.4 | SafeWalk: edge costs from counts, brightness, incidents (B) | | ☐ |
| 4.5 | SafeWalk: fastest vs safest route + heatmap on the globe (C) | | ☐ |
| 4.6 | Gemini confirmation and narration of candidate events (D) | | ☐ |
| 4.7 | Plain-English questions over events (Groq + SQL tools) | | ☐ |
| 4.8 | Encirclement behaviour | | ☐ |
| 4.9 | TfL JamCams live crowd layer | | ☐ |

## Stage 5 — Finish

| # | Task | Owner | Done |
|---|---|---|---|
| 5.1 | Tune false alarms on the negative clips | | ☐ |
| 5.2 | Final eval + bench numbers into the README | | ☐ |
| 5.3 | Showcase README: pitch, hero screenshot, numbers, architecture, scope note, declared resources (fork first), team roles | | ☐ |
| 5.4 | Fresh-clone test by someone who didn't write the README | | ☐ |
| 5.5 | Rehearse the live showcase (`PRODUCT.md` list) three times | | ☐ |
| 5.6 | Submit the repo link in the Google Form | | ☐ |
