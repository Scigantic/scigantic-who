"""The catalog half: find indicators, list dimensions, decode codes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .connection import query

if TYPE_CHECKING:
    import pandas as pd


def indicators(
    search: str | None = None,
    *,
    include_empty: bool = False,
    include_archived: bool = False,
    source: str | None = None,
) -> "pd.DataFrame":
    """Indicators in the mirror, optionally filtered by a case-insensitive name/code substring.

    By default hides the 612 catalog entries with no data (row_count = 0) and
    the 36 named "Archived, see <replacement>", because a name search that
    returns them is mostly noise. Columns: IndicatorCode, IndicatorName,
    row_count, first_year, last_year, n_spatial_units, archived.
    """
    clauses, params = [], []
    if not include_empty:
        clauses.append("row_count > 0")
    if not include_archived:
        clauses.append("NOT archived")
    if search:
        clauses.append("(IndicatorName ILIKE ? OR IndicatorCode ILIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return query(f"SELECT * FROM indicators {where} ORDER BY row_count DESC, IndicatorCode", source, params)


def dimensions(source: str | None = None) -> "pd.DataFrame":
    """The dimension codes (COUNTRY, REGION, SEX, AGEGROUP, GHECAUSES, ...) with titles."""
    return query("SELECT * FROM dimensions ORDER BY Code", source)


def dimension_values(dimension: str | None = None, source: str | None = None) -> "pd.DataFrame":
    """Every code under one dimension (or all), with Title, ParentDimension, ParentCode, ParentTitle.

    This is the table that turns SpatialDim / Dim1..Dim3 codes into labels. It is
    keyed by (Dimension, Code): the same Code string can exist under several
    dimensions, so never join on Code alone.
    """
    if dimension:
        return query(
            "SELECT * FROM dimension_values WHERE Dimension = ? ORDER BY Code", source, [dimension]
        )
    return query("SELECT * FROM dimension_values ORDER BY Dimension, Code", source)


def countries(source: str | None = None) -> "pd.DataFrame":
    """The COUNTRY dimension: ISO3 code, name, and the WHO region it belongs to."""
    return query(
        "SELECT Code AS iso3, Title AS country, ParentCode AS who_region_code, ParentTitle AS who_region "
        "FROM dimension_values WHERE Dimension = 'COUNTRY' ORDER BY Code",
        source,
    )
