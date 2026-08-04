# Consistency Certificates

**Gold-free, provably sound error lower bounds for black-box large language model information extraction.**

This repository contains the code, cached model outputs, and analysis scripts behind the paper
*"Consistency Certificates: Gold-Free, Provably Sound Error Bounds for Black-Box Large Language
Model Information Extraction"* (IEEE Access, under review). Every number in the paper is
reproducible offline from the cached data — no API key is needed to reproduce the results.

A *consistency certificate* audits a black-box extractor's own output. When the output violates a
hard type-signature constraint (for example, a `date-of-birth` relation whose head is not a person),
it is internally self-contradictory, so **at least one extracted item is provably wrong**. The
largest set of mutually disjoint violations is a **provable lower bound** on the number of errors,
computed from a **single decode with no gold reference**. The combinatorial bound is a classical
result from database repair and consistent query answering; the contribution here is its transfer to
black-box, document-level LLM information extraction, plus a multi-model, multi-source empirical
characterization of what it can and cannot certify.

## How it works

![Concept figure](result/figs/F1_concept.png)

1. **Extract.** A black-box LLM is prompted (JSON mode, temperature 0) to emit typed entities and
   relations from a document — one decode, output text only.
2. **Check.** Each emitted relation is checked against the *hard type-signature* its relation admits
   (e.g. `located-in` requires a `LOC`/`ORG` head). A violation is internally self-contradictory, so
   the output is certainly wrong somewhere.
3. **Certify.** The maximum number of vertex-disjoint violations is a **sound lower bound** on the
   number of wrong items — no gold labels, no model internals, no resampling.
4. **Compose.** The certificate covers errors that are *internally inconsistent*; it complements
   self-consistency (which misses stable, self-consistent errors), precision-side signals, and
   recall-side coverage estimates.

## Key results

| Setting | Metric | Value |
|---|---|---|
| In-sample soundness (4 models, empirical + definitional) | checkable violations that are real errors | **2929 / 2929 = 100%** |
| Hold-out signatures (disjoint document split) | out-of-sample soundness | **99.8%** (3537 / 3544) |
| Schema-only signatures (Wikidata semantics, **zero corpus**) | soundness | **98.8%** (3134 / 3171) |
| Cross-architecture control (GLM-4-32B) | soundness | **651 / 651 = 100%** |
| Firing rate (empirical signatures) | documents with a non-zero bound | **66–73%** |
| Detectable class | share of gold errors the certificate can see | **22–24%** |
| Complementarity to self-consistency | certified errors that recur across K=5 decodes | **21%** |
| Weak-model cliff | Qwen2.5-7B valid structured output | **5%** |

Evaluation runs on **297 Re-DocRED documents** on which all four usable extractors produce valid
structured output. DeepSeek-V3 was re-queried over the full 300-document dev split (299 valid
outputs, one empty), so no extractor's coverage is partial in the released data.

Soundness stays between **98.8% and 100%** as the signature source moves from the same corpus,
through a disjoint split, to a fully corpus-independent schema. The theorem
(`#errors ≥ maximum matching`) holds on every document and is separately verified on 2000 random
conflict graphs.

## Reproduce

The cached extractions are included, so every number in the paper can be recomputed offline without
querying any API:

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install requests numpy matplotlib scipy networkx

# Theorem unit test + 2000-graph stress test
python3 code/certificate.py

# Main results table (soundness 2929/2929, firing, detectable class)
python3 code/analyze.py

# Soundness ablations (99.8% hold-out, 98.8% schema-only)
python3 code/ablation_holdout.py
python3 code/ablation_schema.py

# Cross-architecture control (651/651) and self-consistency complementarity (21%)
python3 code/analyze_glm.py
python3 code/analyze_resample.py

# Triage correlation and figure regeneration
python3 code/analyze_triage.py
python3 code/make_figures_pub.py
```

All scripts live in `code/` and resolve data paths relative to the repository root, so they run from
any working directory.

To re-run extraction from scratch (needs a SiliconFlow API key, see below):

```bash
NDOCS=300 WORKERS=4 python3 code/run_extractions.py          # all models
ONLY_MODELS=GLM NDOCS=300 WORKERS=3 python3 code/run_extractions.py   # a single model
```

Extraction is cached per `(model, document)` and resumable; existing results are skipped.

## Repository layout

```
consistency_certificates/
├── code/                   # all analysis scripts (paths resolve relative to repo root)
│   ├── common.py           # shared constants, prompt, violations, gold-free bound
│   ├── certificate.py      # theorem code + 2000-graph stress test (matching / vertex cover)
│   ├── run_extractions.py  # concurrent, cached black-box extraction (SiliconFlow API)
│   ├── analyze.py          # main results table (soundness, firing, detectable class)
│   ├── run_resample.py     # E5: K=5 stochastic decodes at T=0.7
│   ├── analyze_resample.py # E5 analysis: self-consistency overlap
│   ├── analyze_triage.py   # E6: per-document bound vs true error count (Spearman)
│   ├── analyze_glm.py      # GLM-4-32B cross-architecture metrics
│   ├── ablation_holdout.py # two-fold hold-out signature ablation (99.8%)
│   ├── ablation_schema.py  # schema-only (zero-corpus) signature ablation (98.8%)
│   ├── pilot.py            # minimal go/no-go pilot (15 docs, needs API key)
│   ├── make_figures.py     # legacy figures (gradient, self-consistency, triage)
│   └── make_figures_pub.py # publication figures F1-F11 (svg + pdf + png)
├── data/                   # input data
│   ├── relations.json      # empirical (head-type, tail-type) signatures for 18 relations
│   └── redocred_dev_{15,50,100,300}.json   # Re-DocRED dev splits (gold for validation only)
├── result/                 # all outputs
│   ├── extractions/        # cached model outputs, one JSON per (model, document)
│   ├── resample/           # E5 cached stochastic decodes (Qwen2.5-32B)
│   ├── figs/               # generated figures (.pdf, .svg, .png)
│   └── RESULTS.md          # results summary
├── README.md
└── LICENSE
```

The manuscript LaTeX source is kept in a separate private location and is not part of this code
repository.

## Data and models

- **Dataset:** [Re-DocRED](https://github.com/tonytan48/Re-DocRED) validation split. Gold
  annotations are used only to *validate* the certificate, never to run it.
- **Models (via SiliconFlow):** Qwen2.5-{7B, 14B, 32B, 72B}-Instruct, DeepSeek-V3, and
  GLM-4-32B-0414 as a cross-architecture control. All queried black-box in JSON mode at temperature 0.
- **Constraints:** relation type signatures (empirical and definitional), functional-relation
  consistency, and a schema-only variant derived from Wikidata property semantics with no corpus.

## Notes on reproducibility

- Numbers may shift by a fraction of a percent if you re-query the API, because provider models are
  updated over time. The cached outputs in `extractions/` are the exact ones behind the reported results.
- No API key is stored in this repository. For re-extraction, put your key in `~/.siliconflow_key`;
  the certificate itself needs no API at run time.

## Citation

```bibtex
@article{guo2026consistency,
  title   = {Consistency Certificates: Gold-Free, Provably Sound Error Bounds
             for Black-Box Large Language Model Information Extraction},
  author  = {Guo, Dongdong and Li, Jiaxuan},
  journal = {IEEE Access},
  year    = {2026},
  note    = {Under review}
}
```

## License

Released for research and reproducibility. See `LICENSE` (MIT).
