#!/usr/bin/env python3
"""Reviewer-2 revision analyses over the released cached Re-DocRED outputs.

The script writes machine-readable tables and a concise Markdown report under
``result/revision``.  Runtime certificate quantities use all conflict
hyperedges; comparisons with gold use only violations whose endpoints can be
checked through ambiguity-aware gold entity-cluster alignment.
"""

from __future__ import annotations

import csv
import json
import math
import os
import random
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path

import numpy as np
from scipy.stats import beta, spearmanr

from certificate import hypergraph_stats, maximum_disjoint_lower_bound
from common import (
    NAME2PID,
    REL_NAME,
    ROOT,
    TYPES,
    align_gold_entity,
    find_violations,
    gold_error_records,
    gold_relation_ids,
    norm,
    validate_against_gold,
)


MODELS = [
    "Qwen/Qwen2.5-14B-Instruct",
    "Qwen/Qwen2.5-32B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "deepseek-ai/DeepSeek-V3",
]
MODEL_LABEL = {
    "Qwen/Qwen2.5-14B-Instruct": "Qwen2.5-14B",
    "Qwen/Qwen2.5-32B-Instruct": "Qwen2.5-32B",
    "Qwen/Qwen2.5-72B-Instruct": "Qwen2.5-72B",
    "deepseek-ai/DeepSeek-V3": "DeepSeek-V3",
}
CONSOLIDATED_MODELS = [
    "Qwen/Qwen2.5-7B-Instruct",
    *MODELS,
    "THUDM/GLM-4-32B-0414",
]
CONSOLIDATED_LABEL = {
    **MODEL_LABEL,
    "Qwen/Qwen2.5-7B-Instruct": "Qwen2.5-7B",
    "THUDM/GLM-4-32B-0414": "GLM-4-32B",
}
DOCS = json.load(open(Path(ROOT) / "data" / "redocred_dev_300.json"))
EMPIRICAL = json.load(open(Path(ROOT) / "data" / "relations.json"))
OUT = Path(ROOT) / "result" / "revision"


SCHEMA_TYPE_SETS = {
    "P131": ({"LOC", "ORG", "MISC", "PER"}, {"LOC"}),
    "P17": ({"LOC", "ORG", "MISC", "PER"}, {"LOC"}),
    "P27": ({"PER"}, {"LOC"}),
    "P150": ({"LOC"}, {"LOC"}),
    "P800": ({"PER", "ORG"}, {"MISC", "ORG"}),
    "P527": ({"MISC", "ORG", "LOC"}, {"MISC", "ORG", "LOC", "PER"}),
    "P361": ({"MISC", "ORG", "LOC", "PER"}, {"MISC", "ORG", "LOC"}),
    "P175": ({"MISC"}, {"PER", "ORG"}),
    "P577": ({"MISC", "ORG"}, {"TIME"}),
    "P1344": ({"PER", "ORG"}, {"MISC", "ORG"}),
    "P710": ({"MISC", "ORG"}, {"PER", "ORG"}),
    "P463": ({"PER", "ORG"}, {"ORG"}),
    "P1001": ({"MISC", "ORG", "LOC"}, {"LOC", "ORG"}),
    "P495": ({"MISC", "ORG", "PER"}, {"LOC"}),
    "P569": ({"PER"}, {"TIME"}),
    "P161": ({"MISC"}, {"PER"}),
    "P571": ({"ORG", "MISC", "LOC"}, {"TIME"}),
    "P264": ({"PER", "ORG", "MISC"}, {"ORG"}),
}
SCHEMA = {
    pid: {"signatures": [list(pair) for pair in product(heads, tails)]}
    for pid, (heads, tails) in SCHEMA_TYPE_SETS.items()
}


def safe(model: str) -> str:
    return model.replace("/", "__")


def load(model: str, index: int):
    path = Path(ROOT) / "result" / "extractions" / safe(model) / f"{index:04d}.json"
    if not path.exists():
        return None
    try:
        return json.load(open(path))
    except (OSError, json.JSONDecodeError):
        return None


def valid_output(extraction) -> bool:
    if extraction is None or extraction.get("_error"):
        return False
    entities = [
        entity for entity in extraction.get("entities", [])
        if isinstance(entity, dict) and entity.get("name") and entity.get("type") in TYPES
    ]
    return bool(entities or extraction.get("relations"))


