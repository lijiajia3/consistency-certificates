#!/usr/bin/env python3
"""Analyze cached SciERC extractions with train-derived signatures."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from scipy.stats import beta

from common import ROOT
from scierc_common import derive_signatures, load_split, validate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-32B-Instruct")
    parser.add_argument("--splits", default="dev,test")
    parser.add_argument("--require-complete", action="store_true")
    return parser.parse_args()


def safe(model: str) -> str:
    return model.replace("/", "__")


def interval(successes: int, trials: int) -> tuple[float, float]:
    if not trials:
        return math.nan, math.nan
    low = 0.0 if successes == 0 else float(beta.ppf(0.025, successes, trials - successes + 1))
    high = 1.0 if successes == trials else float(beta.ppf(0.975, successes + 1, trials - successes))
    return low, high


def main() -> None:
    args = parse_args()
    signatures = derive_signatures(load_split("train"))
    output_dir = Path(ROOT) / "result" / "scierc"
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    expected = available = valid = firing = checkable = sound = uncheckable = 0
    bound = checkable_bound = errors = theorem_ok = 0
    for split in [value.strip() for value in args.splits.split(",") if value.strip()]:
        docs = load_split(split)
        expected += len(docs)
        cache_dir = output_dir / "extractions" / split / safe(args.model)
        for index, doc in enumerate(docs):
            path = cache_dir / f"{index:04d}.json"
            if not path.exists():
                continue
            available += 1
            extraction = json.loads(path.read_text(encoding="utf-8"))
            is_valid = not extraction.get("_error") and bool(
                extraction.get("entities") or extraction.get("relations")
            )
            valid += int(is_valid)
            if not is_valid:
                continue
            audit = validate(extraction, doc, signatures)
            firing += int(audit["bound"] > 0)
            checkable += audit["checkable"]
            sound += audit["sound"]
            uncheckable += audit["uncheckable"]
            bound += audit["bound"]
            checkable_bound += audit["checkable_bound"]
            errors += audit["gold_errors"]
            theorem_ok += int(audit["theorem_checkable"])
            rows.append({
                "split": split,
                "document_index": index,
                "doc_key": doc.get("doc_key", ""),
                "violations": len(audit["violations"]),
                "checkable": audit["checkable"],
                "sound": audit["sound"],
                "uncheckable": audit["uncheckable"],
                "bound": audit["bound"],
                "checkable_bound": audit["checkable_bound"],
                "gold_errors": audit["gold_errors"],
                "theorem_checkable": audit["theorem_checkable"],
            })

    complete = available == expected
    if args.require_complete and not complete:
        raise SystemExit(f"Incomplete SciERC cache: {available}/{expected}")
    low, high = interval(sound, checkable)
    summary = {
        "model": args.model,
        "expected_documents": expected,
        "available_documents": available,
        "complete": complete,
        "valid_documents": valid,
        "firing_documents": firing,
        "checkable_violations": checkable,
        "sound_violations": sound,
        "uncheckable_violations": uncheckable,
        "soundness": sound / checkable if checkable else None,
        "soundness_ci95": [low, high],
        "certificate_bound": bound,
        "checkable_bound": checkable_bound,
        "gold_verifiable_errors": errors,
        "theorem_documents_ok": theorem_ok,
    }
    name = safe(args.model)
    (output_dir / f"summary_{name}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    if rows:
        with (output_dir / f"per_document_{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print("SCIERC_ANALYSIS_OK")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
