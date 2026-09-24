# -*- coding: utf-8 -*-
"""Retrospectively validate candidate functional constraints on Re-DocRED.

The runtime certificate is gold-free.  This script uses gold cluster identifiers
only to test whether each emitted functional clash contains at least one spurious
relation assertion.  Its output documents why functional candidates are excluded
from the certified bounds in the paper.
"""
import csv
import sys
from collections import Counter

from analyze import COMMON, DOCS, USABLE_MODELS, load
from common import align_gold_entity, find_functional_violations, gold_relation_ids


def validate(model):
    counts = Counter()
    by_relation = Counter()
    for index in COMMON:
        extraction = load(model, index)
        gold_relations = gold_relation_ids(DOCS[index])
        for violation in find_functional_violations(extraction):
            head = align_gold_entity(violation["h"], DOCS[index])
            tail_a = align_gold_entity(violation["t"], DOCS[index])
            tail_b = align_gold_entity(violation["t2"], DOCS[index])
            pid = violation["pid"]
            if not head["candidate_ids"] or not tail_a["candidate_ids"] or not tail_b["candidate_ids"]:
                counts["uncheckable"] += 1
                by_relation[(pid, "uncheckable")] += 1
                continue

            def present(tail):
                return any(
                    (head_id, pid, tail_id) in gold_relations
                    for head_id in head["candidate_ids"]
                    for tail_id in tail["candidate_ids"]
                )

            status = "disagreed" if present(tail_a) and present(tail_b) else "validated"
            counts[status] += 1
            by_relation[(pid, status)] += 1
    return counts, by_relation


def main():
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["model", "relation", "validated", "disagreed", "checkable", "uncheckable", "validation_rate"])
    pooled = Counter()
    pooled_relation = Counter()
    for model in USABLE_MODELS:
        counts, by_relation = validate(model)
        pooled.update(counts)
        pooled_relation.update(by_relation)
        relations = sorted({pid for pid, _ in by_relation})
        for pid in relations:
            good = by_relation[(pid, "validated")]
            bad = by_relation[(pid, "disagreed")]
            uncheckable = by_relation[(pid, "uncheckable")]
            writer.writerow([model, pid, good, bad, good + bad, uncheckable,
                             f"{good / (good + bad):.6f}" if good + bad else ""])
    for pid in sorted({pid for pid, _ in pooled_relation}):
        good = pooled_relation[(pid, "validated")]
        bad = pooled_relation[(pid, "disagreed")]
        uncheckable = pooled_relation[(pid, "uncheckable")]
        writer.writerow(["ALL", pid, good, bad, good + bad, uncheckable,
                         f"{good / (good + bad):.6f}" if good + bad else ""])
    good, bad = pooled["validated"], pooled["disagreed"]
    writer.writerow(["ALL", "ALL", good, bad, good + bad, pooled["uncheckable"],
                     f"{good / (good + bad):.6f}"])


if __name__ == "__main__":
    main()
