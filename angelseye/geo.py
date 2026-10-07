"""Camera geometry: ground homography, ENU <-> lat/lon, and the MEVA camera registry.

`python -m angelseye.geo` rebuilds data/cameras.json from MEVA's published KRTD
camera models (ENU metres around a fixed origin, see meva-data-repo
metadata/camera-models/krtd/README.md).
"""
import json
import math
import re
import urllib.request

import cv2
import numpy as np

from angelseye import ROOT

MEVA_ORIGIN = (39.04977294, -85.52924953)  # lat, lon of the KRTD ENU origin
MEVA_REPO = "https://gitlab.kitware.com/meva/meva-data-repo/-/raw/master/metadata/"
SLOT = "2018-03-07.11-00"
INDOOR = {"G299", "G330"}  # not registered into the shared ENU frame
A, F = 6378137.0, 1 / 298.257223563  # WGS84


def _radii(lat):
    e2 = F * (2 - F)
    s = math.sin(math.radians(lat))
    m = A * (1 - e2) / (1 - e2 * s * s) ** 1.5  # meridian
    n = A / math.sqrt(1 - e2 * s * s)  # prime vertical
    return m, n


def enu_to_latlon(e, n, origin):
    # ponytail: flat tangent plane, cm-accurate over a few km; pyproj if we ever span a city
    m, p = _radii(origin[0])
    return origin[0] + math.degrees(n / m), origin[1] + math.degrees(e / (p * math.cos(math.radians(origin[0]))))


def latlon_to_enu(lat, lon, origin):
    m, p = _radii(origin[0])
    return (math.radians(lon - origin[1]) * p * math.cos(math.radians(origin[0])),
            math.radians(lat - origin[0]) * m)


class Ground:
    """Pixel -> metres on the ground plane, from 4 surveyed pixel<->lat/lon points."""

    def __init__(self, points, origin):
        self.origin = origin
        px = np.float32([p["px"] for p in points])
        en = np.float32([latlon_to_enu(*p["latlon"], origin) for p in points])
        self.H = cv2.getPerspectiveTransform(px, en)
        self.sign = np.sign((self.H @ (*px[0], 1.0))[2])

    def to_metres(self, x, y):
        v = self.H @ (x, y, 1.0)
        if np.sign(v[2]) != self.sign:  # above the horizon: no ground point
            return None
        return float(v[0] / v[2]), float(v[1] / v[2])

    def to_latlon(self, e, n):
        return enu_to_latlon(e, n, self.origin)


def parse_krtd(text):
    v = [float(x) for x in text.split()]
    return np.array(v[:9]).reshape(3, 3), np.array(v[9:18]).reshape(3, 3), np.array(v[18:21])


def meva_camera(cam_id, krtd_text, w=1920, h=1080, max_range=120.0):
    # ponytail: lens distortion (k1 ~0.03) ignored; undistort points if positions look bent at the edges
    K, R, T = parse_krtd(krtd_text)
    C = -R.T @ T
    G = K @ np.column_stack([R[:, 0], R[:, 1], T])  # ground (z=0) -> pixel
    Ginv = np.linalg.inv(G)

    def ground(px, py):
        v = Ginv @ (px, py, 1.0)
        e, n = v[0] / v[2], v[1] / v[2]
        if (R @ (e, n, 0.0) + T)[2] <= 0:  # ground point behind the camera: pixel is above the horizon
            return None
        return (e, n) if math.hypot(e - C[0], n - C[1]) < max_range else None

    def ray_clamped(px, py):
        # where the pixel's ray hits the ground, or max_range along it if it never does
        g = ground(px, py)
        if g:
            return g
        d = R.T @ np.linalg.inv(K) @ (px, py, 1.0)
        d2 = d[:2] / (np.linalg.norm(d[:2]) or 1)
        return C[0] + d2[0] * max_range, C[1] + d2[1] * max_range

    axis = R.T @ (0, 0, 1.0)
    footprint = [ray_clamped(x * w, h) for x in (0, .25, .5, .75, 1)] + \
                [ray_clamped(x * w, .45 * h) for x in (1, .5, 0)]
    pts = []
    for fx, fy in ((.15, .95), (.85, .95), (.85, .7), (.15, .7)):
        g = ground(fx * w, fy * h)
        if g is None:
            raise ValueError(f"{cam_id}: survey pixel {fx},{fy} does not hit the ground")
        pts.append({"px": [round(fx * w), round(fy * h)], "latlon": list(enu_to_latlon(*g, MEVA_ORIGIN))})
    lat, lon = enu_to_latlon(C[0], C[1], MEVA_ORIGIN)
    return {
        "id": cam_id, "lat": lat, "lon": lon, "height_m": round(float(C[2]), 2),
        "heading_deg": round(math.degrees(math.atan2(axis[0], axis[1])) % 360, 1),
        "image_size": [w, h], "points": pts,
        "footprint": [list(enu_to_latlon(e, n, MEVA_ORIGIN)) for e, n in footprint],
    }


def _get(url, cache):
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    return cache.read_text()


def build():
    cache = ROOT / "data/meva/krtd"
    table = _get(MEVA_REPO + "meva-clip-camera-and-time-table.txt", cache / "clip-table.txt")
    cams = []
    for line in table.splitlines():
        clip, _, krtd, camset, *_ = line.split()
        cam = clip.split(".")[-1]
        if not clip.startswith(SLOT) or krtd == "no-camera-model" or camset == "IR" or cam in INDOOR:
            continue
        try:
            c = meva_camera(cam, _get(MEVA_REPO + "camera-models/krtd/" + krtd, cache / krtd))
        except ValueError as e:  # e.g. G639's model has fx 775 vs fy 1326: not usable
            print(f"skipped {cam}: {e}")
            continue
        d, t0 = re.match(r"(\d{4}-\d\d-\d\d)\.(\d\d-\d\d-\d\d)", clip).groups()
        c.update(name=f"{clip.split('.')[-2].title()} {cam}", source="MEVA (CC-BY-4.0)",
                 clip=clip, start=f"{d}T{t0.replace('-', ':')}")
        cams.append(c)
    out = ROOT / "data/cameras.json"
    out.write_text(json.dumps({"site": "MEVA — Muscatatuck Urban Training Center, Indiana",
                               "origin": MEVA_ORIGIN, "cameras": cams}, indent=1))
    for c in cams:
        print(f"{c['id']:5} h={c['height_m']:6.1f} m  heading={c['heading_deg']:5.1f}  {c['lat']:.6f},{c['lon']:.6f}")
    print(f"{len(cams)} cameras -> {out}")


def demo():
    o = MEVA_ORIGIN
    lat, lon = enu_to_latlon(100.0, -50.0, o)
    e, n = latlon_to_enu(lat, lon, o)
    assert abs(e - 100) < 1e-6 and abs(n + 50) < 1e-6
    g = Ground([{"px": p, "latlon": enu_to_latlon(*m, o)} for p, m in
                (([0, 0], (0, 0)), ([100, 0], (10, 0)), ([100, 100], (10, -10)), ([0, 100], (0, -10)))], o)
    assert np.allclose(g.to_metres(50, 50), (5, -5), atol=1e-3)


if __name__ == "__main__":
    demo()
    build()
