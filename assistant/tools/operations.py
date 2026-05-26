"""Deterministic tools the assistant uses for analytics and reports."""

from __future__ import annotations

from datetime import datetime, timezone

from assistant.context.platform_context import build_platform_snapshot


def summarize_shortages(snapshot: dict | None = None) -> str:
    snapshot = snapshot or build_platform_snapshot()
    risks = snapshot.get("zone_risks", [])
    if not risks or "error" in risks[0]:
        return "Unable to load zone risk data. Ensure the dataset and GIS modules are available."

    lines = ["## Water Shortage Summary\n"]
    critical = [r for r in risks if r.get("risk_level") in ("critical", "high")]
    lines.append(
        f"**Overview:** {len(critical)} of {len(risks)} zones at elevated or critical risk "
        f"(as of {snapshot.get('generated_at', 'now')}).\n"
    )

    for r in sorted(risks, key=lambda x: -x.get("risk_score", 0)):
        gap = r.get("gap_liters", 0)
        status = "SHORTAGE" if gap > 0 else "OK"
        lines.append(
            f"- **{r['zone']}** [{r.get('risk_level', '?').upper()}]: "
            f"risk {r.get('risk_score', 0):.1f}%, "
            f"demand {r.get('demand_liters', 0):,.0f} L/day, "
            f"supply {r.get('supply_liters', 0):,.0f} L/day, "
            f"gap {gap:,.0f} L — {status}"
        )

    if critical:
        lines.append("\n**Recommended actions:** Deploy tankers to highest-risk zones, "
                       "increase reservoir pumping, issue conservation advisories.")
    else:
        lines.append("\n**Status:** All zones within acceptable supply margins.")
    return "\n".join(lines)


def explain_predictions(snapshot: dict | None = None, zone: str | None = None) -> str:
    snapshot = snapshot or build_platform_snapshot()
    forecasts = snapshot.get("forecasts", {})
    ml = snapshot.get("ml_models", {})

    lines = ["## Prediction Explanation\n"]
    if ml and "note" not in ml:
        best = min(ml.items(), key=lambda x: x[1].get("mae", float("inf")))
        lines.append(
            f"Forecasts use the **{best[0].upper()}** deep learning model "
            f"(test MAE {best[1].get('mae', 0):,.0f} L, R² {best[1].get('r2', 0):.3f}). "
            "Inputs include 30-day multivariate history: temperature, rainfall, industrial index, "
            "demand lags, and cyclical calendar features.\n"
        )
    else:
        lines.append(
            "Random Forest baseline uses population, weather, industrial index, and calendar features. "
            "Train deep models with `python -m ml.train_deep` for sequence forecasts.\n"
        )

    zones = [zone] if zone else list(forecasts.keys())[:3]
    for z in zones:
        fc = forecasts.get(z, {})
        if "error" in fc:
            lines.append(f"- **{z}:** forecast unavailable ({fc['error']})")
            continue
        lines.append(f"\n### {z}")
        lines.append(f"- Last actual: {fc.get('last_actual_demand', 0):,} L/day")
        lines.append(f"- Model: {fc.get('model', 'unknown')}")
        for day in fc.get("forecast", [])[:5]:
            lines.append(f"  - {day['date']}: **{day['water_demand_liters']:,}** L/day")

    return "\n".join(lines)


def analytics_summary(snapshot: dict | None = None) -> str:
    snapshot = snapshot or build_platform_snapshot()
    consumption = snapshot.get("consumption", [])
    anomalies = snapshot.get("anomalies", {})
    routes = snapshot.get("tanker_routes", [])

    lines = ["## Natural Language Analytics Summary\n"]
    if consumption and "error" not in consumption[0]:
        top = max(consumption, key=lambda x: x.get("share_pct", 0))
        lines.append(
            f"**Consumption:** {top['zone']} leads with {top.get('share_pct', 0)}% of total "
            f"demand over the last 30 days (avg {top.get('avg_daily_demand', 0):,} L/day)."
        )

    if isinstance(anomalies, dict) and "zones" in anomalies:
        total_anom = sum(z.get("anomalies_detected", 0) for z in anomalies["zones"].values())
        lines.append(f"**Anomalies:** {total_anom} sensor/forecast anomalies flagged across zones.")

    if routes and "error" not in routes[0]:
        total_km = sum(r.get("distance_km", 0) for r in routes)
        lines.append(
            f"**Logistics:** {len(routes)} optimized tanker routes ready ({total_km:.1f} km total)."
        )

    iot = snapshot.get("iot_status", {})
    lines.append(f"**IoT telemetry API:** {iot.get('telemetry_api', 'unknown')}.")
    return "\n".join(lines)


def run_tool(name: str, **kwargs) -> str:
    snapshot = kwargs.pop("snapshot", None) or build_platform_snapshot()
    tools = {
        "summarize_shortages": lambda: summarize_shortages(snapshot),
        "explain_predictions": lambda: explain_predictions(snapshot, kwargs.get("zone")),
        "analytics_summary": lambda: analytics_summary(snapshot),
    }
    if name not in tools:
        return f"Unknown tool: {name}"
    return tools[name]()


TOOL_REGISTRY = {
    "summarize_shortages": {
        "description": "Summarize water shortages and risk by zone",
        "function": summarize_shortages,
    },
    "explain_predictions": {
        "description": "Explain ML demand forecasts",
        "function": explain_predictions,
    },
    "analytics_summary": {
        "description": "High-level analytics for administrators",
        "function": analytics_summary,
    },
}
