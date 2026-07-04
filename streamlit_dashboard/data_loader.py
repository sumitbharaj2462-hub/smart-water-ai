"""Load education dashboard JSON into pandas DataFrames."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "education_dashboard" / "data" / "dashboard_data.json"


@lru_cache(maxsize=1)
def load_dashboard_data(path: str | Path = DATA_PATH) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def countries_df(data: dict | None = None) -> pd.DataFrame:
    data = data or load_dashboard_data()
    return pd.DataFrame(data["countries"])


def records_df(data: dict | None = None) -> pd.DataFrame:
    data = data or load_dashboard_data()
    return pd.DataFrame(data["records"])


def latest_df(data: dict | None = None) -> pd.DataFrame:
    data = data or load_dashboard_data()
    return pd.DataFrame(data["latest"])


def regions_df(data: dict | None = None) -> pd.DataFrame:
    data = data or load_dashboard_data()
    return pd.DataFrame(data["regions"])


def metrics_dict(data: dict | None = None) -> dict:
    data = data or load_dashboard_data()
    return data["metrics"]


def metric_label(metric_id: str, data: dict | None = None) -> str:
    meta = metrics_dict(data).get(metric_id, {})
    group = meta.get("group", "")
    label = meta.get("label", metric_id)
    return f"{group}: {label}" if group else label


def format_value(value: float | None, metric_id: str, data: dict | None = None) -> str:
    if value is None or pd.isna(value):
        return "-"
    meta = metrics_dict(data).get(metric_id, {})
    fmt = meta.get("format", "number")
    abs_val = abs(value)
    if fmt == "currency":
        return f"${value:,.0f}"
    if fmt == "percent":
        return f"{value:,.2f}%"
    if fmt == "large" or abs_val >= 1_000_000:
        if abs_val >= 1_000_000_000:
            return f"{value / 1_000_000_000:,.2f}B"
        if abs_val >= 1_000_000:
            return f"{value / 1_000_000:,.2f}M"
        if abs_val >= 1_000:
            return f"{value / 1_000:,.2f}K"
    return f"{value:,.2f}"


def enrich_latest(latest: pd.DataFrame, countries: pd.DataFrame) -> pd.DataFrame:
    return latest.merge(countries, left_on="country", right_on="code", how="inner")


def filter_countries(
    countries: pd.DataFrame,
    region: str = "All",
    income: str = "All",
) -> pd.DataFrame:
    filtered = countries.copy()
    if region != "All":
        filtered = filtered[filtered["region"] == region]
    if income != "All":
        filtered = filtered[filtered["income"] == income]
    return filtered.sort_values("name")
