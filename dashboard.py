from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "delhi_water_dataset.csv"
MODEL_PATH = ROOT / "water_demand_model.pkl"
ENCODER_PATH = ROOT / "zone_encoder.pkl"


def _try_import_plotly():
    try:
        import plotly.express as px
        import plotly.graph_objects as go

        return px, go
    except Exception:
        return None, None


def _load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            "delhi_water_dataset.csv not found. Run: python generate_datset.py"
        )
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(show_spinner=False)
def load_data_cached() -> pd.DataFrame:
    return _load_data()


@st.cache_data(show_spinner=False)
def compute_latest_metrics(df: pd.DataFrame) -> dict:
    latest_day = df["date"].max()
    latest = df[df["date"] == latest_day].copy()
    total_demand = float(latest["water_demand"].sum())
    avg_temp = float(latest["temperature"].mean())
    avg_rain = float(latest["rainfall"].mean())
    return {
        "latest_day": latest_day,
        "total_demand": total_demand,
        "avg_temp": avg_temp,
        "avg_rain": avg_rain,
        "zones": sorted(df["zone"].dropna().unique().tolist()),
    }


def _liters_to_billions(value: float) -> float:
    return float(value) / 1_000_000_000


def _format_billions(value: float) -> str:
    return f"{_liters_to_billions(float(value)):.2f}B"


def _style_plotly(fig, *, height: int, title: str | None = None, y_title: str | None = None):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=55 if title else 30, b=10),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(size=13),
        title_text=title or "",
        title_x=0,
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(0,0,0,0.06)", title_text="")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.06)", title_text=y_title or "")
    fig.update_traces(line=dict(width=3), selector=dict(type="scatter"))
    fig.update_traces(marker_line_width=0, selector=dict(type="bar"))
    return fig


@st.cache_data(show_spinner=False)
def compute_city_daily(df: pd.DataFrame) -> pd.DataFrame:
    daily = (
        df.groupby("date", as_index=False)
        .agg(
            water_demand=("water_demand", "sum"),
            temperature=("temperature", "mean"),
            rainfall=("rainfall", "mean"),
        )
        .sort_values("date")
    )
    daily["demand_bil"] = daily["water_demand"].map(_liters_to_billions)
    daily["demand_7d_avg_bil"] = daily["demand_bil"].rolling(7, min_periods=1).mean()
    daily["temp_7d_avg"] = daily["temperature"].rolling(7, min_periods=1).mean()
    daily["rain_7d_sum"] = daily["rainfall"].rolling(7, min_periods=1).sum()
    return daily


def _pct_change(curr: float, prev: float) -> float | None:
    if prev == 0:
        return None
    return (curr - prev) / prev * 100.0


def _safe_float(v) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _humanize_weather_error(err: Exception) -> str:
    msg = str(err).strip() or err.__class__.__name__
    low = msg.lower()
    if "not configured" in low or "api_key" in low:
        return (
            "Weather API keys not configured. Set OPENWEATHER_API_KEY or WEATHERAPI_KEY, then restart Streamlit."
        )
    if "401" in low or "unauthorized" in low or "invalid api key" in low:
        return "Weather API key rejected (unauthorized). Double-check the key and provider."
    if "timed out" in low or "timeout" in low:
        return "Weather request timed out. Check internet/firewall or increase WEATHER_TIMEOUT_SECONDS."
    if "name or service not known" in low or "nodename nor servname" in low:
        return "DNS/network error reaching the weather API. Check your internet/proxy/firewall."
    return msg


