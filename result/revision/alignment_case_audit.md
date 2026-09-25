# Stratified case audit of conservative entity alignment

The 67-row stratified sample in `alignment_audit_sample.csv` was inspected
against the corresponding Re-DocRED document text, normalized cluster aliases,
and the resolver's candidate-cluster status. Jiaxuan Li manually adjudicated
each row and recorded the decision in `gold_id_manual_audit_67.xlsx`. The sample
deliberately over-represents uncheckable cases; it is a diagnostic case audit,
not a population estimate or a replacement for adjudication of all 222 excluded
rows.

## Automatic screening categories

| Row-level category | Rows | Interpretation |
|---|---:|---|
| Unmatched endpoint only | 41 | The emitted endpoint was a descriptive phrase, number, role, adjectival form, or malformed surface form that Re-DocRED did not annotate as a compatible entity cluster. |
| Type-conflicting multiple match only | 24 | The same normalized alias or best containment target mapped to multiple gold clusters carrying different types; selecting one cluster would make the audit order-dependent. |
| Both mechanisms | 2 | One endpoint was unmatched and the other had type-conflicting candidate clusters. |

These are the automatic resolver's failure-mechanism labels. They are not the
final manual outcomes.

## Author adjudication outcomes

| Manual outcome | Rows | Interpretation |
|---|---:|---|
| Unique gold-cluster assignment | 37 | Both emitted endpoints could be assigned to one gold cluster after reading the source document. |
| No corresponding annotated entity | 29 | At least one emitted endpoint did not refer to any gold entity cluster in the document. |
| Genuine ambiguity | 1 | The gold annotation did not support a unique cluster assignment for the emitted endpoint. |

All 37 uniquely aligned rows contained at least one gold-measured error. In 36
rows, the emitted relation was absent from the gold labels. In the remaining
row, the relation was present but the model assigned the wrong type to the tail
entity. This 37/37 result applies only to the manually resolvable part of the
stratified sample and is not merged into the automated 2,547/2,547 same-corpus
tally.

Representative unmatched endpoints include `50 states`, `VFL/AFL clubs`,
`polish invaders`, `U.S. energy policies`, `professional soccer players`, `12
volumes`, `commissioner of railroads`, and punctuation-damaged titles such as
`ca n t take my eyes off you`. These are mainly generated descriptions or
benchmark-unannotated spans, not aliases that can be assigned automatically
without judgment.

The automatic ambiguity group included `Washington v Texas`, `Mumford Sons`,
`Brigden`, `Rage Against the Machine`, and `Chachalacas`. The source context and
model entity inventory resolved these cases during manual adjudication. The one
remaining ambiguity is `Kurdish`, which the gold annotation splits across
incompatible cluster uses.

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
(1,961/1,961 same-corpus validations). The completed 67-row workbook provides
the author-verified sample evidence. The separate 222-row worksheet remains
available for an optional full adjudication and is not presented as completed.
