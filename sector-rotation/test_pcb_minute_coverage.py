#!/usr/bin/env python3
"""Offline regression tests for the read-only PCB minute coverage audit."""
import json
import tempfile
import unittest
from pathlib import Path
from audit_pcb_minute_coverage import audit

class PcbCoverageTests(unittest.TestCase):
    def check(self, rows, expected_complete=0, expected_partial=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            path.write_text(json.dumps({"date": "2026-10-29", "status": "SHADOW_PARTIAL",
                                        "coverage": {"market_wide": False}, "rows": rows}), encoding="utf-8")
            result = audit(path)
        self.assertFalse(result["ready_for_rotation"])
        self.assertEqual(result["groups"]["玻纖布"]["complete"], expected_complete)
        if expected_partial is not None:
            self.assertEqual(result["groups"]["玻纖布"]["partial"], expected_partial)
        return result

    def test_no_pcb_rows(self):
        result = self.check([{"code": "2330", "minute": "09:00"}])
        self.assertEqual(result["groups"]["玻纖布"]["complete_pct"], 0)
        self.assertEqual(len(result["groups"]["玻纖布"]["missing"]), 6)

    def test_partial_is_not_complete(self):
        self.check([{"code": "1303", "minute": "09:00"}], expected_partial={"1303": 1})

    def test_265_distinct_minutes_complete(self):
        rows = [{"code": "1303", "minute": f"{9 + i // 60:02d}:{i % 60:02d}"} for i in range(265)]
        result = self.check(rows, expected_complete=1)
        self.assertEqual(result["groups"]["玻纖布"]["complete_pct"], round(100 / 6, 2))

    def test_duplicate_minute_does_not_inflate_coverage(self):
        self.check([{"code": "1303", "minute": "09:00"}] * 265, expected_partial={"1303": 1})

if __name__ == "__main__":
    unittest.main()
