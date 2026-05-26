# Smart Urban Water Management Platform — Delhi NCR

## Run the unified dashboard

```powershell
cd "c:\Users\DELL\Downloads\Project dataset\WATER"
python -m pip install -r requirements-ml.txt -r requirements-gis.txt -r requirements-assistant.txt -r requirements-xai.txt
python -m streamlit run dashboard.py
```

## Windows setup (when python/pip/streamlit are not recognized)

Check which launcher you have:

```powershell
Get-Command python -ErrorAction SilentlyContinue
Get-Command py -ErrorAction SilentlyContinue
```

If neither `python` nor `py` exists, install Python 3.11+ from https://www.python.org/downloads/windows/ and ensure:
- "Add python.exe to PATH" is enabled in the installer, or add it manually
- Windows Settings → Apps → Advanced app settings → App execution aliases: disable python.exe/python3.exe aliases

Create a virtual environment:

```powershell
cd "c:\Users\DELL\Downloads\Project dataset\WATER"
py -m venv .venv
```

Activate it:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Install deps and run:

```powershell
python -m pip install -r requirements-ml.txt -r requirements-gis.txt -r requirements-assistant.txt -r requirements-xai.txt
python -m streamlit run dashboard.py
```

Use the **sidebar** to switch modules:

- **Overview** — platform status & zone risks
- **Demand Prediction** — Random Forest + recommendations
- **Explainable AI** — SHAP/LIME importance and local reasoning
- **Deep Learning Forecast** — LSTM / GRU / Transformer
- **GIS Maps** — heatmaps, consumption, tanker routes
- **AI Assistant** — AquaOps operational chat & reports

## First-time setup

```powershell
python generate_datset.py
python train_model.py
python -m ml.train_deep --epochs 30
```

## Weather API setup (optional, for live features)

Set at least one API key to enable real-time weather (used by Demand Prediction, GIS risk scoring, and the AI assistant snapshot).

```powershell
$env:WEATHER_PROVIDER="openweather"   # or "weatherapi"
$env:OPENWEATHER_API_KEY="your_key_here"
$env:WEATHERAPI_KEY="your_key_here"
```

Optional tuning:

```powershell
$env:WEATHER_TIMEOUT_SECONDS="3"
$env:WEATHER_CACHE_TTL_SECONDS="600"
```

## Legacy standalone apps (optional)

| Command | Same module in unified dashboard |
|---------|----------------------------------|
| `streamlit run dashboard_forecast.py` | Deep Learning Forecast |
| `streamlit run dashboard_gis.py` | GIS Maps |
| `streamlit run dashboard_assistant.py` | AI Assistant |

**Always use `streamlit run dashboard.py` for the full platform.**
