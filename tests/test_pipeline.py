import duckdb
import pytest

from climate import ingest, quality
from climate.config import SOURCES


def test_pipeline_passes_all_error_checks(warehouse):
    _, summary = warehouse
    assert summary["checks_total"] >= 10
    assert "marts.annual_climate" in summary["models"]


def test_annual_mart_joins_all_three_sources(warehouse):
    path, _ = warehouse
    with duckdb.connect(str(path), read_only=True) as con:
        row = con.execute("SELECT temp_anomaly_c, co2_ppm, world_co2_mt FROM marts.annual_climate "
                          "WHERE year = 2022").fetchone()
    assert all(v is not None for v in row)
    assert 0.8 < row[0] < 2.0 and 400 < row[1] < 450 and 30_000 < row[2] < 45_000


def test_top_emitter_is_china(warehouse):
    path, _ = warehouse
    with duckdb.connect(str(path), read_only=True) as con:
        top = con.execute("SELECT entity FROM marts.country_emissions_latest ORDER BY rank_total LIMIT 1").fetchone()[0]
    assert top == "China"


def test_regions_never_counted_as_countries(warehouse):
    path, _ = warehouse
    with duckdb.connect(str(path), read_only=True) as con:
        n = con.execute("SELECT count(*) FROM marts.country_emissions_latest "
                        "WHERE entity IN ('World', 'Asia', 'Europe', 'European Union (27)')").fetchone()[0]
    assert n == 0


def test_quality_check_detects_failure():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE t AS SELECT 1 AS k UNION ALL SELECT 1")
    with pytest.raises(quality.DataQualityError):
        quality.run_checks(con, [quality.unique("t", "k")])


def test_ingest_validation_rejects_truncated_file():
    with pytest.raises(ingest.IngestError, match="truncated"):
        ingest._validate(SOURCES["co2_ppm"], b"a,b\n1,2\n")


def test_ingest_validation_rejects_html():
    body = b"<html>" + b"\n" * 5000
    with pytest.raises(ingest.IngestError, match="HTML"):
        ingest._validate(SOURCES["co2_ppm"], body)
