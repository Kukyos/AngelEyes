"""Hub: the only thing the engine and the screens share.

    python -m angelseye.hub [--port 8000]

SQLite event store, WebSocket push, media (annotated video, clips, keyframes),
upload-a-video mode, and the web pages (/ site view, /responder phone page).
On start it loads every runs/*/events.json, so finished runs appear without re-running.
"""
import argparse
import asyncio
import json
import re
import time
import os
import sqlite3
import subprocess
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from angelseye import ROOT, env, load_config, rules
from angelseye.safewalk import SafeWalk

RUNS = ROOT / "runs"
WEB = ROOT / "web"
DB = ROOT / "data" / "hub.sqlite"
UPLOADS = ROOT / "data" / "raw" / "uploads"  # raw, unblurred: never under /media
VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".mpg", ".mpeg", ".webm", ".m4v"}
MAX_UPLOAD = 500 * 1024 * 1024


class Evidence(BaseModel):
    keyframes: list[str]
    series: dict


class Event(BaseModel):
    """The event record from docs/ARCHITECTURE.md. No event without who, when and evidence."""
    id: str = Field(min_length=1, max_length=200)
    type: Literal["sos", "following", "loitering", "fall", "sudden_run", "activity", "rule"]
    camera: str = Field(min_length=1, max_length=200)
    track_ids: list[int] = Field(min_length=1)
    t_start: str
    t_end: str
    confidence: float = Field(ge=0, le=1)
    evidence: Evidence
    clip_path: Optional[str] = None
    geo: Optional[list[float]] = Field(default=None, min_length=2, max_length=2)


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    RUNS.mkdir(exist_ok=True)
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, type TEXT NOT NULL, camera TEXT NOT NULL, track_ids TEXT NOT NULL,
            t_start TEXT NOT NULL, t_end TEXT NOT NULL, confidence REAL NOT NULL,
            evidence TEXT NOT NULL, clip_path TEXT, geo TEXT)""")
        con.execute("CREATE TABLE IF NOT EXISTS rules (id TEXT PRIMARY KEY, text TEXT NOT NULL, spec TEXT NOT NULL, created TEXT NOT NULL)")


def upsert(ev: Event):
    with db() as con:
        con.execute("INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (ev.id, ev.type, ev.camera, json.dumps(ev.track_ids), ev.t_start, ev.t_end, ev.confidence,
                     ev.evidence.model_dump_json(), ev.clip_path, json.dumps(ev.geo)))


def row(r):
    d = dict(r)
    for k in ("track_ids", "evidence", "geo"):
        d[k] = json.loads(d[k]) if d[k] else None
    return d


def load_runs():
    n = 0
    for f in RUNS.glob("*/events.json"):
        for e in json.loads(f.read_text())["events"]:
            upsert(Event(**e))
            n += 1
    return n


@asynccontextmanager
async def lifespan(app):
    init_db()
    print(f"hub: loaded {load_runs()} events from {RUNS}")
    yield


app = FastAPI(title="Angel's Eye hub", lifespan=lifespan)
clients: set[WebSocket] = set()
jobs: dict[str, dict] = {}


class Gate:
    """Tunnel traffic (it carries X-Forwarded-For) needs HUB_TOKEN, as ?token= once (sets a cookie) or the cookie.
    Local traffic (the engine, you on localhost) is not asked. No HUB_TOKEN set = no gate."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        token = env("HUB_TOKEN")
        if token and scope["type"] in ("http", "websocket") and any(k == b"x-forwarded-for" for k, _ in scope["headers"]):
            hdr = {k.decode(): v.decode() for k, v in scope["headers"]}
            cookie = dict(c.strip().partition("=")[::2] for c in hdr.get("cookie", "").split(";") if c)
            given = dict(q.partition("=")[::2] for q in scope["query_string"].decode().split("&") if q).get("token")
            if token not in (given, cookie.get("hub_token")):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"text/plain")]})
                    await send({"type": "http.response.body", "body": b"hub token needed: open the link you were given"})
                return
            if given == token and scope["type"] == "http":
                inner_send = send

                async def send(msg):  # noqa: F811
                    if msg["type"] == "http.response.start":
                        msg["headers"] = list(msg["headers"]) + [(b"set-cookie", f"hub_token={token}; Path=/; HttpOnly; Secure; SameSite=Lax".encode())]
                    await inner_send(msg)
        await self.inner(scope, receive, send)


