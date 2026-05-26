"""
Run all sensor simulators feeding into edge gateway(s).
Usage (from project root): python -m iot.simulators.run_all
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import yaml

from iot.edge.gateway import EdgeGateway
from iot.simulators.flow_sensor import FlowSensorSimulator
from iot.simulators.groundwater_sensor import GroundwaterSensorSimulator
from iot.simulators.pressure_sensor import PressureSensorSimulator
from iot.simulators.reservoir_sensor import ReservoirSensorSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SIM] %(message)s")
log = logging.getLogger("simulators")

SIMULATOR_CLASSES = {
    "flow_meter": FlowSensorSimulator,
    "reservoir_level": ReservoirSensorSimulator,
    "pressure_sensor": PressureSensorSimulator,
    "groundwater": GroundwaterSensorSimulator,
}


def load_devices():
    path = Path(__file__).resolve().parents[1] / "config" / "devices.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> None:
    cfg = load_devices()
    gateways: dict[str, EdgeGateway] = {}

    for gw in cfg.get("edge_gateways", []):
        g = EdgeGateway(gw["id"], gw["zone_code"])
        g.connect()
        gateways[gw["id"]] = g
        threading.Thread(target=_aggregate_loop, args=(g,), daemon=True).start()

    if not gateways:
        g = EdgeGateway("edge-north-01", "north-delhi")
        g.connect()
        gateways["edge-north-01"] = g
        threading.Thread(target=_aggregate_loop, args=(g,), daemon=True).start()

    threads: list[threading.Thread] = []
    for dev in cfg.get("devices", []):
        cls = SIMULATOR_CLASSES.get(dev["device_type"])
        if not cls:
            log.warning("Unknown device type: %s", dev["device_type"])
            continue
        gw_id = dev.get("edge_gateway_id", list(gateways.keys())[0])
        gateway = gateways.get(gw_id) or list(gateways.values())[0]
        sim = cls(dev["device_id"], dev["zone_code"])
        interval = dev.get("publish_interval_sec", 5)
        t = threading.Thread(
            target=sim.run_loop,
            args=(gateway, interval),
            name=dev["device_id"],
            daemon=True,
        )
        t.start()
        threads.append(t)
        log.info("Started %s (%s) -> %s", dev["device_id"], dev["device_type"], gw_id)

    log.info("All simulators running. Press Ctrl+C to stop.")
    for t in threads:
        t.join()


def _aggregate_loop(gateway: EdgeGateway) -> None:
    import time

    while True:
        n = gateway.publish_aggregates()
        if n:
            log.debug("Gateway %s published %d aggregates", gateway.gateway_id, n)
        time.sleep(10)


if __name__ == "__main__":
    main()
