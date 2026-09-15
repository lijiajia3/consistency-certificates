"""SciERC adapter for independent consistency-certificate validation."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from certificate import maximum_disjoint_lower_bound
from common import ROOT, norm


SCIERC_TYPES = ["Task", "Method", "Metric", "Material", "OtherScientificTerm", "Generic"]
SCIERC_RELATIONS = [
    "COMPARE",
    "CONJUNCTION",
    "EVALUATE-FOR",
    "FEATURE-OF",
    "HYPONYM-OF",
    "PART-OF",
    "USED-FOR",
]
RELATION_LOOKUP = {re.sub(r"[^a-z]", "", relation.lower()): relation for relation in SCIERC_RELATIONS}


def load_split(split: str) -> list[dict]:
    path = Path(ROOT) / "data" / "scierc" / f"{split}.json"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def document_text(doc: dict) -> str:
    return " ".join(" ".join(sentence) for sentence in doc["sentences"])


def build_prompt(text: str) -> str:
    types = ", ".join(SCIERC_TYPES)
    relations = "\n".join(f"- {relation}" for relation in SCIERC_RELATIONS)
    return (
        "Extract scientific entities and semantic relations from the abstract. "
        "Return one JSON object with arrays named entities and relations. "
        f'Each entity must have the form {{"name": str, "type": one of [{types}]}}. '
        "Each relation must have head and tail equal to entity names and relation equal to one "
        f"of the following labels:\n{relations}\nAbstract:\n{text}"
    )


def relation_label(value) -> str | None:
    key = re.sub(r"[^a-z]", "", str(value or "").lower())
    return RELATION_LOOKUP.get(key)


def _tokens(doc: dict) -> list[str]:
    return [token for sentence in doc["sentences"] for token in sentence]


def gold_clusters(doc: dict) -> dict:
    """Build entity clusters, types, and cluster-level gold relations."""
    tokens = _tokens(doc)
    span_types = {}
    for sentence in doc.get("ner", []):
        for start, end, entity_type in sentence:
            span_types[(start, end)] = entity_type

    coreference = [set(map(tuple, cluster)) for cluster in doc.get("clusters", [])]
    covered = set().union(*coreference) if coreference else set()
    coreference.extend([{span} for span in span_types if span not in covered])

    clusters = []
    span_to_cluster = {}
    for cluster_id, spans in enumerate(coreference):
        annotated = sorted(span for span in spans if span in span_types)
        if not annotated:
            continue
        types = {span_types[span] for span in annotated}
        aliases = {
            norm(" ".join(tokens[start:end + 1]))
            for start, end in annotated
        }
        new_id = len(clusters)
        clusters.append({
            "spans": tuple(annotated),
            "aliases": tuple(sorted(alias for alias in aliases if alias)),
            "types": tuple(sorted(types)),
            "gold_type": next(iter(types)) if len(types) == 1 else None,
        })
        for span in annotated:
            span_to_cluster[span] = new_id

    relations = set()
    for sentence in doc.get("relations", []):
        for h_start, h_end, t_start, t_end, label in sentence:
            head = span_to_cluster.get((h_start, h_end))
            tail = span_to_cluster.get((t_start, t_end))
            if head is not None and tail is not None:
                relations.add((head, label, tail))
    return {"clusters": clusters, "relations": relations}


def align_entity(name: str, gold: dict) -> dict:
    query = norm(name)
    exact = [
        index for index, cluster in enumerate(gold["clusters"])
        if query in cluster["aliases"]
    ]
    candidates = exact
    mode = "exact"
    if not candidates and len(query) >= 4:
        scores = {}
        for index, cluster in enumerate(gold["clusters"]):
            lengths = [
                len(alias) for alias in cluster["aliases"]
                if len(alias) >= 4 and (query in alias or alias in query)
            ]
            if lengths:
                scores[index] = max(lengths)
        if scores:
            best = max(scores.values())
            candidates = [index for index, score in scores.items() if score == best]
            mode = "containment"
    candidates = tuple(sorted(candidates))
    if not candidates:
        return {"candidate_ids": (), "gold_type": None, "status": "unmatched"}
    types = {gold["clusters"][index]["gold_type"] for index in candidates}
    types.discard(None)
    if len(types) != 1:
        return {"candidate_ids": candidates, "gold_type": None, "status": f"{mode}_ambiguous_type"}
    return {
        "candidate_ids": candidates,
        "gold_type": next(iter(types)),
        "status": f"{mode}_{'multiple' if len(candidates) > 1 else 'unique'}",
    }


def derive_signatures(docs: list[dict]) -> dict[str, set[tuple[str, str]]]:
    signatures = defaultdict(set)
    for doc in docs:
        gold = gold_clusters(doc)
        for head, relation, tail in gold["relations"]:
            head_type = gold["clusters"][head]["gold_type"]
            tail_type = gold["clusters"][tail]["gold_type"]
            if head_type and tail_type:
                signatures[relation].add((head_type, tail_type))
    return dict(signatures)


def find_violations(extraction: dict, signatures: dict[str, set[tuple[str, str]]]):
    entity_types = {
        norm(entity.get("name")): entity.get("type")
        for entity in extraction.get("entities", [])
        if isinstance(entity, dict)
        and entity.get("name")
        and entity.get("type") in SCIERC_TYPES
    }
    violations = []
    for relation in extraction.get("relations", []):
        if not isinstance(relation, dict):
            continue
        label = relation_label(relation.get("relation"))
        head, tail = norm(relation.get("head")), norm(relation.get("tail"))
        if not label or head not in entity_types or tail not in entity_types:
            continue
        pair = (entity_types[head], entity_types[tail])
        if pair in signatures.get(label, set()):
            continue
        violations.append({
            "relation": label,
            "head": head,
            "tail": tail,
            "head_type": entity_types[head],
            "tail_type": entity_types[tail],
            "he": frozenset({f"E:{head}", f"E:{tail}", f"R:{head}|{label}|{tail}"}),
        })
    return violations, entity_types


def validate(extraction: dict, doc: dict, signatures: dict[str, set[tuple[str, str]]]) -> dict:
    gold = gold_clusters(doc)
    violations, entity_types = find_violations(extraction, signatures)
    for violation in violations:
        head = align_entity(violation["head"], gold)
        tail = align_entity(violation["tail"], gold)
        violation["head_alignment"] = head["status"]
        violation["tail_alignment"] = tail["status"]
        violation["checkable"] = head["gold_type"] is not None and tail["gold_type"] is not None
        violation["head_wrong"] = head["gold_type"] is not None and head["gold_type"] != violation["head_type"]
        violation["tail_wrong"] = tail["gold_type"] is not None and tail["gold_type"] != violation["tail_type"]
        relation_present = any(
            (head_id, violation["relation"], tail_id) in gold["relations"]
            for head_id in head["candidate_ids"]
            for tail_id in tail["candidate_ids"]
        )
        violation["relation_spurious"] = violation["checkable"] and not relation_present
        violation["sound"] = violation["checkable"] and (
            violation["head_wrong"] or violation["tail_wrong"] or violation["relation_spurious"]
        )

    errors = []
    for name, emitted_type in entity_types.items():
        aligned = align_entity(name, gold)
        if aligned["gold_type"] is not None and aligned["gold_type"] != emitted_type:
            errors.append(f"E:{name}")
    seen_relations = set()
    for relation in extraction.get("relations", []):
        if not isinstance(relation, dict):
            continue
        label = relation_label(relation.get("relation"))
        head, tail = norm(relation.get("head")), norm(relation.get("tail"))
        key = (head, label, tail)
        if not label or key in seen_relations:
            continue
        seen_relations.add(key)
        head_alignment = align_entity(head, gold)
        tail_alignment = align_entity(tail, gold)
        if not head_alignment["candidate_ids"] or not tail_alignment["candidate_ids"]:
            continue
        if not any(
            (head_id, label, tail_id) in gold["relations"]
            for head_id in head_alignment["candidate_ids"]
            for tail_id in tail_alignment["candidate_ids"]
        ):
            errors.append(f"R:{head}|{label}|{tail}")

    checkable = [violation for violation in violations if violation["checkable"]]
    return {
        "violations": violations,
        "checkable": len(checkable),
        "sound": sum(violation["sound"] for violation in checkable),
        "uncheckable": len(violations) - len(checkable),
        "bound": maximum_disjoint_lower_bound(violation["he"] for violation in violations),
        "checkable_bound": maximum_disjoint_lower_bound(violation["he"] for violation in checkable),
        "gold_errors": len(errors),
        "theorem_checkable": maximum_disjoint_lower_bound(violation["he"] for violation in checkable) <= len(errors),
    }
