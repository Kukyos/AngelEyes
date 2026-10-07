"""Admin-written watch rules (D20): "flag if a person raises their hand" -> fixed pose / pair checks.

A rule is compiled once (text-only model call) into a spec built from a closed list of
checks, shown back to the admin, then evaluated on every frame like the other
behaviours. The model's JSON is validated, never run. Thresholds the admin didn't
state come from config.yaml `rules:`.

    python -m angelseye.rules     # self-checks on synthetic keypoints (no network)

Spec:
    {"subject": "person", "checks": [{"check": "hand_up", "side": "either", "above": "head"}],
     "hold_s": 1.0, "summary": "a person raises a hand above their head"}

Checks (person): hand_up {side: either|both|left|right, above: head|shoulder},
bent_over {min_deg}, jump {times, within_s}. Checks (pair): near {max_m}, hand_on_neck.

What geometry can't express but one person visibly shows (clothing, what they hold or do with an
object) compiles to a yes/no question instead (2.R3):
    {"subject": "person", "vision": "Is this person holding a knife?", "summary": "..."}
The question rides on the live describer's regular call (no extra calls) and the rule fires after
rules.vision_yes consecutive yes answers for that person.
"""
import json
import re
import threading
import time
import urllib.request
from collections import deque

import numpy as np

from angelseye import env
from angelseye.behaviours import L_HIP, L_SH, L_WR, NOSE, R_HIP, R_SH, R_WR, Hit, distance, torso_angle

BODY = [NOSE, L_SH, R_SH, L_WR, R_WR, L_HIP, R_HIP]
CHECKS = {
    "person": {
        "hand_up": {"side": ("either", "both", "left", "right"), "above": ("head", "shoulder")},
        "bent_over": {"min_deg": (10, 90)},
        "jump": {"times": (1, 20), "within_s": (1, 60)},
    },
    "pair": {"near": {"max_m": (0.2, 10)}, "hand_on_neck": {}},
}
# D20: no rules on gender, age, identity, faces or a named person
BANNED = re.compile(r"\b(gender|male|female|man|men|woman|women|boy|girl|age|aged|old|older|elderly|young|child|"
                    r"children|kid|kids|teen\w*|face|faces|facial|identity|identify|recogni\w*|named?|race|racial|"
                    r"ethnic\w*|skin colou?r|religio\w*)\b", re.I)

PROMPT = """You turn a CCTV watch rule into JSON for a fixed rule engine. Reply with JSON only.

The engine can only check these things, per tracked person (subject "person"):
- {{"check": "hand_up", "side": "either"|"both"|"left"|"right", "above": "head"|"shoulder"}}  a wrist raised above the head or shoulder
- {{"check": "bent_over", "min_deg": <10-90, optional>}}  upper body leaning forward from vertical
- {{"check": "jump", "times": <1-20>, "within_s": <1-60, optional>}}  jumps this many times
or between two tracked people (subject "pair"):
- {{"check": "near", "max_m": <0.2-10, optional>}}  two people close together
- {{"check": "hand_on_neck"}}  one person's hand at the other's neck or throat (choking, strangling, grabbing the throat)

Person checks in one rule all have to be true at once. A pair rule has exactly one check.
"hold_s" (optional, seconds) is how long it must stay true, only if the rule says so ("for 5 seconds").
Leave optional numbers out unless the rule states them.

Reply {{"subject": ..., "checks": [...], "hold_s": ..., "summary": "<the rule in plain words, as checked>"}}.
If the rule instead needs something visible that these checks can't measure, ask the vision model, which looks
at each person in turn. That covers what a person wears or carries (a mask, a helmet, a red jacket, a bag, a
knife), what they do with an object, and what they do to another person (fighting, hitting, pushing, grabbing,
dragging). A rule about two or more people doing something together is asked about each person
("fighting between two people" -> "Is this person fighting with, hitting or pushing another person?").
Ask about what can be seen, not about intent: name the body parts, the contact and the objects, and give
examples for a kind of object: "a sharp object" -> "Is this person holding a sharp or pointed object such as a
knife, blade, scissors, needle or pen?". Choking or strangling is the pair check "hand_on_neck", not a question.
Reply
{{"subject": "person", "vision": "<one yes/no question about a single person, starting 'Is this person'>",
"summary": "<the rule in plain words>"}}.
If the rule needs anything else (sounds, places, counting people, emotions) or concerns gender, age,
identity, faces or a named person, reply {{"unsupported": "<short reason>"}}.

Rule: {text}"""


