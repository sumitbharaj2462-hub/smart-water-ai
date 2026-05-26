"""Build zone-level daily multivariate time series from raw CSV."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler

from ml.config import DATA_PATH, PROCESSED_PATH, RAW_FEATURES, TARGET_COL, ZONE_COL


def _cyclical_encode(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["dow_sin"] = np.sin(2 * np.pi * df["dayofweek"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["dayofweek"] / 7)
    df["day_sin"] = np.sin(2 * np.pi * df["day"] / 31)
    df["day_cos"] = np.cos(2 * np.pi * df["day"] / 31)
    return df


def _add_lags(group: pd.DataFrame, col: str, lags: list[int]) -> pd.DataFrame:
    for lag in lags:
        group[f"{col}_lag_{lag}"] = group[col].shift(lag)
    return group


def build_panel(csv_path: Path | None = None, save: bool = True) -> pd.DataFrame:
    """
    Resample to daily series per zone (interpolate gaps).
    Adds cyclical time features, lags, and rolling statistics.
    """
    path = csv_path or DATA_PATH
    raw = pd.read_csv(path)
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.sort_values(["zone", "date"])

    # Aggregate duplicate date-zone rows
    agg = (
        raw.groupby([ZONE_COL, "date"], as_index=False)
        .agg(
            {
                "population": "first",
                "temperature": "mean",
                "rainfall": "mean",
                "industrial_index": "mean",
                TARGET_COL: "mean",
            }
        )
    )

    frames = []
    for zone, grp in agg.groupby(ZONE_COL):
        grp = grp.set_index("date").sort_index()
        full_idx = pd.date_range(grp.index.min(), grp.index.max(), freq="D")
        grp = grp.reindex(full_idx)
        grp[ZONE_COL] = zone
        numeric = grp.select_dtypes(include=[np.number]).columns
        grp[numeric] = grp[numeric].interpolate(method="linear").ffill().bfill()
        grp["month"] = grp.index.month
        grp["day"] = grp.index.day
        grp["dayofweek"] = grp.index.dayofweek
        grp["year"] = grp.index.year
        grp = _add_lags(grp.reset_index().rename(columns={"index": "date"}), TARGET_COL, [1, 7, 14])
        grp = _add_lags(grp, "temperature", [1])
        grp["demand_roll_mean_7"] = grp[TARGET_COL].rolling(7, min_periods=1).mean()
        grp["demand_roll_std_7"] = grp[TARGET_COL].rolling(7, min_periods=1).std().fillna(0)
        grp = _cyclical_encode(grp)
        grp = grp.dropna().reset_index(drop=True)
        frames.append(grp)

    panel = pd.concat(frames, ignore_index=True)
    le = LabelEncoder()
    panel["zone_encoded"] = le.fit_transform(panel[ZONE_COL])

    if save:
        PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
        panel.to_csv(PROCESSED_PATH, index=False)
        meta = {
            "zones": list(le.classes_),
            "zone_to_id": {z: int(i) for i, z in enumerate(le.classes_)},
        }
        (PROCESSED_PATH.parent / "zone_map.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

    return panel


def get_feature_columns() -> list[str]:
    return (
        RAW_FEATURES
        + [
            "month_sin",
            "month_cos",
            "dow_sin",
            "dow_cos",
            "day_sin",
            "day_cos",
            "water_demand_lag_1",
            "water_demand_lag_7",
            "water_demand_lag_14",
            "temperature_lag_1",
            "demand_roll_mean_7",
            "demand_roll_std_7",
            "zone_encoded",
        ]
    )


def fit_scalers(
    train_df: pd.DataFrame, feature_cols: list[str]
) -> tuple[StandardScaler, StandardScaler]:
    x_scaler = StandardScaler()
    y_scaler = StandardScaler()
    x_scaler.fit(train_df[feature_cols])
    y_scaler.fit(train_df[[TARGET_COL]])
    return x_scaler, y_scaler


def transform_df(
    df: pd.DataFrame,
    feature_cols: list[str],
    x_scaler: StandardScaler,
    y_scaler: StandardScaler,
) -> pd.DataFrame:
    out = df.copy()
    out[feature_cols] = x_scaler.transform(df[feature_cols])
    out[TARGET_COL] = y_scaler.transform(df[[TARGET_COL]])
    return out
