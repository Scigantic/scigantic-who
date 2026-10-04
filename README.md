<h1 align="center">scigantic-who</h1>

<p align="center">
    <a href="https://github.com/Scigantic/scigantic-who/actions/workflows/ci.yml">
        <img alt="CI" src="https://github.com/Scigantic/scigantic-who/actions/workflows/ci.yml/badge.svg" /></a>
    <a href="https://pypi.org/project/scigantic-who/">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/scigantic-who" /></a>
    <a href="https://pypi.org/project/scigantic-who/">
        <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/scigantic-who" /></a>
    <a href="https://github.com/Scigantic/scigantic-who/blob/main/LICENSE">
        <img alt="License" src="https://img.shields.io/github/license/Scigantic/scigantic-who" /></a>
</p>

Query the WHO [Global Health Observatory](https://www.who.int/data/gho) from Python: every indicator, from a public parquet mirror over DuckDB, with WHO's codes decoded. No API key, no download, no local database.

```python
import scigantic_who as who

who.indicators("life expectancy")
df = who.data("WHOSIS_000001", countries=["JPN", "NGA"], dims={"SEX": who.BOTH_SEXES}, decode=True)
```

That runs against `s3://scigantic-who` over DuckDB's httpfs extension. Inside a Scigantic notebook with the archive mounted, the same call reads the mount instead.

## Installation

```console
$ pip install scigantic-who
```

## Why this exists

WHO's GHO OData API serves one indicator per request and has no bulk download. Pulling the observatory means 3,099 requests and about 6 GB of JSON, and the API serves large indicators at roughly 1 MB/s. [ghoclient](https://pypi.org/project/ghoclient/) (1.2.0, May 2026) is the existing Python client and is a good live wrapper: indicator search, country and region lists, one indicator at a time as a DataFrame. It has no bulk path, no decoding of the `Dim1`..`Dim3` codes to labels, and no DuckDB.

This package adds the mirror. `s3://scigantic-who/gho/` holds all 3,099 indicators (9.9 million observations) as parquet, rebuilt monthly, plus the lookup tables that turn every code into a label. One SQL statement over `observations` replaces thousands of API calls, and `data()` makes the pins a GHO query needs explicit. The live API is still here, in `who.live`, returning the same 25 columns so everything else works on a fresh pull too.

## The shape of a GHO indicator, and the three mistakes this package prevents

A GHO indicator file holds every disaggregation and every spatial level at once: both sexes plus male plus female, every age group plus all ages, countries plus WHO regions plus income groups plus the world. Three things follow.

**Pin the spatial level.** `data()` keeps `SpatialDimType = 'COUNTRY'` by default; pass `spatial_type=None` to see regions and the world too.

**Pin the disaggregations by type, not by slot.** `Dim1` is a sex code for one indicator and an age group for another. `dims={"SEX": "SEX_BTSX"}` matches whichever of `Dim1`..`Dim3` carries `SEX` for this indicator.

```python
who.data("GHE_YLLNUM", countries="BRA", years=2021,
         dims={"SEX": who.BOTH_SEXES, "AGEGROUP": who.ALL_AGES}, decode=True)
```

**Decode on (dimension, code), never on code alone.** The same code string can exist under different dimensions. `decode=True` and `who.decode(df)` join `dimension_values` on the pair.

Two more facts worth knowing. `Value` is the published string (`48.1 [45.4-50.8]`, or a category); `NumericValue`, `Low` and `High` are the numbers. And 612 of the 3,099 catalog entries have no data behind them; `indicators()` hides them unless you ask.

## What is in the mirror

| path | what |
|---|---|
| `gho/indicators.parquet` | code, name, `row_count`, first and last year, number of spatial units, `archived` |
| `gho/dimensions.parquet` | the 202 dimension codes |
| `gho/dimension_values.parquet` | 20,860 rows: every code in every dimension, with `Title`, `ParentCode`, `ParentTitle` |
| `gho/observations.parquet` | 9,944,921 rows, every indicator, ordered by `IndicatorCode` |
| `gho/data/<IndicatorCode>.parquet` | the same rows, one file per indicator |
| `_MANIFEST.json` | when the mirror was pulled and the row counts; `who.manifest()` |
| `_MIRROR.txt` | WHO's terms and the attribution they require |

## Raw SQL

```python
con = who.connect()   # views: indicators, dimensions, dimension_values, observations
con.sql("""
  select o.SpatialDim, c.Title, o.TimeDim, o.NumericValue
  from observations o
  join dimension_values c on c.Dimension = 'COUNTRY' and c.Code = o.SpatialDim
  where o.IndicatorCode = 'MDG_0000000001' and o.Dim1 = 'SEX_BTSX' and o.TimeDim = 2022
  order by o.NumericValue desc limit 10
""").show()
```

`who.query(sql)` does the same and returns a DataFrame. `observations.parquet` is ordered by `IndicatorCode`, so a `WHERE IndicatorCode = ...` reads a few row groups, not the file.

## Live API

```python
fresh = who.live.fetch("WHOSIS_000001", odata_filter="SpatialDim eq 'JPN' and TimeDim ge 2015")
who.decode(fresh)
```

`who.live.indicators()` lists the catalog as WHO publishes it today, for spotting codes added since the last mirror run.

## Where it reads from

In order: an explicit `source=` (a directory or an `s3://` prefix), the `SCIGANTIC_WHO_PATH` environment variable, a Scigantic notebook mount (`$SCIGANTIC_MOUNT_PATH`, `/mnt/archive`, `/home/jovyan/archive`), then `s3://scigantic-who`.

## Command line

```console
$ scigantic-who search "under-five"
$ scigantic-who data MDG_0000000001 --country NGA --years 2010-2022 --dim SEX=SEX_BTSX --decode
$ scigantic-who query "select count(*) from observations"
$ scigantic-who info
```

## Data terms

The data is WHO's. WHO's [terms](https://www.who.int/about/policies/publishing/data-policy/terms-and-conditions) grant a royalty-free right to use, reproduce and distribute the datasets for public health purposes, require attribution in the form `WHO, Global Health Observatory data, <year>, accessed <date>` with acknowledgement of the reporting countries, and bar use in connection with the promotion of a commercial enterprise. The mirror changes storage format only; `_MIRROR.txt` carries the full notice. This package's own code is MIT-0.
