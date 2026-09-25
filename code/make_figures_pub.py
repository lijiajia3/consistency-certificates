# -*- coding: utf-8 -*-
"""Publication figures F1-F11 for the paper (exported as svg+pdf+png)."""
import json, os
from collections import Counter
import numpy as np
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from common import (find_violations, find_functional_violations, disjoint_lower_bound,
                    validate_against_gold, gold_error_records, TYPES, norm, NAME2PID, REL_NAME,
                    fuzzy_gtype, ROOT)
from analyze_resample import analyze_model as analyze_recurrence

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
    "svg.fonttype": "none", "svg.hashsalt": "consistency-certificates",
    "pdf.fonttype": 42, "font.size": 7,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6,
    "axes.labelsize": 7, "axes.labelpad": 3, "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.direction": "out",
    "ytick.direction": "out", "legend.frameon": False, "legend.fontsize": 6.3,
    "figure.dpi": 150, "lines.linewidth": 1.2, "lines.markersize": 4.2,
})
# Restrained, colour-blind-safe palette.  Blue denotes the certificate throughout;
# vermillion denotes missed/error mass; grey provides context rather than emphasis.
C = dict(valid="#A7A9AC", fire="#0072B2", sound="#009E73", error="#D55E00",
         cover="#E69F00", n="#7A7A7A", sig="#0072B2", defi="#56B4E9", func="#CC79A7",
         soft="#DCEAF3", red_s="#F6E5DC", pale="#ECECEC", ink="#222222")
FIG = os.path.join(ROOT, "result", "figs"); os.makedirs(FIG, exist_ok=True)
DOCS = json.load(open(os.path.join(ROOT, "data", "redocred_dev_300.json")))
SIGS = json.load(open(os.path.join(ROOT, "data", "relations.json")))
MODELS = ["Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-32B-Instruct",
          "Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3"]
LAB = ["7B", "14B", "32B", "72B", "DS-V3"]
VALID = MODELS[1:]; VLAB = LAB[1:]
safe = lambda m: m.replace("/", "__")


def save(fig, name):
    for ext in ("svg", "pdf", "png"):
        metadata = None
        if ext == "pdf":
            metadata = {
                "Creator": "Consistency Certificates reproducibility pipeline",
                "Producer": "Matplotlib",
                "CreationDate": None,
                "ModDate": None,
            }
        elif ext == "svg":
            metadata = {
                "Creator": "Consistency Certificates reproducibility pipeline",
                "Date": None,
            }
        elif ext == "png":
            metadata = {"Software": "Matplotlib"}
        fig.savefig(
            f"{FIG}/{name}.{ext}",
            bbox_inches="tight",
            dpi=(600 if ext == "png" else None),
            metadata=metadata,
        )
        if ext == "svg" and name == "F2_gradient":
            path = f"{FIG}/{name}.{ext}"
            with open(path, encoding="utf-8") as handle:
                svg = handle.read()
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("\n".join(line.rstrip() for line in svg.splitlines()) + "\n")
    plt.close(fig)


def clean(ax, *, left=True, bottom=True):
    """Nature-like axes: thin rules, no chart furniture, no in-panel headline."""
    ax.spines["left"].set_visible(left)
    ax.spines["bottom"].set_visible(bottom)
    ax.tick_params(pad=2)
    ax.grid(False)


def panel_label(ax, letter):
    ax.text(-0.13, 1.06, letter, transform=ax.transAxes, fontsize=8, fontweight="bold",
            ha="left", va="top", clip_on=False)


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


def true_items(ext, d):
    return [record["item"] for record in gold_error_records(ext, d)["errors"]]


def _has_valid_output(i, m):
    ext = load(m, i)
    if ext is None or ext.get("_error"):
        return False
    ents = [e for e in ext.get("entities", []) if isinstance(e, dict) and e.get("type") in TYPES and e.get("name")]
    return bool(ents or ext.get("relations"))

COMMON = [i for i in range(len(DOCS)) if all(_has_valid_output(i, m) for m in VALID)]
print("common docs (4 valid) =", len(COMMON))


