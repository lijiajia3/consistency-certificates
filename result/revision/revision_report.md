# Reviewer 2 revision analysis

- Common evaluation set: 297 documents; 1188 document-model pairs.
- In-source empirical audit: 2547/2547 sound after cluster-ID alignment.
- Submitted heuristic left 188 violations uncheckable; the ambiguity-aware cluster-ID audit conservatively leaves 222 uncheckable.
- Hold-out/schema-only unsound cases after cluster-ID alignment: 6/46.

## Per-model certificate and tightness

| Model | Relations | Fired docs | Hyperedges | Bound | Gold errors | Median tightness | Spearman |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen2.5-14B | 3683 | 195 | 657 | 273 | 2909 | 0.083 | 0.327 |
| Qwen2.5-32B | 3414 | 196 | 573 | 247 | 2611 | 0.083 | 0.337 |
| Qwen2.5-72B | 4557 | 214 | 773 | 346 | 3492 | 0.083 | 0.351 |
| DeepSeek-V3 | 4185 | 218 | 752 | 297 | 3298 | 0.080 | 0.369 |

The CSV files in this directory contain relation-level confidence intervals, exact unsound cases, volume-normalized rates, review-budget comparisons, error taxonomy, and the stratified alignment-audit sample and alignment-selection analysis.
