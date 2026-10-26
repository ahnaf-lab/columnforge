import unittest

from columnforge import (
    AddColumn,
    Column,
    DropColumn,
    RenameColumn,
    RetypeColumn,
    build_transform,
    diff_schemas,
    invert_op,
    render_source,
)


class BuildTransformTests(unittest.TestCase):
    def test_add_column_forward_sets_none_inverse_drops_it(self):
        ops = [AddColumn(column=Column(name="email", dtype="str"))]
        pair = build_transform(ops)

        forward_row = pair.forward({"id": 1})
        self.assertEqual(forward_row, {"id": 1, "email": None})

        inverse_row = pair.inverse(forward_row)
        self.assertEqual(inverse_row, {"id": 1})

    def test_drop_column_forward_removes_it_inverse_restores_as_none(self):
        ops = [DropColumn(column=Column(name="legacy_flag", dtype="bool"))]
        pair = build_transform(ops)

        forward_row = pair.forward({"id": 1, "legacy_flag": True})
        self.assertEqual(forward_row, {"id": 1})

        inverse_row = pair.inverse(forward_row)
        self.assertEqual(inverse_row, {"id": 1, "legacy_flag": None})

    def test_rename_column_round_trips(self):
        ops = [
            RenameColumn(
                old=Column(name="fname", dtype="str"),
                new=Column(name="first_name", dtype="str"),
            )
        ]
        pair = build_transform(ops)

        forward_row = pair.forward({"fname": "Ada"})
        self.assertEqual(forward_row, {"first_name": "Ada"})

        inverse_row = pair.inverse(forward_row)
        self.assertEqual(inverse_row, {"fname": "Ada"})

    def test_retype_column_casts_value_and_round_trips(self):
        ops = [
            RetypeColumn(
                old=Column(name="age", dtype="str"),
                new=Column(name="age", dtype="int"),
            )
        ]
        pair = build_transform(ops)

        forward_row = pair.forward({"age": "42"})
        self.assertEqual(forward_row, {"age": 42})
        self.assertIsInstance(forward_row["age"], int)

        inverse_row = pair.inverse(forward_row)
        self.assertEqual(inverse_row, {"age": "42"})
        self.assertIsInstance(inverse_row["age"], str)

    def test_retype_passes_through_none(self):
        ops = [
            RetypeColumn(
                old=Column(name="age", dtype="str"),
                new=Column(name="age", dtype="int"),
            )
        ]
        pair = build_transform(ops)
        self.assertEqual(pair.forward({"age": None}), {"age": None})

    def test_forward_does_not_mutate_input_row(self):
        ops = [AddColumn(column=Column(name="email", dtype="str"))]
        pair = build_transform(ops)
        original = {"id": 1}

        pair.forward(original)

        self.assertEqual(original, {"id": 1})

    def test_full_mixed_diff_round_trips_for_non_destructive_ops(self):
        old = [
            ("id", "int"),
            ("fname", "str"),
            ("age", "str"),
        ]
        new = [
            ("id", "int"),
            ("first_name", "str"),
            ("age", "int"),
        ]
        ops = diff_schemas(old, new)
        pair = build_transform(ops)

        old_row = {"id": 1, "fname": "Ada", "age": "36"}
        new_row = pair.forward(old_row)
        self.assertEqual(new_row, {"id": 1, "first_name": "Ada", "age": 36})

        round_tripped = pair.inverse(new_row)
        self.assertEqual(round_tripped, old_row)

    def test_invert_op_roundtrips_each_kind(self):
        add = AddColumn(column=Column(name="email", dtype="str"))
        self.assertEqual(invert_op(add), DropColumn(column=add.column))

        drop = DropColumn(column=Column(name="legacy", dtype="bool"))
        self.assertEqual(invert_op(drop), AddColumn(column=drop.column))

        rename = RenameColumn(
            old=Column(name="fname", dtype="str"),
            new=Column(name="first_name", dtype="str"),
        )
        self.assertEqual(
            invert_op(rename), RenameColumn(old=rename.new, new=rename.old)
        )

        retype = RetypeColumn(
            old=Column(name="age", dtype="str"), new=Column(name="age", dtype="int")
        )
        self.assertEqual(
            invert_op(retype), RetypeColumn(old=retype.new, new=retype.old)
        )


class RenderSourceTests(unittest.TestCase):
    def test_render_source_contains_expected_statements(self):
        ops = [
            AddColumn(column=Column(name="email", dtype="str")),
            DropColumn(column=Column(name="legacy_flag", dtype="bool")),
            RenameColumn(
                old=Column(name="fname", dtype="str"),
                new=Column(name="first_name", dtype="str"),
            ),
            RetypeColumn(
                old=Column(name="age", dtype="str"), new=Column(name="age", dtype="int")
            ),
        ]
        source = render_source(ops, "transform_forward")

        self.assertTrue(source.startswith("def transform_forward(row):"))
        self.assertIn("row['email'] = None", source)
        self.assertIn("row.pop('legacy_flag', None)", source)
        self.assertIn("row['first_name'] = row.pop('fname', None)", source)
        self.assertIn("_cast_int(row['age'])", source)

    def test_render_source_is_syntactically_valid_python(self):
        ops = [
            AddColumn(column=Column(name="email", dtype="str")),
            RetypeColumn(
                old=Column(name="age", dtype="str"), new=Column(name="age", dtype="int")
            ),
        ]
        source = render_source(ops, "transform_forward")

        # compile() only parses/compiles the text; it never executes it.
        compile(source, "<render_source>", "exec")

    def test_render_source_escapes_unusual_column_names(self):
        ops = [AddColumn(column=Column(name="weird'name", dtype="str"))]
        source = render_source(ops)

        compile(source, "<render_source>", "exec")
        self.assertIn("weird", source)


if __name__ == "__main__":
    unittest.main()
