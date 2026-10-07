"""Tracks in, behaviour hits out. No video, no model: everything here runs on numbers,
so `python -m angelseye.behaviours` self-checks each detector on synthetic tracks.

A *hit* says "this behaviour is true right now for these tracks". `EventBook` turns
hits into events with a start, an end and evidence.
"""
import math
from bisect import bisect_left, bisect_right
from collections import deque
from dataclasses import dataclass, field

import numpy as np

# COCO keypoint indices
NOSE, L_EYE, R_EYE, L_SH, R_SH, L_WR, R_WR, L_HIP, R_HIP = 0, 1, 2, 5, 6, 9, 10, 11, 12


@dataclass
class Obs:
    t: float                 # seconds into the video
    box: tuple               # x1, y1, x2, y2 in source pixels
    kp: np.ndarray = None    # 17 x 3 (x, y, conf)
    pos: tuple = None        # metres on the ground plane, when the camera is calibrated
    edge: bool = False       # box touches the frame edge: the person is cut off, so its shape says little

    @property
    def foot(self):
        return (self.box[0] + self.box[2]) / 2, self.box[3]

    @property
    def h(self):
        return self.box[3] - self.box[1]

    @property
    def w(self):
        return self.box[2] - self.box[0]


@dataclass
class Track:
    id: int
    calibrated: bool
    person_h: float = 1.7
    keep: int = 1500  # observations kept (150 s at 10 fps)
    obs: list = field(default_factory=list)
    ts: list = field(default_factory=list)
    colour: np.ndarray = None
    label: str = ""
    caption: str = ""        # what the vision model says this person is doing
    strong: int = 0          # detections at or above 2 x draw_conf (ghost detections stay low)
    flags: list = field(default_factory=list)
    _heights: deque = field(default_factory=lambda: deque(maxlen=50))

    def add(self, o):
        self.obs.append(o)
        self.ts.append(o.t)
        if len(self.obs) > self.keep * 1.2:
            del self.obs[:-self.keep], self.ts[:-self.keep]
        if o.h > 0:
            self._heights.append(o.h)

    def between(self, t0, t1):
        return self.obs[bisect_left(self.ts, t0):bisect_right(self.ts, t1)]

    @property
    def last(self):
        return self.obs[-1]

    @property
    def scale(self):  # metres per pixel, pixel-space fallback
        return self.person_h / max(float(np.median(self._heights)), 1.0) if self._heights else 0.0

    def path(self, t0, t1, scale=None):
        """times and ground positions (metres) of observations in [t0, t1]."""
        s = scale or self.scale
        ts, xy = [], []
        for o in self.between(t0, t1):
            p = o.pos if self.calibrated else (o.foot[0] * s, o.foot[1] * s)
            if p is not None:
                ts.append(o.t)
                xy.append(p)
        return np.array(ts), np.array(xy).reshape(-1, 2)

    def where(self, t, half=0.3, scale=None):
        ts, xy = self.path(t - half, t + half, scale)
        return xy.mean(axis=0) if len(xy) else None

    def speed(self, t, win=1.0):
        a, b = self.where(t - win), self.where(t)
        return float(np.linalg.norm(b - a) / win) if a is not None and b is not None else 0.0

    def age(self):
        return self.obs[-1].t - self.obs[0].t if self.obs else 0.0


def pair_scale(a, b):
    return (a.scale + b.scale) / 2


def distance(a, b, t):
    s = None if a.calibrated else pair_scale(a, b)
    pa, pb = a.where(t, scale=s), b.where(t, scale=s)
    return float(np.linalg.norm(pa - pb)) if pa is not None and pb is not None else math.inf


def torso_angle(kp, min_conf):
    """Shoulder-hip line from vertical, degrees; None if the keypoints are not visible."""
    if kp is None or min(kp[[L_SH, R_SH, L_HIP, R_HIP], 2]) < min_conf:
        return None
    sh, hp = kp[[L_SH, R_SH], :2].mean(0), kp[[L_HIP, R_HIP], :2].mean(0)
    dx, dy = sh - hp
    return math.degrees(math.atan2(abs(dx), -dy))  # 0 = upright, 90 = lying, >90 = upside down


