"""Interactive Folium maps (Leaflet.js) with optional Mapbox tiles."""

from __future__ import annotations

import json
import os

import folium
import pandas as pd
from branca.colormap import LinearColormap
from folium import plugins
from folium.plugins import HeatMap, MarkerCluster

from gis.analytics.consumption import get_zone_consumption
from gis.analytics.heatmap import build_consumption_grid, build_shortage_heatmap_points
from gis.analytics.risk import compute_zone_risks, risk_color
from gis.config import ASSETS_GEOJSON, MAP_CENTER, MAP_ZOOM, ZONES_GEOJSON
from gis.routing.tanker_optimizer import TankerRoute


def _base_map(tiles: str = "OpenStreetMap") -> folium.Map:
    m = folium.Map(location=MAP_CENTER, zoom_start=MAP_ZOOM, tiles=tiles)
    token = os.getenv("MAPBOX_TOKEN", "")
    if token and tiles == "mapbox":
        folium.TileLayer(
            tiles=f"https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/{{z}}/{{x}}/{{y}}?access_token={token}",
            attr="Mapbox",
            name="Mapbox Streets",
        ).add_to(m)
    return m


def _style_zone_feature(feature, risk_lookup: dict):
    name = feature["properties"]["name"]
    score = risk_lookup.get(name, 0)
    return {
        "fillColor": risk_color(score),
        "color": "#1e293b",
        "weight": 2,
        "fillOpacity": 0.55,
    }


def _zone_popup_html(name: str, row: pd.Series) -> str:
    return f"""
    <b>{name}</b><br>
    Demand: {row.get('demand_liters', 0):,.0f} L/day<br>
    Supply: {row.get('supply_liters', 0):,.0f} L/day<br>
    Gap: {row.get('gap_liters', 0):,.0f} L<br>
    Risk: <b>{row.get('risk_score', 0):.1f}%</b> ({row.get('risk_level', '')})
    """


def build_risk_monitor_map(
    risks: pd.DataFrame | None = None,
    show_heatmap: bool = True,
    show_assets: bool = True,
    tiles: str = "OpenStreetMap",
) -> folium.Map:
    """Real-time geospatial risk map with shortage heatmap overlay."""
    if risks is None:
        risks = compute_zone_risks()

    risk_lookup = dict(zip(risks["zone"], risks["risk_score"]))
    m = _base_map(tiles)

    zones_geo = json.loads(ZONES_GEOJSON.read_text(encoding="utf-8"))
    risk_rows = {r["zone"]: r for _, r in risks.iterrows()}

    folium.GeoJson(
        zones_geo,
        name="Zone risk choropleth",
        style_function=lambda f: _style_zone_feature(f, risk_lookup),
        tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Zone:"]),
        popup=folium.GeoJsonPopup(
            fields=["name"],
            labels=False,
            localize=True,
        ),
    ).add_to(m)

    for _, row in risks.iterrows():
        folium.Marker(
            [row["lat"], row["lon"]],
            popup=folium.Popup(_zone_popup_html(row["zone"], row), max_width=280),
            icon=folium.Icon(
                color="red" if row["risk_level"] in ("high", "critical") else "orange",
                icon="tint",
                prefix="fa",
            ),
        ).add_to(m)

    if show_heatmap:
        heat = build_shortage_heatmap_points(risks)
        if heat:
            HeatMap(
                heat,
                name="Shortage intensity",
                min_opacity=0.3,
                radius=18,
                blur=22,
                gradient={0.2: "blue", 0.5: "lime", 0.7: "orange", 1: "red"},
            ).add_to(m)

    if show_assets:
        _add_assets_layer(m)

    colormap = LinearColormap(
        colors=["#22c55e", "#eab308", "#f97316", "#ef4444"],
        index=[0, 15, 40, 70],
        vmin=0,
        vmax=100,
        caption="Water shortage risk score (%)",
    )
    colormap.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def build_consumption_map(
    days: int = 30,
    tiles: str = "OpenStreetMap",
) -> folium.Map:
    """Zone-wise consumption choropleth + consumption heatmap."""
    consumption = get_zone_consumption(days)
    if consumption.empty:
        return _base_map(tiles)

    share_lookup = dict(zip(consumption["zone"], consumption["share_pct"]))
    zones_geo = json.loads(ZONES_GEOJSON.read_text(encoding="utf-8"))

    m = _base_map(tiles)

    def style_fn(feature):
        name = feature["properties"]["name"]
        share = share_lookup.get(name, 0)
        return {
            "fillColor": _consumption_color(share),
            "color": "#334155",
            "weight": 2,
            "fillOpacity": 0.6,
        }

    folium.GeoJson(
        zones_geo,
        name="Consumption share %",
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Zone:"]),
    ).add_to(m)

    heat = build_consumption_grid(consumption)
    if heat:
        HeatMap(
            heat,
            name="Consumption density",
            min_opacity=0.25,
            radius=15,
            gradient={0.2: "#dbeafe", 0.5: "#3b82f6", 1: "#1e3a8a"},
        ).add_to(m)

    for _, row in consumption.iterrows():
        risks = compute_zone_risks()
        zr = risks[risks["zone"] == row["zone"]]
        if len(zr):
            lat, lon = zr.iloc[0]["lat"], zr.iloc[0]["lon"]
            folium.CircleMarker(
                [lat, lon],
                radius=8 + row["share_pct"] / 5,
                popup=(
                    f"<b>{row['zone']}</b><br>"
                    f"Avg daily: {row['avg_daily_demand']:,} L<br>"
                    f"Share: {row['share_pct']}%"
                ),
                color="#1d4ed8",
                fill=True,
                fill_opacity=0.7,
            ).add_to(m)

    LinearColormap(
        colors=["#dbeafe", "#3b82f6", "#1e3a8a"],
        index=[0, 15, 25],
        vmin=0,
        vmax=max(share_lookup.values()) if share_lookup else 30,
        caption=f"Consumption share % (last {days} days)",
    ).add_to(m)

    folium.LayerControl().add_to(m)
    return m


