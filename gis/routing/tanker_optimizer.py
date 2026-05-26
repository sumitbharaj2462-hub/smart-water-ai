"""
Tanker route optimization — capacitated nearest-neighbor + 2-opt improvement.
Uses haversine distances; depot → priority sites → high-risk zone stops.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

import pandas as pd

from gis.config import ASSETS_GEOJSON
from gis.analytics.risk import compute_zone_risks


@dataclass
class RouteStop:
    stop_id: str
    name: str
    lat: float
    lon: float
    demand_liters: float
    stop_type: str  # depot | priority | zone


@dataclass
class TankerRoute:
    depot_id: str
    stops: list[RouteStop]
    total_distance_km: float
    total_demand_liters: float
    geometry: list[tuple[float, float]]  # (lat, lon) path


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _distance_matrix(stops: list[RouteStop]) -> list[list[float]]:
    n = len(stops)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                dist[i][j] = haversine_km(
                    stops[i].lat, stops[i].lon, stops[j].lat, stops[j].lon
                )
    return dist


def _route_length(order: list[int], dist: list[list[float]]) -> float:
    total = 0.0
    for i in range(len(order) - 1):
        total += dist[order[i]][order[i + 1]]
    return total


def _two_opt(order: list[int], dist: list[list[float]]) -> list[int]:
    improved = True
    best = order[:]
    while improved:
        improved = False
        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best)):
                if j - i == 1:
                    continue
                new_order = best[:i] + best[i:j][::-1] + best[j:]
                if _route_length(new_order, dist) < _route_length(best, dist):
                    best = new_order
                    improved = True
    return best


def _nearest_neighbor_tsp(dist: list[list[float]], start: int = 0) -> list[int]:
    n = len(dist)
    unvisited = set(range(n)) - {start}
    order = [start]
    current = start
    while unvisited:
        nxt = min(unvisited, key=lambda j: dist[current][j])
        order.append(nxt)
        unvisited.remove(nxt)
        current = nxt
    order.append(start)  # return to depot
    return order


def _load_stops(risks: pd.DataFrame, max_zone_stops: int = 5) -> tuple[list[RouteStop], list[RouteStop]]:
    geo = json.loads(ASSETS_GEOJSON.read_text(encoding="utf-8"))
    depots: list[RouteStop] = []
    deliveries: list[RouteStop] = []

    for feat in geo["features"]:
        props = feat["properties"]
        lon, lat = feat["geometry"]["coordinates"]
        atype = props.get("asset_type", "")
        if atype == "tanker_depot":
            depots.append(
                RouteStop(
                    props["asset_id"],
                    props["name"],
                    lat,
                    lon,
                    0,
                    "depot",
                )
            )
        elif atype in ("priority_site", "reservoir"):
            demand = 50000 if atype == "priority_site" else 30000
            deliveries.append(
                RouteStop(
                    props["asset_id"],
                    props["name"],
                    lat,
                    lon,
                    demand,
                    "priority" if atype == "priority_site" else "zone",
                )
            )

    # High-risk zones as delivery stops (centroids)
    top = risks.nlargest(max_zone_stops, "risk_score")
    for _, row in top.iterrows():
        gap = max(0, row["gap_liters"])
        deliveries.append(
            RouteStop(
                f"ZONE-{row['slug']}",
                f"{row['zone']} (risk {row['risk_score']:.0f}%)",
                row["lat"],
                row["lon"],
                min(gap, 500_000_000) / 1000,
                "zone",
            )
        )

    return depots, deliveries


def optimize_tanker_routes(
    risks: pd.DataFrame | None = None,
    tanker_capacity_liters: float = 100_000,
    num_tankers: int = 2,
) -> list[TankerRoute]:
    """
    Build optimized routes per depot/tanker using TSP heuristic.
    """
    if risks is None:
        risks = compute_zone_risks()

    depots, deliveries = _load_stops(risks)
    if not depots or not deliveries:
        return []

    routes: list[TankerRoute] = []
    # Split deliveries across tankers (round-robin by risk order)
    deliveries_sorted = sorted(
        [d for d in deliveries if d.stop_type == "zone"],
        key=lambda s: -s.demand_liters,
    )
    priority = [d for d in deliveries if d.stop_type == "priority"]

    for t in range(min(num_tankers, len(depots))):
        depot = depots[t % len(depots)]
        assigned = priority[t : len(priority) : num_tankers] if t < len(priority) else []
        zone_chunk = deliveries_sorted[t::num_tankers]
        stops = [depot] + assigned + zone_chunk

        if len(stops) < 2:
            continue

        dist = _distance_matrix(stops)
        order = _nearest_neighbor_tsp(dist, start=0)
        order = _two_opt(order, dist)

        geometry = [(stops[i].lat, stops[i].lon) for i in order]
        total_d = _route_length(order, dist)
        total_demand = sum(s.demand_liters for s in stops[1:])

        routes.append(
            TankerRoute(
                depot_id=depot.stop_id,
                stops=[stops[i] for i in order[:-1]],
                total_distance_km=round(total_d, 2),
                total_demand_liters=total_demand,
                geometry=geometry,
            )
        )

    return routes
