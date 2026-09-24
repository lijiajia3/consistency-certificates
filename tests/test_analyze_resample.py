import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from analyze_resample import entity_type_keys, error_recurrence  # noqa: E402


class ErrorRecurrenceTests(unittest.TestCase):
    def test_spurious_relation_requires_the_exact_triple(self):
        error = {
            "category": "relation_spurious",
            "head": "alpha",
            "pid": "P17",
            "tail": "beta",
        }
        relation_sets = [
            {("alpha", "P17", "beta")},
            {("alpha", "P17", "gamma")},
            {("alpha", "P17", "beta")},
        ]
        self.assertEqual(error_recurrence(error, relation_sets, [set()] * 3), 2)

    def test_entity_error_requires_the_same_incorrect_type(self):
        error = {
            "category": "entity_type",
            "name": "alpha institute",
            "emitted_type": "PER",
        }
        entity_sets = [
            {("alpha institute", "PER")},
            {("alpha institute", "ORG")},
            {("alpha institute", "PER")},
        ]
        self.assertEqual(error_recurrence(error, [set()] * 3, entity_sets), 2)

    def test_entity_type_keys_normalizes_names(self):
        extraction = {
            "entities": [
                {"name": "Alpha-Institute", "type": "ORG"},
                {"name": "", "type": "PER"},
            ]
        }
        self.assertEqual(entity_type_keys(extraction), {("alpha institute", "ORG")})


if __name__ == "__main__":
    unittest.main()
