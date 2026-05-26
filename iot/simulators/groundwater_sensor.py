import random

from iot.simulators.base import SensorSimulator


class GroundwaterSensorSimulator(SensorSimulator):
    device_type = "groundwater"

    def __init__(self, device_id: str, zone_code: str):
        super().__init__(device_id, zone_code)
        self._water_table = random.uniform(26, 32)

    def read_metrics(self) -> dict[str, float]:
        self._water_table += random.gauss(-0.01, 0.02)
        drawdown = max(0, random.gauss(1.0, 0.3))
        return {
            "water_table_m": round(self._water_table, 2),
            "drawdown_m": round(drawdown, 2),
            "conductivity_us_cm": round(random.uniform(400, 800), 0),
            "temperature_c": round(random.uniform(22, 26), 1),
        }