def _decision_engine(
    predicted_demand,
    supply,
    rainfall_next_24h,
    temperature_c,
    humidity_pct,
    industrial_index,
):

    gap = predicted_demand - supply
    risk_score = (gap / supply) * 100 if supply > 0 else 0
    if gap <= 0:
        recommendation = "Supply sufficient. Maintain standard distribution."
    elif rainfall_next_24h < 5 and temperature_c > 35 and humidity_pct < 70:
        recommendation = (
            "Heatwave risk detected. Increase reservoir pumping and issue water conservation advisory."
        )
    elif temperature_c > 40 and humidity_pct > 70:
        recommendation = (
            "High heat and humidity detected. Increase treatment throughput and issue public hydration advisory."
        )
    elif industrial_index > 80 and gap > 200_000_000:
        recommendation = (
            "Industrial demand high. Reduce industrial water allocation by 10% and deploy water tankers."
        )
    elif rainfall_next_24h > 20:
        recommendation = "Good rainfall expected. Maintain supply and increase reservoir storage."
    elif gap > 500_000_000:
        recommendation = (
            "Critical shortage predicted. Activate emergency groundwater reserves and deploy tankers."
        )
    else:
        recommendation = "Moderate shortage predicted. Increase pumping from reservoirs and monitor demand."
    return recommendation, float(risk_score)


def _kpi_card_row(
    *,
    metrics: dict,
    supply_total: float,
    risk_summary: dict | None,
    city_daily: pd.DataFrame,
) -> None:
    latest_day = metrics["latest_day"]
    if len(city_daily) >= 2:
        today = city_daily.iloc[-1]
        yesterday = city_daily.iloc[-2]
        demand_delta = _pct_change(float(today["water_demand"]), float(yesterday["water_demand"]))
        temp_delta = _pct_change(float(today["temperature"]), float(yesterday["temperature"]))
        rain_delta = _pct_change(float(today["rainfall"]), float(yesterday["rainfall"]))
        demand_today = float(today["water_demand"])
        temp_today = float(today["temperature"])
        rain_today = float(today["rainfall"])
    else:
        demand_delta = None
        temp_delta = None
        rain_delta = None
        demand_today = metrics["total_demand"]
        temp_today = metrics["avg_temp"]
        rain_today = metrics["avg_rain"]

    gap = demand_today - supply_total

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("As of", latest_day.date().isoformat())
    c2.metric(
        "Demand (today)",
        f"{_format_billions(demand_today)} L/day",
        delta=(f"{demand_delta:+.1f}%" if demand_delta is not None else None),
    )
    c3.metric("Supply (baseline)", f"{_format_billions(supply_total)} L/day")
    c4.metric("Gap (today)", f"{_format_billions(gap)} L")
    if risk_summary:
        c5.metric("High+ risk zones", str(risk_summary.get("high_or_worse", 0)))
    else:
        c5.metric(
            "Rainfall (today)",
            f"{rain_today:.1f} mm",
            delta=(f"{rain_delta:+.1f}%" if rain_delta is not None else None),
        )


