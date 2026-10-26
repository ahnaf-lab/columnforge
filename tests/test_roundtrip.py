import unittest

from columnforge import (
    AddColumn,
    Column,
    DropColumn,
    RenameColumn,
    RetypeColumn,
    Schema,
    assert_round_trip,
    build_transform,
    diff_schemas,
)
from columnforge.roundtrip import RoundTripError, _verify_row, generate_table


class GenerateTableTests(unittest.TestCase):
    def test_same_seed_is_deterministic(self):
        schema = Schema([("id", "int"), ("name", "str"), ("active", "bool")])

        first = generate_table(schema, n_rows=20, seed=42)
        second = generate_table(schema, n_rows=20, seed=42)

        self.assertEqual(first, second)

    def test_different_seed_changes_the_table(self):
        schema = Schema([("id", "int"), ("name", "str")])

        first = generate_table(schema, n_rows=20, seed=1)
        second = generate_table(schema, n_rows=20, seed=2)

        self.assertNotEqual(first, second)

    def test_retype_safe_values_cast_losslessly_both_ways(self):
        # age will be retyped float -> int, which truncates in general;
        # the generator must only emit integral-valued floats so the
        # round trip through build_transform's casters is exact.
        schema = Schema([("age", "float")])
        targets = {"age": "int"}

        rows = generate_table(schema, n_rows=30, seed=7, retype_targets=targets)
        pair = build_transform(
            [RetypeColumn(old=schema["age"], new=Column(name="age", dtype="int"))]
        )

        for row in rows:
            forward_row = pair.forward(row)
            restored_row = pair.inverse(forward_row)
            self.assertEqual(restored_row, row)


class AssertRoundTripTests(unittest.TestCase):
    def test_mixed_diff_round_trips_exactly(self):
        old = [("id", "int"), ("fname", "str"), ("age", "str"), ("legacy", "bool")]
        new = [("id", "int"), ("first_name", "str"), ("age", "int"), ("email", "str")]

        report = assert_round_trip(old, new, n_rows=40, seed=123)

        ops = diff_schemas(old, new)
        self.assertEqual(report.rows_checked, 40)
        self.assertEqual(len(report.ops), len(ops))
        self.assertTrue(any(isinstance(op, RenameColumn) for op in report.ops))
        self.assertTrue(any(isinstance(op, RetypeColumn) for op in report.ops))
        self.assertTrue(any(isinstance(op, DropColumn) for op in report.ops))
        self.assertTrue(any(isinstance(op, AddColumn) for op in report.ops))

    def test_dropped_column_round_trips_to_documented_none(self):
        old = [("id", "int"), ("legacy_flag", "bool")]
        new = [("id", "int")]

        # Should not raise: a dropped column coming back as None is the
        # documented, expected outcome, not a reconstruction failure.
        assert_round_trip(old, new, n_rows=10, seed=5)

        ops = diff_schemas(old, new)
        pair = build_transform(ops)
        restored = pair.inverse(pair.forward({"id": 1, "legacy_flag": True}))
        self.assertEqual(restored, {"id": 1, "legacy_flag": None})

    def test_is_deterministic_across_repeated_runs(self):
        old = [("id", "int"), ("score", "float")]
        new = [("id", "int"), ("score", "float")]

        first = assert_round_trip(old, new, n_rows=25, seed=99)
        second = assert_round_trip(old, new, n_rows=25, seed=99)

        self.assertEqual(first.rows_checked, second.rows_checked)
        self.assertEqual(first.ops, second.ops)


class VerifyRowFailsLoudlyTests(unittest.TestCase):
    def test_raises_round_trip_error_on_mismatch(self):
        original = {"id": 1, "name": "Ada"}
        forward_row = {"id": 1, "name": "Ada"}
        corrupted_restore = {"id": 1, "name": "not-ada"}

        with self.assertRaises(RoundTripError) as ctx:
            _verify_row(0, original, forward_row, corrupted_restore, dropped_columns=set())

        message = str(ctx.exception)
        self.assertIn("row 0", message)
        self.assertIn("not-ada", message)

    def test_does_not_raise_when_reconstruction_matches(self):
        original = {"id": 1, "flag": True}
        forward_row = {"id": 1}
        restored = {"id": 1, "flag": None}

        # No exception expected: flag was dropped, so None is correct.
        _verify_row(0, original, forward_row, restored, dropped_columns={"flag"})


if __name__ == "__main__":
    unittest.main()
