#!/usr/bin/env python3
"""Analyze certificate/self-consistency overlap for one or more models."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import beta

from common import NAME2PID, REL_NAME, ROOT, find_violations, norm, validate_against_gold


ALL_MODELS = [
    "Qwen/Qwen2.5-14B-Instruct",
    "Qwen/Qwen2.5-32B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "deepseek-ai/DeepSeek-V3",
    "THUDM/GLM-4-32B-0414",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="Qwen/Qwen2.5-32B-Instruct")
    parser.add_argument("--all-models", action="store_true")
    parser.add_argument("--documents", type=int, default=50)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--require-complete", action="store_true")
    return parser.parse_args()


def safe(model: str) -> str:
    return model.replace("/", "__")


def load(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def relation_key(relation: dict):
    return (
        norm(relation.get("head")),
        NAME2PID.get(relation.get("relation")),
        norm(relation.get("tail")),
    )


def interval(successes: int, trials: int) -> tuple[float, float]:
    if not trials:
        return math.nan, math.nan
    low = 0.0 if successes == 0 else float(beta.ppf(0.025, successes, trials - successes + 1))
    high = 1.0 if successes == trials else float(beta.ppf(0.975, successes + 1, trials - successes))
    return low, high


def analyze_model(model: str, documents: int, samples: int) -> tuple[dict, list[dict]]:
    docs = json.load(open(Path(ROOT) / "data" / "redocred_dev_300.json"))[:documents]
    signatures = json.load(open(Path(ROOT) / "data" / "relations.json"))
    recurrence = []
    per_relation = defaultdict(list)
    complete_documents = 0
    missing_samples = 0
    for index, doc in enumerate(docs):
        baseline = load(Path(ROOT) / "result" / "extractions" / safe(model) / f"{index:04d}.json")
        decodes = [
            load(Path(ROOT) / "result" / "resample" / safe(model) / f"{index:04d}_{sample}.json")
            for sample in range(samples)
        ]
        valid_decodes = [decode for decode in decodes if decode and not decode.get("_error")]
        if not baseline or baseline.get("_error") or len(valid_decodes) != samples:
            missing_samples += samples - len(valid_decodes)
            continue
        complete_documents += 1
        relation_sets = [
            {
                relation_key(relation)
                for relation in decode.get("relations", [])
                if isinstance(relation, dict) and relation_key(relation)[1]
            }
            for decode in valid_decodes
        ]
        violations, entity_types = find_violations(baseline, signatures, "empirical")
        violations, _ = validate_against_gold(violations, entity_types, doc)
        for violation in violations:
            if not violation["sound"]:
                continue
            key = (violation["h"], violation["pid"], violation["t"])
            frequency = sum(key in relation_set for relation_set in relation_sets)
            recurrence.append(frequency)
            per_relation[violation["pid"]].append(frequency)

    stable = sum(frequency >= math.ceil(samples / 2) for frequency in recurrence)
    low, high = interval(stable, len(recurrence))
    summary = {
        "model": model,
        "requested_documents": documents,
        "complete_documents": complete_documents,
        "samples_per_document": samples,
        "missing_or_failed_samples": missing_samples,
        "certified_errors": len(recurrence),
        "stable_certified_errors": stable,
        "stable_fraction": stable / len(recurrence) if recurrence else None,
        "stable_ci95_lower": low,
        "stable_ci95_upper": high,
        **{f"recurrence_{frequency}": recurrence.count(frequency) for frequency in range(samples + 1)},
    }
    relation_rows = []
    for pid, values in sorted(per_relation.items()):
        relation_stable = sum(value >= math.ceil(samples / 2) for value in values)
        relation_rows.append({
            "model": model,
            "pid": pid,
            "relation": REL_NAME.get(pid, pid),
            "certified_errors": len(values),
            "stable_errors": relation_stable,
            "stable_fraction": relation_stable / len(values),
            **{f"recurrence_{frequency}": values.count(frequency) for frequency in range(samples + 1)},
        })
    return summary, relation_rows


def main() -> None:
    args = parse_args()
    models = ALL_MODELS if args.all_models else [value.strip() for value in args.models.split(",") if value.strip()]
    summaries = []
    relation_rows = []
    for model in models:
        summary, rows = analyze_model(model, args.documents, args.samples)
        summaries.append(summary)
        relation_rows.extend(rows)
        if args.require_complete and summary["complete_documents"] != args.documents:
            raise SystemExit(
                f"Incomplete resample cache for {model}: "
                f"{summary['complete_documents']}/{args.documents} complete documents"
            )

    output_dir = Path(ROOT) / "result" / "revision"
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "self_consistency_by_model.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    if relation_rows:
        with (output_dir / "self_consistency_by_relation.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(relation_rows[0]))
            writer.writeheader()
            writer.writerows(relation_rows)

    for summary in summaries:
        print(
            f"{summary['model']}: complete={summary['complete_documents']}/{summary['requested_documents']} "
            f"stable={summary['stable_certified_errors']}/{summary['certified_errors']} "
            f"= {summary['stable_fraction']:.1%}" if summary["stable_fraction"] is not None else
            f"{summary['model']}: no complete certified cases"
        )
        distribution = ", ".join(
            f"{frequency}/{args.samples}:{summary[f'recurrence_{frequency}']}"
            for frequency in range(args.samples + 1)
        )
        print("  recurrence", distribution)
    print("SELF_CONSISTENCY_ANALYSIS_OK")


if __name__ == "__main__":
    main()