COMMON = [
    index for index in range(len(DOCS))
    if all(valid_output(load(model, index)) for model in MODELS)
]


def clopper_pearson(successes: int, trials: int, alpha: float = 0.05) -> tuple[float, float]:
    if trials == 0:
        return math.nan, math.nan
    lower = 0.0 if successes == 0 else float(beta.ppf(alpha / 2, successes, trials - successes + 1))
    upper = 1.0 if successes == trials else float(beta.ppf(1 - alpha / 2, successes + 1, trials - successes))
    return lower, upper


def write_csv(name: str, rows: list[dict]) -> None:
    path = OUT / name
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def emitted_relations(extraction) -> set[tuple[str, str, str]]:
    return {
        (norm(relation.get("head")), NAME2PID.get(relation.get("relation")),
         norm(relation.get("tail")))
        for relation in extraction.get("relations", [])
        if isinstance(relation, dict) and NAME2PID.get(relation.get("relation"))
    }


def raw_cross_model_disagreement(model: str, index: int) -> float:
    target = emitted_relations(load(model, index))
    scores = []
    for other in MODELS:
        if other == model:
            continue
        comparison = emitted_relations(load(other, index))
        union = target | comparison
        scores.append(1 - len(target & comparison) / len(union) if union else 0.0)
    return float(np.mean(scores))


def derive_signatures(indices: list[int]) -> dict:
    signatures = defaultdict(set)
    for index in indices:
        doc = DOCS[index]
        types = [cluster[0]["type"] for cluster in doc["vertexSet"]]
        for label in doc.get("labels", []):
            if label["r"] in EMPIRICAL:
                signatures[label["r"]].add((types[label["h"]], types[label["t"]]))
    return {
        pid: {"signatures": [list(pair) for pair in sorted(pairs)]}
        for pid, pairs in signatures.items()
    }


def document_rows() -> tuple[list[dict], list[dict], Counter]:
    rows = []
    alignment_rows = []
    taxonomy = Counter()
    for model in MODELS:
        for index in COMMON:
            extraction = load(model, index)
            relations = emitted_relations(extraction)
            violations, entity_types = find_violations(extraction, EMPIRICAL, "empirical")
            violations, _ = validate_against_gold(violations, entity_types, DOCS[index])
            checkable = [violation for violation in violations if violation["checkable"]]
            all_edges = [violation["he"] for violation in violations]
            checkable_edges = [violation["he"] for violation in checkable]
            bound = maximum_disjoint_lower_bound(all_edges)
            checkable_bound = maximum_disjoint_lower_bound(checkable_edges)
            structure = hypergraph_stats(all_edges)
            audit = gold_error_records(extraction, DOCS[index])
            errors = audit["errors"]
            involved = set().union(*(violation["he"] for violation in violations)) if violations else set()
            detectable = sum(error["item"] in involved for error in errors)
            type_errors = sum(error["category"] == "entity_type" for error in errors)
            relation_errors = sum(error["category"] == "relation_spurious" for error in errors)
            for error in errors:
                taxonomy[(model, error["category"], "detectable" if error["item"] in involved else "invisible")] += 1

            # Recall-side errors are reported separately because no emitted item
            # exists for the certificate to implicate.
            emitted_gold_ids = set()
            for head, pid, tail in relations:
                head_alignment = align_gold_entity(head, DOCS[index])
                tail_alignment = align_gold_entity(tail, DOCS[index])
                for head_id in head_alignment["candidate_ids"]:
                    for tail_id in tail_alignment["candidate_ids"]:
                        if (head_id, pid, tail_id) in gold_relation_ids(DOCS[index]):
                            emitted_gold_ids.add((head_id, pid, tail_id))
            target_gold = {
                relation for relation in gold_relation_ids(DOCS[index]) if relation[1] in REL_NAME
            }
            taxonomy[(model, "relation_omission", "out_of_scope")] += len(target_gold - emitted_gold_ids)

            row = {
                "model": MODEL_LABEL[model],
                "document_index": index,
                "title": DOCS[index].get("title", ""),
                "n_entities": audit["n_emitted_entities"],
                "n_relations": len(relations),
                "n_violations": len(violations),
                "n_checkable_violations": len(checkable),
                "n_uncheckable_violations": len(violations) - len(checkable),
                "certificate_bound": bound,
                "gold_checkable_bound": checkable_bound,
                "gold_verifiable_errors": len(errors),
                "entity_type_errors": type_errors,
                "spurious_relation_errors": relation_errors,
                "detectable_errors": detectable,
                "tightness_ratio": checkable_bound / len(errors) if errors else "",
                "conflicts_per_relation": len(violations) / len(relations) if relations else 0.0,
                "bound_per_relation": bound / len(relations) if relations else 0.0,
                "cross_model_disagreement": raw_cross_model_disagreement(model, index),
                **structure,
            }
            rows.append(row)

            gtypes = {}
            for cluster in DOCS[index]["vertexSet"]:
                for mention in cluster:
                    gtypes[norm(mention.get("name"))] = cluster[0]["type"]
            for violation in violations:
                legacy_checkable = bool(
                    # Reproduce the submitted exact/first-containment heuristic
                    # only for the requested alignment sensitivity comparison.
                    _legacy_type(violation["h"], gtypes)
                    and _legacy_type(violation["t"], gtypes)
                )
                alignment_rows.append({
                    "model": MODEL_LABEL[model],
                    "document_index": index,
                    "title": DOCS[index].get("title", ""),
                    "relation": REL_NAME.get(violation["pid"], violation["pid"]),
                    "pid": violation["pid"],
                    "head": violation["h"],
                    "tail": violation["t"],
                    "head_alignment": violation["head_alignment"],
                    "tail_alignment": violation["tail_alignment"],
                    "cluster_id_checkable": violation["checkable"],
                    "legacy_checkable": legacy_checkable,
                    "document_relations": len(relations),
                })
    return rows, alignment_rows, taxonomy


