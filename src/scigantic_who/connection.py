"""DuckDB connection helpers for the mirror.

Queries run against the public S3 mirror over httpfs (no download, no key), or
against a local copy when one is present: a Scigantic notebook has the archive
FUSE-mounted at /mnt/archive, and `who_mirror.py --work` builds the same tree
locally. Resolution order, first hit wins:

1. an explicit `source=` argument (a directory or an `s3://` prefix),
2. the SCIGANTIC_WHO_PATH environment variable,
3. `$SCIGANTIC_MOUNT_PATH/gho/indicators.parquet`, then /mnt/archive and
   /home/jovyan/archive (Scigantic notebook mounts),
4. s3://scigantic-who.

connect() hands out a cursor() on a lazily-created, shared base connection per
source rather than a brand new duckdb.connect() per call: setup (INSTALL/LOAD
httpfs, the anonymous S3 secret, registering the four views) happens once per
(source, process), the pattern scigantic-bindingdb measured as a real cost when a
caller loops a query-returning function.

Views registered on every connection:

  indicators        gho/indicators.parquet        catalog with row_count, year span, archived flag
  dimensions        gho/dimensions.parquet        the 202 dimension codes
  dimension_values  gho/dimension_values.parquet  every code in every dimension, with label and parent
  observations      gho/observations.parquet      every row of every indicator, ordered by IndicatorCode

Per-indicator files (gho/data/<IndicatorCode>.parquet) are read directly by
data.data(); they are not views because there are 2,487 of them.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ._constants import DEFAULT_MOUNTS, HTTPS_PREFIX, MOUNT_ENV, REGION, S3_PREFIX, SOURCE_ENV, USER_AGENT

if TYPE_CHECKING:
    import duckdb
    import pandas as pd


def resolve_source(source: str | None = None) -> str:
    """Return the mirror root this process will read: a local directory or an s3:// prefix."""
    if source:
        return _normalise(source)
    env = os.environ.get(SOURCE_ENV)
    if env:
        return _normalise(env)
    candidates = []
    mount = os.environ.get(MOUNT_ENV)
    if mount:
        candidates.append(mount)
    candidates.extend(DEFAULT_MOUNTS)
    for c in candidates:
        if (Path(c) / "gho" / "indicators.parquet").is_file():
            return str(Path(c))
    return S3_PREFIX


def _normalise(source: str) -> str:
    if source.startswith("s3://"):
        return source.rstrip("/")
    p = Path(source).expanduser()
    if not (p / "gho" / "indicators.parquet").is_file():
        raise FileNotFoundError(
            f"{p} does not look like a scigantic-who mirror (no gho/indicators.parquet under it)"
        )
    return str(p)


def is_remote(source: str) -> bool:
    return source.startswith("s3://")


def path_for(source: str, relative: str) -> str:
    """Join a mirror-relative path onto the source, for read_parquet() or open()."""
    return f"{source}/{relative}" if is_remote(source) else str(Path(source) / relative)


_base_cons: dict[str, "duckdb.DuckDBPyConnection"] = {}
_base_cons_lock = threading.Lock()


def _get_base_connection(source: str) -> "duckdb.DuckDBPyConnection":
    con = _base_cons.get(source)
    if con is not None:
        return con
    with _base_cons_lock:
        con = _base_cons.get(source)
        if con is None:  # re-check: another thread may have won the race
            import duckdb

            new_con = duckdb.connect()
            # Inside a Jupyter kernel without ipywidgets, DuckDB (1.5.5) raises
            # InvalidInputException on ANY change to enable_progress_bar, even
            # turning it off ("required package 'ipywidgets' is missing"). Plain
            # Python never hits it, which is how 0.1.0 shipped with it. The
            # setting is cosmetic; skip it rather than fail the connection.
            try:
                new_con.execute("SET enable_progress_bar=false")
            except duckdb.Error:
                pass
            if is_remote(source):
                new_con.execute("INSTALL httpfs")
                new_con.execute("LOAD httpfs")
                new_con.execute(f"SET s3_region='{REGION}'")
                # The mirror is public-read. Without this, DuckDB looks for AWS
                # credentials and fails on a machine that has none configured.
                new_con.execute(
                    "CREATE OR REPLACE SECRET scigantic_who "
                    "(TYPE s3, PROVIDER config, KEY_ID '', SECRET '')"
                )
            for view, rel in (
                ("indicators", "gho/indicators.parquet"),
                ("dimensions", "gho/dimensions.parquet"),
                ("dimension_values", "gho/dimension_values.parquet"),
                ("observations", "gho/observations.parquet"),
            ):
                # CREATE VIEW cannot take a prepared parameter, so the path is
                # quoted as a literal (single quotes doubled).
                literal = path_for(source, rel).replace("'", "''")
                new_con.execute(f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM read_parquet('{literal}')")
            _base_cons[source] = new_con
            con = new_con
    return con


def connect(source: str | None = None) -> "duckdb.DuckDBPyConnection":
    """A DuckDB connection with the mirror's tables registered as views.

    `SELECT * FROM indicators`, `dimension_values`, `dimensions` and
    `observations` all work. Returns an independent cursor() on a shared base
    connection for this source, safe to use and close() on its own.
    """
    return _get_base_connection(resolve_source(source)).cursor()


def query(sql: str, source: str | None = None, params: list[Any] | None = None) -> "pd.DataFrame":
    """Run SQL against the mirror and return a pandas DataFrame.

    For several queries against the same source, call connect() once and reuse
    it instead, to avoid opening and closing a cursor per query.
    """
    resolved = resolve_source(source)
    con = connect(resolved)
    try:
        df = con.execute(sql, params or []).df()
        df.attrs["who_source"] = resolved
        return df
    finally:
        con.close()


def manifest(source: str | None = None) -> dict[str, Any]:
    """The mirror's _MANIFEST.json: when it was pulled and what it holds."""
    resolved = resolve_source(source)
    if is_remote(resolved):
        url = resolved.replace(S3_PREFIX, HTTPS_PREFIX) + "/_MANIFEST.json"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as r:
            data: dict[str, Any] = json.loads(r.read())
            return data
    with open(Path(resolved) / "_MANIFEST.json", encoding="utf-8") as f:
        loaded: dict[str, Any] = json.load(f)
        return loaded
