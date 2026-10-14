"""
Pipeline orchestrator.

    python -m climate              # ingest (cached 12h) -> stage -> build -> check
    python -m climate --refresh    # force a fresh download of every source
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from . import ingest, load, quality, transform
from .config import RAW_DIR

log = logging.getLogger("climate")


def run(warehouse: Path | str | None = None, raw_dir: Path = RAW_DIR,
        refresh: bool = False, skip_ingest: bool = False) -> dict:
    run_id, t0 = uuid.uuid4().hex[:12], time.perf_counter()
    started = datetime.now(UTC).replace(tzinfo=None)

    if skip_ingest:
        manifest = json.loads((raw_dir / "manifest.json").read_text())
    else:
        manifest = ingest.ingest(raw_dir, force=refresh)
    staged = transform.transform(raw_dir)

    con = load.connect(warehouse)
    status = "failed"
    try:
        for name, df in staged.tables.items():
            load.write_table(con, "staging", name, df)
        load.write_table(con, "audit", "rejects", staged.rejects_df)
        load.write_table(con, "audit", "sources", pd.DataFrame(
            [{"source": k, **v} for k, v in manifest.items()]))
        models = load.build_models(con)
        dq = quality.run_checks(con)
        dq["run_id"] = run_id
        load.write_table(con, "audit", "dq_results", dq)
        status = "success"
        return {"run_id": run_id, "models": models, "checks_passed": int(dq.passed.sum()),
                "checks_total": len(dq), "sources_changed": [k for k, v in manifest.items()
                                                             if v.get("changed_since_last_fetch")]}
    finally:
        con.execute("""CREATE TABLE IF NOT EXISTS audit.pipeline_runs
                       (run_id VARCHAR, started_at TIMESTAMP, status VARCHAR, duration_s DOUBLE)""")
        con.execute("INSERT INTO audit.pipeline_runs VALUES (?, ?, ?, ?)",
                    [run_id, started, status, round(time.perf_counter() - t0, 2)])
        con.close()
        log.info("run %s: %s in %.1fs", run_id, status, time.perf_counter() - t0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Climate & emissions pipeline")
    p.add_argument("--refresh", action="store_true", help="ignore the download cache")
    p.add_argument("--warehouse", default=None)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    try:
        summary = run(args.warehouse, refresh=args.refresh)
    except (quality.DataQualityError, ingest.IngestError) as exc:
        log.error(str(exc))
        return 1
    log.info("summary: %s", summary)
    return 0