def _legacy_type(name: str, gold_types: dict[str, str]):
    if name in gold_types:
        return gold_types[name]
    if len(name) >= 4:
        for gold_name, entity_type in gold_types.items():
            if len(gold_name) >= 4 and (name in gold_name or gold_name in name):
                return entity_type
    return None


def aggregate_models(rows: list[dict]) -> list[dict]:
    output = []
    for label in MODEL_LABEL.values():
        selected = [row for row in rows if row["model"] == label]
        ratios = np.asarray([float(row["tightness_ratio"]) for row in selected if row["tightness_ratio"] != ""])
        rho = spearmanr(
            [row["certificate_bound"] for row in selected],
            [row["gold_verifiable_errors"] for row in selected],
        ).statistic
        output.append({
            "model": label,
            "documents": len(selected),
            "relations": sum(row["n_relations"] for row in selected),
            "documents_firing": sum(row["certificate_bound"] > 0 for row in selected),
            "conflict_hyperedges": sum(row["n_hyperedges"] for row in selected),
            "checkable_violations": sum(row["n_checkable_violations"] for row in selected),
            "certificate_bound_total": sum(row["certificate_bound"] for row in selected),
            "certificate_bound_mean": np.mean([row["certificate_bound"] for row in selected]),
            "certificate_bound_max": max(row["certificate_bound"] for row in selected),
            "gold_verifiable_errors": sum(row["gold_verifiable_errors"] for row in selected),
            "tightness_median": np.median(ratios),
            "tightness_q1": np.quantile(ratios, 0.25),
            "tightness_q3": np.quantile(ratios, 0.75),
            "spearman_bound_error": rho,
            "mean_maximum_vertex_degree": np.mean([row["maximum_vertex_degree"] for row in selected]),
            "maximum_vertex_degree": max(row["maximum_vertex_degree"] for row in selected),
            "mean_largest_component_hyperedges": np.mean([row["largest_component_hyperedges"] for row in selected]),
            "maximum_component_hyperedges": max(row["largest_component_hyperedges"] for row in selected),
            "mean_overlap_density": np.mean([row["hyperedge_overlap_density"] for row in selected]),
        })
    return output


