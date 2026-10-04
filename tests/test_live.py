"""Tests against the real mirror (s3://scigantic-who) and WHO's live API.

Kept small on purpose: the indicators table is ~100 KB, TB_e_inc_num is one of
the smaller indicator files, and the live fetch asks for 5 rows.
"""

from __future__ import annotations

import pytest

import scigantic_who as who

S3 = "s3://scigantic-who"


def test_live_mirror_indicators() -> None:
    df = who.indicators("tuberculosis", source=S3)
    assert "TB_e_inc_num" in set(df["IndicatorCode"])
    assert (df["row_count"] > 0).all()


def test_live_mirror_data_and_decode() -> None:
    df = who.data("TB_e_inc_num", countries=["IND"], years=(2015, 2020), decode=True, source=S3)
    assert not df.empty
    assert set(df["SpatialDim_name"]) == {"India"}
    assert df["TimeDim"].between(2015, 2020).all()
    assert df.attrs["who_remote"] is True


def test_live_mirror_manifest() -> None:
    m = who.manifest(S3)
    assert m["gho"]["indicators"] >= 3000
    assert m["gho"]["observations"] > 5_000_000


def test_live_api_fetch_matches_mirror_shape() -> None:
    try:
        df = who.live.fetch("TB_e_inc_num", odata_filter="SpatialDim eq 'IND'", top=5)
    except OSError as e:  # WHO's API is slow at times; a network failure is not a package bug
        pytest.skip(f"WHO API unreachable: {e}")
    assert list(df.columns) == list(who._constants.OBS_COLUMNS)
    assert len(df) == 5
    assert str(df["TimeDim"].dtype) == "Int64"
    decoded = who.decode(df, source=S3)
    assert set(decoded["SpatialDim_name"]) == {"India"}
