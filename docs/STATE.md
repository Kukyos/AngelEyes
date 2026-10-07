# State — start here

**Every new session reads this file first, and updates it before the session ends.**
It says where the project is right now, what is decided, what is not, and what to
do next. Everything else in `docs/` is reference; this is the handoff.

Last updated: 2026-10-07 (branch `mvp3`: SafeWalk merged, World tab with public livestreams).

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

- **Remote testing (I8, `mvp2`):** teammates open `/webcam?token=…` through an ngrok link, their browser
  webcam goes to the hub (`/api/ingest/{name}`), the hub starts an engine on the host for it, and the
  annotated feed appears on Camera. `HUB_TOKEN` gates tunnel traffic (requests with `X-Forwarded-For`);
  local traffic is exempt. Checked with curl (gate 401/200, raw stream 403 via tunnel, engine started,
  `/api/live` listed it). **Not yet tried through real ngrok with a real webcam.**

- **IP cameras + grid (I9, `mvp2`):** Camera page shows every live camera as a tile; "Add camera" takes a name
  and URL and the hub starts an engine (`/api/sources`, host only: the hub fetches that URL, so tunnel
  callers are refused). Webcam page now sends 480 px frames, 3 in flight (it was ~2 fps through ngrok).
  Checked with a fake MJPEG camera; the page itself has not been looked at in a browser yet.

- **Branch `mvp3`** = `mvp2` + I10 (rotate, subject tiles, tracker memory, prompt fixes). New work goes here.
- **Live-camera fixes (I10, `mvp2`/`mvp3`):** the phone stream was sideways (the main cause of false "down"/falls,
  ID churn and dead hand-up rules): Add camera now has a rotate option (`--rotate`). Enter/leave are no longer
  logged; the Camera page shows one tile per subject. Longer live tracker buffer; prompt no longer leaks
  "puzzle cube"; 2 vision calls in flight. Captions by priority (D21): objects only when used, valuable
  or dangerous; looks only through a rule. Rules geometry can't check compile to a yes/no question asked inside
  the describer call (2.R3): "holding a laptop" fired on the replay, "wearing a lanyard" missed. Checked on a replayed recording only (`IMPROVEMENTS.md` I10).

- **SafeWalk merged (`feat/safewalk` → `mvp3`, 4.21–4.22):** the teammate's branch is merged with their commits.
  Routing no longer needs networkx or OSMnx: the graph is `data/street_graph.json` (189 nodes, 490 edges) and
  `angelseye/safewalk.py` runs Dijkstra on the standard library, so the hub-only setup still starts. Thresholds are in
  `config.yaml` `safewalk`. `/api/safewalk?at=` replays the site: people per camera from its tracks, incidents aged
  against that time (with wall-clock time every 2018 alert had expired). The SafeWalk tab follows the site clock and
  draws streets shaded by cost, a dashed fastest and a solid safest route, alert rings, and a reason per camera.
  Checked: at 11:03:20 the fall near G341 moves the safe route (505 m → 532 m, +5%).
