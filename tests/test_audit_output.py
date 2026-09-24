import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from audit_output import audit  # noqa: E402


class AuditOutputConstraintRoleTests(unittest.TestCase):
    def setUp(self):
        self.functional_clash = {
            "entities": [
                {"name": "Alice", "type": "PER"},
                {"name": "1990", "type": "TIME"},
                {"name": "1991", "type": "TIME"},
            ],
            "relations": [
                {"head": "Alice", "relation": "date of birth", "tail": "1990"},
                {"head": "Alice", "relation": "date of birth", "tail": "1991"},
            ],
        }

    def test_all_reports_functional_warning_without_certifying_it(self):
        result = audit(self.functional_clash, "all")
        self.assertEqual(result["violations_by_family"]["functional"], 1)
        self.assertEqual(result["exploratory_warning_count"], 1)
        self.assertEqual(result["certified_error_lower_bound"], 0)
        functional = [
            row for row in result["violations"] if row["family"] == "functional"
        ]
        self.assertEqual(functional[0]["role"], "exploratory")

    def test_functional_only_never_issues_certificate(self):
        result = audit(self.functional_clash, "functional")
        self.assertIsNone(result["certified_error_lower_bound"])
        self.assertIn("not issued", result["certificate"])


if __name__ == "__main__":
    unittest.main()
