# -*- coding: utf-8 -*-
"""Shared constants, prompt, and certificate primitives.

ROOT points to the repository root so every script works from any CWD.
"""
import json, os, re

from certificate import greedy_disjoint_lower_bound, maximum_disjoint_lower_bound

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REL_NAME = {
    "P131": "located in the administrative territorial entity", "P17": "country",
    "P27": "country of citizenship", "P150": "contains administrative territorial entity",
    "P800": "notable work", "P527": "has part", "P361": "part of", "P175": "performer",
    "P577": "publication date", "P1344": "participant in", "P710": "participant",
    "P463": "member of", "P1001": "applies to jurisdiction", "P495": "country of origin",
    "P569": "date of birth", "P161": "cast member", "P571": "inception (date founded/created)",
    "P264": "record label",
}
NAME2PID = {v: k for k, v in REL_NAME.items()}
TYPES = ["PER", "ORG", "LOC", "TIME", "NUM", "MISC"]

# Logically necessary signatures (independent of any corpus).
DEFINITIONAL = {
    "P569": {("PER", "TIME")},
    "P577": {("MISC", "TIME"), ("ORG", "TIME"), ("LOC", "TIME")},
    "P571": {("ORG", "TIME"), ("MISC", "TIME"), ("LOC", "TIME")},
    "P27": {("PER", "LOC")},
    "P19": {("PER", "LOC")}, "P20": {("PER", "LOC")},
}

# Single-valued relations: at most one value per head.
FUNCTIONAL = {"P569", "P570", "P571", "P577", "P19", "P20"}


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def doc_text(d):
    return " ".join(" ".join(s) for s in d["sents"])


def build_prompt(text):
    rels = "\n".join(f"- {v}" for v in REL_NAME.values())
    return (f"Extract a knowledge graph from the passage. Output JSON with keys "
            f'"entities" and "relations". Each entity: {{"name":str,"type":one of {TYPES}}}. '
            f'Each relation: {{"head":entity name,"relation":one of the names below,"tail":entity name}}.\n'
            f"Relation names:\n{rels}\nPassage:\n{text}")


def gold_maps(d):
    """Gold entity types and gold relation set (used for validation only)."""
    etype, names = {}, []
    for e in d["vertexSet"]:
        t = e[0]["type"]; ns = set()
        for m in e:
            etype.setdefault(norm(m["name"]), t); ns.add(norm(m["name"]))
        names.append(ns)
    rel = set()
    for l in d.get("labels", []):
        for hn in names[l["h"]]:
            for tn in names[l["t"]]:
                rel.add((hn, l["r"], tn))
    return etype, rel


def gold_relation_ids(d):
    """Gold relations keyed by entity-cluster identifiers rather than surface strings."""
    return {(label["h"], label["r"], label["t"]) for label in d.get("labels", [])}


def align_gold_entity(name, d):
    """Align one emitted name to gold entity clusters with ambiguity-aware abstention.

    Exact normalized aliases are preferred.  Otherwise, bidirectional containment
    is used for strings of at least four characters and only clusters with the
    longest matching alias are retained.  Multiple candidate clusters are safe
    when they agree on entity type; conflicting types make the alignment
    uncheckable instead of selecting an arbitrary first match.
    """
    query = norm(name)
    aliases = [
        {norm(mention.get("name")) for mention in cluster if norm(mention.get("name"))}
        for cluster in d.get("vertexSet", [])
    ]
    candidate_ids = [index for index, names in enumerate(aliases) if query in names]
    mode = "exact"

    if not candidate_ids and len(query) >= 4:
        scores = {}
        for index, names in enumerate(aliases):
            matched_lengths = [
                len(alias)
                for alias in names
                if len(alias) >= 4 and (query in alias or alias in query)
            ]
            if matched_lengths:
                scores[index] = max(matched_lengths)
        if scores:
            best = max(scores.values())
            candidate_ids = [index for index, score in scores.items() if score == best]
            mode = "containment"

    candidate_ids = tuple(sorted(candidate_ids))
    if not candidate_ids:
        return {"candidate_ids": (), "gold_type": None, "status": "unmatched"}

    gold_types = {
        d["vertexSet"][index][0]["type"]
        for index in candidate_ids
        if d["vertexSet"][index]
    }
    multiplicity = "multiple" if len(candidate_ids) > 1 else "unique"
    if len(gold_types) != 1:
        status = f"{mode}_ambiguous_type"
        gold_type = None
    else:
        status = f"{mode}_{multiplicity}"
        gold_type = next(iter(gold_types))
    return {
        "candidate_ids": candidate_ids,
        "gold_type": gold_type,
        "status": status,
    }