def collect():
    D = {m: dict(valid=0, n=0, fire=0, viol=0, sound=0, det=0, dett=0, rels=0,
                 d_fire=0, d_viol=0, f_fire=0, f_viol=0, sig_v=0, def_v=0,
                 def_sound=0, fun_v=0,
                 true=0, per_b=[], per_e=[], per_pid=Counter()) for m in MODELS}
    for m in MODELS:
        R = D[m]
        idxs = COMMON if m in VALID else cached_indices(m)
        for i in idxs:
            ext = load(m, i)
            R["n"] += 1
            if ext is None or ext.get("_error"):
                continue
            ents = [e for e in ext.get("entities", []) if isinstance(e, dict) and e.get("type") in TYPES and e.get("name")]
            if not ents and not ext.get("relations"):
                continue
            R["valid"] += 1
            R["rels"] += len([r for r in ext.get("relations", []) if isinstance(r, dict)])
            vs, et = find_violations(ext, SIGS, "empirical"); vs, _ = validate_against_gold(vs, et, DOCS[i])
            runtime_bound = disjoint_lower_bound([v["he"] for v in vs]); R["fire"] += (runtime_bound > 0)
            chk = [v for v in vs if v["checkable"]]; R["viol"] += len(chk); R["sound"] += sum(1 for v in chk if v["sound"]); R["sig_v"] += len(chk)
            checkable_bound = disjoint_lower_bound([v["he"] for v in chk])
            # Per-relation concentration is a gold-free descriptive count, so it
            # includes every empirical signature violation, not only the subset
            # whose endpoints align to gold for retrospective validation.
            R["per_pid"].update(v["pid"] for v in vs)
            ti = true_items(ext, DOCS[i]); inv = set()
            for v in vs:
                inv |= {f"E:{v['h']}", f"E:{v['t']}", f"R:{v['h']}|{v['pid']}|{v['t']}"}
            R["det"] += sum(1 for it in ti if it in inv); R["dett"] += len(ti)
            # Figures that describe the deployed certificate must use the
            # runtime bound over all emitted conflicts.  Gold-checkable bounds
            # are only for retrospective validation and can differ when an
            # endpoint cannot be aligned conservatively.
            R["per_b"].append(runtime_bound); R["per_e"].append(len(ti))
            R["true"] += len(ti)
            dv, _ = find_violations(ext, SIGS, "definitional"); dv, _ = validate_against_gold(dv, et, DOCS[i])
            R["d_fire"] += (disjoint_lower_bound([v["he"] for v in dv]) > 0)
            definitional_checkable = [v for v in dv if v["checkable"]]
            R["def_v"] += len(definitional_checkable)
            R["def_sound"] += sum(1 for v in definitional_checkable if v["sound"])
            fv = find_functional_violations(ext); R["f_fire"] += (disjoint_lower_bound([v["he"] for v in fv]) > 0); R["fun_v"] += len(fv)
    return D


D = collect()
p = lambda a, b: a / b if b else 0

