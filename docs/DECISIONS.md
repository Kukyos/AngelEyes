# Decisions

A log of what we decided and why, including the options we rejected, so no reasoning
lives only in a chat. Newest decisions are appended at the bottom. When you change a
decision, add a new entry that supersedes the old one — don't rewrite history.

---

## D1 — Problem statement: PSI07 (2026-10-06)

**Decided:** PSI07, Autonomous Vision & Behaviour Understanding, with a women's and
children's safety product on top.

**How we got there.** The constraints that filtered the ten statements:
1. Judges may bring their own inputs and hidden tests, so favour statements where API
   models generalise without training.
2. Wins should be visible live; a rubric scored on things a demo can't show is risky.
3. Crowded statements cost more to stand out in.
4. One overall winner from ~400 teams — this weights peak impressiveness, not just
   maxing one rubric.

| PS | What it is, plainly | What we'd have built / the hook | Why not (or why) |
|---|---|---|---|
| 01 Document intelligence | Ask questions over PDFs (tables, charts, scans); every answer cites document, page, section; charts read visually | Citations that highlight the exact box on the page; chart numbers extracted and re-plotted over the original as proof; a "damage slider" that blurs/stains the page live; all maths done in code | Solid, but the most-picked statement |
| 02 Video temporal reasoning | Ask a video "what happened right before the alarm?"; every answer needs a timestamp; right event at wrong time = half credit | Event log with timestamps; answer jumps the video to that second with the person boxed | Timestamp accuracy on their videos; heavy setup |
| 03 Cyber threat intel | Stitch innocent-looking logs into an attack story; false-alarm cap | Simulated company + attacks, entity graph, MITRE stages, cinematic attack replay, zero alarms on clean logs | False-alarm cap on unseen judge logs |
| 04 Fraud rings | Find groups of accounts acting together; risk score + reason per transaction/account; false-alarm cap | Simulated transactions with rings, graph clustering, ring lights up | Same cap as 03, less dramatic, Kaggle-crowded |
| 05 Medical images | X-ray second opinion: points to the spot, confidence, phrased as "Doctor, consider…" | Pre-trained model + heatmap + Gemini with notes | Everyone shows the same heatmap; sensitive domain |
| 06 Inpainting | Erase things from photo/video seamlessly; nothing else may move; no flicker | Paste original pixels back outside the hole as a provable "nothing else changed" map | GPU; video consistency very hard in 24h |
| **07 Behaviour understanding** | Track people, understand behaviour, flag who and when | **Chosen** — see below | Crowded with YOLO demos, so the product layer must carry it |
| 08 Proof-carrying data analyst | Every number comes with runnable code; refuse unanswerable questions | Trap scanner before the AI; compute every valid interpretation (dates, currency, dupes) and answer only if they agree; two blind solvers must agree; every number re-runs in the judge's browser (Pyodide); edit a cell and dependent proofs turn red | Was the first recommendation: mechanical rubric, least crowded, reuses AutoLAB's runner and NetSage's rules-before-AI pattern. Rejected by the team as not cool or usable enough to win overall |
| 09 Coding agent | A homemade Claude Code that fixes bugs without breaking tests; hidden tests | — | Judges compare it to tools they already use |
| 10 Deepfake forensics | Real-or-fake score with reasons; must catch unseen fake types | — | Generalising to unseen fakes is near impossible in 24h |

Earlier ranking was 08 > 01 > 03. The team chose 07 instead, with the "God's Eye"
idea and a women's safety twist: the detection engine answers PSI07, and the data it
produces powers a product nobody else will have.

## D2 — Two sides and a gate (2026-10-06)

Side A (scored engine) must run end to end before any Side B (globe extras, amber,
SafeWalk) work starts. Rationale: PSI07 scores Side A; Side B is worthless without it,
and the submission's required Scope Note maps directly onto MVP vs stretch.

## D3 — Five behaviours only (2026-10-06)

SOS gesture, following, loitering, fall, sudden run (encirclement as stretch). Each one
appears in what we show judges; anything else is scope creep. Thresholds configurable
so short staged clips still trigger.

## D4 — Globe: fork gods-eye-view (2026-10-06)

The team wants the God's Eye look. Fork it (MIT), turn off upstream's flights, ships,
satellites, CCTV layer and voice agent so everything on screen is ours, keep its
night-vision/thermal looks, and declare the fork at the top of the README — the repo
went viral (#1 GitHub trending, Aug 2026), so some judges will recognise it.
Fallback: a plain CesiumJS page. Voice agent cut: it needs an OpenAI Realtime key we
don't have.

## D5 — Privacy stance (2026-10-06)

No face recognition, no gender inference, faces blurred, rolling buffer, amber alert
authority-only with an audit log, SafeWalk on aggregates only, mock footage of
consenting teammates only. Rationale: "parents monitor kids on street CCTV" would let
anyone claiming to be a parent track a person across a city; judges will ask; and
gender classification is unreliable and unnecessary because the threats are behaviours.

## D6 — Data sources (2026-10-06)

Real continuous 5 km street CCTV is not obtainable (police-owned; bystanders can't be
published). Use our own staged recordings + MEVA + TfL JamCams; place clips along a
5 km route as labelled mock feeds. Details and sources: `DATA.md`.

## D7 — Name: Angel's Eye (2026-10-06)

Working name TRINETRA was replaced by **Angel's Eye** (repo `AngelEyes`, Python
package `angelseye`).

