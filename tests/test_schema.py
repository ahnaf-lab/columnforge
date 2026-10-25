import unittest

from columnforge import Column, Schema


class SchemaParsingTests(unittest.TestCase):
    def test_parses_dict_specs(self):
        schema = Schema([{"name": "id", "dtype": "int"}, {"name": "email", "type": "str", "nullable": False}])
        self.assertEqual(schema["id"], Column(name="id", dtype="int", nullable=True))
        self.assertEqual(schema["email"], Column(name="email", dtype="str", nullable=False))

    def test_parses_tuple_specs(self):
        schema = Schema([("id", "int"), ("age", "int", False)])
        self.assertEqual(schema.names, ["id", "age"])
        self.assertFalse(schema["age"].nullable)

    def test_accepts_column_instances_directly(self):
        col = Column(name="id", dtype="int")
        schema = Schema([col])
        self.assertIs(schema["id"], col)

    def test_rejects_duplicate_names(self):
        with self.assertRaises(ValueError):
            Schema([("id", "int"), ("id", "str")])

    def test_rejects_spec_missing_dtype(self):
        with self.assertRaises(ValueError):
            Schema([{"name": "id"}])

    def test_contains_and_len(self):
        schema = Schema([("id", "int"), ("name", "str")])
        self.assertIn("id", schema)
        self.assertNotIn("missing", schema)
        self.assertEqual(len(schema), 2)


if __name__ == "__main__":
    unittest.main()
