from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def read_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def write_cache(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def cache_get_or_set(
    *,
    cache_path: Path,
    cache_key: str,
    ttl_seconds: int,
    fetcher,
) -> Any:
    now = time.time()
    cache = read_cache(cache_path)
    entry = cache.get(cache_key)
    if isinstance(entry, dict):
        expires_at = entry.get("expires_at")
        if isinstance(expires_at, (int, float)) and expires_at > now and "value" in entry:
            return entry["value"]
    value = fetcher()
    cache[cache_key] = {"expires_at": now + ttl_seconds, "value": value}
    write_cache(cache_path, cache)
    return value
