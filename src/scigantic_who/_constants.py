"""Shared constants: where the mirror lives, where the live API is, and the one schema both share."""

BUCKET = "scigantic-who"
REGION = "us-east-1"
S3_PREFIX = f"s3://{BUCKET}"
HTTPS_PREFIX = f"https://{BUCKET}.s3.amazonaws.com"

# WHO's Global Health Observatory OData API. Public, no key, one indicator per
# request, no bulk download: that last fact is why the mirror exists.
GHO_API = "https://ghoapi.azureedge.net/api"

# Point the package at a local copy of the mirror (a Scigantic notebook mount,
# or a `who_mirror.py --work` build) instead of S3. Resolved in connection.py.
SOURCE_ENV = "SCIGANTIC_WHO_PATH"
MOUNT_ENV = "SCIGANTIC_MOUNT_PATH"
DEFAULT_MOUNTS = ("/mnt/archive", "/home/jovyan/archive")

USER_AGENT = "scigantic-who/0.1.1 (+https://github.com/Scigantic/scigantic-who)"

# The observation schema, identical in the mirror's parquet files and in what
# live.fetch() returns. These are the OData entity's own property names.
OBS_COLUMNS: tuple[str, ...] = (
    "Id",
    "IndicatorCode",
    "SpatialDimType",
    "SpatialDim",
    "ParentLocationCode",
    "ParentLocation",
    "TimeDimType",
    "TimeDim",
    "TimeDimensionValue",
    "TimeDimensionBegin",
    "TimeDimensionEnd",
    "Dim1Type",
    "Dim1",
    "Dim2Type",
    "Dim2",
    "Dim3Type",
    "Dim3",
    "DataSourceDimType",
    "DataSourceDim",
    "Value",
    "NumericValue",
    "Low",
    "High",
    "Comments",
    "Date",
)
INT_COLUMNS = ("Id", "TimeDim")
FLOAT_COLUMNS = ("NumericValue", "Low", "High")

# Well-known codes, so callers do not have to remember WHO's spelling.
BOTH_SEXES = "SEX_BTSX"
# "All ages" is spelled three ways across indicators (measured on the 2026-10
# mirror: AGEGROUP_AGEAll in 268k rows, AGEGROUP_YEARSALL in 56k, AGEGROUP_ALLAges
# rarely). Look up which one your indicator uses in dimension_values; dims={"AGEGROUP":
# ...} accepts any of them, and ALL_AGES_CODES is the full set.
ALL_AGES_CODES = ("AGEGROUP_AGEAll", "AGEGROUP_YEARSALL", "AGEGROUP_ALLAges")
ALL_CAUSES = "GHECAUSES_GHE000"