def validate(spec):
    """The checked spec, or raises ValueError. Model output crosses a trust boundary: only known keys survive."""
    if not isinstance(spec, dict):
        raise ValueError("spec is not an object")
    subject = spec.get("subject")
    if subject not in CHECKS:
        raise ValueError(f"unknown subject {subject!r}")
    if "vision" in spec:  # a yes/no question for the vision model about one person (2.R3)
        q = " ".join(str(spec["vision"]).split())[:200]
        if subject != "person" or not q.lower().startswith("is this person ") or not q.endswith("?"):
            raise ValueError("a vision rule is one yes/no question about one person")
        m = BANNED.search(q)
        if m:
            raise ValueError(f"questions about gender, age, identity or faces are not allowed ('{m.group(0)}')")
        return {"subject": "person", "vision": q, "checks": [], "hold_s": None,
                "summary": str(spec.get("summary") or q).strip()[:200]}
    checks = spec.get("checks")
    if not isinstance(checks, list) or not 1 <= len(checks) <= 4:
        raise ValueError("needs 1-4 checks")
    out = []
    for c in checks:
        name = c.get("check") if isinstance(c, dict) else None
        allowed = CHECKS[subject].get(name)
        if allowed is None:
            raise ValueError(f"check {name!r} not supported for a {subject}")
        clean = {"check": name}
        for k, rule in allowed.items():
            v = c.get(k)
            if v is None:
                continue
            if isinstance(rule[0], str):
                if v not in rule:
                    raise ValueError(f"{name}.{k} must be one of {rule}")
            else:
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not rule[0] <= v <= rule[1]:
                    raise ValueError(f"{name}.{k} must be a number in {list(rule)}")
            clean[k] = v
        out.append(clean)
    if subject == "pair" and len(out) != 1:
        raise ValueError("a pair rule has exactly one check")
    if sum(c["check"] == "jump" for c in out) > 1:
        raise ValueError("at most one jump check")
    hold = spec.get("hold_s")
    if hold is not None and (isinstance(hold, bool) or not isinstance(hold, (int, float)) or not 0 <= hold <= 600):
        raise ValueError("hold_s must be 0-600")
    hold = hold or None  # the model sends 0 for "not stated" (seen live); 0 would let a one-frame flicker fire
    summary = str(spec.get("summary") or "").strip()[:200]
    return {"subject": subject, "checks": out, "hold_s": hold, "summary": summary}


def compile_rule(text, cfg):
    """Admin text -> {"spec": ...} or {"error": reason}. One text-only call to the VISION_* endpoint."""
    text = " ".join(str(text).split())[:300]
    if not text:
        return {"error": "empty rule"}
    m = BANNED.search(text)
    if m:
        return {"error": f"rules about gender, age, identity, faces or named people are not allowed ('{m.group(0)}')"}
    url, key, model = env("VISION_BASE_URL"), env("VISION_API_KEY"), env("VISION_MODEL")
    if not (url and key and model):
        return {"error": "VISION_BASE_URL / VISION_API_KEY / VISION_MODEL not set in .env"}
    body = {"model": model, "max_tokens": 300, "temperature": 0,
            "messages": [{"role": "user", "content": PROMPT.format(text=text)}]}
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "angelseye"})
    try:
        with urllib.request.urlopen(req, timeout=cfg["rules"]["compile_timeout_s"]) as r:
            reply = json.load(r)["choices"][0]["message"]["content"]
    except urllib.error.URLError as e:  # DNS / no route: the laptop is offline or switched networks
        return {"error": f"can't reach the vision model ({getattr(e, 'reason', e)}); check the internet connection and try again"}
    except Exception as e:  # quota, bad reply
        return {"error": f"model call failed ({e})"}
    return parse_reply(reply)


def parse_reply(reply):
    m = re.search(r"\{.*\}", reply, re.S)
    try:
        data = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return {"error": "the model did not return a rule"}
    if "unsupported" in data:
        return {"error": f"not supported yet: {data['unsupported']}"}
    try:
        return {"spec": validate(data)}
    except ValueError as e:
        return {"error": f"not supported yet: {e}"}


class RuleFeed:
    """Active rules from the hub, re-read on a background thread so the video loop never waits."""

    def __init__(self, hub, poll_s):
        self.url, self.poll_s, self.rules = hub + "/api/rules", poll_s, []
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                with urllib.request.urlopen(self.url, timeout=3) as r:
                    self.rules = [{**x, "spec": validate(x["spec"])} for x in json.load(r)]
            except (OSError, ValueError, KeyError):
                pass  # hub down or a bad row: keep the last good list
            time.sleep(self.poll_s)


# --- evaluation ---------------------------------------------------------------
def kp_ok(kp, idx, min_conf):
    return kp is not None and min(kp[idx, 2]) >= min_conf


