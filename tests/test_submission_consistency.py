import csv
import re
import subprocess
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def pdf_text(path: Path) -> str:
    return subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


class SubmissionConsistencyTests(unittest.TestCase):
    def test_reviewer_response_has_one_block_per_comment(self):
        path = ROOT / "revision" / "response_to_reviewers.md"
        if not path.is_file():
            self.skipTest("reviewer response not released")
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count("**Response.**"), 34)
        self.assertEqual(text.count("**Action.**"), 34)
        self.assertNotIn("previously empty cell", text)

    def test_response_evidence_is_directly_packaged_or_archived(self):
        package = ROOT / "revision" / "submission_package"
        if not package.is_dir():
            self.skipTest("submission package not assembled")
        tables = package / "04_Supplementary_Files" / "ReDocRED_Analysis_Tables"
        direct_files = {
            "per_document.csv",
            "tightness_by_volume.csv",
            "tightness_by_relation.csv",
            "relation_reliability.csv",
            "unsound_cases.csv",
            "alignment_breakdown.csv",
            "alignment_audit_sample.csv",
            "alignment_case_audit.md",
            "alignment_selection_effect.csv",
            "review_budget.csv",
            "error_taxonomy.csv",
            "candidate_family_screen.csv",
            "schema_signature_mapping.csv",
            "functional_validation.csv",
            "gold_id_anchor_ablation.csv",
            "transversal_sensitivity.csv",
            "consolidated_model_table.csv",
            "self_consistency_by_model.csv",
            "self_consistency_by_relation.csv",
            "constraint_sensitivity.json",
        }
        self.assertEqual([], sorted(name for name in direct_files if not (tables / name).is_file()))

        archive = package / "04_Supplementary_Files" / "Reproducibility_Archive.zip"
        with zipfile.ZipFile(archive) as handle:
            archived = set(handle.namelist())
        for path in (
            "code/common.py",
            "code/run_resample.py",
            "code/analyze_resample.py",
            "code/ablation_gold_ids.py",
            "code/validate_functional.py",
        ):
            self.assertIn(path, archived)

    def test_reported_validation_totals_match_machine_readable_tables(self):
        base = ROOT / "result" / "revision"
        with (base / "relation_reliability.csv").open(newline="", encoding="utf-8") as handle:
            relation_rows = list(csv.DictReader(handle))
        pooled = {}
        for setting in ("holdout", "schema_only"):
            rows = [row for row in relation_rows if row["setting"] == setting]
            pooled[setting] = (
                sum(int(row["sound"]) for row in rows),
                sum(int(row["checkable"]) for row in rows),
            )
        self.assertEqual((3495, 3501), pooled["holdout"])
        self.assertEqual((3076, 3122), pooled["schema_only"])

        with (base / "functional_validation.csv").open(newline="", encoding="utf-8") as handle:
            functional_rows = list(csv.DictReader(handle))
        functional_total = next(
            row for row in functional_rows if row["model"] == "ALL" and row["relation"] == "ALL"
        )
        self.assertEqual(415, int(functional_total["validated"]))
        self.assertEqual(34, int(functional_total["disagreed"]))
        self.assertEqual(449, int(functional_total["checkable"]))
        self.assertEqual(27, int(functional_total["uncheckable"]))

        with (base / "self_consistency_by_model.csv").open(newline="", encoding="utf-8") as handle:
            recurrence_rows = list(csv.DictReader(handle))
        self.assertEqual(5, len(recurrence_rows))
        self.assertEqual(1250, sum(
            int(row["complete_documents"]) * int(row["samples_per_document"])
            for row in recurrence_rows
        ))
        for row in recurrence_rows:
            counts = [int(row[f"recurrence_{index}"]) for index in range(6)]
            self.assertEqual(int(row["certificate_visible_errors"]), sum(counts))
            self.assertEqual(int(row["stable_visible_errors"]), sum(counts[3:]))

    def test_author_manual_sheet_marks_the_stratified_sample(self):
        path = ROOT / "revision" / "Author_Only_Gold_ID_Check.csv"
        if not path.is_file():
            self.skipTest("author-only manual sheet not assembled")
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(222, len(rows))
        self.assertEqual(67, sum(row["in_stratified_67_sample"] == "YES" for row in rows))

    def test_figure_4_matches_authoritative_volume_bins(self):
        text = pdf_text(ROOT / "result" / "figs" / "F4_firing_volume.pdf")
        for expected in ("n=56", "n=323", "n=447", "n=253", "n=79", "n=30"):
            self.assertIn(expected, text)

    def test_figure_9_uses_runtime_bound_and_tie_aware_spearman(self):
        text = pdf_text(ROOT / "result" / "figs" / "F9_triage.pdf")
        self.assertRegex(text, r"Spearman\s+ρ\s*=\s*0\.37")
        self.assertNotRegex(text, r"Spearman\s+ρ\s*=\s*0\.39")

    @unittest.skipUnless((ROOT / "paper" / "main.tex").is_file(), "local manuscript not released")
    def test_manuscript_uses_non_circular_validation_as_headline(self):
        text = (ROOT / "paper" / "main.tex").read_text(encoding="utf-8")
        self.assertIn("one-sided 95\\%", text)
        self.assertIn("0.88\\%", text)
        self.assertIn("construction-aligned diagnostic", text)
        self.assertNotIn("pooled main audit observed $0/2{,}887$", text)

    @unittest.skipUnless((ROOT / "paper" / "main.tex").is_file(), "local manuscript not released")
    def test_bound_maximum_and_weak_model_table_are_consistent(self):
        text = (ROOT / "paper" / "main.tex").read_text(encoding="utf-8")
        self.assertIn("largest observed document-level bound was six", text)
        rows = re.findall(r"Qwen2\.5-7B\s+&.*", text)
        self.assertTrue(rows)
        diagnostic_row = next((row for row in rows if "15/15" in row), None)
        self.assertIsNotNone(diagnostic_row)
        self.assertIn("15/300", diagnostic_row)
        self.assertIn("0/3", diagnostic_row)

    @unittest.skipUnless((ROOT / "paper" / "main.tex").is_file(), "local manuscript not released")
    def test_self_consistency_uses_unique_visible_error_items(self):
        text = (ROOT / "paper" / "main.tex").read_text(encoding="utf-8")
        self.assertIn("28/102", text)
        self.assertIn("same incorrect type", text)
        self.assertNotIn("21/95", text)

    @unittest.skipUnless((ROOT / "paper" / "refs.bib").is_file(), "local bibliography not released")
    def test_chao_reference_uses_published_2025_record(self):
        text = (ROOT / "paper" / "refs.bib").read_text(encoding="utf-8")
        entry = re.search(r"@inproceedings\{chao2023jailbreaking,.*?\n\}", text, re.S)
        self.assertIsNotNone(entry)
        self.assertIn("year={2025}", entry.group(0))
        self.assertIn("pages={23--42}", entry.group(0))
        self.assertIn("doi={10.1109/SATML64287.2025.00010}", entry.group(0))


if __name__ == "__main__":
    unittest.main()
