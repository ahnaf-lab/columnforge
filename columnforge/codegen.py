"""Generate forward and inverse row-transform functions from schema diff ops.

Given the ops produced by `diff_schemas`, this module builds a pair of
plain Python callables: one that maps an old-schema row (a `dict`) to a
new-schema row, and one that maps a new-schema row back to the old
shape. Each kind of diff op has a fixed inverse rule -- add and drop
invert each other, a rename inverts to the reverse rename, and a
retype inverts to a retype back to the original dtype -- so the inverse
pipeline is derived automatically rather than hand-written.

Dropping a column is lossy: the forward transform discards its value,
so the inverse of a drop can only restore the column with a null
placeholder, not the original data.

The callables are built directly as closures, not by compiling and
executing generated text, so no part of a schema (column names,
dtypes) is ever passed to `exec`/`eval`. `render_source` separately
renders the equivalent pure-Python source as a string purely for
display/review; that text is not what actually runs.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .diff import AddColumn, DiffOp, DropColumn, RenameColumn, RetypeColumn

Row = Dict[str, Any]
RowTransform = Callable[[Row], Row]


def _identity(value: Any) -> Any:
    return value


def _to_int(value: Any) -> Any:
    return value if value is None else int(value)


def _to_float(value: Any) -> Any:
    return value if value is None else float(value)


def _to_str(value: Any) -> Any:
    return value if value is None else str(value)


def _to_bool(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "t")
    return bool(value)


# Casters for the dtypes columnforge understands natively. A retype to any
# other dtype name passes the value through unchanged (identity), since
# there is no safe generic conversion for an arbitrary user-defined dtype.
CASTERS: Dict[str, Callable[[Any], Any]] = {
    "int": _to_int,
    "float": _to_float,
    "str": _to_str,
    "bool": _to_bool,
}


def _caster(dtype: str) -> Callable[[Any], Any]:
    return CASTERS.get(dtype, _identity)


def _step_for(op: DiffOp) -> RowTransform:
    if isinstance(op, AddColumn):
        name = op.column.name

        def step(row: Row, _name: str = name) -> Row:
            row[_name] = None
            return row

        return step

    if isinstance(op, DropColumn):
        name = op.column.name

        def step(row: Row, _name: str = name) -> Row:
            row.pop(_name, None)
            return row

        return step

    if isinstance(op, RenameColumn):
        old_name, new_name = op.old.name, op.new.name

        def step(row: Row, _old: str = old_name, _new: str = new_name) -> Row:
            row[_new] = row.pop(_old, None)
            return row

        return step

    if isinstance(op, RetypeColumn):
        name = op.old.name
        cast = _caster(op.new.dtype)

        def step(row: Row, _name: str = name, _cast: Callable[[Any], Any] = cast) -> Row:
            if _name in row:
                row[_name] = _cast(row[_name])
            return row

        return step

    raise TypeError(f"unsupported diff op: {op!r}")


def invert_op(op: DiffOp) -> DiffOp:
    """Return the single op that undoes `op`."""

    if isinstance(op, AddColumn):
        return DropColumn(column=op.column)
    if isinstance(op, DropColumn):
        return AddColumn(column=op.column)
    if isinstance(op, RenameColumn):
        return RenameColumn(old=op.new, new=op.old)
    if isinstance(op, RetypeColumn):
        return RetypeColumn(old=op.new, new=op.old)
    raise TypeError(f"unsupported diff op: {op!r}")


def invert_ops(ops: List[DiffOp]) -> List[DiffOp]:
    """Return the op list that undoes `ops`, applied in reverse order."""

    return [invert_op(op) for op in reversed(ops)]


def _compile_steps(ops: List[DiffOp]) -> RowTransform:
    steps = [_step_for(op) for op in ops]

    def transform(row: Row) -> Row:
        current = dict(row)
        for step in steps:
            current = step(current)
        return current

    return transform


def _op_lines(op: DiffOp) -> List[str]:
    if isinstance(op, AddColumn):
        return [f"    row[{op.column.name!r}] = None"]
    if isinstance(op, DropColumn):
        return [f"    row.pop({op.column.name!r}, None)"]
    if isinstance(op, RenameColumn):
        return [f"    row[{op.new.name!r}] = row.pop({op.old.name!r}, None)"]
    if isinstance(op, RetypeColumn):
        caster = op.new.dtype if op.new.dtype in CASTERS else "identity"
        return [
            f"    if {op.old.name!r} in row:",
            f"        row[{op.old.name!r}] = _cast_{caster}(row[{op.old.name!r}])",
        ]
    raise TypeError(f"unsupported diff op: {op!r}")


def render_source(ops: List[DiffOp], func_name: str = "transform") -> str:
    """Render `ops` as readable pure-Python source implementing the transform.

    This is a display/review artifact -- e.g. for printing alongside the
    terminal row preview so a reader can see exactly what will run. The
    callables produced by `build_transform` are independent closures, not
    the result of compiling and executing this text.
    """

    lines = [f"def {func_name}(row):", "    row = dict(row)"]
    for op in ops:
        lines.extend(_op_lines(op))
    lines.append("    return row")
    return "\n".join(lines)


@dataclass(frozen=True)
class TransformPair:
    """A forward row transform and its auto-derived inverse."""

    forward: RowTransform
    inverse: RowTransform
    forward_source: str
    inverse_source: str

    def apply_forward(self, rows: List[Row]) -> List[Row]:
        return [self.forward(row) for row in rows]

    def apply_inverse(self, rows: List[Row]) -> List[Row]:
        return [self.inverse(row) for row in rows]


def build_transform(ops: List[DiffOp]) -> TransformPair:
    """Build the forward row transform for `ops` and its derived inverse."""

    inverse_ops = invert_ops(ops)
    return TransformPair(
        forward=_compile_steps(ops),
        inverse=_compile_steps(inverse_ops),
        forward_source=render_source(ops, "transform_forward"),
        inverse_source=render_source(inverse_ops, "transform_inverse"),
    )
