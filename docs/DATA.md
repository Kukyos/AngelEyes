# Data, keys and costs

Researched 2026-10-06. Answer first:

**Real, continuous street CCTV across 5 km is not obtainable. A believable
multi-camera "city" built from real footage is, and it costs nothing.** Indian city
CCTV belongs to the police and municipalities, so access needs official permission,
and footage of bystanders can't go in a public repo. No public dataset follows
people along 5 km of streets.

## What we can actually get

| Source | What you get | Access | Use in Angel's Eye |
|---|---|---|---|
| Our own recordings | 3–4 phone "CCTV" cameras on campus; our exact scenarios (SOS, following, the amber "child") | Record ourselves, consenting teammates only | Live showcase and evaluation ground truth |
| [MEVA](https://mevadata.org/) | Real multi-camera footage of a mock town (Muscatatuck Urban Training Center, Indiana): 38 cameras (some thermal IR), 328 hours / 516 GB / 4,259 clips released, 37 annotated activity types, camera models (KRTD), a 3D site model, a site map, and the actors' GPS logs | Free, CC-BY-4.0. AWS S3, no account: `aws s3 ls --no-sign-request s3://mevadata-public-01/` (us-east-1; [registry](https://registry.opendata.aws/mevadata/)) | The multi-camera "town" on the globe; amber search checked against the actors' GPS |
| [TfL JamCams](https://api.tfl.gov.uk/Place/Type/JamCam) | Real live London street cameras: id, name, lat/long, `imageUrl` (JPG) and `videoUrl` (short MP4) per camera, e.g. `https://s3-eu-west-1.amazonaws.com/jamcams.tfl.gov.uk/00001.07450.mp4` | Free; the endpoint answered without a key | Real live crowd levels for the SafeWalk heatmap; a "real city" layer |
| IITB-Corridor | Indian campus corridor, 1080p, single camera, anomalies including chasing and fighting | Request from the authors; may not arrive in time | Optional extra evaluation |
| [MTMMC](https://sites.google.com/view/mtmmc) | 16 cameras, campus and factory, RGB + thermal, 3,669 people | Signed agreement by email, reviewed for ethics | Skip — too slow |
| Real Coimbatore street CCTV | — | Police or municipal permission | Not possible |

**How we make "5 km":** camera pins along a 5 km route on the map, each backed by a
MEVA clip or our own recording and labelled "mock feed" in the UI. The globe can also
fly to MEVA's real site, where cameras sit at their true positions. (Which route is an
open question in `STATE.md`.)

**Effort:**
- Our recordings: one evening with 3–4 phones (plan below).
- MEVA: about 120 MB per 5-minute clip. Pull 20–40 clips (~2.5–5 GB), preferably from
  the annotated subset.
- TfL: one API call returns every camera with its image and video URLs.

**Avoid:** directories of unsecured private cameras (accessing them is illegal) and
ripping YouTube live streams (against YouTube's terms).

---

## Recording plan (our own footage)

Footage and the pass/fail checks come first, because every other piece is tested on them.

### Camera setup
- [ ] 3–4 phones mounted high (first-floor window or tripod) so the angle looks like CCTV
- [ ] A few clips shot at night
- [ ] A clap or on-screen stopwatch in frame at the start of every clip, for syncing
- [ ] For each camera: GPS position, heading, and 4 ground reference points with lat/long
      from Google Maps (feeds `data/cameras.json` and the homography)
- [ ] Only consenting teammates in frame — no bystanders
- [ ] Clips compressed to under 50 MB each (GitHub rejects files over 100 MB)

### Shot list

| Scenario | Should trigger? | Notes |
|---|---|---|
| Following with 2–3 turns, across 2 cameras | Yes — following | Follower stays 2–10 m behind |
| Loitering ~60 s | Yes — loitering | Same spot, small movements |
| Fall | Yes — fall | Use a mat; stay down 3+ s |
| Sudden run | Yes — sudden run | Walk first, then sprint away |
| SOS gesture at 1, 2, 3 and 4 m | Yes — SOS | Palm out, thumb tucked, fingers fold over |
| "Child" in a loud outfit walking past cameras 1→2→3→4 | Amber search target | Note the exact time at each camera |
| Encirclement (optional) | Yes — encirclement | 3 people close in around one |
| Two people walking side by side | No | Negative for following |
| Someone waiting at a stop | No | Negative for loitering, short wait |
| Jogging | No | Negative for sudden run |
| Sitting down or tying a shoe | No | Negative for fall |
| Waving | No | Negative for SOS |

- [ ] Write `data/ground_truth.csv` right after recording, while it's fresh:
      `clip, event_type, who, true_start, true_end`

---

## Pass/fail checks

| Check | Pass if | Fallback if it fails |
|---|---|---|
| gods-eye-view on Windows | `npm ci && npm run dev` runs on Node 24.14+; free Cesium ion token works | Plain CesiumJS page with our layer |
| 3D tiles over Karunya / Coimbatore | Photorealistic buildings render on campus | OSM buildings + Esri satellite imagery |
| SOS gesture range | MediaPipe Hands reads the gesture at 3 m with an upscaled crop | Show it under 2 m; add the whole-body distress pose |
| YOLO11n-pose speed per laptop | Note fps on CPU and GPU at 640 px | Fewer streams, lower sampling rate |
| API keys | Gemini, Groq and Airouter all answer; note Gemini free-tier limits (shown per project in AI Studio) | Run with the vision model off |
| Phone streams to laptop | IP Webcam streams reach the laptop over our own hotspot or router | Recorded clips through the same pipeline |

## Environment
- [ ] Python 3.11 with ultralytics, mediapipe, opencv-python, fastapi, uvicorn, open_clip_torch, osmnx
- [ ] Model weights, the campus street graph and 20–40 MEVA clips downloaded in advance
- [ ] Keys in a local `.env` only — never committed (`.env.example` lists them)
- [ ] Node 24.14+ for the globe

---

## Keys and costs

| Item | Needed for | Cost | Action |
|---|---|---|---|
| Cesium ion token | The globe; Google Photorealistic 3D Tiles stream through ion (2,500+ cities, 49 countries) | Free account; free-plan quota for Google tiles unconfirmed | Sign up; check Karunya in Google Earth's 3D view |
| Gemini API key | Confirming and narrating events from keyframes | Free tier on current Flash and Flash-Lite models (Gemini 3.x at time of research); paid Flash-Lite input $0.25–0.30 per 1M tokens, Flash $0.75 | Have it. Check our limits in AI Studio. AutoLAB's `gemini.py` still names `gemini-2.5-flash` — update the model name when reusing it |
| Groq API key | Plain-English questions; Llama 4 Scout as a backup vision model | Free tier; exact limits in our Groq console (third-party sources say ~30 RPM / 1,000 requests a day for Scout — unverified) | Have it |
| Airouter | Fallback for any model if free tiers run out (OpenRouter-style, pays by UPI) | Prepaid | Optional top-up. Key file stays on the Desktop |
| Responder alerts | Pushing alerts and clips to a guard's phone | Free (ntfy.sh or a Telegram bot) | Pick one |
| Google Maps Platform key | Only if Cesium ion's Google tiles don't work | Metered, needs a card | Skip unless needed |
| OpenAI | Upstream's voice agent only | — | Skip; voice is cut |

**Money:** nothing is required. Even 1,000 events × 4 keyframes at a generous 1,000
tokens each is 4M tokens, about $1–3 on paid Gemini. Worth having: a small Airouter
top-up (around ₹500–1,000) as a fallback, and our own Wi-Fi router if campus Wi-Fi
blocks phone streams. Rupee amounts are rough estimates.

## Sources (pages opened during research)

[MEVA](https://mevadata.org/) · [MEVA on AWS](https://registry.opendata.aws/mevadata/) ·
[TfL JamCam API](https://api.tfl.gov.uk/Place/Type/JamCam) ·
[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) ·
[Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) ·
[MTMMC](https://sites.google.com/view/mtmmc) ·
[Cesium ion + Google 3D Tiles](https://cesium.com/blog/2023/10/26/photorealistic-3d-tiles-in-cesium-ion/) ·
[gods-eye-view](https://github.com/bilawalsidhu/gods-eye-view)
