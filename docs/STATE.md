# State — start here

**Every new session reads this file first, and updates it before the session ends.**
It says where the project is right now, what is decided, what is not, and what to
do next. Everything else in `docs/` is reference; this is the handoff.

Last updated: 2026-10-07 (docs synced to `main` from `mvp2`).

> **Branches:** `main` carries the docs only plus the first build. The code described below
> (watch rules, live fixes I6/I7, I5 scorer, Side B setup) lives on `mvp1` / `mvp2`.

---

## Where we are

- **Side A runs end to end and live.** One package, `angelseye/`:
  - `engine` turns video into tracks, events and annotated video.
  - `behaviours` holds the rules, each with self-checks.
  - `geo` holds the cameras and homography; `describe` calls the vision model.
  - `hub` is FastAPI + SQLite + WebSocket + the live MJPEG relay.
  - `eval` and `bench` produce the numbers.
- **The screens are one page,** `web/index.html`, served by the hub, in black and white (D18):
  - **Camera:** the user's Android phone (IP Webcam) as a live CCTV. Pose and tracking run at
    15 fps. The vision model (Airouter Qwen3-VL) says in open vocabulary what each person is
    doing, every ~4 s. Verified live on 2026-10-07: "holding a scrambled puzzle cube",
    "resting chin on hand", entries and leaves.
  - **Site:** 9 synchronised MEVA cameras (2018-03-07 11:00) on a grid, plus a grayscale map
    with each camera's calibrated position and view cone, people dots and event pins.
  - **Clips:** the UMN crowd run, a UR Fall clip and drag-and-drop upload.
  - The responder phone page is at `/responder`.
- **Measured** (`docs/EVALUATION.md`, `angelseye.eval`, 59 public clips): fall P 0.80 / R 0.27,
  sudden run P 0.60 / R 0.56. The thresholds were tuned on those same clips, so the numbers
  are optimistic; the false-alarm fixes traded fall recall (it was 0.53) for precision.
- **Team:** D13 made the user sole builder; teammates are now working too. Lanes are not
  re-assigned yet; claim rows in `TASKS.md` before touching code.
- **Improvements open to claim:** `docs/IMPROVEMENTS.md` (I1–I5: false enter/leave, token
  use, ghost subjects, model latency, self-reported confidence), rows in `TASKS.md`.
- **Branch `mvp1`** is the working build the user tests; live fixes I6/I7 are there
  (`docs/IMPROVEMENTS.md`). Campus Wi-Fi blocks the phone camera; use the laptop webcam
  (`angelseye.engine 0 --live --name laptop --hub http://127.0.0.1:8000`) or the phone's hotspot.
- **I5 branch:** `eval/activity-confidence-i5` has a standalone scorer and review
  protocol for the confidence displayed on vision-model activity events. It needs
  labelled clips before any calibration conclusion; it does not alter live alerts.
- **Watch rules (D20, 2.R1) built on `mvp1`:** the admin types a rule in the Camera page's "Watch
  rules" box. It is compiled by one text-only model call into fixed checks (`hand_up`, `bent_over`,
  `jump`, pair `near`) and read back as "Will flag: …". On Confirm it is stored in the hub
  (`/api/rules`); engines re-read it every 3 s and emit `rule` events. Objects (2.R2) and
  vision-model yes/no (2.R3) are refused for now, and so are gender, age, face and identity rules
  (both refusals seen live). Self-checks: `python -m angelseye.rules`.
- **Branch `mvp2`** (from `mvp1`) is what teammates build Side B (the map layer) on. They don't
  run the engine: `requirements-hub.txt` (no torch/CUDA) + the MEVA site snapshot in
  `data/samples/site/` copied into `runs/`. README → "Screens only". Videos aren't in the
  snapshot (87 MB > the 50 MB samples limit), so the grid tiles stay black; map, dots and pins work.
- **I5 merged:** `eval/activity-confidence-i5` (teammate) is merged into `mvp1`:
  `angelseye/eval_activity.py`, `docs/I5_CONFIDENCE_EVALUATION.md`, `tests/test_eval_activity.py`.
- **While I5 waits for labels:** I2 change detection/backoff logic can be built with
  synthetic sequences on a separate branch. Final token/cost and caption-quality
  measurements should follow I1/I3 integration and use the same recorded input.

## Decided this session

| Decision | Where |
|---|---|
| Sole builder; build before the clock | D13 |
| Plain CesiumJS page, not the gods-eye-view fork (Node 24.13 < 24.14) | D14 |
| MEVA site from KRTD calibration; slot 2018-03-07 11:00; UR Fall + UMN + CAVIAR for scoring; YOLO11m-pose @1280, conf 0.1; motion gate off | D15, D17 |
| Black-and-white screens, no name or claims text | D18 |
| Live phone camera + open-ended activity via Airouter Qwen3-VL; new event type `activity` | D19 |

## Not decided / open

- [ ] **Organisers' ruling** on code written before the 24-hour clock (TASKS 0.2).
- [ ] **Airouter top-up.** About $0.0003–0.0005 per call, measured. $0.25 left at the start of
      live testing; ~$2 recommended.
- [ ] **Cesium token.** It's restricted to `http://localhost:5173`. Either run the hub with
      `--port 5173` or add `localhost:8000` to the token's allowed URLs. Without it the map
      falls back to Esri imagery, which works.
- [ ] Our own staged recordings (`DATA.md` shot list): SOS hand sign, following, loitering
      with ground truth. Following, loitering and SOS have no scored truth yet.
