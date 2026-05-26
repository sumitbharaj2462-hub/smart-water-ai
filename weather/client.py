from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from weather.cache import cache_get_or_set
from weather.config import load_settings


@dataclass(frozen=True)
class WeatherCurrent:
    temperature_c: float
    humidity_pct: float
    rainfall_mm: float
    condition: str
    observed_at: str


@dataclass(frozen=True)
class WeatherForecastDay:
    date: str
    min_temp_c: float | None
    max_temp_c: float | None
    rainfall_mm: float
    avg_humidity_pct: float | None
    condition: str | None


def get_weather_bundle(lat: float, lon: float, days: int = 3) -> dict[str, Any]:
    settings = load_settings()
    if not settings.enabled:
        raise RuntimeError(
            "Weather APIs not configured. Set OPENWEATHER_API_KEY and/or WEATHERAPI_KEY."
        )

    provider = settings.provider
    if provider not in {"openweather", "weatherapi"}:
        raise ValueError("WEATHER_PROVIDER must be 'openweather' or 'weatherapi'")

    root = Path(__file__).resolve().parents[1]
    cache_path = root / "ml" / "artifacts" / "weather_cache.json"
    days = max(1, min(int(days), 7))

    cache_key = f"{provider}:{lat:.4f}:{lon:.4f}:{days}"

    def fetch():
        if provider == "openweather":
            current = _openweather_current(lat, lon, settings.openweather_api_key, settings.timeout_seconds)
            forecast = _openweather_forecast(lat, lon, days, settings.openweather_api_key, settings.timeout_seconds)
        else:
            current = _weatherapi_current(lat, lon, settings.weatherapi_key, settings.timeout_seconds)
            forecast = _weatherapi_forecast(lat, lon, days, settings.weatherapi_key, settings.timeout_seconds)

        rainfall_next_24h_mm = forecast[0].rainfall_mm if forecast else None
        return {
            "provider": provider,
            "lat": lat,
            "lon": lon,
            "current": asdict(current),
            "forecast_days": [asdict(d) for d in forecast],
            "rainfall_next_24h_mm": rainfall_next_24h_mm,
        }

    return cache_get_or_set(
        cache_path=cache_path,
        cache_key=cache_key,
        ttl_seconds=settings.cache_ttl_seconds,
        fetcher=fetch,
    )


def _fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "WATER/1.0"})
    with urlopen(req, timeout=timeout_seconds) as resp:
        raw = resp.read()
    return json.loads(raw)


def _openweather_current(
    lat: float, lon: float, api_key: str, timeout_seconds: float
) -> WeatherCurrent:
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY is not set")
    qs = urlencode({"lat": lat, "lon": lon, "appid": api_key, "units": "metric"})
    url = f"https://api.openweathermap.org/data/2.5/weather?{qs}"
    data = _fetch_json(url, timeout_seconds)
    temp_c = float(data["main"]["temp"])
    humidity = float(data["main"]["humidity"])
    rain = data.get("rain") or {}
    rainfall_mm = float(rain.get("1h") or rain.get("3h") or 0.0)
    cond = ""
    if isinstance(data.get("weather"), list) and data["weather"]:
        cond = str(data["weather"][0].get("description") or "")
    observed_at = datetime.fromtimestamp(int(data.get("dt") or 0), tz=timezone.utc).isoformat()
    return WeatherCurrent(
        temperature_c=temp_c,
        humidity_pct=humidity,
        rainfall_mm=rainfall_mm,
        condition=cond,
        observed_at=observed_at,
    )


def _openweather_forecast(
    lat: float, lon: float, days: int, api_key: str, timeout_seconds: float
) -> list[WeatherForecastDay]:
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY is not set")
    qs = urlencode({"lat": lat, "lon": lon, "appid": api_key, "units": "metric"})
    url = f"https://api.openweathermap.org/data/2.5/forecast?{qs}"
    data = _fetch_json(url, timeout_seconds)
    buckets: dict[str, dict[str, Any]] = {}

    for item in data.get("list") or []:
        ts = int(item.get("dt") or 0)
        day = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        b = buckets.setdefault(day, {"temps": [], "humidity": [], "rain": 0.0, "cond": None})
        main = item.get("main") or {}
        if "temp" in main:
            b["temps"].append(float(main["temp"]))
        if "humidity" in main:
            b["humidity"].append(float(main["humidity"]))
        rain = item.get("rain") or {}
        b["rain"] += float(rain.get("3h") or rain.get("1h") or 0.0)
        w = item.get("weather") or []
        if not b["cond"] and isinstance(w, list) and w:
            b["cond"] = w[0].get("description")

    out: list[WeatherForecastDay] = []
    for day in sorted(buckets.keys())[:days]:
        b = buckets[day]
        temps: list[float] = b["temps"]
        humidity: list[float] = b["humidity"]
        out.append(
            WeatherForecastDay(
                date=day,
                min_temp_c=min(temps) if temps else None,
                max_temp_c=max(temps) if temps else None,
                rainfall_mm=float(b["rain"]),
                avg_humidity_pct=(sum(humidity) / len(humidity)) if humidity else None,
                condition=str(b["cond"]) if b["cond"] is not None else None,
            )
        )
    return out


def _weatherapi_current(
    lat: float, lon: float, api_key: str, timeout_seconds: float
) -> WeatherCurrent:
    if not api_key:
        raise RuntimeError("WEATHERAPI_KEY is not set")
    qs = urlencode({"key": api_key, "q": f"{lat},{lon}", "aqi": "no"})
    url = f"https://api.weatherapi.com/v1/current.json?{qs}"
    data = _fetch_json(url, timeout_seconds)
    cur = data["current"]
    temp_c = float(cur["temp_c"])
    humidity = float(cur["humidity"])
    rainfall_mm = float(cur.get("precip_mm") or 0.0)
    cond = ""
    if isinstance(cur.get("condition"), dict):
        cond = str(cur["condition"].get("text") or "")
    observed_at = datetime.now(timezone.utc).isoformat()
    return WeatherCurrent(
        temperature_c=temp_c,
        humidity_pct=humidity,
        rainfall_mm=rainfall_mm,
        condition=cond,
        observed_at=observed_at,
    )


def _weatherapi_forecast(
    lat: float, lon: float, days: int, api_key: str, timeout_seconds: float
) -> list[WeatherForecastDay]:
    if not api_key:
        raise RuntimeError("WEATHERAPI_KEY is not set")
    qs = urlencode({"key": api_key, "q": f"{lat},{lon}", "days": days, "aqi": "no", "alerts": "no"})
    url = f"https://api.weatherapi.com/v1/forecast.json?{qs}"
    data = _fetch_json(url, timeout_seconds)
    forecast_days = ((data.get("forecast") or {}).get("forecastday")) or []
    out: list[WeatherForecastDay] = []
    for item in forecast_days[:days]:
        day = item.get("day") or {}
        cond = None
        if isinstance(day.get("condition"), dict):
            cond = day["condition"].get("text")
        out.append(
            WeatherForecastDay(
                date=str(item.get("date") or ""),
                min_temp_c=float(day["mintemp_c"]) if "mintemp_c" in day else None,
                max_temp_c=float(day["maxtemp_c"]) if "maxtemp_c" in day else None,
                rainfall_mm=float(day.get("totalprecip_mm") or 0.0),
                avg_humidity_pct=float(day["avghumidity"]) if "avghumidity" in day else None,
                condition=str(cond) if cond is not None else None,
            )
        )
    return out
