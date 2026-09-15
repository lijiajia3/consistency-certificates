import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from common import (  # noqa: E402
    align_gold_entity,
    gold_error_records,
    gold_relation_ids,
    validate_against_gold,
)


DOC = {
    "vertexSet": [
        [{"name": "Alpha Institute", "type": "ORG"}],
        [{"name": "Alpha", "type": "ORG"}],
        [{"name": "Springfield", "type": "LOC"}],
        [{"name": "Springfield", "type": "ORG"}],
        [{"name": "2024", "type": "TIME"}],
    ],
    "labels": [{"h": 0, "r": "P571", "t": 4}],
}


class GoldAlignmentTests(unittest.TestCase):
    def test_exact_unique_alignment_returns_cluster_id(self):
        aligned = align_gold_entity("Alpha Institute", DOC)
        self.assertEqual(aligned["candidate_ids"], (0,))
        self.assertEqual(aligned["gold_type"], "ORG")
        self.assertEqual(aligned["status"], "exact_unique")

    def test_duplicate_alias_with_conflicting_types_abstains(self):
        aligned = align_gold_entity("Springfield", DOC)
        self.assertEqual(aligned["candidate_ids"], (2, 3))
        self.assertIsNone(aligned["gold_type"])
        self.assertEqual(aligned["status"], "exact_ambiguous_type")

    def test_cluster_id_relation_validation_accepts_containment_alias(self):
        violations = [{
            "pid": "P571",
            "h": "alpha institute organization",
            "t": "2024",
            "ht": "PER",
            "tt": "TIME",
            "he": frozenset({"E:a", "E:t", "R:a|P571|t"}),
        }]
        checked, _ = validate_against_gold(violations, {}, DOC)
        self.assertTrue(checked[0]["checkable"])
        self.assertEqual(checked[0]["gold_head_ids"], (0,))
        self.assertFalse(checked[0]["rel_spurious"])
        self.assertTrue(checked[0]["h_wrong"])
        self.assertTrue(checked[0]["sound"])

    def test_gold_relations_use_cluster_identifiers(self):
        self.assertEqual(gold_relation_ids(DOC), {(0, "P571", 4)})

    def test_unmatched_entities_are_reported_not_assumed_wrong(self):
        extraction = {
            "entities": [
                {"name": "Unknown object", "type": "MISC"},
                {"name": "Alpha Institute", "type": "PER"},
            ],
            "relations": [],
        }
        audit = gold_error_records(extraction, DOC)
        self.assertEqual(audit["alignment_counts"]["unmatched"], 1)
        self.assertEqual(len(audit["errors"]), 1)
        self.assertEqual(audit["errors"][0]["category"], "entity_type")


if __name__ == "__main__":
    unittest.main()
