# -*- coding: utf-8 -*-
"""Reproduce the paper's main results on the declared 297-document common set.

Valid-output rates use the released cache entries. The Qwen2.5-7B cache contains
247 entries; the other model caches contain all 300. Certificate metrics for the
four usable extractors use only documents on which all four returned valid output,
exactly as reported in the manuscript.
"""
import json, os
from common import (find_violations, disjoint_lower_bound, validate_against_gold,
                    gold_error_records, TYPES, ROOT)

MODELS = ["Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-32B-Instruct",
          "Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3"]
USABLE_MODELS = MODELS[1:]
DOCS = json.load(open(os.path.join(ROOT, "data", "redocred_dev_300.json")))
SIGS = json.load(open(os.path.join(ROOT, "data", "relations.json")))


def safe(m): return m.replace("/", "__")


def load(m, i):
    p = os.path.join(ROOT, "result", "extractions", safe(m), f"{i:04d}.json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception:
        return None


def cached_indices(m):
    directory = os.path.join(ROOT, "result", "extractions", safe(m))
    return [
        index for index in range(len(DOCS))
        if os.path.isfile(os.path.join(directory, f"{index:04d}.json"))
    ]


def valid_output(ext):
    """Whether a cache entry contains a usable structured extraction."""
    if ext is None or ext.get("_error"):
        return False
    entities = [
        entity
        for entity in ext.get("entities", [])
        if isinstance(entity, dict)
        and entity.get("type") in TYPES
        and entity.get("name")
    ]
    return bool(entities or ext.get("relations"))


COMMON = [
    index
    for index in range(len(DOCS))
    if all(valid_output(load(model, index)) for model in USABLE_MODELS)
]


def true_errors(ext, d):
    """Gold-verifiable type and spurious-relation errors using cluster IDs."""
    records = gold_error_records(ext, d)["errors"]
    tterr = sum(record["category"] == "entity_type" for record in records)
    rerr = sum(record["category"] == "relation_spurious" for record in records)
    return tterr, rerr, [record["item"] for record in records]


def analyze_model(m, constraint, document_indices):
    rows = dict(valid=0, n=0, ents=0, viol=0, chk=0, sound=0, bound=0, terr=0, tterr=0, rerr=0,
                fired=0, thm_ok=0, thm_n=0, catchable=0, true_items=0)
    for i in document_indices:
        ext = load(m, i)
        rows["n"] += 1
        if not valid_output(ext):
            continue
        ents = [e for e in ext.get("entities", []) if isinstance(e, dict) and e.get("type") in TYPES and e.get("name")]
        rows["valid"] += 1
        rows["ents"] += len(ents)
        viols, etype = find_violations(ext, SIGS, constraint)
        viols, _ = validate_against_gold(viols, etype, DOCS[i])
        b = disjoint_lower_bound([v["he"] for v in viols])
        chk = [v for v in viols if v["checkable"]]
        checkable_bound = disjoint_lower_bound([v["he"] for v in chk])
        sc = sum(1 for v in chk if v["sound"])
        tterr, rerr, true_items = true_errors(ext, DOCS[i])
        te = tterr + rerr
        involved = set()
        for v in viols:
            involved |= {f"E:{v['h']}", f"E:{v['t']}", f"R:{v['h']}|{v['pid']}|{v['t']}"}
        catch = sum(1 for it in true_items if it in involved)
        rows["viol"] += len(viols); rows["chk"] += len(chk); rows["sound"] += sc
        rows["bound"] += b; rows["terr"] += te; rows["tterr"] += tterr; rows["rerr"] += rerr
        rows["fired"] += (b > 0)
        # Only the checkable sub-hypergraph can be compared with gold. Runtime
        # certificate bounds still use every violation and are reported above.
        rows["thm_n"] += 1; rows["thm_ok"] += (checkable_bound <= te)
        rows["catchable"] += catch; rows["true_items"] += len(true_items)
    return rows


def pct(a, b): return f"{a/b:.0%}" if b else "-"


def main():
    print(f"common evaluation set = {len(COMMON)} documents")
    if len(COMMON) != 297:
        raise SystemExit(f"Expected the reported 297-document common set, found {len(COMMON)}")
    summaries = {}
    for constraint in ["empirical", "definitional"]:
        print(f"\n{'='*96}\nconstraint family = {constraint}\n{'='*96}")
        print(f"{'model':26} {'validJSON':>9} {'ents/doc':>8} {'firing':>7} {'validation':>10} "
              f"{'bound_sum':>9} {'true_err':>8} {'theorem':>7} {'detectable':>9}")
        for m in MODELS:
            cached = cached_indices(m)
            full_valid = sum(valid_output(load(m, i)) for i in cached)
            indices = COMMON if m in USABLE_MODELS else cached
            r = analyze_model(m, constraint, indices)
            summaries[(constraint, m)] = r
            name = m.split("/")[-1]
            print(f"{name:26} {pct(full_valid, len(cached)):>9} {r['ents']/max(r['valid'],1):>8.1f} "
                  f"{pct(r['fired'], r['valid']):>7} {r['sound']}/{r['chk']}={pct(r['sound'], r['chk']):>4} "
                  f"{r['bound']:>9} {r['terr']:>8} {pct(r['thm_ok'], r['thm_n']):>7} "
                  f"{pct(r['catchable'], r['true_items']):>9}")

    empirical = sum(summaries[("empirical", model)]["chk"] for model in USABLE_MODELS)
    definitional = sum(summaries[("definitional", model)]["chk"] for model in USABLE_MODELS)
    empirical_sound = sum(summaries[("empirical", model)]["sound"] for model in USABLE_MODELS)
    definitional_sound = sum(summaries[("definitional", model)]["sound"] for model in USABLE_MODELS)
    total = empirical + definitional
    total_sound = empirical_sound + definitional_sound
    print("\nreported common-set audit")
    print(f"  empirical:    {empirical_sound}/{empirical}")
    print(f"  definitional: {definitional_sound}/{definitional}")
    print(f"  combined:     {total_sound}/{total} = {pct(total_sound, total)}")


if __name__ == "__main__":
    main()
