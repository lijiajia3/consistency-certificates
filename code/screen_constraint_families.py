#!/usr/bin/env python3
"""Measure candidate functional-rule gain without treating it as certified.

The other proposed families (symmetry, transitivity, coreference) cannot yield
an emitted-item error certificate from these outputs alone; see the companion
methodological screen.  Here we quantify the only instantiated candidate family.
"""

import csv
from collections import Counter

from analyze_revision import COMMON, DOCS, EMPIRICAL, MODELS, OUT, load
from certificate import maximum_disjoint_lower_bound
from common import find_functional_violations, find_violations


def main():
    per_relation = {}
    pooled = Counter()
    for model in MODELS:
        for index in COMMON:
            extraction = load(model, index)
            base, _ = find_violations(extraction, EMPIRICAL, "empirical")
            base_edges = [violation["he"] for violation in base]
            base_bound = maximum_disjoint_lower_bound(base_edges)
            candidates = find_functional_violations(extraction)
            candidate_edges = [violation["he"] for violation in candidates]
            pooled["raw_increment_over_empirical"] += (
                maximum_disjoint_lower_bound(base_edges + candidate_edges) - base_bound
            )
            for pid in sorted({violation["pid"] for violation in candidates}):
                selected = [violation["he"] for violation in candidates if violation["pid"] == pid]
                row = per_relation.setdefault(pid, Counter())
                row["clashes"] += len(selected)
                row["documents_with_clashes"] += 1
                row["raw_increment_over_empirical"] += (
                    maximum_disjoint_lower_bound(base_edges + selected) - base_bound
                )
    validation = {}
    with (OUT / "functional_validation.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["model"] == "ALL":
                validation[row["relation"]] = row
    columns = ["family", "relation", "clashes", "documents_with_clashes",
               "raw_increment_over_empirical", "gold_checkable", "validated",
               "disagreed", "uncheckable", "certified_gain"]
    rows = []
    for pid, count in sorted(per_relation.items()):
        val = validation[pid]
        rows.append({
            "family": "candidate_functional", "relation": pid,
            "clashes": count["clashes"],
            "documents_with_clashes": count["documents_with_clashes"],
            "raw_increment_over_empirical": count["raw_increment_over_empirical"],
            "gold_checkable": val["checkable"], "validated": val["validated"],
            "disagreed": val["disagreed"], "uncheckable": val["uncheckable"],
            "certified_gain": 0,
        })
    rows.append({
        "family": "candidate_functional", "relation": "ALL",
        "clashes": sum(row["clashes"] for row in rows),
        "documents_with_clashes": "not_additive",
        "raw_increment_over_empirical": pooled["raw_increment_over_empirical"],
        "gold_checkable": validation["ALL"]["checkable"],
        "validated": validation["ALL"]["validated"],
        "disagreed": validation["ALL"]["disagreed"],
        "uncheckable": validation["ALL"]["uncheckable"],
        "certified_gain": 0,
    })
    with (OUT / "candidate_family_screen.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
