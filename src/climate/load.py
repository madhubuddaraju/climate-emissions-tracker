"""Load step: write staging tables to DuckDB and build the SQL models."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

from .config import SQL_DIR, WAREHOUSE

log = logging.getLogger(__name__)


def connect(path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    path = str(path or WAREHOUSE)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(path)
    for schema in ("staging", "core", "marts", "audit"):
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    return con


def write_table(con: duckdb.DuckDBPyConnection, schema: str, name: str, df: pd.DataFrame) -> None:
    con.register("_df", df)
    con.execute(f"CREATE OR REPLACE TABLE {schema}.{name} AS SELECT * FROM _df")
    con.unregister("_df")


def build_models(con: duckdb.DuckDBPyConnection, sql_dir: Path = SQL_DIR) -> list[str]:
    built = []
    for path in sorted((sql_dir / "core").glob("*.sql")) + sorted((sql_dir / "marts").glob("*.sql")):
        schema, name = path.parent.name, path.stem.split("__", 1)[-1]
        con.execute(f"CREATE OR REPLACE TABLE {schema}.{name} AS {path.read_text()}")
        n = con.execute(f"SELECT count(*) FROM {schema}.{name}").fetchone()[0]
        log.info("built %-34s %7d rows", f"{schema}.{name}", n)
        built.append(f"{schema}.{name}")
    return built
