# -*- coding: utf-8 -*-
"""GLM-4-32B (cross-architecture control): valid-JSON / firing / soundness / theorem / detectable."""
import json, os
from common import (find_violations, disjoint_lower_bound, validate_against_gold,
                    gold_error_records, NAME2PID, norm, TYPES, ROOT)

DOCS = json.load(open(os.path.join(ROOT, "data", "redocred_dev_300.json")))
SIGS = json.load(open(os.path.join(ROOT, "data", "relations.json")))
M = "THUDM/GLM-4-32B-0414"
safe = lambda m: m.replace("/", "__")


def load(i):
    p = os.path.join(ROOT, "result", "extractions", safe(M), f"{i:04d}.json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception:
        return None


def true_items(ext, d):
    return [record["item"] for record in gold_error_records(ext, d)["errors"]]


n = valid = fire = chk = snd = det = dett = thm_ok = thm_tot = 0
relation_total = hyperedge_total = bound_total = bound_max = 0
for i in range(len(DOCS)):
    ext = load(i)
    if ext is None:
        continue
    n += 1
    if ext.get("_error"):
        continue
    ents = [e for e in ext.get("entities", []) if isinstance(e, dict) and e.get("type") in TYPES and e.get("name")]
    if not ents and not ext.get("relations"):
        continue
    valid += 1
    relation_total += len({
        (norm(relation.get("head")), NAME2PID.get(relation.get("relation")), norm(relation.get("tail")))
        for relation in ext.get("relations", [])
        if isinstance(relation, dict) and NAME2PID.get(relation.get("relation"))
    })
    vs, et = find_violations(ext, SIGS, "empirical"); vs, _ = validate_against_gold(vs, et, DOCS[i])
    hyperedge_total += len(vs)
    b = disjoint_lower_bound([v["he"] for v in vs]); fire += (b > 0)
    bound_total += b; bound_max = max(bound_max, b)
    c = [v for v in vs if v["checkable"]]; chk += len(c); snd += sum(1 for v in c if v["sound"])
    checkable_bound = disjoint_lower_bound([v["he"] for v in c])
    ti = true_items(ext, DOCS[i]); inv = set()
    for v in vs:
        inv |= {f"E:{v['h']}", f"E:{v['t']}", f"R:{v['h']}|{v['pid']}|{v['t']}"}
    det += sum(1 for it in ti if it in inv); dett += len(ti)
    thm_tot += 1; thm_ok += (checkable_bound <= len(ti))

print(f"GLM-4-32B-0414  files={n}")
print(f"  validJSON = {valid}/{n} = {100*valid/n:.1f}%")
print(f"  firing    = {fire}/{valid} = {100*fire/valid:.1f}%  (of valid)")
print(f"  soundness = {snd}/{chk} = {100*snd/chk if chk else 0:.1f}%")
print(f"  theorem   = {thm_ok}/{thm_tot} docs hold")
print(f"  detectable= {det}/{dett} = {100*det/dett if dett else 0:.1f}%")
print(f"  relations = {relation_total}")
print(f"  hyperedges= {hyperedge_total}")
print(f"  bound     = {bound_total} total, {bound_total/valid if valid else 0:.2f} mean, {bound_max} max")
print(f"  goldErrors= {dett}")
