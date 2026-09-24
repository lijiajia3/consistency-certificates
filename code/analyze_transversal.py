# -*- coding: utf-8 -*-
"""Compare exact packing and exact transversal certificates on cached outputs."""
import csv
import sys

from analyze import COMMON, SIGS, USABLE_MODELS, load
from certificate import maximum_disjoint_lower_bound, minimum_hitting_set_lower_bound
from common import find_violations


def main():
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow([
        "model", "document_model_pairs", "packing_total", "transversal_total",
        "pairs_tightened", "maximum_increment",
    ])
    pooled = [0, 0, 0, 0, 0]
    for model in USABLE_MODELS:
        packing_total = transversal_total = pairs_tightened = maximum_increment = 0
        for index in COMMON:
            violations, _ = find_violations(load(model, index), SIGS, "empirical")
            hyperedges = [violation["he"] for violation in violations]
            packing = maximum_disjoint_lower_bound(hyperedges)
            transversal = minimum_hitting_set_lower_bound(hyperedges)
            packing_total += packing
            transversal_total += transversal
            pairs_tightened += transversal > packing
            maximum_increment = max(maximum_increment, transversal - packing)
        writer.writerow([
            model, len(COMMON), packing_total, transversal_total,
            pairs_tightened, maximum_increment,
        ])
        pooled[0] += len(COMMON)
        pooled[1] += packing_total
        pooled[2] += transversal_total
        pooled[3] += pairs_tightened
        pooled[4] = max(pooled[4], maximum_increment)
    writer.writerow(["ALL", *pooled])


if __name__ == "__main__":
    main()
