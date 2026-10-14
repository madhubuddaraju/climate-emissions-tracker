"""
Build charts and the findings report from the warehouse.

    python analysis/report.py

Writes reports/figures/*.png and reports/insights.md. Every number in the
report is computed here from the marts, so the weekly refresh keeps it current.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "climate.duckdb"
FIG = ROOT / "reports" / "figures"

BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"
INK, INK2, GRID, MUTED = "#0b0b0b", "#52514e", "#e6e5e1", "#b9b8b3"
plt.rcParams.update({
    "figure.dpi": 130, "savefig.bbox": "tight", "font.size": 10,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titleweight": "bold", "axes.titlesize": 12,
    "axes.titlecolor": INK, "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": INK2, "ytick.color": INK2, "legend.frameon": False,
})


def source_note(fig, text: str) -> None:
    fig.text(0.01, -0.02, text, fontsize=8, color=INK2, ha="left", va="top")


def fig_temperature(annual: pd.DataFrame) -> None:
    a = annual[annual.temp_year_complete]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(a.year, a.temp_anomaly_c, width=0.8,
           color=np.where(a.temp_anomaly_c >= 0, ORANGE, BLUE), alpha=0.55, linewidth=0)
    ax.plot(a.year, a.temp_anomaly_10yr_c, color=INK, linewidth=2, label="10-year average")
    ax.axhline(1.5, color=INK2, linestyle=(0, (4, 3)), linewidth=1)
    ax.text(a.year.min() + 1, 1.53, "Paris Agreement 1.5 °C limit", fontsize=9, color=INK2, va="bottom")
    last = a.iloc[-1]
    ax.annotate(f"{int(last.year)}: {last.temp_anomaly_c:+.2f} °C", (last.year, last.temp_anomaly_c),
                xytext=(-115, -28), textcoords="offset points", fontsize=9, color=INK,
                arrowprops={"arrowstyle": "-", "color": INK2, "lw": 0.8})
    ax.set_ylabel("°C vs 1850-1900")
    ax.set_title("Global surface temperature anomaly")
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.92))
    ax.grid(axis="x", visible=False)
    source_note(fig, "Source: NOAA NCEI global surface temperature (GCAG), re-baselined to 1850-1900.")
    fig.savefig(FIG / "temperature_anomaly.png")
    plt.close(fig)


def fig_keeling(co2: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(co2.month, co2.co2_ppm, color=BLUE, linewidth=1, alpha=0.6, label="Monthly mean")
    ax.plot(co2.month, co2.co2_deseasonalized_ppm, color=INK, linewidth=2, label="Seasonally adjusted")
    last = co2.iloc[-1]
    ax.annotate(f"{last.month:%b %Y}: {last.co2_ppm:.1f} ppm", (last.month, last.co2_ppm),
                xytext=(-130, 0), textcoords="offset points", fontsize=9, va="center",
                arrowprops={"arrowstyle": "-", "color": INK2, "lw": 0.8})
    ax.set_ylabel("CO₂ (ppm)")
    ax.set_title("Atmospheric CO₂ at Mauna Loa (the Keeling Curve)")
    ax.legend(loc="upper left")
    source_note(fig, "Source: NOAA Global Monitoring Laboratory, Mauna Loa Observatory.")
    fig.savefig(FIG / "keeling_curve.png")
    plt.close(fig)


def fig_temp_vs_co2(df: pd.DataFrame, slope: float, intercept: float, r2: float) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    sc = ax.scatter(df.co2_ppm, df.temp_anomaly_c, c=df.year, cmap="Blues", s=26,
                    edgecolor="white", linewidth=0.6, vmin=1940)
    x = np.linspace(df.co2_ppm.min(), df.co2_ppm.max(), 50)
    ax.plot(x, slope * x + intercept, color=ORANGE, linewidth=2)
    ax.text(0.03, 0.95, f"+{slope * 100:.2f} °C per 100 ppm\nR² = {r2:.2f}", transform=ax.transAxes,
            va="top", fontsize=10, color=INK)
    fig.colorbar(sc, ax=ax, label="Year", shrink=0.8)
    ax.set_xlabel("Atmospheric CO₂ (ppm, annual mean)")
    ax.set_ylabel("Temperature anomaly (°C vs 1850-1900)")
    ax.set_title("Temperature tracks CO₂ concentration")
    fig.savefig(FIG / "temp_vs_co2.png")
    plt.close(fig)


def fig_top_emitters(top: pd.DataFrame, year: int) -> None:
    t = top.sort_values("co2_mt")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True, gridspec_kw={"width_ratios": [1.2, 1]})
    ax = axes[0]
    ax.barh(t.entity, t.co2_mt / 1000, color=BLUE, height=0.65)
    for y, (v, pc) in enumerate(zip(t.co2_mt, t.co2_t_per_capita, strict=True)):
        ax.text(v / 1000, y, f"  {v / 1000:.1f} Gt · {pc:.1f} t/person", va="center", fontsize=8.5, color=INK2)
    ax.set_xlim(0, t.co2_mt.max() / 1000 * 1.7)
    ax.tick_params(axis="y", length=0)
    ax.set_title(f"Largest emitters, {year}")
    ax.set_xlabel("CO₂ (billion tonnes)")
    ax.grid(axis="y", visible=False)
    ax = axes[1]
    ch = t.change_since_1990 * 100
    ax.barh(t.entity, ch, color=np.where(ch >= 0, ORANGE, BLUE), height=0.65)
    for y, v in enumerate(ch):
        ax.text(v, y, f" {v:+.0f}%" if v >= 0 else f"{v:+.0f}% ", va="center", ha="left" if v >= 0 else "right",
                fontsize=8.5, color=INK2)
    ax.axvline(0, color=INK2, linewidth=0.8)
    lo, hi = min(ch.min(), 0), ch.max()
    ax.set_xlim(lo - 45, hi * 1.25)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_title("Change since 1990")
    ax.grid(axis="y", visible=False)
    source_note(fig, "Source: Our World in Data / Global Carbon Project. Territorial fossil CO₂, excluding land use.")
    fig.savefig(FIG / "top_emitters.png")
    plt.close(fig)


def fig_fuel_mix(fuel: pd.DataFrame) -> None:
    p = fuel[fuel.year >= 1950].pivot(index="year", columns="fuel", values="co2_mt").fillna(0) / 1000
    p["other"] = p.get("other", 0) + p.pop("flaring")  # flaring is too small to read on its own
    p = p[["coal", "oil", "gas", "cement", "other"]]
    colors = [INK2, ORANGE, BLUE, YELLOW, MUTED]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.stackplot(p.index, p.T.values, colors=colors, edgecolor="white", linewidth=0.6,
                 labels=["Coal", "Oil", "Gas", "Cement", "Flaring & other"])
    ax.set_ylabel("CO₂ (billion tonnes)")
    ax.set_title("World fossil CO₂ emissions by source")
    ax.legend(loc="upper left", ncol=3)
    ax.grid(axis="x", visible=False)
    source_note(fig, "Source: Our World in Data / Global Carbon Project.")
    fig.savefig(FIG / "fuel_mix.png")
    plt.close(fig)


def build(warehouse: Path = WAREHOUSE) -> str:
    if not warehouse.exists():
        sys.exit("warehouse not found - run `make pipeline` first")
    FIG.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse), read_only=True)
    annual = con.execute("SELECT * FROM marts.annual_climate ORDER BY year").df()
    co2 = con.execute("SELECT * FROM core.fct_co2_monthly ORDER BY month").df()
    fuel = con.execute("SELECT * FROM marts.fuel_mix").df()
    countries = con.execute("SELECT * FROM marts.country_emissions_latest").df()
    decades = con.execute("SELECT * FROM marts.decade_summary ORDER BY decade").df()
    growth = con.execute("SELECT * FROM marts.co2_growth ORDER BY year").df()
    decoup = con.execute("SELECT * FROM marts.decoupling").df()
    regions = con.execute("""
        SELECT region, max(co2_mt) FILTER (WHERE year = (SELECT max(year) FROM marts.regional_emissions))
                     - max(co2_mt) FILTER (WHERE year = 2015) AS change_mt
        FROM marts.regional_emissions WHERE grouping = 'continent' GROUP BY region""").df().set_index("region")
    sources = con.execute("SELECT source, publisher, url, fetched_at FROM audit.sources").df()
    dq = con.execute("SELECT count(*) n, sum(passed::INT) ok FROM audit.dq_results").fetchone()
    temp_last = con.execute("SELECT max(month) FROM core.fct_temperature_monthly WHERE series='GCAG'").fetchone()[0]
    con.close()

    complete = annual[annual.temp_year_complete]
    # warming trend since 1975 (ordinary least squares on annual means)
    recent = complete[complete.year >= 1975]
    rate_per_decade = np.polyfit(recent.year, recent.temp_anomaly_c, 1)[0] * 10
    # temperature vs CO2 concentration
    both = complete.dropna(subset=["co2_ppm"]).query("co2_year_complete")
    slope, intercept = np.polyfit(both.co2_ppm, both.temp_anomaly_c, 1)
    r2 = np.corrcoef(both.co2_ppm, both.temp_anomaly_c)[0, 1] ** 2
    # when would the 10-year mean reach 1.5 C on the current linear trend?
    trend_now = np.polyval(np.polyfit(recent.year, recent.temp_anomaly_c, 1), complete.year.max())
    years_to_15 = (1.5 - trend_now) / (rate_per_decade / 10)

    hottest = complete.nlargest(10, "temp_anomaly_c")
    last = complete.iloc[-1]
    emis = annual.dropna(subset=["world_co2_mt"])
    e_last = emis.iloc[-1]
    e_1990 = emis[emis.year == 1990].iloc[0]
    co2_last = co2.iloc[-1]
    ppm_1960 = annual.loc[annual.year == 1960, "co2_ppm"].iloc[0]
    g10 = growth.dropna(subset=["growth_ppm"])
    top10 = countries.head(10)
    emis_year = int(countries.year.iloc[0])
    top3_share = countries.head(3).share_global_pct.sum()
    absolute = decoup[decoup.status == "Absolute decoupling"].sort_values("co2_end_mt", ascending=False)

    fig_temperature(annual)
    fig_keeling(co2)
    fig_temp_vs_co2(both, slope, intercept, r2)
    fig_top_emitters(top10, emis_year)
    fig_fuel_mix(fuel)

    growth_recent = g10.growth_ppm.tail(10).mean()
    growth_1960s = g10[g10.year.between(1960, 1969)].growth_ppm.mean()
    emis_vs_1990 = e_last.world_co2_mt / e_1990.world_co2_mt - 1
    india_1990 = countries.set_index("entity").loc["India", "change_since_1990"]
    pc_lo, pc_hi = top10.co2_t_per_capita.idxmin(), top10.co2_t_per_capita.idxmax()
    pc_ratio = top10.co2_t_per_capita.max() / top10.co2_t_per_capita.min()
    leader = top10.iloc[0]

    def gt(region: str) -> str:
        return f"{regions.change_mt[region] / 1000:+.1f} Gt"

    def pctf(x: float) -> str:
        return f"{x * 100:+.0f}%"

    now = datetime.now(UTC).strftime("%Y-%m-%d")
    md = f"""# Climate & emissions findings

