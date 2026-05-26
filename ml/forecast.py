"""
Generate multi-step water demand forecasts using trained deep learning models.

Usage:
  python -m ml.forecast --zone "North Delhi" --model lstm
  python -m ml.forecast --zone "Central Delhi" --horizon 7
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

from ml.config import ARTIFACTS_DIR, HORIZON, LOOKBACK, TARGET_COL
from ml.data.preprocessing import build_panel, get_feature_columns
from ml.training.trainer import DeepLearningTrainer


def forecast_zone(
    zone: str,
    model_name: str | None = None,
    horizon: int = HORIZON,
) -> dict:
    panel = build_panel(save=False)
    zone_df = panel[panel["zone"] == zone].sort_values("date").reset_index(drop=True)
    if zone_df.empty:
        raise ValueError(f"Unknown zone: {zone}")

    feature_cols = json.loads((ARTIFACTS_DIR / "feature_columns.json").read_text())
    x_scaler = joblib.load(ARTIFACTS_DIR / "x_scaler.pkl")
    y_scaler = joblib.load(ARTIFACTS_DIR / "y_scaler.pkl")

    if model_name is None:
        model_name = (ARTIFACTS_DIR / "best_model_name.txt").read_text().strip()

    ckpt = ARTIFACTS_DIR / f"{model_name}_model.pt"
    if not ckpt.exists():
        ckpt = ARTIFACTS_DIR / "best_model.pt"

    trainer = DeepLearningTrainer.load(ckpt, len(feature_cols))
    trainer.model.eval()

    tail = zone_df.tail(LOOKBACK).copy()
    scaled = tail.copy()
    scaled[feature_cols] = x_scaler.transform(tail[feature_cols])
    scaled[TARGET_COL] = y_scaler.transform(tail[[TARGET_COL]])

    x = torch.from_numpy(scaled[feature_cols].values.astype(np.float32)).unsqueeze(0)
    with torch.no_grad():
        pred_scaled = trainer.model(x.to(trainer.device)).cpu().numpy()[0]

    scale = y_scaler.scale_[0]
    mean = y_scaler.mean_[0]
    pred_liters = pred_scaled * scale + mean

    last_date = pd.to_datetime(zone_df["date"].iloc[-1])
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon, freq="D")

    return {
        "zone": zone,
        "model": model_name,
        "last_observed_date": str(last_date.date()),
        "horizon_days": horizon,
        "forecast": [
            {"date": str(d.date()), "water_demand_liters": int(v)}
            for d, v in zip(future_dates, pred_liters[:horizon])
        ],
        "last_actual_demand": int(zone_df[TARGET_COL].iloc[-1]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zone", default="North Delhi")
    parser.add_argument("--model", default=None, choices=["lstm", "gru", "transformer"])
    parser.add_argument("--horizon", type=int, default=HORIZON)
    args = parser.parse_args()

    result = forecast_zone(args.zone, args.model, args.horizon)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
