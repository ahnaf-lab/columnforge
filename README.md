# columnforge

A Python library that takes two versions of a tabular schema and generates a
deterministic, reversible transform pipeline between them, complete with an
auto-generated inverse. It renders a side-by-side terminal diff of real
sample rows before/after so you can see the migration, not just trust it.

This repository currently implements the first four building blocks: the
schema diff engine, the codegen step on top of it, a round-trip proof that
holds the generated transforms to their promise, and the terminal
before/after sample-row report. Given an old and a new column specification,
it computes a typed, deterministic list of add/drop/rename/retype
operations, builds a forward row transform for those operations plus an
inverse derived automatically from them, can run a seeded random table
through forward-then-inverse to prove the two actually reconstruct each
other, and can render real sample rows side by side -- before and after --
with every changed cell highlighted.

## Install

Requires Python 3.9+. The package has no third-party dependencies. Install
it in editable mode from this directory:

```bash
pip install -e .
```

Alternatively, run code from this directory directly, or add it to
`sys.path`, without installing anything.

## Usage

```python
from columnforge import diff_schemas, AddColumn, DropColumn, RenameColumn, RetypeColumn

old_schema = [
    ("id", "int"),
    ("fname", "str"),
    ("age", "str"),
    ("legacy_flag", "bool"),
]

new_schema = [
    ("id", "int"),
    ("email", "str"),
    ("age", "int"),
    ("first_name", "str"),
]

ops = diff_schemas(old_schema, new_schema)

for op in ops:
    print(op)
# RetypeColumn(old=Column(name='age', dtype='str', ...), new=Column(name='age', dtype='int', ...))
# RenameColumn(old=Column(name='fname', ...), new=Column(name='email', ...))
# DropColumn(column=Column(name='legacy_flag', ...))
# AddColumn(column=Column(name='first_name', ...))
```

Column specs can be given as `(name, dtype)` or `(name, dtype, nullable)`
tuples, as dicts with `name`/`dtype` (or `type`) and an optional `nullable`
key, or as `Column` instances directly. A `Schema` wraps a parsed, validated,
name-indexed collection of columns and rejects duplicate column names.

Diff matching is deterministic: columns present in both schemas are compared
in sorted name order; columns unique to one side are paired into renames (by
sorted name order) only when their data type matches exactly, otherwise they
are reported as a drop plus an add.

### Transform codegen

`build_transform` turns a list of diff ops into a `TransformPair`: a forward
function that maps an old-schema row (a `dict`) to a new-schema row, and an
inverse function derived automatically from the same ops, applied in reverse.

```python
from columnforge import build_transform, diff_schemas

ops = diff_schemas(old_schema, new_schema)
pair = build_transform(ops)

new_row = pair.forward({"id": 1, "fname": "Ada", "age": "36"})
# {"id": 1, "age": 36, "email": "Ada", "first_name": None}

old_row = pair.inverse(new_row)
# {"id": 1, "age": "36", "legacy_flag": None, "fname": "Ada"}
```

Each op kind has a fixed, mechanical inverse: an add inverts to a drop and
vice versa, a rename inverts to the reverse rename, and a retype inverts to a
retype back to the original dtype (casting between `int`, `float`, `str`, and
`bool`; any other dtype name passes values through unchanged). A dropped
column's data cannot be recovered, so the inverse of a drop restores the
column as `None` rather than its original value.

`pair.forward_source` and `pair.inverse_source` hold a readable pure-Python
rendering of each transform (via `render_source`), meant for display next to
a before/after row preview so you can see what will run, not just trust it.
That text is generated for review only; the callables in `pair.forward` and
`pair.inverse` are built directly as closures and are never produced by
compiling or executing it.

### Round-trip proofs

`assert_round_trip` proves that a diff's forward/inverse pair is actually
reversible, rather than just trusting the derivation in `invert_ops`. It
generates a seeded, deterministic table of random rows matching the old
schema, pushes each row through forward-then-inverse, and raises
`RoundTripError` with the offending row (original, forward, restored, and
expected values) the instant one fails to reconstruct exactly.

```python
from columnforge import assert_round_trip

report = assert_round_trip(old_schema, new_schema, n_rows=200, seed=0)
print(report.rows_checked, len(report.ops))
```

The same `seed` always produces the same table, so a failure is reproducible.
"Exact reconstruction" means the restored row equals the original row, with
one documented exception: a column removed by a `DropColumn` comes back as
`None` (its value was discarded going forward, so there is nothing to
restore), and that is treated as the expected outcome, not a failure.
Retyped columns are held to full exactness: the random generator only draws
values that are known to cast losslessly to the new dtype and back (for
example, a `float`-to-`int` retype only generates integral-valued floats,
since truncating a fractional one would lose information that no amount of
correct pipeline code could recover), so any mismatch always indicates a
real bug in the transform rather than an inherently lossy cast.

`generate_table(schema, n_rows, seed)` is the underlying row generator and
can be used on its own to get a deterministic sample table for a schema.

### Sample-row diff report

`preview` (and its lower-level pieces, `build_report` and `render_report`)
renders a before/after terminal table so you can see what a migration
actually does to real rows, not just trust the generated transform.

```python
from columnforge import preview

rows = [{"id": 1, "fname": "Ada", "age": "36", "legacy_flag": True}]
print(preview(old_schema, new_schema, rows))
```

Each diff op becomes one display column, labeled the same way regardless of
whether a column kept its name, was renamed (`fname→email`), was retyped,
was added (`+first_name`), or was dropped (`-legacy_flag`). Every sample row
renders as a `before` line and an `after` line underneath the header, and any
cell whose value actually changed is highlighted -- in color on a terminal,
or always via the `before`/`after` text itself when color is unavailable, so
nothing depends on color to be understood. An added or dropped column's
missing side is always highlighted, since there is nothing on the other side
to compare it to.

Color is used automatically when stdout is a terminal and the `NO_COLOR`
environment variable is unset; pass `color=True`/`color=False` to `preview`
or `render_report` to override that detection explicitly (for example, when
capturing output for a log file). `build_report` returns the structured
`SampleRowReport` (ops, column pairings, and per-row before/after/changed
data) if you want to build your own renderer instead of the built-in
text table.

## Status

This project is built autonomously, milestone by milestone, with each change
gated on passing its automated test suite before being accepted.
