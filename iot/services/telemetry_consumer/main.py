"""
Kafka consumer: telemetry.water.validated.v1 → PostgreSQL + Redis.
Optional FastAPI for querying latest telemetry.
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import threading

from confluent_kafka import Consumer, KafkaError

from iot.common.config import KAFKA_BOOTSTRAP, KAFKA_TOPIC_VALIDATED
from iot.services.telemetry_consumer.storage import TelemetryStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CONSUMER] %(message)s")
log = logging.getLogger("telemetry.consumer")


class TelemetryConsumer:
    def __init__(self) -> None:
        self._consumer = Consumer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP,
                "group.id": "telemetry-db-writer",
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }
        )
        self._consumer.subscribe([KAFKA_TOPIC_VALIDATED])
        self._storage = TelemetryStorage()
        self._running = True
        self._count = 0

    def run(self) -> None:
        log.info("Consuming %s from %s", KAFKA_TOPIC_VALIDATED, KAFKA_BOOTSTRAP)
        while self._running:
            msg = self._consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                log.error("Kafka error: %s", msg.error())
                continue
            try:
                event = json.loads(msg.value().decode("utf-8"))
                n = self._storage.store_event(event)
                self._count += 1
                if self._count % 25 == 0:
                    log.info("Stored %d events (%d metrics last batch)", self._count, n)
            except Exception as exc:
                log.exception("Failed to process message: %s", exc)

    def stop(self) -> None:
        self._running = False
        self._consumer.close()
        self._storage.close()


def start_api_server() -> None:
    import uvicorn

    from iot.services.telemetry_consumer.api import app

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--api", action="store_true", help="Also start REST API on :8080")
    args = parser.parse_args()

    consumer = TelemetryConsumer()

    if args.api:
        threading.Thread(target=start_api_server, daemon=True).start()
        log.info("REST API at http://localhost:8080/docs")

    def shutdown(signum, frame):
        log.info("Shutting down consumer...")
        consumer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    consumer.run()


if __name__ == "__main__":
    main()