## D8 — Efficiency is a measured claim (2026-10-06)

Cheap-first cascade; the vision-language model only sees candidate events and is
optional. We show streams × fps and % of frames sent to the VLM from `angelseye.bench`,
never an estimate.

## D9 — How we work and present (2026-10-06)

- No hour-by-hour timings in plans — dependency order and gates instead.
- No scripted demo, no video: we show the working system live, as a plain ordered list
  of features (`PRODUCT.md`).
- Prep is for getting a clear picture of what we build; building early is acceptable to
  the team, subject to checking the organisers' rules (open in `STATE.md`).

## D10 — Ambition raised; capability map first (2026-10-06)

The team does not want to stop at the PSI07 minimum or at five behaviours. Before any
build, `CAPABILITY_MAP.md` lists everything that is possible by layer (tracks, pose,
pairs, crowd, cross-camera, context) and every Side B feature, each with feasibility,
data need and how it would be measured. D3's five behaviours remain the *committed*
build scope until the team promotes more from the map; each promotion gets its own
entry here. D2 (Side A before Side B) is unchanged.

## D11 — Behaviours apply to anyone, not to women (2026-10-06)

Cross-camera and context rules (e.g. a person who never exits a street) flag **any**
person. Women's and children's safety sets priorities and alert wording, not a
classifier. Consistent with D5 (no gender inference).

## D12 — Offender-registry layer and non-consensual tracking (2026-10-06)

- Tracking a named person by appearance without their consent (the "mother tracks
  daughter purely through footage" idea): **rejected.** The consented trip share
  replaces it (`CAPABILITY_MAP.md` §3.3).
- Public sex-offender registry layer: **open, not in MVP or showcase.** Needs a verified
  official public source and a team decision between the options in
  `CAPABILITY_MAP.md` §3.4. If built, it never links a registered person to a camera
  track.

## D13 — Sole builder; build now (2026-10-06)

The user is the only builder and holds every lane and the integrator role. They
chose to start building before the 24-hour clock ("we have planned enough"). This
answers `STATE.md`'s "who builds what" and "start early" items. The organisers' rule
on code written before the clock still needs to be checked.

## D14 — Globe: plain CesiumJS page now (supersedes D4 for the build) (2026-10-06)

gods-eye-view needs Node 24.14+; this machine has 24.13.1, so pass/fail check 1.7
fails as written. We took the documented fallback: one HTML page (`web/index.html`)
that loads CesiumJS 1.146 from jsDelivr and is served by the hub. There is no Node
build step, and all data comes from the hub API. Cesium ion world terrain and
imagery, with a "Photoreal 3D" toggle that tries Google tiles and says so if they
fail. The fork stays possible later; nothing in the hub depends on the page.

## D15 — Demo site: MEVA's Muscatatuck town, cameras from real calibration (2026-10-06; slot and fall data revised in D17)

The grid and globe show the 2018-03-11 16:15 time slot of MEVA. That slot has 14
outdoor cameras with published KRTD calibration in a shared ENU frame with a known
lat/lon origin, so camera positions, view cones and each camera's ground homography
come from MEVA's own models rather than from a hand survey (`angelseye/geo.py` →
`data/cameras.json`, which still uses the planned "4 pixel ↔ lat/long points" form).
The 9 most active of them are analysed. Fall and sudden-run evaluation uses CAVIAR
(INRIA lobby clips with per-frame labels), because MEVA has no falls or runs. The
campus route (`STATE.md`) is still open for our own recordings.

## D16 — Stack confirmed for the build (2026-10-06)

Python 3.12 venv (uv); torch CUDA 12.8 build (an RTX 4060 laptop GPU is available, so
the CPU-only assumption is lifted for this machine); ultralytics YOLO11-pose +
ByteTrack; FastAPI + SQLite + WebSocket; ffmpeg for H.264 output. MediaPipe is
not added yet. The hand-sign SOS needs our own footage to test, so the whole-body
distress pose (both wrists above the head) is the SOS trigger for now. Event `geo`
is `[lat, lon]`.

## D17 — Data, revised after looking at it (2026-10-06, supersedes D15's slot and fall data)

- **Site slot:** 2018-03-07 11:00, not 2018-03-11 16:15. A person-count sweep of the 16:15
  slot found at most 5 people on any of 9 cameras and most cameras empty. Ranking every
  annotated slot by MEVA annotation volume picked 11:00: 12 calibrated outdoor cameras
  (G639 is dropped everywhere: its KRTD model has fx 775 vs fy 1326 and fails the ground
  check). We analyse 9 of the 12, the first ~2.5–5 minutes of each.
