# Architecture

One engine feeds every safety feature. Side A turns footage into tracks and events;
everything in Side B reads from the hub, which is why the engine is built and
measured first.

```
 Footage in                 Side A engine                  Hub                    Side B layer
 ----------                 -------------                  ---                    ------------
 Live cameras      --->  Motion gate                  Track index        --->   3D globe
 (phones, CCTV)            |                          (crops, colour,           Guard's phone
 Recorded footage  --->  YOLO11n-pose                  height)                  Amber alert
 (MEVA, our clips)         |                                                    SafeWalk
 Judge's upload    --->  Tracker + repair    --->     Event store        --->
 (any video file)          |                          (SQLite + WebSocket)
                         Behaviour rules
                           |
                         Gemini check (optional)
```

> **Stack and repo shape below are proposed, not locked.** Confirm them in the first
> build session and record the result in `DECISIONS.md`.

---

## Side A — perception and behaviour engine (Python)

A cheap-first cascade runs on one laptop; the vision-language model only sees
candidate events, so the system still works with it switched off.

### Efficiency cascade
1. **Motion gate:** frame differencing skips frames where nothing moves.
2. **Pose detection:** Ultralytics YOLO11n-pose at ~5–8 fps per camera, frames from
   several cameras batched.
3. **Tracking:** ByteTrack — `model.track(persist=True, tracker="bytetrack.yaml")` —
   gives each person an ID.
4. **Track features:** position, speed, heading, keypoints, bounding-box shape over time.
5. **Behaviour rules and state machines** over those features.
6. **Stretch:** candidate events only send 3–6 keyframes to Gemini to confirm and narrate.

The efficiency claim we show judges is measured, never estimated: streams × fps on one
laptop and the % of frames that reach the vision model (`EVALUATION.md`).

### Ground-plane mapping
Each camera maps 4 pixel points to 4 latitude/longitude points (a homography). That
gives positions in metres and on the globe, so distances and speeds are real and people
appear as dots on the map. **Uploaded or uncalibrated video falls back to pixel space,
scaled by bounding-box height** — the system must survive a judge's own video.

### Track repair
When a track ends and a new one starts within ~1.5 s, nearby, with similar clothing
colours, join them. Loitering and following depend on track duration, so tracker ID
switches would break them.

### The five behaviours
All thresholds live in one `config.yaml`, so short staged clips (30–90 s) still fire.

| Behaviour | How we detect it | Evidence on the alert |
|---|---|---|
| SOS gesture (Signal for Help) | Pose wrist points locate the hand; an upscaled hand crop goes to MediaPipe Hands; a state machine looks for open palm with thumb tucked, then fingers folding over the thumb, within 2 s | Hand crop frames, landmark states, time |
| Following | For each pair of tracks: the follower's path matches the leader's path delayed 1–10 s, 2–10 m apart, for N+ seconds, with at least one shared turn. Side by side (delay ~0 s, under 1.5 m) counts as companions, not following | Both paths, delay, duration, matched turns |
| Loitering | Stays within radius r for longer than T seconds | Dwell time, positions over time |
| Fall | Bounding box flips from tall to wide, hip drops fast, person stays down 2+ s | Keyframes, hip-height curve |
| Sudden run | Speed jumps above ~2.5 m/s from walking pace; scored higher when moving away from another track | Speed curve |
| Encirclement (stretch) | 3+ tracks within 2.5 m of one person, covering more than 180° around them, for 3+ s | Positions, angle covered |

SOS backup trigger if hand landmarks fail beyond ~2 m: a whole-body distress pose
(both arms raised and crossed), visible to the pose model at longer range.

### Config knobs (`config.yaml`, values from the plan; TBD = tune on our clips)

