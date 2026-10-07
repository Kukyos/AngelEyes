# README pictures

Screenshots and one GIF of Angel's Eye's own output, used by the top-level README. Every face that
the engine detected is blurred. Each frame was checked by eye before it was committed. Clips
where the blur missed a face for even one frame (several UR Fall clips) are not used.

| File | What | Source footage |
|---|---|---|
| `live-captions.gif` | MEVA camera G506 replayed as a live camera (`--live --imgsz 1280`), 8 s at 100 s, cropped | MEVA dataset, Kitware/IARPA DIVA, mevadata.org (CC-BY-4.0) |
| `camera.jpg` | Camera tab during the same replay | MEVA (CC-BY-4.0) |
| `incidents.jpg` | Incidents tab: UR Fall `fall-02`, the rule it broke, and one Ask answer (Qwen3-VL, 5.6 s) | UR Fall Detection Dataset (Kwolek & Kepski, CMPB 2014), research use |
| `site.jpg`, `safewalk.jpg` | Site and SafeWalk tabs at 11:03:32 on the site clock | MEVA (CC-BY-4.0); Esri World Imagery |

The screenshots were taken with headless Chrome at 1600×1000, scaled to 1200 px wide.
