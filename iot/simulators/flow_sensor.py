import math
import random

from iot.simulators.base import SensorSimulator


class FlowSensorSimulator(SensorSimulator):
    device_type = "flow_meter"

    def __init__(self, device_id: str, zone_code: str):
        super().__init__(device_id, zone_code)
        self._cumulative = random.uniform(800_000_000, 900_000_000)
        self._base_rate = random.uniform(800, 1800)

    def read_metrics(self) -> dict[str, float]:
        hour_factor = 1.0 + 0.3 * math_sin_hour(self._tick)
        flow = max(0, self._base_rate * hour_factor + random.gauss(0, 80))
        self._cumulative += flow * (5 / 60)  # approx 5s interval contribution
        return {
            "flow_rate_lpm": round(flow, 2),
            "cumulative_volume_liters": round(self._cumulative, 0),
            "velocity_mps": round(flow / 4200, 3),
        }


def math_sin_hour(tick: int) -> float:
    return math.sin(tick * 0.05)
