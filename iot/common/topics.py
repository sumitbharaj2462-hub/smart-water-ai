"""MQTT topic helpers for water IoT hierarchy."""


def telemetry_topic(
    city_id: str,
    zone_code: str,
    device_type: str,
    device_id: str,
) -> str:
    return f"water/{city_id}/{zone_code}/{device_type}/{device_id}/telemetry"


def status_topic(
    city_id: str,
    zone_code: str,
    device_type: str,
    device_id: str,
) -> str:
    return f"water/{city_id}/{zone_code}/{device_type}/{device_id}/status"


def parse_telemetry_topic(topic: str) -> dict[str, str] | None:
    """
    Parse: water/{city}/{zone}/{device_type}/{device_id}/telemetry
    """
    parts = topic.split("/")
    if len(parts) != 7 or parts[0] != "water" or parts[6] != "telemetry":
        return None
    return {
        "city_id": parts[1],
        "zone_code": parts[2],
        "device_type": parts[3],
        "device_id": parts[4],
    }


TELEMETRY_SUBSCRIBE_FILTER = "water/+/+/+/+/telemetry"
