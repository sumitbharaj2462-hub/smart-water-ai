"""
GIS Water Management Dashboard
Interactive maps: shortage heatmaps, zone consumption, tanker routes, live risk.

Run: streamlit run dashboard_gis.py
"""

from __future__ import annotations

import time
from datetime import datetime

import pandas as pd
import streamlit as st

from gis.analytics.consumption import get_zone_consumption
from gis.analytics.risk import compute_zone_risks
from gis.config import DEFAULT_ZONE_SUPPLY, MAP_CENTER
from gis.maps.folium_builder import (
    build_command_center_map,
    build_consumption_map,
    build_risk_monitor_map,
    build_tanker_route_map,
)
from gis.routing.tanker_optimizer import optimize_tanker_routes

try:
    from streamlit_folium import st_folium

    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

st.set_page_config(
    page_title="GIS Water Management",
    page_icon="🗺️",
    layout="wide",
)

st.info("**Tip:** All modules are in the unified app → run `streamlit run dashboard.py` and choose **GIS Maps** in the sidebar.")
st.title("GIS Smart Urban Water Management")
st.caption("Interactive geospatial analytics · Folium/Leaflet · shortage heatmaps · tanker routing · live risk")

# Sidebar — supply overrides & refresh
st.sidebar.header("Geospatial controls")
auto_refresh = st.sidebar.checkbox("Auto-refresh risk (30s)", value=False)
tile_choice = st.sidebar.selectbox(
    "Base map",
    ["OpenStreetMap", "CartoDB positron", "mapbox"],
    help="Set MAPBOX_TOKEN env for Mapbox tiles",
)
tiles = "OpenStreetMap"
if tile_choice == "CartoDB positron":
    tiles = "CartoDB positron"
elif tile_choice == "mapbox":
    tiles = "mapbox"

st.sidebar.subheader("Zone supply (L/day)")
supply_overrides = {}
for zone, default in DEFAULT_ZONE_SUPPLY.items():
    supply_overrides[zone] = st.sidebar.number_input(
        zone, value=default, step=50_000_000, format="%d", key=f"supply_{zone}"
    )

num_tankers = st.sidebar.slider("Tankers to deploy", 1, 4, 2)
consumption_days = st.sidebar.slider("Consumption window (days)", 7, 90, 30)

if auto_refresh:
    st.sidebar.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")
    time.sleep(0.1)


@st.cache_data(ttl=30 if auto_refresh else 300)
def load_risks(supply: dict) -> pd.DataFrame:
    return compute_zone_risks(supply_overrides=supply)


@st.cache_data(ttl=60)
def load_routes(_risk_hash: str, tankers: int):
    risks = load_risks(supply_overrides)
    return optimize_tanker_routes(risks, num_tankers=tankers)


risks = load_risks(supply_overrides)
consumption = get_zone_consumption(consumption_days)
routes = load_routes(str(risks["risk_score"].tolist()), num_tankers)

# KPI row
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Zones monitored", len(risks))
c2.metric("Avg risk score", f"{risks['risk_score'].mean():.1f}%")
c3.metric("Critical zones", int((risks["risk_level"] == "critical").sum()))
c4.metric("Total demand", f"{risks['demand_liters'].sum()/1e9:.2f}B L/d")
c5.metric("Tanker routes", len(routes))

tab_cmd, tab_risk, tab_cons, tab_route, tab_data = st.tabs(
    [
        "Command center",
        "Shortage heatmap",
        "Zone consumption",
        "Tanker routes",
        "Geospatial data",
    ]
)

if not HAS_FOLIUM:
    st.error("Install streamlit-folium: `pip install streamlit-folium folium`")
    st.stop()


def show_map(m, height: int = 520, key: str = "map"):
    st_folium(m, width=None, height=height, returned_objects=[], key=key)


with tab_cmd:
    st.subheader("Unified operations map")
    m = build_command_center_map(risks, routes, tiles=tiles)
    show_map(m, key="cmd_map")
    st.info(
        f"Map center: {MAP_CENTER[0]:.4f}°N, {MAP_CENTER[1]:.4f}°E · "
        "Layers: zone risk, shortage heatmap, assets, tanker paths"
    )

with tab_risk:
    st.subheader("Real-time geospatial risk monitoring")
    col_l, col_r = st.columns([2, 1])
    with col_l:
        m = build_risk_monitor_map(risks, show_heatmap=True, tiles=tiles)
        show_map(m, height=560, key="risk_map")
    with col_r:
        st.markdown("#### Zone risk table")
        display = risks[
            ["zone", "risk_score", "risk_level", "gap_liters", "demand_liters", "supply_liters"]
        ].copy()
        display["gap_liters"] = display["gap_liters"].apply(lambda x: f"{x:,.0f}")
        display["demand_liters"] = display["demand_liters"].apply(lambda x: f"{x:,.0f}")
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.bar_chart(risks.set_index("zone")["risk_score"], color="#ef4444")

with tab_cons:
    st.subheader("Zone-wise consumption visualization")
    col_m, col_c = st.columns([2, 1])
    with col_m:
        m = build_consumption_map(consumption_days, tiles=tiles)
        show_map(m, key="cons_map")
    with col_c:
        st.markdown(f"#### Last {consumption_days} days")
        st.dataframe(consumption, use_container_width=True, hide_index=True)
        st.bar_chart(consumption.set_index("zone")["share_pct"])

with tab_route:
    st.subheader("Tanker route optimization")
    m = build_tanker_route_map(routes, risks, tiles=tiles)
    show_map(m, height=560, key="route_map")
    for i, route in enumerate(routes):
        with st.expander(f"Route {i+1} — {route.depot_id} ({route.total_distance_km} km)"):
            stops_df = pd.DataFrame(
                [
                    {
                        "stop": s.name,
                        "type": s.stop_type,
                        "demand_L": int(s.demand_liters),
                        "lat": s.lat,
                        "lon": s.lon,
                    }
                    for s in route.stops
                ]
            )
            st.dataframe(stops_df, use_container_width=True, hide_index=True)

with tab_data:
    st.subheader("Geospatial analytics export")
    st.download_button(
        "Download risk GeoJSON (zone attributes)",
        risks.to_json(orient="records", indent=2),
        file_name="zone_risk.json",
        mime="application/json",
    )
    st.download_button(
        "Download consumption CSV",
        consumption.to_csv(index=False),
        file_name="zone_consumption.csv",
        mime="text/csv",
    )
    if routes:
        route_summary = pd.DataFrame(
            [
                {
                    "route": i + 1,
                    "depot": r.depot_id,
                    "stops": len(r.stops),
                    "distance_km": r.total_distance_km,
                    "demand_liters": r.total_demand_liters,
                }
                for i, r in enumerate(routes)
            ]
        )
        st.dataframe(route_summary, use_container_width=True, hide_index=True)

if auto_refresh:
    time.sleep(30)
    st.rerun()
