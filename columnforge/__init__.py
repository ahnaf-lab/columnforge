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

__all__ = [
    "Column",
    "Schema",
    "AddColumn",
    "DropColumn",
    "RenameColumn",
    "RetypeColumn",
    "DiffOp",
    "diff_schemas",
]

__version__ = "0.1.0"
