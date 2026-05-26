"""Persist telemetry to PostgreSQL and cache latest values in Redis."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.extras
import redis

from iot.common.config import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PORT,
)

log = logging.getLogger("telemetry.storage")

METRIC_UNITS = {
    "flow_rate_lpm": "lpm",
    "cumulative_volume_liters": "L",
    "velocity_mps": "m/s",
    "level_m": "m",
    "level_percent": "%",
    "volume_m3": "m3",
    "inflow_lpm": "lpm",
    "outflow_lpm": "lpm",
    "pressure_bar": "bar",
    "pressure_kpa": "kPa",
    "differential_bar": "bar",
    "water_table_m": "m",
    "drawdown_m": "m",
    "conductivity_us_cm": "uS/cm",
    "temperature_c": "C",
}


class TelemetryStorage:
    def __init__(self) -> None:
        self._pg = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            dbname=POSTGRES_DB,
        )
        self._pg.autocommit = False
        self._redis = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
        )

    def store_event(self, event: dict[str, Any]) -> int:
        ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        rows: list[tuple] = []
        for metric, value in event.get("metrics", {}).items():
            if not isinstance(value, (int, float)):
                continue
            rows.append(
                (
                    ts,
                    event["device_id"],
                    event["device_type"],
                    event["zone_code"],
                    metric,
                    float(value),
                    METRIC_UNITS.get(metric),
                    event.get("quality", "good"),
                    event.get("event_id"),
                )
            )

        if not rows:
            return 0

        with self._pg.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO telemetry_reading
                    (time, device_id, device_type, zone_code, metric, value, unit, quality, event_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, device_id, metric) DO UPDATE SET value = EXCLUDED.value
                """,
                rows,
            )
            cur.execute(
                "UPDATE iot_device SET last_seen_at = %s WHERE device_id = %s",
                (ts, event["device_id"]),
            )
        self._pg.commit()

        latest_key = f"telemetry:latest:{event['device_id']}"
        self._redis.setex(latest_key, 3600, json.dumps(event))
        zone_key = f"telemetry:zone:{event['zone_code']}:{event['device_id']}"
        self._redis.setex(zone_key, 3600, json.dumps(event))
        return len(rows)

    def get_latest(self, device_id: str) -> dict | None:
        raw = self._redis.get(f"telemetry:latest:{device_id}")
        return json.loads(raw) if raw else None

    def close(self) -> None:
        self._pg.close()
        self._redis.close()
