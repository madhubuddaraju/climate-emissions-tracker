"""
Ingest step: download each source, validate it, and record a manifest entry.

Downloads are cached (default 12 h) so repeated local runs don't hit the
sources, and every file's SHA-256 is recorded so a run can tell whether the
upstream data actually changed since the last refresh.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from .config import RAW_DIR, SOURCES, Source

log = logging.getLogger(__name__)

USER_AGENT = "climate-emissions-tracker/1.0 (+https://github.com/madhubuddaraju/climate-emissions-tracker)"


class IngestError(RuntimeError):
    pass


def _download(source: Source, retries: int = 3, timeout: int = 60) -> bytes:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(source.url, timeout=timeout, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            last_exc = exc
            wait = 2 ** attempt
            log.warning("download %s failed (attempt %d/%d): %s - retrying in %ds",
                        source.name, attempt, retries, exc, wait)
            time.sleep(wait)
    raise IngestError(f"could not download {source.name} from {source.url}: {last_exc}")


def _validate(source: Source, content: bytes) -> int:
    text = content.decode("utf-8", errors="replace")
    rows = text.count("\n")
    if rows < source.min_rows:
        raise IngestError(f"{source.name}: only {rows} rows, expected at least {source.min_rows} (truncated?)")
    if text.lstrip().startswith("<"):
        raise IngestError(f"{source.name}: got HTML instead of CSV")
    return rows


def ingest(raw_dir: Path = RAW_DIR, max_age_hours: float = 12, force: bool = False) -> dict:
    """Fetch all sources into raw_dir. Returns the manifest."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest = {}

    for source in SOURCES.values():
        path = raw_dir / f"{source.name}.csv"
        prev = previous.get(source.name, {})
        age_h = (time.time() - path.stat().st_mtime) / 3600 if path.exists() else None

        if not force and age_h is not None and age_h < max_age_hours and prev:
            log.info("using cached %-12s (%.1fh old)", source.name, age_h)
            manifest[source.name] = prev
            continue

        content = _download(source)
        rows = _validate(source, content)
        sha = hashlib.sha256(content).hexdigest()
        path.write_bytes(content)
        changed = sha != prev.get("sha256")
        manifest[source.name] = {
            "url": source.url,
            "publisher": source.publisher,
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "bytes": len(content),
            "rows": rows,
            "sha256": sha,
            "changed_since_last_fetch": changed,
        }
        log.info("fetched %-12s %8d rows %6.1f MB %s", source.name, rows, len(content) / 1e6,
                 "(new data)" if changed else "(unchanged)")

    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest
