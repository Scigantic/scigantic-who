"""The data half: one indicator's observations, filtered and optionally decoded.

A GHO indicator file is not one series. It holds every disaggregation and every
spatial level at once: both sexes plus male plus female, every age group plus all
ages, countries plus WHO regions plus income groups plus the world. data() makes
the pins explicit so a caller cannot sum a country series that silently includes
its region's total.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from ._constants import OBS_COLUMNS
from .connection import connect, is_remote, path_for, resolve_source

if TYPE_CHECKING:
    import pandas as pd

_CODE_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
_DIM_TYPE_RE = re.compile(r"^[A-Z0-9_]+$")


def _check_code(code: str) -> str:
    if not _CODE_RE.match(code):
        raise ValueError(f"{code!r} is not a GHO indicator code")
    return code


def data(
    code: str,
    *,
    countries: str | Iterable[str] | None = None,
    years: int | Iterable[int] | tuple[int, int] | None = None,
    spatial_type: str | None = "COUNTRY",
    dims: Mapping[str, str] | None = None,
    decode: bool = False,
    source: str | None = None,
) -> "pd.DataFrame":
    """Observations for one indicator from the mirror.

    code         the IndicatorCode, e.g. "WHOSIS_000001" (life expectancy at birth).
    countries    ISO3 code or codes to keep (matched against SpatialDim).
    years        one year, an iterable of years, or a (first, last) tuple inclusive.
    spatial_type "COUNTRY" by default, which drops WHO regions, income groups and
                 the world; pass None to keep every spatial level, or "REGION" etc.
    dims         pins on the disaggregation dimensions by dimension TYPE, e.g.
                 {"SEX": "SEX_BTSX", "AGEGROUP": "AGEGROUP_YEARSALL"}. Each pin
                 matches whichever of Dim1..Dim3 carries that type, so you do not
                 need to know which slot WHO put it in for this indicator.
    decode       add *_name columns for SpatialDim and Dim1..Dim3 by joining
                 dimension_values on (dimension type, code).

    Raises KeyError for a code with no file in the mirror (unknown, or one of the
    612 indicators WHO lists with no data).
    """
    _check_code(code)
    resolved = resolve_source(source)
    con = connect(resolved)
    try:
        exists = con.execute(
            "SELECT row_count FROM indicators WHERE IndicatorCode = ?", [code]
        ).fetchone()
        if exists is None:
            raise KeyError(f"{code}: not an indicator in this mirror (try indicators(search=...))")
        if exists[0] == 0:
            raise KeyError(f"{code}: WHO lists this indicator but publishes no data for it")

        clauses: list[str] = []
        params: list[Any] = [path_for(resolved, f"gho/data/{code}.parquet")]
        if spatial_type is not None:
            clauses.append("o.SpatialDimType = ?")
            params.append(spatial_type)
        if countries is not None:
            cs = [countries] if isinstance(countries, str) else list(countries)
            clauses.append(f"o.SpatialDim IN ({', '.join('?' * len(cs))})")
            params.extend(cs)
        if years is not None:
            if isinstance(years, int):
                clauses.append("o.TimeDim = ?")
                params.append(years)
            elif isinstance(years, tuple) and len(years) == 2:
                clauses.append("o.TimeDim BETWEEN ? AND ?")
                params.extend(years)
            else:
                ys = list(years)
                clauses.append(f"o.TimeDim IN ({', '.join('?' * len(ys))})")
                params.extend(ys)
        for dim_type, dim_code in (dims or {}).items():
            if not _DIM_TYPE_RE.match(dim_type):
                raise ValueError(f"{dim_type!r} is not a dimension type code (expected e.g. 'SEX')")
            clauses.append(
                "((o.Dim1Type = ? AND o.Dim1 = ?) OR (o.Dim2Type = ? AND o.Dim2 = ?) "
                "OR (o.Dim3Type = ? AND o.Dim3 = ?))"
            )
            params.extend([dim_type, dim_code] * 3)

        select = "o.*"
        joins = ""
        if decode:
            select += (
                ", sp.Title AS SpatialDim_name, d1.Title AS Dim1_name, "
                "d2.Title AS Dim2_name, d3.Title AS Dim3_name"
            )
            joins = (
                " LEFT JOIN dimension_values sp ON sp.Dimension = o.SpatialDimType AND sp.Code = o.SpatialDim"
                " LEFT JOIN dimension_values d1 ON d1.Dimension = o.Dim1Type AND d1.Code = o.Dim1"
                " LEFT JOIN dimension_values d2 ON d2.Dimension = o.Dim2Type AND d2.Code = o.Dim2"
                " LEFT JOIN dimension_values d3 ON d3.Dimension = o.Dim3Type AND d3.Code = o.Dim3"
            )
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT {select} FROM read_parquet(?) o{joins}{where} "
            "ORDER BY o.SpatialDim, o.TimeDim, o.Dim1, o.Dim2, o.Dim3"
        )
        df = con.execute(sql, params).df()
        df.attrs["who_source"] = resolved
        df.attrs["who_remote"] = is_remote(resolved)
        return df
    finally:
        con.close()


def decode(df: "pd.DataFrame", source: str | None = None) -> "pd.DataFrame":
    """Add *_name columns to any observations frame (e.g. one from live.fetch()).

    Joins dimension_values on (dimension type, code) for SpatialDim and
    Dim1..Dim3. Rows whose code is unknown to the mirror keep a null name.
    """
    missing = [c for c in ("SpatialDimType", "SpatialDim", "Dim1Type", "Dim1") if c not in df.columns]
    if missing:
        raise ValueError(f"not an observations frame, missing {missing}")
    con = connect(source)
    try:
        con.register("obs_to_decode", df)
        cols = ", ".join(f"o.{c}" for c in df.columns if c in OBS_COLUMNS or c not in {
            "SpatialDim_name", "Dim1_name", "Dim2_name", "Dim3_name"})
        out = con.execute(
            f"SELECT {cols}, sp.Title AS SpatialDim_name, d1.Title AS Dim1_name, "
            "d2.Title AS Dim2_name, d3.Title AS Dim3_name FROM obs_to_decode o"
            " LEFT JOIN dimension_values sp ON sp.Dimension = o.SpatialDimType AND sp.Code = o.SpatialDim"
            " LEFT JOIN dimension_values d1 ON d1.Dimension = o.Dim1Type AND d1.Code = o.Dim1"
            " LEFT JOIN dimension_values d2 ON d2.Dimension = o.Dim2Type AND d2.Code = o.Dim2"
            " LEFT JOIN dimension_values d3 ON d3.Dimension = o.Dim3Type AND d3.Code = o.Dim3"
        ).df()
        con.unregister("obs_to_decode")
        return out
    finally:
        con.close()