app.add_middleware(Gate)


@app.get("/api/config")
def config():
    return {"cesium_token": env("CESIUM_ION_TOKEN")}


def run_info(d):
    f = d / "events.json"
    if not f.exists():
        return None
    s = json.loads(f.read_text())
    s.pop("events")
    s.update(name=d.name, video_url=f"/media/{d.name}/annotated.mp4")
    return s


@app.get("/api/runs")
def runs():
    return [i for d in sorted(RUNS.iterdir()) if d.is_dir() and (i := run_info(d))]


@app.get("/api/cameras")
def cameras():
    reg = json.loads((ROOT / "data/cameras.json").read_text())
    for c in reg["cameras"]:
        c["run"] = run_info(RUNS / c["id"])
    return reg


@app.get("/api/events")
def events(camera: Optional[str] = None, type: Optional[str] = None):
    q, args = "SELECT * FROM events WHERE 1=1", []
    if camera:
        q, args = q + " AND camera=?", args + [camera]
    if type:
        q, args = q + " AND type=?", args + [type]
    with db() as con:
        return [row(r) for r in con.execute(q + " ORDER BY t_start", args)]


@app.post("/api/events")
async def post_event(ev: Event):
    upsert(ev)
    data = ev.model_dump()
    for ws in list(clients):
        try:
            await ws.send_json(data)
        except Exception:
            clients.discard(ws)
    return {"ok": True}


