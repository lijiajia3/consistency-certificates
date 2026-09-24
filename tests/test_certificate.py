import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from certificate import (  # noqa: E402
    greedy_disjoint_lower_bound,
    hypergraph_stats,
    maximum_disjoint_lower_bound,
    minimum_hitting_set_lower_bound,
)


class HypergraphCertificateTests(unittest.TestCase):
    def test_empty_family_has_zero_bound(self):
        self.assertEqual(maximum_disjoint_lower_bound([]), 0)

    def test_binary_and_ternary_hyperedges_share_one_interface(self):
        edges = [{"a", "b"}, {"c", "d", "e"}, {"b", "f", "g"}]
        self.assertEqual(maximum_disjoint_lower_bound(edges), 2)

    def test_exact_bound_fixes_greedy_order_sensitivity(self):
        # Choosing {a,c} first blocks both singleton-compatible alternatives;
        # the exact packing instead selects {a,b} and {c,d}.
        edges = [{"a", "c"}, {"a", "b"}, {"c", "d"}]
        self.assertEqual(greedy_disjoint_lower_bound(edges), 1)
        self.assertEqual(greedy_disjoint_lower_bound(list(reversed(edges))), 2)
        self.assertEqual(maximum_disjoint_lower_bound(edges), 2)
        self.assertEqual(maximum_disjoint_lower_bound(list(reversed(edges))), 2)

    def test_duplicates_and_empty_hyperedges_do_not_change_bound(self):
        edges = [{"a", "b"}, {"a", "b"}, set(), {"c", "d"}]
        self.assertEqual(maximum_disjoint_lower_bound(edges), 2)

    def test_exact_transversal_tightens_triangle_but_not_star(self):
        triangle = [{"a", "b"}, {"b", "c"}, {"a", "c"}]
        star = [{"a", "b"}, {"a", "c"}, {"a", "d"}]
        self.assertEqual(maximum_disjoint_lower_bound(triangle), 1)
        self.assertEqual(minimum_hitting_set_lower_bound(triangle), 2)
        self.assertEqual(minimum_hitting_set_lower_bound(star), 1)

    def test_hypergraph_statistics_describe_overlap_structure(self):
        edges = [{"a", "b", "c"}, {"c", "d"}, {"x", "y"}]
        stats = hypergraph_stats(edges)
        self.assertEqual(stats["n_vertices"], 6)
        self.assertEqual(stats["n_hyperedges"], 3)
        self.assertEqual(stats["maximum_vertex_degree"], 2)
        self.assertEqual(stats["n_components"], 2)
        self.assertEqual(stats["largest_component_vertices"], 4)
        self.assertAlmostEqual(stats["hyperedge_overlap_density"], 1 / 3)
        self.assertEqual(stats["matching_number"], 2)


if __name__ == "__main__":
    unittest.main()
