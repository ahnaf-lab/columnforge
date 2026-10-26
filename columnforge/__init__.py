"""columnforge: deterministic, reversible transforms between tabular schemas."""

from .schema import Column, Schema
from .diff import (
    AddColumn,
    DiffOp,
    DropColumn,
    RenameColumn,
    RetypeColumn,
    diff_schemas,
)
from .codegen import (
    TransformPair,
    build_transform,
    invert_op,
    invert_ops,
    render_source,
)
from .roundtrip import (
    RoundTripError,
    RoundTripReport,
    assert_round_trip,
    generate_table,
)
from .report import (
    ColumnPairing,
    RowDiff,
    SampleRowReport,
    build_pairings,
    build_report,
    preview,
    render_report,
)
from .cli import main as cli_main

__all__ = [
    "Column",
    "Schema",
    "AddColumn",
    "DropColumn",
    "RenameColumn",
    "RetypeColumn",
    "DiffOp",
    "diff_schemas",
    "TransformPair",
    "build_transform",
    "invert_op",
    "invert_ops",
    "render_source",
    "RoundTripError",
    "RoundTripReport",
    "assert_round_trip",
    "generate_table",
    "ColumnPairing",
    "RowDiff",
    "SampleRowReport",
    "build_pairings",
    "build_report",
    "preview",
    "render_report",
    "cli_main",
]

__version__ = "0.5.0"