- **Fall data:** UR Fall Detection (front camera), not CAVIAR. CAVIAR set 1 is an
  overhead fisheye; the pose model does not see people lying or running from straight
  above, and "upright" has no meaning there. CAVIAR falls are marked unscored.
- **Run data:** UMN crowd video (11 scenes; its own "Abnormal Crowd Activity" overlay
  is the ground truth) plus CAVIAR's runs.
- **Model:** YOLO11m-pose at imgsz 1280, conf 0.1 into ByteTrack (its low-score pass keeps
  blurred runners on their tracks). Measured on UMN running frames: m@1280 found the
  most people; 640 found none on 320 px video.
- **Motion gate off** (`motion_gate: 0`): the global-mean test skipped 17% of G506 frames
  with small walkers in view. Needs a per-block test before it can be turned on.
- **Thresholds tuned on the evaluation clips** (pixel-space speeds from UMN scene 1; fall
  `down_s`, hip drop and track-repair joins from UR Fall). There is no held-out split, so
  the numbers in `EVALUATION.md` are optimistic.

## D18 — Screen design: black and white, no labels-for-the-sake-of-it (2026-10-06)

User direction: simple black and white, smooth and responsive, no product name or
claims text on screen; what we detect is the point. The overlay burned into the
footage is monochrome too (grey = tracked, white = flagged, inverted tag = alert). The
map has no sky, sun, moon or atmosphere, and uses grayscale imagery.

## D19 — Open-ended activity from a live phone camera (2026-10-07)

User direction: a phone mounted above as the CCTV camera, with the system saying what a
person is doing in open vocabulary (drinking water, reading a book, leaving the frame),
not a fixed list.

- **Phone:** Android with the IP Webcam app (MJPEG over Wi-Fi), read directly by OpenCV.
- **Model:** Airouter `alibaba/qwen3-vl-instruct` (user's choice). Measured on one CCTV
  frame: Qwen3-VL answered correctly at 3.1 s and $0.00031. `nemotron-nano-12b-vl`
  invented two people who weren't there. `ling-3.0-flash-vl` spent its budget
  reasoning and returned no answer. Groq `qwen3.8-27b` was faster (1.3 s) but was not chosen.
- **Schema:** a new event type `activity`, approved by the user, with the description in
  `evidence.series.caption`. No other field added.

## D20 — Admin-written watch rules (2026-10-07)

User direction: on the live camera, an admin types what to flag ("flag if a person raises
their hand", "…jumps three times", "…bends down"), including person–person and
person–object relations, and it is detected accurately without inventing people.

- **Compile, don't guess.** Each rule is compiled once (text-only call) into a fixed set of
  pose / pair / object checks, shown back to the admin in plain words before it goes live.
  Thresholds the admin didn't state come from `config.yaml`.
- **Objects:** Ultralytics YOLOE open-vocabulary detection, prompted with the objects the
  rules name (user's choice over fixed COCO classes). Already in the installed `ultralytics`;
  new weights + MobileCLIP text encoder (RESOURCES.md).
- **Can't express it in geometry:** the vision model answers yes/no, only after a cheap
  pose/object prefilter fires, and the rule fires only after 2 consecutive yes answers
  (user's choice; keeps I2 token use down).
- **Schema:** new event type `rule`, approved by the user; rule id, rule text, compiled spec
  and the measured signals go in `evidence.series`. No other field added.
- **Privacy:** rules on gender, age, identity, face or a named person are refused.
- **Lanes:** I1 (ID switches) and I3 (ghost subjects) stay with teammates; rules run on the
  tracker as it is until those land.
- **Cost control:** the model runs only with `--live` / `--describe` and only while a
  person is in view, at most every 4 s (1.5 s on enter or leave). The engine records
  the provider's reported cost per run (`events.json` → `vlm`). The user's balance was
  $0.25; a ~$2 top-up was recommended for building and the showcase.
- **Privacy:** only frames with heads already blurred leave the machine. The close-up
  blur was resized for near faces after the first live test showed a readable face.

## D21 — What the describer says, by priority (2026-10-07)

User direction: colours and other looks are stated only when a rule asks for them; objects only when
the person is doing something with them or they matter (valuable, or could hurt someone).

- **Default caption:** posture, then what the hands or body do, then an object only if used, handled,
  valuable or dangerous. No clothing, colours or looks. (Replaces the short-lived "wearing" tile line.)
- **Looks and objects come from rules:** a rule geometry can't check ("anyone holding a laptop",
  "someone wearing a lanyard") compiles to one yes/no question about one person (2.R3). It rides on the
  describer's regular call, so it costs no extra calls; it fires after `rules.vision_yes` (2) yes answers in a row.
  D20's "cheap prefilter" is not needed for this: no call is made only for the rule.
- Gender, age, identity and faces stay refused in rule text and in the compiled question.

## Still open

Tracked in `STATE.md` → "Not decided".
