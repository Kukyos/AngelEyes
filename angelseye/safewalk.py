"""SafeWalk routing engine: A* on OSMnx graph with dynamic edge costs.

Cost = length * (1 + deserted + dark + incident)

- deserted: 0-1 based on rolling people count (0 = busy, 1 = deserted)
- dark: 0-1 based on frame brightness (0 = bright, 1 = dark)
- incident: 0-1 based on recent events near edge (0 = none, 1 = active alert)
- unknown penalty: edges with no camera get a fixed penalty (never "safe")
"""

import pickle
import heapq
import math
from pathlib import Path
from typing import Optional

from angelseye import ROOT

GRAPH_PATH = ROOT / "data" / "street_graph.pkl"
CAMERAS_PATH = ROOT / "data" / "cameras.json"


class SafeWalk:
    def __init__(self, counts: dict = None, brightness: dict = None, events: list = None):
        """
        Args:
            counts: {camera_id: {"count": int, "age_s": float}}
            brightness: {camera_id: {"brightness": float, "age_s": float}}
            events: list of event dicts with "camera", "geo", "type", "t_start"
        """
        with open(GRAPH_PATH, "rb") as f:
            self.G = pickle.load(f)

        import json
        with open(CAMERAS_PATH) as f:
            cams = json.load(f)["cameras"]

        # camera_id -> (edge_u, edge_v, edge_key)
        self.cam_to_edge = {}
        for c in cams:
            if c.get("edge_u") is not None:
                self.cam_to_edge[c["id"]] = (c["edge_u"], c["edge_v"], c["edge_key"])

        # Build edge -> camera mapping
        self.edge_to_cam = {}
        for cam_id, (u, v, k) in self.cam_to_edge.items():
            self.edge_to_cam[(u, v, k)] = cam_id
            self.edge_to_cam[(v, u, k)] = cam_id  # bidirectional

        self.counts = counts or {}
        self.brightness = brightness or {}
        self.events = events or []

        # Config
        self.deserted_threshold = 2.0  # count <= 2 = deserted
        self.bright_threshold = 80.0   # brightness <= 80 = dark
        self.incident_radius_m = 100.0
        self.incident_decay_hours = 2.0
        self.unknown_penalty = 0.5

    def _edge_deserted(self, u, v, k) -> float:
        """0.0 = busy, 1.0 = deserted"""
        cam = self.edge_to_cam.get((u, v, k))
        if not cam:
            return self.unknown_penalty
        data = self.counts.get(cam)
        if not data:
            return self.unknown_penalty
        count = data["count"]
        if count <= self.deserted_threshold:
            return 1.0
        # Linear: 2 -> 1.0, 10+ -> 0.0
        return max(0.0, 1.0 - (count - 2) / 8.0)

    def _edge_dark(self, u, v, k) -> float:
        """0.0 = bright, 1.0 = dark"""
        cam = self.edge_to_cam.get((u, v, k))
        if not cam:
            return self.unknown_penalty
        data = self.brightness.get(cam)
        if not data:
            return self.unknown_penalty
        bright = data["brightness"]
        if bright <= self.bright_threshold:
            return 1.0
        # Linear: 80 -> 1.0, 200+ -> 0.0
        return max(0.0, 1.0 - (bright - 80) / 120.0)

    def _edge_incident(self, u, v, k) -> float:
        """0.0 = no recent incident, 1.0 = active alert nearby"""
        if not self.events:
            return 0.0

        # Get edge midpoint
        mid_u = self.G.nodes[u]
        mid_v = self.G.nodes[v]
        mid_lat = (mid_u["y"] + mid_v["y"]) / 2
        mid_lon = (mid_u["x"] + mid_v["x"]) / 2

        import time
        now = time.time()
        max_score = 0.0

        for ev in self.events:
            if ev.get("type") in ("loitering", "activity"):
                continue  # not an incident
            geo = ev.get("geo")
            if not geo:
                continue
            ev_lat, ev_lon = geo[0], geo[1]
            # Haversine distance
            d = self._haversine(mid_lat, mid_lon, ev_lat, ev_lon)
            if d <= self.incident_radius_m:
                # Decay by time
                try:
                    from datetime import datetime
                    ev_time = datetime.fromisoformat(ev["t_start"]).timestamp()
                    age_h = (now - ev_time) / 3600
                    score = max(0.0, 1.0 - age_h / self.incident_decay_hours)
                    max_score = max(max_score, score)
                except Exception:
                    pass
        return max_score

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2) -> float:
        R = 6371000.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.asin(math.sqrt(a))

    def _edge_cost(self, u, v, k) -> float:
        """Total cost = length * (1 + deserted + dark + incident)"""
        data = self.G.get_edge_data(u, v, k)
        length = data.get("length", 1.0)

        deserted = self._edge_deserted(u, v, k)
        dark = self._edge_dark(u, v, k)
        incident = self._edge_incident(u, v, k)

        multiplier = 1.0 + deserted + dark + incident
        return length * multiplier

    def _heuristic(self, u, v) -> float:
        """Straight-line distance heuristic for A*."""
        n1 = self.G.nodes[u]
        n2 = self.G.nodes[v]
        return self._haversine(n1["y"], n1["x"], n2["y"], n2["x"])

    def route(self, origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
              prefer_safe: bool = True):
        """
        Find route from origin to destination.
        Returns: (fastest_path, safest_path) as lists of (lat, lon) coords.
        """
        # Find nearest nodes
        import osmnx as ox
        orig_node = ox.distance.nearest_nodes(self.G, origin_lon, origin_lat)
        dest_node = ox.distance.nearest_nodes(self.G, dest_lon, dest_lat)

        # Fastest path (length only)
        fastest = nx.astar_path(self.G, orig_node, dest_node, heuristic=self._heuristic, weight="length")

        if not prefer_safe:
            return self._path_to_coords(fastest), None

        # Safest path (dynamic cost)
        def safe_weight(u, v, d):
            # MultiDiGraph: d is dict of key->edge_data
            min_cost = float("inf")
            for k, edata in d.items():
                cost = self._edge_cost(u, v, k)
                if cost < min_cost:
                    min_cost = cost
            return min_cost

        try:
            safest = nx.astar_path(self.G, orig_node, dest_node, heuristic=self._heuristic, weight=safe_weight)
        except nx.NetworkXNoPath:
            safest = fastest

        return self._path_to_coords(fastest), self._path_to_coords(safest)

    def _path_to_coords(self, path) -> list:
        """Convert node path to [(lat, lon), ...]"""
        return [(self.G.nodes[n]["y"], self.G.nodes[n]["x"]) for n in path]

    def heatmap(self) -> dict:
        """Return per-edge heatmap data for visualization."""
        out = {"deserted": [], "dark": [], "incident": [], "total": []}
        for u, v, k in self.G.edges(keys=True):
            data = self.G.get_edge_data(u, v, k)
            mid_u = self.G.nodes[u]
            mid_v = self.G.nodes[v]
            mid = [(mid_u["y"] + mid_v["y"]) / 2, (mid_u["x"] + mid_v["x"]) / 2]

            deserted = self._edge_deserted(u, v, k)
            dark = self._edge_dark(u, v, k)
            incident = self._edge_incident(u, v, k)
            total = 1.0 + deserted + dark + incident

            out["deserted"].append({"coord": mid, "value": deserted})
            out["dark"].append({"coord": mid, "value": dark})
            out["incident"].append({"coord": mid, "value": incident})
            out["total"].append({"coord": mid, "value": total})
        return out


# NetworkX import at module level for weight function
import networkx as nx


def demo():
    """Quick test with Muscatatuck center points."""
    sw = SafeWalk()
    # Hospital G436 to School G328
    fast, safe = sw.route(39.0486, -85.5290, 39.0505, -85.5285)
    print(f"Fastest: {len(fast)} points")
    print(f"Safest: {len(safe) if safe else 0} points")
    hm = sw.heatmap()
    print(f"Heatmap edges: {len(hm['total'])}")


if __name__ == "__main__":
    demo()