# F1: concept illustration (multi-panel)
r"""Legacy Matplotlib implementation retained for provenance.  The IEEE-style
SVG generator invoked below is the canonical publication version.
from matplotlib.patches import Circle, Rectangle, Polygon
_INK = "#1D1D1F"; _BLUE = "#2F6DB5"; _DKBLUE = "#1F4E82"; _RED = "#C0403A"
_GREEN = "#2E8B57"; _DKGREEN = "#1F6B41"; _TEAL = "#3E8E9A"; _GREY = "#8A8D93"
_PF = "#F5F7F9"; _PE = "#D3D7DD"; _GREENF = "#E9F5EE"
_TYPECOL = {"LOC": _GREEN, "MISC": _RED, "ORG": _TEAL, "TIME": _GREY, "PER": _BLUE, "NUM": "#C99A2E"}

fig, ax = plt.subplots(figsize=(7.2, 4.35)); ax.axis("off")
ax.set_xlim(0, 100); ax.set_ylim(0, 60)


def _panel(x, y, w, h, fc=_PF, ec=_PE, lw=1.1, rs=1.4, z=1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.2,rounding_size={rs}", fc=fc, ec=ec, lw=lw, zorder=z))


def _arr(x1, y1, x2, y2, color=_GREY, lw=1.4, ms=11, z=4):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=ms, lw=lw, color=color, zorder=z, shrinkA=0, shrinkB=0))


def _doc_icon(cx, cy, w=7, h=7.4):
    x0, y0 = cx - w / 2, cy - h / 2
    ax.add_patch(Rectangle((x0, y0), w, h, fc="white", ec="#9AA0AA", lw=1.1, zorder=5))
    f = 2.0
    ax.add_patch(Polygon([(x0 + w - f, y0 + h), (x0 + w, y0 + h - f), (x0 + w - f, y0 + h - f)], closed=True, fc="#D9DDE3", ec="#9AA0AA", lw=0.8, zorder=6))
    for i, yy in enumerate([y0 + h - 2.6, y0 + h - 3.8, y0 + h - 5.0, y0 + h - 6.2]):
        ww = (w - 2.4) if i else (w - f - 1.4)
        ax.plot([x0 + 1.2, x0 + 1.2 + ww], [yy, yy], color="#B9BEC7", lw=1.0, zorder=6, solid_capstyle="round")


def _enode(cx, cy, name, typ, culprit=False):
    fw = "bold" if culprit else "normal"
    ec = _RED if culprit else "#A9AEB8"; lw = 1.7 if culprit else 1.0
    tn = ax.text(cx, cy, name, ha="left", va="center", fontsize=5.5, zorder=8, color=_INK, fontweight=fw)
    tt = ax.text(cx, cy, f":{typ}", ha="left", va="center", fontsize=5.5, zorder=8, color=_TYPECOL.get(typ, _GREY), fontweight="bold")
    fig.canvas.draw()
    inv = ax.transData.inverted()
    wn = tn.get_window_extent().transformed(inv).width
    wt = tt.get_window_extent().transformed(inv).width
    tw = wn + wt; w = tw + 3.4; h = 3.4
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.12,rounding_size=0.9", fc="white", ec=ec, lw=lw, zorder=7))
    x0 = cx - tw / 2
    tn.set_position((x0, cy)); tt.set_position((x0 + wn, cy))
    return (cx, cy)


def _gedge(p, q, color, lw=1.5, z=3, directed=True):
    style = "-|>" if directed else "-"
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=9, lw=lw, color=color, zorder=z, shrinkA=7, shrinkB=7))


def _scircle(cx, cy, culprit=False):
    ax.add_patch(Circle((cx, cy), 1.35, fc=("#FBEBE9" if culprit else "white"), ec=(_RED if culprit else "#8A8D93"), lw=1.4, zorder=6))


def _check(cx, cy, s=1.0, color=_GREEN):
    ax.plot([cx - 2.6 * s, cx - 0.7 * s, cx + 3.0 * s], [cy + 0.2 * s, cy - 2.0 * s, cy + 2.6 * s], color=color, lw=3.0, solid_capstyle="round", solid_joinstyle="round", zorder=7)


def _outbox(cx, cy, w, h, text, fc=_GREENF, ec="#BFE0CC", tc=_DKGREEN):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.14,rounding_size=0.8", fc=fc, ec=ec, lw=1.0, zorder=6))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=6.0, color=tc, zorder=7)


# top band: black-box extraction pipeline
_panel(1, 44, 98, 14, fc="#FAFBFC")
ax.text(3.2, 56.4, "BLACK-BOX EXTRACTION   ·   single decode, output only", ha="left", va="center", fontsize=6.6, color="#6B7079", fontweight="bold")
_doc_icon(11, 50.6)
ax.text(11, 45.3, "Document", ha="center", fontsize=6.4, color=_INK)
_arr(16.5, 50, 24.5, 50, _GREY, 1.6, 12)
ax.add_patch(FancyBboxPatch((25.5, 46.0), 15, 8, boxstyle="round,pad=0.2,rounding_size=1.2", fc=_DKBLUE, ec="none", zorder=5))
ax.text(33, 51.2, "Black-box LLM", ha="center", va="center", fontsize=6.9, color="white", fontweight="bold", zorder=6)
ax.text(33, 48.3, "no logits · no gold", ha="center", va="center", fontsize=5.6, color="#CBD8EA", zorder=6)
_arr(41.5, 50, 49.5, 50, _GREY, 1.6, 12)
ax.add_patch(FancyBboxPatch((50.5, 45.0), 47.5, 10.5, boxstyle="round,pad=0.2,rounding_size=1.0", fc="white", ec="#C7CBD3", lw=1.0, zorder=5))
ax.text(52.2, 54.0, "Structured output  (typed entities + relations)", ha="left", va="center", fontsize=6.1, color="#43474E", fontweight="bold", zorder=6)
_mono = dict(family="monospace", fontsize=5.7, color="#33373D", zorder=6, va="center")
ax.text(52.2, 51.1, '"entities": [2002 Olympics:MISC, Mediaș:LOC, medal:MISC,', ha="left", **_mono)
ax.text(52.2, 48.9, '             China:LOC, IOC:ORG, 1894:TIME, …]', ha="left", **_mono)
ax.text(52.2, 46.7, '"relations": [located-in, capital-of, date-of-birth, …]', ha="left", **_mono)
ax.add_patch(Polygon([(15, 43.6), (23, 43.6), (23, 41.6), (26, 41.6), (19, 38.4), (12, 41.6), (15, 41.6)], closed=True, fc=_BLUE, ec="none", alpha=0.85, zorder=4))
ax.text(28.5, 41.0, "apply certificate to the output alone", ha="left", va="center", fontsize=6.0, style="italic", color="#6B7079")

# panel a: type-signature check
_panel(1, 2, 37, 35)
ax.text(2.4, 39.0, "a", ha="left", va="center", fontsize=10, fontweight="bold", color=_INK)
ax.text(6.0, 34.6, "Type-signature check", ha="left", va="center", fontsize=7.4, fontweight="bold", color=_INK)
ax.text(6.0, 31.7, "the extractor's own output as a typed graph", ha="left", va="center", fontsize=5.7, color=_GREY)
_nO = _enode(11, 27, "Olympics", "MISC", True)
_nM = _enode(31, 28, "Mediaș", "LOC")
_nD = _enode(9, 18, "medal", "MISC", True)
_nC = _enode(30, 17, "China", "LOC")
_nI = _enode(12, 8.5, "IOC", "ORG", True)
_nT = _enode(32, 9, "1894", "TIME")
_gedge(_nM, _nC, _GREY, 1.3)
_gedge(_nC, _nT, _GREY, 1.3)
_gedge(_nO, _nM, _RED, 1.9)
_gedge(_nD, _nC, _RED, 1.9)
_gedge(_nI, _nT, _RED, 1.9)
ax.text(21, 28.8, "located-in", ha="center", fontsize=5.2, color=_RED, style="italic")
ax.text(19.5, 18.4, "capital-of", ha="center", fontsize=5.2, color=_RED, style="italic")
ax.text(22, 9.4, "date-of-birth", ha="center", fontsize=5.2, color=_RED, style="italic")
ax.plot([4, 8], [4.6, 4.6], color=_GREY, lw=1.3, solid_capstyle="round")
ax.text(8.8, 4.6, "type-consistent", ha="left", va="center", fontsize=5.4, color="#5C616B")
ax.plot([22.5, 26.5], [4.6, 4.6], color=_RED, lw=1.9, solid_capstyle="round")
ax.text(27.3, 4.6, "signature violation", ha="left", va="center", fontsize=5.4, color="#5C616B")
_arr(38, 19.5, 40.5, 19.5, _BLUE, 1.6, 12)

# panel b: conflict hypergraph -> disjoint packing
_panel(40.5, 2, 29, 35)
ax.text(41.9, 39.0, "b", ha="left", va="center", fontsize=10, fontweight="bold", color=_INK)
ax.text(45.2, 34.6, "Conflict hypergraph", ha="left", va="center", fontsize=7.4, fontweight="bold", color=_INK)
ax.text(45.2, 31.7, "each enclosure: items that", ha="left", va="center", fontsize=5.7, color=_GREY)
ax.text(45.2, 29.4, "cannot all be correct", ha="left", va="center", fontsize=5.7, color=_GREY)
for _px, _a, _b in [(48, "Olympics", "Mediaș"), (55, "medal", "China"), (62, "IOC", "1894")]:
    ax.add_patch(FancyBboxPatch((_px - 3.0, 15.0), 6.0, 11.0, boxstyle="round,pad=0.1,rounding_size=1.6", fc="#E6F4EC", ec="#93CDA9", lw=1.0, zorder=1))
    _gedge((_px, 24.5), (_px, 16.5), _RED, 1.9, directed=False)
    _scircle(_px, 24.5, True); _scircle(_px, 16.5, False)
    ax.text(_px, 26.9, _a, ha="center", fontsize=5.0, color=_INK)
    ax.text(_px, 13.9, _b, ha="center", fontsize=5.0, color=_INK)
ax.text(55, 10.4, "3 vertex-disjoint hyperedges", ha="center", fontsize=5.8, color="#5C616B")
ax.text(55, 6.7, "maximum packing $= 3$", ha="center", fontsize=7.6, color=_DKGREEN, fontweight="bold")
_arr(69.5, 19.5, 72.0, 19.5, _BLUE, 1.6, 12)

# panel c: certificate
_panel(72, 2, 27, 35, fc=_GREENF, ec="#BFE0CC")
ax.text(73.4, 39.0, "c", ha="left", va="center", fontsize=10, fontweight="bold", color=_INK)
ax.text(76.8, 34.6, "Certificate", ha="left", va="center", fontsize=7.4, fontweight="bold", color=_DKGREEN)
ax.text(76.8, 31.7, "gold-free · single decode", ha="left", va="center", fontsize=5.7, color="#5C7A67")
_check(77.5, 26.0, 1.05)
ax.text(85.5, 26.2, r"$\geq 3$ items", ha="center", va="center", fontsize=9.5, color=_DKGREEN, fontweight="bold")
ax.text(85.5, 22.3, "provably wrong", ha="center", va="center", fontsize=7.2, color=_DKGREEN)
_outbox(85.5, 17.0, 24, 3.5, "sound: every flag is a real error")
_outbox(85.5, 12.6, 24, 3.5, "no gold labels, no training")
_outbox(85.5, 8.2, 24, 3.5, "one deterministic decode")
_outbox(85.5, 3.8, 24, 3.5, "a provable floor, not an estimate")
save(fig, "F1_concept")
"""
from make_figure1_svg import write_assets as write_figure1_assets
write_figure1_assets(FIG)

