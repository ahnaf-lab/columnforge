# columnforge

A Python library that takes two versions of a tabular schema and generates a
deterministic, reversible transform pipeline between them, complete with an
auto-generated inverse. It renders a side-by-side terminal diff of real
sample rows before/after so you can see the migration, not just trust it.

This repository currently implements the first building block: the schema
diff engine. Given an old and a new column specification, it computes a
typed, deterministic list of add/drop/rename/retype operations. Later
milestones will build the transform pipeline and the terminal preview on top
of this diff.

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

## Status

This project is built autonomously, milestone by milestone, with each change
gated on passing its automated test suite before being accepted.
