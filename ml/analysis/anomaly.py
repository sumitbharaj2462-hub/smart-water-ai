"""Anomaly detection: forecast residuals + Isolation Forest."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from ml.config import ARTIFACTS_DIR, TARGET_COL
from ml.data.preprocessing import get_feature_columns


def detect_anomalies(
    df: pd.DataFrame,
    actual: np.ndarray,
    predicted: np.ndarray,
    residual_threshold_pct: float = 95,
    contamination: float = 0.05,
) -> pd.DataFrame:
    """
    Flag anomalies where:
    - |residual| exceeds percentile threshold (forecast-based)
    - Isolation Forest on multivariate features (point anomalies)
    """
    out = df.copy()
    residual = actual - predicted
    abs_res = np.abs(residual)
    threshold = np.percentile(abs_res, residual_threshold_pct)

    feature_cols = [c for c in get_feature_columns() if c in out.columns]
    if len(feature_cols) >= 3:
        iso = IsolationForest(contamination=contamination, random_state=42)
        iso_pred = iso.fit_predict(out[feature_cols].fillna(0))
        out["isolation_anomaly"] = iso_pred == -1
    else:
        out["isolation_anomaly"] = False

    out["residual"] = residual
    out["abs_residual"] = abs_res
    out["residual_anomaly"] = abs_res > threshold
    out["anomaly"] = out["residual_anomaly"] | out["isolation_anomaly"]
    out["anomaly_score"] = abs_res / (threshold + 1e-9)
    return out


def run_anomaly_report(
    panel: pd.DataFrame,
    predictions: pd.DataFrame,
    output_dir: Path | None = None,
) -> dict:
    """
    predictions: columns [date, zone, predicted, actual]
    """
    output_dir = output_dir or ARTIFACTS_DIR / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    merged = predictions.merge(
        panel[["date", "zone", TARGET_COL]],
        on=["date", "zone"],
        how="left",
    )
    merged["actual"] = merged.get("actual", merged[TARGET_COL])

    all_flags = []
    summary: dict = {"zones": {}}

    for zone, grp in merged.groupby("zone"):
        grp = grp.sort_values("date").reset_index(drop=True)
        zone_panel = panel[panel["zone"] == zone].sort_values("date")
        flagged = detect_anomalies(
            zone_panel.tail(len(grp)).reset_index(drop=True),
            grp["actual"].values,
            grp["predicted"].values,
        )
        flagged["date"] = grp["date"].values
        flagged["zone"] = zone
        flagged["predicted"] = grp["predicted"].values
        flagged["actual"] = grp["actual"].values
        all_flags.append(flagged)

        n_anom = int(flagged["anomaly"].sum())
        summary["zones"][zone] = {
            "total_points": len(flagged),
            "anomalies_detected": n_anom,
            "anomaly_rate_pct": round(100 * n_anom / max(len(flagged), 1), 2),
            "residual_threshold": round(float(flagged["abs_residual"].quantile(0.95)), 2),
        }

    if all_flags:
        combined = pd.concat(all_flags, ignore_index=True)
        combined.to_csv(output_dir / "anomalies.csv", index=False)

    summary_path = output_dir / "anomaly_report.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
