# Explainable AI for Water Demand Prediction

This module adds transparent model interpretation using **SHAP** and **LIME**.

## Included capabilities

- Global feature importance graphs (SHAP mean absolute values)
- Local prediction explanations (SHAP contribution chart per sample)
- LIME rule-based local decision interpretation
- Natural-language transparent reasoning for administrators

## Run

```powershell
pip install -r requirements-xai.txt
streamlit run dashboard.py
```

Then open **Explainable AI** from the sidebar.

## Notes

- Current XAI integrates with the Random Forest model (`water_demand_model.pkl`).
- If models are missing, train first with:

```powershell
python train_model.py
```