_Auto-generated by `analysis/report.py` on {now}. Temperature data through {temp_last:%B %Y},
CO₂ concentration through {co2_last.month:%B %Y}, emissions through {emis_year}.
{int(dq[1])}/{int(dq[0])} data quality checks passed._

## Headline numbers

| Indicator | Value |
|---|---|
| Global temperature, {int(last.year)} | **{last.temp_anomaly_c:+.2f} °C** vs 1850-1900 |
| Warming rate since 1975 | **{rate_per_decade:+.2f} °C per decade** |
| Atmospheric CO₂, {co2_last.month:%b %Y} | **{co2_last.co2_ppm:.1f} ppm** (1960: {ppm_1960:.0f}; pre-industrial ~280) |
| CO₂ growth, last 10 years | **{growth_recent:.2f} ppm/year** (1960s: {growth_1960s:.2f}) |
| World fossil CO₂, {int(e_last.year)} | **{e_last.world_co2_mt / 1000:.1f} Gt** ({pctf(emis_vs_1990)} vs 1990) |
| Share from top 3 emitters | **{top3_share:.0f}%** ({", ".join(countries.head(3).entity)}) |

## Findings

1. **The ten hottest years on record are all since {int(hottest.year.min())}.** {int(hottest.iloc[0].year)} was the
   warmest at {hottest.iloc[0].temp_anomaly_c:+.2f} °C. The 10-year average is now {last.temp_anomaly_10yr_c:+.2f} °C.
