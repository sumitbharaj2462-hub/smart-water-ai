"""Base sensor simulator — generates realistic telemetry for Delhi NCR demo."""

from __future__ import annotations

import math
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from iot.common.config import CITY_ID


class SensorSimulator(ABC):
    device_id: str
    device_type: str
    zone_code: str

    def __init__(self, device_id: str, zone_code: str):
        self.device_id = device_id
        self.zone_code = zone_code
        self._tick = 0

    @abstractmethod
    def read_metrics(self) -> dict[str, float]:
        pass

    def generate(self) -> dict:
        self._tick += 1
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "city_id": CITY_ID,
            "zone_code": self.zone_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": self.read_metrics(),
            "quality": "good",
        }

    def run_loop(self, gateway, interval_sec: float) -> None:
        while True:
            reading = self.generate()
            gateway.ingest(reading)
            time.sleep(interval_sec)
