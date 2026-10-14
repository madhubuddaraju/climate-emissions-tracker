"""
Rebuild the small test fixtures from a full download in data/raw.

    python tests/fixtures/make_fixtures.py

Fixtures keep tests offline and fast while using real upstream formats.
"""

import json
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
OUT = Path(__file__).resolve().parent

YEARS = [1990, 2005, 2010, 2015, 2020, 2021, 2022, 2023, 2024]

emis = pd.read_csv(RAW / "emissions.csv", low_memory=False)
emis[emis.year.isin(YEARS)].to_csv(OUT / "emissions.csv", index=False)

temp = pd.read_csv(RAW / "temperature.csv", dtype=str)
yr = temp["Year"].str[:4].astype(int)
keep = yr.between(1850, 1905) | yr.between(1950, 1981) | yr.between(2015, 2026)
temp[keep].to_csv(OUT / "temperature.csv", index=False)

lines = (RAW / "co2_ppm.csv").read_text().splitlines()
header, rows = lines[0], lines[1:]
rows = [r for r in rows if r[:4] in {"1959", "1960", "1990", "2015", "2020", "2021", "2022", "2023", "2024", "2025"}]
(OUT / "co2_ppm.csv").write_text("\n".join([header, *rows]) + "\n")

manifest = {name: {"url": f"fixture://{name}", "publisher": "test fixture", "fetched_at": "2026-01-01T00:00:00+00:00",
                   "bytes": 0, "rows": 0, "sha256": "", "changed_since_last_fetch": False}
            for name in ("emissions", "temperature", "co2_ppm")}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
print("fixtures written to", OUT)
