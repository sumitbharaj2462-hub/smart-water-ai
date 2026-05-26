"""Zone-wise water consumption analytics from historical panel data."""

from __future__ import annotations

import pandas as pd

from gis.analytics.risk import _load_panel


def get_zone_consumption(days: int = 30) -> pd.DataFrame:
    """
    Per-zone consumption stats for choropleth and charts.
    """
    panel = _load_panel()
    if "zone" not in panel.columns:
        return pd.DataFrame()

    panel = panel.sort_values("date")
    cutoff = panel["date"].max() - pd.Timedelta(days=days)
    recent = panel[panel["date"] >= cutoff]

    agg = (
        recent.groupby("zone")
        .agg(
            avg_daily_demand=("water_demand", "mean"),
            max_demand=("water_demand", "max"),
            min_demand=("water_demand", "min"),
            total_period=("water_demand", "sum"),
            days=("date", "nunique"),
        )
        .reset_index()
    )
    agg["avg_daily_demand"] = agg["avg_daily_demand"].astype(int)
    agg["max_demand"] = agg["max_demand"].astype(int)
    agg["total_period_liters"] = agg["total_period"].astype(int)
    agg["share_pct"] = (
        100 * agg["total_period"] / agg["total_period"].sum()
    ).round(2)
    return agg.drop(columns=["total_period"])
