"""Deep learning forecasting configuration."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "delhi_water_dataset.csv"
ARTIFACTS_DIR = ROOT / "ml" / "artifacts"
PROCESSED_PATH = ARTIFACTS_DIR / "processed_panel.csv"

# Sequence forecasting
LOOKBACK = 30
HORIZON = 7
TRAIN_RATIO = 0.7
VAL_RATIO = 0.15

# Features (multivariate)
TARGET_COL = "water_demand"
RAW_FEATURES = ["temperature", "rainfall", "industrial_index", "population"]
ZONE_COL = "zone"

# Training
BATCH_SIZE = 32
EPOCHS = 40
LEARNING_RATE = 1e-3
PATIENCE = 8
HIDDEN_SIZE = 128
NUM_LAYERS = 2
DROPOUT = 0.2
TRANSFORMER_HEADS = 4
TRANSFORMER_LAYERS = 2
D_MODEL = 64

MODELS = ("lstm", "gru", "transformer")
RANDOM_SEED = 42
