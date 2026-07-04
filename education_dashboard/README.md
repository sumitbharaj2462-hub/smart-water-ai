# Global Education and Development Intelligence Dashboard

This is a self-contained browser dashboard built from selected indicators in `DS.zip`.

## Build the dashboard data

```powershell
python scripts/build_education_dashboard_data.py
```

The script reads `C:\Users\DELL\Desktop\DS.zip` by default and writes:

```text
education_dashboard/data/dashboard_data.json
```

You can also pass a custom zip path and output path:

```powershell
python scripts/build_education_dashboard_data.py "C:\path\to\DS.zip" "education_dashboard\data\dashboard_data.json"
```

## Run locally

```powershell
python -m http.server 8765 --directory education_dashboard
```

Open:

```text
http://localhost:8765
```

## What it includes

- Country and region filters
- Metric filters across education, development, R&D, technology, health, and education quality
- KPI cards
- Country trend comparison
- Regional average chart
- Education/development scatter chart
- Latest country ranking table

The dashboard uses plain HTML, CSS, JavaScript, and Python standard library only.
