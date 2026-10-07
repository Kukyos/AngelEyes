"""Measure engine throughput on this machine.

    python -m angelseye.bench [VIDEO --camera G340] [--max-s 60]

Runs the full pipeline (decode, motion gate, pose + tracking, behaviours, blur,
annotation, H.264 encode) and reports frames analysed per second, how many camera
streams that sustains at config sample_fps, and the share of frames the motion gate
skipped. Writes runs/bench.json. Defaults to the first MEVA camera in data/cameras.json.
"""
import argparse
import json
import platform

from angelseye import ROOT, load_config
from angelseye.engine import Engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("--camera")
    ap.add_argument("--max-s", type=float, default=60)
    a = ap.parse_args()
    if not a.video:
        cam = json.loads((ROOT / "data/cameras.json").read_text())["cameras"][0]
        hits = sorted((ROOT / "data/meva").glob(cam["clip"] + "*"))
        if not hits:
            raise SystemExit(f"no footage for {cam['id']} in data/meva; pass a video")
        a.video, a.camera = str(hits[0]), cam["id"]
    cfg = load_config()
    s = Engine(a.video, a.camera, ROOT / "runs" / "bench" / (a.camera or "video"), None, a.max_s, cfg).run()
    import torch
    out = {
        "video": a.video, "seconds_of_video": s["duration_s"], "frames_analysed": s["frames_analysed"],
        "analysed_fps": s["analysed_fps"], "sample_fps": cfg["model"]["sample_fps"],
        "streams_at_sample_fps": round(s["analysed_fps"] / cfg["model"]["sample_fps"], 1),
        "motion_gate_skipped_pct": round(100 * s["frames_gated"] / max(s["frames_analysed"], 1), 1),
        "frames_to_vlm_pct": 0.0, "model": s["model"], "imgsz": s["imgsz"], "device": s["device"],
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "cpu": platform.processor(),
    }
    (ROOT / "runs" / "bench.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
