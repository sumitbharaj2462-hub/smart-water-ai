"""Geospatial risk scoring from demand, supply, and optional IoT telemetry."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from gis.config import DEFAULT_ZONE_SUPPLY, RISK_CRITICAL, RISK_HIGH, RISK_LOW, RISK_MEDIUM
from gis.zone_mapping import ZONE_DISPLAY_TO_SLUG, ZONE_SLUG_TO_DISPLAY

ROOT = Path(__file__).resolve().parents[2]


def _load_panel() -> pd.DataFrame:
    processed = ROOT / "ml" / "artifacts" / "processed_panel.csv"
    if processed.exists():
        df = pd.read_csv(processed)
        df["date"] = pd.to_datetime(df["date"])
        return df
    raw = pd.read_csv(ROOT / "delhi_water_dataset.csv")
    raw["date"] = pd.to_datetime(raw["date"])
    return raw


def _latest_demand_per_zone(panel: pd.DataFrame) -> dict[str, float]:
    if "zone" in panel.columns:
        latest = panel.sort_values("date").groupby("zone").tail(1)
        return dict(zip(latest["zone"], latest["water_demand"]))
    return {}


def _iot_supply_adjustment() -> dict[str, float]:
    """Optional: reduce effective supply if reservoir level low (from IoT API)."""
    try:
        import urllib.request

        url = "http://localhost:8080/telemetry/zone/central-delhi/summary"
        with urllib.request.urlopen(url, timeout=1) as resp:
            data = json.loads(resp.read())
        # Placeholder factor — extend per zone when IoT API is live
        return {}
    except Exception:
        return {}


def compute_zone_risks(
    supply_overrides: dict[str, float] | None = None,
    demand_overrides: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Returns DataFrame: zone, demand, supply, gap, risk_score, risk_level, lat, lon, weather
    """
    panel = _load_panel()
    demands = _latest_demand_per_zone(panel)
    if demand_overrides:
        demands.update(demand_overrides)

    supply = {**DEFAULT_ZONE_SUPPLY}
    if supply_overrides:
        supply.update(supply_overrides)

    iot_adj = _iot_supply_adjustment()

    zones_geo = _zone_centroids()
    get_weather_bundle = None
    try:
        from weather import get_weather_bundle as _get_weather_bundle

        get_weather_bundle = _get_weather_bundle
    except Exception:
        get_weather_bundle = None
    rows = []
    for zone_name, supply_liters in supply.items():
        demand = demands.get(zone_name, supply_liters * 0.98)
        if zone_name in iot_adj:
            supply_liters *= iot_adj[zone_name]
        gap = demand - supply_liters
        risk = (gap / supply_liters) * 100 if supply_liters > 0 else 0
        lat, lon = zones_geo.get(zone_name, (28.61, 77.21))
        weather_provider = None
        temp_c = None
        humidity_pct = None
        rainfall_next_24h_mm = None
        if get_weather_bundle is not None:
            try:
                bundle = get_weather_bundle(lat, lon, days=3)
                weather_provider = bundle.get("provider")
                cur = bundle.get("current") or {}
                temp_c = float(cur.get("temperature_c")) if cur.get("temperature_c") is not None else None
                humidity_pct = (
                    float(cur.get("humidity_pct")) if cur.get("humidity_pct") is not None else None
                )
                rainfall_next_24h_mm = bundle.get("rainfall_next_24h_mm")
                if rainfall_next_24h_mm is not None:
                    rainfall_next_24h_mm = float(rainfall_next_24h_mm)
            except Exception:
                pass

        if rainfall_next_24h_mm is not None and temp_c is not None:
            if rainfall_next_24h_mm < 5 and temp_c > 35:
                risk += 10
            elif rainfall_next_24h_mm > 20:
                risk -= 5
        risk = max(-50, min(150, risk))
        rows.append(
            {
                "zone": zone_name,
                "slug": ZONE_DISPLAY_TO_SLUG.get(zone_name, zone_name.lower().replace(" ", "-")),
                "demand_liters": demand,
                "supply_liters": supply_liters,
                "gap_liters": gap,
                "risk_score": round(risk, 2),
                "risk_level": risk_level(risk),
                "lat": lat,
                "lon": lon,
                "weather_provider": weather_provider,
                "temperature_c": temp_c,
                "humidity_pct": humidity_pct,
                "rainfall_next_24h_mm": rainfall_next_24h_mm,
            }
        )
    return pd.DataFrame(rows)


def _zone_centroids() -> dict[str, tuple[float, float]]:
    import json as js

    from gis.config import ZONES_GEOJSON

    geo = js.loads(ZONES_GEOJSON.read_text(encoding="utf-8"))
    out = {}
    for feat in geo["features"]:
        name = feat["properties"]["name"]
        coords = feat["geometry"]["coordinates"][0]
        lats = [c[1] for c in coords]
        lons = [c[0] for c in coords]
        out[name] = (sum(lats) / len(lats), sum(lons) / len(lons))
    return out


def risk_level(score: float) -> str:
    if score >= RISK_CRITICAL:
        return "critical"
    if score >= RISK_HIGH:
        return "high"
    if score >= RISK_MEDIUM:
        return "medium"
    return "low"


def risk_color(score: float) -> str:
    level = risk_level(score)
    return {
        "low": "#22c55e",
        "medium": "#eab308",
        "high": "#f97316",
        "critical": "#ef4444",
    }.get(level, "#94a3b8")
