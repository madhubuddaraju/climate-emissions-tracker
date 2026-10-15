"""
Build the static web dashboard (docs/index.html, served by GitHub Pages) from the warehouse.

    python analysis/build_dashboard.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "climate.duckdb"
TEMPLATE = ROOT / "dashboard" / "template.html"
OUT = ROOT / "docs" / "index.html"
EXTRA_COUNTRIES = ["United Kingdom", "France", "Brazil", "Australia", "Nigeria", "South Africa"]


def rows(con, sql: str, params: list | None = None) -> list:
    return [[None if isinstance(v, float) and math.isnan(v) else v for v in r] for r in con.execute(sql, params or []).fetchall()]


def build() -> Path:
    if not WAREHOUSE.exists():
        sys.exit("warehouse not found - run `make pipeline` first")
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    d = {
        "annual": rows(con, "SELECT year, temp_anomaly_c, temp_anomaly_10yr_c, temp_year_complete, co2_ppm, co2_year_complete, "
                            "world_co2_mt, world_co2_yoy FROM marts.annual_climate ORDER BY year"),
        "co2": rows(con, "SELECT strftime(month, '%Y-%m'), co2_ppm, co2_deseasonalized_ppm FROM core.fct_co2_monthly ORDER BY month"),
        "latest": rows(con, "SELECT entity, co2_mt, co2_t_per_capita, share_global_pct, change_since_1990, change_since_paris_2015, "
                            "consumption_vs_territorial, year FROM marts.country_emissions_latest"),
        "fuel": rows(con, "SELECT year, fuel, round(co2_mt, 1) FROM marts.fuel_mix WHERE year >= 1950 ORDER BY year"),
        "decoup": rows(con, "SELECT entity, gdp_change, co2_change, co2_end_mt, status, end_year FROM marts.decoupling"),
        "growth": rows(con, "SELECT year, growth_ppm FROM marts.co2_growth WHERE growth_ppm IS NOT NULL"),
        "dq": rows(con, "SELECT check_name, severity, passed FROM audit.dq_results"),
        "sources": [[s, p, u, str(f)] for s, p, u, f in rows(con, "SELECT source, publisher, url, fetched_at FROM audit.sources")],
        "temp_last": con.execute("SELECT strftime(max(month), '%B %Y') FROM core.fct_temperature_monthly "
                                 "WHERE series = 'GCAG'").fetchone()[0],
    }
    top = list(dict.fromkeys([r[0] for r in d["latest"][:25]] + EXTRA_COUNTRIES))
    d["hist"] = {e: rows(con, "SELECT year, round(co2_mt, 1), round(co2_t_per_capita, 2) FROM core.fct_emissions "
                              "WHERE entity = ? AND year >= 1950 AND co2_mt IS NOT NULL ORDER BY year", [e]) for e in top}
    con.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(TEMPLATE.read_text().replace("__DATA__", json.dumps(d, separators=(",", ":"), default=str)))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")
    return OUT


if __name__ == "__main__":
    build()
