"""PyTorch sliding-window datasets for multivariate forecasting."""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from ml.config import BATCH_SIZE, HORIZON, LOOKBACK, TARGET_COL, TRAIN_RATIO, VAL_RATIO
from ml.data.preprocessing import (
    build_panel,
    fit_scalers,
    get_feature_columns,
    transform_df,
)


class WaterDemandSequenceDataset(Dataset):
    def __init__(
        self,
        df: pd.DataFrame,
        feature_cols: list[str],
        lookback: int = LOOKBACK,
        horizon: int = HORIZON,
    ):
        self.lookback = lookback
        self.horizon = horizon
        self.features = feature_cols
        self.sequences: list[tuple[np.ndarray, np.ndarray]] = []

        for _, grp in df.groupby("zone"):
            grp = grp.sort_values("date").reset_index(drop=True)
            x = grp[feature_cols].values.astype(np.float32)
            y = grp[TARGET_COL].values.astype(np.float32)
            for i in range(len(grp) - lookback - horizon + 1):
                self.sequences.append(
                    (x[i : i + lookback], y[i + lookback : i + lookback + horizon])
                )

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, idx: int):
        x, y = self.sequences[idx]
        return torch.from_numpy(x), torch.from_numpy(y)


def _split_panel(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = np.sort(panel["date"].unique())
    n = len(dates)
    t1 = int(n * TRAIN_RATIO)
    t2 = int(n * (TRAIN_RATIO + VAL_RATIO))
    train_dates = set(dates[:t1])
    val_dates = set(dates[t1:t2])
    test_dates = set(dates[t2:])
    return (
        panel[panel["date"].isin(train_dates)].copy(),
        panel[panel["date"].isin(val_dates)].copy(),
        panel[panel["date"].isin(test_dates)].copy(),
    )


def create_dataloaders(
    panel: pd.DataFrame | None = None,
) -> tuple[DataLoader, DataLoader, DataLoader, list[str], object, object, pd.DataFrame]:
    if panel is None:
        panel = build_panel()
    feature_cols = get_feature_columns()
    train_df, val_df, test_df = _split_panel(panel)
    x_scaler, y_scaler = fit_scalers(train_df, feature_cols)

    train_t = transform_df(train_df, feature_cols, x_scaler, y_scaler)
    val_t = transform_df(val_df, feature_cols, x_scaler, y_scaler)
    test_t = transform_df(test_df, feature_cols, x_scaler, y_scaler)

    train_ds = WaterDemandSequenceDataset(train_t, feature_cols)
    val_ds = WaterDemandSequenceDataset(val_t, feature_cols)
    test_ds = WaterDemandSequenceDataset(test_t, feature_cols)

    loaders = (
        DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True),
        DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False),
        DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False),
    )
    return (*loaders, feature_cols, x_scaler, y_scaler, panel)
