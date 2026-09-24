import csv
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from ablation_gold_ids import unique_exact_gold_id  # noqa: E402


class GoldIdAnchorTests(unittest.TestCase):
    def test_unique_exact_alias_receives_gold_id(self):
        document = {"vertexSet": [
            [{"name": "Alice Smith", "type": "PER"}, {"name": "A. Smith", "type": "PER"}],
            [{"name": "Boston", "type": "LOC"}],
        ]}
        self.assertEqual(unique_exact_gold_id("A. Smith", document), 0)
        self.assertEqual(unique_exact_gold_id("BOSTON", document), 1)

    def test_containment_is_not_oracle_identification(self):
        document = {"vertexSet": [[{"name": "Alice Smith", "type": "PER"}]]}
        self.assertIsNone(unique_exact_gold_id("Alice", document))

    def test_duplicate_alias_does_not_force_cluster_choice(self):
        document = {"vertexSet": [
            [{"name": "Washington", "type": "PER"}],
            [{"name": "Washington", "type": "LOC"}],
        ]}
        self.assertIsNone(unique_exact_gold_id("Washington", document))

    def test_released_ablation_retains_holdout_failures(self):
        path = ROOT / "result" / "revision" / "gold_id_anchor_ablation.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = {(row["setting"], row["model"]): row for row in csv.DictReader(handle)}
        holdout = rows[("holdout", "ALL")]
        self.assertEqual(int(holdout["exact_unique_checkable"]), 2726)
        self.assertEqual(int(holdout["exact_unique_validated"]), 2720)
        schema = rows[("schema_only", "ALL")]
        self.assertEqual(int(schema["exact_unique_checkable"]), 2449)
        self.assertEqual(int(schema["exact_unique_validated"]), 2412)


if __name__ == "__main__":
    unittest.main()
