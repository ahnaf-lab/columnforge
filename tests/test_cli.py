import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from columnforge.cli import main

OLD_SCHEMA = [["id", "int"], ["fname", "str"], ["age", "str"], ["legacy_flag", "bool"]]
NEW_SCHEMA = [["id", "int"], ["email", "str"], ["age", "int"], ["first_name", "str"]]
SAMPLE_ROWS = [{"id": 1, "fname": "Ada", "age": "36", "legacy_flag": True}]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        tmp = Path(self.tmpdir.name)

        self.old_path = tmp / "old.json"
        self.new_path = tmp / "new.json"
        self.rows_path = tmp / "rows.json"
        self.old_path.write_text(json.dumps(OLD_SCHEMA))
        self.new_path.write_text(json.dumps(NEW_SCHEMA))
        self.rows_path.write_text(json.dumps(SAMPLE_ROWS))

    def _run(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(argv)
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_diff_command_lists_each_op(self):
        exit_code, out, _ = self._run(["diff", str(self.old_path), str(self.new_path)])

        self.assertEqual(exit_code, 0)
        self.assertIn("retype age str -> int", out)
        self.assertIn("rename fname -> email", out)
        self.assertIn("drop   legacy_flag (bool)", out)
        self.assertIn("add    first_name (str)", out)

    def test_codegen_command_prints_forward_and_inverse_source(self):
        exit_code, out, _ = self._run(["codegen", str(self.old_path), str(self.new_path)])

        self.assertEqual(exit_code, 0)
        self.assertIn("def transform_forward(row):", out)
        self.assertIn("def transform_inverse(row):", out)
        self.assertIn("row['email'] = row.pop('fname', None)", out)

    def test_roundtrip_command_reports_success(self):
        exit_code, out, _ = self._run(
            ["roundtrip", str(self.old_path), str(self.new_path), "--rows", "25", "--seed", "3"]
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("round-trip OK", out)
        self.assertIn("25 rows checked", out)
        self.assertIn("seed=3", out)

    def test_preview_command_renders_before_after_table(self):
        exit_code, out, _ = self._run(
            [
                "preview",
                str(self.old_path),
                str(self.new_path),
                str(self.rows_path),
                "--color",
                "never",
            ]
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("fname→email", out)
        self.assertIn("before", out)
        self.assertIn("after", out)
        self.assertNotIn("\033[", out)

    def test_missing_command_exits_nonzero(self):
        with self.assertRaises(SystemExit):
            self._run([])


if __name__ == "__main__":
    unittest.main()
