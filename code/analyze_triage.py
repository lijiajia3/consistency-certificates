# -*- coding: utf-8 -*-
"""E6 triage: rank correlation between per-document bound and true error count,
plus top-10 recall. Does the certificate order documents for review by error load?"""
import json, os
import numpy as np
from scipy.stats import spearmanr
from common import find_violations, disjoint_lower_bound, validate_against_gold, gold_error_records, TYPES, NAME2PID, ROOT

MODELS = ["Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-32B-Instruct", "Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3"]
DOCS = json.load(open(os.path.join(ROOT, "data", "redocred_dev_300.json")))
SIGS = json.load(open(os.path.join(ROOT, "data", "relations.json")))


def safe(m): return m.replace("/", "__")


def true_err(ext, d):
    return len(gold_error_records(ext, d)["errors"])


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
    rho = float(spearmanr(bounds, errs).statistic)
    order = np.argsort(bounds)[::-1]
    top = order[:10]
    cov = sum(errs[j] for j in top) / max(sum(errs), 1)
    print(f"{m.split('/')[-1]:26} {rho:>18.3f} {sum(bounds[j] for j in top)}/{cov:.0%} of true errors in top-10 docs")
