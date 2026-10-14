from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
WAREHOUSE = APP.parents[1] / "data" / "climate.duckdb"


@pytest.mark.skipif(not WAREHOUSE.exists(), reason="run the pipeline first")
def test_dashboard_renders():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert len(at.metric) == 4
