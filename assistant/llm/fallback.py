"""Local analyst mode when no LLM API is configured — uses real platform data."""

from __future__ import annotations

import re

from assistant.context.platform_context import build_platform_snapshot
from assistant.reports.emergency import generate_emergency_report
from assistant.tools.operations import (
    analytics_summary,
    explain_predictions,
    summarize_shortages,
)


def _detect_zone(text: str) -> str | None:
    zones = [
        "North Delhi",
        "South Delhi",
        "East Delhi",
        "West Delhi",
        "Central Delhi",
    ]
    for z in zones:
        if z.lower() in text.lower():
            return z
    return None


def local_response(user_message: str, snapshot: dict | None = None) -> str:
    """Rule-based responses backed by live platform tools."""
    snapshot = snapshot or build_platform_snapshot()
    msg = user_message.lower().strip()

    if re.search(r"emergency|incident|crisis|urgent report", msg):
        return generate_emergency_report(save=True)

    if re.search(r"summar(y|ize).*short|shortage|supply gap|risk", msg):
        return summarize_shortages(snapshot)

    if re.search(r"explain|predict|forecast|demand model|lstm|gru|transformer", msg):
        zone = _detect_zone(user_message)
        return explain_predictions(snapshot, zone)

    if re.search(r"analytics|overview|dashboard|status|briefing", msg):
        parts = [
            analytics_summary(snapshot),
            "",
            "---",
            "",
            summarize_shortages(snapshot),
        ]
        return "\n".join(parts)

    if re.search(r"tanker|route|deploy|logistics", msg):
        routes = snapshot.get("tanker_routes", [])
        lines = ["## Tanker Route Summary\n"]
        if routes and "error" not in routes[0]:
            for i, r in enumerate(routes, 1):
                lines.append(
                    f"**Route {i}** from {r.get('depot')}: {r.get('distance_km')} km, "
                    f"{r.get('stops')} stops"
                )
                for n in r.get("stop_names", []):
                    lines.append(f"  - {n}")
        else:
            lines.append("Routes unavailable. Open GIS dashboard or check `gis` module.")
        return "\n".join(lines)

    if re.search(r"anomal|sensor|iot|telemetry", msg):
        anom = snapshot.get("anomalies", {})
        iot = snapshot.get("iot_status", {})
        return (
            f"## Anomalies & IoT\n\n**Telemetry API:** {iot.get('telemetry_api')}\n\n"
            f"```json\n{anom}\n```\n\n"
            "Start IoT stack: `docker compose -f docker-compose.iot.yml up -d`"
        )

    if re.search(r"help|what can you", msg):
        return """## AquaOps AI — Capabilities

I can help with:
- **Shortage summaries** — zone risk, supply-demand gaps
- **Prediction explanations** — deep learning & RF forecasts per zone
- **Emergency reports** — downloadable incident briefings
- **Analytics** — consumption, anomalies, tanker routes
- **Operations Q&A** — based on live platform data

*Tip: Set `OPENAI_API_KEY` for full natural-language reasoning.*

Example questions:
- "Summarize water shortages across Delhi"
- "Explain the forecast for South Delhi"
- "Generate an emergency report"
- "What tanker routes are optimized?"
"""

    # Default: analytics + shortages
    return (
        "I'm running in **local analyst mode** (no LLM API key). "
        "Here's a quick operational briefing:\n\n"
        + analytics_summary(snapshot)
        + "\n\n"
        + summarize_shortages(snapshot)
        + "\n\n*Set OPENAI_API_KEY for conversational follow-ups.*"
    )