2. **At the post-1975 trend, the long-term average crosses 1.5 °C around {int(complete.year.max() + years_to_15)}.**
   This is a straight-line extrapolation of {rate_per_decade:+.2f} °C/decade, not a climate model projection.
3. **Temperature tracks CO₂ closely.** Across {len(both)} years, each additional 100 ppm of CO₂ lines up with
   {slope * 100:+.2f} °C of warming (R² = {r2:.2f}). Correlation alone isn't proof of cause, but it matches the
   physics: CO₂ traps outgoing heat.
4. **CO₂ is accumulating faster, not slower.** Concentration now rises about
   {growth_recent:.1f} ppm a year, roughly {growth_recent / growth_1960s:.1f}x the 1960s rate.
5. **Emissions are still rising globally** ({e_last.world_co2_yoy * 100:+.1f}% in {int(e_last.year)}).
   Since 2015 Asia's annual emissions changed by {gt("Asia")} while Europe ({gt("Europe")})
   and North America ({gt("North America")}) cut theirs. {leader.entity} emits
   {leader.share_global_pct:.0f}% of the world total; India is up {pctf(india_1990)} since 1990.
6. **{len(absolute)} countries cut CO₂ while growing GDP** between 2010 and {int(decoup.end_year.max())}
   (absolute decoupling), including {", ".join(absolute.entity.head(5))}.
