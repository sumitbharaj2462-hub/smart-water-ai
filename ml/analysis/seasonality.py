"""Seasonality detection via decomposition and autocorrelation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import acf

from ml.config import ARTIFACTS_DIR, TARGET_COL


def _dominant_period(acf_vals: np.ndarray, min_lag: int = 7) -> int | None:
    if len(acf_vals) <= min_lag + 1:
        return None
    search = acf_vals[min_lag : min(len(acf_vals) - 1, 90)]
    if len(search) == 0:
        return None
    peak = int(np.argmax(search)) + min_lag
    if acf_vals[peak] < 0.25:
        return None
    return peak


def detect_seasonality(
    series: pd.Series,
    period: int | None = None,
    zone: str = "all",
) -> dict:
    """
    STL-style seasonal decomposition + ACF peak detection.
    """
    series = series.dropna().astype(float)
    n = len(series)
    result: dict = {"zone": zone, "n_observations": n}

    if n < 14:
        result["status"] = "insufficient_data"
        return result

    if period is None:
        acf_vals = acf(series, nlags=min(60, n // 2), fft=True)
        period = _dominant_period(acf_vals) or 7

    period = max(2, min(period, n // 2))
    result["detected_period"] = period

    try:
        decomp = seasonal_decompose(
            series, model="additive", period=period, extrapolate_trend="freq"
        )
        seasonal_strength = float(
            np.var(decomp.seasonal) / (np.var(series) + 1e-9)
        )
        result["seasonal_strength"] = round(seasonal_strength, 4)
        result["seasonal_amplitude"] = round(float(decomp.seasonal.max() - decomp.seasonal.min()), 2)
        result["status"] = "ok"
        result["interpretation"] = (
            "strong seasonal pattern"
            if seasonal_strength > 0.3
            else "moderate seasonal pattern"
            if seasonal_strength > 0.1
            else "weak seasonal pattern"
        )
    except Exception as exc:
        result["status"] = "decompose_failed"
        result["error"] = str(exc)

    acf_vals = acf(series, nlags=min(30, n // 2), fft=True)
    result["acf_lag7"] = round(float(acf_vals[7]) if len(acf_vals) > 7 else 0, 4)
    return result


def run_seasonality_report(panel: pd.DataFrame, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or ARTIFACTS_DIR / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {"zones": {}}
    for zone, grp in panel.groupby("zone"):
        grp = grp.sort_values("date")
        report["zones"][zone] = detect_seasonality(grp[TARGET_COL], zone=zone)

    path = output_dir / "seasonality_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
