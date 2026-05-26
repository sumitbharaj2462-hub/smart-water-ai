"""
MQTT → Kafka telemetry ingestion bridge.
Subscribe: water/+/+/+/+/telemetry
Produce: telemetry.water.validated.v1 (and raw copy)
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from confluent_kafka import Producer

from iot.common.config import (
    KAFKA_BOOTSTRAP,
    KAFKA_TOPIC_RAW,
    KAFKA_TOPIC_VALIDATED,
    MQTT_HOST,
    MQTT_PASSWORD,
    MQTT_PORT,
    MQTT_USERNAME,
)
from iot.common.topics import TELEMETRY_SUBSCRIBE_FILTER, parse_telemetry_topic
from iot.common.validator import validate_telemetry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [INGEST] %(message)s")
log = logging.getLogger("telemetry.ingestion")


class TelemetryIngestionBridge:
    def __init__(self) -> None:
        self._producer = Producer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP,
                "client.id": "telemetry-ingestion",
                "acks": "all",
            }
        )
        self._mqtt = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="telemetry-ingestion",
        )
        if MQTT_USERNAME:
            self._mqtt.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self._mqtt.on_connect = self._on_connect
        self._mqtt.on_message = self._on_message
        self._running = True
        self._stats = {"received": 0, "valid": 0, "invalid": 0}

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            client.subscribe(TELEMETRY_SUBSCRIBE_FILTER, qos=1)
            log.info("Subscribed to %s", TELEMETRY_SUBSCRIBE_FILTER)
        else:
            log.error("MQTT connect failed: %s", reason_code)

    def _on_message(self, client, userdata, msg):
        self._stats["received"] += 1
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            self._stats["invalid"] += 1
            log.warning("Invalid JSON on %s", msg.topic)
            return

        meta = parse_telemetry_topic(msg.topic)
        if meta:
            payload.setdefault("city_id", meta["city_id"])
            payload.setdefault("zone_code", meta["zone_code"])
            payload.setdefault("device_type", meta["device_type"])
            payload.setdefault("device_id", meta["device_id"])

        errors = validate_telemetry(payload)
        if errors:
            self._stats["invalid"] += 1
            log.warning("Validation failed %s: %s", msg.topic, errors[:2])
            return

        event = self._envelope(payload, msg.topic)
        self._produce(KAFKA_TOPIC_RAW, event)
        self._produce(KAFKA_TOPIC_VALIDATED, event)
        self._stats["valid"] += 1
        self._producer.poll(0)

        if self._stats["valid"] % 50 == 0:
            log.info("Stats: %s", self._stats)

    def _envelope(self, payload: dict, source_topic: str) -> dict:
        return {
            "schema_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "device_id": payload["device_id"],
            "device_type": payload["device_type"],
            "city_id": payload.get("city_id", "delhi-ncr"),
            "zone_code": payload["zone_code"],
            "timestamp": payload["timestamp"],
            "metrics": payload["metrics"],
            "quality": payload.get("quality", "good"),
            "edge_gateway_id": payload.get("edge_gateway_id"),
            "source_topic": source_topic,
        }

    def _produce(self, topic: str, event: dict) -> None:
        key = event["device_id"].encode("utf-8")
        value = json.dumps(event).encode("utf-8")

        def _delivery(err, msg):
            if err:
                log.error("Kafka delivery failed: %s", err)

        self._producer.produce(topic, key=key, value=value, callback=_delivery)

    def start(self) -> None:
        log.info("Connecting MQTT %s:%s, Kafka %s", MQTT_HOST, MQTT_PORT, KAFKA_BOOTSTRAP)
        self._mqtt.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        self._mqtt.loop_forever()

    def stop(self) -> None:
        self._running = False
        self._mqtt.loop_stop()
        self._producer.flush(10)


def main() -> None:
    bridge = TelemetryIngestionBridge()

    def shutdown(signum, frame):
        log.info("Shutting down...")
        bridge.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    bridge.start()


if __name__ == "__main__":
    main()
