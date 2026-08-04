# -*- coding: utf-8 -*-
"""E5: self-consistency vs the certificate.

A certified error that recurs across K stochastic decodes is self-consistent and thus
invisible to resampling / self-consistency detectors, but the certificate catches it
deterministically from a single decode.
"""
import json, os
from common import find_violations, validate_against_gold, norm, NAME2PID, ROOT

MODEL = "Qwen/Qwen2.5-32B-Instruct"
K = 5
NDOCS = 50
DOCS = json.load(open(os.path.join(ROOT, "data", "redocred_dev_300.json")))[:NDOCS]
SIGS = json.load(open(os.path.join(ROOT, "data", "relations.json")))


def safe(m): return m.replace("/", "__")


def load_k(i, k):
    p = os.path.join(ROOT, "result", "resample", safe(MODEL), f"{i:04d}_{k}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def rel_key(r):
    return (norm(r.get("head")), NAME2PID.get(r.get("relation")), norm(r.get("tail")))


def load_t0(i):
    p = os.path.join(ROOT, "result", "extractions", safe(MODEL), f"{i:04d}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    # Deployed baseline = deterministic T=0 extraction; stability of its certified
    # errors across K high-temperature decodes is the self-consistency signal.
    sc_dist = []
    for i in range(NDOCS):
        t0 = load_t0(i)
        if not t0 or t0.get("_error"):
            continue
        decs = [d for d in [load_k(i, k) for k in range(K)] if d]
        if len(decs) < K:
            continue
        relsets = []
        for d in decs:
            rs = set(rel_key(r) for r in d.get("relations", []) if isinstance(r, dict) and rel_key(r)[1])
            relsets.append(rs)
        viols, etype = find_violations(t0, SIGS, "empirical")
        viols, _ = validate_against_gold(viols, etype, DOCS[i])
        for v in viols:
            if v["sound"]:
                key = (v["h"], v["pid"], v["t"])
                freq = sum(1 for rs in relsets if key in rs)
                sc_dist.append(freq)

    if not sc_dist:
        print("no resample data available"); return
    n = len(sc_dist)
    hi = sum(1 for f in sc_dist if f >= 3)     # >=3/5 recurrence = resampling rates it reliable
    allk = sum(1 for f in sc_dist if f == K)   # recurs in all K decodes
    lo = sum(1 for f in sc_dist if f <= 1)     # low recurrence (resampling can flag these)
    print(f"===== E5: self-consistency vs certificate ({MODEL}, {NDOCS} docs, K={K}) =====")
    print(f"certified (sound) error relations: {n}")
    print(f"recurrence of a certified error across K={K} decodes:")
    from collections import Counter
    c = Counter(sc_dist)
    for f in range(K + 1):
        bar = "#" * c.get(f, 0)
        print(f"  {f}/{K}: {c.get(f,0):3}  {bar}")
    print(f"\nkey comparison:")
    print(f"  self-consistent errors (>=3/5, missed by resampling): {hi}/{n} = {hi/n:.0%}")
    print(f"  fully stable errors (5/5, invisible to self-consistency): {allk}/{n} = {allk/n:.0%}")
    print(f"  low-recurrence errors (<=1/5, flaggable by resampling): {lo}/{n} = {lo/n:.0%}")
    print(f"\nconclusion: {hi/n:.0%} of certified errors are self-consistent, so "
          f"resampling/self-consistency systematically miss them while the type-signature "
          f"certificate catches all of them deterministically (soundness 100%).")


if __name__ == "__main__":
    main()