def _render_exec_overview(df: pd.DataFrame) -> None:
    px, go = _try_import_plotly()
    if df.empty:
        st.error("No data available to render dashboard.")
        return
    required = {"date", "zone", "water_demand", "temperature", "rainfall", "industrial_index"}
    missing = sorted(required - set(df.columns))
    if missing:
        st.error(f"Dataset missing required columns: {', '.join(missing)}")
        return
    st.markdown(
        """
        <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:16px;">
          <div>
            <div style="font-size:34px; font-weight:800; line-height:1.05;">Smart-City Water Command Center</div>
            <div style="opacity:0.75; margin-top:4px;">Demand intelligence · weather impact · zone risks · operational actions</div>
          </div>
          <div style="opacity:0.75; font-size:13px; text-align:right;">
            Delhi NCR<br/>
            Executive view
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        from gis.config import DEFAULT_ZONE_SUPPLY

        supply_total = float(sum(DEFAULT_ZONE_SUPPLY.values()))
    except Exception:
        supply_total = float(df[df["date"] == df["date"].max()]["water_demand"].sum()) * 0.98

    metrics = compute_latest_metrics(df)
    city_daily = compute_city_daily(df)
    risk_summary = None
    risks = None
    try:
        from gis.analytics.risk import compute_zone_risks

        risks = compute_zone_risks()
        high_or_worse = int((risks["risk_level"].isin(["high", "critical"])).sum())
        risk_summary = {"high_or_worse": high_or_worse}
    except Exception:
        risk_summary = None

    _kpi_card_row(metrics=metrics, supply_total=supply_total, risk_summary=risk_summary, city_daily=city_daily)

    st.divider()
    t1, t2, t3 = st.tabs(["Demand", "Weather Impact", "Risk & Zones"])

    with t1:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("City Demand Trend")
            if px:
                s = city_daily["demand_bil"].dropna()
                if s.empty:
                    st.info("Demand series is empty in the selected window.")
                else:
                    demand_min = float(s.min())
                    demand_max = float(s.max())
                    span = demand_max - demand_min
                    pad = 0.05 if span < 0.05 else span * 0.12

                    if go:
                        fig = go.Figure()
                        fig.add_trace(
                            go.Bar(
                                x=city_daily["date"],
                                y=city_daily["demand_bil"],
                                name="Daily demand",
                                marker_color="rgba(37, 99, 235, 0.30)",
                            )
                        )
                        fig.add_trace(
                            go.Scatter(
                                x=city_daily["date"],
                                y=city_daily["demand_7d_avg_bil"],
                                name="7-day avg",
                                mode="lines",
                                line=dict(width=3, color="#1d4ed8"),
                            )
                        )
                    else:
                        fig = px.line(city_daily, x="date", y="demand_bil", markers=True)

                    fig = _style_plotly(fig, height=420, y_title="Demand (B liters/day)")
                    if np.isfinite(demand_min) and np.isfinite(demand_max):
                        fig.update_yaxes(
                            range=[demand_min - pad, demand_max + pad],
                            rangemode="normal",
                            tickformat=".2f",
                        )
                    fig.update_xaxes(title_text="Date")
                    st.plotly_chart(fig, use_container_width=True)
                    if np.isfinite(span) and span < 0.005:
                        st.warning(
                            "Demand is nearly constant in the selected window, so the trend looks flat. Try a larger time window or verify that the dataset has varying demand values."
                        )
            else:
                st.line_chart(city_daily.set_index("date")["water_demand"])
        with c2:
            st.subheader("Key Insights")
            last = city_daily.iloc[-1]
            prev_7 = city_daily.iloc[-7:]["water_demand"].mean() if len(city_daily) >= 7 else float(last["water_demand"])
            prev_30 = city_daily.iloc[-30:]["water_demand"].mean() if len(city_daily) >= 30 else float(last["water_demand"])
            peak_30 = float(city_daily.iloc[-30:]["water_demand"].max()) if len(city_daily) >= 30 else float(city_daily["water_demand"].max())
            vol_30 = float(city_daily.iloc[-30:]["water_demand"].std()) if len(city_daily) >= 30 else float(city_daily["water_demand"].std())
            rain_7 = float(city_daily.iloc[-7:]["rainfall"].sum()) if len(city_daily) >= 7 else float(city_daily["rainfall"].sum())

            bullets: list[str] = []
            bullets.append(f"Demand (7-day avg): {_format_billions(prev_7)} L/day")
            bullets.append(f"Demand (30-day avg): {_format_billions(prev_30)} L/day")
            bullets.append(f"Peak demand (window): {_format_billions(peak_30)} L/day")
            bullets.append(f"Volatility (std, window): {_format_billions(vol_30)} L/day")
            bullets.append(f"Rainfall (last 7 days): {rain_7:.1f} mm")

            if len(city_daily) >= 2:
                d = _pct_change(float(city_daily.iloc[-1]["water_demand"]), float(city_daily.iloc[-2]["water_demand"]))
                if d is not None:
                    bullets.insert(0, f"Day-over-day change: {d:+.1f}%")

            ops_line = None
            if risk_summary and risk_summary.get("high_or_worse", 0) >= 2:
                ops_line = "Multiple zones elevated risk. Prioritize tanker readiness and reservoir scheduling."
            elif float(last["temperature"]) > 38 and float(last["rainfall"]) < 5:
                ops_line = "Heat stress conditions. Expect higher consumption; trigger conservation advisory."
            elif float(last["rainfall"]) > 20:
                ops_line = "High rainfall pattern. Maximize storage capture and reduce pumping where possible."

            if risk_summary:
                bullets.append(f"Zones high/critical risk: {int(risk_summary.get('high_or_worse', 0))}")

            st.markdown("\n".join([f"- {b}" for b in bullets]))
            if ops_line:
                st.markdown(f"**Suggested action:** {ops_line}")
            st.caption("Use Zone Analytics for drill-down and Zone Comparison for benchmarking.")

    with t2:
        st.subheader("Weather Analytics & Demand Sensitivity")
        top, bottom = st.columns([2, 1])
        with top:
            if px:
                tmp = city_daily.dropna(subset=["rainfall"])
                if tmp.empty:
                    st.info("Rainfall series is empty in the selected window.")
                else:
                    fig = px.bar(tmp, x="date", y="rainfall", opacity=0.75)
                    fig = _style_plotly(fig, height=280, y_title="Rainfall (mm)")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.line_chart(city_daily.set_index("date")["rainfall"])
        with bottom:
            if px:
                tmp = city_daily.dropna(subset=["temperature"])
                if tmp.empty:
                    st.info("Temperature series is empty in the selected window.")
                else:
                    fig = px.line(tmp, x="date", y="temperature")
                    fig = _style_plotly(fig, height=280, y_title="Temperature (°C)")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.line_chart(city_daily.set_index("date")["temperature"])

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Demand vs Temperature")
            if px:
                tmp = city_daily.dropna(subset=["temperature", "demand_bil"]).copy()
                if tmp.empty:
                    st.info("Not enough data to compute temperature sensitivity.")
                else:
                    fig = px.scatter(tmp, x="temperature", y="demand_bil", opacity=0.7)
                    if len(tmp) >= 3 and go and tmp["temperature"].nunique() >= 2:
                        try:
                            m, b = np.polyfit(
                                tmp["temperature"].to_numpy(),
                                tmp["demand_bil"].to_numpy(),
                                1,
                            )
                            xs = np.linspace(
                                float(tmp["temperature"].min()),
                                float(tmp["temperature"].max()),
                                30,
                            )
                            ys = m * xs + b
                            fig.add_trace(
                                go.Scatter(
                                    x=xs,
                                    y=ys,
                                    name="trend",
                                    mode="lines",
                                    line=dict(color="#111827"),
                                )
                            )
                        except Exception:
                            pass
                    fig = _style_plotly(fig, height=360, y_title="Demand (B liters/day)")
                    fig.update_xaxes(title_text="Temperature (°C)")
                    st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("Demand vs Rainfall")
            if px:
                tmp = city_daily.dropna(subset=["rainfall", "demand_bil"]).copy()
                if tmp.empty:
                    st.info("Not enough data to compute rainfall sensitivity.")
                else:
                    fig = px.scatter(tmp, x="rainfall", y="demand_bil", opacity=0.7)
                    if len(tmp) >= 3 and go and tmp["rainfall"].nunique() >= 2:
                        try:
                            m, b = np.polyfit(
                                tmp["rainfall"].to_numpy(),
                                tmp["demand_bil"].to_numpy(),
                                1,
                            )
                            xs = np.linspace(
                                float(tmp["rainfall"].min()),
                                float(tmp["rainfall"].max()),
                                30,
                            )
                            ys = m * xs + b
                            fig.add_trace(
                                go.Scatter(
                                    x=xs,
                                    y=ys,
                                    name="trend",
                                    mode="lines",
                                    line=dict(color="#111827"),
                                )
                            )
                        except Exception:
                            pass
                    fig = _style_plotly(fig, height=360, y_title="Demand (B liters/day)")
                    fig.update_xaxes(title_text="Rainfall (mm)")
                    st.plotly_chart(fig, use_container_width=True)

    with t3:
        left, right = st.columns([1.25, 1])
        with left:
            st.subheader("Top Zones by Demand (latest)")
            latest_day = df["date"].max()
            latest = df[df["date"] == latest_day].copy()
            latest_zone = (
                latest.groupby("zone", as_index=False)
                .agg(
                    water_demand=("water_demand", "sum"),
                    temperature=("temperature", "mean"),
                    rainfall=("rainfall", "mean"),
                    industrial_index=("industrial_index", "mean"),
                )
                .sort_values("water_demand", ascending=False)
            )
            latest_zone["demand_bil"] = latest_zone["water_demand"].map(_liters_to_billions)
            if px:
                if latest_zone.empty:
                    st.info("No zone data available for the latest date.")
                else:
                    fig = px.bar(latest_zone.head(10), x="zone", y="demand_bil")
                    fig = _style_plotly(fig, height=360, y_title="Demand (B liters/day)")
                    fig.update_xaxes(title_text="")
                    st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                latest_zone[["zone", "water_demand", "temperature", "rainfall", "industrial_index"]].head(10),
                use_container_width=True,
                hide_index=True,
            )

        with right:
            st.subheader("Risk Snapshot")
            if risks is not None and px:
                worst = risks.sort_values("risk_score", ascending=False).head(7)[
                    ["zone", "risk_score", "risk_level"]
                ]
                if worst.empty:
                    st.info("Risk data is empty.")
                else:
                    fig = px.bar(
                        worst,
                        x="risk_score",
                        y="zone",
                        orientation="h",
                        color="risk_level",
                        color_discrete_map={
                            "low": "#22c55e",
                            "medium": "#eab308",
                            "high": "#f97316",
                            "critical": "#ef4444",
                        },
                    )
                    fig = _style_plotly(fig, height=360, y_title=None)
                    fig.update_xaxes(title_text="Risk score (%)")
                    st.plotly_chart(fig, use_container_width=True)
            elif risks is None:
                st.info("Risk engine unavailable. Ensure gis/ is installed and zone geojson is present.")
            else:
                st.info("Install plotly to view risk charts.")


def _render_zone_analytics(df: pd.DataFrame) -> None:
    px, go = _try_import_plotly()
    st.title("Zone Analytics")
    if df.empty:
        st.error("No data available for the selected time window.")
        return
    required = {"date", "zone", "water_demand", "temperature", "rainfall", "industrial_index"}
    missing = sorted(required - set(df.columns))
    if missing:
        st.error(f"Dataset missing required columns: {', '.join(missing)}")
        return

    zones = sorted(df["zone"].dropna().unique().tolist())
    zone = st.selectbox("Zone", zones)
    zdf = df[df["zone"] == zone].sort_values("date").copy()

    c1, c2, c3, c4 = st.columns(4)
    last = zdf.iloc[-1]
    c1.metric("Latest demand", f"{int(last['water_demand']):,} L/day")
    c2.metric("Temperature", f"{float(last['temperature']):.1f} °C")
    c3.metric("Rainfall", f"{float(last['rainfall']):.1f} mm")
    c4.metric("Industrial index", f"{float(last['industrial_index']):.0f}")

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("Demand")
        if px:
            zdf["demand_bil"] = zdf["water_demand"].map(_liters_to_billions)
            fig = px.line(zdf, x="date", y="demand_bil")
            fig = _style_plotly(fig, height=340, title=None, y_title="Demand (B liters/day)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.line_chart(zdf.set_index("date")["water_demand"])

    with right:
        st.subheader("Risk Gauge")
        if go:
            try:
                from gis.analytics.risk import compute_zone_risks
                from gis.config import RISK_CRITICAL, RISK_HIGH, RISK_MEDIUM

                risks = compute_zone_risks()
                row = risks[risks["zone"] == zone].iloc[0]
                score = float(row["risk_score"])
                fig = go.Figure(
                    go.Indicator(
                        mode="gauge+number",
                        value=score,
                        number={"suffix": "%"},
                        gauge={
                            "axis": {"range": [-50, 150]},
                            "bar": {"color": "#2563eb"},
                            "steps": [
                                {"range": [-50, RISK_MEDIUM], "color": "#22c55e"},
                                {"range": [RISK_MEDIUM, RISK_HIGH], "color": "#eab308"},
                                {"range": [RISK_HIGH, RISK_CRITICAL], "color": "#f97316"},
                                {"range": [RISK_CRITICAL, 150], "color": "#ef4444"},
                            ],
                        },
                        title={"text": f"{zone} risk"},
                    )
                )
                fig.update_layout(
                    template="plotly_white",
                    height=340,
                    margin=dict(l=10, r=10, t=70, b=10),
                    font=dict(size=13),
                )
                st.plotly_chart(fig, use_container_width=True)
            except Exception as exc:
                st.info(f"Risk gauge unavailable: {exc}")
        else:
            st.info("Install plotly to view the risk gauge.")

    st.subheader("Weather Analytics")
    w1, w2 = st.columns(2)
    with w1:
        if px:
            fig = px.bar(zdf, x="date", y="rainfall", opacity=0.75)
            fig = _style_plotly(fig, height=300, title=None, y_title="Rainfall (mm)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.line_chart(zdf.set_index("date")["rainfall"])

    with w2:
        if px:
            fig = px.line(zdf, x="date", y="temperature")
            fig = _style_plotly(fig, height=300, title=None, y_title="Temperature (°C)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.line_chart(zdf.set_index("date")["temperature"])


def _render_zone_comparison(df: pd.DataFrame) -> None:
    px, _ = _try_import_plotly()
    st.title("Zone Comparison")
    if df.empty:
        st.error("No data available for the selected time window.")
        return
    required = {"date", "zone", "water_demand", "temperature", "rainfall", "industrial_index"}
    missing = sorted(required - set(df.columns))
    if missing:
        st.error(f"Dataset missing required columns: {', '.join(missing)}")
        return

    zones = sorted(df["zone"].dropna().unique().tolist())
    selected = st.multiselect("Compare zones", zones, default=zones[:3])
    if not selected:
        st.info("Select at least one zone.")
        return
    if len(selected) > 6:
        st.warning("Too many zones selected. Showing the first 6 for chart clarity.")
        selected = selected[:6]

    zdf = df[df["zone"].isin(selected)].sort_values("date").copy()

    st.subheader("Demand trends (multi-zone)")
    if px:
        zdf["demand_bil"] = zdf["water_demand"].map(_liters_to_billions)
        fig = px.line(zdf, x="date", y="demand_bil", color="zone")
        fig = _style_plotly(fig, height=380, title=None, y_title="Demand (B liters/day)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        pivot = zdf.pivot_table(index="date", columns="zone", values="water_demand", aggfunc="sum")
        st.line_chart(pivot)

    st.subheader("Latest snapshot")
    latest_day = zdf["date"].max()
    latest = zdf[zdf["date"] == latest_day].copy()
    latest = latest[["zone", "water_demand", "temperature", "rainfall", "industrial_index"]]
    if px:
        latest["demand_bil"] = latest["water_demand"].map(_liters_to_billions)
        st.caption(f"Snapshot date: {pd.to_datetime(latest_day).date().isoformat()} (latest available in selected window)")
        fig = px.bar(
            latest.sort_values("demand_bil", ascending=True),
            y="zone",
            x="demand_bil",
            orientation="h",
        )
        fig = _style_plotly(fig, height=320, title=None, y_title="Demand (B liters/day)")
        fig.update_xaxes(title_text="Demand (B liters/day)")
        fig.update_yaxes(title_text="")
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(latest.sort_values("water_demand", ascending=False), use_container_width=True)


def _render_live_prediction() -> None:
    px, _ = _try_import_plotly()
    st.title("Live Demand Prediction")

    if not MODEL_PATH.exists() or not ENCODER_PATH.exists():
        st.error("ML models not found. Train them first:")
        st.code("python train_model.py", language="bash")
        return

    try:
        import joblib
    except Exception as exc:
        st.error(f"joblib not available: {exc}")
        return

    model = joblib.load(MODEL_PATH)
    zone_encoder = joblib.load(ENCODER_PATH)

    zones = [
        "North Delhi",
        "South Delhi",
        "East Delhi",
        "West Delhi",
        "Central Delhi",
    ]
    zone = st.selectbox("Zone", zones)

    try:
        from gis.analytics.risk import _zone_centroids

        lat, lon = _zone_centroids().get(zone, (28.6139, 77.2090))
    except Exception:
        lat, lon = (28.6139, 77.2090)

    has_weather_key = bool(os.getenv("OPENWEATHER_API_KEY", "").strip() or os.getenv("WEATHERAPI_KEY", "").strip())
    use_live_weather = st.toggle("Use live weather", value=has_weather_key)
    weather_bundle = None
    weather_error = None
    if use_live_weather:
        try:
            from weather import get_weather_bundle

            weather_bundle = get_weather_bundle(lat, lon, days=3)
        except Exception as exc:
            weather_error = _humanize_weather_error(exc)

    temp_default = 32
    humidity_default = 50
    rain_default = 10
    if weather_bundle:
        cur = weather_bundle.get("current") or {}
        temp_v = _safe_float(cur.get("temperature_c"))
        hum_v = _safe_float(cur.get("humidity_pct"))
        rain_v = _safe_float(weather_bundle.get("rainfall_next_24h_mm"))
        if temp_v is not None:
            temp_default = int(round(temp_v))
        if hum_v is not None:
            humidity_default = int(round(hum_v))
        if rain_v is not None:
            rain_default = int(round(rain_v))

    try:
        from gis.config import DEFAULT_ZONE_SUPPLY

        supply_default = int(DEFAULT_ZONE_SUPPLY.get(zone, 4_800_000_000))
    except Exception:
        supply_default = 4_800_000_000

    c1, c2, c3 = st.columns(3)
    with c1:
        population = st.number_input("Population", value=32_000_000)
        industrial_index = st.slider("Industrial Activity Index", 0, 100, 70)
    with c2:
        temperature = st.slider("Temperature (°C)", 10, 50, temp_default)
        humidity = st.slider("Humidity (%)", 0, 100, humidity_default)
        rainfall_next_24h = st.slider("Rainfall next 24h (mm)", 0, 100, rain_default)
    with c3:
        supply = st.number_input("Available supply (L/day)", value=supply_default)
        if weather_error:
            st.info(f"Live weather unavailable: {weather_error}")
        elif weather_bundle:
            st.caption(f"Live weather source: {weather_bundle.get('provider')}")

    if st.button("Run prediction", type="primary"):
        today = datetime.datetime.today()
        zone_encoded = zone_encoder.transform([zone])[0]
        features = np.array(
            [[population, temperature, rainfall_next_24h, industrial_index, today.month, today.day, zone_encoded]]
        )
        prediction = float(model.predict(features)[0])
        recommendation, risk_score = _decision_engine(
            prediction, float(supply), float(rainfall_next_24h), float(temperature), float(humidity), float(industrial_index)
        )
        gap = prediction - float(supply)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Predicted demand", f"{int(prediction):,} L/day")
        m2.metric("Supply", f"{int(supply):,} L/day")
        m3.metric("Gap", f"{int(gap):,} L")
        m4.metric("Risk score", f"{risk_score:.1f}%")

        st.subheader("Operational recommendation")
        if risk_score > 40:
            st.error(recommendation)
        elif risk_score > 15:
            st.warning(recommendation)
        else:
            st.success(recommendation)

        if px and weather_bundle:
            forecast_days = weather_bundle.get("forecast_days") or []
            if forecast_days:
                fdf = pd.DataFrame(forecast_days)
                st.subheader("Weather forecast (next days)")
                fig = px.bar(fdf, x="date", y="rainfall_mm")
                fig.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.set_page_config(
        page_title="Smart-City Water Analytics",
        page_icon="💧",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
          .block-container { padding-top: 1.15rem; padding-bottom: 2.0rem; max-width: 1400px; }
          [data-testid="stSidebar"] { min-width: 310px; }
          div[data-testid="stMetricValue"] { font-size: 1.35rem; font-weight: 800; }
          div[data-testid="stMetricLabel"] { opacity: 0.75; }
          h1, h2, h3 { letter-spacing: -0.02em; }
          [data-testid="stHeader"] { background: rgba(255,255,255,0.0); }
          [data-testid="stToolbar"] { visibility: hidden; height: 0px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.title("Water Command Center")
    st.sidebar.caption("Delhi NCR · Smart-City Analytics")

    page = st.sidebar.radio(
        "Navigate",
        ["Executive Overview", "Zone Analytics", "Zone Comparison", "Live Prediction"],
        label_visibility="collapsed",
    )

    st.sidebar.divider()
    window = st.sidebar.selectbox("Time window", ["30D", "90D", "180D", "All"], index=1)
    st.sidebar.caption("Plotly charts render when plotly is installed.")
    if not os.getenv("OPENWEATHER_API_KEY", "").strip() and not os.getenv("WEATHERAPI_KEY", "").strip():
        st.sidebar.info("Live weather is OFF (no API key detected).")
    else:
        try:
            from weather.config import load_settings

            s = load_settings()
            st.sidebar.success(f"Live weather is ON ({s.provider}).")
        except Exception:
            st.sidebar.success("Live weather is ON.")

    with st.sidebar.expander("Weather test", expanded=False):
        st.caption("Delhi centroid (28.6139, 77.2090)")
        if st.button("Test weather now", key="sidebar_weather_test"):
            try:
                from weather import get_weather_bundle

                bundle = get_weather_bundle(28.6139, 77.2090, days=3)
                cur = bundle.get("current") or {}
                temp = cur.get("temperature_c")
                hum = cur.get("humidity_pct")
                rain = bundle.get("rainfall_next_24h_mm")
                st.success(f"OK · Temp {temp}°C · Hum {hum}% · Rain24h {rain}mm")
                st.json(
                    {
                        "provider": bundle.get("provider"),
                        "current": cur,
                        "rainfall_next_24h_mm": bundle.get("rainfall_next_24h_mm"),
                    }
                )
            except Exception as exc:
                st.error(_humanize_weather_error(exc))

    with st.sidebar.expander("System", expanded=False):
        st.caption(f"Python: {sys.version.split()[0]}")
        st.caption(f"Executable: {sys.executable}")
        st.caption(f"Working dir: {ROOT}")

    try:
        df = load_data_cached()
    except Exception as exc:
        st.error(str(exc))
        return

    if window != "All":
        days = int(window.replace("D", ""))
        cutoff = df["date"].max() - pd.Timedelta(days=days)
        df_view = df[df["date"] >= cutoff].copy()
    else:
        df_view = df

    if page == "Executive Overview":
        _render_exec_overview(df_view)
    elif page == "Zone Analytics":
        _render_zone_analytics(df_view)
    elif page == "Zone Comparison":
        _render_zone_comparison(df_view)
    else:
        _render_live_prediction()


if __name__ == "__main__":
    main()
