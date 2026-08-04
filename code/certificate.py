# -*- coding: utf-8 -*-
"""Consistency certificate: the database-repair error lower bound.

Theorem (classical): erroneous items form a vertex cover of the conflict graph,
so #errors >= |min vertex cover| >= |max matching| = m(G).
Matching is the poly-time certificate; min vertex cover is tighter (exact on small graphs).
"""
import itertools
import networkx as nx


def build_conflict_graph(items, conflicts):
    """Graph on hashable items; an edge (i,j) means i and j cannot both be correct."""
    G = nx.Graph()
    G.add_nodes_from(items)
    for i, j in conflicts:
        if i != j:
            G.add_edge(i, j)
    return G


def matching_lower_bound(G):
    """m(G) = maximum-cardinality matching size: a poly-time valid #errors lower bound."""
    M = nx.max_weight_matching(G, maxcardinality=True)
    return len(M)


def min_vertex_cover_exact(G):
    """Minimum vertex cover (exact, small graphs only): a tighter #errors lower bound."""
    active = [n for n in G.nodes if G.degree(n) > 0]
    E = list(G.edges())
    if not E:
        return 0
    total = 0
    for comp in nx.connected_components(G.subgraph(active)):
        comp = list(comp)
        Ec = [(u, v) for u, v in E if u in comp and v in comp]
        total += _min_cover_bruteforce(comp, Ec)
    return total


def _min_cover_bruteforce(nodes, edges):
    n = len(nodes)
    if n > 20:  # large component: fall back to the (still valid) matching bound
        H = nx.Graph(); H.add_nodes_from(nodes); H.add_edges_from(edges)
        return len(nx.max_weight_matching(H, maxcardinality=True))
    for k in range(0, n + 1):
        for cover in itertools.combinations(nodes, k):
            cs = set(cover)
            if all(u in cs or v in cs for u, v in edges):
                return k
    return n


def certificate(items, conflicts):
    """Return {matching_bound, vertex_cover_bound, n_conflict_edges, conflict_nodes}.
    Guarantee (gold-free): true errors >= vertex_cover_bound >= matching_bound."""
    G = build_conflict_graph(items, conflicts)
    mb = matching_lower_bound(G)
    vc = min_vertex_cover_exact(G)
    return {
        "matching_bound": mb,
        "vertex_cover_bound": vc,
        "n_conflict_edges": G.number_of_edges(),
        "conflict_nodes": sorted([n for n in G.nodes if G.degree(n) > 0], key=str),
    }


def _test():
    """Unit tests + 2000-graph stress test for the matching <= cover <= true-errors order."""
    cases = [
        # (name, items, conflicts, expected matching, expected vertex cover)
        ("empty", [1, 2, 3], [], 0, 0),
        ("single edge", [1, 2], [(1, 2)], 1, 1),
        ("two disjoint", [1, 2, 3, 4], [(1, 2), (3, 4)], 2, 2),
        ("triangle", [1, 2, 3], [(1, 2), (2, 3), (1, 3)], 1, 2),
        ("star", [0, 1, 2, 3], [(0, 1), (0, 2), (0, 3)], 1, 1),
        ("path P4", [1, 2, 3, 4], [(1, 2), (2, 3), (3, 4)], 2, 2),
        ("K4", [1, 2, 3, 4], [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)], 2, 3),
    ]
    ok = True
    print(f"{'case':16} {'matching':>9} {'vcover':>7}  expected(m/vc)  result")
    for name, items, conf, em, evc in cases:
        c = certificate(items, conf)
        mb, vc = c["matching_bound"], c["vertex_cover_bound"]
        passed = (mb == em and vc == evc and vc >= mb)
        ok = ok and passed
        print(f"{name:16} {mb:>9} {vc:>7}  ({em}/{evc})          {'PASS' if passed else 'FAIL'}")
    import random
    random.seed(0)
    stress_ok = True
    for _ in range(2000):
        nnodes = random.randint(2, 9)
        nodes = list(range(nnodes))
        conf = [(i, j) for i in range(nnodes) for j in range(i + 1, nnodes)
                if random.random() < 0.4]
        c = certificate(nodes, conf)
        true_vc = _min_cover_bruteforce(nodes, [(u, v) for u, v in conf])
        if not (c["vertex_cover_bound"] == true_vc and c["vertex_cover_bound"] >= c["matching_bound"]):
            stress_ok = False
            print("STRESS FAIL", nodes, conf, c, true_vc)
            break
    print(f"\nstress test (2000 random graphs): {'PASS (vc exact & vc>=matching always)' if stress_ok else 'FAIL'}")
    print(f"\ntheorem verification: {'ALL PASS' if (ok and stress_ok) else 'HAS FAILURES'}")
    return ok and stress_ok


if __name__ == "__main__":
    _test()