@dataclass
class Hit:
    type: str
    ids: tuple
    t_start: float
    confidence: float
    series: dict


class Detectors:
    def __init__(self, cfg):
        self.c = cfg
        self.down_since = {}      # track id -> time first seen down (drives the "down" label)
        self._fall = {}
        self.run_since = {}
        self.sos_since = {}
        self.follow_since = {}    # (leader, follower) -> time
        self._next_follow = 0.0
        self._follow_hits = []

    # --- per track -----------------------------------------------------------
    def is_down(self, o):
        c = self.c["fall"]
        ang = torso_angle(o.kp, self.c["sos_pose"]["min_kpt_conf"])
        if ang is not None and ang >= c["torso_angle_deg"]:
            # lying, not bending over: the hips sit low in the box, not up at its top
            hip_y = o.kp[[L_HIP, R_HIP], 1].mean()
            return (o.box[3] - hip_y) / max(o.h, 1) <= c["max_hip_height"]
        return not o.edge and o.w / max(o.h, 1) >= c["wide_ratio"]  # a cut-off box's shape is not evidence

    def is_upright(self, o):
        return o.h / max(o.w, 1) >= self.c["fall"]["upright_ratio"] and not self.is_down(o)

    def fall(self, tr, t):
        """Upright, then down (lying shape, or shrunk to a fraction of the upright height)
        and staying down. Brief flickers back to "up" do not reset the timer."""
        c = self.c["fall"]
        o = tr.last
        look = tr.between(t - c["drop_window_s"] - c["down_s"] - 2, t)
        upright = [p for p in look if self.is_upright(p)]
        tall = max(upright, key=lambda p: p.h) if upright else None
        shrunk = (tall is not None and not o.edge and o.h <= c["max_height_ratio"] * tall.h
                  and o.w / max(o.h, 1) >= c["shrunk_aspect"])
        st = self._fall.setdefault(tr.id, {"since": None, "last": None})
        if self.is_down(o) or shrunk:
            st["last"] = t
            st["since"] = st["since"] if st["since"] is not None else t
        elif st["since"] is not None and t - st["last"] > c["flicker_s"]:
            st["since"] = None
        if st["since"] is None:
            self.down_since.pop(tr.id, None)
            return None
        t0 = self.down_since[tr.id] = st["since"]
        if t - t0 < c["down_s"] or t - st["last"] > c["flicker_s"]:
            return None
        if not any(self.is_down(p) for p in tr.between(t0, t)):
            return None  # shrunk but never lying (crouching, picking something up)
        before = [p for p in upright if t0 - c["drop_window_s"] <= p.t < t0]
        if not before:
            return None
        ref = max(before, key=lambda p: p.h)  # the height it fell from
        if o.h > c["max_height_ratio"] * ref.h and not self.is_down(o):
            return None
        hip = [(round(p.t, 2), round(p.h / max(ref.h, 1), 3)) for p in tr.between(ref.t - 1, t)]
        conf = min(0.95, 0.6 + 0.1 * (t - t0))
        return Hit("fall", (tr.id,), t0, conf, {"box_height_ratio": hip[-60:],
                                                "upright_at_s": round(ref.t, 2)})

    def loitering(self, tr, t):
        c = self.c["loitering"]
        if tr.age() < c["min_s"] or (c["require_calibrated"] and not tr.calibrated):
            return None
        ts, xy = tr.path(t - c["min_s"], t)
        if len(xy) < 5 or ts[0] > t - c["min_s"] + 2:  # needs the whole window observed
            return None
        centre = xy.mean(axis=0)
        r = float(np.max(np.linalg.norm(xy - centre, axis=1)))
        if r > c["radius_m"]:
            return None
        # extend back as long as the person has stayed within the radius
        ts_all, xy_all = tr.path(-1, t)
        inside = np.linalg.norm(xy_all - centre, axis=1) <= c["radius_m"]
        k = len(inside) - 1
        while k > 0 and inside[k - 1]:
            k -= 1
        start = float(ts_all[k])
        dwell = t - start
        return Hit("loitering", (tr.id,), start, min(0.95, 0.5 + dwell / (4 * c["min_s"])),
                   {"dwell_s": round(dwell, 1), "radius_m": round(r, 2),
                    "centre": [round(float(v), 2) for v in centre]})

    def sudden_run(self, tr, t):
        c = self.c["sudden_run"]
        if tr.last.h < self.c["geometry"]["min_box_px"] or tr.last.edge:  # cut-off box: foot point is not the foot
            self.run_since.pop(tr.id, None)
            return None
        sfx = "" if tr.calibrated else "_uncalibrated"
        v = tr.speed(t)
        if v < c["speed_mps" + sfx]:
            self.run_since.pop(tr.id, None)
            return None
        t0 = self.run_since.setdefault(tr.id, t)
        if t - t0 < c["hold_s"]:
            return None
        # speed at x covers [x-1, x], so "before the run" ends one window before the threshold crossing
        prior = [tr.speed(x) for x in np.arange(t0 - 1 - c["prior_s"], t0 - 1 + 1e-6, 0.25) if x - 1.0 >= tr.obs[0].t]
        if len(prior) < 4 or max(prior) > c["prior_max_mps" + sfx] or v < c["jump_ratio"] * max(np.mean(prior), 0.1):
            return None  # was already moving fast (jogging), not seen walking first, or no real jump
        curve = [(round(float(x), 2), round(tr.speed(x), 2)) for x in np.arange(max(tr.obs[0].t + 1, t0 - c["prior_s"]), t + 0.01, 0.25)]
        return Hit("sudden_run", (tr.id,), t0, min(0.95, 0.5 + 0.1 * (v - c["speed_mps" + sfx]) + 0.1 * (t - t0)),
                   {"speed_mps": curve, "peak_mps": round(max(s for _, s in curve), 2)})

    def sos_pose(self, tr, t):
        c = self.c["sos_pose"]
        kp = tr.last.kp
        up = False
        if kp is not None and min(kp[[L_WR, R_WR, L_SH, R_SH], 2]) >= c["min_kpt_conf"]:
            head_y = kp[NOSE, 1] if kp[NOSE, 2] >= c["min_kpt_conf"] else kp[[L_SH, R_SH], 1].min() - 0.15 * tr.last.h
            ang = torso_angle(kp, c["min_kpt_conf"])
            up = kp[L_WR, 1] < head_y and kp[R_WR, 1] < head_y and ang is not None and ang <= c["max_torso_angle_deg"]
            if up and c["require_crossed"]:
                up = (kp[L_WR, 0] - kp[R_WR, 0]) * (kp[L_SH, 0] - kp[R_SH, 0]) < 0
        if not up:
            self.sos_since.pop(tr.id, None)
            return None
        t0 = self.sos_since.setdefault(tr.id, t)
        if t - t0 < c["hold_s"]:
            return None
        return Hit("sos", (tr.id,), t0, min(0.9, 0.55 + 0.1 * (t - t0)),
                   {"mode": "body_pose_both_wrists_above_head", "held_s": round(t - t0, 1)})

    # --- pairs ---------------------------------------------------------------
    def following(self, tracks, t):
        c = self.c["following"]
        if t < self._next_follow:
            return self._follow_hits
        self._next_follow = t + 0.5
        movers = [tr for tr in tracks if tr.last.h >= self.c["geometry"]["min_box_px"]
                  and tr.speed(t) >= c["min_speed_mps"]]
        hits, seen = [], set()
        win = 4.0
        for lead in movers:
            for fol in movers:
                if lead is fol:
                    continue
                key = (lead.id, fol.id)
                s = None if lead.calibrated else pair_scale(lead, fol)
                d = distance(lead, fol, t)
                tf, pf = fol.path(t - win, t, s)
                tl, pl = lead.path(t - win - c["delay_max_s"], t, s)
                if len(tf) < 8 or len(tl) < 8 or not (c["dist_min_m"] <= d <= c["dist_max_m"]):
                    continue
                best = None
                for delay in np.arange(c["delay_min_s"], c["delay_max_s"] + 0.01, 0.5):
                    tq = tf - delay
                    if tq[0] < tl[0]:
                        break
                    lx = np.interp(tq, tl, pl[:, 0])
                    ly = np.interp(tq, tl, pl[:, 1])
                    err = float(np.mean(np.hypot(pf[:, 0] - lx, pf[:, 1] - ly)))
                    if best is None or err < best[1]:
                        best = (float(delay), err)
                if best is None or best[1] > c["path_match_m"]:
                    continue
                seen.add(key)
                t0 = self.follow_since.setdefault(key, t)
                if t - t0 < c["min_s"]:
                    continue
                turns = count_turns(*lead.path(t0 - best[0], t, s), c["turn_deg"])
                if turns < c["min_turns"]:
                    continue
                hits.append(Hit("following", (lead.id, fol.id), t0,
                                min(0.95, 0.55 + 0.03 * (t - t0) + 0.05 * turns),
                                {"delay_s": best[0], "path_error_m": round(best[1], 2),
                                 "distance_m": round(d, 2), "matched_turns": turns,
                                 "duration_s": round(t - t0, 1)}))
        for k in list(self.follow_since):
            if k not in seen:
                del self.follow_since[k]
        self._follow_hits = hits
        return hits

    def step(self, tracks, t):
        hits = []
        for tr in tracks:
            for f in (self.fall, self.loitering, self.sudden_run, self.sos_pose):
                h = f(tr, t)
                if h:
                    hits.append(h)
        hits += self.following(tracks, t)
        return hits


