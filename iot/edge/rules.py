"""Edge threshold rules — evaluated locally before cloud round-trip."""

from dataclasses import dataclass


@dataclass
class EdgeAlert:
    alert_type: str
    severity: str
    message: str
    metric: str | None = None
    value: float | None = None
    threshold: float | None = None


def evaluate_reading(device_type: str, metrics: dict) -> list[EdgeAlert]:
    alerts: list[EdgeAlert] = []

    if device_type == "flow_meter":
        rate = metrics.get("flow_rate_lpm", 0)
        if rate > 5000:
            alerts.append(
                EdgeAlert(
                    "FLOW_BURST",
                    "WARNING",
                    f"Abnormally high flow: {rate:.0f} L/min",
                    "flow_rate_lpm",
                    rate,
                    5000,
                )
            )

    elif device_type == "reservoir_level":
        level = metrics.get("level_percent", 100)
        if level < 20:
            alerts.append(
                EdgeAlert(
                    "RESERVOIR_LOW",
                    "HIGH",
                    f"Reservoir critically low: {level:.1f}%",
                    "level_percent",
                    level,
                    20,
                )
            )

    elif device_type == "pressure_sensor":
        pressure = metrics.get("pressure_bar", 0)
        if pressure < 1.5:
            alerts.append(
                EdgeAlert(
                    "PRESSURE_LOW",
                    "HIGH",
                    f"Service pressure low: {pressure:.2f} bar",
                    "pressure_bar",
                    pressure,
                    1.5,
                )
            )
        if pressure < 1.0:
            alerts.append(
                EdgeAlert(
                    "PRESSURE_CRITICAL",
                    "CRITICAL",
                    f"Critical under-pressure: {pressure:.2f} bar",
                    "pressure_bar",
                    pressure,
                    1.0,
                )
            )

    elif device_type == "groundwater":
        table = metrics.get("water_table_m", 0)
        if table < 25.0:
            alerts.append(
                EdgeAlert(
                    "GROUNDWATER_LOW",
                    "HIGH",
                    f"Water table below policy minimum: {table:.2f} m",
                    "water_table_m",
                    table,
                    25.0,
                )
            )

    return alerts
