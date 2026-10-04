"""A two-indicator mirror on disk, in the exact layout who_mirror.py produces.

Every test in this suite that does not say `live` in its name runs against this
fixture, so the package's own logic (resolution, pins, decoding, the CLI) is
tested without the network. The live tests hit s3://scigantic-who and WHO's API.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

OBS_SCHEMA = pa.schema(
    [
        ("Id", pa.int64()),
        ("IndicatorCode", pa.string()),
        ("SpatialDimType", pa.string()),
        ("SpatialDim", pa.string()),
        ("ParentLocationCode", pa.string()),
        ("ParentLocation", pa.string()),
        ("TimeDimType", pa.string()),
        ("TimeDim", pa.int64()),
        ("TimeDimensionValue", pa.string()),
        ("TimeDimensionBegin", pa.string()),
        ("TimeDimensionEnd", pa.string()),
        ("Dim1Type", pa.string()),
        ("Dim1", pa.string()),
        ("Dim2Type", pa.string()),
        ("Dim2", pa.string()),
        ("Dim3Type", pa.string()),
        ("Dim3", pa.string()),
        ("DataSourceDimType", pa.string()),
        ("DataSourceDim", pa.string()),
        ("Value", pa.string()),
        ("NumericValue", pa.float64()),
        ("Low", pa.float64()),
        ("High", pa.float64()),
        ("Comments", pa.string()),
        ("Date", pa.string()),
    ]
)


def _obs(code: str, sdt: str, sd: str, year: int, dim1t: str, dim1: str, value: float, i: int) -> dict[str, object]:
    return {
        "Id": i,
        "IndicatorCode": code,
        "SpatialDimType": sdt,
        "SpatialDim": sd,
        "ParentLocationCode": "AFR" if sd == "NGA" else None,
        "ParentLocation": "Africa" if sd == "NGA" else None,
        "TimeDimType": "YEAR",
        "TimeDim": year,
        "TimeDimensionValue": str(year),
        "TimeDimensionBegin": f"{year}-01-01T00:00:00+01:00",
        "TimeDimensionEnd": f"{year}-12-31T00:00:00+01:00",
        "Dim1Type": dim1t,
        "Dim1": dim1,
        "Dim2Type": None,
        "Dim2": None,
        "Dim3Type": None,
        "Dim3": None,
        "DataSourceDimType": None,
        "DataSourceDim": None,
        "Value": f"{value:.1f} [{value - 1:.1f}-{value + 1:.1f}]",
        "NumericValue": value,
        "Low": value - 1,
        "High": value + 1,
        "Comments": None,
        "Date": "2026-10-01T16:11:13.08+02:00",
    }


@pytest.fixture(scope="session")
def mirror(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("who")
    gho = root / "gho"
    (gho / "data").mkdir(parents=True)

    rows: list[dict[str, object]] = []
    i = 0
    # WHOSIS_000001: two countries x two years x three sexes, plus one region row
    for sd in ("JPN", "NGA"):
        for year in (2019, 2020):
            for sex, v in (("SEX_BTSX", 70.0), ("SEX_MLE", 68.0), ("SEX_FMLE", 72.0)):
                i += 1
                rows.append(_obs("WHOSIS_000001", "COUNTRY", sd, year, "SEX", sex, v + (year - 2019), i))
    i += 1
    rows.append(_obs("WHOSIS_000001", "REGION", "AFR", 2020, "SEX", "SEX_BTSX", 64.0, i))
    t1 = pa.Table.from_pylist(rows, schema=OBS_SCHEMA)
    pq.write_table(t1, gho / "data" / "WHOSIS_000001.parquet")

    # A second, tiny indicator with an AGEGROUP disaggregation in Dim1
    rows2 = [_obs("NCD_BMI_MEAN", "COUNTRY", "JPN", 2020, "AGEGROUP", "AGEGROUP_YEARS18-PLUS", 22.5, 100)]
    t2 = pa.Table.from_pylist(rows2, schema=OBS_SCHEMA)
    pq.write_table(t2, gho / "data" / "NCD_BMI_MEAN.parquet")

    pq.write_table(pa.concat_tables([t1, t2]).sort_by("IndicatorCode"), gho / "observations.parquet")

    pq.write_table(
        pa.table(
            {
                "IndicatorCode": ["WHOSIS_000001", "NCD_BMI_MEAN", "EMPTY_ONE", "OLD_ONE"],
                "IndicatorName": [
                    "Life expectancy at birth (years)",
                    "Mean BMI (kg/m²) (age-standardized estimate)",
                    "An indicator with no data",
                    "Archived, see WHOSIS_000001",
                ],
                "row_count": [13, 1, 0, 0],
                "first_year": [2019, 2020, None, None],
                "last_year": [2020, 2020, None, None],
                "n_spatial_units": [3, 1, 0, 0],
                "archived": [False, False, False, True],
            }
        ),
        gho / "indicators.parquet",
    )
    pq.write_table(
        pa.table({"Code": ["COUNTRY", "REGION", "SEX", "AGEGROUP"], "Title": ["Country", "Region", "Sex", "Age Group"]}),
        gho / "dimensions.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "Dimension": ["COUNTRY", "COUNTRY", "REGION", "SEX", "SEX", "SEX", "AGEGROUP"],
                "Code": ["JPN", "NGA", "AFR", "SEX_BTSX", "SEX_MLE", "SEX_FMLE", "AGEGROUP_YEARS18-PLUS"],
                "Title": ["Japan", "Nigeria", "Africa", "Both sexes", "Male", "Female", "18+  years"],
                "ParentDimension": ["REGION", "REGION", None, None, None, None, None],
                "ParentCode": ["WPR", "AFR", None, None, None, None, None],
                "ParentTitle": ["Western Pacific", "Africa", None, None, None, None, None],
            }
        ),
        gho / "dimension_values.parquet",
    )
    (root / "_MANIFEST.json").write_text(
        json.dumps(
            {
                "mirroredAt": "2026-10-04T15:00:00+00:00",
                "bucket": "fixture",
                "gho": {"indicators": 4, "indicatorsWithData": 2, "indicatorsEmpty": 2, "dimensions": 4,
                        "dimensionValues": 7, "observations": 14},
            }
        )
    )
    return root
