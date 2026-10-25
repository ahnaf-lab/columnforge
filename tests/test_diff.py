import unittest

from columnforge import (
    AddColumn,
    DropColumn,
    RenameColumn,
    RetypeColumn,
    diff_schemas,
)


class DiffSchemasTests(unittest.TestCase):
    def test_no_changes_yields_empty_diff(self):
        old = [("id", "int"), ("name", "str")]
        new = [("id", "int"), ("name", "str")]
        self.assertEqual(diff_schemas(old, new), [])

    def test_detects_added_column(self):
        old = [("id", "int")]
        new = [("id", "int"), ("email", "str")]
        ops = diff_schemas(old, new)
        self.assertEqual(len(ops), 1)
        self.assertIsInstance(ops[0], AddColumn)
        self.assertEqual(ops[0].column.name, "email")

    def test_detects_dropped_column(self):
        old = [("id", "int"), ("legacy_flag", "bool")]
        new = [("id", "int")]
        ops = diff_schemas(old, new)
        self.assertEqual(len(ops), 1)
        self.assertIsInstance(ops[0], DropColumn)
        self.assertEqual(ops[0].column.name, "legacy_flag")

    def test_detects_renamed_column_with_matching_dtype(self):
        old = [("id", "int"), ("fname", "str")]
        new = [("id", "int"), ("first_name", "str")]
        ops = diff_schemas(old, new)
        self.assertEqual(len(ops), 1)
        self.assertIsInstance(ops[0], RenameColumn)
        self.assertEqual(ops[0].old.name, "fname")
        self.assertEqual(ops[0].new.name, "first_name")

    def test_detects_retyped_column(self):
        old = [("id", "int"), ("age", "str")]
        new = [("id", "int"), ("age", "int")]
        ops = diff_schemas(old, new)
        self.assertEqual(len(ops), 1)
        self.assertIsInstance(ops[0], RetypeColumn)
        self.assertEqual(ops[0].old.dtype, "str")
        self.assertEqual(ops[0].new.dtype, "int")

    def test_rename_requires_matching_dtype_otherwise_drop_and_add(self):
        old = [("id", "int"), ("fname", "str")]
        new = [("id", "int"), ("first_name", "int")]
        ops = diff_schemas(old, new)
        self.assertEqual(len(ops), 2)
        kinds = {type(op) for op in ops}
        self.assertEqual(kinds, {DropColumn, AddColumn})

    def test_mixed_diff_reports_each_op_type(self):
        old = [
            ("id", "int"),
            ("fname", "str"),
            ("age", "str"),
            ("legacy_flag", "bool"),
        ]
        new = [
            ("id", "int"),
            ("first_name", "str"),
            ("age", "int"),
            ("email", "str"),
        ]
        ops = diff_schemas(old, new)
        kinds = [type(op) for op in ops]
        self.assertIn(RetypeColumn, kinds)
        self.assertIn(RenameColumn, kinds)
        self.assertIn(DropColumn, kinds)
        self.assertIn(AddColumn, kinds)
        self.assertEqual(len(ops), 4)

    def test_diff_is_deterministic_across_calls(self):
        old = [("b", "str"), ("a", "str"), ("c", "int")]
        new = [("x", "str"), ("y", "str"), ("c", "float")]
        first = diff_schemas(old, new)
        second = diff_schemas(old, new)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
