#!/usr/bin/env python3
"""Gold-ID-anchored alignment ablation on existing Re-DocRED decodes.

An emitted name receives a gold identifier only when its normalized surface
matches aliases in exactly one annotated entity cluster.  This is a genuine
gold-ID condition on that subset, not an oracle for novel generated mentions.
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

from analyze_revision import (
    COMMON, DOCS, EMPIRICAL, MODEL_LABEL, MODELS, OUT, SCHEMA,
    derive_signatures, load, valid_output,
)
from common import find_violations, gold_relation_ids, norm, validate_against_gold


def unique_exact_gold_id(name, document):
    matches = [
        index for index, cluster in enumerate(document["vertexSet"])
        if any(norm(mention.get("name")) == norm(name) for mention in cluster)
    ]
    return matches[0] if len(matches) == 1 else None


def accumulate(setting, partitions, counts):
    for signatures, indices in partitions:
        for model in MODELS:
            for index in indices:
                extraction = load(model, index)
                if not valid_output(extraction):
                    continue
                document = DOCS[index]
                gold_relations = gold_relation_ids(document)
                violations, entity_types = find_violations(extraction, signatures, "empirical")
                violations, _ = validate_against_gold(violations, entity_types, document)
                for violation in violations:
                    row = counts[(setting, MODEL_LABEL[model])]
                    row["all_violations"] += 1
                    if violation["checkable"]:
                        row["conservative_checkable"] += 1
                        row["conservative_validated"] += int(violation["sound"])
                    head_id = unique_exact_gold_id(violation["h"], document)
                    tail_id = unique_exact_gold_id(violation["t"], document)
                    if head_id is None or tail_id is None:
                        if violation["checkable"]:
                            row["other_checkable"] += 1
                            row["other_validated"] += int(violation["sound"])
                        else:
                            row["no_unique_gold_id"] += 1
                        continue
                    row["exact_unique_checkable"] += 1
                    head_type = document["vertexSet"][head_id][0]["type"]
                    tail_type = document["vertexSet"][tail_id][0]["type"]
                    sound = (violation["ht"] != head_type or
                             violation["tt"] != tail_type or
                             (head_id, violation["pid"], tail_id) not in gold_relations)
                    row["exact_unique_validated"] += int(sound)
                    # The conservative resolver always retains a unique exact
                    # match, so this should be the same gold judgement.
                    assert violation["checkable"] and violation["sound"] == sound


def main():
    even = [index for index in range(len(DOCS)) if index % 2 == 0]
    odd = [index for index in range(len(DOCS)) if index % 2 == 1]
    settings = {
        "in_source": [(EMPIRICAL, COMMON)],
        "holdout": [(derive_signatures(even), odd), (derive_signatures(odd), even)],
        "schema_only": [(SCHEMA, list(range(len(DOCS))))],
    }
    counts = defaultdict(Counter)
    for setting, partitions in settings.items():
        accumulate(setting, partitions, counts)

    columns = [
        "setting", "model", "all_violations", "conservative_checkable",
        "conservative_validated", "exact_unique_checkable",
        "exact_unique_validated", "other_checkable", "other_validated",
        "no_unique_gold_id",
    ]
    rows = []
    for setting in settings:
        for label in list(MODEL_LABEL.values()) + ["ALL"]:
            if label == "ALL":
                counter = sum((counts[(setting, name)] for name in MODEL_LABEL.values()), Counter())
            else:
                counter = counts[(setting, label)]
            row = {"setting": setting, "model": label}
            row.update({key: counter[key] for key in columns[2:]})
            assert row["all_violations"] == (row["exact_unique_checkable"] +
                                               row["other_checkable"] +
                                               row["no_unique_gold_id"])
            assert row["conservative_checkable"] == (row["exact_unique_checkable"] +
                                                       row["other_checkable"])
            rows.append(row)
    path = Path(OUT) / "gold_id_anchor_ablation.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        if row["model"] == "ALL":
            print(row)


if __name__ == "__main__":
    main()
