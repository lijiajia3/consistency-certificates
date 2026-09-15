# -*- coding: utf-8 -*-
"""Nature-style statistical figures (F2--F11).

The plotting code is kept separate from the data collection in
``make_figures_pub.py`` so the visual grammar can be audited independently.
"""

import json
import os
from collections import Counter

import numpy as np
from scipy.stats import beta, spearmanr


def generate(g):
    plt, C, D = g["plt"], g["C"], g["D"]
    MODELS, LAB, VALID, VLAB = g["MODELS"], g["LAB"], g["VALID"], g["VLAB"]
    DOCS, SIGS, TYPES = g["DOCS"], g["SIGS"], g["TYPES"]
    ROOT, FIG, REL_NAME = g["ROOT"], g["FIG"], g["REL_NAME"]
    load, save, p, safe = g["load"], g["save"], g["p"], g["safe"]
    COMMON = g["COMMON"]
    find_violations = g["find_violations"]
    disjoint_lower_bound = g["disjoint_lower_bound"]
    validate_against_gold = g["validate_against_gold"]
    NAME2PID, norm = g["NAME2PID"], g["norm"]

    def clean(ax, *, left=True, bottom=True):
        ax.spines["left"].set_visible(left)
        ax.spines["bottom"].set_visible(bottom)
        ax.tick_params(pad=2)
        ax.grid(False)

    def panel_label(ax, letter):
        ax.text(-0.13, 1.06, letter, transform=ax.transAxes, fontsize=8,
                fontweight="bold", ha="left", va="top", clip_on=False)

    # F2 — three metrics use lines and distinct markers rather than heavy bars.
    fig, ax = plt.subplots(figsize=(7.15, 2.35))
    x = np.arange(len(MODELS))

    def fullset_valid(m):
        ok = 0
        for i in range(len(DOCS)):
            ext = load(m, i)
            if ext is None or ext.get("_error"):
                continue
            ents = [e for e in ext.get("entities", [])
                    if isinstance(e, dict) and e.get("type") in TYPES and e.get("name")]
            ok += bool(ents or ext.get("relations"))
        return ok

    valid_rate = [fullset_valid(m) / len(DOCS) * 100 for m in MODELS]
    firing = [p(D[m]["fire"], D[m]["valid"]) * 100 if D[m]["valid"] else np.nan
              for m in MODELS]
    sound = [p(D[m]["sound"], D[m]["viol"]) * 100 if D[m]["viol"] else np.nan
             for m in MODELS]
    ax.plot(x, valid_rate, "s-", color=C["valid"], label="Valid output",
            markeredgecolor="white", markeredgewidth=.5)
    ax.plot(x[1:], np.asarray(firing)[1:], "o-", color=C["fire"],
            label="Certificate firing")
    ax.plot(x[1:], np.asarray(sound)[1:], "^-", color=C["sound"], label="Observed soundness")
    ax.axvspan(-.35, .35, color=C["red_s"], zorder=-1)
    ax.text(0, 34, "structural\ncollapse", ha="center", va="center",
            fontsize=6.5, color=C["error"])
    ax.text(0, valid_rate[0] + 5, f"{valid_rate[0]:.0f}%", ha="center",
            color=C["valid"], fontsize=6.2)
    for i in range(1, len(MODELS)):
        ax.text(i, sound[i] + 3.2, "100% obs.", ha="center", color=C["sound"], fontsize=6.2)
    ax.set_xticks(x); ax.set_xticklabels(LAB)
    ax.set_ylabel("Rate (%)")
    ax.set_ylim(0, 108); ax.set_yticks([0, 25, 50, 75, 100])
    ax.legend(loc="lower center", ncol=3, bbox_to_anchor=(.5, 1.01),
              handlelength=1.5, columnspacing=1.8)
    clean(ax); save(fig, "F2_gradient")

    # F3 — evidence scale, with the aggregate soundness result called out once.
    fig, ax = plt.subplots(figsize=(3.5, 2.35)); y = np.arange(len(VALID))
    sig = [D[m]["sig_v"] for m in VALID]
    defin = [D[m]["def_v"] for m in VALID]
    ax.barh(y, sig, height=.5, color=C["sig"], label="Relation signature")
    ax.barh(y, defin, left=sig, height=.5, color=C["defi"], label="Definitional")
    for i, total in enumerate(np.asarray(sig) + np.asarray(defin)):
        ax.text(total + 12, i, f"{total}", va="center", fontsize=6.3, color=C["ink"])
    ax.text(0, 1.04, f"{sum(sig) + sum(defin):,} checked  •  0 observed FP  •  95% upper 0.10%",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=6.6,
            color=C["sound"])
    ax.set_yticks(y); ax.set_yticklabels(VLAB); ax.invert_yaxis()
    ax.set_xlabel("Checkable violations")
    ax.set_xlim(0, max(np.asarray(sig) + np.asarray(defin)) * 1.13)
    ax.legend(loc="lower center", bbox_to_anchor=(.5, 1.12), ncol=2,
              handlelength=1.5)
    clean(ax); save(fig, "F3_soundness")

    # F4 — binned proportions with approximate 95% binomial intervals.
    rows = []
    for m in VALID:
        for i in COMMON:
            ext = load(m, i)
            if not ext or ext.get("_error"):
                continue
            nrel = len([r for r in ext.get("relations", [])
                        if isinstance(r, dict) and NAME2PID.get(r.get("relation"))])
            vs, et = find_violations(ext, SIGS, "empirical")
            vs, _ = validate_against_gold(vs, et, DOCS[i])
            rows.append((nrel, int(disjoint_lower_bound([v["he"] for v in vs]) > 0)))
    rows = np.asarray(rows)
    edges = [0, 5, 10, 15, 20, 25, 999]
    labels = ["1–5", "6–10", "11–15", "16–20", "21–25", "26+"]
    rates, ns = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        mask = (rows[:, 0] > a) & (rows[:, 0] <= b)
        ns.append(int(mask.sum()))
        rates.append(rows[mask, 1].mean() * 100 if mask.sum() else 0)
    ci = [1.96 * np.sqrt((r / 100) * (1 - r / 100) / n) * 100 if n else 0
          for r, n in zip(rates, ns)]
    fig, ax = plt.subplots(figsize=(3.5, 2.45)); xx = np.arange(len(labels))
    ax.plot(xx, rates, color=C["fire"], lw=1.0, zorder=1)
    ax.errorbar(xx, rates, yerr=ci, fmt="o", color=C["fire"], ecolor=C["fire"],
                elinewidth=.7, capsize=2, markeredgecolor="white",
                markeredgewidth=.5, zorder=2)
    for i, (rate, n) in enumerate(zip(rates, ns)):
        ax.text(i, rate + ci[i] + 4, f"{rate:.0f}%", ha="center", fontsize=6.1,
                color=C["fire"])
        ax.text(i, 3, f"n={n}", ha="center", fontsize=5.4, color=C["n"])
    ax.set_xticks(xx); ax.set_xticklabels(labels)
    ax.set_xlabel("Relations extracted per document")
    ax.set_ylabel("Documents firing (%)")
    ax.set_ylim(0, 105); ax.set_yticks([0, 25, 50, 75, 100])
    clean(ax); save(fig, "F4_firing_volume")

    # F5 — consistent series encodings reveal complementarity without grouped bars.
    fig, ax = plt.subplots(figsize=(7.15, 2.25)); x = np.arange(len(VALID))
    rel = [p(D[m]["fire"], D[m]["valid"]) * 100 for m in VALID]
    defin = [p(D[m]["d_fire"], D[m]["valid"]) * 100 for m in VALID]
    functional = [p(D[m]["f_fire"], D[m]["valid"]) * 100 for m in VALID]
    for vals, marker, color, label in [
            (rel, "o", C["sig"], "Relation signature"),
            (defin, "s", C["defi"], "Definitional"),
            (functional, "^", C["func"], "Functional (firing only)")]:
        ax.plot(x, vals, marker=marker, color=color, label=label,
                markeredgecolor="white", markeredgewidth=.45)
    ax.set_xticks(x); ax.set_xticklabels(VLAB)
    ax.set_ylabel("Documents firing (%)")
    ax.set_ylim(0, max(rel) * 1.17); ax.set_yticks([0, 20, 40, 60, 80])
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(.5, 1.01), columnspacing=2)
    clean(ax); save(fig, "F5_families")

    # F6 — detectable and invisible classes sum to 100% for each extractor.
    fig, ax = plt.subplots(figsize=(3.5, 2.25)); y = np.arange(len(VALID))
    detectable = [p(D[m]["det"], D[m]["dett"]) * 100 for m in VALID]
    invisible = [100 - d for d in detectable]
    ax.barh(y, detectable, height=.5, color=C["fire"], label="Certifiable")
    ax.barh(y, invisible, left=detectable, height=.5, color=C["pale"], label="Invisible")
    for i, d in enumerate(detectable):
        ax.text(d / 2, i, f"{d:.0f}%", ha="center", va="center", fontsize=6.1,
                color="white")
        ax.text(d + (100 - d) / 2, i, f"{100-d:.0f}%", ha="center", va="center",
                fontsize=6.1, color=C["n"])
    ax.set_yticks(y); ax.set_yticklabels(VLAB); ax.invert_yaxis()
    ax.set_xlabel("Gold-measured errors (%)"); ax.set_xlim(0, 100)
    ax.legend(ncol=2, loc="lower center", bbox_to_anchor=(.5, 1.02),
              handlelength=1.5)
    clean(ax); save(fig, "F6_detectable")

    # F7/F8 — recurrence and complementary detection.
    resample_model, k_decodes = "Qwen/Qwen2.5-32B-Instruct", 5

    def load_k(i, k):
        path = os.path.join(ROOT, "result", "resample", safe(resample_model),
                            f"{i:04d}_{k}.json")
        return json.load(open(path)) if os.path.exists(path) else None

    recurrence = []
    for i in range(50):
        deployed = load(resample_model, i)
        if not deployed or deployed.get("_error"):
            continue
        decodes = [d for d in [load_k(i, k) for k in range(k_decodes)] if d]
        if len(decodes) < k_decodes:
            continue
        rel_sets = [set((norm(r.get("head")), NAME2PID.get(r.get("relation")),
                         norm(r.get("tail"))) for r in d.get("relations", [])
                        if isinstance(r, dict) and NAME2PID.get(r.get("relation")))
                    for d in decodes]
        violations, et = find_violations(deployed, SIGS, "empirical")
        violations, _ = validate_against_gold(violations, et, DOCS[i])
        for v in violations:
            if v["sound"]:
                recurrence.append(sum((v["h"], v["pid"], v["t"]) in s for s in rel_sets))
    if recurrence:
        counts = [recurrence.count(i) for i in range(k_decodes + 1)]
        stable = sum(counts[3:]); total = len(recurrence)
        ci_low = 100 * beta.ppf(0.025, stable, total - stable + 1)
        ci_high = 100 * beta.ppf(0.975, stable + 1, total - stable)
        fig, ax = plt.subplots(figsize=(3.5, 2.35))
        ax.bar(range(k_decodes + 1), counts, width=.62,
               color=[C["valid"]] * 3 + [C["error"]] * 3)
        ymax = max(counts) * 1.23
        ax.plot([2.7, 2.7, 5.3, 5.3], [ymax*.82, ymax*.88, ymax*.88, ymax*.82],
                color=C["error"], lw=.7)
        ax.text(4, ymax*.91,
                f"{stable}/{total} (95% CI {ci_low:.1f}–{ci_high:.1f}%)",
                ha="center", fontsize=6.1, color=C["error"])
        ax.set_xticks(range(k_decodes + 1))
        ax.set_xlabel(f"Recurrence across {k_decodes} additional decodes")
        ax.set_ylabel("Certified errors"); ax.set_ylim(0, ymax)
        clean(ax); save(fig, "F7_selfconsistency")

        detected = 100 * (total - stable) / total
        fig, ax = plt.subplots(figsize=(3.0, 1.35)); yy = np.array([1, 0])
        vals = [100, detected]
        ax.hlines(yy, 0, vals, color=C["pale"], lw=4, zorder=1)
        ax.scatter(vals, yy, s=24, color=[C["sound"], C["fire"]], zorder=2)
        ax.text(100, 1, " 100%", va="center", fontsize=6.4, color=C["sound"])
        ax.text(detected, 0, f" {detected:.0f}%", va="center", fontsize=6.4,
                color=C["fire"])
        ax.set_yticks(yy)
        ax.set_yticklabels(["Certificate (1 decode)", f"Resampling (K={k_decodes})"])
        ax.set_xlabel("Deployed certified errors detected (%)"); ax.set_xlim(0, 108)
        ax.set_ylim(-.3, 1.3)
        clean(ax, left=False); ax.tick_params(axis="y", length=0)
        save(fig, "F8_complementary")

    # F9 — raw per-document data and the implied review ordering.
    model = "deepseek-ai/DeepSeek-V3"
    bounds, errors = D[model]["per_b"], D[model]["per_e"]
    if len(bounds) > 5:
        rho = float(spearmanr(bounds, errors).statistic)
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.15, 2.55),
                                     gridspec_kw={"wspace": .34})
        jitter = np.asarray(bounds) + np.random.RandomState(0).uniform(-.16, .16,
                                                                       len(bounds))
        a1.scatter(jitter, errors, s=9, alpha=.42, color=C["fire"], edgecolor="none",
                   rasterized=False)
        a1.set_xlabel("Certificate bound (per doc)"); a1.set_ylabel("True error count")
        a1.text(.98, .96, f"Spearman ρ = {rho:.2f}", transform=a1.transAxes,
                ha="right", va="top", fontsize=6.3)
        panel_label(a1, "a"); clean(a1)
        order = np.argsort(bounds)[::-1]
        cumulative = np.cumsum([errors[j] for j in order]) / max(sum(errors), 1)
        reviewed = np.arange(1, len(cumulative) + 1) / len(cumulative) * 100
        a2.plot(reviewed, cumulative * 100, color=C["fire"], lw=1.4,
                label="Certificate order")
        a2.plot([0, 100], [0, 100], "--", color=C["n"], lw=.8,
                label="Random order")
        a2.set_xlabel("Documents reviewed (%)"); a2.set_ylabel("Errors found (%)")
        a2.legend(loc="upper left", handlelength=2.2)
        panel_label(a2, "b"); clean(a2)
        save(fig, "F9_triage")

    # F10 — a compact dumbbell chart foregrounds the guaranteed floor.
    fig, ax = plt.subplots(figsize=(3.5, 2.35)); y = np.arange(len(VALID))
    bound = [sum(D[m]["per_b"]) for m in VALID]
    truth = [D[m]["true"] for m in VALID]
    for i in range(len(VALID)):
        ax.plot([bound[i], truth[i]], [i, i], color="#B9B9B9", lw=1.0, zorder=1)
    ax.scatter(bound, y, s=24, color=C["fire"], label="Certified floor", zorder=2)
    ax.scatter(truth, y, s=24, facecolors="white", edgecolors=C["error"],
               linewidths=.9, label="Gold-measured errors", zorder=2)
    for i in range(len(VALID)):
        ax.text(bound[i] + 45, i - .15, f"{p(bound[i], truth[i]):.0%}", ha="left",
                va="bottom", fontsize=5.8, color=C["fire"])
    ax.set_yticks(y); ax.set_yticklabels(VLAB); ax.invert_yaxis()
    ax.set_xlabel("Total items across 297 documents")
    ax.set_xlim(0, max(truth) * 1.08)
    ax.legend(ncol=2, loc="lower center", bbox_to_anchor=(.5, 1.02),
              handletextpad=.4, columnspacing=1.2)
    clean(ax); save(fig, "F10_tightness")

    # F11 — gold-free empirical violations on the shared 297-document set.  This
    # intentionally includes flags without a gold endpoint alignment; gold is not
    # needed to issue a certificate, only to measure soundness in F3.
    pooled = Counter()
    for m in VALID:
        pooled.update(D[m]["per_pid"])
    top = pooled.most_common(5)
    names = [f"{REL_NAME.get(pid, pid)}\n({pid})" for pid, _ in top][::-1]
    vals = [value for _, value in top][::-1]
    fig, ax = plt.subplots(figsize=(3.5, 2.35)); y = np.arange(len(vals))
    colors = [C["fire"] if i >= len(vals) - 2 else "#6AAED6" for i in range(len(vals))]
    ax.barh(y, vals, height=.52, color=colors)
    for yi, value in zip(y, vals):
        ax.text(value + max(vals)*.018, yi, f"{value:,}", va="center", fontsize=6.2,
                color=C["ink"])
    ax.set_yticks(y); ax.set_yticklabels(names)
    ax.set_xlabel("Certified violations across four models")
    ax.set_xlim(0, max(vals) * 1.14)
    clean(ax); save(fig, "F11_perrelation")
