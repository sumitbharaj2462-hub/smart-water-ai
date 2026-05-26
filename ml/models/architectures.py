"""LSTM, GRU, and Transformer encoders for multivariate water demand forecasting."""

from __future__ import annotations

import math

import torch
import torch.nn as nn

from ml.config import (
    D_MODEL,
    DROPOUT,
    HIDDEN_SIZE,
    HORIZON,
    NUM_LAYERS,
    TRANSFORMER_HEADS,
    TRANSFORMER_LAYERS,
)


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 512, dropout: float = DROPOUT):
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div)
        pe[:, 1::2] = torch.cos(position * div)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


class _SeqEncoderHead(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, horizon: int, dropout: float):
        super().__init__()
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, horizon),
        )
        self.input_size = input_size

    def forward_head(self, encoded: torch.Tensor) -> torch.Tensor:
        return self.head(encoded)


class LSTMForecaster(_SeqEncoderHead):
    def __init__(
        self,
        input_size: int,
        hidden_size: int = HIDDEN_SIZE,
        num_layers: int = NUM_LAYERS,
        horizon: int = HORIZON,
        dropout: float = DROPOUT,
    ):
        super().__init__(input_size, hidden_size, horizon, dropout)
        self.lstm = nn.LSTM(
            input_size,
            hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.forward_head(out[:, -1, :])


class GRUForecaster(_SeqEncoderHead):
    def __init__(
        self,
        input_size: int,
        hidden_size: int = HIDDEN_SIZE,
        num_layers: int = NUM_LAYERS,
        horizon: int = HORIZON,
        dropout: float = DROPOUT,
    ):
        super().__init__(input_size, hidden_size, horizon, dropout)
        self.gru = nn.GRU(
            input_size,
            hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.gru(x)
        return self.forward_head(out[:, -1, :])


class TransformerForecaster(nn.Module):
    def __init__(
        self,
        input_size: int,
        d_model: int = D_MODEL,
        nhead: int = TRANSFORMER_HEADS,
        num_layers: int = TRANSFORMER_LAYERS,
        horizon: int = HORIZON,
        dropout: float = DROPOUT,
    ):
        super().__init__()
        self.input_proj = nn.Linear(input_size, d_model)
        self.pos_encoder = PositionalEncoding(d_model, dropout=dropout)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.head = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, horizon),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_proj(x)
        x = self.pos_encoder(x)
        x = self.encoder(x)
        return self.head(x[:, -1, :])


def build_model(name: str, input_size: int) -> nn.Module:
    name = name.lower()
    if name == "lstm":
        return LSTMForecaster(input_size)
    if name == "gru":
        return GRUForecaster(input_size)
    if name == "transformer":
        return TransformerForecaster(input_size)
    raise ValueError(f"Unknown model: {name}. Use lstm, gru, or transformer.")