def consolidated_model_results() -> list[dict]:
    """Build one six-model descriptive table under identical certificate code."""
    output = []
    for model in CONSOLIDATED_MODELS:
        indices = COMMON if model in MODELS else list(range(len(DOCS)))
        valid_documents = relations = firing = hyperedges = bound_total = errors = detectable = 0
        bound_max = 0
        for index in indices:
            extraction = load(model, index)
            if not valid_output(extraction):
                continue
            valid_documents += 1
            emitted = emitted_relations(extraction)
            relations += len(emitted)
            violations, _ = find_violations(extraction, EMPIRICAL, "empirical")
            edges = [violation["he"] for violation in violations]
            bound = maximum_disjoint_lower_bound(edges)
            audit_errors = gold_error_records(extraction, DOCS[index])["errors"]
            involved = set().union(*edges) if edges else set()
            firing += int(bound > 0)
            hyperedges += len(edges)
            bound_total += bound
            bound_max = max(bound_max, bound)
            errors += len(audit_errors)
            detectable += sum(error["item"] in involved for error in audit_errors)
        output.append({
            "model": CONSOLIDATED_LABEL[model],
            "evaluated_documents": len(indices),
            "valid_documents": valid_documents,
            "valid_output_rate": valid_documents / len(indices),
            "relations": relations,
            "documents_firing": firing,
            "conflict_hyperedges": hyperedges,
            "certificate_bound_total": bound_total,
            "certificate_bound_mean_per_evaluated_document": bound_total / len(indices),
            "certificate_bound_max": bound_max,
            "gold_verifiable_errors": errors,
            "detectable_errors": detectable,
            "detectable_fraction": detectable / errors if errors else math.nan,
        })
    return output


def volume_strata(rows: list[dict]) -> list[dict]:
    bins = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 25), (26, 10**9)]
    output = []
    for low, high in bins:
        selected = [row for row in rows if low <= row["n_relations"] <= high]
        ratios = [float(row["tightness_ratio"]) for row in selected if row["tightness_ratio"] != ""]
        output.append({
            "relation_volume_bin": f"{low}-{high}" if high < 10**9 else f"{low}+",
            "document_model_pairs": len(selected),
            "mean_relations": np.mean([row["n_relations"] for row in selected]) if selected else math.nan,
            "firing_rate": np.mean([row["certificate_bound"] > 0 for row in selected]) if selected else math.nan,
            "conflicts_per_relation": (
                sum(row["n_violations"] for row in selected) /
                max(sum(row["n_relations"] for row in selected), 1)
            ),
            "bound_per_relation": (
                sum(row["certificate_bound"] for row in selected) /
                max(sum(row["n_relations"] for row in selected), 1)
            ),
            "tightness_median": np.median(ratios) if ratios else math.nan,
            "tightness_q1": np.quantile(ratios, 0.25) if ratios else math.nan,
            "tightness_q3": np.quantile(ratios, 0.75) if ratios else math.nan,
        })
    return output


