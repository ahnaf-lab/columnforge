"""Parsing and representation of a tabular column schema.

A schema is an ordered collection of columns, each with a name, a data
type, and a nullability flag. Schemas accept several equivalent input
shapes so callers can hand in whatever they already have on hand
(dicts, (name, dtype) tuples, or Column instances).
"""

from dataclasses import dataclass
from typing import Any, Iterable, Iterator, List, Mapping, Sequence, Union

ColumnSpec = Union[Mapping[str, Any], Sequence[Any], "Column"]


@dataclass(frozen=True)
class Column:
    """A single column definition: its name, data type, and nullability."""

    name: str
    dtype: str
    nullable: bool = True


def _parse_column(spec: ColumnSpec) -> Column:
    if isinstance(spec, Column):
        return spec

    if isinstance(spec, Mapping):
        if "name" not in spec:
            raise ValueError(f"column spec is missing a 'name' key: {spec!r}")
        name = spec["name"]
        dtype = spec.get("dtype", spec.get("type"))
        if dtype is None:
            raise ValueError(f"column spec for {name!r} is missing a 'dtype'/'type'")
        nullable = spec.get("nullable", True)
        return Column(name=str(name), dtype=str(dtype), nullable=bool(nullable))

    if isinstance(spec, Sequence) and not isinstance(spec, str):
        if len(spec) == 2:
            name, dtype = spec
            nullable = True
        elif len(spec) == 3:
            name, dtype, nullable = spec
        else:
            raise ValueError(
                f"column spec sequence must have 2 or 3 elements, got {spec!r}"
            )
        return Column(name=str(name), dtype=str(dtype), nullable=bool(nullable))

    raise TypeError(f"unsupported column spec: {spec!r}")


class Schema:
    """An ordered, name-indexed collection of columns."""

    def __init__(self, columns: Iterable[ColumnSpec]):
        parsed: List[Column] = [_parse_column(c) for c in columns]

        seen: dict = {}
        for col in parsed:
            if col.name in seen:
                raise ValueError(f"duplicate column name in schema: {col.name!r}")
            seen[col.name] = col

        self.columns: List[Column] = parsed
        self._by_name: dict = seen

    def __iter__(self) -> Iterator[Column]:
        return iter(self.columns)

    def __len__(self) -> int:
        return len(self.columns)

    def __getitem__(self, name: str) -> Column:
        return self._by_name[name]

    def __contains__(self, name: object) -> bool:
        return name in self._by_name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Schema):
            return NotImplemented
        return self.columns == other.columns

    def __repr__(self) -> str:
        return f"Schema({self.columns!r})"

    @property
    def names(self) -> List[str]:
        return [c.name for c in self.columns]
