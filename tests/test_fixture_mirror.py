from __future__ import annotations

from pathlib import Path

import pytest

import scigantic_who as who
from scigantic_who.cli import main


def test_resolve_source_prefers_argument_then_env_then_s3(mirror: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCIGANTIC_WHO_PATH", raising=False)
    monkeypatch.delenv("SCIGANTIC_MOUNT_PATH", raising=False)
    assert who.resolve_source(str(mirror)) == str(mirror)
    monkeypatch.setenv("SCIGANTIC_WHO_PATH", str(mirror))
    assert who.resolve_source() == str(mirror)
    monkeypatch.delenv("SCIGANTIC_WHO_PATH")
    monkeypatch.setenv("SCIGANTIC_MOUNT_PATH", str(mirror))
    assert who.resolve_source() == str(mirror)
    monkeypatch.delenv("SCIGANTIC_MOUNT_PATH")
    assert who.resolve_source() == "s3://scigantic-who"


def test_resolve_source_rejects_a_directory_that_is_not_a_mirror(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        who.resolve_source(str(tmp_path))


def test_indicators_hides_empty_and_archived_by_default(mirror: Path) -> None:
    df = who.indicators(source=str(mirror))
    assert list(df["IndicatorCode"]) == ["WHOSIS_000001", "NCD_BMI_MEAN"]
    full = who.indicators(include_empty=True, include_archived=True, source=str(mirror))
    assert len(full) == 4
    hit = who.indicators("life expect", source=str(mirror))
    assert list(hit["IndicatorCode"]) == ["WHOSIS_000001"]


def test_data_pins_country_level_by_default(mirror: Path) -> None:
    df = who.data("WHOSIS_000001", source=str(mirror))
    assert set(df["SpatialDimType"]) == {"COUNTRY"}
    assert len(df) == 12
    everything = who.data("WHOSIS_000001", spatial_type=None, source=str(mirror))
    assert len(everything) == 13


def test_data_filters_countries_years_and_dims(mirror: Path) -> None:
    df = who.data(
        "WHOSIS_000001",
        countries="NGA",
        years=2020,
        dims={"SEX": who.BOTH_SEXES},
        source=str(mirror),
    )
    assert len(df) == 1
    assert df["NumericValue"].iloc[0] == 71.0
    rng = who.data("WHOSIS_000001", countries=["JPN"], years=(2019, 2020), source=str(mirror))
    assert len(rng) == 6
    lst = who.data("WHOSIS_000001", years=[2019], source=str(mirror))
    assert set(lst["TimeDim"]) == {2019}


def test_dims_pin_matches_whichever_slot_carries_the_type(mirror: Path) -> None:
    df = who.data("NCD_BMI_MEAN", dims={"AGEGROUP": "AGEGROUP_YEARS18-PLUS"}, source=str(mirror))
    assert len(df) == 1
    none = who.data("NCD_BMI_MEAN", dims={"SEX": who.BOTH_SEXES}, source=str(mirror))
    assert none.empty


def test_data_decode_adds_label_columns(mirror: Path) -> None:
    df = who.data("WHOSIS_000001", countries="JPN", years=2020, decode=True, source=str(mirror))
    assert set(df["SpatialDim_name"]) == {"Japan"}
    assert set(df["Dim1_name"]) == {"Both sexes", "Male", "Female"}
    assert df["Dim2_name"].isna().all()


def test_decode_works_on_any_observations_frame(mirror: Path) -> None:
    raw = who.data("WHOSIS_000001", countries="NGA", years=2019, source=str(mirror))
    out = who.decode(raw, source=str(mirror))
    assert "SpatialDim_name" in out.columns
    assert set(out["SpatialDim_name"]) == {"Nigeria"}
    assert len(out) == len(raw)


def test_data_unknown_or_empty_indicator_raises(mirror: Path) -> None:
    with pytest.raises(KeyError, match="not an indicator"):
        who.data("NOPE", source=str(mirror))
    with pytest.raises(KeyError, match="publishes no data"):
        who.data("EMPTY_ONE", source=str(mirror))
    with pytest.raises(ValueError):
        who.data("DROP TABLE x", source=str(mirror))
    with pytest.raises(ValueError):
        who.data("WHOSIS_000001", dims={"sex; drop": "x"}, source=str(mirror))


def test_catalog_helpers(mirror: Path) -> None:
    assert list(who.dimensions(source=str(mirror))["Code"]) == ["AGEGROUP", "COUNTRY", "REGION", "SEX"]
    sex = who.dimension_values("SEX", source=str(mirror))
    assert len(sex) == 3
    c = who.countries(source=str(mirror))
    assert list(c.columns) == ["iso3", "country", "who_region_code", "who_region"]
    assert c.set_index("iso3").loc["NGA", "who_region"] == "Africa"


def test_query_and_connect_share_views(mirror: Path) -> None:
    df = who.query("SELECT count(*) AS n FROM observations", source=str(mirror))
    assert df["n"].iloc[0] == 14
    assert df.attrs["who_source"] == str(mirror)
    con = who.connect(str(mirror))
    try:
        assert con.execute("SELECT count(*) FROM dimension_values").fetchone() == (7,)
    finally:
        con.close()


def test_manifest(mirror: Path) -> None:
    m = who.manifest(str(mirror))
    assert m["gho"]["observations"] == 14


def test_cli(mirror: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--source", str(mirror), "search", "bmi"]) == 0
    out = capsys.readouterr().out
    assert "NCD_BMI_MEAN" in out and "WHOSIS" not in out

    assert main(["--source", str(mirror), "data", "WHOSIS_000001", "--country", "JPN", "--years", "2020",
                 "--dim", "SEX=SEX_FMLE", "--decode"]) == 0
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert len(lines) == 2 and "Female" in lines[1]

    assert main(["--source", str(mirror), "query", "SELECT 1 AS one"]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "1"

    assert main(["--source", str(mirror), "info"]) == 0
    assert "observations 14" in capsys.readouterr().out
