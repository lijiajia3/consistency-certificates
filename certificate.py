# -*- coding: utf-8 -*-
"""Consistency Certificates — 免金标文档级错误下界。
核心定理(Thm 1):错误项集合是冲突图的顶点覆盖 ⟹ #err ≥ |最小覆盖| ≥ 最大匹配 m(G)。
matching 是多项式时间证书;min-vertex-cover 更紧(小图可精确)。"""
import itertools
import networkx as nx


def build_conflict_graph(items, conflicts):
    """items: 可哈希项 id 列表;conflicts: (i,j) 对,表示 i,j 不能同时正确(硬约束被违反)。"""
    G = nx.Graph()
    G.add_nodes_from(items)
    for i, j in conflicts:
        if i != j:
            G.add_edge(i, j)
    return G


def matching_lower_bound(G):
    """m(G) = 最大基数匹配大小 —— 多项式时间、恒有效的 #err 下界(弱对偶)。"""
    M = nx.max_weight_matching(G, maxcardinality=True)
    return len(M)


def min_vertex_cover_exact(G):
    """最小顶点覆盖(精确,仅用于小图):在有冲突边的诱导子图上暴力/ILP。
    = 更紧的 #err 下界。NP-hard,但违反子图通常很小。"""
    active = [n for n in G.nodes if G.degree(n) > 0]
    E = list(G.edges())
    if not E:
        return 0
    # 按连通分量分治,降规模
    total = 0
    for comp in nx.connected_components(G.subgraph(active)):
        comp = list(comp)
        Ec = [(u, v) for u, v in E if u in comp and v in comp]
        # 暴力找最小覆盖(comp 小)
        k = _min_cover_bruteforce(comp, Ec)
        total += k
    return total


def _min_cover_bruteforce(nodes, edges):
    n = len(nodes)
    if n > 20:  # 兜底:大分量用匹配下界(仍有效,只是不精确)
        H = nx.Graph(); H.add_nodes_from(nodes); H.add_edges_from(edges)
        return len(nx.max_weight_matching(H, maxcardinality=True))
    idx = {u: b for b, u in enumerate(nodes)}
    for k in range(0, n + 1):
        for cover in itertools.combinations(nodes, k):
            cs = set(cover)
            if all(u in cs or v in cs for u, v in edges):
                return k
    return n


def certificate(items, conflicts):
    """返回 {matching_bound, vertex_cover_bound, n_conflicts, conflict_nodes}。
    保证:真错误数 ≥ vertex_cover_bound ≥ matching_bound(免金标)。"""
    G = build_conflict_graph(items, conflicts)
    mb = matching_lower_bound(G)
    vc = min_vertex_cover_exact(G)
    return {
        "matching_bound": mb,
        "vertex_cover_bound": vc,
        "n_conflict_edges": G.number_of_edges(),
        "conflict_nodes": sorted([n for n in G.nodes if G.degree(n) > 0], key=str),
    }


# ============================ 单元测试(定理验证) ============================
def _test():
    cases = [
        # (名称, items, conflicts, 期望 matching, 期望 vertex_cover)
        ("空图", [1, 2, 3], [], 0, 0),
        ("单边", [1, 2], [(1, 2)], 1, 1),
        ("两不交边", [1, 2, 3, 4], [(1, 2), (3, 4)], 2, 2),
        ("三角形", [1, 2, 3], [(1, 2), (2, 3), (1, 3)], 1, 2),  # 匹配1松, 覆盖2紧
        ("星形", [0, 1, 2, 3], [(0, 1), (0, 2), (0, 3)], 1, 1),
        ("路径P4", [1, 2, 3, 4], [(1, 2), (2, 3), (3, 4)], 2, 2),
        ("K4", [1, 2, 3, 4], [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)], 2, 3),
    ]
    ok = True
    print(f"{'case':10} {'matching':>9} {'vcover':>7}  期望(m/vc)  结果")
    for name, items, conf, em, evc in cases:
        c = certificate(items, conf)
        mb, vc = c["matching_bound"], c["vertex_cover_bound"]
        passed = (mb == em and vc == evc and vc >= mb)  # 关键: vc>=mb 恒成立
        ok = ok and passed
        print(f"{name:10} {mb:>9} {vc:>7}   ({em}/{evc})    {'✓' if passed else '✗ FAIL'}")
    # 随机压力测试: 恒有 真最小覆盖 >= 匹配, 且我们的 vc == 真最小覆盖
    import random
    random.seed(0)
    stress_ok = True
    for _ in range(2000):
        nnodes = random.randint(2, 9)
        nodes = list(range(nnodes))
        conf = []
        for i in range(nnodes):
            for j in range(i + 1, nnodes):
                if random.random() < 0.4:
                    conf.append((i, j))
        c = certificate(nodes, conf)
        # 独立核验最小覆盖(暴力)
        true_vc = _min_cover_bruteforce(nodes, [(u, v) for u, v in conf])
        if not (c["vertex_cover_bound"] == true_vc and c["vertex_cover_bound"] >= c["matching_bound"]):
            stress_ok = False
            print("STRESS FAIL", nodes, conf, c, true_vc)
            break
    print(f"\n随机压力测试(2000 图): {'✓ 全过(vc精确 & vc>=matching 恒成立)' if stress_ok else '✗ FAIL'}")
    print(f"\n定理验证总结: {'✓ 全部通过' if (ok and stress_ok) else '✗ 有失败'}")
    return ok and stress_ok


if __name__ == "__main__":
    _test()
