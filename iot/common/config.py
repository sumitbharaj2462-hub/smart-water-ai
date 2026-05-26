import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / "iot" / ".env")


def env(key: str, default: str | None = None) -> str:
    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = env_int("MQTT_PORT", 1883)
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:19092")
KAFKA_TOPIC_RAW = os.getenv("KAFKA_TOPIC_RAW", "telemetry.water.raw.v1")
KAFKA_TOPIC_VALIDATED = os.getenv(
    "KAFKA_TOPIC_VALIDATED", "telemetry.water.validated.v1"
)
KAFKA_TOPIC_ALERTS = os.getenv("KAFKA_TOPIC_ALERTS", "alerts.water.iot.v1")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = env_int("POSTGRES_PORT", 5432)
POSTGRES_USER = os.getenv("POSTGRES_USER", "water")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "water")
POSTGRES_DB = os.getenv("POSTGRES_DB", "water_iot")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = env_int("REDIS_PORT", 6379)
REDIS_DB = env_int("REDIS_DB", 0)

CITY_ID = os.getenv("CITY_ID", "delhi-ncr")