# The statistical figures use a separate Nature-style visual layer.  Exit after
# generating them; the legacy code below remains only as a provenance snapshot.
from make_figures_nature import generate as generate_nature_figures
generate_nature_figures(globals())
print("done:", sorted(f for f in os.listdir(FIG) if f.startswith("F") and f.endswith(".png")))
raise SystemExit(0)

# F2: model-capability gradient
fig, ax = plt.subplots(figsize=(7.0, 3.3)); x = np.arange(len(MODELS)); w = 0.26

def _fullset_valid(m):
    ok = 0
    indices = cached_indices(m)
    for i in indices:
        ext = load(m, i)
        if ext is None or ext.get("_error"):
            continue
        ents = [e for e in ext.get("entities", []) if isinstance(e, dict) and e.get("type") in TYPES and e.get("name")]
        if ents or ext.get("relations"):
            ok += 1
    return ok, len(indices)

vj = [valid / cached * 100 if cached else 0 for valid, cached in map(_fullset_valid, MODELS)]
fr = [p(D[m]["fire"], D[m]["valid"]) * 100 if D[m]["valid"] else 0 for m in MODELS]
sd = [p(D[m]["sound"], D[m]["viol"]) * 100 if D[m]["viol"] else np.nan for m in MODELS]
ax.bar(x - w, vj, w, label="Valid-JSON rate", color=C["valid"], edgecolor="#9a9da3", lw=0.5)
ax.bar(x, fr, w, label="Firing rate", color=C["fire"])
ax.bar(x + w, [0 if np.isnan(s) else s for s in sd], w, label="Gold validation", color=C["sound"])
for i, s in enumerate(sd):
    if not np.isnan(s):
        ax.text(i + w, s + 1.6, "100%", ha="center", fontsize=7, color="#227a3f", fontweight="bold")
