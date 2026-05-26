"""
AquaOps Explainable AI (XAI) Dashboard — SHAP + LIME model interpretability.

Run: streamlit run dashboard_xai.py
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from xai.explainer import (
    FEATURE_COLUMNS,
    global_feature_importance,
    load_artifacts,
    local_lime_explanation,
    local_shap_explanation,
    transparent_reasoning,
)


def render():
    st.header("Explainable AI (SHAP + LIME)")
    st.caption(
        "Transparent prediction reasoning · global feature importance · "
        "local decision interpretation"
    )

    try:
        model, _encoder, raw, features = load_artifacts()
    except FileNotFoundError:
        st.error("Model artifacts not found. Run `python train_model.py` first.")
        return
    except Exception as exc:
        st.error(f"Failed to load explainability artifacts: {exc}")
        return

    tab1, tab2, tab3 = st.tabs(
        ["Global Importance", "Local Explanation", "Decision Interpretation"]
    )

    with tab1:
        st.subheader("Global Feature Importance")
        try:
            _, shap_values, importance = global_feature_importance(model, features)
        except Exception as exc:
            st.error(
                "SHAP unavailable. Install dependencies: "
                "`pip install -r requirements-xai.txt`\n\n"
                f"{exc}"
            )
            return

        c1, c2 = st.columns([1, 1])
        with c1:
            st.dataframe(importance, use_container_width=True, hide_index=True)
        with c2:
            fig, ax = plt.subplots(figsize=(7, 4))
            ax.barh(
                importance["feature"][::-1],
                importance["importance"][::-1],
                color="#2563eb",
            )
            ax.set_xlabel("Mean |SHAP value|")
            ax.set_title("Global feature importance (SHAP)")
            st.pyplot(fig)

    with tab2:
        st.subheader("Local Explanation Dashboard")
        row_idx = st.slider(
            "Select historical sample", 0, len(raw) - 1, len(raw) - 1
        )
        row = raw.iloc[row_idx]
        zone = row["zone"]
        row_df = pd.DataFrame([row[FEATURE_COLUMNS]])
        prediction = float(model.predict(row_df)[0])

        st.write(
            f"**Sample context:** `{row['date'].date()}` · **Zone:** {zone} · "
            f"**Actual:** {int(row['water_demand']):,} L/day"
        )
        st.metric("Model prediction", f"{int(prediction):,} L/day")

        shap_row, expected = local_shap_explanation(model, row_df)
        shap_local = pd.DataFrame(
            {"feature": FEATURE_COLUMNS, "shap_value": shap_row}
        ).sort_values("shap_value", key=lambda s: s.abs(), ascending=False)

        fig2, ax2 = plt.subplots(figsize=(7, 4))
        colors = [
            "#16a34a" if v >= 0 else "#dc2626"
            for v in shap_local["shap_value"]
        ]
        ax2.barh(
            shap_local["feature"][::-1],
            shap_local["shap_value"][::-1],
            color=colors[::-1],
        )
        ax2.axvline(0, color="#111827", linewidth=1)
        ax2.set_title(f"Local SHAP contributions (baseline: {expected:,.0f})")
        ax2.set_xlabel("Contribution to prediction (L/day)")
        st.pyplot(fig2)
        st.dataframe(shap_local, use_container_width=True, hide_index=True)

        st.markdown("### LIME local explanation")
        try:
            lime_exp = local_lime_explanation(model, features, row_df)
            lime_df = pd.DataFrame(lime_exp.as_list(), columns=["Rule", "Weight"])
            st.dataframe(lime_df, use_container_width=True, hide_index=True)
            fig3, ax3 = plt.subplots(figsize=(7, 4))
            ax3.barh(
                lime_df["Rule"][::-1],
                lime_df["Weight"][::-1],
                color=[
                    "#0ea5e9" if w >= 0 else "#f97316"
                    for w in lime_df["Weight"][::-1]
                ],
            )
            ax3.set_title("LIME local decision factors")
            st.pyplot(fig3)
        except Exception as exc:
            st.warning(f"LIME explanation unavailable: {exc}")

    with tab3:
        st.subheader("Transparent Prediction Reasoning")
        zone_choice = st.selectbox(
            "Zone for explanation",
            [
                "North Delhi",
                "South Delhi",
                "East Delhi",
                "West Delhi",
                "Central Delhi",
            ],
        )
        latest = raw[raw["zone"] == zone_choice].sort_values("date").tail(1)
        if latest.empty:
            st.info("No data for selected zone.")
            return
        sample = latest.iloc[0]
        sample_df = pd.DataFrame([sample[FEATURE_COLUMNS]])
        pred = float(model.predict(sample_df)[0])
        shap_row2, _ = local_shap_explanation(model, sample_df)
        st.markdown(
            transparent_reasoning(zone_choice, pred, shap_row2, sample[FEATURE_COLUMNS])
        )

        st.markdown("### What this means for administrators")
        st.info(
            "Use this panel to justify operational decisions with interpretable "
            "model drivers. Pair SHAP/LIME outputs with GIS risk and shortage "
            "summaries for transparent governance."
        )


if __name__ == "__main__":
    st.set_page_config(
        page_title="AquaOps Explainable AI",
        page_icon="🔍",
        layout="wide",
    )
    st.info("**Tip:** All modules are in the unified app → run `streamlit run dashboard.py` or use individual dashboards.")
    render()
