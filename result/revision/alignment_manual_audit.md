# Manual audit of conservative entity alignment

We manually inspected the 67-row stratified sample in `alignment_audit_sample.csv` against the
corresponding Re-DocRED document text and cluster aliases. The sample deliberately over-represents
uncheckable cases; it is a diagnostic audit, not a population estimate.

## Outcome categories

| Row-level category | Rows | Interpretation |
|---|---:|---|
| Unmatched endpoint only | 41 | The model emitted a descriptive phrase, number, role, adjectival form, or malformed surface form that Re-DocRED did not annotate as a compatible entity cluster. |
| Type-conflicting multiple match only | 24 | The same normalized alias or containment target mapped to multiple gold clusters carrying different types; selecting one cluster would make the audit order-dependent. |
| Both mechanisms | 2 | One endpoint was unmatched and the other had type-conflicting candidate clusters. |

Representative unmatched endpoints include `50 states`, `VFL/AFL clubs`, `polish invaders`,
`U.S. energy policies`, `professional soccer players`, `12 volumes`, `commissioner of railroads`,
and punctuation-damaged titles such as `ca n t take my eyes off you`. These are mostly model-created
descriptions or benchmark-unannotated spans, not clear aliases that the resolver simply overlooked.

Representative ambiguity cases include `Washington v Texas`, `Mumford Sons`, `Brigden`,
`Rage Against the Machine`, and `Chachalacas`. Re-DocRED contains more than one candidate cluster
for these normalized surfaces or containment matches, and the candidates disagree in type. The
submitted string heuristic silently chose a type; the revised procedure abstains.

## Consequence for the soundness audit

The revised alignment is intentionally conservative. It increases excluded empirical-signature
violations from 188 to 222, but removes arbitrary cluster choice as a source of apparent relation
errors. Runtime certificate firing and the gold-free lower bound do not use this alignment layer;
only the retrospective soundness, taxonomy, and tightness analyses do. A gold-identifier oracle
ablation is equivalent to retaining all compatible candidate cluster identifiers for relation
membership and requiring type agreement across them, which is the revised implementation.
