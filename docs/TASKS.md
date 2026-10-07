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
| 0.1 | Assign lanes A–D and the integrator; fill `HACKATHON_PLAN.md` §1 and §11 | solo | ☑ sole builder holds every lane (D13) |
| 0.2 | Ask organisers whether code written before the clock is allowed; decide whether to start early | solo | ◐ user chose to build now; organisers' rule still unchecked |
| 0.3 | GPU laptop? Router/hotspot? Record answers in `STATE.md` | solo | ☑ RTX 4060 laptop GPU; phone over home Wi-Fi works |
| 0.4 | Pick the 5 km route to draw on the map | team | ☐ |
| 0.5 | Pick the responder alert channel (ntfy.sh or Telegram) | team | ☐ |
| 0.6 | Confirm stack and repo shape; record in `DECISIONS.md` | solo | ☑ D14, D16, D17 |
| 0.7 | Each builder copies `docs/BUILD_RULES.md` into a local, gitignored `CLAUDE.md` | all | ☐ |
| 0.8 | Pre-planning phase: list what the problem statement REQUIRES (must), then what is possible (could), before any build; record in `STATE.md` | | ◐ map written in `CAPABILITY_MAP.md`; promotion into scope still to decide |

## Stage 1 — Data and setup

| # | Task | Owner | Done |
|---|---|---|---|
| 1.1 | Record the shot list in `DATA.md` with 3–4 high-mounted phones, incl. night clips | | ☐ |
| 1.2 | Survey each camera: GPS, heading, 4 ground points → `data/cameras.json` | solo | ◐ MEVA cameras from KRTD calibration (`angelseye/geo.py`); our own cameras not surveyed |
| 1.3 | Write `data/ground_truth.csv` right after recording | solo | ◐ built from CAVIAR, UR Fall and UMN labels (`eval --build-gt`); no own recordings yet |
| 1.4 | Compress clips < 50 MB; pick one sample clip for `data/samples/` | | ☐ |
| 1.5 | Pull 20–40 MEVA clips (`aws s3 ... --no-sign-request`) into `data/meva/` | solo | ☑ 9 cameras of MEVA 2018-03-07 11:00 (first ~140 MB each), via HTTPS range requests |
| 1.6 | Keys working: Gemini, Groq, Airouter, Cesium ion; `.env.example` complete | solo | ◐ Cesium token works only on http://localhost:5173 (referrer-restricted); Airouter vision key works; Gemini/Groq not wired |
| 1.7 | Pass/fail: gods-eye-view runs on Windows with Node 24.14+ | solo | ✖ Node 24.13.1 < 24.14; plain CesiumJS page instead (D14) |
| 1.8 | Pass/fail: Google 3D coverage over Karunya | | ☐ |
| 1.9 | Pass/fail: SOS gesture range at 2/3/4 m, with and without crop upscaling | | ☐ |
| 1.10 | Pass/fail: YOLO11n-pose fps per laptop (CPU/GPU, 640 px) | solo | ☑ measured in `angelseye.bench` / `events.json` (`analysed_fps`) |
| 1.11 | Pass/fail: phone streams reach the laptop over our own network | solo | ☑ Android IP Webcam stream read live at 1080p |
| 1.12 | Python env + weights + campus street graph (OSMnx) downloaded | solo | ◐ venv + weights done; OSMnx street graph not downloaded |

## Stage 2 — Side A, in parallel lanes

| # | Task | Owner | Done |
|---|---|---|---|
| 2.A1 | Ingest from files and streams; motion gate | solo | ◐ files, webcam index and stream URLs with newest-frame reader; motion gate built but off (D17) |
| 2.A2 | YOLO11n-pose + ByteTrack → `tracks.jsonl` | solo | ☑ YOLO11m-pose + ByteTrack → `tracks.jsonl` |
| 2.A3 | Homography per camera; pixel-space fallback for uncalibrated video | solo | ☑ homography from 4 surveyed points; pixel fallback; 96% of G505 track points inside its footprint |
| 2.A4 | Track repair (gap ~1.5 s, position, colour) | solo | ☑ gap/position/colour joins, plus close-in-time joins for falls |
| 2.A5 | Head blur on every output frame; rolling buffer, event clips ±5 s | solo | ◐ heads blurred on every detected person (sized for close-up too); people the detector misses are NOT blurred; event clips ±5 s from a ring buffer |
| 2.B1 | Eval harness: precision, recall, start-time error, temporal IoU, false alarms/hour | solo | ☑ `angelseye.eval` (precision, recall, start error, tIoU, false alarms/hour, duplicates) |
| 2.B2 | Behaviour: SOS gesture (MediaPipe on upscaled hand crop + state machine) | solo | ◐ whole-body pose (both wrists above head) only; hand-sign SOS needs our own footage |
| 2.B3 | Behaviour: following (vs companions) | solo | ◐ built + self-check (follows vs companions); no ground truth to score it |
| 2.B4 | Behaviour: loitering | solo | ◐ built + self-check; fires on MEVA; no ground truth to score it |
| 2.B5 | Behaviour: fall | solo | ◐ scored on UR Fall: P 0.80, R 0.27 (EVALUATION.md); recall traded for fewer false alarms |
| 2.B6 | Behaviour: sudden run | solo | ◐ scored on UMN + CAVIAR: P 0.60, R 0.56 (EVALUATION.md) |
| 2.B7 | `config.yaml` with every threshold | solo | ☑ `config.yaml` |
| 2.C1 | Fork gods-eye-view into `globe/`; running locally; upstream layers and voice off | solo | ✖ fork replaced by plain CesiumJS page (D14) |
| 2.C2 | Cameras with view cones; fly-to | solo | ☑ cameras, view cones from calibration, fly-to on event |
| 2.D1 | Hub: FastAPI + SQLite event store + WebSocket + clip serving | solo | ☑ FastAPI + SQLite + WebSocket + /media + live MJPEG relay |
| 2.D2 | Alert card; responder phone page | solo | ☑ toast + responder page (`/responder`) |
| 2.R1 | Watch rules: admin types a rule ("flag if a person raises their hand") → compiled to pose/object/pair checks (`angelseye/rules.py`), hub `/api/rules`, rule box on the Camera page, `rule` events (D20) | kukyos | ◐ compile→confirm→hub→engine→event runs end to end; refusals work live; hand_up/jump only pass synthetic checks, no real true positive yet (2.R4); pair rule floods crowds |
| 2.R2 | Watch rules: YOLOE open-vocab objects for person–object rules, at a reduced rate; fps cost from `angelseye.bench` | kukyos | ☐ |
| 2.R3 | Watch rules: gated vision-model yes/no for rules geometry can't express (prefilter first, 2 consecutive yes) | kukyos | ◐ compiles to a yes/no question, asked inside the describer call (D21); replay: "holding a laptop" fired (4 yes), "wearing a lanyard" missed; not live yet |
| 2.R4 | Watch rules: record + label clips (raise hand, jump ×3, bend down, one person–person, one person–object) and score in `angelseye.eval` | kukyos | ☐ |
| 2.D3 | Upload-a-video mode → events JSON + annotated video | solo | ◐ built (Clips → drop a video); not yet exercised end to end in the browser |