def relation_reliability() -> tuple[list[dict], list[dict], dict]:
    fold_even = [index for index in range(len(DOCS)) if index % 2 == 0]
    fold_odd = [index for index in range(len(DOCS)) if index % 2 == 1]
    even_signatures = derive_signatures(fold_even)
    odd_signatures = derive_signatures(fold_odd)
    settings = {
        "in_source": [(EMPIRICAL, COMMON)],
        "holdout": [(even_signatures, fold_odd), (odd_signatures, fold_even)],
        "schema_only": [(SCHEMA, list(range(len(DOCS))))],
    }
    counts = defaultdict(Counter)
    unsound = []
    unsafe_pairs = defaultdict(set)
    sensitivity = defaultdict(lambda: Counter(documents=0, bound=0, filtered_bound=0,
                                               affected_documents=0, repeated_unsafe_edges=0))

    for setting, partitions in settings.items():
        per_doc = []
        for signatures, indices in partitions:
            for model in MODELS:
                for index in indices:
                    extraction = load(model, index)
                    if not valid_output(extraction):
                        continue
                    violations, entity_types = find_violations(extraction, signatures, "empirical")
                    violations, _ = validate_against_gold(violations, entity_types, DOCS[index])
                    for violation in violations:
                        key = (setting, violation["pid"])
                        counts[key]["violations"] += 1
                        if violation["checkable"]:
                            counts[key]["checkable"] += 1
                            counts[key]["sound"] += int(violation["sound"])
                            counts[key]["unsound"] += int(not violation["sound"])
                            if not violation["sound"]:
                                pair = (violation["pid"], violation["ht"], violation["tt"])
                                unsafe_pairs[setting].add(pair)
                                unsound.append({
                                    "setting": setting,
                                    "model": MODEL_LABEL[model],
                                    "document_index": index,
                                    "title": DOCS[index].get("title", ""),
                                    "pid": violation["pid"],
                                    "relation": REL_NAME.get(violation["pid"], violation["pid"]),
                                    "emitted_head_type": violation["ht"],
                                    "emitted_tail_type": violation["tt"],
                                    "gold_head_type": violation["gh"],
                                    "gold_tail_type": violation["gt"],
                                    "head": violation["h"],
                                    "tail": violation["t"],
                                    "cause": (
                                        "valid type pair absent from signature-training fold"
                                        if setting == "holdout"
                                        else "ontology rule conflicts with Re-DocRED annotation policy"
                                    ),
                                })
                    per_doc.append((model, index, violations))

        for model, index, violations in per_doc:
            edges = [violation["he"] for violation in violations]
            filtered = [
                violation["he"] for violation in violations
                if (violation["pid"], violation["ht"], violation["tt"])
                not in unsafe_pairs[setting]
            ]
            bound = maximum_disjoint_lower_bound(edges)
            filtered_bound = maximum_disjoint_lower_bound(filtered)
            unsafe_count = sum(
                (violation["pid"], violation["ht"], violation["tt"])
                in unsafe_pairs[setting]
                for violation in violations
            )
            s = sensitivity[setting]
            s["documents"] += 1
            s["bound"] += bound
            s["filtered_bound"] += filtered_bound
            s["affected_documents"] += int(bound != filtered_bound)
            s["repeated_unsafe_edges"] += int(unsafe_count > 1)

    relation_rows = []
    for (setting, pid), count in sorted(counts.items()):
        lower, upper = clopper_pearson(count["sound"], count["checkable"])
        relation_rows.append({
            "setting": setting,
            "pid": pid,
            "relation": REL_NAME.get(pid, pid),
            "violations": count["violations"],
            "checkable": count["checkable"],
            "sound": count["sound"],
            "unsound": count["unsound"],
            "soundness": count["sound"] / count["checkable"] if count["checkable"] else "",
            "ci95_lower": lower,
            "ci95_upper": upper,
        })
    return relation_rows, unsound, {key: dict(value) for key, value in sensitivity.items()}


def relation_tightness() -> list[dict]:
    output = []
    for model in MODELS:
        accumulators = defaultdict(lambda: Counter(documents=0, violations=0, bound=0,
                                                    involved_errors=0, document_errors=0))
        for index in COMMON:
            extraction = load(model, index)
            violations, entity_types = find_violations(extraction, EMPIRICAL, "empirical")
            violations, _ = validate_against_gold(violations, entity_types, DOCS[index])
            error_items = {record["item"] for record in gold_error_records(extraction, DOCS[index])["errors"]}
            by_relation = defaultdict(list)
            for violation in violations:
                if violation["checkable"]:
                    by_relation[violation["pid"]].append(violation)
            for pid, relation_violations in by_relation.items():
                involved = set().union(*(violation["he"] for violation in relation_violations))
                accumulator = accumulators[pid]
                accumulator["documents"] += 1
                accumulator["violations"] += len(relation_violations)
                accumulator["bound"] += maximum_disjoint_lower_bound(
                    violation["he"] for violation in relation_violations
                )
                accumulator["involved_errors"] += len(error_items & involved)
                accumulator["document_errors"] += len(error_items)
        for pid, count in sorted(accumulators.items()):
            output.append({
                "model": MODEL_LABEL[model],
                "pid": pid,
                "relation": REL_NAME.get(pid, pid),
                **count,
                "bound_to_involved_error_ratio": count["bound"] / count["involved_errors"] if count["involved_errors"] else "",
                "bound_to_document_error_ratio": count["bound"] / count["document_errors"] if count["document_errors"] else "",
            })
    return output


