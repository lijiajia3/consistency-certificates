# -*- coding: utf-8 -*-
"""独立来源(纯 schema, 零语料)签名消融。
对全部 18 个关系, 根据 Wikidata 属性语义手工构造保守的 (head-type, tail-type) 允许集,
完全不参考 Re-DocRED 语料统计。测 soundness/firing, 直接回应"签名同源诱导声音性"质疑,
并证明存在一个真正 corpus-free 的变体。"""
import json, os
from itertools import product
from common import find_violations, disjoint_lower_bound, validate_against_gold, TYPES

DOCS = json.load(open("redocred_dev_300.json"))
EMP = json.load(open("relations.json"))
MODELS = ["Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-32B-Instruct",
          "Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3"]
safe = lambda m: m.replace("/", "__")

# 纯 schema 允许集: {pid: (allowed_head_types, allowed_tail_types)}  保守(宽进以保 soundness)
SCHEMA_HT = {
    "P131": ({"LOC", "ORG", "MISC", "PER"}, {"LOC"}),          # located in -> 地点在地点
    "P17":  ({"LOC", "ORG", "MISC", "PER"}, {"LOC"}),          # country
    "P27":  ({"PER"}, {"LOC"}),                                  # country of citizenship
    "P150": ({"LOC"}, {"LOC"}),                                  # contains admin territory
    "P800": ({"PER", "ORG"}, {"MISC", "ORG"}),                  # notable work
    "P527": ({"MISC", "ORG", "LOC"}, {"MISC", "ORG", "LOC", "PER"}),  # has part
    "P361": ({"MISC", "ORG", "LOC", "PER"}, {"MISC", "ORG", "LOC"}),  # part of
    "P175": ({"MISC"}, {"PER", "ORG"}),                         # performer: 作品->人/团
    "P577": ({"MISC", "ORG"}, {"TIME"}),                       # publication date
    "P1344": ({"PER", "ORG"}, {"MISC", "ORG"}),                # participant in -> 事件
    "P710": ({"MISC", "ORG"}, {"PER", "ORG"}),                 # participant: 事件->人/团
    "P463": ({"PER", "ORG"}, {"ORG"}),                         # member of
    "P1001": ({"MISC", "ORG", "LOC"}, {"LOC", "ORG"}),         # applies to jurisdiction
    "P495": ({"MISC", "ORG", "PER"}, {"LOC"}),                 # country of origin
    "P569": ({"PER"}, {"TIME"}),                                # date of birth
    "P161": ({"MISC"}, {"PER"}),                                # cast member: 影视->人
    "P571": ({"ORG", "MISC", "LOC"}, {"TIME"}),               # inception
    "P264": ({"PER", "ORG", "MISC"}, {"ORG"}),                # record label -> 组织
}
SCHEMA = {pid: {"signatures": [list(p) for p in product(hs, ts)]} for pid, (hs, ts) in SCHEMA_HT.items()}


def load(m, i):
    p = f"extractions/{safe(m)}/{i:04d}.json"
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
print("================  纯 SCHEMA(零语料)签名  vs  经验签名  ================")
print(f"[schema-only 独立来源]  checkable={sc}  sound={ss}  soundness={100*ss/sc:.1f}%  firing={100*sf/st:.0f}%")
print(f"[empirical  同源语料 ]  checkable={ec}  sound={es}  soundness={100*es/ec:.1f}%  firing={100*ef/et_:.0f}%")
print("=====================================================================")
print("schema 签名完全不看 Re-DocRED 语料统计, 只按 Wikidata 属性语义手工构造。")
print("若其 soundness 仍高, 则声音性并非'同源构造'的产物。")