- **World tab (4.23):** 12 public YouTube livestreams (`data/streams.json`: the user's 4 plus 8 street/square cams
  picked by hand from Volve Vision, with Volve's coordinates) as embeds, plus pins on a world map. **Analyse** resolves
  one with yt-dlp and starts an engine with `--no-describe` (tracking, pose, rules, blurred faces, no vision-model
  credit); **Captions** restarts it with the vision model. Analysed streams also show on Camera. The HLS reader is
  paced (segments arrive in bursts): 332 vs 141 distinct frames in 25 s, max gap 1.0 s vs 4.5 s, measured on Sukhumvit.
  All 12 open in OpenCV at 720p. Streams run at `streams.imgsz: 1280` (wide scenes, small people; 640 found 0 people
  in 10 Brasov frames, 1280 found 10). Analyse seen live on Davao and Brasov: boxes, blur, person count on the tile.
  Distant seated crowds are still missed; false alarms on busy scenes not measured.

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
- [ ] Amber alert (Stage 4) not started. SafeWalk is built (4.21–4.22); its street graph is a fixed export, so a new area needs OSMnx once to regenerate `street_graph.json`.
- [ ] Older open items from planning still stand: 5 km route, alert channel, offender-registry
      layer, post-hackathon path.

## Known problems (say them out loud, don't hide them)

- **World tab embeds are not blurred.** Until Analyse is pressed a tile is YouTube's own player (grayscale), so faces
  show as the channel publishes them. Only the analysed picture is ours and blurred. Flagged to the user, who asked for
  the streams "visible first"; whether unblurred embeds are acceptable under the privacy rule is **not yet confirmed**.
- **SafeWalk has no brightness for the recorded site** (only live engines push it), so "dark" is the unknown penalty
  everywhere there. Streets without a camera all cost the same, so the safe route only moves where a camera sees an
  alert or an empty street.

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

- Try Analyse on two or three World streams at once on the 4060 (`hub.max_engines: 4`) and write the fps in
  EVALUATION; check the false-alarm rate on busy scenes (Times Square, Sukhumvit) before showing them.

0. Re-add the phone camera with **90°** rotation and check tiles, captions, the hand-up rule and one vision rule
   ("anyone holding a phone") live. The lanyard miss needs a look: try a larger crop_h for vision rules.
   Then test watch rules live on the webcam: raise a hand, jump 3×, bend down. Then record those
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
| 2026-10-07 | SafeWalk merge + World streams | Merged `feat/safewalk`; graph to JSON, stdlib Dijkstra, config thresholds, replay-time costs, finished SafeWalk tab. World tab: 12 livestreams, Analyse/Captions toggles (yt-dlp, `--no-describe`), paced HLS reader. Checked in Chrome. |
| 2026-10-07 | mvp3 + rule questions | Branch `mvp3` pushed. D21 caption priorities; 2.R3 vision rules ride the describer call (2 yes in a row). Replay: laptop rule fired, lanyard rule missed. |
| 2026-10-07 | Live accuracy (I10) | Phone feed was sideways: `--rotate`, rotate option on Add camera. Subject tiles replace enter/leave log lines. `trackers/live.yaml`, neutral prompt, 2 calls in flight. Replay: down 648→26 frames, IDs 20→14, 0 false alarms, 2.1–2.7 s per call. Not yet live. |
| 2026-10-07 | Remote teammate testing | I8: token gate, `/webcam` page, ingest → engine auto-start, README section, RESOURCES (ngrok). Curl-checked only. |
| 2026-10-07 | mvp2 Side B setup | Branch `mvp2`. `requirements-hub.txt`; `data/samples/site/` (9 MEVA runs: events, tracks, keyframes, 4.7 MB, CC-BY attribution); README "Screens only". G506 re-rendered: its false fall (191.9 s, person behind a pillar) still fires. Checked from a fresh clone + fresh venv with hub-only deps. |
| 2026-10-07 | Watch rules + I5 merge | Merged teammate's `eval/activity-confidence-i5` into `mvp1`. Finished 2.R1: `rules.py` + hub `/api/rules` + Camera rule box + `rule` events. Live compile verified; refusals verified; hub→engine→event verified on UMN (57 pair events/40 s, 0 hand). Fixed `hold_s: 0` from the model. Not yet tried on a real person. |
| 2026-10-07 | Street test data | TfL JamCam API live (890 cams). Engine runs a JamCam MP4 straight from its URL, no code: Piccadilly Circus, 131 frames, 10.8 fps, people tracked, 0 events. No new resources added. |
| 2026-10-07 | mvp1 fixes | Branch `mvp1`. Webcam test: one person showed as 3–5 nested boxes / 18 IDs (1280 upscale); `live_imgsz: 640` → 1 box, 1 ID. Idle answers not logged, no clothing/absence captions, loitering only on calibrated cameras (I6, I7). Rules module (2.R1) paused, no code yet. |
| 2026-10-07 | I5 confidence evaluation | Built offline event-confidence scorer, label-sheet generator, and review protocol on an independent branch; synthetic checks pass. Real labels and a calibration decision remain. |
| 2026-10-07 | Issues doc | Wrote `IMPROVEMENTS.md` (I1–I5) with measured evidence from the hub DB and `vlm` stats; TASKS rows for teammates. |
| 2026-10-07 | First build | Engine, hub, eval, bench, web page (Camera / Site / Clips), responder page. MEVA site from calibration; UR Fall, UMN and CAVIAR scored; live phone camera with open-ended activity via Qwen3-VL. Decisions D13–D19. Committed and pushed. |
| 2026-10-06 | Pre-planning | Pushed docs to GitHub. Re-read PSI07's must-do list. Wrote `CAPABILITY_MAP.md` (all behaviours by layer, Side B features, legal paths); added D10–D12 and task 0.8. No code. |
| 2026-10-06 | Planning | Read the booklet; compared all 10 statements; chose PSI07 + safety layer; named it Angel's Eye; researched data, keys and costs; wrote these docs. No code. |
