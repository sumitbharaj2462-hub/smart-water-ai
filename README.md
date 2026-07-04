# Global Education and Development Dashboard

Interactive Streamlit dashboard for exploring global education, health, technology, and development indicators across countries.

## Live app

Deploy on [Streamlit Community Cloud](https://share.streamlit.io):

- **Repository:** `sumitbharaj2462-hub/smart-water-ai`
- **Main file:** `streamlit_dashboard/app.py`
- **Branch:** `main`

## Run locally

```powershell
pip install -r requirements.txt
streamlit run streamlit_dashboard/app.py
```

Open http://localhost:8501

## Rebuild data (optional)

The dashboard reads `education_dashboard/data/dashboard_data.json`. To regenerate from source CSVs in `DS.zip`:

```powershell
python scripts/build_education_dashboard_data.py
```

## Project layout

- `streamlit_dashboard/app.py` — Streamlit UI (Plotly, Seaborn, pandas)
- `streamlit_dashboard/data_loader.py` — JSON → DataFrame helpers
- `education_dashboard/` — Original HTML/CSS dashboard and bundled data
- `scripts/build_education_dashboard_data.py` — Data pipeline from DS.zip
