# -*- coding: utf-8 -*-
"""Hold-out signature ablation.

Empirical signatures are built from one disjoint fold's gold and evaluated on the
other fold, so a test document's gold never contributes to the signatures auditing it.
This directly answers the circular-construction objection to the zero-false-positive claim.
"""
import json, os
from collections import defaultdict
from common import find_violations, validate_against_gold, NAME2PID, TYPES, ROOT

DOCS = json.load(open(os.path.join(ROOT, "data", "redocred_dev_300.json")))
SIGS_FULL = json.load(open(os.path.join(ROOT, "data", "relations.json")))
PIDSET = set(SIGS_FULL.keys())  # 18 relations
MODELS = ["Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-32B-Instruct",
          "Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3"]
safe = lambda m: m.replace("/", "__")


def load(m, i):
    p = os.path.join(ROOT, "result", "extractions", safe(m), f"{i:04d}.json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception:
        return None


def valid(ext):
    if ext is None or ext.get("_error"):
        return False
    ents = [e for e in ext.get("entities", []) if isinstance(e, dict) and e.get("type") in TYPES and e.get("name")]
    return bool(ents or ext.get("relations"))


def derive_sigs(doc_idx):
    """Empirical signatures from the gold of the given documents."""
    sig = defaultdict(set)
    for i in doc_idx:
        d = DOCS[i]
        vt = [e[0]["type"] for e in d["vertexSet"]]
        for l in d.get("labels", []):
            if l["r"] in PIDSET:
                sig[l["r"]].add((vt[l["h"]], vt[l["t"]]))
    return {r: {"signatures": [list(x) for x in pairs]} for r, pairs in sig.items()}


N = len(DOCS)
fold0 = [i for i in range(N) if i % 2 == 0]
fold1 = [i for i in range(N) if i % 2 == 1]
SIG0 = derive_sigs(fold0)   # built on fold0, tested on fold1
SIG1 = derive_sigs(fold1)   # built on fold1, tested on fold0
print(f"folds: {len(fold0)} / {len(fold1)} docs; "
      f"sig relations covered: fold0={len(SIG0)}, fold1={len(SIG1)}")


def run(sig_for_test, test_idx):
    chk = snd = fire_docs = tot_docs = 0
    for m in MODELS:
        for i in test_idx:
            ext = load(m, i)
            if not valid(ext):
                continue
            tot_docs += 1
            vs, et = find_violations(ext, sig_for_test, "empirical")
            vs, _ = validate_against_gold(vs, et, DOCS[i])
            c = [v for v in vs if v["checkable"]]
            chk += len(c); snd += sum(1 for v in c if v["sound"])
            fire_docs += (len(vs) > 0)
    return chk, snd, fire_docs, tot_docs


c1, s1, f1, t1 = run(SIG0, fold1)
c0, s0, f0, t0 = run(SIG1, fold0)
CHK, SND, FIRE, TOT = c1 + c0, s1 + s0, f1 + f0, t1 + t0

# In-sample baseline: full-corpus signatures on the same documents.
bc = bs = bf = 0
for m in MODELS:
    for i in range(N):
        ext = load(m, i)
        if not valid(ext):
            continue
        vs, et = find_violations(ext, SIGS_FULL, "empirical")
        vs, _ = validate_against_gold(vs, et, DOCS[i])
        c = [v for v in vs if v["checkable"]]
        bc += len(c); bs += sum(1 for v in c if v["sound"]); bf += (len(vs) > 0)

print("\n================  HOLD-OUT SIGNATURE ABLATION  ================")
print(f"[hold-out (disjoint)]  checkable={CHK}  sound={SND}  "
      f"soundness={100*SND/CHK:.1f}%  firing-docs={FIRE}/{TOT}={100*FIRE/TOT:.0f}%")
print(f"[in-sample (full corpus)]  checkable={bc}  sound={bs}  "
      f"soundness={100*bs/bc:.1f}%  firing-docs={bf}")
print("================================================================")
print("If hold-out soundness stays ~100%, zero false positives is not an artifact of")
print("signature construction: the test documents' gold never shapes their own signatures.")
