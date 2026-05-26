import json
from pathlib import Path

from jsonschema import Draft202012Validator

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "telemetry_v1.json"
_VALIDATOR: Draft202012Validator | None = None


def get_validator() -> Draft202012Validator:
    global _VALIDATOR
    if _VALIDATOR is None:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        _VALIDATOR = Draft202012Validator(schema)
    return _VALIDATOR


def validate_telemetry(payload: dict) -> list[str]:
    errors = sorted(get_validator().iter_errors(payload), key=lambda e: e.path)
    return [e.message for e in errors]
