import json
import tempfile
import unittest
from pathlib import Path

from run_extractions import cached_result_is_usable


class ExtractionCacheTests(unittest.TestCase):
    def test_failed_api_response_is_not_a_usable_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "0000.json"
            path.write_text(json.dumps({"entities": [], "relations": [], "_error": "provider failure"}))
            self.assertFalse(cached_result_is_usable(path))

    def test_empty_extraction_is_not_a_usable_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "0000.json"
            path.write_text(json.dumps({"entities": [], "relations": []}))
            self.assertFalse(cached_result_is_usable(path))


if __name__ == "__main__":
    unittest.main()
