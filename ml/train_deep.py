"""
Train LSTM, GRU, and Transformer models for multivariate water demand forecasting.
Also runs seasonality, trend, and anomaly analysis.

Usage (from project root):
  python -m ml.train_deep
  python -m ml.train_deep --models lstm gru --epochs 25
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.analysis.anomaly import run_anomaly_report
from ml.analysis.seasonality import run_seasonality_report
from ml.analysis.trend import run_trend_report
from ml.config import ARTIFACTS_DIR, EPOCHS, MODELS, TARGET_COL
from ml.data.dataset import create_dataloaders
from ml.data.preprocessing import build_panel
from ml.training.trainer import DeepLearningTrainer


def _collect_test_predictions(
    trainer: DeepLearningTrainer,
    test_loader,
    panel: pd.DataFrame,
    y_scaler,
) -> pd.DataFrame:
    from ml.config import LOOKBACK, HORIZON

    preds, actuals = trainer.predict_loader(test_loader, y_scaler)
    dates_sorted = sorted(panel["date"].unique())
    test_cutoff = dates_sorted[int(len(dates_sorted) * 0.85)]

    rows = []
    idx = 0
    for zone, grp in panel.groupby("zone"):
        grp = grp.sort_values("date").reset_index(drop=True)
        for i in range(len(grp) - LOOKBACK - HORIZON + 1):
            if grp.loc[i + LOOKBACK, "date"] < test_cutoff:
                continue
            if idx >= len(preds):
                break
            rows.append(
                {
                    "date": grp.loc[i + LOOKBACK, "date"],
                    "zone": zone,
                    "predicted": float(preds[idx, 0]),
                    "actual": float(actuals[idx, 0]),
                }
            )
            idx += 1
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train deep learning forecasters")
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    args = parser.parse_args()

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    print("Building zone-level multivariate panel...")
    panel = build_panel()

    print("Running seasonality & trend analysis...")
    run_seasonality_report(panel)
    run_trend_report(panel)

    print("Creating sequence dataloaders...")
    train_loader, val_loader, test_loader, feature_cols, x_scaler, y_scaler, _ = (
        create_dataloaders(panel)
    )
    input_size = len(feature_cols)

    joblib.dump(x_scaler, ARTIFACTS_DIR / "x_scaler.pkl")
    joblib.dump(y_scaler, ARTIFACTS_DIR / "y_scaler.pkl")
    (ARTIFACTS_DIR / "feature_columns.json").write_text(
        json.dumps(feature_cols, indent=2), encoding="utf-8"
    )

    results: dict = {}
    best_name, best_mae = None, float("inf")

    for name in args.models:
        print(f"\n{'='*50}\nTraining {name.upper()}...\n{'='*50}")
        trainer = DeepLearningTrainer(name, input_size)
        trainer.fit(train_loader, val_loader, epochs=args.epochs)
        metrics = trainer.evaluate(test_loader, y_scaler)
        results[name] = metrics
        print(f"  Test MAE:  {metrics['mae']:,.0f}")
        print(f"  Test RMSE: {metrics['rmse']:,.0f}")
        print(f"  Test R2:   {metrics['r2']:.4f}")
        print(f"  Test MAPE: {metrics['mape_pct']:.2f}%")

        ckpt_path = ARTIFACTS_DIR / f"{name}_model.pt"
        trainer.save(
            ckpt_path,
            meta={
                "feature_cols": feature_cols,
                "metrics": metrics,
                "history": trainer.history[-5:],
            },
        )

        if metrics["mae"] < best_mae:
            best_mae = metrics["mae"]
            best_name = name

    # Save best model copy
    if best_name:
        import shutil

        shutil.copy(ARTIFACTS_DIR / f"{best_name}_model.pt", ARTIFACTS_DIR / "best_model.pt")
        (ARTIFACTS_DIR / "best_model_name.txt").write_text(best_name, encoding="utf-8")
        print(f"\nBest model: {best_name.upper()} (MAE={best_mae:,.0f})")

    (ARTIFACTS_DIR / "training_results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    # Anomaly detection on best model predictions
    if best_name:
        print("\nRunning anomaly detection on test forecasts...")
        best_trainer = DeepLearningTrainer.load(
            ARTIFACTS_DIR / "best_model.pt", input_size
        )
        pred_df = _collect_test_predictions(best_trainer, test_loader, panel, y_scaler)
        pred_df.to_csv(ARTIFACTS_DIR / "test_predictions.csv", index=False)
        anomaly_summary = run_anomaly_report(panel, pred_df)
        print(json.dumps(anomaly_summary, indent=2))

    print(f"\nArtifacts saved to: {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
