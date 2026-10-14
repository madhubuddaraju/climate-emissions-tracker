"""
Data quality checks run after every build.

Each check is SQL returning the number of failing rows (0 = pass).
`error` failures stop the pipeline; `warn` failures are recorded and logged.
Freshness checks catch the most common real-world failure: a source that
silently stops updating.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import duckdb
import pandas as pd

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Check:
    name: str
    sql: str
    severity: str = "error"


def unique(table: str, cols: str) -> Check:
    return Check(f"{table} unique on ({cols})",
                 f"SELECT count(*) FROM (SELECT {cols} FROM {table} GROUP BY ALL HAVING count(*) > 1)")


CHECKS = [
    unique("core.fct_emissions", "entity, year"),
    unique("core.fct_temperature_monthly", "series, month"),
    unique("core.fct_co2_monthly", "month"),
    unique("marts.annual_climate", "year"),
    Check("temperature anomalies within +/-4 C of pre-industrial",
          "SELECT count(*) FROM core.fct_temperature_monthly WHERE abs(anomaly_c) > 4"),
    Check("pre-industrial baseline averages to 0",
          """SELECT abs(avg(anomaly_c)) > 0.001 FROM core.fct_temperature_monthly
             WHERE series = 'GCAG' AND year BETWEEN 1850 AND 1900"""),
    Check("Mauna Loa CO2 between 300 and 500 ppm",
          "SELECT count(*) FROM core.fct_co2_monthly WHERE co2_ppm NOT BETWEEN 300 AND 500"),
    Check("annual CO2 concentration rises every complete year",
          """SELECT count(*) FROM (SELECT co2_ppm - lag(co2_ppm) OVER (ORDER BY year) AS d
             FROM marts.annual_climate WHERE co2_year_complete) WHERE d <= 0""", severity="warn"),
    Check("no negative emissions values",
          """SELECT count(*) FROM core.fct_emissions
             WHERE co2_mt < 0 OR coal_co2_mt < 0 OR oil_co2_mt < 0 OR gas_co2_mt < 0"""),
    Check("countries + international transport reconcile to World within 5%",
          """WITH y AS (SELECT max(year) y FROM core.fct_emissions WHERE entity = 'World' AND co2_mt IS NOT NULL),
             parts AS (SELECT sum(co2_mt) s FROM core.fct_emissions, y
                       WHERE year = y.y AND (entity_type = 'country'
                             OR entity IN ('International aviation', 'International shipping'))),
             world AS (SELECT co2_mt w FROM core.fct_emissions, y WHERE entity = 'World' AND year = y.y)
             SELECT abs(s / w - 1) > 0.05 FROM parts, world"""),
    Check("fuel mix sums to world total",
          """SELECT count(*) FROM (SELECT year, sum(co2_mt) s FROM marts.fuel_mix GROUP BY year) f
             JOIN core.fct_emissions e ON e.entity = 'World' AND e.year = f.year
             WHERE abs(f.s - e.co2_mt) > 0.01 * e.co2_mt"""),
    Check("temperature data is less than 120 days old",
          """SELECT date_diff('day', max(month), current_date) > 120
             FROM core.fct_temperature_monthly WHERE series = 'GCAG'""",
          severity="warn"),
    Check("CO2 data is less than 120 days old",
          "SELECT date_diff('day', max(month), current_date) > 120 FROM core.fct_co2_monthly", severity="warn"),
    Check("emissions data is at most 3 years behind",
          "SELECT year(current_date) - max(year) > 3 FROM core.fct_emissions WHERE entity = 'World'", severity="warn"),
]


class DataQualityError(RuntimeError):
    pass


def run_checks(con: duckdb.DuckDBPyConnection, checks: list[Check] | None = None,
               raise_on_error: bool = True) -> pd.DataFrame:
    rows = []
    for c in checks or CHECKS:
        failing = int(con.execute(c.sql).fetchone()[0] or 0)
        ok = failing == 0
        rows.append({"check_name": c.name, "severity": c.severity, "failing": failing, "passed": ok})
        level = logging.INFO if ok else (logging.ERROR if c.severity == "error" else logging.WARNING)
        log.log(level, "[%s] %s", "PASS" if ok else "FAIL", c.name)
    res = pd.DataFrame(rows)
    errors = res[~res.passed & (res.severity == "error")]
    if raise_on_error and not errors.empty:
        raise DataQualityError("failed checks: " + "; ".join(errors.check_name))
    return res
