"""Command-line interface: `scigantic-who search|data|query|info`."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from .catalog import indicators
from .connection import manifest, query as run_query, resolve_source
from .data import data


def _cmd_search(args: argparse.Namespace) -> int:
    df = indicators(args.text, include_empty=args.include_empty, source=args.source)
    print(df.to_csv(sep="\t", index=False), end="")
    return 0


def _cmd_data(args: argparse.Namespace) -> int:
    dims = dict(kv.split("=", 1) for kv in args.dim) if args.dim else None
    years: tuple[int, int] | None = None
    if args.years:
        a, _, b = args.years.partition("-")
        years = (int(a), int(b or a))
    df = data(
        args.code,
        countries=args.country or None,
        years=years,
        spatial_type=None if args.all_levels else "COUNTRY",
        dims=dims,
        decode=args.decode,
        source=args.source,
    )
    print(df.to_csv(sep="\t", index=False), end="")
    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    print(run_query(args.sql, source=args.source).to_csv(sep="\t", index=False), end="")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    src = resolve_source(args.source)
    m = manifest(src)
    g = m.get("gho", {})
    print(f"source      {src}")
    print(f"mirrored    {m.get('mirroredAt')}")
    print(f"indicators  {g.get('indicators')} ({g.get('indicatorsWithData')} with data)")
    print(f"observations {g.get('observations'):,}" if g.get("observations") else "observations ?")
    print(f"dimensions  {g.get('dimensions')} / {g.get('dimensionValues')} values")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scigantic-who")
    parser.add_argument("--source", default=None, help="mirror directory or s3:// prefix (default: auto)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search", help="find indicators by name or code substring")
    p.add_argument("text")
    p.add_argument("--include-empty", action="store_true", help="also list indicators with no data")
    p.set_defaults(func=_cmd_search)

    p = sub.add_parser("data", help="observations for one indicator, tab-separated")
    p.add_argument("code")
    p.add_argument("--country", action="append", help="ISO3, repeatable")
    p.add_argument("--years", help="YYYY or YYYY-YYYY")
    p.add_argument("--dim", action="append", help="pin a dimension, e.g. SEX=SEX_BTSX (repeatable)")
    p.add_argument("--all-levels", action="store_true", help="keep regions/income groups/world too")
    p.add_argument("--decode", action="store_true", help="add *_name label columns")
    p.set_defaults(func=_cmd_data)

    p = sub.add_parser("query", help="run SQL (views: indicators, dimensions, dimension_values, observations)")
    p.add_argument("sql")
    p.set_defaults(func=_cmd_query)

    p = sub.add_parser("info", help="which mirror is in use and when it was pulled")
    p.set_defaults(func=_cmd_info)

    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
