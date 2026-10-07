"""Questions about the footage, answered by the vision model (Airouter, the VISION_* endpoint in .env).

The model sees only what the hub hands it: the events of ONE incident's run or ONE live camera session (never
the whole database, which holds old test runs), the picture on screen (the engine's annotated output, heads
already blurred) and the incident's keyframe. It must answer from that and cite event IDs in [brackets]; cited
IDs that were not in the context are dropped. Questions about gender, age, faces or identity are refused before
any call, with the same list as watch rules.
"""
import base64
import json
import re
import time
import urllib.request

from angelseye import env
from angelseye.rules import BANNED

PROMPT = """You answer questions about CCTV footage for a safety operator. You get a list of the events the system \
detected (one per line, with its ID) and one or more pictures from the same footage. People are labelled P<number>; \
their heads are blurred on purpose.

Rules:
- Answer only from the events and pictures given. If they do not show it, say it is not in this footage.
- Cite the event IDs you rely on in square brackets, e.g. [{example}]. Cite only IDs from the list.
- Never guess identity, gender, age, race or anything about faces; say you do not do that if asked.
- Give times exactly as the event list gives them.
- Plain sentences, at most 80 words.

{scope}

Events:
{events}

Question: {question}"""


def event_line(e, note="", clock=True):
    s = e["evidence"]["series"]
    what = s.get("caption") or s.get("rule_text") or ""
    t = f"{s['video_s'][0]:.1f}-{s['video_s'][1]:.1f} s into the video" + (f", clock {e['t_start'][11:19]}" if clock else "")
    return (f"[{e['id']}] {e['type']} | P{', P'.join(map(str, e['track_ids']))} | {t} | confidence {e['confidence']:.2f}"
            + (f" | {what}" if what else "") + (f" | {note}" if note else ""))


def jpeg_part(data):
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(data).decode()}}


def cites(answer, ids):
    """Cited IDs that were in the context; brackets around anything else are removed from the answer."""
    found = []
    def keep(m):
        i = m.group(1).strip()
        if i in ids:
            found.append(i)
            return m.group(0)
        return ""
    text = re.sub(r"\s?\[([^\]]{1,200})\]", keep, answer)
    return text.strip(), list(dict.fromkeys(found))


def ask(question, scope, events, images, cfg, notes=None, clock=True):
    """events: the event dicts in scope; images: JPEG bytes (blurred). -> {"answer", "cites", ...} or {"error"}."""
    q = " ".join(str(question).split())[:300]
    if not q:
        return {"error": "type a question"}
    m = BANNED.search(q)
    if m:
        return {"answer": f"I don't answer questions about gender, age, faces or identity ('{m.group(0)}'). "
                          "Ask about what people are doing instead, e.g. 'what is P3 doing?'", "cites": [], "refused": True}
    url, key, model = env("VISION_BASE_URL"), env("VISION_API_KEY"), env("VISION_MODEL")
    if not (url and key and model):
        return {"error": "VISION_BASE_URL / VISION_API_KEY / VISION_MODEL not set in .env"}
    c = cfg["ask"]
    events = events[-c["max_events"]:]
    notes = notes or {}
    lines = "\n".join(event_line(e, notes.get(e["id"], ""), clock) for e in events) or "(no events detected in this footage)"
    text = PROMPT.format(example=events[0]["id"] if events else "event-id", scope=scope, events=lines, question=q)
    body = {"model": model, "max_tokens": c["max_tokens"], "temperature": 0,
            "messages": [{"role": "user", "content": [{"type": "text", "text": text}] + [jpeg_part(i) for i in images]}]}
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "angelseye"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=c["timeout_s"]) as r:
            d = json.load(r)
        reply = d["choices"][0]["message"]["content"] or ""
    except urllib.error.HTTPError as e:
        detail = e.read()[:200].decode(errors="replace")
        hint = " (out of credit? top up Airouter)" if e.code in (402, 429) or "credit" in detail.lower() or "balance" in detail.lower() else ""
        return {"error": f"model call failed: HTTP {e.code}{hint}"}
    except Exception as e:  # network, timeout, bad reply
        return {"error": f"model call failed ({e})"}
    answer, cited = cites(reply, {e["id"] for e in events})
    return {"answer": answer, "cites": cited, "model": model, "latency_s": round(time.time() - t, 1),
            "images": len(images), "events": len(events), "cost": (d.get("usage") or {}).get("total_cost")}


if __name__ == "__main__":
    # self-check: invented citations are dropped, real ones kept; banned questions never reach the model
    text, got = cites("P1 fell [fall-02-fall-001] then [made-up-id] got up [fall-02-fall-001].", {"fall-02-fall-001"})
    assert got == ["fall-02-fall-001"] and "made-up-id" not in text and text.count("[fall-02-fall-001]") == 2, (text, got)
    r = ask("is the woman in red ok?", "", [], [], {"ask": {}})
    assert r.get("refused"), r
    print("ask: self-checks passed")
