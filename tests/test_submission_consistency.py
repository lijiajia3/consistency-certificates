import re
import subprocess
import unittest
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
        row = re.search(r"Qwen2\.5-7-billion\s+&.*", text)
        self.assertIsNotNone(row)
        self.assertIn("& N/A & N/A", row.group(0))

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
