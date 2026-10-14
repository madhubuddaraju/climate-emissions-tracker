"""
Interactive climate dashboard.

    streamlit run dashboard/app.py
"""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "climate.duckdb"
BLUE, ORANGE, AQUA, INK = "#2a78d6", "#eb6834", "#1baf7a", "#52514e"

st.set_page_config(page_title="Climate & Emissions Tracker", layout="wide")


@st.cache_data(ttl=3600)
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        return con.execute(sql, list(params)).df()


if not WAREHOUSE.exists():
    st.error("Warehouse not found. Run `make pipeline` first.")
    st.stop()

annual = q("SELECT * FROM marts.annual_climate ORDER BY year")
complete = annual[annual.temp_year_complete]
co2 = q("SELECT * FROM core.fct_co2_monthly ORDER BY month")
latest = q("SELECT * FROM marts.country_emissions_latest")

st.title("Climate & Emissions Tracker")
st.caption(f"Temperature through {q('SELECT max(month) m FROM core.fct_temperature_monthly').m[0]:%B %Y} · "
           f"CO₂ through {co2.month.iloc[-1]:%B %Y} · emissions through {int(latest.year.iloc[0])}")

last, prev = complete.iloc[-1], complete.iloc[-2]
emis = annual.dropna(subset=["world_co2_mt"])
k = st.columns(4)
k[0].metric(f"Global temperature {int(last.year)}", f"{last.temp_anomaly_c:+.2f} °C",
            f"{last.temp_anomaly_c - prev.temp_anomaly_c:+.2f} °C vs {int(prev.year)}", delta_color="inverse")
k[1].metric("10-year average", f"{last.temp_anomaly_10yr_c:+.2f} °C", "vs 1850-1900", delta_color="off")
k[2].metric(f"CO₂ {co2.month.iloc[-1]:%b %Y}", f"{co2.co2_ppm.iloc[-1]:.1f} ppm",
            f"{co2.co2_ppm.iloc[-1] - co2.co2_ppm.iloc[-13]:+.2f} ppm vs a year earlier", delta_color="inverse")
k[3].metric(f"World fossil CO₂ {int(emis.year.iloc[-1])}", f"{emis.world_co2_mt.iloc[-1] / 1000:.1f} Gt",
            f"{emis.world_co2_yoy.iloc[-1]:+.1%} vs prior year", delta_color="inverse")

tab1, tab2, tab3, tab4 = st.tabs(["Global trends", "Countries", "Decoupling", "Data & quality"])

with tab1:
    c1, c2 = st.columns(2)
    fig = go.Figure()
    fig.add_bar(x=complete.year, y=complete.temp_anomaly_c, name="Annual",
                marker_color=[ORANGE if v >= 0 else BLUE for v in complete.temp_anomaly_c], opacity=0.55)
    fig.add_scatter(x=complete.year, y=complete.temp_anomaly_10yr_c, name="10-year average",
                    line={"color": INK, "width": 2.5})
    fig.add_hline(y=1.5, line_dash="dash", annotation_text="1.5 °C Paris limit", annotation_position="top left")
    fig.update_layout(title="Temperature anomaly (°C vs 1850-1900)", hovermode="x unified", legend={"orientation": "h"})
    c1.plotly_chart(fig, use_container_width=True)

    fig = go.Figure()
    fig.add_scatter(x=co2.month, y=co2.co2_ppm, name="Monthly mean", line={"color": BLUE, "width": 1})
    fig.add_scatter(x=co2.month, y=co2.co2_deseasonalized_ppm, name="Seasonally adjusted",
                    line={"color": INK, "width": 2})
    fig.update_layout(title="Atmospheric CO₂ at Mauna Loa (ppm)", hovermode="x unified", legend={"orientation": "h"})
    c2.plotly_chart(fig, use_container_width=True)

    fuel = q("SELECT * FROM marts.fuel_mix WHERE year >= 1950")
    fig = px.area(fuel, x="year", y="co2_mt", color="fuel", title="World fossil CO₂ by source (Mt)",
                  color_discrete_sequence=[BLUE, ORANGE, AQUA, "#eda100", "#e87ba4", "#6250d6"])
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    countries = q("SELECT DISTINCT entity FROM core.fct_emissions WHERE entity_type = 'country' ORDER BY 1").entity
    default = [c for c in ["China", "United States", "India", "Germany", "United Kingdom"] if c in set(countries)]
    picked = st.multiselect("Countries", countries, default=default)
    metric = st.radio("Measure", ["co2_mt", "co2_t_per_capita", "cumulative_co2_mt"], horizontal=True,
                      format_func={"co2_mt": "Total CO₂ (Mt)", "co2_t_per_capita": "CO₂ per person (t)",
                                   "cumulative_co2_mt": "Cumulative CO₂ (Mt)"}.get)
    start = st.slider("From year", 1850, int(latest.year.iloc[0]) - 5, 1950)
    if picked:
        marks = ",".join("?" * len(picked))
        hist = q(f"SELECT entity, year, {metric} AS value FROM core.fct_emissions "
                 f"WHERE entity IN ({marks}) AND year >= ? ORDER BY year", (*picked, start))
        st.plotly_chart(px.line(hist, x="year", y="value", color="entity", labels={"value": ""}),
                        use_container_width=True)
    st.subheader(f"All countries, {int(latest.year.iloc[0])}")
    st.dataframe(latest[["rank_total", "entity", "co2_mt", "co2_t_per_capita", "share_global_pct",
                         "change_since_1990", "change_since_paris_2015", "consumption_vs_territorial"]],
                 use_container_width=True, hide_index=True,
                 column_config={"change_since_1990": st.column_config.NumberColumn(format="percent"),
                                "change_since_paris_2015": st.column_config.NumberColumn(format="percent"),
                                "consumption_vs_territorial": st.column_config.NumberColumn(format="percent")})

with tab3:
    d = q("SELECT * FROM marts.decoupling")
    st.markdown("Did countries grow their economy **and** cut CO₂? Comparing 2010 with the latest year with GDP data.")
    fig = px.scatter(d, x="gdp_change", y="co2_change", size="co2_end_mt", color="status", hover_name="entity",
                     color_discrete_map={"Absolute decoupling": AQUA, "Relative decoupling": BLUE,
                                         "Coupled growth": ORANGE, "Economic decline": INK},
                     labels={"gdp_change": "GDP change", "co2_change": "CO₂ change"})
    fig.add_hline(y=0, line_color=INK, line_width=1)
    fig.add_vline(x=0, line_color=INK, line_width=1)
    fig.update_layout(xaxis_tickformat=".0%", yaxis_tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.dataframe(q("SELECT source, publisher, fetched_at, rows, changed_since_last_fetch, url FROM audit.sources"),
                 use_container_width=True, hide_index=True)
    st.dataframe(q("SELECT check_name, severity, passed FROM audit.dq_results"),
                 use_container_width=True, hide_index=True)
    st.dataframe(q("SELECT * FROM audit.pipeline_runs ORDER BY started_at DESC LIMIT 10"),
                 use_container_width=True, hide_index=True)