def count_turns(ts, xy, turn_deg, seg_s=1.5, min_move=0.7):
    """Heading changes of at least turn_deg between consecutive path segments."""
    if len(ts) < 2:
        return 0
    heads, t, turns = [], ts[0], 0
    while t + seg_s <= ts[-1]:
        a = np.array([np.interp(t, ts, xy[:, i]) for i in (0, 1)])
        b = np.array([np.interp(t + seg_s, ts, xy[:, i]) for i in (0, 1)])
        if np.linalg.norm(b - a) >= min_move:
            heads.append(math.degrees(math.atan2(*(b - a)[::-1])))
        t += seg_s
    ref = heads[0] if heads else 0
    for h in heads[1:]:
        if abs((h - ref + 180) % 360 - 180) >= turn_deg:
            turns += 1
            ref = h
    return turns


class EventBook:
    """Hits -> events. An event stays open while its hit keeps coming back."""

    def __init__(self, grace_s=1.0, reopen_s=5.0):
        self.grace, self.reopen = grace_s, reopen_s
        self.open = {}
        self.closed = []
        self.reopened = []  # events that came back after closing; the engine extends their record

    def step(self, t, hits):
        opened = []
        self.reopened = []
        for h in hits:
            key = (h.type, h.ids, h.series.get("rule_id"))  # two watch rules on one person are two events
            ev = self.open.get(key)
            if ev is None:  # the same behaviour resuming shortly after it closed continues that event
                ev = next((c for c in reversed(self.closed) if (c["type"], tuple(c["ids"]), c["series"].get("rule_id")) == key
                           and t - c["e"] <= self.reopen), None)
                if ev is not None:
                    self.closed.remove(ev)
                    self.open[key] = ev
                    self.reopened.append(ev)
            if ev is None:
                ev = self.open[key] = {"type": h.type, "ids": list(h.ids), "s": h.t_start,
                                       "e": t, "confidence": h.confidence, "series": h.series, "last": t}
                opened.append(ev)
            ev.update(e=t, last=t, confidence=max(ev["confidence"], h.confidence), series=h.series)
        closed = [k for k, ev in self.open.items() if t - ev["last"] > self.grace]
        done = [self.open.pop(k) for k in closed]
        self.closed += done
        return opened, done

    def flush(self):
        done = list(self.open.values())
        self.closed += done
        self.open.clear()
        return done


