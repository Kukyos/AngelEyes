"""SafeWalk routing: shortest path on the street graph with costs from the cameras.

Cost of a street = length * (1 + deserted + dark + incident), each 0..1:
- deserted: people the camera on that street sees (few = 1)
- dark: frame brightness on that camera (dim = 1)
- incident: an alert within incident_radius_m, fading over incident_decay_h
A street with no camera, or a camera with no data, gets unknown_penalty for deserted and dark:
unwatched is never "safe". Thresholds: config.yaml `safewalk`.

The graph is OpenStreetMap's walk network around the MEVA site (data/street_graph.json,
exported once from OSMnx), so routing needs only the standard library.
"""

import heapq
import json
import math
from datetime import datetime

from angelseye import ROOT, load_config

ALERTS_SKIP = ("loitering", "activity")  # watch-level events, not incidents


def haversine(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


class SafeWalk:
    def __init__(self, counts=None, brightness=None, events=None, now=None, cfg=None):
        """counts / brightness: {camera: number}; events: hub event dicts; now: datetime the incidents age against."""
        g = json.loads((ROOT / "data/street_graph.json").read_text())
        self.nodes, self.edges = g["nodes"], g["edges"]
        self.c = (cfg or load_config())["safewalk"]
        cams = json.loads((ROOT / "data/cameras.json").read_text())["cameras"]
        self.edge_cam = {}
        for c in cams:
            if c.get("edge_u") is not None:
                for u, v in ((c["edge_u"], c["edge_v"]), (c["edge_v"], c["edge_u"])):
                    self.edge_cam[(str(u), str(v), c["edge_key"])] = c["id"]
        self.counts, self.brightness = counts or {}, brightness or {}
        now = now or datetime.now()
        self.incidents = []  # (lat, lon, weight 0..1)
        for e in events or []:
            if e.get("type") in ALERTS_SKIP or not e.get("geo"):
                continue
            age_h = (now - datetime.fromisoformat(e["t_start"])).total_seconds() / 3600
            if 0 <= age_h < self.c["incident_decay_h"]:
                self.incidents.append((e["geo"][0], e["geo"][1], 1 - age_h / self.c["incident_decay_h"]))
        for e in self.edges:
            e["cost"], e["why"] = self._cost(e)
        self.adj = {}
        for i, e in enumerate(self.edges):
            self.adj.setdefault(e["u"], []).append(i)

    def _cost(self, e):
        c = self.c
        cam = self.edge_cam.get((e["u"], e["v"], e["k"]))
        n, b = self.counts.get(cam), self.brightness.get(cam)
        deserted = c["unknown_penalty"] if n is None else max(0.0, min(1.0, 1 - (n - c["deserted_count"]) / c["busy_span"]))
        dark = c["unknown_penalty"] if b is None else max(0.0, min(1.0, 1 - (b - c["dark_brightness"]) / c["bright_span"]))
        mid = e["coords"][len(e["coords"]) // 2]
        incident = max([w for la, lo, w in self.incidents if haversine(mid, (la, lo)) <= c["incident_radius_m"]], default=0.0)
        why = {"camera": cam, "people": n, "brightness": b, "deserted": round(deserted, 2), "dark": round(dark, 2),
               "incident": round(incident, 2)}
        return e["length"] * (1 + deserted + dark + incident), why

    def nearest(self, lat, lon):
        return min(self.nodes, key=lambda n: haversine(self.nodes[n], (lat, lon)))

    def path(self, src, dst, weight):
        """Dijkstra; returns the list of edge indexes from src to dst ([] if unreachable)."""
        best, prev, q = {src: 0.0}, {}, [(0.0, src)]
        while q:
            d, n = heapq.heappop(q)
            if n == dst:
                break
            if d > best[n]:
                continue
            for i in self.adj.get(n, []):
                m, nd = self.edges[i]["v"], d + self.edges[i][weight]
                if nd < best.get(m, math.inf):
                    best[m], prev[m] = nd, i
                    heapq.heappush(q, (nd, m))
        out = []
        while dst in prev:
            out.append(prev[dst])
            dst = self.edges[prev[dst]]["u"]
        return out[::-1]

    def line(self, idx):
        pts = []
        for i in idx:
            pts += self.edges[i]["coords"][1 if pts else 0:]
        return pts

    def route(self, o_lat, o_lon, d_lat, d_lon):
        src, dst = self.nearest(o_lat, o_lon), self.nearest(d_lat, d_lon)
        out = {}
        for name, w in (("fastest", "length"), ("safest", "cost")):
            idx = self.path(src, dst, w)
            out[name] = {"coords": self.line(idx), "length_m": round(sum(self.edges[i]["length"] for i in idx), 1),
                         "cameras": sorted({self.edges[i]["why"]["camera"] for i in idx} - {None})}
        return out

    def heatmap(self):
        """Every street once (one direction) with its cost multiplier and the reasons."""
        seen, out = set(), []
        for e in self.edges:
            key = (min(e["u"], e["v"]), max(e["u"], e["v"]), e["k"])
            if key in seen:
                continue
            seen.add(key)
            out.append({"coords": e["coords"], "mult": round(e["cost"] / e["length"], 2) if e["length"] else 1.0,
                        "name": e["name"], **e["why"]})
        return out


if __name__ == "__main__":
    # Self-check: an incident on the fastest route must push the safest route off it.
    sw = SafeWalk()
    o, d = (39.0486, -85.5290), (39.0505, -85.5285)
    r = sw.route(*o, *d)
    assert r["fastest"]["coords"] and r["fastest"]["length_m"] <= r["safest"]["length_m"], r
    mid = r["fastest"]["coords"][len(r["fastest"]["coords"]) // 2]
    ev = {"type": "fall", "geo": mid, "t_start": "2018-03-07T11:00:00"}
    r2 = SafeWalk(events=[ev], now=datetime(2018, 3, 7, 11, 5)).route(*o, *d)
    assert r2["safest"]["coords"] != r["fastest"]["coords"], "incident did not move the safe route"
    assert r2["safest"]["length_m"] >= r2["fastest"]["length_m"]
    old = SafeWalk(events=[ev], now=datetime(2018, 3, 8)).incidents
    assert not old, "incident should have faded"
    print("safewalk ok:", r2["fastest"]["length_m"], "m fastest,", r2["safest"]["length_m"], "m safest with incident;",
          len(sw.heatmap()), "streets")
