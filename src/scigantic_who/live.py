"""The live half: WHO's GHO OData API, returned in the mirror's exact shape.

The mirror is rebuilt monthly. When a caller needs an indicator as WHO publishes
it today, fetch() pulls it from the API and returns a DataFrame with the same 25
columns and types as the mirror's parquet, so the rest of the package (decode(),
the same pins) works on it unchanged. One request per indicator; the API has no
bulk endpoint and, as measured while building the mirror, serves large
indicators at roughly 1 MB/s, so fetching more than a handful this way is what
the mirror is for.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

import pandas as pd

from ._constants import FLOAT_COLUMNS, GHO_API, INT_COLUMNS, OBS_COLUMNS, USER_AGENT


def _get(url: str, timeout: int = 600) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=list(OBS_COLUMNS))
    for c in INT_COLUMNS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in FLOAT_COLUMNS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df


def fetch(code: str, *, odata_filter: str | None = None, top: int | None = None) -> pd.DataFrame:
    """One indicator straight from the API, as WHO publishes it right now.

    odata_filter is passed through as the OData $filter, e.g.
    "SpatialDim eq 'JPN' and TimeDim ge 2015". Returns the mirror's column set.
    """
    params: dict[str, str] = {}
    if odata_filter:
        params["$filter"] = odata_filter
    if top is not None:
        params["$top"] = str(top)
    url = f"{GHO_API}/{urllib.parse.quote(code, safe='_-.')}"
    if params:
        url += "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    payload = _get(url)
    rows = payload.get("value", [])
    df = _frame(rows)
    df.attrs["who_source"] = url
    df.attrs["who_remote"] = True
    return df


def indicators() -> pd.DataFrame:
    """The live indicator catalog (IndicatorCode, IndicatorName, Language), no row counts.

    The mirror's indicators table is the better search surface because it knows
    which indicators actually have data; this is for spotting codes WHO added
    since the last mirror run.
    """
    rows = _get(f"{GHO_API}/Indicator").get("value", [])
    return pd.DataFrame(rows, columns=["IndicatorCode", "IndicatorName", "Language"])
