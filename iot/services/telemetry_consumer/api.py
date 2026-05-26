"""REST API for latest IoT telemetry (operations dashboard integration)."""

from __future__ import annotations

from datetime import datetime

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException, Query

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
from iot.services.telemetry_consumer.storage import TelemetryStorage

app = FastAPI(
    title="Water IoT Telemetry API",
    description="Latest sensor readings from MQTT/Kafka pipeline",
    version="1.0.0",
)

_storage: TelemetryStorage | None = None


def get_storage() -> TelemetryStorage:
    global _storage
    if _storage is None:
        _storage = TelemetryStorage()
    return _storage


def pg_conn():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "telemetry-consumer-api"}


@app.get("/devices")
def list_devices():
    with pg_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT device_id, device_type, zone_code, asset_name, last_seen_at
            FROM iot_device ORDER BY zone_code, device_id
            """
        )
        return {"devices": cur.fetchall()}


@app.get("/telemetry/latest/{device_id}")
def latest_telemetry(device_id: str):
    event = get_storage().get_latest(device_id)
    if not event:
        raise HTTPException(404, f"No recent telemetry for {device_id}")
    return event


@app.get("/telemetry/history/{device_id}")
def telemetry_history(
    device_id: str,
    metric: str = Query(..., description="e.g. flow_rate_lpm, pressure_bar"),
    hours: int = Query(24, ge=1, le=168),
):
    with pg_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT time, value, unit, quality
            FROM telemetry_reading
            WHERE device_id = %s AND metric = %s
              AND time > now() - make_interval(hours => %s)
            ORDER BY time ASC
            """,
            (device_id, metric, hours),
        )
        rows = cur.fetchall()
    return {"device_id": device_id, "metric": metric, "points": rows}


@app.get("/telemetry/zone/{zone_code}/summary")
def zone_summary(zone_code: str):
    """Latest metric per device in a zone (for command center dashboard)."""
    import redis
    import json as json_lib

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    pattern = f"telemetry:zone:{zone_code}:*"
    summaries = []
    for key in r.scan_iter(match=pattern, count=100):
        raw = r.get(key)
        if raw:
            summaries.append(json_lib.loads(raw))
    return {
        "zone_code": zone_code,
        "device_count": len(summaries),
        "readings": summaries,
        "as_of": datetime.utcnow().isoformat() + "Z",
    }
