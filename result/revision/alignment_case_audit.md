# Stratified case audit of conservative entity alignment

The 67-row stratified sample in `alignment_audit_sample.csv` was inspected
against the corresponding Re-DocRED document text, normalized cluster aliases,
and the resolver's candidate-cluster status. The sample deliberately
over-represents uncheckable cases; it is a diagnostic case audit, not a
population estimate or a replacement for adjudication of all 222 excluded rows.

## Outcome categories

| Row-level category | Rows | Interpretation |
|---|---:|---|
| Unmatched endpoint only | 41 | The emitted endpoint was a descriptive phrase, number, role, adjectival form, or malformed surface form that Re-DocRED did not annotate as a compatible entity cluster. |
| Type-conflicting multiple match only | 24 | The same normalized alias or best containment target mapped to multiple gold clusters carrying different types; selecting one cluster would make the audit order-dependent. |
| Both mechanisms | 2 | One endpoint was unmatched and the other had type-conflicting candidate clusters. |

Representative unmatched endpoints include `50 states`, `VFL/AFL clubs`,
`polish invaders`, `U.S. energy policies`, `professional soccer players`, `12
volumes`, `commissioner of railroads`, and punctuation-damaged titles such as
`ca n t take my eyes off you`. These are mainly generated descriptions or
benchmark-unannotated spans, not aliases that can be assigned automatically
without judgment.

Representative ambiguity cases include `Washington v Texas`, `Mumford Sons`,
`Brigden`, `Rage Against the Machine`, and `Chachalacas`. Re-DocRED contains
more than one candidate cluster for these normalized surfaces or containment
matches, and the candidates disagree in type. The earlier string heuristic
silently chose a type; the revised procedure abstains.

## Quantified selection effect

The excluded share is 222/2,769 (8.0%) overall, but it is not uniform. It ranges
from 5.2% to 11.6% by model and from 0% to 25.0% by relation. P17 (2/8), P527
(71/292), and P569 (4/19) have the largest observed rates at 25.0%, 24.3%, and
21.1%. Excluded violations come from outputs containing 17.0 relations on
average, compared with 15.6 for retained violations. Exact stratum counts and
rates are in `alignment_selection_effect.csv`.

## Consequence for retrospective validation

The revised alignment is intentionally conservative. It increases excluded
empirical-signature violations from 188 to 222, but removes arbitrary cluster
choice as a source of apparent relation errors. Runtime certificate firing and
the gold-free lower bound do not use this alignment layer; only retrospective
validation, taxonomy, and tightness analyses do. The checkable tally is not
extrapolated to excluded cases. The separate strict gold-ID-anchored ablation
checks only emitted names with one exact annotated-cluster match
(1,961/1,961 same-corpus validations). The author-only 222-row evidence sheet
supports any further human adjudication without changing the reported analysis.
