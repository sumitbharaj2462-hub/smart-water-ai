from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "water_demand_model.pkl"
ENCODER_PATH = ROOT / "zone_encoder.pkl"
DATA_PATH = ROOT / "delhi_water_dataset.csv"

FEATURE_COLUMNS = [
    "population",
    "temperature",
    "rainfall",
    "industrial_index",
    "month",
    "day",
    "zone_encoded",
]


def _build_feature_table() -> pd.DataFrame:
    data = pd.read_csv(DATA_PATH)
    data["date"] = pd.to_datetime(data["date"])
    data["month"] = data["date"].dt.month
    data["day"] = data["date"].dt.day
    le = joblib.load(ENCODER_PATH)
    data["zone_encoded"] = le.transform(data["zone"])
    return data


def load_artifacts() -> tuple[Any, Any, pd.DataFrame, pd.DataFrame]:
    model = joblib.load(MODEL_PATH)
    encoder = joblib.load(ENCODER_PATH)
    raw = _build_feature_table()
    features = raw[FEATURE_COLUMNS].copy()
    return model, encoder, raw, features


def global_feature_importance(
    model: Any,
    features: pd.DataFrame,
    sample_size: int = 400,
):
    import shap

    sample = features.sample(min(sample_size, len(features)), random_state=42)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(sample)
    mean_abs = np.abs(shap_values).mean(axis=0)
    importance = (
        pd.DataFrame({"feature": FEATURE_COLUMNS, "importance": mean_abs})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    return sample, shap_values, importance


def local_shap_explanation(model, row_df):
    import shap
    import numpy as np

    explainer = shap.TreeExplainer(model)

    shap_values = explainer.shap_values(row_df)

    expected_raw = explainer.expected_value

    if isinstance(expected_raw, (list, np.ndarray)):
        expected = float(np.array(expected_raw).flatten()[0])
    else:
        expected = float(expected_raw)

    return shap_values[0], expected


def local_lime_explanation(
    model: Any,
    train_features: pd.DataFrame,
    row_df: pd.DataFrame,
):
    from lime.lime_tabular import LimeTabularExplainer

    explainer = LimeTabularExplainer(
        training_data=train_features.values,
        feature_names=FEATURE_COLUMNS,
        mode="regression",
        random_state=42,
    )
    exp = explainer.explain_instance(
        row_df.iloc[0].values.astype(float),
        model.predict,
        num_features=min(7, len(FEATURE_COLUMNS)),
    )
    return exp


def transparent_reasoning(
    zone: str,
    prediction: float,
    shap_row: np.ndarray,
    feature_row: pd.Series,
) -> str:
    contributions = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "shap": shap_row,
            "value": [feature_row[c] for c in FEATURE_COLUMNS],
        }
    )
    top = contributions.reindex(
        contributions["shap"].abs().sort_values(ascending=False).index
    ).head(4)
    lines = [
        f"Predicted demand for **{zone}** is **{int(prediction):,} L/day**.",
        "",
        "Top drivers for this prediction:",
    ]
    for _, row in top.iterrows():
        direction = "increases" if row["shap"] >= 0 else "reduces"
        lines.append(
            f"- `{row['feature']}` = **{row['value']}** {direction} demand "
            f"by ~**{abs(row['shap']):,.0f} L/day**"
        )
    lines.append("")
    lines.append(
        "Interpretation note: SHAP values quantify each feature's contribution "
        "relative to the model baseline."
    )
    return "\n".join(lines)
