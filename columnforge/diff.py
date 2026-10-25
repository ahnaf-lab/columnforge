"""Compute a typed diff between two schema versions.

The diff is a list of operations describing how to turn the old schema
into the new one: columns that were added, dropped, renamed (same
data type, different name), or retyped (same name, different data
type). A column that is both renamed and retyped is reported as a
drop of the old column plus an add of the new one, since there is no
reliable signal to distinguish that case from an unrelated
drop-and-add.

Matching is deterministic: common columns are compared in sorted name
order, and rename candidates are paired by sorted name order among the
columns that only exist on one side, matched on identical dtype.
"""

from dataclasses import dataclass
from typing import List, Union

from .schema import Column, Schema, ColumnSpec
from typing import Iterable


@dataclass(frozen=True)
class AddColumn:
    """A column present in the new schema but not the old one."""

    column: Column


@dataclass(frozen=True)
class DropColumn:
    """A column present in the old schema but not the new one."""

    column: Column


@dataclass(frozen=True)
class RenameColumn:
    """A column whose name changed but whose data type did not."""

    old: Column
    new: Column


@dataclass(frozen=True)
class RetypeColumn:
    """A column whose data type changed but whose name did not."""

    old: Column
    new: Column


DiffOp = Union[AddColumn, DropColumn, RenameColumn, RetypeColumn]


def diff_schemas(
    old: Union[Schema, Iterable[ColumnSpec]],
    new: Union[Schema, Iterable[ColumnSpec]],
) -> List[DiffOp]:
    """Compute the ordered list of operations turning `old` into `new`."""

    old_schema = old if isinstance(old, Schema) else Schema(old)
    new_schema = new if isinstance(new, Schema) else Schema(new)

    old_names = set(old_schema.names)
    new_names = set(new_schema.names)

    ops: List[DiffOp] = []

    for name in sorted(old_names & new_names):
        old_col = old_schema[name]
        new_col = new_schema[name]
        if old_col.dtype != new_col.dtype:
            ops.append(RetypeColumn(old=old_col, new=new_col))

    removed_only = sorted(old_names - new_names)
    added_only = sorted(new_names - old_names)

    renamed_removed = set()
    renamed_added = set()
    for removed_name in removed_only:
        removed_col = old_schema[removed_name]
        for added_name in added_only:
            if added_name in renamed_added:
                continue
            added_col = new_schema[added_name]
            if removed_col.dtype == added_col.dtype:
                ops.append(RenameColumn(old=removed_col, new=added_col))
                renamed_removed.add(removed_name)
                renamed_added.add(added_name)
                break

    for name in removed_only:
        if name not in renamed_removed:
            ops.append(DropColumn(column=old_schema[name]))

    for name in added_only:
        if name not in renamed_added:
            ops.append(AddColumn(column=new_schema[name]))

    return ops
