"""Round-trip proofs for a schema diff's generated transform pair.

A diff's forward/inverse transforms (see `codegen.build_transform`) are
only trustworthy if running real data through forward-then-inverse
actually reconstructs the original rows. This module builds a seeded,
deterministic table of random rows matching an old schema, pushes each
row through forward-then-inverse, and asserts the result is exactly
what the diff's semantics promise -- raising a detailed, loud error the
moment any row fails to reconstruct instead of silently trusting the
pipeline.

The only data loss the pipeline ever admits is a dropped column coming
back as `None` (see `codegen`'s module docstring); that is treated as
the expected, documented outcome, not a failure. Everything else --
adds, drops, renames, and retypes among the dtypes columnforge natively
casts (`int`, `float`, `str`, `bool`) -- must reconstruct exactly, so
the random generator only ever produces values that are known to be
losslessly invertible for the specific dtype conversion a given column
will undergo.
"""

import random
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Union

from .codegen import Row, TransformPair, build_transform
from .diff import DiffOp, DropColumn, RetypeColumn, diff_schemas
from .schema import ColumnSpec, Schema

_STR_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_NULL_PROBABILITY = 0.1
_INT_RANGE = (-1000, 1000)
_FLOAT_RANGE = (-1000.0, 1000.0)


class RoundTripError(AssertionError):
    """Raised when a seeded row fails to reconstruct through forward+inverse."""


def _random_str(rng: random.Random) -> str:
    length = rng.randint(1, 12)
    return "".join(rng.choice(_STR_ALPHABET) for _ in range(length))


def _random_scalar(dtype: str, rng: random.Random) -> Any:
    """A random value of `dtype`, with no concern for any later retype."""

    if dtype == "int":
        return rng.randint(*_INT_RANGE)
    if dtype == "float":
        return round(rng.uniform(*_FLOAT_RANGE), 6)
    if dtype == "bool":
        return rng.choice([True, False])
    if dtype == "str":
        return _random_str(rng)
    # Unknown/custom dtype: build_transform treats it as opaque (identity
    # cast), so any distinguishable value exercises the pipeline fine.
    return f"{dtype}-{rng.randint(0, 1_000_000)}"


def _random_retype_safe(old_dtype: str, new_dtype: str, rng: random.Random) -> Any:
    """A random `old_dtype` value guaranteed to cast to `new_dtype` and back
    to an equal value.

    Casting through `bool`, or truncating a `float` into an `int`, loses
    information for arbitrary values (e.g. `int(bool(5)) == 1 != 5`), so
    those conversions are generated from a restricted domain -- 0/1-valued
    numbers and integral floats -- where the round trip is exact. Every
    other pairing of the four natively-cast dtypes is exactly invertible
    for any value, so it falls back to the general-purpose generator.
    """

    if old_dtype == "bool" or new_dtype == "bool":
        as_bool = rng.choice([True, False])
        if old_dtype == "bool":
            return as_bool
        if old_dtype == "int":
            return int(as_bool)
        if old_dtype == "float":
            return float(as_bool)
        if old_dtype == "str":
            return "True" if as_bool else "False"

    if old_dtype == "float" and new_dtype == "int":
        return float(rng.randint(*_INT_RANGE))

    if old_dtype == "str" and new_dtype == "int":
        return str(rng.randint(*_INT_RANGE))

    if old_dtype == "str" and new_dtype == "float":
        return str(round(rng.uniform(*_FLOAT_RANGE), 6))

    return _random_scalar(old_dtype, rng)


def _retype_targets(ops: Iterable[DiffOp]) -> Dict[str, str]:
    """Map each column undergoing a RetypeColumn to its new dtype."""

    return {op.old.name: op.new.dtype for op in ops if isinstance(op, RetypeColumn)}


def generate_table(
    schema: Schema,
    n_rows: int,
    seed: int,
    *,
    retype_targets: Dict[str, str] = None,
) -> List[Row]:
    """Generate `n_rows` deterministic random rows matching `schema`.

    The same `seed` always produces the same rows. If `retype_targets`
    maps a column name to the dtype it will be retyped to, that column's
    values are drawn from the subset that casts losslessly to the target
    dtype and back, so a round-trip proof built on this table never fails
    due to an inherently lossy cast rather than an actual pipeline bug.
    """

    rng = random.Random(seed)
    retype_targets = retype_targets or {}

    rows: List[Row] = []
    for _ in range(n_rows):
        row: Row = {}
        for column in schema:
            if column.nullable and rng.random() < _NULL_PROBABILITY:
                row[column.name] = None
                continue
            target_dtype = retype_targets.get(column.name)
            if target_dtype is not None:
                row[column.name] = _random_retype_safe(column.dtype, target_dtype, rng)
            else:
                row[column.name] = _random_scalar(column.dtype, rng)
        rows.append(row)
    return rows


def _expected_row(row: Row, dropped_columns: set) -> Row:
    expected = dict(row)
    for name in dropped_columns:
        expected[name] = None
    return expected


def _verify_row(
    index: int,
    row: Row,
    forward_row: Row,
    restored_row: Row,
    dropped_columns: set,
) -> None:
    expected = _expected_row(row, dropped_columns)
    if restored_row != expected:
        raise RoundTripError(
            "round-trip reconstruction failed at row "
            f"{index}:\n"
            f"  original: {row!r}\n"
            f"  forward:  {forward_row!r}\n"
            f"  restored: {restored_row!r}\n"
            f"  expected: {expected!r}"
        )


@dataclass(frozen=True)
class RoundTripReport:
    """Summary of a successful round-trip proof."""

    ops: List[DiffOp]
    rows_checked: int
    seed: int


def assert_round_trip(
    old: Union[Schema, Iterable[ColumnSpec]],
    new: Union[Schema, Iterable[ColumnSpec]],
    *,
    n_rows: int = 50,
    seed: int = 0,
) -> RoundTripReport:
    """Prove that `old`-to-`new`'s forward+inverse transform reconstructs
    a seeded random table exactly.

    Generates `n_rows` deterministic rows matching `old`, runs each
    through the diff's forward transform and then its inverse, and
    raises `RoundTripError` the moment a row does not come back exactly
    as expected -- equal to the original row, except that any dropped
    column is expected to come back as `None` (its forward value is
    discarded, so that is the documented, non-failing outcome).
    """

    old_schema = old if isinstance(old, Schema) else Schema(old)
    new_schema = new if isinstance(new, Schema) else Schema(new)

    ops = diff_schemas(old_schema, new_schema)
    pair: TransformPair = build_transform(ops)
    dropped_columns = {op.column.name for op in ops if isinstance(op, DropColumn)}

    rows = generate_table(
        old_schema, n_rows, seed, retype_targets=_retype_targets(ops)
    )

    for index, row in enumerate(rows):
        forward_row = pair.forward(row)
        restored_row = pair.inverse(forward_row)
        _verify_row(index, row, forward_row, restored_row, dropped_columns)

    return RoundTripReport(ops=ops, rows_checked=len(rows), seed=seed)
