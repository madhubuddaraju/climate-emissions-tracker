import numpy as np
import pandas as pd
import pytest

from climate import transform
from climate.transform import Staged


def _temp_frame():
    months = pd.period_range("1850-01", "1990-12", freq="M").astype(str)
    gcag = pd.DataFrame({"Source": "GCAG", "Year": months, "Mean": "-0.30"})
    gis = pd.DataFrame({"Source": "GISTEMP", "Year": months[months >= "1880-01"], "Mean": "0.10"})
    return pd.concat([gcag, gis], ignore_index=True)


def test_temperature_rebaselined_to_preindustrial():
    out = transform.stage_temperature(_temp_frame(), Staged())
    pre = out[(out.series == "GCAG") & (out.month.dt.year <= 1900)]
    assert pre.anomaly_c.abs().max() == pytest.approx(0, abs=1e-9)


def test_gistemp_aligned_to_gcag_over_overlap():
    out = transform.stage_temperature(_temp_frame(), Staged())
    ov = out[out.month.dt.year.between(1951, 1980)]
    g = ov.groupby("series").anomaly_c.mean()
    assert g["GISTEMP"] == pytest.approx(g["GCAG"], abs=1e-9)


def test_temperature_rejects_bad_values():
    raw = _temp_frame()
    raw.loc[0, "Mean"] = "n/a"
    raw.loc[1, "Mean"] = "99"
    st = Staged()
    transform.stage_temperature(raw, st)
    assert st.rejects_df.rows.sum() == 2


def test_co2_missing_sentinels_removed(tmp_path):
    p = tmp_path / "co2.csv"
    p.write_text("Date,Decimal Date,Average,Interpolated,Trend,Number of Days\n"
                 "1958-03,1958.2027,315.71,314.44,-01,-9.99,-0.99\n"
                 "1958-06,1958.4548,-99.99,317.10,-01,-9.99,-0.99\n"
                 "2024-05,2024.375,426.90,423.10,30,0.70,0.25\n")
    st = Staged()
    out = transform.stage_co2_ppm(p, st)
    assert list(out.co2_ppm) == [315.71, 426.90]
    assert np.isnan(out.days.iloc[0]) and out.days.iloc[1] == 30
    assert st.rejects_df.rows.sum() == 1


def test_emissions_classifies_entities():
    cols = transform.EMISSION_COLS
    raw = pd.DataFrame([{c: None for c in cols} for _ in range(4)])
    raw["country"] = ["France", "World", "Asia (GCP)", "Kosovo"]
    raw["iso_code"] = ["FRA", None, None, None]
    raw["year"] = 2020
    raw["co2"] = [300, 35000, 18000, 7]
    st = Staged()
    out = transform.stage_emissions(raw, st)
    assert dict(zip(out.country, out.entity_type, strict=True)) == {"France": "country", "World": "region"}
    assert st.rejects_df.rows.sum() == 2


def test_emissions_missing_columns_fail_loudly():
    with pytest.raises(ValueError, match="missing expected columns"):
        transform.stage_emissions(pd.DataFrame({"country": ["x"]}), Staged())
