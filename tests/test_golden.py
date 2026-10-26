"""Golden-file tests: pin the exact text columnforge's codegen and report
renderers produce for a fixed schema pair, so any change to their output
format is caught explicitly rather than only through behavioral assertions.
"""

import unittest
from pathlib import Path

from columnforge import build_transform, diff_schemas, preview

GOLDEN_DIR = Path(__file__).parent / "golden"

OLD_SCHEMA = [("id", "int"), ("fname", "str"), ("age", "str"), ("legacy_flag", "bool")]
NEW_SCHEMA = [("id", "int"), ("email", "str"), ("age", "int"), ("first_name", "str")]
SAMPLE_ROWS = [{"id": 1, "fname": "Ada", "age": "36", "legacy_flag": True}]


def _read_golden(name: str) -> str:
    return (GOLDEN_DIR / name).read_text(encoding="utf-8")


class CodegenGoldenTests(unittest.TestCase):
    def setUp(self):
        self.ops = diff_schemas(OLD_SCHEMA, NEW_SCHEMA)
        self.pair = build_transform(self.ops)

    def test_forward_source_matches_golden_file(self):
        self.assertEqual(self.pair.forward_source, _read_golden("forward_transform.txt"))

    def test_inverse_source_matches_golden_file(self):
        self.assertEqual(self.pair.inverse_source, _read_golden("inverse_transform.txt"))


class ReportGoldenTests(unittest.TestCase):
    def test_plain_report_matches_golden_file(self):
        text = preview(OLD_SCHEMA, NEW_SCHEMA, SAMPLE_ROWS, color=False)
        self.assertEqual(text, _read_golden("preview_plain.txt"))

    def test_colored_report_matches_golden_file(self):
        text = preview(OLD_SCHEMA, NEW_SCHEMA, SAMPLE_ROWS, color=True)
        self.assertEqual(text, _read_golden("preview_color.txt"))


if __name__ == "__main__":
    unittest.main()
