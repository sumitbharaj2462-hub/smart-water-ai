"""Training loop for LSTM / GRU / Transformer forecasters."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml.config import (
    ARTIFACTS_DIR,
    EPOCHS,
    LEARNING_RATE,
    PATIENCE,
    RANDOM_SEED,
)
from ml.models.architectures import build_model


class DeepLearningTrainer:
    def __init__(
        self,
        model_name: str,
        input_size: int,
        device: str | None = None,
    ):
        torch.manual_seed(RANDOM_SEED)
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = build_model(model_name, input_size).to(self.device)
        self.criterion = nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=LEARNING_RATE)
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=3
        )
        self.history: list[dict] = []
        self.best_val_loss = float("inf")
        self.patience_counter = 0

    def _run_epoch(self, loader, train: bool = True) -> float:
        self.model.train(train)
        losses = []
        for x, y in loader:
            x, y = x.to(self.device), y.to(self.device)
            if train:
                self.optimizer.zero_grad()
            pred = self.model(x)
            loss = self.criterion(pred, y)
            if train:
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.optimizer.step()
            losses.append(loss.item())
        return float(np.mean(losses))

    def fit(self, train_loader, val_loader, epochs: int = EPOCHS) -> list[dict]:
        for epoch in range(1, epochs + 1):
            train_loss = self._run_epoch(train_loader, train=True)
            val_loss = self._run_epoch(val_loader, train=False)
            self.scheduler.step(val_loss)
            self.history.append(
                {"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss}
            )
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.patience_counter = 0
                self._best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
            else:
                self.patience_counter += 1
            if self.patience_counter >= PATIENCE:
                break
        if hasattr(self, "_best_state"):
            self.model.load_state_dict(self._best_state)
        return self.history

    @torch.no_grad()
    def predict_loader(self, loader, y_scaler) -> tuple[np.ndarray, np.ndarray]:
        self.model.eval()
        preds, actuals = [], []
        for x, y in loader:
            x = x.to(self.device)
            pred = self.model(x).cpu().numpy()
            preds.append(pred)
            actuals.append(y.numpy())
        preds = np.vstack(preds)
        actuals = np.vstack(actuals)

        # Inverse scale (first horizon step for metrics)
        scale = y_scaler.scale_[0]
        mean = y_scaler.mean_[0]
        preds_inv = preds * scale + mean
        actuals_inv = actuals * scale + mean
        return preds_inv, actuals_inv

    def evaluate(self, loader, y_scaler) -> dict:
        preds, actuals = self.predict_loader(loader, y_scaler)
        p1 = preds[:, 0]
        a1 = actuals[:, 0]
        return {
            "mae": float(mean_absolute_error(a1, p1)),
            "rmse": float(np.sqrt(mean_squared_error(a1, p1))),
            "r2": float(r2_score(a1, p1)),
            "mape_pct": float(np.mean(np.abs((a1 - p1) / (np.abs(a1) + 1e-9))) * 100),
        }

    def save(self, path: Path, meta: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state": self.model.state_dict(),
                "model_name": self.model_name,
                "meta": meta,
            },
            path,
        )

    @staticmethod
    def load(path: Path, input_size: int, device: str | None = None) -> "DeepLearningTrainer":
        device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        ckpt = torch.load(path, map_location=device, weights_only=False)
        trainer = DeepLearningTrainer(ckpt["model_name"], input_size, device)
        trainer.model.load_state_dict(ckpt["model_state"])
        trainer._checkpoint_meta = ckpt.get("meta", {})
        return trainer
