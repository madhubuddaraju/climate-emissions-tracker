"""
Transform step: parse each raw source into a tidy, typed staging table.

Notable handling:
- Temperature series use different baselines (NOAA GCAG: 1901-2000, NASA GISTEMP:
  1951-1980). Both are re-baselined to 1850-1900 ("pre-industrial", as used by the
  IPCC and the Paris Agreement) so they are comparable with the 1.5 C / 2 C targets.
  GISTEMP starts in 1880, so it is aligned to GCAG over their 1951-1980 overlap.
- Mauna Loa uses -99.99 for missing monthly means.
- OWID mixes countries and aggregates (continents, income groups); entities are
  classified so they are never double counted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .config import PREINDUSTRIAL, RAW_DIR, REGIONS

log = logging.getLogger(__name__)

EMISSION_COLS = [
    "country", "year", "iso_code", "population", "gdp", "co2", "co2_per_capita", "co2_per_gdp",
    "coal_co2", "oil_co2", "gas_co2", "cement_co2", "flaring_co2", "other_industry_co2",
    "land_use_change_co2", "consumption_co2", "trade_co2", "cumulative_co2", "share_global_co2",
    "share_global_cumulative_co2", "total_ghg", "methane", "nitrous_oxide", "energy_per_capita",
    "primary_energy_consumption", "temperature_change_from_ghg",
]


@dataclass
class Staged:
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    rejects: list[dict] = field(default_factory=list)

    def reject(self, source: str, n: int, reason: str) -> None:
        if n:
            self.rejects.append({"source": source, "rows": int(n), "reason": reason})
            log.warning("%s: rejected %d rows (%s)", source, n, reason)

    @property
    def rejects_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.rejects, columns=["source", "rows", "reason"])


def stage_temperature(raw: pd.DataFrame, st: Staged) -> pd.DataFrame:
    df = raw.rename(columns={"Source": "series", "Year": "month", "Mean": "anomaly_raw_c"})
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m", errors="coerce")
    df["anomaly_raw_c"] = pd.to_numeric(df["anomaly_raw_c"], errors="coerce")
    bad = df["month"].isna() | df["anomaly_raw_c"].isna() | ~df["anomaly_raw_c"].between(-5, 5)
    st.reject("temperature", bad.sum(), "unparseable or out-of-range anomaly")
    df = df[~bad].drop_duplicates(["series", "month"]).sort_values(["series", "month"])

    year = df["month"].dt.year
    gcag = df["series"] == "GCAG"
    pre = gcag & year.between(*PREINDUSTRIAL)
    if pre.sum() < 12 * 40:
        raise ValueError("GCAG series does not cover the 1850-1900 reference period")
    gcag_offset = df.loc[pre, "anomaly_raw_c"].mean()
    df.loc[gcag, "anomaly_c"] = df.loc[gcag, "anomaly_raw_c"] - gcag_offset

    # align GISTEMP to GCAG's pre-industrial-based scale over their 1951-1980 overlap
    gis = df["series"] == "GISTEMP"
    if gis.any():
        ov = year.between(1951, 1980)
        gis_offset = df.loc[gis & ov, "anomaly_raw_c"].mean() - df.loc[gcag & ov, "anomaly_c"].mean()
        df.loc[gis, "anomaly_c"] = df.loc[gis, "anomaly_raw_c"] - gis_offset

    df["anomaly_c"] = df["anomaly_c"].round(4)
    log.info("temperature: GCAG re-baselined by %+.3f C to 1850-1900", -gcag_offset)
    return df[["series", "month", "anomaly_raw_c", "anomaly_c"]].reset_index(drop=True)


def stage_co2_ppm(raw_path: Path, st: Staged) -> pd.DataFrame:
    # The mirror's header has fewer names than data columns, so name them explicitly
    # (order follows NOAA's co2_mm_mlo file).
    names = ["month", "decimal_date", "co2_ppm", "co2_deseasonalized_ppm", "days", "std_dev", "uncertainty"]
    df = pd.read_csv(raw_path, header=None, skiprows=1, names=names, dtype=str)
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m", errors="coerce")
    for c in names[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.replace({-99.99: np.nan, -9.99: np.nan, -0.99: np.nan})
    df.loc[df["days"] < 0, "days"] = np.nan

    bad = df["month"].isna() | df["co2_ppm"].isna() | ~df["co2_ppm"].between(280, 600)
    st.reject("co2_ppm", bad.sum(), "missing or implausible monthly mean")
    df = df[~bad].drop_duplicates("month").sort_values("month")
    return df[["month", "co2_ppm", "co2_deseasonalized_ppm", "days"]].reset_index(drop=True)


def stage_emissions(raw: pd.DataFrame, st: Staged) -> pd.DataFrame:
    missing = set(EMISSION_COLS) - set(raw.columns)
    if missing:
        raise ValueError(f"emissions source is missing expected columns: {sorted(missing)}")
    df = raw[EMISSION_COLS].copy()
    num = [c for c in EMISSION_COLS if c not in ("country", "iso_code")]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")
    df["year"] = df["year"].astype("Int64")

    is_country = df["iso_code"].notna() & ~df["iso_code"].str.startswith("OWID", na=False)
    is_region = df["country"].isin(REGIONS)
    df["entity_type"] = np.select([is_country, is_region], ["country", "region"], default="other")
    dropped = df["entity_type"] == "other"
    st.reject("emissions", dropped.sum(), "aggregate or territory not used in analysis")
    df = df[~dropped]

    negative = df["co2"] < 0
    st.reject("emissions", negative.sum(), "negative territorial CO2")
    df = df[~negative].drop_duplicates(["country", "year"])
    df["iso_code"] = df["iso_code"].where(df["entity_type"] == "country")
    return df.reset_index(drop=True)


def transform(raw_dir: Path = RAW_DIR) -> Staged:
    st = Staged()
    temp_raw = pd.read_csv(raw_dir / "temperature.csv", dtype=str)
    emis_raw = pd.read_csv(raw_dir / "emissions.csv", dtype={"iso_code": str, "country": str}, low_memory=False)
    st.tables = {
        "stg_temperature": stage_temperature(temp_raw, st),
        "stg_co2_ppm": stage_co2_ppm(raw_dir / "co2_ppm.csv", st),
        "stg_emissions": stage_emissions(emis_raw, st),
    }
    for name, df in st.tables.items():
        log.info("staged %-16s %7d rows", name, len(df))
    return st
