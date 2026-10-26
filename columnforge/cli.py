"""Command-line entry point for columnforge.

Each subcommand reads an old/new schema pair from JSON files -- a JSON
array of `[name, dtype]` / `[name, dtype, nullable]` arrays or
`{"name": ..., "dtype": ..., "nullable": ...}` objects, the same shapes
`Schema` already accepts -- and prints one of the library's existing
views on the diff between them: the raw ops, the generated transform
source, a round-trip proof, or a before/after sample-row preview.

No part of a schema or row file is ever passed to `exec`/`eval`; this
module only parses JSON and calls the library's existing pure-Python
functions.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional, Sequence

from .codegen import build_transform
from .diff import AddColumn, DiffOp, DropColumn, RenameColumn, RetypeColumn, diff_schemas
from .report import preview
from .roundtrip import RoundTripError, assert_round_trip
from .schema import Schema


def _load_schema(path: Path) -> Schema:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return Schema(data)


def _load_rows(path: Path) -> List[Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _describe_op(op: DiffOp) -> str:
    if isinstance(op, AddColumn):
        return f"add    {op.column.name} ({op.column.dtype})"
    if isinstance(op, DropColumn):
        return f"drop   {op.column.name} ({op.column.dtype})"
    if isinstance(op, RenameColumn):
        return f"rename {op.old.name} -> {op.new.name}"
    if isinstance(op, RetypeColumn):
        return f"retype {op.old.name} {op.old.dtype} -> {op.new.dtype}"
    raise TypeError(f"unsupported diff op: {op!r}")


def _add_schema_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("old_schema", type=Path, help="path to the old schema JSON file")
    parser.add_argument("new_schema", type=Path, help="path to the new schema JSON file")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="columnforge",
        description="Deterministic, reversible transforms between tabular schema versions.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    diff_parser = subcommands.add_parser("diff", help="list the ops that turn old into new")
    _add_schema_args(diff_parser)

    codegen_parser = subcommands.add_parser(
        "codegen", help="print the generated forward/inverse transform source"
    )
    _add_schema_args(codegen_parser)

    roundtrip_parser = subcommands.add_parser(
        "roundtrip", help="prove the transform reconstructs a seeded sample table"
    )
    _add_schema_args(roundtrip_parser)
    roundtrip_parser.add_argument("--rows", type=int, default=50, help="number of sample rows")
    roundtrip_parser.add_argument("--seed", type=int, default=0, help="random seed")

    preview_parser = subcommands.add_parser(
        "preview", help="render a before/after sample-row report"
    )
    _add_schema_args(preview_parser)
    preview_parser.add_argument("sample_rows", type=Path, help="path to a JSON file of sample rows")
    preview_parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="whether to highlight changed cells with ANSI color",
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "diff":
        old = _load_schema(args.old_schema)
        new = _load_schema(args.new_schema)
        for op in diff_schemas(old, new):
            print(_describe_op(op))
        return 0

    if args.command == "codegen":
        old = _load_schema(args.old_schema)
        new = _load_schema(args.new_schema)
        pair = build_transform(diff_schemas(old, new))
        print(pair.forward_source)
        print()
        print(pair.inverse_source)
        return 0

    if args.command == "roundtrip":
        old = _load_schema(args.old_schema)
        new = _load_schema(args.new_schema)
        try:
            report = assert_round_trip(old, new, n_rows=args.rows, seed=args.seed)
        except RoundTripError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            f"round-trip OK: {report.rows_checked} rows checked, "
            f"seed={report.seed}, {len(report.ops)} ops"
        )
        return 0

    if args.command == "preview":
        old = _load_schema(args.old_schema)
        new = _load_schema(args.new_schema)
        rows = _load_rows(args.sample_rows)
        color = {"auto": None, "always": True, "never": False}[args.color]
        print(preview(old, new, rows, color=color))
        return 0

    parser.error(f"unknown command: {args.command!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
