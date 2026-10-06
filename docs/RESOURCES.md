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
| MediaPipe Hands | Apache-2.0 | SOS gesture landmarks |
| OpenCLIP | MIT | Amber appearance search |
| OSMnx + OpenStreetMap | MIT; ODbL | SafeWalk street graph |
| [MEVA](https://mevadata.org/) | CC-BY-4.0 | Multi-camera footage |
| [TfL JamCams](https://api.tfl.gov.uk/Place/Type/JamCam) | TfL open data terms | Live crowd levels |
| Gemini, Groq, Airouter APIs | Provider terms | Event confirmation, questions, fallback |
