from __future__ import annotations

from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from stress_test_uni_api import (  # type: ignore
    parse_positive_int_list,
    percentile_ms,
    summarize_samples,
)


class UniApiStressUnitTest(unittest.TestCase):
    def test_parse_positive_int_list(self) -> None:
        self.assertEqual(parse_positive_int_list("1,2,4"), [1, 2, 4])
        self.assertEqual(parse_positive_int_list(" 3 , 5 "), [3, 5])
        with self.assertRaises(ValueError):
            parse_positive_int_list("1,0,2")

    def test_percentile_ms(self) -> None:
        self.assertEqual(percentile_ms([100, 200, 300], 50), 200)
        self.assertEqual(percentile_ms([100, 200, 300], 95), 300)
        self.assertEqual(percentile_ms([], 95), 0)

    def test_summarize_samples(self) -> None:
        summary = summarize_samples(
            [
                {"ok": True, "latency_ms": 100, "error": ""},
                {"ok": False, "latency_ms": 300, "error": "timeout"},
                {"ok": True, "latency_ms": 200, "error": ""},
            ]
        )
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["success"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["success_rate"], 2 / 3)
        self.assertEqual(summary["p95_ms"], 300)
        self.assertEqual(summary["error_counts"]["timeout"], 1)


if __name__ == "__main__":
    unittest.main()