ax.axvspan(-0.5, 0.5, color=C["red_s"], alpha=0.22)
ax.annotate("structural\ncollapse", (0, 46), ha="center", fontsize=8, color=C["error"], style="italic")
ax.set_xticks(x); ax.set_xticklabels(LAB); ax.set_ylabel("%"); ax.set_ylim(0, 110)
ax.set_yticks([0, 25, 50, 75, 100])
ax.set_title("(a)  Certificate across the model-capability gradient", loc="left")
ax.legend(loc="lower center", fontsize=8, ncol=3, bbox_to_anchor=(0.5, -0.28))
save(fig, "F2_gradient")

# F3: evidence scale and zero false positives
fig, ax = plt.subplots(figsize=(6.4, 3.2)); y = np.arange(len(VALID))
sig = [D[m]["sig_v"] for m in VALID]; dfv = [D[m]["def_v"] for m in VALID]
ax.barh(y, sig, color=C["sig"], label="Relation-signature")
ax.barh(y, dfv, left=sig, color=C["defi"], label="Definitional")
for i, m in enumerate(VALID):
    tot = sig[i] + dfv[i]
    ax.text(tot + max(sig) * 0.02, i, f"{tot} checked · 0 FP", va="center", fontsize=8, color="#227a3f", fontweight="bold")
