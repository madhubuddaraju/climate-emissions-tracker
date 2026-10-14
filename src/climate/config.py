"""Paths and data source definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
WAREHOUSE = DATA_DIR / "climate.duckdb"
SQL_DIR = PROJECT_ROOT / "sql"
REPORTS_DIR = PROJECT_ROOT / "reports"


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    description: str
    publisher: str
    min_rows: int  # sanity floor: a truncated download fails fast


SOURCES: dict[str, Source] = {
    "emissions": Source(
        name="emissions",
        url="https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv",
        description="Annual CO2 and greenhouse gas emissions by country, 1750-present",
        publisher="Our World in Data / Global Carbon Project",
        min_rows=40_000,
    ),
    "temperature": Source(
        name="temperature",
        url="https://raw.githubusercontent.com/datasets/global-temp/main/data/monthly.csv",
        description="Monthly global surface temperature anomaly (NOAA GCAG and NASA GISTEMP)",
        publisher="NOAA NCEI / NASA GISS via datasets/global-temp",
        min_rows=3_000,
    ),
    "co2_ppm": Source(
        name="co2_ppm",
        url="https://raw.githubusercontent.com/datasets/co2-ppm/main/data/co2-mm-mlo.csv",
        description="Monthly mean atmospheric CO2 at Mauna Loa Observatory, 1958-present",
        publisher="NOAA Global Monitoring Laboratory via datasets/co2-ppm",
        min_rows=700,
    ),
}

# OWID aggregate rows kept for regional analysis (everything else without an ISO code is dropped)
REGIONS = [
    "World", "Africa", "Asia", "Europe", "North America", "South America", "Oceania",
    "European Union (27)", "High-income countries", "Upper-middle-income countries",
    "Lower-middle-income countries", "Low-income countries",
    "International aviation", "International shipping",
]

# 1850-1900 is the IPCC "pre-industrial" reference period used for the Paris Agreement targets
PREINDUSTRIAL = (1850, 1900)
