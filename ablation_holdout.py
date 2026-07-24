# -*- coding: utf-8 -*-
"""Hold-out 签名消融: 用与测试集不相交的文档金标造经验签名, 再测 soundness。
直接回应"循环论证"质疑——测试文档的金标从不参与其自身签名的构造。
2-折交叉: fold0 签名测 fold1, fold1 签名测 fold0, 覆盖全部文档。"""
import json, os
from collections import defaultdict
from common import find_violations, validate_against_gold, NAME2PID, TYPES

DOCS = json.load(open("redocred_dev_300.json"))
SIGS_FULL = json.load(open("relations.json"))
PIDSET = set(SIGS_FULL.keys())  # 18 relations
MODELS = ["Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-32B-Instruct",
          "Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3"]
safe = lambda m: m.replace("/", "__")


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


def derive_sigs(doc_idx):
    """从给定文档集合的金标造经验签名。"""
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
SIG0 = derive_sigs(fold0)   # 用 fold0 造, 测 fold1
SIG1 = derive_sigs(fold1)   # 用 fold1 造, 测 fold0
print(f"folds: {len(fold0)} / {len(fold1)} docs; "
      f"sig relations covered: fold0={len(SIG0)}, fold1={len(SIG1)}")


def run(sig_for_test, test_idx, tag):
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


# hold-out (disjoint): fold1 用 SIG0, fold0 用 SIG1
c1, s1, f1, t1 = run(SIG0, fold1, "f1|SIG0")
c0, s0, f0, t0 = run(SIG1, fold0, "f0|SIG1")
CHK, SND, FIRE, TOT = c1 + c0, s1 + s0, f1 + f0, t1 + t0

# in-sample baseline (full corpus signatures, same docs) 对照
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

print("\n================  HOLD-OUT 签名消融  ================")
print(f"[hold-out 不相交]  checkable={CHK}  sound={SND}  "
      f"soundness={100*SND/CHK:.1f}%  firing-docs={FIRE}/{TOT}={100*FIRE/TOT:.0f}%")
print(f"[in-sample 全语料]  checkable={bc}  sound={bs}  "
      f"soundness={100*bs/bc:.1f}%  firing-docs={bf}")
print("=====================================================")
print("结论: 若 hold-out soundness 仍 ~100%, 则零假阳不是签名构造的必然产物,")
print("      因为测试文档的金标从未参与其签名——直接反驳循环论证。")
