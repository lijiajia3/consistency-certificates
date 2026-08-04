# -*- coding: utf-8 -*-
"""Minimal go/no-go pilot: JSON-mode extraction -> signature violations (hyperedge model)
-> gold-free lower bound = vertex-disjoint hyperedge count <= total errors
-> per-violation soundness check against gold."""
import json, os, re, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
KEY = open(os.path.expanduser("~/.siliconflow_key")).read().strip()
API = "https://api.siliconflow.cn/v1/chat/completions"
MODEL = os.environ.get("MODEL", "Qwen/Qwen2.5-32B-Instruct")
SIGS = json.load(open(os.path.join(ROOT, "data", "relations.json")))


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def doc_text(d):
    return " ".join(" ".join(s) for s in d["sents"])


def gold_maps(d):
    etype = {}
    names = []
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


def call_llm(text):
    rels = "\n".join(f"- {v}" for v in REL_NAME.values())
    prompt = (f"Extract a knowledge graph from the passage. Output JSON with keys "
              f'"entities" and "relations". Each entity: {{"name":str,"type":one of {TYPES}}}. '
              f'Each relation: {{"head":entity name,"relation":one of the names below,"tail":entity name}}.\n'
              f"Relation names:\n{rels}\nPassage:\n{text}")
    for _ in range(3):
        try:
            r = requests.post(API, headers={"Authorization": f"Bearer {KEY}"},
                              json={"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                                    "temperature": 0.0, "max_tokens": 3000,
                                    "response_format": {"type": "json_object"}}, timeout=150)
            return json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception:
            time.sleep(2)
    return {"entities": [], "relations": []}


def analyze(d, ext):
    gtype, grel = gold_maps(d)
    etype = {norm(e["name"]): e["type"] for e in ext.get("entities", [])
             if e.get("type") in TYPES and e.get("name")}
    hyperedges, viols = [], []
    for rel in ext.get("relations", []):
        rn, h, t = rel.get("relation"), norm(rel.get("head")), norm(rel.get("tail"))
        pid = NAME2PID.get(rn)
        if not pid or pid not in SIGS or h not in etype or t not in etype:
            continue
        allowed = [tuple(x) for x in SIGS[pid]["signatures"]]
        if (etype[h], etype[t]) in allowed:
            continue
        he = frozenset({f"E:{h}", f"E:{t}", f"R:{h}|{pid}|{t}"})
        hyperedges.append(he)
        gh, gt = gtype.get(h), gtype.get(t)
        h_wrong = gh is not None and etype[h] != gh
        t_wrong = gt is not None and etype[t] != gt
        rel_spurious = (h, pid, t) not in grel
        both_aligned = gh is not None and gt is not None
        gold_types_valid = both_aligned and (gh, gt) in allowed
        checkable = both_aligned
        sound = (h_wrong or t_wrong or rel_spurious)
        viols.append({"rel": rn, "h": h, "ht": etype[h], "gh": gh, "t": t, "tt": etype[t], "gt": gt,
                      "h_wrong": h_wrong, "t_wrong": t_wrong, "rel_spurious": rel_spurious,
                      "checkable": checkable, "gold_types_valid": gold_types_valid, "sound": sound})
    used, bound = set(), 0
    for he in hyperedges:
        if not (he & used):
            bound += 1; used |= he
    true_type_err = sum(1 for n, ty in etype.items() if n in gtype and gtype[n] != ty)
    llm_rels = set((norm(r.get("head")), NAME2PID.get(r.get("relation")), norm(r.get("tail")))
                   for r in ext.get("relations", []) if NAME2PID.get(r.get("relation")))
    true_rel_err = sum(1 for (h, p, t) in llm_rels
                       if p and h in gtype and t in gtype and (h, p, t) not in grel)
    true_err = true_type_err + true_rel_err
    return bound, viols, true_err, true_type_err, true_rel_err, len(etype)


def main():
    docs = json.load(open(os.path.join(ROOT, "data", "redocred_dev_15.json")))
    print(f"model={MODEL}  docs={len(docs)}\n")
    T = dict(bound=0, err=0, terr=0, rerr=0, v=0, checkable=0, sound_checkable=0, fired=0)
    for i, d in enumerate(docs):
        b, vs, te, tte, tre, ne = analyze(d, call_llm(doc_text(d)))
        chk = [v for v in vs if v["checkable"]]
        sc = sum(1 for v in chk if v["sound"])
        T["bound"] += b; T["err"] += te; T["terr"] += tte; T["rerr"] += tre
        T["v"] += len(vs); T["checkable"] += len(chk); T["sound_checkable"] += sc
        T["fired"] += (b > 0)
        ok = "OK" if b <= te else "THEOREM VIOLATED"
        print(f"doc{i:2} {d['title'][:30]:30} entities={ne:2} viol={len(vs):2}(chk={len(chk):2}/snd={sc:2}) "
              f"bound={b} true_err={te}(type={tte}+rel={tre}) {ok}")
        for v in vs[:2]:
            print(f"      - {v['h']}({v['ht']}/{v['gh']}) -{v['rel']}- {v['t']}({v['tt']}/{v['gt']}) "
                  f"[type_wrong={v['h_wrong'] or v['t_wrong']} spurious={v['rel_spurious']} sound={v['sound']}]")
    print(f"\n===== SUMMARY ({MODEL}, {len(docs)} docs) =====")
    print(f"firing rate: {T['fired']}/{len(docs)} documents")
    sr = T['sound_checkable'] / T['checkable'] if T['checkable'] else 0
    print(f"empirical soundness (checkable violations): {T['sound_checkable']}/{T['checkable']} = {sr:.0%}")
    print(f"theorem: bound sum {T['bound']} <= true error sum {T['err']} (type{T['terr']}+rel{T['rerr']}): "
          f"{'HOLDS' if T['bound'] <= T['err'] else 'VIOLATED'}; non-trivial = bound{T['bound']}>0={T['bound']>0}")
    print(f"\nGO/NO-GO -> firing={T['fired']}/{len(docs)}, soundness={sr:.0%}, "
          f"non-trivial bound={T['bound']>0}, theorem holds={T['bound']<=T['err']}")


if __name__ == "__main__":
    main()
