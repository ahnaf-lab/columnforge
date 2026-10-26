"""Render a side-by-side before/after terminal preview of sample rows.

Given an old/new schema pair and a table of sample rows matching the old
schema, this module runs each row through the forward transform (see
`codegen.build_transform`) and renders a plain-text report: one column per
old/new column correspondence -- matched the same way `diff_schemas` already
reasons about columns (added, dropped, renamed, retyped, or unchanged) --
with a "before" and an "after" line per sample row, and any cell whose value
actually changed marked so it stands out even when ANSI color is disabled.

Column width and alignment are always computed from the plain (uncolored)
text, and color is layered on top of an already-padded cell, so turning
color on or off never shifts the table layout.
"""

import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Union

from .codegen import Row, build_transform
from .diff import AddColumn, DiffOp, DropColumn, RenameColumn, diff_schemas
from .schema import ColumnSpec, Schema

_MISSING = "—"  # em dash, shown for the side a column doesn't exist on

_ANSI_RESET = "\033[0m"
_ANSI_BY_KIND = {
    "changed": "\033[1;33m",  # bold yellow: value changed under a shared name
    "added": "\033[1;32m",  # bold green: column only exists after
    "dropped": "\033[1;31m",  # bold red: column only existed before
}


@dataclass(frozen=True)
class ColumnPairing:
    """One display column: the old-side name and/or new-side name it covers."""

    old_name: Optional[str]
    new_name: Optional[str]
    kind: str  # "same", "renamed", "retyped", "added", or "dropped"

    @property
    def label(self) -> str:
        if self.kind == "added":
            return f"+{self.new_name}"
        if self.kind == "dropped":
            return f"-{self.old_name}"
        if self.kind == "renamed":
            return f"{self.old_name}→{self.new_name}"
        return self.old_name


def build_pairings(
    old_schema: Schema, new_schema: Schema, ops: Sequence[DiffOp]
) -> List[ColumnPairing]:
    """Pair up old/new columns in display order from a diff's ops.

    Columns keep the old schema's order, with rename/retype targets mapped
    to their new name and dropped columns kept in place; added columns are
    appended at the end in new-schema order, since they have no old-side
    position to inherit.
    """

    renamed = {op.old.name: op.new.name for op in ops if isinstance(op, RenameColumn)}
    dropped = {op.column.name for op in ops if isinstance(op, DropColumn)}
    added_names = [op.column.name for op in ops if isinstance(op, AddColumn)]

    pairings: List[ColumnPairing] = []
    for col in old_schema:
        name = col.name
        if name in dropped:
            pairings.append(ColumnPairing(old_name=name, new_name=None, kind="dropped"))
        elif name in renamed:
            pairings.append(
                ColumnPairing(old_name=name, new_name=renamed[name], kind="renamed")
            )
        else:
            new_col = new_schema[name]
            kind = "retyped" if new_col.dtype != col.dtype else "same"
            pairings.append(ColumnPairing(old_name=name, new_name=name, kind=kind))

    for name in added_names:
        pairings.append(ColumnPairing(old_name=None, new_name=name, kind="added"))

    return pairings


def _format_cell(value) -> str:
    if value is None:
        return _MISSING
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


@dataclass(frozen=True)
class RowDiff:
    """One sample row's before/after cell text, aligned to a pairing list."""

    before: List[str]
    after: List[str]
    changed: List[bool]


def _diff_row(pairings: Sequence[ColumnPairing], old_row: Row, new_row: Row) -> RowDiff:
    before: List[str] = []
    after: List[str] = []
    changed: List[bool] = []

    for pairing in pairings:
        if pairing.old_name is not None:
            old_value = old_row.get(pairing.old_name)
            before.append(_format_cell(old_value))
        else:
            old_value = None
            before.append(_MISSING)

        if pairing.new_name is not None:
            new_value = new_row.get(pairing.new_name)
            after.append(_format_cell(new_value))
        else:
            new_value = None
            after.append(_MISSING)

        is_added_or_dropped = pairing.kind in ("added", "dropped")
        changed.append(is_added_or_dropped or old_value != new_value)

    return RowDiff(before=before, after=after, changed=changed)


@dataclass(frozen=True)
class SampleRowReport:
    """A diff's ops, display column pairings, and per-row before/after cells."""

    ops: List[DiffOp]
    pairings: List[ColumnPairing]
    rows: List[RowDiff]


SchemaLike = Union[Schema, Sequence[ColumnSpec]]


def build_report(old: SchemaLike, new: SchemaLike, rows: Sequence[Row]) -> SampleRowReport:
    """Build a `SampleRowReport` from an old/new schema pair and sample rows.

    `rows` must be dicts matching `old`'s columns; each is run through the
    diff's forward transform to produce its "after" counterpart.
    """

    old_schema = old if isinstance(old, Schema) else Schema(old)
    new_schema = new if isinstance(new, Schema) else Schema(new)

    ops = diff_schemas(old_schema, new_schema)
    pair = build_transform(ops)
    pairings = build_pairings(old_schema, new_schema, ops)

    row_diffs = [_diff_row(pairings, row, pair.forward(row)) for row in rows]

    return SampleRowReport(ops=ops, pairings=pairings, rows=row_diffs)


def _should_use_color(color: Optional[bool]) -> bool:
    if color is not None:
        return color
    if os.environ.get("NO_COLOR") is not None:
        return False
    return sys.stdout.isatty()


def _paint(padded_text: str, kind: str, use_color: bool) -> str:
    if not use_color:
        return padded_text
    code = _ANSI_BY_KIND.get(kind)
    if code is None:
        return padded_text
    return f"{code}{padded_text}{_ANSI_RESET}"


def render_report(report: SampleRowReport, *, color: Optional[bool] = None) -> str:
    """Render a `SampleRowReport` as a side-by-side before/after text table.

    `color` forces ANSI highlighting on or off; left as `None`, it is used
    only when stdout is a terminal and the `NO_COLOR` environment variable
    is unset. Changed cells under a shared column name are highlighted
    yellow; a column's added/dropped side is always highlighted (green or
    red) since there is nothing on the other side to compare against.
    """

    use_color = _should_use_color(color)
    pairings = report.pairings

    widths = [len(pairing.label) for pairing in pairings]
    for row_diff in report.rows:
        for i in range(len(pairings)):
            widths[i] = max(widths[i], len(row_diff.before[i]), len(row_diff.after[i]))

    label_gutter = len("before  ")
    lines = [
        " " * label_gutter
        + "  ".join(pairing.label.ljust(widths[i]) for i, pairing in enumerate(pairings)),
        " " * label_gutter + "  ".join("-" * w for w in widths),
    ]

    for row_diff in report.rows:
        before_cells = []
        after_cells = []
        for i, pairing in enumerate(pairings):
            before_text = row_diff.before[i].ljust(widths[i])
            after_text = row_diff.after[i].ljust(widths[i])
            if row_diff.changed[i]:
                kind = pairing.kind if pairing.kind in ("added", "dropped") else "changed"
                before_text = _paint(before_text, kind, use_color)
                after_text = _paint(after_text, kind, use_color)
            before_cells.append(before_text)
            after_cells.append(after_text)
        lines.append("before  " + "  ".join(before_cells))
        lines.append("after   " + "  ".join(after_cells))
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def preview(old: SchemaLike, new: SchemaLike, rows: Sequence[Row], *, color: Optional[bool] = None) -> str:
    """Build and render the before/after sample-row report in one call."""

    return render_report(build_report(old, new, rows), color=color)
