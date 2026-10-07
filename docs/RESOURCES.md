# Resources — reuse and declarations

The rules require declaring every external API, dataset, pre-trained model and
open-source component. **Add a row here in the same change that adds the resource.**
This list is copied into the README.

## From our own past projects

Paths are relative to `SHITIBUILT/` on the planning machine.

| Project | What we take | Verified? |
|---|---|---|
| `hmm/gesture_detector.py` | MediaPipe hand-landmark camera loop (OpenCV + MediaPipe hands/face mesh) — the starting point for the SOS gesture | Read |
| `VisioNULLY` | `hooks/usePoseDetector.ts` (MoveNet setup), `components/system/AlertTimeline.tsx` (alert timeline UI), the privacy-first rolling-buffer idea. Note: its fall check is a single-frame rule and its dashboard numbers are simulated | Surveyed |
| `AutoLAB/gemini.py` | Standard-library Gemini client (text + vision, JSON mode). Update its model name (`gemini-2.5-flash`) to a current one | Read |
| `AutoLAB/runner.py` | Subprocess runner with timeouts and output capture — only if we need to run generated code | Read |
| `DispatchUI` | Responder and dispatch UI patterns (React + Leaflet, live mission store) | Surveyed |
| `trotSample/AGENTS.md`, `OdooSampleSolo/HACKATHON_PLAN.md`, `DayFlowOdoo/docs/` | Tested way for 4 people with AI coding agents to share one repo; the source of `HACKATHON_PLAN.md`'s manual and lessons | Read |

Other past projects surveyed during planning (not planned for use): `freshline`
(AST + dependency-graph context packing), `Claweo` (ReAct agent + ChromaDB),
`Lancist/llm.py` (Anthropic/OpenAI-compatible wrapper), `internshipp` (deterministic
rules before AI, human review), `3 Body Agents` (multi-agent pipeline UI),
`NULLSPACE` (Cytoscape graph view), `GameAI` (LSTM sequence model),
`ArtAid` / `Accessnullfr` (MediaPipe face and gaze tracking), `AutoLAB/pdfedit.py`
(PyMuPDF span extraction), `RAGCHATBOT` (page-cited PDF RAG notebook), `NULLCHAT`
(RAG backend whose answer step is a stub). `AsyncRAT-C-Sharp` is excluded from
everything.

## External

| Resource | Licence or terms | Used for |
|---|---|---|
| [gods-eye-view](https://github.com/bilawalsidhu/gods-eye-view) | MIT | Globe shell and sensor visual styles |
| CesiumJS + Cesium ion | Apache-2.0; ion and Google 3D Tiles terms | 3D globe and tiles |
| Ultralytics YOLO11-pose | AGPL-3.0 (fine: our repo is public) | Person and pose detection |
| ByteTrack | MIT | Tracking |
| Ultralytics YOLOE (open-vocabulary detection) + Apple MobileCLIP text encoder | AGPL-3.0; Apple MobileCLIP licence | Objects named in watch rules (D20) |
| MediaPipe Hands | Apache-2.0 | SOS gesture landmarks |
| OpenCLIP | MIT | Amber appearance search |
| OSMnx + OpenStreetMap | MIT; ODbL | SafeWalk street graph (exported once to `data/street_graph.json`; the app needs neither OSMnx nor networkx) |
| [MEVA](https://mevadata.org/) | CC-BY-4.0 | Multi-camera footage |
| [TfL JamCams](https://api.tfl.gov.uk/Place/Type/JamCam) | TfL open data terms | Live crowd levels |
| Gemini, Groq, Airouter APIs | Provider terms | Event confirmation, questions, fallback |

### Added in the first build session (2026-10-06)

| Resource | Licence or terms | Used for |
|---|---|---|
| [MEVA KRTD camera models](https://gitlab.kitware.com/meva/meva-data-repo/-/tree/master/metadata/camera-models/krtd) + clip table | CC-BY-4.0 (MEVA) | Camera positions, view cones, ground homographies (`data/cameras.json`) |
| MEVA clips, 2018-03-07 11:00 slot, 9 cameras (first ~140 MB of each) | CC-BY-4.0. Attribution: "MEVA dataset, Kitware/IARPA DIVA, mevadata.org" | The multi-camera site in the grid and on the map |
| [CAVIAR](https://homepages.inf.ed.ac.uk/rbf/CAVIARDATA1/) INRIA lobby clips + ground-truth XML | EC Funded CAVIAR project/IST 2001 37540; free for research with acknowledgement | Sudden-run truth and walking/meeting negatives (overhead camera; see `EVALUATION.md`) |
| [UR Fall Detection Dataset](https://fenix.ur.edu.pl/~mkepski/ds/uf.html) cam0 videos + per-frame labels (30 falls, 20 everyday activities) | Free for research; cite Kwolek & Kepski, CMPB 2014 | Fall evaluation (front-facing camera) |
| [UMN Unusual Crowd Activity](https://mha.cs.umn.edu/proj_events.shtml) "Crowd-Activity-All" video | University of Minnesota; research use | Sudden-run evaluation (11 crowd panic scenes, labels burned into the frame) and the Clips showcase |
| Ultralytics YOLO11m-pose weights (n and s also downloaded for comparison) | AGPL-3.0 | Pose model, in `models/` (GitHub release v8.4.0) |
| CesiumJS 1.146 from cdn.jsdelivr.net | Apache-2.0 | Globe, no build step |
| Cesium World Terrain + ion imagery | Cesium ion terms (free account token in `.env`) | Ground the cameras and people sit on |
| PyTorch (CUDA 12.8 wheels) | BSD-3 | Runs the pose model on the GPU |
| FastAPI, Uvicorn, python-multipart, PyYAML, lap | MIT / BSD / Apache | Hub, uploads, config, tracker assignment |
| ngrok (host-side tunnel, free tier; user's own install, not a repo dependency) | ngrok terms | Gives teammates an https link to the host's hub so they can send their webcam and watch the result |
| FFmpeg (system install) | LGPL/GPL | H.264 output browsers can play |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | Resolves a YouTube livestream to its HLS address when Analyse is pressed (World tab); engine side only |
| Public YouTube livestreams in `data/streams.json` (4 picked by the user, 8 from Volve Vision's city/square/traffic lists) | YouTube terms; each channel's own. Shown through the standard youtube-nocookie embed | Extra CCTV on the World tab; analysed only on demand |
| [Volve Vision](https://volvevision.com/en) camera pages | Site terms; read by hand, not scraped by the app | Camera coordinates for `data/streams.json`, and the look of the World tab (map + live tiles) |
| OpenStreetMap Nominatim (one lookup, by hand) | ODbL; Nominatim usage policy | Island-level position of the Windmill Bar cam (not on Volve) |
| Esri World Imagery tiles | Esri terms; attribution "Esri, Maxar, Earthstar Geographics" shown on the map | Map imagery when the Cesium token is not valid for the page's address |