# --- self-check --------------------------------------------------------------
def _cfg():
    from angelseye import load_config
    return load_config()


def _track(tid, pts, boxes=None, kps=None, dt=0.1):
    tr = Track(tid, calibrated=True)
    for i, p in enumerate(pts):
        b = boxes[i] if boxes else (0, 0, 40, 170)
        tr.add(Obs(i * dt, b, kps[i] if kps else None, p))
    return tr


# --- why an event fired, in the detector's own terms -------------------------------
def explain(ev, cfg, calibrated):
    """The rule an event broke: each check with what was measured and the config limit, built only from what the
    event's evidence recorded (no re-detection). ok is True/False, or None when the evidence does not carry it.
    -> {"rule", "plain", "checks": [{"check", "measured", "limit", "ok"}], "chart"} or None (activity: no rule)."""
    s, typ = ev["evidence"]["series"], ev["type"]
    t0, t1 = s["video_s"]
    sfx = "" if calibrated else "_uncalibrated"
    unit = "m/s" if calibrated else "≈m/s"
    chk = lambda check, measured, limit, ok: {"check": check, "measured": measured, "limit": limit, "ok": ok}
    if typ == "fall":
        c = cfg["fall"]
        after = [r for t, r in s["box_height_ratio"] if t >= t0]
        low = min(after) if after else None
        down = (chk("Down: height dropped to at most this share of the upright height", f"{low:.0%}", f"≤ {c['max_height_ratio']:.0%}", True)
                if low is not None and low <= c["max_height_ratio"] else
                chk("Down: lying shape (torso angle or box width)", "not recorded in the evidence",
                    f"torso ≥ {c['torso_angle_deg']}° or box {c['wide_ratio']}× wider than tall", None))
        return {"rule": "Fall", "plain": "Someone upright went down within seconds and stayed down.",
                "checks": [chk("Upright first (box taller than wide)", f"at {s['upright_at_s']:.1f} s", f"≥ {c['upright_ratio']}× taller", True),
                           chk("Went down soon after being upright", f"{t0 - s['upright_at_s']:.1f} s", f"≤ {c['drop_window_s']} s",
                               t0 - s["upright_at_s"] <= c["drop_window_s"]),
                           down,
                           chk("Stayed down", f"{t1 - t0:.1f} s", f"≥ {c['down_s']} s", t1 - t0 >= c["down_s"] - 0.05)],
                "chart": {"label": "box height ÷ upright height", "points": s["box_height_ratio"],
                          "limit": c["max_height_ratio"], "below": True, "span": [t0, t1]}}
    if typ == "sudden_run":
        c = cfg["sudden_run"]
        lim, pmax = c["speed_mps" + sfx], c["prior_max_mps" + sfx]
        prior = [v for t, v in s["speed_mps"] if t <= t0 - 1 + 1e-6]
        checks = [chk("Running speed", f"{s['peak_mps']:.1f} {unit}", f"≥ {lim}", s["peak_mps"] >= lim),
                  chk("Kept running", f"{t1 - t0:.1f} s", f"≥ {c['hold_s']} s", t1 - t0 >= c["hold_s"] - 0.05)]
        if prior:  # the engine's 2 s window ends 1 s before the run; the curve keeps its last part
            checks.append(chk("Walking just before (recorded part of the window)", f"{max(prior):.1f} {unit}", f"≤ {pmax}",
                              max(prior) <= pmax))
            ratio = s["peak_mps"] / max(sum(prior) / len(prior), 0.1)
            checks.append(chk("Sudden: peak speed over walking pace", f"{ratio:.1f}×", f"≥ {c['jump_ratio']}×",
                              True if ratio >= c["jump_ratio"] else None))
        plain = "Someone walking broke into a run." + ("" if calibrated else
                 " No camera calibration here, so speeds (≈m/s) are scaled by the person's height in the picture.")
        return {"rule": "Sudden run", "plain": plain, "checks": checks,
                "chart": {"label": f"speed ({unit})", "points": s["speed_mps"], "limit": lim, "below": False, "span": [t0, t1]}}
    if typ == "loitering":
        c = cfg["loitering"]
        return {"rule": "Loitering", "plain": "Someone stayed in one small area for a long time.",
                "checks": [chk("Time in one spot", f"{s['dwell_s']:.0f} s", f"≥ {c['min_s']} s", s["dwell_s"] >= c["min_s"]),
                           chk("Area (radius)", f"{s['radius_m']:.1f} m", f"≤ {c['radius_m']} m", s["radius_m"] <= c["radius_m"])],
                "chart": None}
    if typ == "sos":
        c = cfg["sos_pose"]
        return {"rule": "SOS pose", "plain": "Both wrists held above the head.",
                "checks": [chk("Held", f"{s['held_s']:.1f} s", f"≥ {c['hold_s']} s", s["held_s"] >= c["hold_s"])], "chart": None}
    if typ == "following":
        c = cfg["following"]
        return {"rule": "Following", "plain": "One person retraced another's path a few seconds behind, through turns.",
                "checks": [chk("Same path, seconds later", f"{s['path_error_m']:.1f} m off, {s['delay_s']:.1f} s behind",
                               f"≤ {c['path_match_m']} m, {c['delay_min_s']}–{c['delay_max_s']} s",
                               s["path_error_m"] <= c["path_match_m"] and c["delay_min_s"] <= s["delay_s"] <= c["delay_max_s"]),
                           chk("Distance between them", f"{s['distance_m']:.1f} m", f"{c['dist_min_m']}–{c['dist_max_m']} m",
                               c["dist_min_m"] <= s["distance_m"] <= c["dist_max_m"]),
                           chk("Turns followed", str(s["matched_turns"]), f"≥ {c['min_turns']}", s["matched_turns"] >= c["min_turns"]),
                           chk("Kept up", f"{s['duration_s']:.0f} s", f"≥ {c['min_s']} s", s["duration_s"] >= c["min_s"])],
                "chart": None}
    if typ == "rule":
        hold = s["spec"].get("hold_s")
        hold = cfg["rules"]["hold_s"] if hold is None else hold
        sig = s["signals"]
        if "question" in sig:  # a vision-model rule (2.R3): yes answers in a row from the describer
            need = cfg["rules"]["vision_yes"]
            first = chk("Vision model: " + sig["question"], f"yes {sig['yes_in_a_row']} times in a row", f"≥ {need}",
                        sig["yes_in_a_row"] >= need)
        else:
            show = lambda v: " and ".join(map(str, v)) if isinstance(v, list) else str(v)
            first = chk("Pose measured", "; ".join(f"{k.replace('_', ' ')}: {show(v)}" for k, v in sig.items()) or "—",
                        "the rule's checks", True)
        return {"rule": "Watch rule: " + s["rule_text"], "plain": "Will flag: " + s["spec"].get("summary", s["rule_text"]),
                "checks": [first, chk("Held", f"{s['held_s']:.1f} s", f"≥ {hold} s", s["held_s"] >= hold - 0.05)],
                "chart": None}
    return None


