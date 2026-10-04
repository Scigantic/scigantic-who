"""Regression: DuckDB inside a Jupyter kernel without ipywidgets.

DuckDB 1.5.5 detects Jupyter and raises InvalidInputException on any change to
enable_progress_bar when ipywidgets is absent, even `SET enable_progress_bar=false`.
0.1.0 did that unconditionally and every call failed in a Scigantic notebook
(minimal image, no ipywidgets). The connection setup must survive that.

The real condition needs an ipykernel; this test reproduces the raise by
wrapping duckdb.connect so the one SET statement fails the way DuckDB fails it.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

import scigantic_who as who
from scigantic_who import connection


class _JupyterLikeConnection:
    def __init__(self, real: duckdb.DuckDBPyConnection) -> None:
        self._real = real

    def execute(self, sql: str, *a: object, **k: object) -> duckdb.DuckDBPyConnection:
        if "enable_progress_bar" in sql:
            raise duckdb.InvalidInputException(
                "Invalid Input Error: Could not change the progress bar setting because: "
                "'required package 'ipywidgets' is missing, which is needed to render progress bars in Jupyter'"
            )
        return self._real.execute(sql, *a, **k)

    def __getattr__(self, name: str) -> object:
        return getattr(self._real, name)


def test_connect_survives_jupyter_progress_bar_refusal(mirror: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_connect = duckdb.connect
    monkeypatch.setattr(duckdb, "connect", lambda *a, **k: _JupyterLikeConnection(real_connect(*a, **k)))
    source = str(mirror)
    # Drop the shared base connection for this source so connect() has to build a
    # new one through the patched duckdb.connect.
    connection._base_cons.pop(connection.resolve_source(source), None)
    df = who.indicators("life", source=source)
    assert list(df["IndicatorCode"]) == ["WHOSIS_000001"]
