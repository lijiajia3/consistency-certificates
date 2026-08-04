# -*- coding: utf-8 -*-
"""E6 triage: rank correlation between per-document bound and true error count,
plus top-10 recall. Does the certificate order documents for review by error load?"""
import json, os
import numpy as np
from common import find_violations, disjoint_lower_bound, validate_against_gold, gold_maps, TYPES, norm, NAME2PID, fuzzy_gtype, ROOT

MODELS = ["Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-32B-Instruct", "Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3"]
DOCS = json.load(open(os.path.join(ROOT, "data", "redocred_dev_300.json")))
SIGS = json.load(open(os.path.join(ROOT, "data", "relations.json")))


def safe(m): return m.replace("/", "__")


def true_err(ext, d):
    gtype, grel = gold_maps(d)
    etype = {norm(e["name"]): e["type"] for e in ext.get("entities", []) if isinstance(e, dict) and e.get("type") in TYPES and e.get("name")}
    te = sum(1 for n, ty in etype.items() if fuzzy_gtype(n, gtype) != ty)
    llm = set((norm(r.get("head")), NAME2PID.get(r.get("relation")), norm(r.get("tail")))
              for r in ext.get("relations", []) if isinstance(r, dict) and NAME2PID.get(r.get("relation")))
    te += sum(1 for (h, p, t) in llm if p and fuzzy_gtype(h, gtype) and fuzzy_gtype(t, gtype) and (h, p, t) not in grel)
    return te


def spearman(x, y):
    x, y = np.array(x, float), np.array(y, float)
    rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


print(f"{'model':26} {'Spearman(bound,err)':>18} {'top10 bound / err coverage':>26}")
for m in MODELS:
    bounds, errs = [], []
    for i in range(len(DOCS)):
        p = os.path.join(ROOT, "result", "extractions", safe(m), f"{i:04d}.json")
        if not os.path.exists(p):
            continue
        try:
            ext = json.load(open(p))
        except Exception:
            continue
        if ext.get("_error"):
            continue
        viols, etype = find_violations(ext, SIGS, "empirical")
        viols, _ = validate_against_gold(viols, etype, DOCS[i])
        b = disjoint_lower_bound([v["he"] for v in viols])
        bounds.append(b); errs.append(true_err(ext, DOCS[i]))
    if len(bounds) < 5:
        print(f"{m.split('/')[-1]:26} (insufficient data)"); continue
    rho = spearman(bounds, errs)
    order = np.argsort(bounds)[::-1]
    top = order[:10]
    cov = sum(errs[j] for j in top) / max(sum(errs), 1)
    print(f"{m.split('/')[-1]:26} {rho:>18.3f} {sum(bounds[j] for j in top)}/{cov:.0%} of true errors in top-10 docs")