def alignment_summary(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    counters = defaultdict(Counter)
    for row in rows:
        key = (row["model"], row["pid"])
        counters[key]["total"] += 1
        counters[key]["cluster_checkable"] += int(row["cluster_id_checkable"])
        counters[key]["legacy_checkable"] += int(row["legacy_checkable"])
        head_bad = "unmatched" in row["head_alignment"] or "ambiguous_type" in row["head_alignment"]
        tail_bad = "unmatched" in row["tail_alignment"] or "ambiguous_type" in row["tail_alignment"]
        if head_bad and tail_bad:
            counters[key]["both_uncheckable"] += 1
        elif head_bad:
            counters[key]["head_only_uncheckable"] += 1
        elif tail_bad:
            counters[key]["tail_only_uncheckable"] += 1
    summary = []
    for (model, pid), count in sorted(counters.items()):
        summary.append({"model": model, "pid": pid, "relation": REL_NAME.get(pid, pid), **count})

    audit_candidates = [row for row in rows if not row["cluster_id_checkable"]]
    audit_candidates.sort(key=lambda row: (row["model"], row["pid"], row["document_index"]))
    sample = []
    strata = defaultdict(list)
    for row in audit_candidates:
        category = f"{row['head_alignment']}|{row['tail_alignment']}"
        strata[(row["model"], category)].append(row)
    for key in sorted(strata):
        sample.extend(strata[key][:3])
    return summary, sample


def alignment_selection_effect(rows: list[dict]) -> list[dict]:
    """Quantify whether gold-alignment exclusions are uniform across strata."""
    strata: list[tuple[str, str, str, str, list[dict]]] = [
        ("overall", "ALL", "", "all relations", rows),
    ]
    for model in sorted({row["model"] for row in rows}):
        strata.append(("model", model, "", "all relations", [
            row for row in rows if row["model"] == model
        ]))
    for pid in sorted({row["pid"] for row in rows}):
        strata.append(("relation", pid, pid, REL_NAME.get(pid, pid), [
            row for row in rows if row["pid"] == pid
        ]))

    output = []
    for scope, group, pid, relation, selected in strata:
        excluded = [row for row in selected if not row["cluster_id_checkable"]]
        retained = [row for row in selected if row["cluster_id_checkable"]]
        output.append({
            "scope": scope,
            "group": group,
            "pid": pid,
            "relation": relation,
            "violations": len(selected),
            "checkable": len(retained),
            "uncheckable": len(excluded),
            "uncheckable_rate": len(excluded) / len(selected) if selected else math.nan,
            "mean_document_relations_uncheckable": (
                float(np.mean([row["document_relations"] for row in excluded]))
                if excluded else math.nan
            ),
            "mean_document_relations_checkable": (
                float(np.mean([row["document_relations"] for row in retained]))
                if retained else math.nan
            ),
        })
    return output


def review_budget(rows: list[dict]) -> list[dict]:
    output = []
    rng = random.Random(20260915)
    for model in MODEL_LABEL.values():
        selected = [row for row in rows if row["model"] == model]
        total_errors = sum(row["gold_verifiable_errors"] for row in selected)
        for fraction in (0.05, 0.10, 0.20):
            n_review = max(1, math.ceil(len(selected) * fraction))
            rankings = {
                "certificate": sorted(
                    selected,
                    key=lambda row: (row["certificate_bound"], row["bound_per_relation"], -row["document_index"]),
                    reverse=True,
                ),
                "cross_model_disagreement": sorted(
                    selected,
                    key=lambda row: (row["cross_model_disagreement"], -row["document_index"]),
                    reverse=True,
                ),
            }
            for method, ranking in rankings.items():
                discovered = sum(row["gold_verifiable_errors"] for row in ranking[:n_review])
                output.append({
                    "model": model,
                    "budget_fraction": fraction,
                    "documents_reviewed": n_review,
                    "method": method,
                    "errors_discovered": discovered,
                    "errors_per_document": discovered / n_review,
                    "error_recall": discovered / total_errors if total_errors else 0.0,
                    "random_ci95_lower": "",
                    "random_ci95_upper": "",
                })
            discoveries = []
            for _ in range(2000):
                sample = rng.sample(selected, n_review)
                discoveries.append(sum(row["gold_verifiable_errors"] for row in sample))
            output.append({
                "model": model,
                "budget_fraction": fraction,
                "documents_reviewed": n_review,
                "method": "random",
                "errors_discovered": np.mean(discoveries),
                "errors_per_document": np.mean(discoveries) / n_review,
                "error_recall": np.mean(discoveries) / total_errors if total_errors else 0.0,
                "random_ci95_lower": np.quantile(discoveries, 0.025),
                "random_ci95_upper": np.quantile(discoveries, 0.975),
            })
    return output


def taxonomy_rows(taxonomy: Counter) -> list[dict]:
    return [
        {"model": MODEL_LABEL[model], "error_category": category, "certificate_visibility": visibility, "count": count}
        for (model, category, visibility), count in sorted(taxonomy.items())
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, alignments, taxonomy = document_rows()
    models = aggregate_models(rows)
    consolidated = consolidated_model_results()
    volumes = volume_strata(rows)
    relations, unsound, sensitivity = relation_reliability()
    relation_tightness_rows = relation_tightness()
    alignment_counts, audit_sample = alignment_summary(alignments)
    alignment_selection = alignment_selection_effect(alignments)
    budgets = review_budget(rows)
    taxonomy_table = taxonomy_rows(taxonomy)

    write_csv("per_document.csv", rows)
    write_csv("per_model.csv", models)
    write_csv("consolidated_model_table.csv", consolidated)
    write_csv("tightness_by_volume.csv", volumes)
    write_csv("relation_reliability.csv", relations)
    write_csv("tightness_by_relation.csv", relation_tightness_rows)
    write_csv("unsound_cases.csv", unsound)
    write_csv("alignment_breakdown.csv", alignment_counts)
    write_csv("alignment_audit_sample.csv", audit_sample)
    write_csv("alignment_selection_effect.csv", alignment_selection)
    write_csv("review_budget.csv", budgets)
    write_csv("error_taxonomy.csv", taxonomy_table)
    (OUT / "constraint_sensitivity.json").write_text(
        json.dumps(sensitivity, indent=2, sort_keys=True), encoding="utf-8"
    )

    legacy_uncheckable = sum(not row["legacy_checkable"] for row in alignments)
    cluster_uncheckable = sum(not row["cluster_id_checkable"] for row in alignments)
    empirical_relation_rows = [row for row in relations if row["setting"] == "in_source"]
    holdout_unsound = sum(row["setting"] == "holdout" for row in unsound)
    schema_unsound = sum(row["setting"] == "schema_only" for row in unsound)
    summary = {
        "common_documents": len(COMMON),
        "document_model_pairs": len(rows),
        "empirical_checkable": sum(row["checkable"] for row in empirical_relation_rows),
        "empirical_unsound": sum(row["unsound"] for row in empirical_relation_rows),
        "legacy_uncheckable_violations": legacy_uncheckable,
        "cluster_id_uncheckable_violations": cluster_uncheckable,
        "alignment_selection_effect": alignment_selection,
        "holdout_unsound_cases": holdout_unsound,
        "schema_unsound_cases": schema_unsound,
        "models": models,
        "consolidated_models": consolidated,
        "constraint_sensitivity": sensitivity,
    }
    (OUT / "revision_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    report = [
        "# Reviewer 2 revision analysis",
        "",
        f"- Common evaluation set: {len(COMMON)} documents; {len(rows)} document-model pairs.",
        f"- In-source empirical audit: {summary['empirical_checkable'] - summary['empirical_unsound']}/"
        f"{summary['empirical_checkable']} sound after cluster-ID alignment.",
        f"- Submitted heuristic left {legacy_uncheckable} violations uncheckable; the ambiguity-aware "
        f"cluster-ID audit conservatively leaves {cluster_uncheckable} uncheckable.",
        f"- Hold-out/schema-only unsound cases after cluster-ID alignment: {holdout_unsound}/{schema_unsound}.",
        "",
        "## Per-model certificate and tightness",
        "",
        "| Model | Relations | Fired docs | Hyperedges | Bound | Gold errors | Median tightness | Spearman |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in models:
        report.append(
            f"| {row['model']} | {row['relations']} | {row['documents_firing']} | "
            f"{row['conflict_hyperedges']} | {row['certificate_bound_total']} | "
            f"{row['gold_verifiable_errors']} | {row['tightness_median']:.3f} | "
            f"{row['spearman_bound_error']:.3f} |"
        )
    report.extend([
        "",
        "The CSV files in this directory contain relation-level confidence intervals, exact unsound "
        "cases, volume-normalized rates, review-budget comparisons, error taxonomy, and the "
        "stratified alignment-audit sample and alignment-selection analysis.",
    ])
    (OUT / "revision_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("REVISION_ANALYSIS_OK")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