ax.set_yticks(y); ax.set_yticklabels(VLAB); ax.set_xlabel("Checkable violations (gold-free)")
ax.set_xlim(0, max(s + d for s, d in zip(sig, dfv)) * 1.32)
ax.set_title("(b)  Every checkable violation is gold-validated (100%)", loc="left")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=8)
save(fig, "F3_soundness")

# F4: firing vs output volume (pooled, binned)
rc = []
for m in VALID:
    for i in COMMON:
        ext = load(m, i)
        if not ext or ext.get("_error"):
            continue
        nrel = len([r for r in ext.get("relations", []) if isinstance(r, dict) and NAME2PID.get(r.get("relation"))])
        vs, et = find_violations(ext, SIGS, "empirical"); vs, _ = validate_against_gold(vs, et, DOCS[i])
        rc.append((nrel, 1 if disjoint_lower_bound([v["he"] for v in vs]) > 0 else 0))
rc = np.array(rc)
edges = [0, 5, 10, 15, 20, 25, 999]; labels = ["1–5", "6–10", "11–15", "16–20", "21–25", "26+"]
fr_b, n_b = [], []
for a, b in zip(edges[:-1], edges[1:]):
    mask = (rc[:, 0] > a) & (rc[:, 0] <= b)
    n_b.append(int(mask.sum())); fr_b.append(rc[mask, 1].mean() * 100 if mask.sum() else 0)
fig, ax = plt.subplots(figsize=(5.4, 3.4))
ax.bar(range(len(labels)), fr_b, color=C["fire"], width=0.72)
for i, (f, n) in enumerate(zip(fr_b, n_b)):
    ax.text(i, f + 2, f"{f:.0f}%", ha="center", fontsize=8, color=C["fire"], fontweight="bold")
    ax.text(i, 3, f"n={n}", ha="center", fontsize=6.5, color="white")
ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels)
ax.set_xlabel("Relations extracted per document"); ax.set_ylabel("Firing rate (%)")
ax.set_ylim(0, 105)
ax.set_title(f"Firing rises with output volume (per document, N={len(rc)})", loc="left")
save(fig, "F4_firing_volume")

# F5: constraint families
fig, ax = plt.subplots(figsize=(6.2, 3.2)); x = np.arange(len(VALID)); w = 0.26
rs = [p(D[m]["fire"], D[m]["valid"]) * 100 for m in VALID]
de = [p(D[m]["d_fire"], D[m]["valid"]) * 100 for m in VALID]
fu = [p(D[m]["f_fire"], D[m]["valid"]) * 100 for m in VALID]
ax.bar(x - w, rs, w, label="Relation-signature", color=C["sig"])
ax.bar(x, de, w, label="Definitional", color=C["defi"])
ax.bar(x + w, fu, w, label="Functional", color=C["func"])
ax.set_xticks(x); ax.set_xticklabels(VLAB); ax.set_ylabel("Firing rate (%)"); ax.set_ylim(0, max(rs) * 1.25)
ax.set_title("Complementary firing across constraint families", loc="left")
ax.legend(fontsize=8, ncol=3, loc="upper left")
save(fig, "F5_families")

