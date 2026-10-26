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
]

__version__ = "0.3.0"
