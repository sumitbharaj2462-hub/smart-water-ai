import random

from iot.simulators.base import SensorSimulator


class PressureSensorSimulator(SensorSimulator):
    device_type = "pressure_sensor"

    def __init__(self, device_id: str, zone_code: str):
        super().__init__(device_id, zone_code)
        self._pressure = random.uniform(2.8, 3.8)

    def read_metrics(self) -> dict[str, float]:
        # Occasional pressure drop simulating leak signature
        if random.random() < 0.02:
            self._pressure -= random.uniform(0.4, 0.8)
        else:
            self._pressure += random.gauss(0, 0.03)
        self._pressure = max(0.8, min(5.0, self._pressure))
        bar = self._pressure
        return {
            "pressure_bar": round(bar, 3),
            "pressure_kpa": round(bar * 100, 1),
            "differential_bar": round(random.uniform(0.05, 0.2), 3),
        }