# --- watch rules (D20): compile -> admin confirms -> engines pick them up ------
class RuleText(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class Rule(RuleText):
    spec: dict


@app.post("/api/rules/compile")
def rule_compile(r: RuleText):
    """Preview only: what the rule compiles to, in plain words. Nothing is saved."""
    return rules.compile_rule(r.text, load_config())


@app.get("/api/rules")
def rule_list():
    with db() as con:
        return [{"id": x["id"], "text": x["text"], "spec": json.loads(x["spec"]), "created": x["created"]}
                for x in con.execute("SELECT * FROM rules ORDER BY created")]


@app.post("/api/rules")
def rule_add(r: Rule):
    try:
        spec = rules.validate(r.spec)
    except ValueError as e:
        raise HTTPException(400, str(e))
    rid = "r" + uuid.uuid4().hex[:6]
    with db() as con:
        con.execute("INSERT INTO rules VALUES (?,?,?,?)", (rid, r.text.strip(), json.dumps(spec),
                                                           time.strftime("%Y-%m-%dT%H:%M:%S")))
    return {"id": rid, "text": r.text.strip(), "spec": spec}


@app.delete("/api/rules/{rid}")
def rule_delete(rid: str):
    with db() as con:
        con.execute("DELETE FROM rules WHERE id=?", (rid,))
    return {"ok": True}


@lru_cache(maxsize=64)
def _tracks(path, mtime, hz):
    frames = {}
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            if d["geo"] is None:
                continue
            k = round(d["t"] * hz)
            frames.setdefault(k, {})[d["id"]] = [d["id"], d["geo"][0], d["geo"][1], d["label"], 1 if d["flags"] else 0]
    return {"hz": hz, "frames": {k: list(v.values()) for k, v in frames.items()}}


@app.get("/api/tracks/{run}")
def tracks(run: str, hz: int = 2):
    p = (RUNS / run / "tracks.jsonl").resolve()
    if RUNS.resolve() not in p.parents or not p.exists():
        raise HTTPException(404, "no tracks for that run")
    return _tracks(str(p), p.stat().st_mtime, max(1, min(hz, 10)))


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    clients.add(sock)
    try:
        while True:
            await sock.receive_text()
    except WebSocketDisconnect:
        clients.discard(sock)


live: dict[str, tuple] = {}  # camera name -> (time, newest annotated JPEG, engine session id, people in view)

# Camera counts for SafeWalk: {camera: {"count": int, "ts": float}}
camera_counts: dict[str, dict] = {}

# Camera brightness for SafeWalk: {camera: {"brightness": float, "ts": float}}
camera_brightness: dict[str, dict] = {}


@app.post("/api/counts/{camera}")
async def push_count(camera: str, request: Request):
    """Engine posts rolling people count for a camera."""
    data = await request.json()
    count = int(data.get("count", 0))
    camera_counts[camera] = {"count": count, "ts": time.time()}
    return {"ok": True}


@app.get("/api/counts")
def get_counts():
    """Rolling 60s people count per camera."""
    now = time.time()
    return {cam: {"count": v["count"], "age_s": round(now - v["ts"], 1)}
            for cam, v in camera_counts.items() if now - v["ts"] < 60}


@app.post("/api/brightness/{camera}")
async def push_brightness(camera: str, request: Request):
    """Engine posts rolling frame brightness (0-255) for a camera."""
    data = await request.json()
    brightness = float(data.get("brightness", 0))
    camera_brightness[camera] = {"brightness": brightness, "ts": time.time()}
    return {"ok": True}


@app.get("/api/brightness")
def get_brightness():
    """Rolling 60s frame brightness per camera."""
    now = time.time()
    return {cam: {"brightness": round(v["brightness"], 1), "age_s": round(now - v["ts"], 1)}
            for cam, v in camera_brightness.items() if now - v["ts"] < 60}


def site_counts(at: datetime):
    """People each recorded site camera sees at `at` (from its tracks), for replaying the MEVA slot."""
    out = {}
    for c in json.loads((ROOT / "data/cameras.json").read_text())["cameras"]:
        info, p = run_info(RUNS / c["id"]), RUNS / c["id"] / "tracks.jsonl"
        if not info or not p.exists():
            continue
        local = (at - datetime.fromisoformat(info["start"])).total_seconds()
        if 0 <= local <= info["duration_s"]:
            d = _tracks(str(p), p.stat().st_mtime, 2)
            out[c["id"]] = len(d["frames"].get(round(local * 2), []))
    return out


@app.get("/api/safewalk")
def safewalk_route(origin_lat: Optional[float] = None, origin_lon: Optional[float] = None,
                   dest_lat: Optional[float] = None, dest_lon: Optional[float] = None, at: Optional[str] = None):
    """Fastest and safest walk between two points, plus every street's cost. `at` (ISO time) replays the
    recorded site at that moment (people from its tracks, incidents aged against it); without it, live data."""
    cfg = load_config()
    max_age = cfg["safewalk"]["live_max_age_s"]
    now = time.time()
    counts = {k: v["count"] for k, v in camera_counts.items() if now - v["ts"] < max_age}
    bright = {k: v["brightness"] for k, v in camera_brightness.items() if now - v["ts"] < max_age}
    try:
        when = datetime.fromisoformat(at) if at else datetime.now()
    except ValueError:
        raise HTTPException(400, "at must be an ISO time")
    if at:
        counts.update(site_counts(when))
    sw = SafeWalk(counts=counts, brightness=bright, events=events(), now=when, cfg=cfg)
    pts = (origin_lat, origin_lon, dest_lat, dest_lon)
    route = sw.route(*pts) if None not in pts else {}  # no points yet: just the street costs
    return {**route, "streets": sw.heatmap(), "incidents": sw.incidents, "at": when.isoformat()}


@app.post("/api/live/{name}")
async def live_push(name: str, request: Request, session: str = ""):
    """The engine (--live) posts its newest annotated frame here: heads already blurred."""
    body = await request.body()
    if not re.fullmatch(r"[\w.-]{1,64}", name) or not body or len(body) > 3_000_000:
        raise HTTPException(400, "bad frame")
    try:  # who is in view right now, sent with the frame so tiles match the picture
        people = json.loads(request.headers.get("x-people") or "[]")
    except ValueError:
        people = []
    live[name] = (time.time(), body, session[:100], people)
    return {"ok": True}


@app.get("/api/live")
def live_list():
    now = time.time()
    return [{"name": k, "age_s": round(now - t, 1), "session": ses, "people": ppl}
            for k, (t, _, ses, ppl) in live.items() if now - t < 10]


def mjpeg(store: dict, name: str, request: Request):
    async def frames():
        sent = None
        while not await request.is_disconnected():
            item = store.get(name)
            if item and item[0] != sent:
                sent = item[0]
                head = f"--f\r\nContent-Type: image/jpeg\r\nContent-Length: {len(item[1])}\r\n\r\n".encode()
                yield head + item[1] + b"\r\n"
            await asyncio.sleep(0.03)
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=f", headers={"Cache-Control": "no-store"})


@app.get("/api/live/{name}/stream")
async def live_stream(name: str, request: Request):
    return mjpeg(live, name, request)


# A teammate's browser webcam (/webcam) posts raw frames here; only the engine on this machine may read them
# back (loopback), so unblurred faces never leave. The engine's annotated, blurred output appears under /api/live.
ingest: dict[str, tuple[float, bytes, str]] = {}
engines: dict[str, dict] = {}  # camera name -> {"proc": Popen, "url": IP camera URL or None for a browser webcam}
NAME_RE = r"[\w.-]{1,64}"


def start_engine(name: str, source: str, url: Optional[str], rotate: int = 0, describe: bool = True,
                 imgsz: Optional[int] = None):
    """One live engine per camera, run by the hub. Browser webcams and IP cameras share the cap."""
    e = engines.get(name)
    if e and e["proc"].poll() is None:
        return
    if sum(x["proc"].poll() is None for x in engines.values()) >= load_config()["hub"]["max_engines"]:
        raise HTTPException(503, "too many cameras running; remove one first")
    port = app.state.port
    UPLOADS.parent.mkdir(parents=True, exist_ok=True)
    engines[name] = {"url": url, "describe": describe, "proc": subprocess.Popen(
        [sys.executable, "-m", "angelseye.engine", source, "--live", "--name", name, "--hub", f"http://127.0.0.1:{port}",
         "--rotate", str(rotate)] + ([] if describe else ["--no-describe"]) + (["--imgsz", str(imgsz)] if imgsz else []),
        cwd=ROOT, stdout=open(UPLOADS.parent / f"cam-{name}.log", "w"), stderr=subprocess.STDOUT)}


def host_only(request: Request):
    if "x-forwarded-for" in request.headers:
        raise HTTPException(403, "only on the host machine (localhost), not through the tunnel")


@app.post("/api/ingest/{name}")
async def ingest_push(name: str, request: Request):
    body = await request.body()
    if not re.fullmatch(NAME_RE, name) or not body or len(body) > 3_000_000:
        raise HTTPException(400, "bad frame")
    ingest[name] = (time.time(), body, "")
    start_engine(name, f"http://127.0.0.1:{app.state.port}/api/ingest/{name}/stream", None)
    return {"ok": True}


class Source(BaseModel):
    name: str
    url: str
    rotate: int = 0  # degrees clockwise; a phone held upright streams sideways


@app.post("/api/sources")
def source_add(src: Source, request: Request):
    """Add an IP camera (e.g. the IP Webcam app: http://PHONE_IP:8080/video). Host only: the hub fetches this URL."""
    host_only(request)
    if not re.fullmatch(NAME_RE, src.name):
        raise HTTPException(400, "Type a name for the camera (letters, digits, - or _, no spaces)")
    if not re.match(r"(https?|rtsp)://\S+$", src.url):
        raise HTTPException(400, "The URL must start with http://, https:// or rtsp://")
    if re.fullmatch(r"https?://[^/]+/?", src.url):  # IP Webcam serves its stream at /video
        src.url = src.url.rstrip("/") + "/video"
    if src.rotate not in (0, 90, 180, 270):
        raise HTTPException(400, "Rotate must be 0, 90, 180 or 270")
    start_engine(src.name, src.url, src.url, src.rotate)
    return {"ok": True}


@app.get("/api/sources")
def source_list():
    return [{"name": n, "url": e["url"], "running": e["proc"].poll() is None} for n, e in engines.items()]


@app.delete("/api/sources/{name}")
def source_remove(name: str, request: Request):
    host_only(request)
    e = engines.pop(name, None)
    if e:
        e["proc"].terminate()
    live.pop(name, None)
    ingest.pop(name, None)
    return {"ok": True}


# --- public livestreams as extra CCTV (World tab). Shown as embeds; analysis only when switched on, since each
# one is an engine on the shared GPU and captions spend vision-model credit.
def stream_reg():
    return json.loads((ROOT / "data/streams.json").read_text(encoding="utf-8"))["streams"]


@app.get("/api/streams")
def stream_list():
    out = []
    for c in stream_reg():
        e = engines.get(c["id"])
        on = bool(e and e["proc"].poll() is None)
        out.append({**c, "analysing": on, "captions": on and e["describe"]})
    return out


class Analyse(BaseModel):
    captions: bool = False  # vision-model activity captions (costs credit); off = tracking, pose and rules only


@app.post("/api/streams/{sid}/analyse")
def stream_analyse(sid: str, a: Analyse, request: Request):
    """Start (or restart with/without captions) the engine on one livestream. Host only: the hub fetches it."""
    host_only(request)
    c = next((x for x in stream_reg() if x["id"] == sid), None)
    if not c:
        raise HTTPException(404, "no such stream")
    try:  # YouTube's HLS address expires after some hours, so resolve it at start time, never store it
        import yt_dlp
        sc = load_config()["streams"]
        h = sc["max_height"]
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                               "format": f"bestvideo[height<={h}]/best[height<={h}]"}) as y:
            hls = y.extract_info(c["url"], download=False)["url"]
    except ImportError:
        raise HTTPException(501, "yt-dlp is not installed (pip install -r requirements.txt)")
    except Exception as e:
        raise HTTPException(502, f"could not open the stream: {str(e)[:200]}")
    e = engines.get(sid)
    if e and e["proc"].poll() is None:
        e["proc"].terminate()
        e["proc"].wait(10)
    start_engine(sid, hls, c["url"], describe=a.captions, imgsz=sc["imgsz"])
    return {"ok": True}


