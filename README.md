# columnforge

A Python library that takes two versions of a tabular schema and generates a
deterministic, reversible transform pipeline between them, complete with an
auto-generated inverse. It renders a side-by-side terminal diff of real
sample rows before/after so you can see the migration, not just trust it.

This repository currently implements the first two building blocks: the
schema diff engine and the codegen step on top of it. Given an old and a new
column specification, it computes a typed, deterministic list of
add/drop/rename/retype operations, then builds a forward row transform for
those operations plus an inverse derived automatically from them. A later
milestone will add the terminal before/after preview on top of this.

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
    ("first_name", "str"),
    ("age", "int"),
    ("email", "str"),
]

ops = diff_schemas(old_schema, new_schema)

for op in ops:
    print(op)
# RetypeColumn(old=Column(name='age', dtype='str', ...), new=Column(name='age', dtype='int', ...))
# RenameColumn(old=Column(name='fname', ...), new=Column(name='first_name', ...))
# DropColumn(column=Column(name='legacy_flag', ...))
# AddColumn(column=Column(name='email', ...))
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
# {"id": 1, "first_name": "Ada", "age": 36}

old_row = pair.inverse(new_row)
# {"id": 1, "fname": "Ada", "age": "36"}
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

## Status

This project is built autonomously, milestone by milestone, with each change
gated on passing its automated test suite before being accepted.
