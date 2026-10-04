"""scigantic-who: every WHO Global Health Observatory indicator, queryable in one place.

    import scigantic_who as who

    who.indicators("life expectancy")                    # find a code
    who.data("WHOSIS_000001", countries=["JPN", "NGA"],  # read it from the mirror
             dims={"SEX": who.BOTH_SEXES}, decode=True)
    who.live.fetch("WHOSIS_000001", odata_filter="SpatialDim eq 'JPN'")  # or from WHO right now
    who.query("SELECT ... FROM observations")            # or raw SQL over everything
"""

from . import live
from ._constants import ALL_AGES, ALL_CAUSES, BOTH_SEXES
from .catalog import countries, dimension_values, dimensions, indicators
from .connection import connect, manifest, query, resolve_source
from .data import data, decode

__version__ = "0.1.0"

__all__ = [
    "ALL_AGES",
    "ALL_CAUSES",
    "BOTH_SEXES",
    "connect",
    "countries",
    "data",
    "decode",
    "dimension_values",
    "dimensions",
    "indicators",
    "live",
    "manifest",
    "query",
    "resolve_source",
]
