"""Aggregate live platform data for LLM context injection."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from assistant.config import ARTIFACTS, ROOT

ROOT_PATH = ROOT


def build_platform_snapshot() -> dict:
    """Collect risks, forecasts, ML metrics, anomalies, consumption, routes."""
    snapshot: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "city": "Delhi NCR",
        "zones": [
            "North Delhi",
            "South Delhi",
            "East Delhi",
            "West Delhi",
            "Central Delhi",
        ],
    }

    snapshot["zone_risks"] = _safe_zone_risks()
    snapshot["weather"] = _safe_weather()
    snapshot["consumption"] = _safe_consumption()
    snapshot["forecasts"] = _safe_forecasts()
    snapshot["ml_models"] = _safe_ml_metrics()
    snapshot["anomalies"] = _safe_anomalies()
    snapshot["tanker_routes"] = _safe_tanker_routes()
    snapshot["seasonality_trends"] = _safe_analysis_reports()
    snapshot["iot_status"] = _safe_iot_status()
    return snapshot


def snapshot_to_prompt_text(snapshot: dict, max_chars: int = 12000) -> str:
    """Serialize snapshot for LLM system context."""
    text = json.dumps(snapshot, indent=2, default=str)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... [truncated]"
    return text


def _safe_zone_risks() -> list[dict]:
    try:
        from gis.analytics.risk import compute_zone_risks

        df = compute_zone_risks()
        return df.to_dict(orient="records")
    except Exception as e:
        return [{"error": str(e)}]


def _safe_weather() -> dict:
    try:
        from gis.analytics.risk import _zone_centroids
        from weather import get_weather_bundle

        zones = [
            "North Delhi",
            "South Delhi",
            "East Delhi",
            "West Delhi",
            "Central Delhi",
        ]
        centroids = _zone_centroids()
        out = {}
        for zone in zones:
            lat, lon = centroids.get(zone, (28.6139, 77.2090))
            try:
                out[zone] = get_weather_bundle(lat, lon, days=3)
            except Exception as exc:
                out[zone] = {"error": str(exc)}
        return out
    except Exception as e:
        return {"error": str(e)}


def _safe_consumption() -> list[dict]:
    try:
        from gis.analytics.consumption import get_zone_consumption

        return get_zone_consumption(30).to_dict(orient="records")
    except Exception as e:
        return [{"error": str(e)}]


def _safe_forecasts() -> dict:
    out = {}
    try:
        from ml.forecast import forecast_zone

        for zone in [
            "North Delhi",
            "South Delhi",
            "East Delhi",
            "West Delhi",
            "Central Delhi",
        ]:
            try:
                out[zone] = forecast_zone(zone)
            except Exception as exc:
                out[zone] = {"error": str(exc)}
    except Exception as e:
        out["error"] = str(e)
    return out


def _safe_ml_metrics() -> dict:
    path = ARTIFACTS / "training_results.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"note": "Deep learning models not trained yet. Run: python -m ml.train_deep"}


def _safe_anomalies() -> dict:
    summary_path = ARTIFACTS / "analysis" / "anomaly_report.json"
    if summary_path.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    return {"note": "No anomaly report. Train ML models first."}


def _safe_tanker_routes() -> list[dict]:
    try:
        from gis.analytics.risk import compute_zone_risks
        from gis.routing.tanker_optimizer import optimize_tanker_routes

        risks = compute_zone_risks()
        routes = optimize_tanker_routes(risks, num_tankers=2)
        return [
            {
                "depot": r.depot_id,
                "distance_km": r.total_distance_km,
                "stops": len(r.stops),
                "demand_liters": r.total_demand_liters,
                "stop_names": [s.name for s in r.stops],
            }
            for r in routes
        ]
    except Exception as e:
        return [{"error": str(e)}]


def _safe_analysis_reports() -> dict:
    out = {}
    for name in ("seasonality_report", "trend_report"):
        p = ARTIFACTS / "analysis" / f"{name}.json"
        if p.exists():
            out[name] = json.loads(p.read_text(encoding="utf-8"))
    return out or {"note": "Analysis reports not available"}


def _safe_iot_status() -> dict:
    try:
        import urllib.request

        with urllib.request.urlopen(
            "http://localhost:8080/health", timeout=1
        ) as resp:
            return {"telemetry_api": "online", "health": json.loads(resp.read())}
    except Exception:
        return {"telemetry_api": "offline", "note": "Start IoT stack for live sensor data"}
