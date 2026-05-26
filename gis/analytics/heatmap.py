"""Generate heatmap point clouds for water shortage intensity."""

from __future__ import annotations

import json
import random

import numpy as np
import pandas as pd

from gis.config import ZONES_GEOJSON
from gis.analytics.risk import compute_zone_risks


def _point_in_polygon(lat: float, lon: float, polygon: list) -> bool:
    """Ray casting for [lon, lat] polygon rings."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def build_shortage_heatmap_points(
    risks: pd.DataFrame | None = None,
    points_per_zone: int = 80,
    seed: int = 42,
) -> list[list[float]]:
    """
    Folium HeatMap format: [[lat, lon, weight], ...]
    Weight scales with zone risk_score (shortage intensity).
    """
    if risks is None:
        risks = compute_zone_risks()

    geo = json.loads(ZONES_GEOJSON.read_text(encoding="utf-8"))
    rng = random.Random(seed)
    heat: list[list[float]] = []

    risk_by_zone = dict(zip(risks["zone"], risks["risk_score"]))

    for feat in geo["features"]:
        name = feat["properties"]["name"]
        ring = feat["geometry"]["coordinates"][0]
        score = max(0, risk_by_zone.get(name, 10))
        weight_base = min(1.0, score / 80)

        lats = [c[1] for c in ring]
        lons = [c[0] for c in ring]
        lat_min, lat_max = min(lats), max(lats)
        lon_min, lon_max = min(lons), max(lons)

        added = 0
        attempts = 0
        while added < points_per_zone and attempts < points_per_zone * 20:
            attempts += 1
            lat = rng.uniform(lat_min, lat_max)
            lon = rng.uniform(lon_min, lon_max)
            if _point_in_polygon(lat, lon, ring):
                w = weight_base * rng.uniform(0.6, 1.0)
                heat.append([lat, lon, w])
                added += 1

    return heat


def build_consumption_grid(
    consumption: pd.DataFrame,
    points_per_zone: int = 40,
) -> list[list[float]]:
    """Heatmap weighted by consumption share."""
    geo = json.loads(ZONES_GEOJSON.read_text(encoding="utf-8"))
    share = dict(zip(consumption["zone"], consumption["share_pct"]))
    heat: list[list[float]] = []
    rng = np.random.default_rng(42)

    for feat in geo["features"]:
        name = feat["properties"]["name"]
        ring = feat["geometry"]["coordinates"][0]
        w_base = share.get(name, 10) / 100
        lats = [c[1] for c in ring]
        lons = [c[0] for c in ring]
        for _ in range(points_per_zone):
            lat = rng.uniform(min(lats), max(lats))
            lon = rng.uniform(min(lons), max(lons))
            if _point_in_polygon(lat, lon, ring):
                heat.append([float(lat), float(lon), float(w_base * rng.uniform(0.5, 1))])
    return heat