def visibility(tr, min_conf):
    """Mean confidence of the visible body keypoints: how well the pose was seen (not a probability)."""
    kp = tr.last.kp
    if kp is None:
        return 0.0
    c = kp[BODY, 2]
    return float(c[c >= min_conf].mean()) if (c >= min_conf).any() else 0.0


class Watch:
    """Active rules over the tracks. `step` returns Hit("rule", ...) like Detectors.step."""

    def __init__(self, cfg):
        self.c = cfg["rules"]
        self.since = {}     # (rule id, ids) -> time first true
        self.jumps = {}     # (rule id, track id) -> {"up": bool, "times": deque}
        self.level = {}     # track id -> deque of (t, shoulder y, scale) for the standing level
        self.yes = {}       # (rule id, track id) -> (consecutive yes answers, model's confidence, image time)

    def vision_answer(self, rid, tid, yes, conf, t):
        """The describer's answer to a vision rule's question about one person."""
        prev = self.yes.get((rid, tid))
        if prev and t <= prev[2]:
            return  # overlapping model calls can finish out of order
        n = prev[0] if prev and t - prev[2] <= self.c["vision_max_age_s"] else 0
        self.yes[(rid, tid)] = (n + 1, conf, t) if yes else (0, conf, t)

    def neck_gap(self, a, b):
        """How far a's nearest visible wrist is from b's neck (mid-shoulders), in b's shoulder widths."""
        ka, kb, mc = a.last.kp, b.last.kp, self.c["min_kpt_conf"]
        if ka is None or not kp_ok(kb, [L_SH, R_SH], mc):
            return None
        neck = kb[[L_SH, R_SH], :2].mean(axis=0)
        sw = float(np.linalg.norm(kb[L_SH, :2] - kb[R_SH, :2])) or 1.0
        gaps = [float(np.linalg.norm(ka[w, :2] - neck)) / sw for w in (L_WR, R_WR) if ka[w, 2] >= mc]
        return min(gaps) if gaps else None

    def hand_up(self, tr, chk):
        kp, mc = tr.last.kp, self.c["min_kpt_conf"]
        if not kp_ok(kp, [L_SH, R_SH], mc):
            return None
        if chk.get("above", "head") == "head":
            ref = kp[NOSE, 1] if kp[NOSE, 2] >= mc else kp[[L_SH, R_SH], 1].min() - 0.15 * tr.last.h
        else:
            ref = kp[[L_SH, R_SH], 1].min()
        up = {s: kp[w, 2] >= mc and kp[w, 1] < ref for s, w in (("left", L_WR), ("right", R_WR))}
        side = chk.get("side", "either")
        ok = (up["left"] and up["right"]) if side == "both" else (up["left"] or up["right"]) if side == "either" else up[side]
        return {"wrists_up": [s for s in ("left", "right") if up[s]]} if ok else None

    def bent_over(self, tr, chk):
        ang = torso_angle(tr.last.kp, self.c["min_kpt_conf"])
        if ang is None or ang < chk.get("min_deg", self.c["bend_deg"]):
            return None
        return {"torso_deg": round(ang, 1)}

    def shoulder_rise(self, tr, t):
        """How far the shoulders sit above the person's standing level, in torso lengths (shoulder width without hips)."""
        kp, mc = tr.last.kp, self.c["min_kpt_conf"]
        if not kp_ok(kp, [L_SH, R_SH], mc):
            return None
        y = kp[[L_SH, R_SH], 1].mean()
        if kp_ok(kp, [L_HIP, R_HIP], mc):
            scale = abs(kp[[L_HIP, R_HIP], 1].mean() - y)
        else:
            scale = abs(kp[L_SH, 0] - kp[R_SH, 0])
        if scale < 5:
            return None
        hist = self.level.setdefault(tr.id, deque())
        if not hist or hist[-1][0] != t:
            hist.append((t, y, scale))
        while hist[0][0] < t - self.c["jump_base_s"]:
            hist.popleft()
        if hist[-1][0] - hist[0][0] < self.c["jump_base_s"] / 2:
            return None  # not watched long enough to know where standing is
        base = np.percentile([h[1] for h in hist], 80)  # standing = low shoulders (large y); jumps are brief
        return (base - y) / np.median([h[2] for h in hist])

    def jump(self, tr, chk, t, rid):
        st = self.jumps.setdefault((rid, tr.id), {"up": False, "times": deque()})
        rise = self.shoulder_rise(tr, t)
        if rise is not None:
            if not st["up"] and rise >= self.c["jump_rise"]:
                st["up"] = True
                st["times"].append(t)
            elif st["up"] and rise <= self.c["jump_rise"] / 2:
                st["up"] = False
        win = chk.get("within_s", self.c["jump_window_s"])
        while st["times"] and st["times"][0] < t - win:
            st["times"].popleft()
        if len(st["times"]) < chk.get("times", 1):
            return None
        return {"jumps_at_s": [round(x, 2) for x in st["times"]]}

    def step(self, tracks, t, rules):
        hits, seen = [], set()
        mc = self.c["min_kpt_conf"]
        for rule in rules:
            spec, rid = rule["spec"], rule["id"]
            if spec.get("vision"):  # answered by the describer, see vision_answer
                cands = []
                for tr in tracks:
                    n, conf, answered_t = self.yes.get((rid, tr.id), (0, 0, -float("inf")))
                    if n >= self.c["vision_yes"] and t - answered_t <= self.c["vision_max_age_s"]:
                        cands.append(((tr.id,), {"question": spec["vision"], "yes_in_a_row": n}, conf))
            elif spec["subject"] == "pair" and spec["checks"][0]["check"] == "hand_on_neck":
                cands = []
                for a in tracks:
                    for b in tracks:
                        if a is not b:
                            d = self.neck_gap(a, b)
                            if d is not None and d <= self.c["neck_sw"]:
                                cands.append(((a.id, b.id), {"wrist_to_neck_shoulder_widths": round(d, 2)},
                                              min(visibility(a, mc), visibility(b, mc))))
            elif spec["subject"] == "pair":
                max_m = spec["checks"][0].get("max_m", self.c["near_m"])
                cands = []
                for i, a in enumerate(tracks):
                    for b in tracks[i + 1:]:
                        d = distance(a, b, t)
                        if d <= max_m:
                            cands.append(((a.id, b.id), {"distance_m": round(d, 2)},
                                          min(visibility(a, mc), visibility(b, mc))))
            else:
                cands = []
                for tr in tracks:  # every check runs every frame: jump counting needs each frame
                    res = [self.jump(tr, chk, t, rid) if chk["check"] == "jump" else getattr(self, chk["check"])(tr, chk)
                           for chk in spec["checks"]]
                    if all(r is not None for r in res):
                        cands.append(((tr.id,), {k: v for r in res for k, v in r.items()}, visibility(tr, mc)))
            hold = spec.get("hold_s")
            hold = self.c["hold_s"] if hold is None else hold
            for ids, signals, conf in cands:
                key = (rid, ids)
                seen.add(key)
                t0 = self.since.setdefault(key, t)
                if t - t0 < hold:
                    continue
                hits.append(Hit("rule", ids, t0, round(conf, 2), {
                    "rule_id": rid, "rule_text": rule["text"], "spec": spec, "signals": signals,
                    "held_s": round(t - t0, 1),
                    "confidence_is": "self-reported by the vision model" if spec.get("vision") else "keypoint visibility"}))
        for k in list(self.since):
            if k not in seen:
                del self.since[k]
        active_rules = {r["id"] for r in rules}
        active_tracks = {tr.id for tr in tracks}
        for key, (_, _, answered_t) in list(self.yes.items()):
            if key[0] not in active_rules or key[1] not in active_tracks or t - answered_t > self.c["vision_max_age_s"]:
                del self.yes[key]
        return hits


