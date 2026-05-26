from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WeatherSettings:
    enabled: bool
    provider: str
    openweather_api_key: str
    weatherapi_key: str
    timeout_seconds: float
    cache_ttl_seconds: int


def load_settings() -> WeatherSettings:
    provider_raw = os.getenv("WEATHER_PROVIDER", "").strip().lower()
    openweather_api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
    weatherapi_key = os.getenv("WEATHERAPI_KEY", "").strip()
    timeout_seconds = float(os.getenv("WEATHER_TIMEOUT_SECONDS", "3.0"))
    cache_ttl_seconds = int(os.getenv("WEATHER_CACHE_TTL_SECONDS", "600"))
    enabled = bool(openweather_api_key or weatherapi_key)

    if provider_raw:
        provider = provider_raw
    else:
        provider = "openweather" if openweather_api_key else "weatherapi"
    return WeatherSettings(
        enabled=enabled,
        provider=provider,
        openweather_api_key=openweather_api_key,
        weatherapi_key=weatherapi_key,
        timeout_seconds=timeout_seconds,
        cache_ttl_seconds=cache_ttl_seconds,
    )