# F6: detectable class
fig, ax = plt.subplots(figsize=(5.4, 3.2)); x = np.arange(len(VALID))
det = [p(D[m]["det"], D[m]["dett"]) * 100 for m in VALID]; inv = [100 - d for d in det]
ax.bar(x, det, color=C["sound"], label="Certifiable (inconsistent)")
ax.bar(x, inv, bottom=det, color=C["valid"], label="Invisible (self-consistent)")
for i, d in enumerate(det):
    ax.text(i, d / 2, f"{d:.0f}%", ha="center", fontsize=8.5, color="white", fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(VLAB); ax.set_ylabel("% of gold-measured errors"); ax.set_ylim(0, 100)
ax.set_title("Detectable class: certified floor vs invisible remainder", loc="left")
ax.legend(fontsize=8, loc="upper right")
save(fig, "F6_detectable")

# E5: resampling self-consistency, using the same unique-item definition as Table III.
RSM = "Qwen/Qwen2.5-32B-Instruct"; K = 5
sc_summary, _ = analyze_recurrence(RSM, 50, K)
cnt = [sc_summary[f"recurrence_{f}"] for f in range(K + 1)]
hi = sc_summary["stable_visible_errors"]
tot = sc_summary["certificate_visible_errors"]
if tot:
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    bars = ax.bar(range(K + 1), cnt, color=[C["valid"]] * 3 + [C["error"]] * 3, edgecolor="white", lw=0.6)
    ax.axvspan(2.5, 5.5, color=C["red_s"], alpha=0.18)
    ax.annotate(f"stable\n{hi}/{tot} = {hi/tot:.0%}\n(recurrence rule misses)", (4, max(cnt) * 0.7),
                ha="center", fontsize=8, color=C["error"], fontweight="bold")
    ax.set_xlabel(f"Recurrence of a visible error item across K={K} decodes"); ax.set_ylabel("# visible error items")
    ax.set_title("Stable errors missed by a recurrence alarm", loc="left")
    save(fig, "F7_selfconsistency")
    fig, ax = plt.subplots(figsize=(4.0, 3.2))
    rc = 100 * (tot - hi) / tot
    b = ax.bar([0, 1], [100, rc], color=[C["sound"], C["fire"]], width=0.5)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["Certificate\n(1 decode)", f"Resampling\n(K={K})"])
    ax.set_ylabel("% certificate-visible errors detected"); ax.set_ylim(0, 112)
    ax.text(0, 101.5, "100%", ha="center", fontsize=9, color="#227a3f", fontweight="bold")
    ax.text(1, rc + 1.5, f"{rc:.0f}%", ha="center", fontsize=9, color=C["fire"], fontweight="bold")
    ax.set_title("Complementary coverage", loc="left")
    save(fig, "F8_complementary")

# F9: triage
M2 = "deepseek-ai/DeepSeek-V3"; bs, es = D[M2]["per_b"], D[M2]["per_e"]
if len(bs) > 5:
    rx = np.argsort(np.argsort(bs)); ry = np.argsort(np.argsort(es)); rho = np.corrcoef(rx, ry)[0, 1]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 3.1))
    jt = np.array(bs) + np.random.RandomState(0).uniform(-0.16, 0.16, len(bs))
    a1.scatter(jt, es, s=20, alpha=0.45, color=C["fire"], edgecolor="none")
    a1.set_xlabel("Certificate bound (per doc)"); a1.set_ylabel("True error count")
    a1.set_title(f"(a)  Bound vs errors  (ρ={rho:.2f})", loc="left", fontsize=9.5)
    order = np.argsort(bs)[::-1]; fr_ = np.cumsum([es[j] for j in order]) / max(sum(es), 1)
    xx = np.arange(1, len(fr_) + 1) / len(fr_) * 100
    a2.fill_between(xx, fr_ * 100, color=C["fire"], alpha=0.12)
    a2.plot(xx, fr_ * 100, color=C["fire"], lw=1.8, label="Bound order")
    a2.plot([0, 100], [0, 100], "--", color=C["n"], lw=0.9, label="Random")
    a2.set_xlabel("% documents reviewed"); a2.set_ylabel("% errors found")
    a2.set_title("(b)  Triage curve", loc="left", fontsize=9.5); a2.legend(fontsize=7.5, loc="lower right")
    save(fig, "F9_triage")

# F10: certificate lower bound versus gold-measured errors
fig, ax = plt.subplots(figsize=(6.2, 3.3)); x = np.arange(len(VALID)); w = 0.34
cb = [sum(D[m]["per_b"]) for m in VALID]; tr = [D[m]["true"] for m in VALID]
ax.bar(x - w / 2, cb, w, label="Certified lower bound", color=C["fire"])
ax.bar(x + w / 2, tr, w, label="Gold-measured errors", color=C["error"])
for i in range(len(VALID)):
    ax.text(i + w / 2, tr[i] + max(tr) * 0.01, f"{p(cb[i], tr[i]):.0%}\nfloor", ha="center", va="bottom", fontsize=6.5, color=C["n"])
ax.set_xticks(x); ax.set_xticklabels(VLAB); ax.set_ylabel("Total count (all docs)")
ax.set_ylim(0, max(tr) * 1.18)
ax.set_title("Certified floor versus gold-measured errors", loc="left")
ax.legend(fontsize=7.5, loc="upper left")
save(fig, "F10_tightness")

print("done:", sorted(f for f in os.listdir(FIG) if f.startswith("F") and f.endswith(".png")))