| Knob | Starting value |
|---|---|
| Sampling rate per camera | 5–8 fps |
| Track repair gap | 1.5 s |
| SOS gesture window | 2 s |
| Following delay range | 1–10 s |
| Following distance range | 2–10 m |
| Following minimum duration | N s (TBD) |
| Following minimum shared turns | 1 |
| Companion rule | delay ~0 s and distance < 1.5 m |
| Loitering radius / time | r (TBD) / T (TBD) |
| Fall: time down | 2 s |
| Sudden run speed | ~2.5 m/s |
| Encirclement | 3+ tracks, 2.5 m, >180°, 3 s |
| Event clip buffer | ~5 s either side |

### Event record
Stored in SQLite, pushed over WebSocket:

```json
{"id": "...", "type": "following", "camera": "cam2", "track_ids": [7, 3],
 "t_start": "...", "t_end": "...", "confidence": 0.86,
 "evidence": {"keyframes": [], "series": {}}, "clip_path": "...", "geo": [0, 0]}
```

**No event without who, when and evidence** — that is the PSI07 key rule.

As built (D16, D19): `type` is one of `sos, following, loitering, fall, sudden_run, activity`;
`t_start`/`t_end` are ISO 8601 local wall-clock times (clip start + offset);
`geo` is `[lat, lon]` of the subject at the start (camera position if uncalibrated,
`null` if neither); `clip_path` is relative to `runs/` (served at `/media/`);
`evidence.series` carries the behaviour's curves plus `video_s: [start, end]`, the
offsets into the source video. The hub rejects records missing any of these
(`angelseye/hub.py` → `Event`). Per-person labels (standing, walking, running, down)
are in `tracks.jsonl`, not in events.

`activity` events (D19) describe what one person is doing in words: `evidence.series.caption`
("holding a scrambled puzzle cube", "entered the frame", "left the frame"), `source`
(`vision model` or `tracker`), and for the model its name, latency and the note that the
confidence is self-reported. The keyframe is the exact image the model was shown.
`clip_path` is `null` for activities. If the tracker switches a person's ID mid-activity,
the new ID is appended to `track_ids` instead of logging a leave and an entry.

### Live camera and open-ended activity (built 2026-10-07)

```
phone (IP Webcam, MJPEG) -> newest-frame reader -> pose + ByteTrack (15 fps) -> rules -> events
                                                        |                         -> hub /api/events, WebSocket
                                                        | heads blurred, P<id> labels
                                                        v
                             every ~4 s, or sooner when someone enters or leaves:
                             [whole view] + [per-person close-up 1 s ago | now]
                                   -> vision model (Airouter Qwen3-VL) -> "activity" events
annotated frames -> hub /api/live/<name> -> MJPEG -> Camera view
```

- `python -m angelseye.engine http://PHONE_IP:8080/video --live --name phone --hub http://127.0.0.1:8000`
- Close-ups are cut from the full-resolution frame, so a far CCTV figure still reaches
  the model in detail. They come after head blur, and the model never sees our captions,
  so it can't echo itself.
- `--describe` adds the same descriptions to a file run; the hub's upload mode uses it.

### Privacy built in
Heads are blurred from pose head keypoints on every frame that leaves the engine. A
rolling buffer keeps only event clips (~5 s either side).

### Two modes
- **Live:** phones (IP Webcam app stream), laptop webcam, or CCTV RTSP.
- **File:** a judge uploads any video and gets an events JSON plus an annotated video back.

---

## Side B — the Angel's Eye layer

Starts only once Side A runs end to end.

