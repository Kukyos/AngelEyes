"""Video in -> tracked people, behaviour events, annotated video out.

    python -m angelseye.engine VIDEO [--camera G340] [--out runs/G340] [--hub http://127.0.0.1:8000] [--max-s 120]
    python -m angelseye.engine http://PHONE_IP:8080/video --live --name phone --hub http://127.0.0.1:8000

VIDEO is a file, a webcam index (0) or a stream URL (rtsp://, http://). With --camera,
positions come from that camera's ground homography in data/cameras.json; without it
the engine falls back to pixel space scaled by person height.

--live treats the source as a camera: wall-clock time, always the newest frame (no lag
build-up), annotated frames pushed to the hub for the live view, and open-ended
activity descriptions (--describe, see angelseye/describe.py). --describe alone adds
the descriptions to a file run.

Writes to the out dir: annotated.mp4 (heads blurred), events.json, tracks.jsonl,
keyframes/, clips/ (event clips, +-clip_pad_s). With --hub, events are pushed live.
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import threading
import time
import urllib.request
from collections import deque
from pathlib import Path

import cv2
import numpy as np

from angelseye import ROOT, load_config
from angelseye.behaviours import Detectors, EventBook, Obs, Track
from angelseye.geo import Ground
from angelseye.rules import RuleFeed, Watch

SKELETON = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)]
# monochrome overlay: grey = tracked, white = flagged, inverted label = alert
BGR = {"ok": (175, 175, 175), "watch": (255, 255, 255), "alert": (255, 255, 255), "dim": (110, 110, 110)}
BLACK = (0, 0, 0)
NAMES = {"fall": "FALL", "sudden_run": "SUDDEN RUN", "sos": "SOS", "following": "FOLLOWING", "loitering": "LOITERING",
         "rule": "RULE"}
FONT = cv2.FONT_HERSHEY_SIMPLEX
ROTATE = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


def load_camera(cam_id):
    reg = json.loads((ROOT / "data/cameras.json").read_text())
    for c in reg["cameras"]:
        if c["id"] == cam_id:
            return c, tuple(reg["origin"])
    sys.exit(f"camera {cam_id} not in data/cameras.json")


class Writer:
    """H.264 via ffmpeg, so browsers can play it (cv2's mp4v cannot)."""

    def __init__(self, path, w, h, fps, crf):
        self.p = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
             "-r", f"{fps:.3f}", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)], stdin=subprocess.PIPE)

    def write(self, frame):
        self.p.stdin.write(frame.tobytes())

    def close(self):
        self.p.stdin.close()
        self.p.wait()


class LatestFrame:
    """Reads a camera stream on its own thread and keeps only the newest frame, so a slow
    loop never falls behind the camera. Reconnects if the stream drops."""

    def __init__(self, src, cap):
        self.src, self.cap = src, cap
        self.frame, self.n, self.alive = None, 0, True
        self.cond = threading.Condition()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        fails = 0
        while self.alive:
            ok, f = self.cap.read()
            if ok:
                fails = 0
                with self.cond:
                    self.frame, self.n = f, self.n + 1
                    self.cond.notify_all()
                continue
            fails += 1
            if fails > 30:  # ~30 s without a frame: give up
                break
            time.sleep(1)
            self.cap.release()
            self.cap = cv2.VideoCapture(self.src)
        with self.cond:
            self.alive = False
            self.cond.notify_all()

    def next(self, after):
        """The newest frame newer than counter `after`, or (None, after) once the stream is gone."""
        with self.cond:
            self.cond.wait_for(lambda: self.n > after or not self.alive, timeout=35)
            return (self.frame, self.n) if self.n > after else (None, after)


class FramePusher:
    """Sends the newest annotated frame to the hub's live view on its own thread."""

    def __init__(self, url):
        self.url, self.img, self.people = url, None, []
        self.ev = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def push(self, img, people):
        self.img, self.people = img, people
        self.ev.set()

    def _run(self):
        while True:
            self.ev.wait()
            self.ev.clear()
            ok, jpg = cv2.imencode(".jpg", self.img, [cv2.IMWRITE_JPEG_QUALITY, 75])
            try:
                req = urllib.request.Request(self.url, data=jpg.tobytes(), method="POST", headers={
                    "Content-Type": "image/jpeg", "X-People": json.dumps(self.people)})
                urllib.request.urlopen(req, timeout=2).close()
            except OSError:
                time.sleep(1)


