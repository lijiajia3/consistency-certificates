# -*- coding: utf-8 -*-
"""Conflict-hypergraph consistency certificates.

Each emitted item is a vertex. A violated constraint is a hyperedge containing
the emitted items that cannot all be correct. Consequently, the unknown set of
erroneous items is a transversal (hitting set) of the conflict hypergraph. Any
family of pairwise vertex-disjoint hyperedges requires a distinct error in every
member, so the hypergraph matching number is a sound error lower bound.

Unlike ordinary graph matching, maximum matching in a general hypergraph is
NP-hard. Document-level extraction outputs in this project contain few
violations (at most 16 in the released Re-DocRED runs), so an exact deterministic
branch-and-bound solver is practical and avoids the order sensitivity of the
previous greedy packing.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import combinations
from typing import Hashable, Iterable


Hyperedge = frozenset[Hashable]


def _canonical_hyperedges(hyperedges: Iterable[Iterable[Hashable]]) -> tuple[Hyperedge, ...]:
    """Drop empty/duplicate hyperedges and return a deterministic ordering."""
    unique = {frozenset(edge) for edge in hyperedges if edge}
    return tuple(sorted(unique, key=lambda edge: (len(edge), tuple(sorted(map(str, edge))))))


def greedy_disjoint_lower_bound(hyperedges: Iterable[Iterable[Hashable]]) -> int:
    """Return an order-dependent maximal packing, retained only as a baseline."""
    used: set[Hashable] = set()
    bound = 0
    for edge in hyperedges:
        edge = frozenset(edge)
        if edge and not edge.intersection(used):
            bound += 1
            used.update(edge)
    return bound


def _overlap_masks(edges: tuple[Hyperedge, ...]) -> tuple[int, ...]:
    masks = [0] * len(edges)
    for i, j in combinations(range(len(edges)), 2):
        if edges[i].intersection(edges[j]):
            masks[i] |= 1 << j
            masks[j] |= 1 << i
    return tuple(masks)


def _edge_components(overlap_masks: tuple[int, ...]) -> list[int]:
    """Return bit masks for components of the hyperedge-overlap graph."""
    unseen = (1 << len(overlap_masks)) - 1
    components: list[int] = []
    while unseen:
        seed = unseen & -unseen
        component = 0
        frontier = seed
        while frontier:
            bit = frontier & -frontier
            frontier ^= bit
            index = bit.bit_length() - 1
            component |= bit
            frontier |= overlap_masks[index] & unseen & ~component
        unseen &= ~component
        components.append(component)
    return components


def _maximum_independent_set_size(component: int, overlap_masks: tuple[int, ...]) -> int:
    """Exact maximum independent set on one hyperedge-overlap component."""

    @lru_cache(maxsize=None)
    def solve(candidates: int) -> int:
        if not candidates:
            return 0
        indices = [i for i in range(len(overlap_masks)) if candidates & (1 << i)]
        pivot = max(
            indices,
            key=lambda i: ((overlap_masks[i] & candidates).bit_count(), -i),
        )
        pivot_bit = 1 << pivot
        without_pivot = candidates & ~pivot_bit
        excluded = solve(without_pivot)
        included = 1 + solve(without_pivot & ~overlap_masks[pivot])
        return max(excluded, included)

    return solve(component)


def maximum_disjoint_lower_bound(hyperedges: Iterable[Iterable[Hashable]]) -> int:
    """Return the exact hypergraph matching number (a sound error lower bound)."""
    edges = _canonical_hyperedges(hyperedges)
    if not edges:
        return 0
    overlaps = _overlap_masks(edges)
    return sum(
        _maximum_independent_set_size(component, overlaps)
        for component in _edge_components(overlaps)
    )


def hypergraph_stats(hyperedges: Iterable[Iterable[Hashable]]) -> dict[str, float | int]:
    """Describe conflict incidence without treating a hyperedge as pairwise conflict."""
    edges = _canonical_hyperedges(hyperedges)
    if not edges:
        return {
            "n_vertices": 0,
            "n_hyperedges": 0,
            "mean_hyperedge_cardinality": 0.0,
            "maximum_hyperedge_cardinality": 0,
            "maximum_vertex_degree": 0,
            "n_components": 0,
            "largest_component_vertices": 0,
            "largest_component_hyperedges": 0,
            "hyperedge_overlap_density": 0.0,
            "incidence_density": 0.0,
            "matching_number": 0,
        }

    vertices = set().union(*edges)
    degrees = Counter(vertex for edge in edges for vertex in edge)
    overlaps = _overlap_masks(edges)
    components = _edge_components(overlaps)
    component_vertex_counts = [
        len(
            set().union(
                *(edges[i] for i in range(len(edges)) if component & (1 << i))
            )
        )
        for component in components
    ]
    component_edge_counts = [component.bit_count() for component in components]
    overlap_pairs = sum(mask.bit_count() for mask in overlaps) // 2
    possible_pairs = len(edges) * (len(edges) - 1) // 2
    incidences = sum(len(edge) for edge in edges)

    return {
        "n_vertices": len(vertices),
        "n_hyperedges": len(edges),
        "mean_hyperedge_cardinality": incidences / len(edges),
        "maximum_hyperedge_cardinality": max(map(len, edges)),
        "maximum_vertex_degree": max(degrees.values()),
        "n_components": len(components),
        "largest_component_vertices": max(component_vertex_counts),
        "largest_component_hyperedges": max(component_edge_counts),
        "hyperedge_overlap_density": overlap_pairs / possible_pairs if possible_pairs else 0.0,
        "incidence_density": incidences / (len(vertices) * len(edges)),
        "matching_number": sum(
            _maximum_independent_set_size(component, overlaps)
            for component in components
        ),
    }


def _brute_force_matching_number(edges: tuple[Hyperedge, ...]) -> int:
    best = 0
    for size in range(len(edges) + 1):
        for choice in combinations(edges, size):
            used: set[Hashable] = set()
            valid = True
            for edge in choice:
                if used.intersection(edge):
                    valid = False
                    break
                used.update(edge)
            if valid:
                best = size
    return best


def _test() -> bool:
    """Unit cases plus random exact comparisons against exhaustive enumeration."""
    cases = [
        ("empty", [], 0),
        ("two disjoint", [{1, 2}, {3, 4}], 2),
        ("all overlap", [{1, 2, 3}, {1, 4}, {1, 5}], 1),
        ("greedy trap", [{1, 3}, {1, 2}, {3, 4}], 2),
        ("mixed cardinality", [{1, 2, 3}, {3, 4}, {5, 6}], 2),
    ]
    ok = True
    for name, edges, expected in cases:
        observed = maximum_disjoint_lower_bound(edges)
        passed = observed == expected
        ok &= passed
        print(
            f"{name:18} observed={observed} expected={expected} "
            f"{'PASS' if passed else 'FAIL'}"
        )

    import random

    random.seed(0)
    for trial in range(500):
        vertices = list(range(random.randint(3, 8)))
        edges = []
        for _ in range(random.randint(0, 9)):
            cardinality = random.randint(2, min(4, len(vertices)))
            edges.append(frozenset(random.sample(vertices, cardinality)))
        canonical = _canonical_hyperedges(edges)
        observed = maximum_disjoint_lower_bound(canonical)
        expected = _brute_force_matching_number(canonical)
        if observed != expected:
            print("STRESS FAIL", trial, canonical, observed, expected)
            return False
    print("stress test (500 random hypergraphs): PASS")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if _test() else 1)
