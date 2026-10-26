import unittest

from columnforge import (
    AddColumn,
    DropColumn,
    RenameColumn,
    Schema,
    build_pairings,
    build_report,
    diff_schemas,
    render_report,
)


class BuildPairingsTests(unittest.TestCase):
    def setUp(self):
        self.old = Schema(
            [
                ("id", "int"),
                ("fname", "str"),
                ("age", "str"),
                ("legacy_flag", "bool"),
            ]
        )
        self.new = Schema(
            [
                ("id", "int"),
                ("first_name", "str"),
                ("age", "int"),
                ("email", "str"),
            ]
        )
        self.ops = diff_schemas(self.old, self.new)

    def test_pairing_kinds_match_the_diff(self):
        # fname (str) is paired with email (str), not first_name: diff_schemas
        # matches rename candidates in sorted added-name order, and "email"
        # sorts before "first_name".
        pairings = build_pairings(self.old, self.new, self.ops)
        by_old_name = {p.old_name: p for p in pairings if p.old_name is not None}

        self.assertEqual(by_old_name["id"].kind, "same")
        self.assertEqual(by_old_name["id"].new_name, "id")
        self.assertEqual(by_old_name["age"].kind, "retyped")
        self.assertEqual(by_old_name["fname"].kind, "renamed")
        self.assertEqual(by_old_name["fname"].new_name, "email")
        self.assertEqual(by_old_name["legacy_flag"].kind, "dropped")
        self.assertIsNone(by_old_name["legacy_flag"].new_name)

    def test_added_column_has_no_old_side(self):
        pairings = build_pairings(self.old, self.new, self.ops)
        added = [p for p in pairings if p.kind == "added"]

        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].new_name, "first_name")
        self.assertIsNone(added[0].old_name)

    def test_labels_describe_each_column(self):
        pairings = build_pairings(self.old, self.new, self.ops)
        labels = {p.label for p in pairings}

        self.assertIn("id", labels)
        self.assertIn("fname→email", labels)
        self.assertIn("-legacy_flag", labels)
        self.assertIn("+first_name", labels)


class BuildReportTests(unittest.TestCase):
    def test_unchanged_value_is_not_marked_changed(self):
        old = [("id", "int"), ("name", "str")]
        new = [("id", "int"), ("name", "str")]
        rows = [{"id": 1, "name": "Ada"}]

        report = build_report(old, new, rows)

        self.assertEqual(report.rows[0].before, ["1", "Ada"])
        self.assertEqual(report.rows[0].after, ["1", "Ada"])
        self.assertEqual(report.rows[0].changed, [False, False])

    def test_retyped_value_is_marked_changed(self):
        old = [("id", "int"), ("age", "str")]
        new = [("id", "int"), ("age", "int")]
        rows = [{"id": 1, "age": "36"}]

        report = build_report(old, new, rows)

        self.assertEqual(report.rows[0].before, ["1", "36"])
        self.assertEqual(report.rows[0].after, ["1", "36"])
        self.assertEqual(report.rows[0].changed, [False, True])

    def test_added_and_dropped_columns_are_always_marked_changed(self):
        old = [("id", "int"), ("legacy", "bool")]
        new = [("id", "int"), ("email", "str")]
        rows = [{"id": 1, "legacy": True}]

        report = build_report(old, new, rows)
        pairings = report.pairings
        legacy_index = next(i for i, p in enumerate(pairings) if p.kind == "dropped")
        email_index = next(i for i, p in enumerate(pairings) if p.kind == "added")

        self.assertTrue(report.rows[0].changed[legacy_index])
        self.assertTrue(report.rows[0].changed[email_index])
        self.assertEqual(report.rows[0].after[legacy_index], "—")
        self.assertEqual(report.rows[0].before[email_index], "—")

    def test_multiple_rows_each_produce_their_own_diff(self):
        old = [("id", "int"), ("age", "str")]
        new = [("id", "int"), ("age", "int")]
        rows = [{"id": 1, "age": "10"}, {"id": 2, "age": "20"}]

        report = build_report(old, new, rows)

        self.assertEqual(len(report.rows), 2)
        self.assertEqual(report.rows[0].after, ["1", "10"])
        self.assertEqual(report.rows[1].after, ["2", "20"])


class RenderReportTests(unittest.TestCase):
    def setUp(self):
        self.old = [("id", "int"), ("fname", "str"), ("age", "str"), ("legacy", "bool")]
        self.new = [("id", "int"), ("first_name", "str"), ("age", "int"), ("email", "str")]
        self.rows = [{"id": 1, "fname": "Ada", "age": "36", "legacy": True}]
        self.report = build_report(self.old, self.new, self.rows)

    def test_plain_render_contains_headers_and_values_with_no_ansi(self):
        text = render_report(self.report, color=False)

        self.assertIn("fname→email", text)
        self.assertIn("-legacy", text)
        self.assertIn("+first_name", text)
        self.assertIn("Ada", text)
        self.assertIn("36", text)
        self.assertIn("before", text)
        self.assertIn("after", text)
        self.assertNotIn("\033[", text)

    def test_colored_render_highlights_only_changed_cells(self):
        text = render_report(self.report, color=True)

        self.assertIn("\033[", text)
        # "id" and the renamed "fname"/"first_name" values are unchanged,
        # so they must appear without any surrounding color codes.
        self.assertIn(" 1 ", text.replace("\033[1;33m", " ").replace("\033[0m", " "))
        self.assertIn("\033[1;33m", text)  # the retyped age value changed
        self.assertIn("\033[1;31m", text)  # legacy was dropped
        self.assertIn("\033[1;32m", text)  # email was added

    def test_color_and_plain_render_have_the_same_layout_width(self):
        plain = render_report(self.report, color=False)
        colored = render_report(self.report, color=True)

        plain_header_width = len(plain.splitlines()[0])
        colored_header_width = len(colored.splitlines()[0])
        self.assertEqual(plain_header_width, colored_header_width)


if __name__ == "__main__":
    unittest.main()