## Stage 3 — The gate

| # | Task | Owner | Done |
|---|---|---|---|
| 3.1 | End to end on staged clips: events with who/when/evidence → hub → pins on globe | solo | ◐ MEVA + showcase clips → hub → grid, map pins, feed; Gate not formally signed off |
| 3.2 | One live phone stream end to end | solo | ☑ phone camera live end to end, with open-ended activity (D19) |
| 3.3 | People dots on the globe from homography | solo | ☑ people dots on the map from the homography |
| 3.4 | First eval numbers and `angelseye.bench` numbers recorded | solo | ◐ eval numbers recorded; bench on a busy camera still to run |

## Improvements — open to teammates (details, evidence and fixes in `IMPROVEMENTS.md`)

| # | Task | Owner | Done |
|---|---|---|---|
| I1 | False "entered"/"left" on the live camera: tracker buffer, merge by position + colour, "left" only at a frame edge; ground-truth clip + score in `eval` | kukyos | ◐ `trackers/live.yaml` (buffer 150), nearest-position merge, edge/occluded leave, enter/leave no longer logged (tiles instead), `--rotate`. Colour merge, ground truth + score open |
| I10 | Live page: one tile per subject; rotate option on Add camera; prompt example leak ("puzzle cube") removed; caption priorities (D21) | kukyos | ◐ replayed recording only; not yet on the live phone |
| I2 | Cut vision-model tokens: send only on change, back off on repeated answers, smaller image; measure from `vlm` stats | | ☐ |
| I3 | Ghost subjects: show/use a track only after strong detections + visible keypoints; check false alarms in `eval` | | ☐ |
| I4 | Vision-model latency 3–14 s: faster model or fewer people per call | kukyos | ◐ no context strip for one person, `crop_h` 240, 2 calls in flight: 2.1–2.7 s on one 90 s replay (was median 7.7 s); not yet live |
| I6 | One person drawn as several on live cameras (1280 upscale) → `model.live_imgsz: 640` | kukyos | ◐ webcam: 1 box, 1 ID per frame; phone stream not rechecked |
| I7 | Non-events in the log (idle captions, clothing, desk loitering) | kukyos | ◐ built on `mvp1`; idle handling seen live, not scored |
| I5 | Check the model's self-reported confidence against labelled clips before alerting on it | jonathan-16bit | ◐ offline evaluator and review protocol built; labelled clips and calibration decision still needed |
| I9 | Camera page is a grid of all live cameras; add/remove IP cameras by URL (host only); cap in `hub.max_engines` | kukyos | ◐ endpoints checked with a fake MJPEG camera; page JS syntax-checked, not looked at in a browser; max_engines not measured |
| I8 | Teammates test Side A remotely: hub token gate for tunnel traffic, `/webcam` browser page, hub starts one engine per webcam (max 2) | kukyos | ◐ gate, ingest and engine start checked locally with curl; not tried through ngrok or a real webcam |
| I11 | Expire stale vision-rule answers and reject out-of-order replies; require a single-person question | jonathan-16bit | ◐ implemented and covered by offline tests on `dev/mvp3-offline-fixes`; live model check remains |
| I12 | Require token for direct LAN access and keep camera source endpoints loopback-only | jonathan-16bit | ◐ implemented and covered by offline ASGI checks on `dev/mvp3-offline-fixes`; real tunnel check remains |

## Stage 4 — Side B

| # | Task | Owner | Done |
|---|---|---|---|
| 4.0 | Side B setup without a GPU: `requirements-hub.txt` + MEVA site snapshot in `data/samples/site/` (README → "Screens only") | kukyos | ☑ on `mvp2`; checked from a fresh clone in a fresh venv |
| 4.1 | Amber: per-track crops, CLIP embeddings, colours, height (A) | | ☐ |
| 4.2 | Amber: search API, case ID, audit log, path + next-camera prediction (D) | | ☐ |
| 4.3 | Amber: path on the globe (C) | | ☐ |
| 4.4 | SafeWalk: edge costs from counts, brightness, incidents (B) | | ☐ |
| 4.5 | SafeWalk: fastest vs safest route + heatmap on the globe (C) | | ☐ |
| 4.6 | Gemini confirmation and narration of candidate events (D) | solo | ◐ superseded in spirit by D19: Qwen3-VL describes activity live; event confirmation not built |
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