def blur_heads(frame, boxes, kps, min_conf):
    """Privacy: blur every detected head. Head keypoints when visible, else the top of the box."""
    H, W = frame.shape[:2]
    for i, (x1, y1, x2, y2) in enumerate(boxes):
        bw, bh = x2 - x1, y2 - y1
        k = kps[i] if kps is not None and len(kps) > i else None
        pts = k[:5][k[:5, 2] >= min_conf, :2] if k is not None else []
        if len(pts):
            cx, cy = pts.mean(0)
            # head size from the spread of face/ear keypoints (close-up faces are big), never below the box rule
            spread = float(np.ptp(pts[:, 0])) if len(pts) > 1 else 0.0
            r = max(0.85 * spread, 0.3 * min(bw, bh * 0.6), 6)
            hx1, hy1, hx2, hy2 = cx - r, cy - 1.35 * r, cx + r, cy + 1.05 * r
        else:
            hx1, hy1, hx2, hy2 = x1, y1 - 0.02 * bh, x2, y1 + 0.28 * bh
        hx1, hy1 = max(int(hx1), 0), max(int(hy1), 0)
        hx2, hy2 = min(int(hx2) + 1, W), min(int(hy2) + 1, H)
        if hx2 - hx1 > 1 and hy2 - hy1 > 1:
            # pixelate to ~6 blocks across whatever the face size, then soften: unreadable at any distance
            bw2, bh2 = hx2 - hx1, hy2 - hy1
            small = cv2.resize(frame[hy1:hy2, hx1:hx2], (max(1, min(6, bw2)), max(1, min(7, bh2))), interpolation=cv2.INTER_AREA)
            frame[hy1:hy2, hx1:hx2] = cv2.GaussianBlur(cv2.resize(small, (bw2, bh2), interpolation=cv2.INTER_LINEAR),
                                                       (0, 0), max(2, bw2 / 12))


def colour_hist(frame, box):
    x1, y1, x2, y2 = box
    h, w = y2 - y1, x2 - x1
    roi = frame[max(int(y1 + .2 * h), 0):int(y1 + .55 * h), max(int(x1 + .2 * w), 0):int(x2 - .2 * w)]
    if roi.size < 12:
        return None
    hist = cv2.calcHist([cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)], [0, 1], None, [12, 8], [0, 180, 0, 256])
    return cv2.normalize(hist, hist)


def text(img, s, org, colour, scale=0.5, bg=(0, 0, 0)):
    (tw, th), base = cv2.getTextSize(s, FONT, scale, 1)
    x, y = int(org[0]), int(org[1])
    cv2.rectangle(img, (x, y - th - base - 2), (x + tw + 6, y + 2), bg, -1)
    cv2.putText(img, s, (x + 3, y - base + 1), FONT, scale, colour, 1, cv2.LINE_AA)


def even(v):
    return int(v) // 2 * 2


def centre_gap(a, b):
    """Distance between two boxes' centres, in units of the first box's height."""
    return np.hypot((a[0] + a[2] - b[0] - b[2]) / 2, (a[1] + a[3] - b[1] - b[3]) / 2) / max(a[3] - a[1], 1)


def same_activity(a, b, threshold):
    """Two descriptions of the same activity, worded differently ("reading a book" / "reading book")."""
    wa, wb = (set(re.findall(r"[a-z]{3,}", s.lower())) for s in (a, b))
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= threshold


