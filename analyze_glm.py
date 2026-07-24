# -*- coding: utf-8 -*-
"""GLM-4-32B(非 Qwen 跨架构对照)的证书指标: validJSON/firing/soundness/定理/可检测类。"""
import json, os
from common import (find_violations, disjoint_lower_bound, validate_against_gold,
                    gold_maps, TYPES, norm, NAME2PID, fuzzy_gtype)

DOCS = json.load(open("redocred_dev_300.json"))
SIGS = json.load(open("relations.json"))
M = "THUDM/GLM-4-32B-0414"
safe = lambda m: m.replace("/", "__")


def load(i):
    p = f"extractions/{safe(M)}/{i:04d}.json"
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception:
        return None


def true_items(ext, d):
    gt, gr = gold_maps(d)
    et = {norm(e["name"]): e["type"] for e in ext.get("entities", []) if isinstance(e, dict) and e.get("type") in TYPES and e.get("name")}
    it = [f"E:{n}" for n, ty in et.items() if fuzzy_gtype(n, gt) != ty]
    llm = set((norm(r.get("head")), NAME2PID.get(r.get("relation")), norm(r.get("tail"))) for r in ext.get("relations", []) if isinstance(r, dict) and NAME2PID.get(r.get("relation")))
    it += [f"R:{h}|{p}|{t}" for (h, p, t) in llm if p and fuzzy_gtype(h, gt) and fuzzy_gtype(t, gt) and (h, p, t) not in gr]
    return it


n = valid = fire = chk = snd = det = dett = thm_ok = thm_tot = 0
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
    vs, et = find_violations(ext, SIGS, "empirical"); vs, _ = validate_against_gold(vs, et, DOCS[i])
    b = disjoint_lower_bound([v["he"] for v in vs]); fire += (b > 0)
    c = [v for v in vs if v["checkable"]]; chk += len(c); snd += sum(1 for v in c if v["sound"])
    ti = true_items(ext, DOCS[i]); inv = set()
    for v in vs:
        inv |= {f"E:{v['h']}", f"E:{v['t']}", f"R:{v['h']}|{v['pid']}|{v['t']}"}
    det += sum(1 for it in ti if it in inv); dett += len(ti)
    thm_tot += 1; thm_ok += (b <= len(ti))

print(f"GLM-4-32B-0414  files={n}")
print(f"  validJSON = {valid}/{n} = {100*valid/n:.0f}%")
print(f"  firing    = {100*fire/valid:.0f}%  (of valid)")
print(f"  soundness = {snd}/{chk} = {100*snd/chk if chk else 0:.1f}%")
print(f"  theorem   = {thm_ok}/{thm_tot} docs hold")
print(f"  detectable= {det}/{dett} = {100*det/dett if dett else 0:.0f}%")
