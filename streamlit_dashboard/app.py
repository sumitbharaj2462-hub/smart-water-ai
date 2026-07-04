"""Global Education and Development Intelligence Dashboard — Streamlit edition."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import streamlit as st

from data_loader import (
    countries_df,
    enrich_latest,
    filter_countries,
    format_value,
    latest_df,
    load_dashboard_data,
    metric_label,
    metrics_dict,
    records_df,
    regions_df,
)

# ---------------------------------------------------------------------------
# Page config & styling
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Education & Development Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

COLORS = {
    "accent": "#1d7c74",
    "accent2": "#d0832f",
    "accent3": "#526fa3",
    "bg": "#f6f7f4",
    "ink": "#17201c",
    "muted": "#64716b",
}

st.markdown(
    f"""
    <style>
      .stApp {{ background-color: {COLORS["bg"]}; }}
      .block-container {{ padding-top: 1.5rem; max-width: 1400px; }}
      .dashboard-title {{
        color: {COLORS["accent"]};
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.25rem;
      }}
      .dashboard-h1 {{
        color: {COLORS["ink"]};
        font-size: clamp(1.6rem, 3vw, 2.4rem);
        font-weight: 800;
        line-height: 1.1;
        margin: 0 0 0.5rem 0;
      }}
      div[data-testid="stMetric"] {{
        background: white;
        border: 1px solid #dce3df;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        box-shadow: 0 12px 35px rgba(23, 32, 28, 0.08);
      }}
      div[data-testid="stMetric"] label {{
        color: {COLORS["muted"]} !important;
        font-weight: 700 !important;
        font-size: 0.8rem !important;
      }}
      div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
        color: {COLORS["ink"]};
        font-weight: 800;
      }}
      .panel-caption {{ color: {COLORS["muted"]}; font-size: 0.85rem; margin-top: -0.5rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, Segoe UI, Arial, sans-serif", color=COLORS["muted"], size=12),
    margin=dict(l=20, r=20, t=40, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


@st.cache_data(show_spinner=False)
def get_data():
    data = load_dashboard_data()
    countries = countries_df(data)
    records = records_df(data)
    latest = enrich_latest(latest_df(data), countries)
    regions = regions_df(data)
    metrics = metrics_dict(data)
    metric_options = sorted(
        [(mid, f"{m['group']}: {m['label']}") for mid, m in metrics.items()],
        key=lambda item: item[1],
    )
    return countries, records, latest, regions, metrics, metric_options


def series_for(records: pd.DataFrame, country: str, metric: str) -> pd.DataFrame:
    return (
        records[(records["country"] == country) & (records["metric"] == metric)]
        .sort_values("year")
        .reset_index(drop=True)
    )


def latest_for_filters(
    latest: pd.DataFrame,
    metric: str,
    region: str,
    income: str,
) -> pd.DataFrame:
    rows = latest[latest["metric"] == metric].copy()
    if region != "All":
        rows = rows[rows["region"] == region]
    if income != "All":
        rows = rows[rows["income"] == income]
    return rows


def build_trend_chart(
    records: pd.DataFrame,
    countries: pd.DataFrame,
    country: str,
    compare: str | None,
    metric: str,
    metrics: dict,
) -> go.Figure:
    meta = metrics.get(metric, {})
    label = meta.get("label", metric)
    unit = meta.get("unit", "")

    frames = []
    main = series_for(records, country, metric)
    if not main.empty:
        name = countries.loc[countries["code"] == country, "name"].iloc[0]
        frames.append(main.assign(series=name))

    if compare:
        comp = series_for(records, compare, metric)
        if not comp.empty:
            cname = countries.loc[countries["code"] == compare, "name"].iloc[0]
            frames.append(comp.assign(series=cname))

    if not frames or len(main) < 2:
        fig = go.Figure()
        fig.add_annotation(
            text="Not enough yearly data for this country and metric.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=COLORS["muted"], size=14),
        )
        fig.update_layout(**PLOTLY_LAYOUT, height=360)
        return fig

    plot_df = pd.concat(frames, ignore_index=True)
    color_map = {
        plot_df["series"].unique()[0]: COLORS["accent"],
    }
    if len(plot_df["series"].unique()) > 1:
        color_map[plot_df["series"].unique()[1]] = COLORS["accent2"]

    fig = px.line(
        plot_df,
        x="year",
        y="value",
        color="series",
        markers=True,
        color_discrete_map=color_map,
        labels={"year": "Year", "value": f"{label} ({unit})", "series": "Country"},
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=7))
    fig.update_layout(**PLOTLY_LAYOUT, height=360, hovermode="x unified")
    return fig


def build_regional_bar(regions: pd.DataFrame, metric: str, metrics: dict) -> go.Figure:
    meta = metrics.get(metric, {})
    label = meta.get("label", metric)
    rows = (
        regions[regions["metric"] == metric]
        .sort_values("average", ascending=True)
        .tail(9)
    )
    if rows.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No regional summary is available for this metric.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=COLORS["muted"], size=14),
        )
        fig.update_layout(**PLOTLY_LAYOUT, height=320)
        return fig

    fig = px.bar(
        rows,
        x="average",
        y="region",
        orientation="h",
        color_discrete_sequence=[COLORS["accent3"]],
        labels={"average": label, "region": "Region"},
        text=rows["average"].map(lambda v: format_value(v, metric)),
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(**PLOTLY_LAYOUT, height=320, showlegend=False)
    return fig


def build_scatter(
    latest: pd.DataFrame,
    metric: str,
    selected_country: str,
    metrics: dict,
) -> go.Figure:
    meta = metrics.get(metric, {})
    label = meta.get("label", metric)
    gdp = latest[latest["metric"] == "NY.GDP.PCAP.CD"][["country", "value"]].rename(
        columns={"value": "gdp"}
    )
    points = (
        latest[latest["metric"] == metric]
        .merge(gdp, on="country", how="inner")
        .dropna(subset=["gdp", "value"])
    )
    points = points[points["metric"] != "NY.GDP.PCAP.CD"]

    if len(points) < 4:
        fig = go.Figure()
        fig.add_annotation(
            text="Choose an education, health, technology, R&D, or quality metric to compare with GDP.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=COLORS["muted"], size=14),
        )
        fig.update_layout(**PLOTLY_LAYOUT, height=320)
        return fig

    points = points.assign(
        highlight=np.where(points["country"] == selected_country, "Selected", "Other")
    )
    fig = px.scatter(
        points,
        x="gdp",
        y="value",
        color="highlight",
        hover_name="name",
        hover_data={"region": True, "income": True, "year": True, "gdp": ":,.0f", "value": ":,.2f"},
        color_discrete_map={"Selected": COLORS["accent"], "Other": COLORS["accent3"]},
        labels={"gdp": "GDP per capita (US$)", "value": label, "highlight": ""},
        opacity=0.75,
    )
    fig.update_traces(marker=dict(size=10), selector=dict(name="Selected"))
    fig.update_traces(marker=dict(size=7), selector=dict(name="Other"))

    if len(points) >= 5:
        x = points["gdp"].to_numpy(dtype=float)
        y = points["value"].to_numpy(dtype=float)
        coeffs = np.polyfit(x, y, 1)
        x_line = np.linspace(x.min(), x.max(), 100)
        y_line = coeffs[0] * x_line + coeffs[1]
        r = np.corrcoef(x, y)[0, 1]
        fig.add_trace(
            go.Scatter(
                x=x_line,
                y=y_line,
                mode="lines",
                name=f"Trend (r={r:.2f})",
                line=dict(color=COLORS["accent2"], dash="dash", width=2),
            )
        )

    fig.update_layout(**PLOTLY_LAYOUT, height=320)
    return fig


def render_distribution(latest_filtered: pd.DataFrame, metric: str, metrics: dict) -> None:
    values = latest_filtered["value"].dropna()
    if values.empty:
        st.info("No distribution data for the current filters.")
        return

    label = metrics.get(metric, {}).get("label", metric)
    sns.set_theme(style="whitegrid", font="Segoe UI")
    fig, ax = plt.subplots(figsize=(8, 3.2))
    sns.histplot(values, kde=True, color=COLORS["accent"], ax=ax, edgecolor="white", linewidth=0.6)
    ax.set_xlabel(label)
    ax.set_ylabel("Countries")
    ax.set_title("Latest value distribution", fontsize=11, color=COLORS["muted"])
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

countries, records, latest, regions, metrics, metric_options = get_data()

st.markdown('<p class="dashboard-title">Education intelligence</p>', unsafe_allow_html=True)
st.markdown(
    '<h1 class="dashboard-h1">Global Education and Development Dashboard</h1>',
    unsafe_allow_html=True,
)
st.caption("Interactive Streamlit rebuild with pandas, numpy, seaborn, and Plotly Express.")

with st.sidebar:
    st.header("Filters")
    if st.button("Reset filters", width='stretch'):
        for key in list(st.session_state.keys()):
            if key.startswith("filter_"):
                del st.session_state[key]
        st.rerun()

    region = st.selectbox(
        "Region",
        ["All"] + sorted(countries["region"].dropna().unique()),
        key="filter_region",
    )
    income = st.selectbox(
        "Income group",
        ["All"] + sorted(countries["income"].dropna().unique()),
        key="filter_income",
    )

    available = filter_countries(countries, region, income)
    country_codes = available["code"].tolist()
    country_names = dict(zip(available["code"], available["name"]))

    default_country = "IND" if "IND" in country_codes else (country_codes[0] if country_codes else None)
    country = st.selectbox(
        "Country",
        country_codes,
        index=country_codes.index(default_country) if default_country in country_codes else 0,
        format_func=lambda c: country_names.get(c, c),
        key="filter_country",
    )

    compare_options = [""] + [c for c in country_codes if c != country]
    default_compare = "USA" if "USA" in compare_options else compare_options[0]
    compare = st.selectbox(
        "Compare with",
        compare_options,
        index=compare_options.index(default_compare) if default_compare in compare_options else 0,
        format_func=lambda c: "No comparison" if c == "" else country_names.get(c, c),
        key="filter_compare",
    )

    metric_ids = [m[0] for m in metric_options]
    default_metric = "SE.XPD.TOTL.GD.ZS"
    metric = st.selectbox(
        "Metric",
        metric_ids,
        index=metric_ids.index(default_metric) if default_metric in metric_ids else 0,
        format_func=lambda m: metric_label(m, {"metrics": metrics}),
        key="filter_metric",
    )

    st.divider()
    st.markdown("**Data source**")
    data_info = load_dashboard_data()
    st.caption(f"Years: {data_info['year_range'][0]}–{data_info['year_range'][1]}")
    st.caption(f"{len(records):,} observations · {len(countries)} countries")

# KPI calculations
selected_info = countries[countries["code"] == country].iloc[0]
series = series_for(records, country, metric)
latest_point = series.iloc[-1] if len(series) else None
filtered_latest = latest_for_filters(latest, metric, region, income)
region_peers = filtered_latest[filtered_latest["region"] == selected_info["region"]]
regional_avg = region_peers["value"].mean() if not region_peers.empty else np.nan
meta = metrics[metric]

prev_value = series.iloc[-2]["value"] if len(series) >= 2 else None
delta = None
if latest_point is not None and prev_value is not None:
    delta = latest_point["value"] - prev_value

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric(
        "Selected value",
        format_value(latest_point["value"] if latest_point is not None else None, metric),
        delta=f"{delta:+.2f}" if delta is not None else None,
        help=f"{selected_info['name']} · {meta['unit']}",
    )
    if latest_point is not None:
        st.caption(f"{selected_info['name']}, {int(latest_point['year'])} · {meta['unit']}")
with k2:
    st.metric(
        "Regional average",
        format_value(regional_avg, metric) if not pd.isna(regional_avg) else "-",
        help=selected_info["region"],
    )
    st.caption(selected_info["region"])
with k3:
    st.metric("Available countries", f"{len(available)}")
    st.caption(f"{len(records):,} data points loaded")
with k4:
    st.metric(
        "Latest year",
        str(int(latest_point["year"])) if latest_point is not None else "-",
    )
    st.caption(latest_point["source"] if latest_point is not None else "-")

st.divider()

# Charts row 1 — trend
st.subheader("Country trend")
st.markdown(
    f'<p class="panel-caption">{selected_info["name"]} · {meta["label"]} ({meta["unit"]})</p>',
    unsafe_allow_html=True,
)
st.plotly_chart(
    build_trend_chart(records, countries, country, compare or None, metric, metrics),
    width='stretch',
)

# Charts row 2 — regional + scatter
left, right = st.columns(2)
with left:
    st.subheader("Regional snapshot")
    st.markdown('<p class="panel-caption">Latest available country values, averaged by region.</p>', unsafe_allow_html=True)
    st.plotly_chart(build_regional_bar(regions, metric, metrics), width='stretch')
with right:
    st.subheader("Development relationship")
    st.markdown('<p class="panel-caption">Latest education metric vs GDP per capita.</p>', unsafe_allow_html=True)
    st.plotly_chart(build_scatter(latest, metric, country, metrics), width='stretch')

# Charts row 3 — seaborn-enhanced analytics
st.subheader("Distribution & correlation")
dist_col, corr_col = st.columns(2)

with dist_col:
    st.markdown('<p class="panel-caption">Distribution of latest values across filtered countries.</p>', unsafe_allow_html=True)
    render_distribution(filtered_latest, metric, metrics)

with corr_col:
    st.markdown('<p class="panel-caption">Correlation matrix (latest values, filtered countries).</p>', unsafe_allow_html=True)
    pivot_metrics = [
        "SE.XPD.TOTL.GD.ZS",
        "SE.PRM.ENRR",
        "SE.SEC.ENRR",
        "IT.NET.USER.ZS",
        "NY.GDP.PCAP.CD",
        "SP.DYN.LE00.IN",
    ]
    pivot_metrics = [m for m in pivot_metrics if m in metrics]
    wide = (
        filtered_latest[filtered_latest["metric"].isin(pivot_metrics)]
        .pivot_table(index="country", columns="metric", values="value", aggfunc="last")
        .dropna(how="all")
    )
    if wide.shape[0] >= 3 and wide.shape[1] >= 2:
        corr = wide.corr()
        labels = [metrics[m]["label"][:22] for m in corr.columns]
        fig_corr = go.Figure(
            data=go.Heatmap(
                z=corr.to_numpy(),
                x=labels,
                y=labels,
                colorscale="Teal",
                zmin=-1,
                zmax=1,
                text=np.round(corr.to_numpy(), 2),
                texttemplate="%{text}",
                hoverongaps=False,
            )
        )
        fig_corr.update_layout(**PLOTLY_LAYOUT, height=320)
        st.plotly_chart(fig_corr, width='stretch')
    else:
        st.info("Not enough overlapping data for a correlation matrix.")

# Ranking table
st.subheader("Country ranking")
st.markdown(f'<p class="panel-caption">{meta["label"]}, latest available value</p>', unsafe_allow_html=True)

search = st.text_input("Search country", placeholder="Type to filter…", label_visibility="collapsed")
ranking = filtered_latest.sort_values("value", ascending=False)
if search.strip():
    ranking = ranking[ranking["name"].str.contains(search.strip(), case=False, na=False)]

display = ranking[["name", "region", "income", "year", "value"]].head(60).copy()
display["value"] = display["value"].map(lambda v: format_value(v, metric))
display.insert(0, "Rank", range(1, len(display) + 1))
display.columns = ["Rank", "Country", "Region", "Income", "Year", "Value"]

st.dataframe(display, width='stretch', hide_index=True)

csv_bytes = ranking.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download filtered ranking (CSV)",
    data=csv_bytes,
    file_name=f"education_ranking_{metric}.csv",
    mime="text/csv",
)
