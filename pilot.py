# -*- coding: utf-8 -*-
"""最小 go/no-go(修正版):强模型 JSON-mode 抽取 → 关系类型签名违反(超边模型)
→ 免金标下界=互不相交超边数 ≤ 总错误数 → 对齐金标逐违反核验 soundness。"""
import json, os, re, time
import requests

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
SIGS = json.load(open("relations.json"))


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def doc_text(d):
    return " ".join(" ".join(s) for s in d["sents"])


def gold_maps(d):
    etype = {}
    names = []  # per entity: set of norm names
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
        # —— 违反:超边 {E:h, E:t, R:hrt} ——
        he = frozenset({f"E:{h}", f"E:{t}", f"R:{h}|{pid}|{t}"})
        hyperedges.append(he)
        # —— 对齐金标核验该违反是否 sound ——
        gh, gt = gtype.get(h), gtype.get(t)
        h_wrong = gh is not None and etype[h] != gh
        t_wrong = gt is not None and etype[t] != gt
        rel_spurious = (h, pid, t) not in grel
        both_aligned = gh is not None and gt is not None
        gold_types_valid = both_aligned and (gh, gt) in allowed
        # 可核验 = 两端都对齐(否则真值未知)
        checkable = both_aligned
        # sound(在可核验前提下)= LLM 类型错 或 关系是金标里没有的(伪关系)
        sound = (h_wrong or t_wrong or rel_spurious)
        viols.append({"rel": rn, "h": h, "ht": etype[h], "gh": gh, "t": t, "tt": etype[t], "gt": gt,
                      "h_wrong": h_wrong, "t_wrong": t_wrong, "rel_spurious": rel_spurious,
                      "checkable": checkable, "gold_types_valid": gold_types_valid, "sound": sound})
    # —— 下界:贪心取互不相交超边(有效下界 ≤ 总错误数)——
    used, bound = set(), 0
    for he in hyperedges:
        if not (he & used):
            bound += 1; used |= he
    # —— 真错误数(可对齐部分):错类型实体 + 伪关系 ——
    true_type_err = sum(1 for n, ty in etype.items() if n in gtype and gtype[n] != ty)
    llm_rels = set((norm(r.get("head")), NAME2PID.get(r.get("relation")), norm(r.get("tail")))
                   for r in ext.get("relations", []) if NAME2PID.get(r.get("relation")))
    true_rel_err = sum(1 for (h, p, t) in llm_rels
                       if p and h in gtype and t in gtype and (h, p, t) not in grel)
    true_err = true_type_err + true_rel_err
    return bound, viols, true_err, true_type_err, true_rel_err, len(etype)


def main():
    docs = json.load(open("redocred_dev_15.json"))
    print(f"model={MODEL}  docs={len(docs)}\n")
    T = dict(bound=0, err=0, terr=0, rerr=0, v=0, checkable=0, sound_checkable=0, fired=0)
    for i, d in enumerate(docs):
        b, vs, te, tte, tre, ne = analyze(d, call_llm(doc_text(d)))
        chk = [v for v in vs if v["checkable"]]
        sc = sum(1 for v in chk if v["sound"])
        T["bound"] += b; T["err"] += te; T["terr"] += tte; T["rerr"] += tre
        T["v"] += len(vs); T["checkable"] += len(chk); T["sound_checkable"] += sc
        T["fired"] += (b > 0)
        ok = "✓" if b <= te else "✗违反定理!"
        print(f"doc{i:2} {d['title'][:30]:30} 实体{ne:2} 违反{len(vs):2}(可核{len(chk):2}/sound{sc:2}) 下界={b} 真错={te}(类型{tte}+伪关系{tre}) {ok}")
        for v in vs[:2]:
            print(f"      · {v['h']}({v['ht']}/{v['gh']}) -{v['rel']}- {v['t']}({v['tt']}/{v['gt']}) "
                  f"[类型错={v['h_wrong'] or v['t_wrong']} 伪关系={v['rel_spurious']} sound={v['sound']}]")
    print(f"\n===== 汇总 (Qwen2.5-32B, {len(docs)} 篇) =====")
    print(f"① 触发率: {T['fired']}/{len(docs)} 篇触发证书")
    sr = T['sound_checkable'] / T['checkable'] if T['checkable'] else 0
    print(f"② 经验 soundness(可核验违反): {T['sound_checkable']}/{T['checkable']} = {sr:.0%}")
    print(f"③ 定理: 下界合计 {T['bound']} ≤ 真错合计 {T['err']} (类型{T['terr']}+伪关系{T['rerr']}) : "
          f"{'✓ 成立' if T['bound'] <= T['err'] else '✗ 违反!'};非平凡=下界{T['bound']}>0={T['bound']>0}")
    print(f"\nGO/NO-GO ⇒ 触发率{T['fired']}/{len(docs)}, soundness {sr:.0%}, 下界非平凡={T['bound']>0}, 定理成立={T['bound']<=T['err']}")


if __name__ == "__main__":
    main()
