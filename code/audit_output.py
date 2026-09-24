#!/usr/bin/env python3
"""Audit one structured extraction and return a gold-free consistency certificate.

Example:
    python3 code/audit_output.py extraction.json --constraints all
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import (
    ROOT,
    disjoint_lower_bound,
    find_functional_violations,
    find_violations,
)


EMPIRICAL_SIGNATURES = Path(ROOT) / "data" / "relations.json"
CERTIFIED_FAMILIES = ("empirical", "definitional")
EXPLORATORY_FAMILIES = ("functional",)
FAMILY_CHOICES = ("certified", "empirical", "definitional", "functional", "all")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit one black-box information extraction output without gold labels, "
            "model internals, or additional model calls."
        )
    )
    parser.add_argument(
        "extraction",
        type=Path,
        help="JSON file containing 'entities' and 'relations' arrays.",
    )
    parser.add_argument(
        "--constraints",
        choices=FAMILY_CHOICES,
        default="certified",
        help=(
            "Constraint family to evaluate (default: certified). 'all' also "
            "reports exploratory functional warnings, but never adds them to "
            "the certified lower bound."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output JSON path; otherwise the certificate is printed.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Input file is not valid JSON: {path}: {exc}") from exc


def validate_extraction(extraction: Any) -> dict[str, Any]:
    if not isinstance(extraction, dict):
        raise SystemExit("The extraction must be a JSON object.")
    for key in ("entities", "relations"):
        if key not in extraction or not isinstance(extraction[key], list):
            raise SystemExit(f"The extraction must contain a '{key}' array.")
    return extraction


def serialise_violation(
    violation: dict[str, Any], family: str, role: str
) -> dict[str, Any]:
    record = {key: value for key, value in violation.items() if key != "he"}
    record["family"] = family
    record["role"] = role
    record["scope"] = sorted(violation["he"])
    return record


def audit(extraction: dict[str, Any], selected: str) -> dict[str, Any]:
    signatures = load_json(EMPIRICAL_SIGNATURES)
    if selected == "all":
        certified_families = CERTIFIED_FAMILIES
        exploratory_families = EXPLORATORY_FAMILIES
    elif selected == "certified":
        certified_families = CERTIFIED_FAMILIES
        exploratory_families = ()
    elif selected == "functional":
        certified_families = ()
        exploratory_families = ("functional",)
    else:
        certified_families = (selected,)
        exploratory_families = ()

    violations: list[dict[str, Any]] = []
    certified_hyperedges = []
    counts: dict[str, int] = {}
    roles = [
        *((family, "certified") for family in certified_families),
        *((family, "exploratory") for family in exploratory_families),
    ]
    for family, role in roles:
        if family == "functional":
            family_violations = find_functional_violations(extraction)
        else:
            family_violations, _ = find_violations(extraction, signatures, family)
        counts[family] = len(family_violations)
        if role == "certified":
            certified_hyperedges.extend(
                violation["he"] for violation in family_violations
            )
        violations.extend(
            serialise_violation(violation, family, role)
            for violation in family_violations
        )

    if certified_families:
        bound: int | None = disjoint_lower_bound(certified_hyperedges)
        certificate = (
            f">= {bound} extracted items are wrong"
            if bound
            else "uninformative lower bound: 0"
        )
    else:
        bound = None
        certificate = (
            "not issued: the selected functional rules are exploratory and "
            "are not validated hard constraints for Re-DocRED"
        )

    exploratory_count = sum(
        count for family, count in counts.items() if family in exploratory_families
    )
    return {
        "certificate": certificate,
        "certified_error_lower_bound": bound,
        "n_violations": len(violations),
        "violations_by_family": counts,
        "certified_constraint_families": list(certified_families),
        "exploratory_constraint_families": list(exploratory_families),
        "exploratory_warning_count": exploratory_count,
        "constraint_validity_required": True,
        "gold_used": False,
        "violations": violations,
    }


def main() -> None:
    args = parse_args()
    extraction = validate_extraction(load_json(args.extraction))
    certificate = audit(extraction, args.constraints)
    rendered = json.dumps(certificate, indent=2, ensure_ascii=False) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
