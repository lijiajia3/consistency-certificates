# Consistency Certificates

**Gold-free, provably sound error lower bounds for black-box large language model information extraction.**

This repository contains the code, cached model outputs, and analysis scripts for the paper *"Consistency Certificates: Gold-Free, Provably Sound Error Bounds for Black-Box Large Language Model Information Extraction"* (IEEE Access, under review).

A *consistency certificate* audits a black-box extractor's own output. When the output violates a hard type-signature constraint (for example, a `date-of-birth` relation whose head is not a person), it is internally self-contradictory, so at least one extracted item is provably wrong. The largest set of mutually disjoint violations is a lower bound on the number of errors, computed from a single decode with no gold reference. The combinatorial bound itself is a classical result from database repair and consistent query answering; the contribution here is its transfer to black-box, document-level LLM information extraction, plus a multi-model, multi-source empirical characterization of what it can and cannot certify.

## Key results

| Setting | Metric | Value |
|---|---|---|
| In-sample soundness (4 models, empirical + definitional) | checkable violations that are real errors | **1904 / 1904 = 100%** |
| Hold-out signatures (disjoint document split) | out-of-sample soundness | **99.8%** (3215 / 3221) |
| Schema-only signatures (Wikidata semantics, **zero corpus**) | soundness | **98.8%** (2860 / 2894) |
| Cross-architecture control (GLM-4-32B) | soundness | **651 / 651 = 100%** |
| Firing rate (empirical signatures) | documents with a non-zero bound | **64–71%** |
| Detectable class | share of gold errors the certificate can see | **21–24%** |
| Complementarity to self-consistency | certified errors that recur across K=5 decodes | **21%** |
| Weak-model cliff | Qwen2.5-7B valid structured output | **5%** |

Soundness stays between **98.8% and 100%** as the signature source moves from the same corpus, through a disjoint split, to a fully corpus-independent schema. The theorem (`#errors ≥ maximum matching`) holds on every document and is separately verified on 2000 random conflict graphs.

## Repository layout

```
consistency_certificates/
├── common.py               # core: find_violations, disjoint_lower_bound,
│                           #       validate_against_gold, gold_maps, signatures, prompt
├── certificate.py          # theorem code + 2000-graph stress test (matching / vertex cover)
├── run_extractions.py      # concurrent, cached black-box extraction (SiliconFlow API)
├── analyze.py              # main results table (soundness, firing, detectable class)
├── run_resample.py         # E5: K=5 stochastic decodes at T=0.7
├── analyze_resample.py     # E5 analysis: self-consistency overlap
├── analyze_triage.py       # E6: per-document bound vs true error count (Spearman)
├── analyze_glm.py          # GLM-4-32B cross-architecture metrics
├── ablation_holdout.py     # two-fold hold-out signature ablation (99.8%)
├── ablation_schema.py      # schema-only (zero-corpus) signature ablation (98.8%)
├── relations.json          # empirical (head-type, tail-type) signatures for 18 relations
├── redocred_dev_300.json   # Re-DocRED dev split (300 documents; gold for validation only)
├── extractions/            # cached model outputs, one JSON per (model, document)
└── figs/                   # generated figures (.pdf, .svg, .png)
```

The manuscript LaTeX source is kept in a separate private location and is not part
of this code repository.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install requests numpy matplotlib scipy
```

Extraction calls a hosted inference API. Put your key in a file the scripts read:

```bash
echo "YOUR_SILICONFLOW_KEY" > ~/.siliconflow_key   # for run_extractions.py
echo "YOUR_SEMANTIC_SCHOLAR_KEY" > ~/.s2_key        # only for build_bib.py
```

No API key is stored in this repository, and the certificate itself needs no API at run time; it reads the cached extractions in `extractions/`.

## Reproduce

The cached extractions are included, so every number in the paper can be recomputed offline without querying any API:

```bash
python3 certificate.py          # theorem unit test + 2000-graph stress test
python3 analyze.py              # main table: soundness 1904/1904, firing, detectable class
python3 ablation_holdout.py     # hold-out signatures -> 99.8% out-of-sample soundness
python3 ablation_schema.py      # schema-only (zero-corpus) signatures -> 98.8% soundness
python3 analyze_glm.py          # GLM-4-32B cross-architecture -> 651/651 = 100%
python3 analyze_resample.py     # self-consistency overlap (21%)
python3 analyze_triage.py       # triage correlation (Spearman 0.25-0.40)
```

The generated figures are provided under `figs/`.

To re-run extraction from scratch (needs the API key above):

```bash
NDOCS=300 WORKERS=4 python3 run_extractions.py            # all models
ONLY_MODELS=GLM NDOCS=300 WORKERS=3 python3 run_extractions.py   # a single model
```

Extraction is cached per `(model, document)` and resumable; existing results are skipped.

## Data and models

- **Dataset:** [Re-DocRED](https://github.com/tonytan48/Re-DocRED) validation split. Gold annotations are used only to *validate* the certificate, never to run it.
- **Models (via SiliconFlow):** Qwen2.5-{7B, 14B, 32B, 72B}-Instruct, DeepSeek-V3, and GLM-4-32B-0414 as a cross-architecture control. All queried black-box in JSON mode at temperature 0.
- **Constraints:** relation type signatures (empirical and definitional), functional-relation consistency, and a schema-only variant derived from Wikidata property semantics with no corpus.

## Notes on reproducibility

- Numbers may shift by a fraction of a percent if you re-query the API, because provider models are updated over time. The cached outputs in `extractions/` are the exact ones behind the reported results.
- The figures under `figs/` (`.pdf`, `.svg`, `.png`) are generated from the cached extractions.

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