def demo():
    cfg = _cfg()
    # loitering: stays within 1 m for 70 s fires; walking past does not
    rng = np.random.default_rng(0)
    still = [(5 + rng.normal(0, .3), 5 + rng.normal(0, .3)) for _ in range(700)]
    assert Detectors(cfg).loitering(_track(1, still), 69.9)
    walk = [(i * 0.13, 0) for i in range(700)]
    assert not Detectors(cfg).loitering(_track(2, walk), 69.9)

    # sudden run: walk 1.2 m/s then sprint 4 m/s fires; steady jogging at 3 m/s does not
    p, pts = 0.0, []
    for i in range(80):
        p += (0.12 if i < 50 else 0.4)
        pts.append((p, 0))
    d = Detectors(cfg)
    assert any(d.sudden_run(_track(3, pts[:k]), (k - 1) * .1) for k in range(55, 80))
    jog = [(i * 0.3, 0) for i in range(80)]
    d = Detectors(cfg)
    assert not any(d.sudden_run(_track(4, jog[:k]), (k - 1) * .1) for k in range(20, 80))

    slow = {"type": "sudden_run", "evidence": {"series": {"video_s": [5.0, 5.2], "peak_mps": 0.9,
            "speed_mps": [[3.0, 0.3], [4.0, 0.3], [5.0, 0.9]]}}}
    assert explain(slow, cfg, False)["checks"][0]["ok"] is False, "below the speed limit must not pass"

    # fall: upright box then wide box for 2.5 s fires; sitting (squarish, torso upright) does not
    up, wide, sit = (0, 0, 40, 170), (0, 120, 170, 170), (0, 60, 60, 170)
    d = Detectors(cfg)
    boxes = [up] * 30 + [wide] * 30
    assert any(d.fall(_track(5, [(0, 0)] * k, boxes[:k]), (k - 1) * .1) for k in range(31, 60))
    d = Detectors(cfg)
    boxes = [up] * 30 + [sit] * 30
    assert not any(d.fall(_track(6, [(0, 0)] * k, boxes[:k]), (k - 1) * .1) for k in range(31, 60))

    crouch = (0, 80, 75, 170)  # shrunk to 0.53 of standing height but square: never lying
    d = Detectors(cfg)
    boxes = [up] * 30 + [crouch] * 30
    assert not any(d.fall(_track(12, [(0, 0)] * k, boxes[:k]), (k - 1) * .1) for k in range(31, 60))

    bend = np.zeros((17, 3)); bend[:, 2] = 1
    bend[[L_SH, R_SH], :2] = [(10, 60), (12, 62)]; bend[[L_HIP, R_HIP], :2] = [(60, 55), (62, 57)]
    lie = bend.copy(); lie[[L_HIP, R_HIP], 1] = [150, 152]; lie[[L_SH, R_SH], 1] = [148, 150]
    assert not Detectors(cfg).is_down(Obs(0, (0, 40, 90, 200), bend, (0, 0)))   # hips near the top of a tall box
    assert Detectors(cfg).is_down(Obs(0, (0, 100, 200, 200), lie, (0, 0)))
    assert not Detectors(cfg).is_down(Obs(0, (0, 100, 300, 200), None, (0, 0), edge=True))
    assert Detectors(cfg).is_down(Obs(0, (0, 100, 300, 200), None, (0, 0)))

    # following: follower retraces the leader's L-shaped path 3 s later fires;
    # a companion walking alongside does not (too close, no delay)
    def lpath(i):
        s = i * 0.12
        return (s, 0) if s < 6 else (6, s - 6)
    lead = _track(7, [lpath(i) for i in range(300)])
    fol = _track(8, [lpath(i - 30) if i >= 30 else (0, 0) for i in range(300)])
    comp = _track(9, [(lpath(i)[0] + 0.0, lpath(i)[1] + 0.8) for i in range(300)])
    d = Detectors(cfg)
    hits = [h for k in np.arange(4, 29.9, 0.5) for h in d.following([lead, fol], k)]
    assert any(h.ids == (7, 8) for h in hits), "following should fire"
    d = Detectors(cfg)
    hits = [h for k in np.arange(4, 29.9, 0.5) for h in d.following([lead, comp], k)]
    assert not hits, "companions must not fire"

    # sos pose: both wrists above the head for 2 s fires; one hand waving does not
    kp = np.zeros((17, 3))
    kp[:, 2] = 1
    kp[NOSE, :2] = (20, 20)
    kp[[L_SH, R_SH], :2] = [(30, 40), (10, 40)]
    kp[[L_HIP, R_HIP], :2] = [(28, 90), (12, 90)]
    both, one = kp.copy(), kp.copy()
    both[[L_WR, R_WR], :2] = [(30, 5), (10, 5)]
    one[[L_WR, R_WR], :2] = [(30, 5), (10, 80)]
    d = Detectors(cfg)
    assert any(d.sos_pose(_track(10, [(0, 0)] * k, kps=[both] * k), (k - 1) * .1) for k in range(1, 25))
    d = Detectors(cfg)
    assert not any(d.sos_pose(_track(11, [(0, 0)] * k, kps=[one] * k), (k - 1) * .1) for k in range(1, 25))

    # event book: one event per continuous hit, closed after the grace period
    book = EventBook(grace_s=1.0)
    h = Hit("fall", (1,), 0.0, 0.7, {})
    o1, _ = book.step(0.0, [h])
    o2, _ = book.step(0.5, [h])
    _, c = book.step(2.0, [])
    assert len(o1) == 1 and not o2 and len(c) == 1 and c[0]["e"] == 0.5
    o3, _ = book.step(3.0, [h])  # back within reopen_s: same event, not a new one
    assert not o3 and book.reopened and len(book.open) == 1 and not book.closed
    print("behaviours: all self-checks passed")


if __name__ == "__main__":
    demo()
