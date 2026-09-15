import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from scierc_common import (  # noqa: E402
    align_entity,
    derive_signatures,
    gold_clusters,
    relation_label,
)


class SciERCAdapterTests(unittest.TestCase):
    def test_relation_labels_are_case_and_hyphen_tolerant(self):
        self.assertEqual(relation_label("used for"), "USED-FOR")
        self.assertEqual(relation_label("HYPONYM-OF"), "HYPONYM-OF")

    def test_cluster_alias_alignment(self):
        doc = {
            "sentences": [["neural", "network", "models"]],
            "ner": [[[0, 1, "Method"], [2, 2, "Generic"]]],
            "relations": [[[0, 1, 2, 2, "USED-FOR"]]],
            "clusters": [[[0, 1]]],
        }
        gold = gold_clusters(doc)
        aligned = align_entity("neural network", gold)
        self.assertEqual(aligned["gold_type"], "Method")
        self.assertEqual(gold["relations"], {(0, "USED-FOR", 1)})

    def test_signatures_are_derived_from_gold_relations(self):
        doc = {
            "sentences": [["method", "task"]],
            "ner": [[[0, 0, "Method"], [1, 1, "Task"]]],
            "relations": [[[0, 0, 1, 1, "USED-FOR"]]],
            "clusters": [],
        }
        self.assertEqual(derive_signatures([doc]), {"USED-FOR": {("Method", "Task")}})


if __name__ == "__main__":
    unittest.main()
