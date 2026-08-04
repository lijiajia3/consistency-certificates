# -*- coding: utf-8 -*-
"""Corpus-independent (schema-only) signature ablation.

Conservative (head-type, tail-type) allow sets are hand-built for all 18 relations from
Wikidata property semantics, with no reference to Re-DocRED. This shows soundness is not
induced by same-corpus construction and that a fully gold-free variant exists.
"""
import json, os
from itertools import product
from common import find_violations, disjoint_lower_bound, validate_against_gold, TYPES, ROOT

DOCS = json.load(open(os.path.join(ROOT, "data", "redocred_dev_300.json")))
EMP = json.load(open(os.path.join(ROOT, "data", "relations.json")))
MODELS = ["Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-32B-Instruct",
          "Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3"]
safe = lambda m: m.replace("/", "__")

# Schema-only allow sets: {pid: (allowed head types, allowed tail types)}, conservative.
SCHEMA_HT = {
    "P131": ({"LOC", "ORG", "MISC", "PER"}, {"LOC"}),          # located in -> place
    "P17":  ({"LOC", "ORG", "MISC", "PER"}, {"LOC"}),          # country
    "P27":  ({"PER"}, {"LOC"}),                                  # country of citizenship
    "P150": ({"LOC"}, {"LOC"}),                                  # contains admin territory
    "P800": ({"PER", "ORG"}, {"MISC", "ORG"}),                  # notable work
    "P527": ({"MISC", "ORG", "LOC"}, {"MISC", "ORG", "LOC", "PER"}),  # has part
    "P361": ({"MISC", "ORG", "LOC", "PER"}, {"MISC", "ORG", "LOC"}),  # part of
    "P175": ({"MISC"}, {"PER", "ORG"}),                         # performer: work -> person/group
    "P577": ({"MISC", "ORG"}, {"TIME"}),                       # publication date
    "P1344": ({"PER", "ORG"}, {"MISC", "ORG"}),                # participant in -> event
    "P710": ({"MISC", "ORG"}, {"PER", "ORG"}),                 # participant: event -> person/group
    "P463": ({"PER", "ORG"}, {"ORG"}),                         # member of
    "P1001": ({"MISC", "ORG", "LOC"}, {"LOC", "ORG"}),         # applies to jurisdiction
    "P495": ({"MISC", "ORG", "PER"}, {"LOC"}),                 # country of origin
    "P569": ({"PER"}, {"TIME"}),                                # date of birth
    "P161": ({"MISC"}, {"PER"}),                                # cast member
    "P571": ({"ORG", "MISC", "LOC"}, {"TIME"}),               # inception
    "P264": ({"PER", "ORG", "MISC"}, {"ORG"}),                # record label -> org
}
SCHEMA = {pid: {"signatures": [list(p) for p in product(hs, ts)]} for pid, (hs, ts) in SCHEMA_HT.items()}


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


def run(sigs):
    chk = snd = fire = tot = 0
    for m in MODELS:
        for i in range(len(DOCS)):
            ext = load(m, i)
            if not valid(ext):
                continue
            tot += 1
            vs, et = find_violations(ext, sigs, "empirical")
            vs, _ = validate_against_gold(vs, et, DOCS[i])
            c = [v for v in vs if v["checkable"]]
            chk += len(c); snd += sum(1 for v in c if v["sound"])
            fire += (disjoint_lower_bound([v["he"] for v in vs]) > 0)
    return chk, snd, fire, tot


sc, ss, sf, st = run(SCHEMA)
ec, es, ef, et_ = run(EMP)
print("================  SCHEMA-ONLY (zero-corpus) vs EMPIRICAL SIGNATURES  ================")
print(f"[schema-only (independent)]  checkable={sc}  sound={ss}  soundness={100*ss/sc:.1f}%  firing={100*sf/st:.0f}%")
print(f"[empirical (same corpus)]    checkable={ec}  sound={es}  soundness={100*es/ec:.1f}%  firing={100*ef/et_:.0f}%")
print("=============================================================================")
print("Schema signatures are hand-built from Wikidata semantics with no Re-DocRED statistics.")
print("If their soundness stays high, soundness is not an artifact of same-corpus construction.")
