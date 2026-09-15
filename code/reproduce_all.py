#!/usr/bin/env python3
"""Reproduce every reported analysis and, by default, all publication figures.

The workflow is fully offline: it reads the exact cached model outputs released
with the repository and never contacts a model API. Each task writes a separate
log to ``result/reproduction/`` so results are easy to inspect and archive.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "result" / "reproduction"

ANALYSIS_TASKS = (
    ("theorem_tests", "certificate.py", ()),
    ("main_results", "analyze.py", ()),
    ("holdout_signatures", "ablation_holdout.py", ()),
    ("schema_only_signatures", "ablation_schema.py", ()),
    ("cross_family_control", "analyze_glm.py", ()),
    ("revision_analyses", "analyze_revision.py", ()),
    ("self_consistency", "analyze_resample.py", ("--all-models", "--documents", "50", "--samples", "5", "--require-complete")),
    ("scierc_external", "analyze_scierc.py", ("--require-complete",)),
    ("triage", "analyze_triage.py", ()),
)

EXPECTED_MARKERS = {
    "theorem_tests": ("stress test (500 random hypergraphs): PASS",),
    "main_results": ("common evaluation set = 297", "combined:     2887/2887 = 100%"),
    "holdout_signatures": ("checkable=3501  sound=3495  soundness=99.8%",),
    "schema_only_signatures": ("checkable=3122  sound=3076  soundness=98.5%",),
    "cross_family_control": ("soundness = 1085/1085 = 100.0%", "theorem   = 300/300 docs hold"),
    "revision_analyses": ("REVISION_ANALYSIS_OK",),
    "self_consistency": ("SELF_CONSISTENCY_ANALYSIS_OK",),
    "scierc_external": ("SCIERC_ANALYSIS_OK",),
}

FIGURE_NAMES = (
    "F1_concept",
    "F2_gradient",
    "F3_soundness",
    "F4_firing_volume",
    "F5_families",
    "F6_detectable",
    "F7_selfconsistency",
    "F8_complementary",
    "F9_triage",
    "F10_tightness",
    "F11_perrelation",
)

REQUIRED_INPUTS = (
    ROOT / "data" / "redocred_dev_300.json",
    ROOT / "data" / "relations.json",
    ROOT / "result" / "extractions",
    ROOT / "result" / "resample",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproduce the paper from released cached model outputs."
    )
    parser.add_argument(
        "--skip-figures",
        action="store_true",
        help="Run all numerical analyses without regenerating Figures 1--11.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory for task logs and the reproduction manifest.",
    )
    return parser.parse_args()


def verify_inputs() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_INPUTS if not path.exists()]
    if missing:
        joined = "\n  - ".join(missing)
        raise SystemExit(f"Missing released inputs:\n  - {joined}")


def installed_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in ("numpy", "matplotlib", "networkx", "requests", "CairoSVG"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not installed"
    return versions


def write_common_document_ids(output_dir: Path) -> Path:
    """Write the exact common-set indices and titles used by the main analysis."""
    sys.path.insert(0, str(ROOT / "code"))
    import analyze  # imported here so the released selection predicate is authoritative

    records = [
        {"index": index, "title": analyze.DOCS[index]["title"]}
        for index in analyze.COMMON
    ]
    path = output_dir / "common_document_ids.json"
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def run_task(
    name: str,
    script: str,
    script_args: tuple[str, ...],
    output_dir: Path,
    environment: dict[str, str],
) -> dict[str, object]:
    command = [sys.executable, str(ROOT / "code" / script), *script_args]
    started = time.monotonic()
    process = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.monotonic() - started

    log_path = output_dir / f"{name}.txt"
    log_text = process.stdout
    if process.stderr:
        log_text += "\n[stderr]\n" + process.stderr
    log_path.write_text(log_text, encoding="utf-8")

    missing_markers = [
        marker for marker in EXPECTED_MARKERS.get(name, ()) if marker not in process.stdout
    ]
    missing_figures = []
    if name == "publication_figures":
        missing_figures = [
            str((ROOT / "result" / "figs" / f"{figure}.{extension}").relative_to(ROOT))
            for figure in FIGURE_NAMES
            for extension in ("svg", "pdf", "png")
            if not (ROOT / "result" / "figs" / f"{figure}.{extension}").exists()
        ]

    passed = process.returncode == 0 and not missing_markers and not missing_figures
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name:24} {elapsed:6.1f}s  -> {log_path.relative_to(ROOT)}")
    if not passed:
        details = []
        if process.returncode != 0:
            details.append(f"exit code {process.returncode}")
        if missing_markers:
            details.append(f"missing expected output: {missing_markers}")
        if missing_figures:
            details.append(f"missing figure assets: {missing_figures}")
        raise SystemExit(
            f"Task '{name}' failed ({'; '.join(details)}). See {log_path}."
        )

    return {
        "name": name,
        "script": f"code/{script}",
        "command": command,
        "return_code": process.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "log": str(log_path.relative_to(ROOT)),
    }


def main() -> None:
    args = parse_args()
    verify_inputs()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = list(ANALYSIS_TASKS)
    if not args.skip_figures:
        tasks.append(("publication_figures", "make_figures_pub.py", ()))

    print("Consistency Certificates: offline reproduction")
    print(f"repository: {ROOT}")
    print(f"python:     {sys.version.split()[0]}")
    print(f"tasks:      {len(tasks)}")

    records: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="consistency-certificates-mpl-") as mpl_dir:
        environment = os.environ.copy()
        environment["MPLCONFIGDIR"] = mpl_dir
        for name, script, script_args in tasks:
            records.append(run_task(name, script, script_args, output_dir, environment))

    common_ids_path = write_common_document_ids(output_dir)

    manifest = {
        "status": "PASS",
        "offline": True,
        "repository": str(ROOT),
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": installed_versions(),
        "common_document_ids": str(common_ids_path.relative_to(ROOT)),
        "tasks": records,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nCommon-set IDs: {common_ids_path.relative_to(ROOT)}")
    print(f"All tasks passed. Manifest: {manifest_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
