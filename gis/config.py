"""GIS module configuration."""

from pathlib import Path

GIS_ROOT = Path(__file__).resolve().parent
DATA_DIR = GIS_ROOT / "data"
ZONES_GEOJSON = DATA_DIR / "delhi_zones.geojson"
ASSETS_GEOJSON = DATA_DIR / "water_assets.geojson"

# Delhi NCR map center
MAP_CENTER = (28.6139, 77.2090)
MAP_ZOOM = 11

# Default supply per zone (liters/day) — override via UI
DEFAULT_ZONE_SUPPLY = {
    "North Delhi": 4_900_000_000,
    "South Delhi": 4_850_000_000,
    "East Delhi": 4_800_000_000,
    "West Delhi": 4_750_000_000,
    "Central Delhi": 4_950_000_000,
}

# Mapbox (optional) — set MAPBOX_TOKEN env for Mapbox tiles
MAPBOX_STYLE = "mapbox/streets-v12"

# Risk thresholds (%)
RISK_LOW = 0
RISK_MEDIUM = 15
RISK_HIGH = 40
RISK_CRITICAL = 70
