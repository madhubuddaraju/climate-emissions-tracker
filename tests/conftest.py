import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def raw_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("raw")
    for f in FIXTURES.glob("*.*"):
        if f.suffix in (".csv", ".json"):
            shutil.copy(f, d / f.name)
    return d


@pytest.fixture(scope="session")
def warehouse(raw_dir, tmp_path_factory):
    from climate import run
    path = tmp_path_factory.mktemp("wh") / "test.duckdb"
    summary = run.run(warehouse=path, raw_dir=raw_dir, skip_ingest=True)
    return path, summary
