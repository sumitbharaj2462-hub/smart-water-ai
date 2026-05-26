"""Trend analysis: linear slope, rolling means, direction."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from ml.config import ARTIFACTS_DIR, TARGET_COL


def analyze_trend(series: pd.Series, zone: str = "all") -> dict:
    series = series.dropna().astype(float)
    n = len(series)
    if n < 10:
        return {"zone": zone, "status": "insufficient_data", "n_observations": n}

    x = np.arange(n)
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, series.values)

    roll_30 = series.rolling(min(30, n), min_periods=1).mean()
    recent = float(roll_30.iloc[-1])
    prior = float(roll_30.iloc[max(0, len(roll_30) - 31)])
    mom_change_pct = ((recent - prior) / (abs(prior) + 1e-9)) * 100

    if slope > 0 and p_value < 0.05:
        direction = "increasing"
    elif slope < 0 and p_value < 0.05:
        direction = "decreasing"
    else:
        direction = "stable"

    return {
        "zone": zone,
        "status": "ok",
        "n_observations": n,
        "slope_per_day": round(float(slope), 2),
        "r_squared": round(float(r_value**2), 4),
        "p_value": round(float(p_value), 6),
        "trend_direction": direction,
        "rolling_30d_change_pct": round(mom_change_pct, 2),
        "latest_value": round(float(series.iloc[-1]), 0),
    }


def run_trend_report(panel: pd.DataFrame, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or ARTIFACTS_DIR / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {"zones": {}}
    for zone, grp in panel.groupby("zone"):
        grp = grp.sort_values("date")
        report["zones"][zone] = analyze_trend(grp[TARGET_COL], zone=zone)

    path = output_dir / "trend_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
