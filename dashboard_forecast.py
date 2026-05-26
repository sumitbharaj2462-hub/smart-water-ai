"""
Deep Learning Water Demand Forecasting Dashboard
LSTM / GRU / Transformer + seasonality, trend, anomaly views.

Run: streamlit run dashboard_forecast.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from ml.config import ARTIFACTS_DIR
from ml.data.preprocessing import build_panel
from ml.forecast import forecast_zone

st.set_page_config(page_title="Deep Learning Water Forecast", layout="wide")
st.info("**Tip:** All modules are in the unified app → run `streamlit run dashboard.py` and choose **Deep Learning Forecast** in the sidebar.")
st.title("Deep Learning Water Demand Forecasting")
st.caption("LSTM · GRU · Transformer — multivariate time-series with seasonality, trend & anomaly detection")

ARTIFACTS = ARTIFACTS_DIR
panel = build_panel(save=False)

# Sidebar
st.sidebar.header("Forecast Settings")
zones = sorted(panel["zone"].unique())
zone = st.sidebar.selectbox("Zone", zones)
model_choice = st.sidebar.selectbox(
    "Model",
    ["best", "lstm", "gru", "transformer"],
)
horizon = st.sidebar.slider("Forecast horizon (days)", 1, 14, 7)

best_path = ARTIFACTS / "best_model_name.txt"
if not best_path.exists():
    st.warning(
        "No trained deep learning models found. Run: `python -m ml.train_deep`"
    )
    st.code("pip install -r requirements-ml.txt\npython -m ml.train_deep --epochs 30")
    st.stop()

model_name = None if model_choice == "best" else model_choice

tab1, tab2, tab3, tab4 = st.tabs(
    ["Forecast", "Seasonality", "Trend", "Anomalies"]
)

with tab1:
    try:
        result = forecast_zone(zone, model_name, horizon)
        st.subheader(f"{zone} — {result['model'].upper()} forecast")
        fc = pd.DataFrame(result["forecast"])
        fc["date"] = pd.to_datetime(fc["date"])
        st.metric("Last actual demand (L/day)", f"{result['last_actual_demand']:,}")
        st.line_chart(fc.set_index("date")["water_demand_liters"])

        hist = panel[panel["zone"] == zone].sort_values("date").tail(90)
        st.subheader("Recent history (90 days)")
        st.line_chart(hist.set_index("date")["water_demand"])

        if st.button("Show forecast table"):
            st.dataframe(fc, use_container_width=True)
    except Exception as exc:
        st.error(f"Forecast failed: {exc}")

with tab2:
    path = ARTIFACTS / "analysis" / "seasonality_report.json"
    if path.exists():
        report = json.loads(path.read_text(encoding="utf-8"))
        zr = report.get("zones", {}).get(zone, {})
        if zr:
            st.json(zr)
            strength = zr.get("seasonal_strength", 0)
            st.progress(min(1.0, strength or 0), text=f"Seasonal strength: {strength}")
        else:
            st.info("No seasonality data for this zone.")
    else:
        st.info("Run training to generate seasonality report.")

with tab3:
    path = ARTIFACTS / "analysis" / "trend_report.json"
    if path.exists():
        report = json.loads(path.read_text(encoding="utf-8"))
        zr = report.get("zones", {}).get(zone, {})
        if zr:
            c1, c2, c3 = st.columns(3)
            c1.metric("Trend", zr.get("trend_direction", "—"))
            c2.metric("Slope (L/day)", zr.get("slope_per_day", "—"))
            c3.metric("R²", zr.get("r_squared", "—"))
            st.json(zr)
    else:
        st.info("Run training to generate trend report.")

with tab4:
    anom_path = ARTIFACTS / "analysis" / "anomalies.csv"
    sum_path = ARTIFACTS / "analysis" / "anomaly_report.json"
    if anom_path.exists():
        adf = pd.read_csv(anom_path)
        adf = adf[adf["zone"] == zone]
        flagged = adf[adf["anomaly"] == True]  # noqa: E712
        st.metric("Anomalies detected", len(flagged))
        if len(flagged) > 0:
            st.dataframe(
                flagged[["date", "actual", "predicted", "residual", "anomaly_score"]].head(50),
                use_container_width=True,
            )
        if sum_path.exists():
            summary = json.loads(sum_path.read_text(encoding="utf-8"))
            st.json(summary.get("zones", {}).get(zone, {}))
    else:
        st.info("Run training to generate anomaly report.")

# Model comparison
st.sidebar.divider()
results_path = ARTIFACTS / "training_results.json"
if results_path.exists():
    st.sidebar.subheader("Model comparison (test set)")
    results = json.loads(results_path.read_text(encoding="utf-8"))
    cmp_df = pd.DataFrame(results).T[["mae", "rmse", "r2", "mape_pct"]]
    st.sidebar.dataframe(cmp_df.round(4))