7. **Per-person emissions vary {pc_ratio:.0f}x among the largest emitters**: from
   {top10.co2_t_per_capita[pc_lo]:.1f} t ({top10.entity[pc_lo]}) to
   {top10.co2_t_per_capita[pc_hi]:.1f} t ({top10.entity[pc_hi]}) per person.

![Temperature anomaly](figures/temperature_anomaly.png)
![Keeling curve](figures/keeling_curve.png)
![Temperature vs CO2](figures/temp_vs_co2.png)
![Top emitters](figures/top_emitters.png)
![Fuel mix](figures/fuel_mix.png)

## Warming by decade

| Decade | Avg anomaly (°C) | Change vs previous | Avg CO₂ (ppm) | Fossil CO₂ emitted (Gt) |
|---|---|---|---|---|
""" + "\n".join(
        f"| {int(r.decade)}s{'*' if r.years < 10 else ''} | {r.avg_temp_anomaly_c:+.2f} | "
        f"{'' if pd.isna(r.warming_vs_prev_decade_c) else f'{r.warming_vs_prev_decade_c:+.2f}'} | "
        f"{'' if pd.isna(r.avg_co2_ppm) else f'{r.avg_co2_ppm:.0f}'} | {r.decade_co2_gt:.0f} |"
        for r in decades[decades.decade >= 1950].itertuples()) + """

\\* decade in progress

## Top 10 emitters

| Country | CO₂ (Mt) | t per person | Share of world | Since 1990 | Since 2015 | Consumption vs territorial |
|---|---|---|---|---|---|---|
""" + "\n".join(
        f"| {r.entity} | {r.co2_mt:,.0f} | {r.co2_t_per_capita:.1f} | {r.share_global_pct:.1f}% | "
        f"{pctf(r.change_since_1990)} | {pctf(r.change_since_paris_2015)} | "
        f"{'' if pd.isna(r.consumption_vs_territorial) else pctf(r.consumption_vs_territorial)} |"
        for r in top10.itertuples()) + """

_Consumption vs territorial: positive means the country's consumption causes more CO₂ (including imported
goods) than it emits at home._

## Sources

| Dataset | Publisher | Fetched (UTC) |
|---|---|---|
""" + "\n".join(f"| [{r.source}]({r.url}) | {r.publisher} | {r.fetched_at[:16].replace('T', ' ')} |"
                for r in sources.itertuples()) + "\n"

    (ROOT / "reports" / "insights.md").write_text(md)
    print(f"wrote reports/insights.md and {len(list(FIG.glob('*.png')))} figures")
    return md


if __name__ == "__main__":
    build()
