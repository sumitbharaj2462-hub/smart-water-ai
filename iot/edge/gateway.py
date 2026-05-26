"""
Edge gateway: receives sensor readings (via queue), applies rules,
buffers on failure, publishes aggregated telemetry to MQTT.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import yaml

from iot.common.config import CITY_ID, MQTT_HOST, MQTT_PORT, MQTT_PASSWORD, MQTT_USERNAME
from iot.common.topics import telemetry_topic
from iot.edge.rules import EdgeAlert, evaluate_reading

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EDGE] %(message)s")
log = logging.getLogger("edge.gateway")

BUFFER_DB = Path(__file__).resolve().parent / "data" / "buffer.db"
AGGREGATE_WINDOW_SEC = 10


class EdgeGateway:
    def __init__(self, gateway_id: str, zone_code: str):
        self.gateway_id = gateway_id
        self.zone_code = zone_code
        self._buffers: dict[str, list[dict]] = defaultdict(list)
        self._lock = threading.Lock()
        self._init_buffer_db()
        self._mqtt = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=gateway_id,
        )
        if MQTT_USERNAME:
            self._mqtt.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self._mqtt.on_connect = self._on_connect

    def _init_buffer_db(self) -> None:
        BUFFER_DB.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(BUFFER_DB) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            log.info("Connected to MQTT %s:%s", MQTT_HOST, MQTT_PORT)
            self._flush_buffer()
        else:
            log.error("MQTT connect failed: %s", reason_code)

    def connect(self) -> None:
        self._mqtt.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        self._mqtt.loop_start()

    def ingest(self, reading: dict) -> list[EdgeAlert]:
        device_id = reading["device_id"]
        device_type = reading["device_type"]
        alerts = evaluate_reading(device_type, reading.get("metrics", {}))
        for alert in alerts:
            log.warning("[%s] %s", device_id, alert.message)

        with self._lock:
            self._buffers[device_id].append(reading)

        return alerts

    def publish_aggregates(self) -> int:
        published = 0
        with self._lock:
            batches = dict(self._buffers)
            self._buffers.clear()

        for device_id, readings in batches.items():
            if not readings:
                continue
            agg = self._aggregate(device_id, readings)
            topic = telemetry_topic(
                CITY_ID,
                agg["zone_code"],
                agg["device_type"],
                agg["device_id"],
            )
            if self._publish(topic, agg):
                published += 1
            else:
                self._buffer(topic, agg)
        return published

    def _aggregate(self, device_id: str, readings: list[dict]) -> dict:
        latest = readings[-1]
        metrics: dict[str, float] = {}
        numeric_keys: set[str] = set()
        for r in readings:
            numeric_keys.update(
                k for k, v in r.get("metrics", {}).items() if isinstance(v, (int, float))
            )
        for key in numeric_keys:
            values = [r["metrics"][key] for r in readings if key in r.get("metrics", {})]
            metrics[key] = sum(values) / len(values)

        return {
            "device_id": device_id,
            "device_type": latest["device_type"],
            "city_id": latest.get("city_id", CITY_ID),
            "zone_code": latest["zone_code"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
            "quality": "good",
            "edge_gateway_id": self.gateway_id,
            "samples_aggregated": len(readings),
        }

    def _publish(self, topic: str, payload: dict) -> bool:
        try:
            result = self._mqtt.publish(topic, json.dumps(payload), qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as exc:
            log.error("Publish failed: %s", exc)
            return False

    def _buffer(self, topic: str, payload: dict) -> None:
        with sqlite3.connect(BUFFER_DB) as conn:
            conn.execute(
                "INSERT INTO pending (topic, payload, created_at) VALUES (?, ?, ?)",
                (topic, json.dumps(payload), time.time()),
            )
        log.info("Buffered message for %s", topic)

    def _flush_buffer(self) -> None:
        with sqlite3.connect(BUFFER_DB) as conn:
            rows = conn.execute(
                "SELECT id, topic, payload FROM pending ORDER BY id LIMIT 100"
            ).fetchall()
            for row_id, topic, payload in rows:
                if self._mqtt.publish(topic, payload, qos=1).rc == mqtt.MQTT_ERR_SUCCESS:
                    conn.execute("DELETE FROM pending WHERE id = ?", (row_id,))
            conn.commit()
        if rows:
            log.info("Flushed %d buffered messages", len(rows))


def load_gateway_from_config(gateway_id: str | None = None) -> EdgeGateway:
    config_path = Path(__file__).resolve().parents[1] / "config" / "devices.yaml"
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    gateways = cfg.get("edge_gateways", [])
    if not gateways:
        return EdgeGateway("edge-north-01", "north-delhi")
    gw = gateways[0]
    if gateway_id:
        gw = next((g for g in gateways if g["id"] == gateway_id), gw)
    return EdgeGateway(gw["id"], gw["zone_code"])


def run_gateway_loop(gateway_id: str | None = None, interval_sec: float = 10) -> None:
    gateway = load_gateway_from_config(gateway_id)
    gateway.connect()
    log.info(
        "Edge gateway %s (%s) running — aggregate every %ss",
        gateway.gateway_id,
        gateway.zone_code,
        interval_sec,
    )
    while True:
        gateway.publish_aggregates()
        time.sleep(interval_sec)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Water IoT edge gateway")
    parser.add_argument("--gateway-id", default=None)
    parser.add_argument("--interval", type=float, default=AGGREGATE_WINDOW_SEC)
    args = parser.parse_args()
    run_gateway_loop(args.gateway_id, args.interval)