class Engine:
    def __init__(self, source, camera=None, out=None, hub=None, max_s=None, cfg=None,
                 live=False, describe=False, name=None, rotate=0):
        self.cfg = cfg or load_config()
        self.source, self.hub, self.max_s, self.live = source, hub and hub.rstrip("/"), max_s, live
        self.rotate = ROTATE.get(rotate)
        self.cam, self.ground = None, None
        if camera:
            self.cam, origin = load_camera(camera)
            self.ground = Ground(self.cam["points"], origin)
        self.name = name or camera or Path(str(source)).stem
        self.out = Path(out or ROOT / "runs" / self.name)
        start = self.cam["start"] if self.cam and not live else dt.datetime.now().isoformat(timespec="seconds")
        self.t0 = dt.datetime.fromisoformat(start)
        self.idp = f"{self.name}-{self.t0:%H%M%S}" if live else self.name  # live sessions never reuse event IDs
        self.tracks, self.alias, self.records = {}, {}, {}
        self.det, self.book = Detectors(self.cfg), EventBook()
        self.watch = Watch(self.cfg)  # admin rules (D20), read from the hub
        self.feed = RuleFeed(self.hub, self.cfg["rules"]["poll_s"]) if self.hub else None
        self._hub_warned = False
        self.describer = None
        if live or describe:
            from angelseye.describe import Describer
            self.describer = Describer(self.cfg)
            if not self.describer.ok:
                print("describe: VISION_BASE_URL / VISION_API_KEY / VISION_MODEL not set in .env; "
                      "running without activity descriptions", file=sys.stderr)
                self.describer = None
        self.activity, self.present, self.missing, self.strips = {}, set(), {}, {}
        self.subject, self.n_subjects, self.answered_t = {}, 0, -1e9  # track id -> (subject number, first seen): survives tracker ID switches
        self.pusher = FramePusher(f"{self.hub}/api/live/{self.name}?session={self.idp}") if live and self.hub else None

    # --- helpers -------------------------------------------------------------
    def iso(self, s):
        return (self.t0 + dt.timedelta(seconds=float(s))).isoformat(timespec="milliseconds")

    def geo_of(self, tr, t):
        if self.ground:
            p = tr.where(t)
            if p is not None:
                return [round(v, 7) for v in self.ground.to_latlon(*p)]
        return [self.cam["lat"], self.cam["lon"]] if self.cam else None

    def post(self, rec):
        if not self.hub:
            return
        try:
            req = urllib.request.Request(self.hub + "/api/events", data=json.dumps(rec).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=3).close()
        except OSError as e:
            if not self._hub_warned:
                print(f"hub unreachable ({e}); events still written to {self.out}", file=sys.stderr)
                self._hub_warned = True

    def repair(self, box, hist, t, pos, busy):
        """A new tracker ID close in time, place and clothing colour to a lost track joins it."""
        c = self.cfg["track_repair"]
        best, best_sim = None, c["min_colour_similarity"]
        for cid, tr in self.tracks.items():
            gap = t - tr.last.t
            if cid in busy or not 0 < gap <= c["gap_s"] or tr.colour is None or hist is None:
                continue
            if self.ground:
                if pos is None or tr.last.pos is None:
                    continue
                d = np.hypot(pos[0] - tr.last.pos[0], pos[1] - tr.last.pos[1])
            else:
                f0, f1 = tr.last.foot, ((box[0] + box[2]) / 2, box[3])
                d = np.hypot(f1[0] - f0[0], f1[1] - f0[1]) * tr.scale
            if d > c["max_dist_m"] + min(tr.speed(tr.last.t), 6.0) * gap:  # a runner covers ground while lost
                continue
            sim = cv2.compareHist(tr.colour, hist, cv2.HISTCMP_CORREL)
            if gap <= c["close_gap_s"] and d <= c["close_dist_m"]:
                sim = max(sim, 1.0 - d)  # near-certain continuation
            if sim >= best_sim:
                best, best_sim = cid, sim
        return best

    # --- frames --------------------------------------------------------------
    def frames(self, cap, fps):
        """(t, frame) pairs: every stride-th frame of a file, or the newest camera frame at sample_fps."""
        sample = self.cfg["model"]["live_sample_fps" if self.live else "sample_fps"]
        if not self.live:
            stride, i = max(1, round(fps / sample)), -1
            while cap.grab():
                i += 1
                if i % stride:
                    continue
                ok, frame = cap.retrieve()
                if not ok:
                    return
                yield i / fps, frame
            return
        src = int(self.source) if str(self.source).isdigit() else str(self.source)
        reader, n, start, nxt = LatestFrame(src, cap), 0, time.monotonic(), time.monotonic()
        try:
            while True:
                wait = nxt - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                nxt = max(nxt + 1 / sample, time.monotonic())
                frame, n = reader.next(n)
                if frame is None:
                    print(f"{self.name}: stream ended", flush=True)
                    return
                yield time.monotonic() - start, frame
        finally:
            reader.alive = False

    # --- the loop ------------------------------------------------------------
    def run(self):
        from ultralytics import YOLO
        import torch

        cfg, mc = self.cfg, self.cfg["model"]
        weights = ROOT / "models" / mc["weights"]
        weights.parent.mkdir(exist_ok=True)
        model = YOLO(str(weights))
        src = int(self.source) if str(self.source).isdigit() else str(self.source)
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            sys.exit(f"cannot open {self.source}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        fps = fps if 1 <= fps <= 120 else 30.0
        out_fps = mc["live_sample_fps"] if self.live else fps / max(1, round(fps / mc["sample_fps"]))
        for d in ("keyframes", "clips"):
            (self.out / d).mkdir(parents=True, exist_ok=True)
        tracks_f = open(self.out / "tracks.jsonl", "w")
        pad = cfg["output"]["clip_pad_s"]
        ring = deque(maxlen=max(1, int(pad * out_fps)))
        clips = {}  # event key -> [Writer, stop_at or None]
        half = torch.cuda.is_available()
        imgsz = mc["live_imgsz" if self.live else "imgsz"]
        tracker = str(ROOT / mc["live_tracker"]) if self.live else mc["tracker"]
        min_conf = cfg["sos_pose"]["min_kpt_conf"]
        full = None
        if self.live:
            print(f"{self.name}: live. Ctrl+C to stop.", flush=True)

        last = (np.zeros((0, 4)), None, [], np.zeros(0))
        prev_small, n, gated, t = None, 0, 0, 0.0
        tic = time.perf_counter()
        try:
            for t, frame in self.frames(cap, fps):
                if self.max_s and t > self.max_s:
                    break
                if self.rotate is not None:
                    frame = cv2.rotate(frame, self.rotate)
                if full is None:  # sizes from the first frame: streams often report none up front
                    H, W = frame.shape[:2]
                    ow = even(cfg["output"]["width"])
                    oh, sx = even(H * ow / W), ow / W
                    full = Writer(self.out / "annotated.mp4", ow, oh, out_fps, cfg["output"]["crf"])
                n += 1
                small = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY)
                gate = mc["motion_gate"]
                if gate and prev_small is not None and cv2.absdiff(small, prev_small).mean() < gate:
                    gated += 1
                else:
                    r = model.track(frame, persist=True, tracker=tracker, imgsz=imgsz, conf=mc["conf"],
                                    classes=[0], quantize=16 if half else None, verbose=False)[0]
                    boxes = r.boxes.xyxy.cpu().numpy() if r.boxes is not None else np.zeros((0, 4))
                    kps = r.keypoints.data.cpu().numpy() if r.keypoints is not None and len(boxes) else None
                    ids = r.boxes.id.int().tolist() if r.boxes is not None and r.boxes.id is not None else [None] * len(boxes)
                    confs = r.boxes.conf.cpu().numpy() if r.boxes is not None else np.zeros(0)
                    last = (boxes, kps, ids, confs)
                    prev_small = small
                boxes, kps, ids, confs = last

                active = self.update_tracks(frame, boxes, kps, ids, confs, t)
                hits = self.det.step(active, t)
                hits += self.watch.step(active, t, self.feed.rules if self.feed else ())
                opened, closed = self.book.step(t, hits)

                if cfg["output"]["head_blur"]:
                    blur_heads(frame, boxes, kps, min_conf)
                img = cv2.resize(frame, (ow, oh), interpolation=cv2.INTER_AREA if ow < W else cv2.INTER_LINEAR)
                plain = self.label_only(img.copy(), sx, boxes, ids, active) if self.describer else None
                self.annotate(img, sx, boxes, kps, ids, confs, active, t)

                for ev in opened:
                    rec = self.open_event(ev, t)
                    w = Writer(self.out / "clips" / f"{rec['id']}.mp4", ow, oh, out_fps, cfg["output"]["crf"])
                    for f in ring:
                        w.write(f)
                    clips[id(ev)] = [w, None, ev]
                for ev in closed:
                    self.close_event(ev)
                    if id(ev) in clips:
                        clips[id(ev)][1] = t + pad
                for ev in self.book.reopened:
                    if id(ev) in clips:  # clip still being written: keep it going
                        clips[id(ev)][1] = None
                for ev in self.book.open.values():  # up to 3 keyframes, 2.5 s apart
                    rec = self.records[id(ev)]
                    kf = rec["evidence"]["keyframes"]
                    if len(kf) < 3 and t >= ev.get("kf_t", -1e9) + 2.5:
                        p = f"{self.out.name}/keyframes/{rec['id']}-{len(kf)}.jpg"
                        cv2.imwrite(str(self.out.parent / p), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        kf.append(p)
                        ev["kf_t"] = t
                if self.describer:
                    self.describe_step(t, frame, plain, img, active)

                full.write(img)
                ring.append(img)
                if self.pusher:
                    self.pusher.push(img, self.people(active, t))
                for key in list(clips):
                    w, stop, _ = clips[key]
                    w.write(img)
                    if stop is not None and t >= stop:
                        w.close()
                        del clips[key]

                for tr in active:
                    o = tr.last
                    tracks_f.write(json.dumps({
                        "t": round(t, 2), "id": tr.id, "box": [int(v) for v in o.box], "label": tr.label,
                        "caption": tr.caption or None, "flags": tr.flags,
                        "pos": [round(v, 2) for v in o.pos] if o.pos else None,
                        "geo": [round(v, 7) for v in self.ground.to_latlon(*o.pos)] if o.pos else None}) + "\n")

                if n % int(out_fps * 15) == 0:
                    el = time.perf_counter() - tic
                    print(f"{self.name}: {t:6.1f}s video, {n / el:5.1f} frames/s, {len(self.tracks)} tracks, "
                          f"{len(self.records)} events", flush=True)
        except KeyboardInterrupt:
            print("stopped; finishing outputs")
        finally:
            for ev in self.book.flush():
                self.close_event(ev)
            for cid in list(self.activity):
                self.end_activity(cid, t)
            for w, _, _ in clips.values():
                w.close()
            if full:
                full.close()
            tracks_f.close()
            cap.release()

        elapsed = time.perf_counter() - tic
        summary = {
            "video": str(self.source), "camera": self.name, "start": self.iso(0), "fps": round(out_fps, 3),
            "duration_s": round(t, 2), "frames_analysed": n, "frames_gated": gated,
            "processing_s": round(elapsed, 2), "analysed_fps": round(n / max(elapsed, 1e-6), 2),
            "model": mc["weights"], "imgsz": imgsz, "device": "cuda" if half else "cpu",
            "vlm": self.describer.stats() if self.describer else None,
            "events": sorted(self.records.values(), key=lambda r: r["t_start"]),
        }
        (self.out / "events.json").write_text(json.dumps(summary, indent=1))
        print(f"{self.name}: done. {n} frames in {elapsed:.1f}s ({summary['analysed_fps']} fps), "
              f"{len(self.records)} events -> {self.out}")
        if self.describer:
            print(f"{self.name}: vision model {summary['vlm']}")
        return summary

    def update_tracks(self, frame, boxes, kps, ids, confs, t):
        seen = set()
        order = sorted(range(len(ids)), key=lambda j: ids[j] not in self.alias)  # known IDs first
        for j in order:
            tid = ids[j]
            if tid is None:
                continue
            b = tuple(float(v) for v in boxes[j])
            foot = ((b[0] + b[2]) / 2, b[3])
            pos = self.ground.to_metres(*foot) if self.ground else None
            hist = None
            cid = self.alias.get(tid)
            if cid is None:
                hist = colour_hist(frame, b)
                cid = self.repair(b, hist, t, pos, seen) or tid
                self.alias[tid] = cid
            if cid in seen:  # repaired track came back under its old ID too; keep them apart
                cid = self.alias[tid] = tid
            tr = self.tracks.get(cid)
            if tr is None:
                tr = self.tracks[cid] = Track(cid, calibrated=self.ground is not None,
                                              person_h=self.cfg["geometry"]["person_height_m"])
            H, W = frame.shape[:2]
            edge = b[0] <= 2 or b[2] >= W - 3 or b[3] >= H - 3
            tr.add(Obs(t, b, kps[j] if kps is not None else None, pos, edge))
            tr.strong += confs[j] >= self.cfg["model"]["draw_conf"] * 2
            if tr.colour is None or len(tr.obs) % 10 == 0:
                tr.colour = hist if hist is not None else colour_hist(frame, b)
            seen.add(cid)
        active = [self.tracks[c] for c in seen]
        lab = self.cfg["labels"]
        sfx = "" if self.ground else "_uncalibrated"
        flags = {}
        for ev in self.book.open.values():
            ids_ = ev["ids"]
            if ev["type"] == "following":
                flags.setdefault(ids_[1], []).append(f"FOLLOWING P{ids_[0]}")
                flags.setdefault(ids_[0], []).append(f"FOLLOWED BY P{ids_[1]}")
            elif ev["type"] == "loitering":
                flags.setdefault(ids_[0], []).append(f"LOITERING {t - ev['s']:.0f}s")
            elif ev["type"] == "rule":
                for i in ids_:
                    flags.setdefault(i, []).append("RULE " + ev["series"]["rule_text"][:28].upper())
            else:
                flags.setdefault(ids_[0], []).append(NAMES[ev["type"]])
        for tr in active:
            v = tr.speed(t)
            if tr.id in self.det.down_since:
                tr.label = "down"
            elif tr.last.edge:  # cut off by the frame (e.g. at a desk): posture unknown, only motion
                tr.label = "still" if v <= lab["standing_max_mps" + sfx] else "moving"
            elif v <= lab["standing_max_mps" + sfx]:
                tr.label = "standing"
            elif v <= lab["walking_max_mps" + sfx]:
                tr.label = "walking"
            else:
                tr.label = "running"
            tr.flags = flags.get(tr.id, [])
        return active

    def open_event(self, ev, t):
        n = sum(1 for r in self.records.values() if r["type"] == ev["type"]) + 1
        eid = f"{self.idp}-{ev['type']}-{n:03d}"
        subject = self.tracks[ev["ids"][-1]]
        rec = {"id": eid, "type": ev["type"], "camera": self.name, "track_ids": ev["ids"],
               "t_start": self.iso(ev["s"]), "t_end": self.iso(ev["e"]), "confidence": round(ev["confidence"], 2),
               "evidence": {"keyframes": [], "series": {**ev["series"], "video_s": [round(ev["s"], 2), round(ev["e"], 2)]}},
               "clip_path": f"{self.out.name}/clips/{eid}.mp4", "geo": self.geo_of(subject, ev["s"])}
        self.records[id(ev)] = rec
        print(f"  EVENT {eid}  P{ev['ids']}  at {ev['s']:.1f}s  conf {rec['confidence']}", flush=True)
        self.post(rec)
        return rec

    def close_event(self, ev):
        rec = self.records.get(id(ev))
        if rec is None:
            return
        rec["t_end"] = self.iso(ev["e"])
        rec["confidence"] = round(ev["confidence"], 2)
        rec["evidence"]["series"] = {**ev["series"], "video_s": [round(ev["s"], 2), round(ev["e"], 2)]}
        self.post(rec)

    # --- open-ended activity (vision model) ----------------------------------
    def describe_step(self, t, frame, plain, img, active):
        """Who is in view (ignoring tracker ID switches) and what each person is doing. Arrivals and departures
        are not logged as events: the live page shows one tile per person in view (people())."""
        c, d = self.cfg["describe"], self.describer
        urgent = False
        for cid in list(self.present):  # someone present but not seen this frame
            last = self.tracks[cid].last.t
            if t - last > 0.5:
                self.missing.setdefault(cid, last)
            else:
                self.missing.pop(cid, None)
        for tr in active:
            if tr.id in self.present or tr.age() < c["enter_s"] or tr.strong < c["enter_strong"]:
                continue
            self.present.add(tr.id)
            urgent = True
            if self.missing:  # a person just lost + a new track now = the tracker switched IDs: the nearest lost one
                old = min(self.missing, key=lambda m: centre_gap(self.tracks[m].last.box, tr.last.box))
                del self.missing[old]
                self.present.discard(old)
                self.subject[tr.id] = self.subject.pop(old)
                tr.caption = self.tracks[old].caption
                rec = self.activity.pop(old, None)
                if rec:
                    rec["track_ids"].append(tr.id)
                    self.activity[tr.id] = rec
            else:
                self.n_subjects += 1
                self.subject[tr.id] = (self.n_subjects, t)
        for cid, last in list(self.missing.items()):
            # out through a frame edge: gone after leave_s; lost mid-frame (turned away, occluded): wait occluded_s
            if t - last > c["leave_s" if self.tracks[cid].last.edge else "occluded_s"]:
                del self.missing[cid]
                self.present.discard(cid)
                self.subject.pop(cid, None)
                self.end_activity(cid, last)
                urgent = True
        crops = {}
        H, W = frame.shape[:2]
        for tr in active:
            if tr.id in self.present:
                x1, y1, x2, y2 = tr.last.box
                px, py = (x2 - x1) * c["crop_pad"], (y2 - y1) * c["crop_pad"]
                crop = frame[max(int(y1 - py), 0):min(int(y2 + py), H), max(int(x1 - px), 0):min(int(x2 + px), W)]
                if crop.size:
                    crops[tr.id] = crop.copy()
        d.add_frame(t, plain, crops)
        if crops:
            questions = [(r["id"], r["spec"]["vision"]) for r in (self.feed.rules if self.feed else [])
                         if r["spec"].get("vision")]
            image = d.maybe_send(t, urgent, questions)
            if image is not None:
                self.strips[t] = image
                for k in sorted(self.strips)[:-4]:
                    del self.strips[k]
        for t_sent, answers, latency in d.poll():
            if t_sent < self.answered_t:  # calls overlap (max_in_flight): an older answer never overwrites a newer one
                continue
            self.answered_t = t_sent
            image = self.strips.get(t_sent)
            for cid, (phrase, conf, rule_answers) in answers.items():
                tr = self.tracks.get(cid)
                for rid, yes in rule_answers.items():
                    self.watch.vision_answer(rid, cid, yes, conf, t_sent)
                if not phrase:
                    continue
                if tr is not None and phrase == "idle":  # nothing happening: not an event; end what they were doing
                    tr.caption = ""
                    if self.activity.get(cid, {}).get("evidence", {}).get("series", {}).get("source") == "vision model":
                        self.end_activity(cid, t_sent)
                elif tr is not None and cid in self.present:
                    self.set_activity(tr, phrase, conf, t_sent, image if image is not None else img, "vision model",
                                      latency)

    def people(self, active, t):
        """One entry per person in view, for the live page's tiles. Lost-but-not-gone people stay, marked."""
        seen = {tr.id for tr in active}
        out = []
        for cid in sorted(self.present if self.describer else seen):
            tr = self.tracks[cid]
            n, since = self.subject.get(cid, (cid, t))
            out.append({"id": cid, "subject": n, "doing": tr.caption or tr.label, "flags": tr.flags,
                        "since": self.iso(since)[11:19], "in_view": cid in seen})
        return out

    def set_activity(self, tr, phrase, conf, t, image, source, latency=None):
        cur = self.activity.get(tr.id)
        prev = cur and cur["evidence"]["series"]["caption"]
        if cur and (prev == phrase or (source == cur["evidence"]["series"]["source"] == "vision model"
                                       and same_activity(prev, phrase, self.cfg["describe"]["same_words"]))):
            cur["t_end"] = self.iso(t)
            cur["evidence"]["series"]["video_s"][1] = round(t, 2)
            cur["confidence"] = round(max(cur["confidence"], conf), 2)
            self.post(cur)
            return
        if cur:
            self.end_activity(tr.id, t)
        n = sum(1 for r in self.records.values() if r["type"] == "activity") + 1
        eid = f"{self.idp}-activity-{n:03d}"
        kf = f"{self.out.name}/keyframes/{eid}.jpg"
        cv2.imwrite(str(self.out.parent / kf), image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        series = {"caption": phrase, "source": source, "video_s": [round(t, 2), round(t, 2)]}
        if source == "vision model":
            series.update(model=self.describer.model, latency_s=latency, confidence_is="self-reported by the model")
        rec = {"id": eid, "type": "activity", "camera": self.name, "track_ids": [tr.id], "t_start": self.iso(t),
               "t_end": self.iso(t), "confidence": round(conf, 2), "evidence": {"keyframes": [kf], "series": series},
               "clip_path": None, "geo": self.geo_of(tr, t)}
        self.records[eid] = rec
        self.activity[tr.id] = rec
        if source == "vision model":
            tr.caption = phrase
        print(f"  ACTIVITY P{tr.id}: {phrase}" + (f"  ({latency}s)" if latency else ""), flush=True)
        self.post(rec)

    def end_activity(self, cid, t):
        rec = self.activity.pop(cid, None)
        if rec:
            rec["t_end"] = self.iso(t)
            rec["evidence"]["series"]["video_s"][1] = round(t, 2)
            self.post(rec)

    # --- drawing ---------------------------------------------------------------
    def label_only(self, img, sx, boxes, ids, active):
        """What the vision model sees: boxes and P<id> tags, no captions to copy back."""
        present = {tr.id for tr in active}
        for j, b in enumerate(boxes):
            cid = self.alias.get(ids[j], ids[j]) if ids[j] is not None else None
            if cid in present:
                x1, y1, x2, y2 = (int(v * sx) for v in b)
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), 2)
                text(img, f"P{cid}", (x1, y1 - 2), BLACK, 0.7, bg=(255, 255, 255))
        return img

    def annotate(self, img, sx, boxes, kps, ids, confs, active, t):
        by_id = {tr.id: tr for tr in active}
        canon = {tid: self.alias.get(tid, tid) for tid in ids if tid is not None}
        alerts = []
        for j, b in enumerate(boxes):
            x1, y1, x2, y2 = (int(v * sx) for v in b)
            tr = by_id.get(canon.get(ids[j]))
            if tr is None:
                if confs[j] >= self.cfg["model"]["draw_conf"]:
                    cv2.rectangle(img, (x1, y1), (x2, y2), BGR["dim"], 1, cv2.LINE_AA)
                continue
            level = "alert" if any(not f.startswith(("LOITERING", "FOLLOWED")) for f in tr.flags) else \
                "watch" if tr.flags else "ok"
            col = BGR[level]
            if kps is not None:
                k = kps[j]
                for a, c in SKELETON:
                    if k[a, 2] > .4 and k[c, 2] > .4:
                        cv2.line(img, (int(k[a, 0] * sx), int(k[a, 1] * sx)), (int(k[c, 0] * sx), int(k[c, 1] * sx)),
                                 BGR["dim"] if level == "ok" else col, 1, cv2.LINE_AA)
            cv2.rectangle(img, (x1, y1), (x2, y2), col, {"ok": 1, "watch": 1, "alert": 2}[level], cv2.LINE_AA)
            text(img, f"P{tr.id} {tr.caption or tr.label}", (x1, y1 - 2), col, 0.4)
            for m, f in enumerate(tr.flags):
                inv = level == "alert"
                text(img, f, (x1, y2 + 15 + 15 * m), BLACK if inv else col, 0.4, bg=col if inv else BLACK)
                if inv:
                    alerts.append(f"{f}  P{tr.id}")
        h, w = img.shape[:2]
        wall = (self.t0 + dt.timedelta(seconds=t)).strftime("%H:%M:%S")
        text(img, f"{self.name}  {wall}", (8, 20), (230, 230, 230), 0.45)
        if alerts:
            cv2.rectangle(img, (0, 0), (w - 1, h - 1), BGR["alert"], 3)
            text(img, "  |  ".join(dict.fromkeys(alerts)), (8, h - 10), BLACK, 0.5, bg=BGR["alert"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="+", help="one or more videos (each gets runs/<name>/), or one camera stream")
    ap.add_argument("--camera", help="camera id in data/cameras.json (enables metres and map positions)")
    ap.add_argument("--out")
    ap.add_argument("--name", help="name for this source (default: camera id or file name)")
    ap.add_argument("--hub", help="hub URL to push events to, e.g. http://127.0.0.1:8000")
    ap.add_argument("--max-s", type=float, help="stop after this many seconds of video")
    ap.add_argument("--live", action="store_true", help="the source is a live camera (implies --describe)")
    ap.add_argument("--describe", action="store_true", help="describe each person's activity with the vision model")
    ap.add_argument("--rotate", type=int, default=0, choices=(0, 90, 180, 270),
                    help="turn each frame clockwise by this much (a phone held upright streams sideways)")
    a = ap.parse_args()
    if len(a.video) > 1 and (a.out or a.camera or a.name or a.live):
        sys.exit("--out, --camera, --name and --live apply to a single source")
    for v in a.video:
        Engine(v, a.camera, a.out, a.hub, a.max_s, live=a.live, describe=a.describe, name=a.name,
               rotate=a.rotate).run()


if __name__ == "__main__":
    main()