- [ ] Amber alert and SafeWalk (Stage 4) not started; a routes graph needs OSMnx.
- [ ] Older open items from planning still stand: 5 km route, alert channel, offender-registry
      layer, post-hackathon path.

## Known problems (say them out loud, don't hide them)

- **Watch rules aren't proven on real people yet.** `hand_up` and `jump` pass only on
  synthetic keypoints. The "close together" rule fired 57 times in 40 s on the UMN crowd
  (uncalibrated, distance from `pair_scale`). That is the rule as written, but too noisy
  for a crowd. The model sends `hold_s: 0` when no hold was stated; it is now read as
  "use the config default" (0.5 s).

- **Privacy rule not fully met:** blur follows detection, so a person the detector misses
  is not blurred (seen on fast runners in the UMN clip). Close-up faces are now covered
  properly; that was fixed after the first live test.
- **False alarms on real CCTV:** bending, crouching and arms-spread close-ups looked like
  falls. Each was fixed with a rule (lying-shape required, hips low, cut-off boxes ignored),
  but `fall` still has measurable false alarms; see EVALUATION.
- **Vision-model latency** is 3–14 s per call, measured, and longer while the GPU is shared
  with batch jobs.
- **Loitering fires on someone sitting at a desk** for 60 s: that is the rule as written. It
  needs context (zones) before a home or office demo.

## First steps for the next session

0. Test watch rules live on the webcam: raise a hand, jump 3×, bend down. Then record those
   clips and score them (2.R4). After that comes 2.R2 (YOLOE objects).
1. Read this file, then `EVALUATION.md` and `DECISIONS.md` D13–D19.
2. Start: `python -m angelseye.hub`, then the live command in the README, and open
   http://localhost:8000.
3. G506 false fall at 191.9 s (11:03:16): re-rendered on the current config, still fires. Two people
   standing, one half hidden behind a pillar. The bending fix doesn't cover occlusion; needs a
   detector fix (it also ships in `data/samples/site/`).
4. Run `python -m angelseye.bench data/meva/<G506 clip> --camera G506` (a busy camera) and
   put the result in EVALUATION.md; it hasn't been run on the final config.
5. Record our own clips for SOS, following and loitering and add them to `ground_truth.csv`.
6. The first build is committed and pushed to `origin/main`. Commit with no AI trailers (CLAUDE.md).

## Housekeeping (outside this repo)

- Plaintext Groq keys in `SHITIBUILT/Claweo/config.py` and `SHITIBUILT/ParticleAI/SD-INTEGRATION.md`:
  rotate them before anything goes public.
- The Airouter key file lives on the Desktop; this repo's `.env` (gitignored) holds a copy of
  the vision key from `SIH26P3/.env`.

## Session log

| Date | Session | Outcome |
|---|---|---|
| 2026-10-07 | I5 handoff on main | Recorded the pushed `eval/activity-confidence-i5` tooling, its missing labels and calibration decision, and I2 work that can proceed independently. Docs only; no evaluator code merged. |
| 2026-10-07 | Docs sync to main | Copied README and `docs/` from `mvp2` to `main` so main's docs match everything done. No code moved. |
| 2026-10-07 | mvp2 Side B setup | Branch `mvp2`. `requirements-hub.txt`; `data/samples/site/` (9 MEVA runs: events, tracks, keyframes, 4.7 MB, CC-BY attribution); README "Screens only". G506 re-rendered: its false fall (191.9 s, person behind a pillar) still fires. Checked from a fresh clone + fresh venv with hub-only deps. |
| 2026-10-07 | Watch rules + I5 merge | Merged teammate's `eval/activity-confidence-i5` into `mvp1`. Finished 2.R1: `rules.py` + hub `/api/rules` + Camera rule box + `rule` events. Live compile verified; refusals verified; hub→engine→event verified on UMN (57 pair events/40 s, 0 hand). Fixed `hold_s: 0` from the model. Not yet tried on a real person. |
| 2026-10-07 | Street test data | TfL JamCam API live (890 cams). Engine runs a JamCam MP4 straight from its URL, no code: Piccadilly Circus, 131 frames, 10.8 fps, people tracked, 0 events. No new resources added. |
| 2026-10-07 | mvp1 fixes | Branch `mvp1`. Webcam test: one person showed as 3–5 nested boxes / 18 IDs (1280 upscale); `live_imgsz: 640` → 1 box, 1 ID. Idle answers not logged, no clothing/absence captions, loitering only on calibrated cameras (I6, I7). Rules module (2.R1) paused, no code yet. |
| 2026-10-07 | I5 confidence evaluation | Built offline event-confidence scorer, label-sheet generator, and review protocol on an independent branch; synthetic checks pass. Real labels and a calibration decision remain. |
| 2026-10-07 | Issues doc | Wrote `IMPROVEMENTS.md` (I1–I5) with measured evidence from the hub DB and `vlm` stats; TASKS rows for teammates. |
| 2026-10-07 | First build | Engine, hub, eval, bench, web page (Camera / Site / Clips), responder page. MEVA site from calibration; UR Fall, UMN and CAVIAR scored; live phone camera with open-ended activity via Qwen3-VL. Decisions D13–D19. Committed and pushed. |
| 2026-10-06 | Pre-planning | Pushed docs to GitHub. Re-read PSI07's must-do list. Wrote `CAPABILITY_MAP.md` (all behaviours by layer, Side B features, legal paths); added D10–D12 and task 0.8. No code. |
| 2026-10-06 | Planning | Read the booklet; compared all 10 statements; chose PSI07 + safety layer; named it Angel's Eye; researched data, keys and costs; wrote these docs. No code. |
