# -*- coding: utf-8 -*-
"""共享:关系/类型常量、prompt、违反检测(超边)、免金标下界、金标核验。"""
import json, os, re

REL_NAME = {
    "P131": "located in the administrative territorial entity", "P17": "country",
    "P27": "country of citizenship", "P150": "contains administrative territorial entity",
    "P800": "notable work", "P527": "has part", "P361": "part of", "P175": "performer",
    "P577": "publication date", "P1344": "participant in", "P710": "participant",
    "P463": "member of", "P1001": "applies to jurisdiction", "P495": "country of origin",
    "P569": "date of birth", "P161": "cast member", "P571": "inception (date founded/created)",
    "P264": "record label",
}
NAME2PID = {v: k for k, v in REL_NAME.items()}
TYPES = ["PER", "ORG", "LOC", "TIME", "NUM", "MISC"]

# 定义即硬的类型签名(逻辑必然, 不靠经验): 用于消假阳的稳健变体
DEFINITIONAL = {
    "P569": {("PER", "TIME")},          # 出生日期: 人→时间
    "P577": {("MISC", "TIME"), ("ORG", "TIME"), ("LOC", "TIME")},  # 发表日期: *→时间
    "P571": {("ORG", "TIME"), ("MISC", "TIME"), ("LOC", "TIME")},  # 成立: *→时间
    "P27": {("PER", "LOC")},            # 国籍: 人→地
    "P19": {("PER", "LOC")}, "P20": {("PER", "LOC")},
}


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def doc_text(d):
    return " ".join(" ".join(s) for s in d["sents"])


def build_prompt(text):
    rels = "\n".join(f"- {v}" for v in REL_NAME.values())
    return (f"Extract a knowledge graph from the passage. Output JSON with keys "
            f'"entities" and "relations". Each entity: {{"name":str,"type":one of {TYPES}}}. '
            f'Each relation: {{"head":entity name,"relation":one of the names below,"tail":entity name}}.\n'
            f"Relation names:\n{rels}\nPassage:\n{text}")


def gold_maps(d):
    """归一名->金标类型; 金标关系集合 (h_norm, pid, t_norm)。"""
    etype, names = {}, []
    for e in d["vertexSet"]:
        t = e[0]["type"]; ns = set()
        for m in e:
            etype.setdefault(norm(m["name"]), t); ns.add(norm(m["name"]))
        names.append(ns)
    rel = set()
    for l in d.get("labels", []):
        for hn in names[l["h"]]:
            for tn in names[l["t"]]:
                rel.add((hn, l["r"], tn))
    return etype, rel


def find_violations(ext, sigs, constraint="empirical"):
    """返回违反列表: 每条 {pid, h, t, ht, tt, hyperedge}。constraint: empirical|definitional。"""
    etype = {norm(e["name"]): e["type"] for e in ext.get("entities", [])
             if isinstance(e, dict) and e.get("type") in TYPES and e.get("name")}
    out = []
    for rel in ext.get("relations", []):
        if not isinstance(rel, dict):
            continue
        pid = NAME2PID.get(rel.get("relation"))
        h, t = norm(rel.get("head")), norm(rel.get("tail"))
        if not pid or h not in etype or t not in etype:
            continue
        if constraint == "definitional":
            if pid not in DEFINITIONAL:
                continue
            allowed = DEFINITIONAL[pid]
        else:
            if pid not in sigs:
                continue
            allowed = set(tuple(x) for x in sigs[pid]["signatures"])
        if (etype[h], etype[t]) in allowed:
            continue
        out.append({"pid": pid, "h": h, "t": t, "ht": etype[h], "tt": etype[t],
                    "he": frozenset({f"E:{h}", f"E:{t}", f"R:{h}|{pid}|{t}"})})
    return out, etype


FUNCTIONAL = {"P569", "P570", "P571", "P577", "P19", "P20"}  # 单值关系: 每个 head 至多一个值


def find_functional_violations(ext):
    """功能关系一致性: 同一 head 对单值关系抽出 >=2 个不同 tail => 冲突(至少一错)。"""
    from collections import defaultdict
    hr = defaultdict(lambda: defaultdict(set))
    for rel in ext.get("relations", []):
        if not isinstance(rel, dict):
            continue
        pid = NAME2PID.get(rel.get("relation"))
        if pid in FUNCTIONAL and rel.get("head") and rel.get("tail"):
            hr[norm(rel.get("head"))][pid].add(norm(rel.get("tail")))
    out = []
    for h, rels in hr.items():
        for pid, tails in rels.items():
            tl = sorted(tails)
            for a in range(len(tl)):
                for b in range(a + 1, len(tl)):
                    out.append({"pid": pid, "h": h, "t": tl[a], "t2": tl[b],
                                "he": frozenset({f"R:{h}|{pid}|{tl[a]}", f"R:{h}|{pid}|{tl[b]}"})})
    return out


def disjoint_lower_bound(hyperedges):
    """贪心互不相交超边数 = 有效错误下界(<= 真错误数)。"""
    used, b = set(), 0
    for he in hyperedges:
        if not (he & used):
            b += 1; used |= he
    return b


def fuzzy_gtype(name, gtype):
    """归一名->金标类型, 先精确后包含匹配(容忍 'the X'/'X' 这类归一差异)。无匹配返回 None。"""
    n = name if isinstance(name, str) else norm(name)
    if n in gtype:
        return gtype[n]
    if len(n) >= 4:
        for gn, t in gtype.items():
            if len(gn) >= 4 and (n in gn or gn in n):
                return t
    return None


def validate_against_gold(viols, etype, d):
    """逐违反核验: h_wrong/t_wrong/rel_spurious/checkable/sound; 并统计真错误数。"""
    gtype, grel = gold_maps(d)
    for v in viols:
        gh, gt = fuzzy_gtype(v["h"], gtype), fuzzy_gtype(v["t"], gtype)
        v["gh"], v["gt"] = gh, gt
        v["h_wrong"] = gh is not None and v["ht"] != gh
        v["t_wrong"] = gt is not None and v["tt"] != gt
        v["rel_spurious"] = (v["h"], v["pid"], v["t"]) not in grel
        v["checkable"] = gh is not None and gt is not None
        v["sound"] = bool(v["h_wrong"] or v["t_wrong"] or v["rel_spurious"])
    true_type_err = sum(1 for n, ty in etype.items() if n in gtype and gtype[n] != ty)
    return viols, true_type_err