def _consumption_color(share: float) -> str:
    if share >= 22:
        return "#1e3a8a"
    if share >= 20:
        return "#3b82f6"
    if share >= 18:
        return "#60a5fa"
    return "#dbeafe"


def build_tanker_route_map(
    routes: list[TankerRoute],
    risks: pd.DataFrame | None = None,
    tiles: str = "OpenStreetMap",
) -> folium.Map:
    """Map optimized tanker routes with stop markers."""
    m = _base_map(tiles)
    if risks is not None:
        zones_geo = json.loads(ZONES_GEOJSON.read_text(encoding="utf-8"))
        risk_lookup = dict(zip(risks["zone"], risks["risk_score"]))
        folium.GeoJson(
            zones_geo,
            name="Zones",
            style_function=lambda f: _style_zone_feature(f, risk_lookup),
        ).add_to(m)

    colors = ["#2563eb", "#7c3aed", "#059669", "#dc2626"]
    for i, route in enumerate(routes):
        color = colors[i % len(colors)]
        folium.PolyLine(
            route.geometry,
            color=color,
            weight=5,
            opacity=0.85,
            popup=f"Route {i+1}: {route.total_distance_km} km",
        ).add_to(m)

        for j, stop in enumerate(route.stops):
            icon = "home" if stop.stop_type == "depot" else "flag"
            folium.Marker(
                [stop.lat, stop.lon],
                popup=(
                    f"<b>{stop.name}</b><br>"
                    f"Type: {stop.stop_type}<br>"
                    f"Demand: {stop.demand_liters:,.0f} L"
                ),
                icon=folium.Icon(color="blue" if stop.stop_type == "depot" else "green", icon=icon, prefix="fa"),
            ).add_to(m)

    folium.LayerControl().add_to(m)
    return m


def build_command_center_map(
    risks: pd.DataFrame | None = None,
    routes: list[TankerRoute] | None = None,
    tiles: str = "OpenStreetMap",
) -> folium.Map:
    """Unified operations map: risk + heatmap + assets + routes."""
    if risks is None:
        risks = compute_zone_risks()
    m = build_risk_monitor_map(risks, show_heatmap=True, show_assets=True, tiles=tiles)
    if routes:
        colors = ["#2563eb", "#7c3aed"]
        for i, route in enumerate(routes):
            folium.PolyLine(
                route.geometry,
                color=colors[i % len(colors)],
                weight=4,
                dash_array="8",
                popup=f"Tanker route {i+1}: {route.total_distance_km} km",
            ).add_to(m)
    return m


def _add_assets_layer(m: folium.Map) -> None:
    geo = json.loads(ASSETS_GEOJSON.read_text(encoding="utf-8"))
    cluster = MarkerCluster(name="Water assets")
    icon_map = {
        "tanker_depot": ("truck", "blue"),
        "reservoir": ("tint", "cadetblue"),
        "pump_station": ("cog", "gray"),
        "priority_site": ("plus-sign", "red"),
        "groundwater": ("tint", "green"),
    }
    for feat in geo["features"]:
        props = feat["properties"]
        lon, lat = feat["geometry"]["coordinates"]
        icon, color = icon_map.get(props.get("asset_type"), ("info-sign", "blue"))
        folium.Marker(
            [lat, lon],
            popup=f"<b>{props['name']}</b><br>{props.get('asset_type', '')}",
            icon=folium.Icon(color=color, icon=icon, prefix="fa"),
        ).add_to(cluster)
    cluster.add_to(m)