@app.get("/api/ingest/{name}/stream")
async def ingest_stream(name: str, request: Request):
    host_only(request)  # raw, unblurred frames: the engine on this machine only
    return mjpeg(ingest, name, request)


@app.post("/api/upload")
async def upload(file: UploadFile):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in VIDEO_EXT:
        raise HTTPException(400, f"not a video file ({', '.join(sorted(VIDEO_EXT))})")
    job = uuid.uuid4().hex[:8]
    src = UPLOADS / f"{job}{ext}"
    src.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with open(src, "wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD:
                f.close()
                src.unlink()
                raise HTTPException(413, "video larger than 500 MB")
            f.write(chunk)
    name = f"upload-{job}"
    log = open(UPLOADS / f"{job}.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "angelseye.engine", str(src), "--out", str(RUNS / name),
                             "--hub", f"http://127.0.0.1:{app.state.port}", "--describe"],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    jobs[job] = {"proc": proc, "name": name, "file": file.filename}
    return {"job": job, "run": name}


@app.get("/api/jobs/{job}")
def job_status(job: str):
    j = jobs.get(job)
    if not j:
        raise HTTPException(404, "unknown job")
    code = j["proc"].poll()
    status = "running" if code is None else "done" if code == 0 else "failed"
    out = {"job": job, "run": j["name"], "file": j["file"], "status": status}
    if status == "done":
        out["result"] = json.loads((RUNS / j["name"] / "events.json").read_text())
    elif status == "failed":
        out["log"] = (UPLOADS / f"{job}.log").read_text()[-2000:]
    return out


NO_CACHE = {"Cache-Control": "no-store"}  # pages change while we build; never serve a stale one


@app.get("/")
def index():
    return FileResponse(WEB / "index.html", headers=NO_CACHE)


@app.get("/webcam")
def webcam():
    return FileResponse(WEB / "webcam.html", headers=NO_CACHE)


@app.get("/responder")
def responder():
    return FileResponse(WEB / "responder.html", headers=NO_CACHE)


RUNS.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=RUNS), name="media")


def main():
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    app.state.port = a.port
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
