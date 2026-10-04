# Changelog

## 0.1.1

- Fix: inside a Jupyter kernel without ipywidgets, DuckDB rejects
  `SET enable_progress_bar=false` and every call failed with
  InvalidInputException. The setting is now best-effort. Found on the first
  launch in a Scigantic notebook (the minimal image has no ipywidgets).

## 0.1.0

First release.

- `indicators()`, `dimensions()`, `dimension_values()`, `countries()`: the
  catalog, from the mirror's lookup tables. `indicators()` hides the 612
  codes WHO lists with no data and the 36 archived ones unless asked.
- `data()`: one indicator's observations with explicit pins on spatial level,
  countries, years and disaggregation dimensions (by dimension type, so the
  caller does not need to know which of Dim1..Dim3 WHO used), and `decode=True`
  to attach labels.
- `decode()`: attach labels to any observations frame, including one from the
  live API.
- `live.fetch()`, `live.indicators()`: WHO's OData API, returned in the
  mirror's exact 25-column shape.
- `connect()`, `query()`, `manifest()`: raw DuckDB over the mirror, with
  `indicators`, `dimensions`, `dimension_values` and `observations` views.
- Source resolution: an explicit path or `s3://` prefix, `SCIGANTIC_WHO_PATH`,
  a Scigantic notebook mount, then the public S3 mirror.
- CLI: `scigantic-who search|data|query|info`.
