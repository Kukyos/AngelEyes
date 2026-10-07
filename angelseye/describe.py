"""Open-ended activity: what is each labelled person doing, in words.

A vision-language model (OpenAI-compatible endpoint from .env: VISION_BASE_URL,
VISION_API_KEY, VISION_MODEL) sees one composite image: the labelled whole view, plus a
close-up of each person cut from the full-resolution frame, a moment ago and now. The
close-ups are what make far CCTV figures readable. Heads are already blurred and people
are labelled P<id>, so answers use the tracker's IDs. Calls run on a background
thread; the video loop never waits for the model.
"""
import base64
import json
import queue
import re
import threading
import time
import urllib.request

import cv2
import numpy as np

from angelseye import env

PROMPT = (
    "Each row shows one labelled person close up, {gap:g} s ago (left) and now (right). A wider picture on top, if "
    "there is one, is the whole camera view. Faces are blurred on purpose. For each labelled person give two things. "
    "'doing': what they are doing right now: their posture, then what their hands or body are doing, then every object "
    "in their hands, however small, named as specifically as you can see it. Answer 'idle' only if nothing at all is "
    "happening. 'wearing': visible clothing with colours, plus accessories (bag, glasses, watch, cap, lanyard). "
    "Describe only what you can actually see; if you cannot tell what an object is, call it 'an object'. Never "
    "describe what is absent, never guess identity, gender or age. At most 12 words each. Reply with JSON only, one "
    'key per labelled person: {{"P<number>": {{"doing": "<phrase>", "wearing": "<phrase>", "confidence": <0 to 1>}}}}.'
)


def parse(text):
    """The model's reply -> {track_id: (phrase, confidence, wearing)}. Tolerates code fences and prose around the JSON."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    out = {}
    for k, v in data.items():
        tid = re.sub(r"\D", "", str(k))
        if not tid:
            continue
        if isinstance(v, dict):
            phrase, conf = str(v.get("doing", "")).strip(), v.get("confidence", 0.5)
            wearing = str(v.get("wearing") or "").strip().rstrip(".").lower()
        else:
            phrase, conf, wearing = str(v).strip(), 0.5, ""
        try:
            conf = min(max(float(conf), 0.0), 1.0)
        except (TypeError, ValueError):
            conf = 0.5
        if phrase:
            out[int(tid)] = (phrase.rstrip(".").lower(), conf, wearing)
    return out


class Describer:
    def __init__(self, cfg):
        self.c = cfg["describe"]
        self.url = env("VISION_BASE_URL").rstrip("/") + "/chat/completions"
        self.key, self.model = env("VISION_API_KEY"), env("VISION_MODEL")
        self.ok = bool(env("VISION_BASE_URL") and self.key and self.model)
        self.frames = []  # (t, labelled whole view, {track id: close-up})
        self.jobs, self.results = queue.Queue(), queue.Queue()
        self.calls, self.last_sent, self.errors = 0, -1e9, 0
        self.prompt_tokens = self.completion_tokens = 0
        self.cost = 0.0  # as reported by the provider (usage.total_cost), when it reports one
        for _ in range(self.c["max_in_flight"] if self.ok else 0):
            threading.Thread(target=self._worker, daemon=True).start()

    def add_frame(self, t, context, crops):
        """Keep recent samples spaced frame_gap_s apart: the labelled whole view and per-person close-ups."""
        if not self.frames or t - self.frames[-1][0] >= self.c["frame_gap_s"]:
            self.frames.append((t, context, crops))
            self.frames = self.frames[-2:]

    def composite(self):
        """Whole view on top (only with 2+ people), then one row per person: close-up a moment ago | close-up now."""
        (_, _, before), (_, context, now) = self.frames[0], self.frames[-1]
        cw, ch = self.c["context_w"], self.c["crop_h"]
        rows = []
        if len(now) > 1:  # ponytail: one person's padded close-up carries the detail; the view is only there to tell people apart
            rows.append(cv2.resize(context, (cw, int(context.shape[0] * cw / context.shape[1])), interpolation=cv2.INTER_AREA))
        for cid in list(now)[:self.c["max_people"]]:
            pair = [c for c in (before.get(cid), now[cid]) if c is not None]
            row = np.hstack([cv2.resize(c, (max(1, int(c.shape[1] * ch / c.shape[0])), ch)) for c in pair])
            row = row[:, :cw] if row.shape[1] > cw else np.hstack([row, np.zeros((ch, cw - row.shape[1], 3), np.uint8)])
            cv2.rectangle(row, (0, 0), (64, 30), (255, 255, 255), -1)
            cv2.putText(row, f"P{cid}", (6, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
            rows.append(row)
        return np.vstack(rows)

    def maybe_send(self, t, urgent=False):
        """Ask the model about the newest sample, at most every interval_s (sooner when something changed)."""
        if not self.ok or self.jobs.unfinished_tasks >= self.c["max_in_flight"] or len(self.frames) < 2 or not self.frames[-1][2]:
            return None
        if t - self.last_sent < (self.c["min_interval_s"] if urgent else self.c["interval_s"]):
            return None
        image = self.composite()
        self.last_sent = t
        self.jobs.put((t, image))
        return image

    def stats(self):
        return {"model": self.model, "calls": self.calls, "errors": self.errors, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "reported_cost_usd": round(self.cost, 6)}

    def poll(self):
        """Finished answers: list of (t_sent, {track_id: (phrase, confidence)})."""
        out = []
        while not self.results.empty():
            out.append(self.results.get())
        return out

    def _worker(self):
        while True:
            t, strip = self.jobs.get()
            try:
                ok, jpg = cv2.imencode(".jpg", strip, [cv2.IMWRITE_JPEG_QUALITY, 80])
                body = {"model": self.model, "max_tokens": 400, "temperature": 0.2, "messages": [{"role": "user", "content": [
                    {"type": "text", "text": PROMPT.format(gap=self.c["frame_gap_s"])},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpg).decode()}}]}]}
                req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers={
                    "Authorization": "Bearer " + self.key, "Content-Type": "application/json", "User-Agent": "angelseye"})
                tic = time.perf_counter()
                with urllib.request.urlopen(req, timeout=self.c["timeout_s"]) as r:
                    reply = json.load(r)
                text = reply["choices"][0]["message"]["content"]
                u = reply.get("usage") or {}
                self.calls += 1
                self.prompt_tokens += u.get("prompt_tokens", 0)
                self.completion_tokens += u.get("completion_tokens", 0)
                self.cost += u.get("total_cost") or 0.0
                self.results.put((t, parse(text), round(time.perf_counter() - tic, 2)))
            except Exception as e:  # network or quota trouble must never stop the video loop
                self.errors += 1
                if self.errors in (1, 10, 100):
                    print(f"describe: model call failed ({e})", flush=True)
            finally:
                self.jobs.task_done()


def demo():
    assert parse('```json\n{"P1": {"doing": "Reading a book.", "confidence": 0.9}}\n```') == {1: ("reading a book", 0.9, "")}
    assert parse('{"P12": "walking"}') == {12: ("walking", 0.5, "")}
    assert parse('{"P2": {"doing": "sitting", "wearing": "Red cap.", "confidence": 1}}') == {2: ("sitting", 1.0, "red cap")}
    assert parse("no idea") == {} and parse('{"P3": {"doing": ""}}') == {}


if __name__ == "__main__":
    demo()
    print("describe: parse self-checks passed")
