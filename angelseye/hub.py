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
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from angelseye import ROOT, env

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
    type: Literal["sos", "following", "loitering", "fall", "sudden_run", "activity"]
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


live: dict[str, tuple[float, bytes, str]] = {}  # camera name -> (time, newest annotated JPEG, engine session id)

# Camera counts for SafeWalk: {camera: {"count": int, "ts": float}}
camera_counts: dict[str, dict] = {}


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


@app.post("/api/live/{name}")
async def live_push(name: str, request: Request, session: str = ""):
    """The engine (--live) posts its newest annotated frame here: heads already blurred."""
    body = await request.body()
    if not re.fullmatch(r"[\w.-]{1,64}", name) or not body or len(body) > 3_000_000:
        raise HTTPException(400, "bad frame")
    live[name] = (time.time(), body, session[:100])
    return {"ok": True}


@app.get("/api/live")
def live_list():
    now = time.time()
    return [{"name": k, "age_s": round(now - t, 1), "session": ses} for k, (t, _, ses) in live.items() if now - t < 10]


@app.get("/api/live/{name}/stream")
async def live_stream(name: str, request: Request):
    async def frames():
        sent = None
        while not await request.is_disconnected():
            item = live.get(name)
            if item and item[0] != sent:
                sent = item[0]
                head = f"--f\r\nContent-Type: image/jpeg\r\nContent-Length: {len(item[1])}\r\n\r\n".encode()
                yield head + item[1] + b"\r\n"
            await asyncio.sleep(0.03)
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=f", headers={"Cache-Control": "no-store"})


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