### Globe (MVP)
Fork [gods-eye-view](https://github.com/bilawalsidhu/gods-eye-view) and add an Angel's Eye layer:
- our cameras with view cones, live people dots, event pins and an event timeline
- fly-to on alert, plus a clip player
- upstream's flights, ships, satellites, CCTV layer and voice agent switched off, so
  everything on screen is ours; keep its night-vision and thermal looks
- declare the fork at the top of the README
- **fallback:** if the fork fights us early on, a plain ~200-line CesiumJS page with
  3D tiles or OSM buildings and the same layer

Facts about upstream (researched 2026-10-06):
- Vanilla JS + CesiumJS + Vite; Google Photorealistic 3D Tiles; custom GLSL sensor modes
  (CRT, night vision, FLIR/thermal, noir, …).
- Needs **Node 24.14+ or 26.x** (Node 25 unsupported). `npm ci && npm run doctor && npm run dev`
  → http://localhost:4173. Its `dev-fresh.sh` helper is macOS-only.
- Env vars: `CESIUM_ION_TOKEN` (free), `GOOGLE_MAPS_API_KEY` (metered), `OPENAI_API_KEY`
  (voice agent, OpenAI Realtime, 29 tools — we have no key, so it is cut),
  `AISSTREAM_API_KEY`, `FIRMS_MAP_KEY`, `TOMTOM_API_KEY` (not needed).
- ~3,900 public cameras, none in India. Layout: `src/` (`main.js`, `ui.js`, `hud.js`,
  `voice/`, `layers/`, `data/`, `scenes/`), `server/` (credential broker, HLS decoder),
  `config/`, `scripts/`, `tools/`.
- Its responsible-use note: no named-person search, face recognition or tracking individuals.

### Amber alert (stretch 1)
Finds a missing child across cameras by appearance, never by face.
- Per track: the 3 best crops, an OpenCLIP ViT-B/32 embedding, and dominant torso and
  leg colours (located with pose keypoints).
- The homography gives an estimated height in metres, so "child-sized" is a filter
  without faces.
- A text query ("child, yellow hoodie, black backpack") ranks sightings across cameras,
  orders them by time, and draws the path.
- Next camera predicted from a camera-adjacency graph plus heading.
- Authority-only: a case ID is required and every search is audit-logged.
- On MEVA footage, the actors' GPS logs are ground truth for the search.

### SafeWalk (stretch 2)
Routes around deserted and dark streets.
- Campus street graph from OSMnx (download in advance).
- Edge cost = length × (1 + deserted + dark + recent incident). Deserted = the camera's
  rolling people count; dark = frame brightness.
- Streets with no camera get a moderate "unknown" penalty.
- Shows fastest vs safest route, plus a busy/deserted heatmap.
- Real live crowd levels can come from TfL JamCams (`DATA.md`).

### Responder page (MVP)
A minimal phone web page that receives alerts with the clip, camera and a map link.
Delivery via ntfy.sh or a Telegram bot (open question).

### Later stretch, in order
1. Gemini confirms and narrates each event.
2. Plain-English questions ("what happened near Gate 2 after 9 pm?"): Groq answers with
   SQL tools over the event store, returning timestamps and clip links.

---

## Proposed stack

| Part | Proposed |
|---|---|
| Engine | Python 3.11: ultralytics (YOLO11n-pose + ByteTrack), mediapipe, opencv-python, numpy |
| Hub | FastAPI + uvicorn, SQLite, WebSocket |
| Amber | open_clip_torch |
| SafeWalk | osmnx |
| Globe | gods-eye-view fork (CesiumJS + Vite, Node 24.14+) |
| AI | Gemini (confirm/narrate), Groq (questions; Llama 4 Scout vision fallback), Airouter (fallback) |

## Proposed repo shape

```
angelseye/        Python package: ingest, perception, tracking, behaviours, hub, eval, bench
globe/            gods-eye-view fork (vendored; our layer in its own files)
responder/        phone page
data/
  cameras.json      camera registry: id, lat/long, heading, 4 pixel↔lat/long points
  ground_truth.csv  clip, event type, who, true start, true end
  samples/          one small staged clip + its outputs (committed, < 50 MB)
  raw/  meva/       footage (gitignored)
config.yaml       all thresholds
docs/
```

Commands referenced elsewhere: `python -m angelseye.eval --gt data/ground_truth.csv`,
`python -m angelseye.bench`.