# --- self-check ---------------------------------------------------------------
def demo():
    from angelseye import load_config
    from angelseye.behaviours import EventBook, Obs, Track
    cfg = load_config()

    def pose(wrist_y=330, sh_y=200, dx=0):
        kp = np.zeros((17, 3))
        kp[:, 2] = 0.9
        kp[NOSE, :2] = (320 + dx, 140)
        kp[L_SH, :2], kp[R_SH, :2] = (360 + dx, sh_y), (280 + dx, sh_y)
        kp[L_HIP, :2], kp[R_HIP, :2] = (350 + dx, sh_y + 160), (290 + dx, sh_y + 160)
        kp[L_WR, :2], kp[R_WR, :2] = (370 + dx, wrist_y), (270 + dx, 330)
        return kp

    def run(rules, frames, n_tracks=1):
        w, book, tracks = Watch(cfg), EventBook(), [Track(i + 1, calibrated=False) for i in range(n_tracks)]
        events = []
        for k, f in enumerate(frames):
            t = k * 0.1
            for i, tr in enumerate(tracks):
                kp = f(t, i)
                tr.add(Obs(t, (kp[:, 0].min() - 20, 100, kp[:, 0].max() + 20, 440), kp))
            opened, _ = book.step(t, w.step(tracks, t, rules))
            events += opened
        return events

    hand = {"id": "r1", "text": "raises a hand", "spec": validate({"subject": "person", "checks": [{"check": "hand_up"}]})}
    assert run([hand], [lambda t, i: pose(wrist_y=100)] * 20), "raised hand must fire"
    assert not run([hand], [lambda t, i: pose()] * 20), "arms at the sides must not fire"

    def bounce(n):  # stand 2.5 s, then n jumps of 0.4 s each, 0.6 s apart
        def f(t, i):
            up = any(2.5 + j * 1.0 <= t < 2.9 + j * 1.0 for j in range(n))
            return pose(sh_y=140 if up else 200)
        return [f] * int((2.5 + n + 1) * 10)

    jump3 = {"id": "r2", "text": "jumps three times",
             "spec": validate({"subject": "person", "checks": [{"check": "jump", "times": 3}], "hold_s": 0})}
    assert run([jump3], bounce(3)), "3 jumps must fire"
    assert not run([jump3], bounce(2)), "2 jumps must not fire"

    hand2 = {**hand, "id": "r3", "text": "hand above shoulder",
             "spec": validate({"subject": "person", "checks": [{"check": "hand_up", "above": "shoulder"}]})}
    evs = run([hand, hand2], [lambda t, i: pose(wrist_y=100)] * 20)
    assert sorted(e["series"]["rule_id"] for e in evs) == ["r1", "r3"], "two rules, one person -> two events"

    near = {"id": "r4", "text": "two people close", "spec": validate({"subject": "pair", "checks": [{"check": "near", "max_m": 1.0}]})}
    assert run([near], [lambda t, i: pose(dx=60 * i)] * 20, n_tracks=2), "people 0.3 m apart must fire"
    assert not run([near], [lambda t, i: pose(dx=600 * i)] * 20, n_tracks=2), "people 3 m apart must not fire"

    neck = {"id": "r6", "text": "choking", "spec": validate({"subject": "pair", "checks": [{"check": "hand_on_neck"}]})}
    def grab(t, i):  # person 2 reaches its right wrist to person 1's mid-shoulders
        kp = pose(dx=150 * i)
        if i == 1:
            kp[R_WR, :2] = (320, 205)
        return kp
    assert run([neck], [grab] * 20, n_tracks=2), "a hand at the other's neck must fire"
    assert not run([neck], [lambda t, i: pose(dx=150 * i)] * 20, n_tracks=2), "side by side, hands down must not fire"

    knife = {"id": "r5", "text": "someone holding a knife",
             "spec": validate({"subject": "person", "vision": "Is this person holding a knife?"})}
    w, tr = Watch(cfg), Track(7, calibrated=False)
    tr.add(Obs(0.0, (0, 0, 50, 150), pose()))
    w.vision_answer("r5", 7, True, 0.8, 0.0)
    assert not w.step([tr], 0.0, [knife]), "one yes is not enough"
    w.vision_answer("r5", 7, True, 0.9, 1.0)
    w.step([tr], 1.0, [knife])
    assert w.step([tr], 2.0, [knife]), "two yes in a row fires (after hold_s)"
    w.vision_answer("r5", 7, False, 0.9, 3.0)
    assert not w.step([tr], 3.0, [knife]), "a no resets it"
    for q in ("Is this person a woman?", "knife", "Are these two people fighting"):
        try:
            validate({"subject": "person", "vision": q})
        except ValueError:
            continue
        raise AssertionError(f"accepted vision question {q!r}")

    for bad in ({"subject": "person", "checks": [{"check": "holding", "object": "knife"}]},
                {"subject": "person", "checks": [{"check": "near"}]},
                {"subject": "person", "checks": [{"check": "jump", "times": 500}]},
                {"subject": "crowd", "checks": []}, "rm -rf /"):
        try:
            validate(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad}")
    assert "error" in compile_rule("flag if a woman raises her hand", cfg), "gender rule must be refused"
    assert "error" in compile_rule("flag the man with the red face", cfg)
    assert validate({"subject": "person", "checks": [{"check": "hand_up"}], "hold_s": 0})["hold_s"] is None, \
        "hold_s 0 means the config default"
    assert parse_reply('```json\n{"unsupported": "needs objects"}\n```')["error"].startswith("not supported")
    assert parse_reply('{"subject": "person", "checks": [{"check": "hand_up", "side": "left"}], "summary": "x"}')["spec"]
    assert parse_reply('{"subject": "person", "vision": "Is this person wearing a red jacket?"}')["spec"]["vision"]


if __name__ == "__main__":
    demo()
    print("rules: self-checks passed")