def gold_error_records(ext, d):
    """Return gold-verifiable emitted errors and alignment diagnostics.

    Unmatched or type-ambiguous entities are reported but are not silently
    counted as type errors.  A relation is checkable when both endpoint names
    map to at least one gold cluster; it is spurious only if no candidate cluster
    pair carries the emitted relation.
    """
    from collections import Counter

    entity_types = {
        norm(entity["name"]): entity["type"]
        for entity in ext.get("entities", [])
        if isinstance(entity, dict)
        and entity.get("type") in TYPES
        and entity.get("name")
    }
    alignments = {name: align_gold_entity(name, d) for name in entity_types}
    alignment_counts = Counter(alignment["status"] for alignment in alignments.values())
    errors = []
    for name, emitted_type in entity_types.items():
        alignment = alignments[name]
        if alignment["gold_type"] is not None and alignment["gold_type"] != emitted_type:
            errors.append({
                "item": f"E:{name}",
                "category": "entity_type",
                "name": name,
                "emitted_type": emitted_type,
                "gold_type": alignment["gold_type"],
                "alignment": alignment["status"],
            })

    relations = {
        (norm(relation.get("head")), NAME2PID.get(relation.get("relation")),
         norm(relation.get("tail")))
        for relation in ext.get("relations", [])
        if isinstance(relation, dict) and NAME2PID.get(relation.get("relation"))
    }
    gold_relations = gold_relation_ids(d)
    relation_checkable = relation_uncheckable = 0
    for head, pid, tail in relations:
        head_alignment = alignments.get(head) or align_gold_entity(head, d)
        tail_alignment = alignments.get(tail) or align_gold_entity(tail, d)
        if not head_alignment["candidate_ids"] or not tail_alignment["candidate_ids"]:
            relation_uncheckable += 1
            continue
        relation_checkable += 1
        present = any(
            (head_id, pid, tail_id) in gold_relations
            for head_id in head_alignment["candidate_ids"]
            for tail_id in tail_alignment["candidate_ids"]
        )
        if not present:
            errors.append({
                "item": f"R:{head}|{pid}|{tail}",
                "category": "relation_spurious",
                "head": head,
                "pid": pid,
                "tail": tail,
                "head_alignment": head_alignment["status"],
                "tail_alignment": tail_alignment["status"],
            })

    return {
        "errors": errors,
        "alignment_counts": dict(alignment_counts),
        "relation_checkable": relation_checkable,
        "relation_uncheckable": relation_uncheckable,
        "n_emitted_entities": len(entity_types),
        "n_emitted_relations": len(relations),
    }


def find_violations(ext, sigs, constraint="empirical"):
    """Relation-signature violations, each as a hyperedge {E:h, E:t, R:h|r|t}."""
    etype = {norm(e["name"]): e["type"] for e in ext.get("entities", [])
             if isinstance(e, dict) and e.get("type") in TYPES and e.get("name")}
    out = []
    for rel in ext.get("relations", []):
        if not isinstance(rel, dict):
            continue
        pid = NAME2PID.get(rel.get("relation"))
        h, t = norm(rel.get("head")), norm(rel.get("tail"))
        if not pid or h not in etype or t not in etype:
            continue
        if constraint == "definitional":
            if pid not in DEFINITIONAL:
                continue
            allowed = DEFINITIONAL[pid]
        else:
            if pid not in sigs:
                continue
            allowed = set(tuple(x) for x in sigs[pid]["signatures"])
        if (etype[h], etype[t]) in allowed:
            continue
        out.append({"pid": pid, "h": h, "t": t, "ht": etype[h], "tt": etype[t],
                    "he": frozenset({f"E:{h}", f"E:{t}", f"R:{h}|{pid}|{t}"})})
    return out, etype


def find_functional_violations(ext):
    """Functional-relation violations: two distinct values for one head."""
    from collections import defaultdict
    hr = defaultdict(lambda: defaultdict(set))
    for rel in ext.get("relations", []):
        if not isinstance(rel, dict):
            continue
        pid = NAME2PID.get(rel.get("relation"))
        if pid in FUNCTIONAL and rel.get("head") and rel.get("tail"):
            hr[norm(rel.get("head"))][pid].add(norm(rel.get("tail")))
    out = []
    for h, rels in hr.items():
        for pid, tails in rels.items():
            tl = sorted(tails)
            for a in range(len(tl)):
                for b in range(a + 1, len(tl)):
                    out.append({"pid": pid, "h": h, "t": tl[a], "t2": tl[b],
                                "he": frozenset({f"R:{h}|{pid}|{tl[a]}", f"R:{h}|{pid}|{tl[b]}"})})
    return out


def disjoint_lower_bound(hyperedges):
    """Backward-compatible alias for the exact hypergraph matching number."""
    return maximum_disjoint_lower_bound(hyperedges)


def fuzzy_gtype(name, gtype):
    """Exact-then-containment entity-to-gold alignment; None if unmatched."""
    n = name if isinstance(name, str) else norm(name)
    if n in gtype:
        return gtype[n]
    if len(n) >= 4:
        for gn, t in gtype.items():
            if len(gn) >= 4 and (n in gn or gn in n):
                return t
    return None


def validate_against_gold(viols, etype, d):
    """Per-violation soundness check using ambiguity-aware gold cluster IDs."""
    grel = gold_relation_ids(d)
    for v in viols:
        head = align_gold_entity(v["h"], d)
        tail = align_gold_entity(v["t"], d)
        gh, gt = head["gold_type"], tail["gold_type"]
        v["gh"], v["gt"] = gh, gt
        v["gold_head_ids"] = head["candidate_ids"]
        v["gold_tail_ids"] = tail["candidate_ids"]
        v["head_alignment"] = head["status"]
        v["tail_alignment"] = tail["status"]
        v["h_wrong"] = gh is not None and v["ht"] != gh
        v["t_wrong"] = gt is not None and v["tt"] != gt
        v["checkable"] = gh is not None and gt is not None
        v["rel_spurious"] = bool(
            v["checkable"]
            and not any(
                (head_id, v["pid"], tail_id) in grel
                for head_id in head["candidate_ids"]
                for tail_id in tail["candidate_ids"]
            )
        )
        v["sound"] = bool(
            v["checkable"]
            and (v["h_wrong"] or v["t_wrong"] or v["rel_spurious"])
        )
    true_type_err = sum(
        1
        for name, emitted_type in etype.items()
        if (aligned := align_gold_entity(name, d))["gold_type"] is not None
        and aligned["gold_type"] != emitted_type
    )
    return viols, true_type_err
