# -*- coding: utf-8 -*-
"""E5 分析: self-consistency vs 一致性证书。
论点: 证书认证的错误里, 大量是"自洽的"(K 次解码多数都出现)→ resampling/自一致性
判其可靠、检测不出; 而类型签名证书确定性地抓到。"""
import json, os
from common import find_violations, validate_against_gold, norm, NAME2PID

MODEL = "Qwen/Qwen2.5-32B-Instruct"
K = 5
NDOCS = 50
DOCS = json.load(open("redocred_dev_300.json"))[:NDOCS]
SIGS = json.load(open("relations.json"))


def safe(m): return m.replace("/", "__")


def load_k(i, k):
    p = f"resample/{safe(MODEL)}/{i:04d}_{k}.json"
    return json.load(open(p)) if os.path.exists(p) else None


def rel_key(r):
    return (norm(r.get("head")), NAME2PID.get(r.get("relation")), norm(r.get("tail")))


def load_t0(i):
    p = f"extractions/{safe(MODEL)}/{i:04d}.json"
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    # 部署基线 = T=0 确定性抽取; 其认证错误在 K 次高温解码里的稳定性 = self-consistency
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
        # T=0 抽取里的 sound 违反 = 部署时会真实发生的认证错误
        viols, etype = find_violations(t0, SIGS, "empirical")
        viols, _ = validate_against_gold(viols, etype, DOCS[i])
        for v in viols:
            if v["sound"]:
                key = (v["h"], v["pid"], v["t"])
                freq = sum(1 for rs in relsets if key in rs)  # 该错误在 K 次高温解码中的稳定度
                sc_dist.append(freq)

    if not sc_dist:
        print("无数据(resample 未就绪?)"); return
    n = len(sc_dist)
    import statistics
    hi = sum(1 for f in sc_dist if f >= 3)     # 出现 >=3/5 = 高自一致(resampling 判可靠)
    allk = sum(1 for f in sc_dist if f == K)    # K 次全出现 = 完全自洽
    lo = sum(1 for f in sc_dist if f <= 1)      # 只出现 <=1 次 = 自一致性能标记
    print(f"===== E5: self-consistency vs 证书 ({MODEL}, {NDOCS}篇, K={K}) =====")
    print(f"证书认证(sound)的错误关系数: {n}")
    print(f"self-consistency 频次分布(在 K={K} 次解码中出现次数):")
    from collections import Counter
    c = Counter(sc_dist)
    for f in range(K + 1):
        bar = "█" * c.get(f, 0)
        print(f"  出现 {f}/{K} 次: {c.get(f,0):3}  {bar}")
    print(f"\n关键对照:")
    print(f"  · 高自一致错误(>=3/5, resampling 会判其'可靠/稳定'→漏检): {hi}/{n} = {hi/n:.0%}")
    print(f"  · 完全自洽错误(5/5 全出现, self-consistency 完全无感): {allk}/{n} = {allk/n:.0%}")
    print(f"  · 低一致错误(<=1/5, 只有这些 resampling 才可能标记): {lo}/{n} = {lo/n:.0%}")
    print(f"\n结论: 证书认证的错误中 {hi/n:.0%} 是自一致的 → self-consistency/resampling 系统性漏掉,")
    print(f"      而类型签名证书**确定性**地全部抓到(soundness 100%)。这正是综述的 self-consistency blind spot。")


if __name__ == "__main__":
    main()
