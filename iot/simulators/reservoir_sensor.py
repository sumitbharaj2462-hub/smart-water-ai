import random

from iot.simulators.base import SensorSimulator


class ReservoirSensorSimulator(SensorSimulator):
    device_type = "reservoir_level"

    def __init__(self, device_id: str, zone_code: str):
        super().__init__(device_id, zone_code)
        self._level_percent = random.uniform(45, 75)
        self._max_volume_m3 = 300_000

    def read_metrics(self) -> dict[str, float]:
        self._level_percent += random.gauss(-0.05, 0.15)
        self._level_percent = max(12, min(95, self._level_percent))
        level_m = (self._level_percent / 100) * 20.0
        inflow = random.uniform(2500, 4500)
        outflow = inflow + random.gauss(200, 100)
        return {
            "level_m": round(level_m, 2),
            "level_percent": round(self._level_percent, 2),
            "volume_m3": round(self._max_volume_m3 * self._level_percent / 100, 0),
            "inflow_lpm": round(inflow, 1),
            "outflow_lpm": round(max(0, outflow), 1),
        }
