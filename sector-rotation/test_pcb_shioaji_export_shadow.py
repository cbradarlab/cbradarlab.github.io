#!/usr/bin/env python3
"""Offline tests: no Shioaji installation, credentials or network required."""
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from export_pcb_shioaji_kbars_shadow import export

class FakeApi:
    def __init__(self, broken=False):
        self.Contracts = SimpleNamespace(Stocks={"1303": "contract-1303"})
        self.broken = broken

    def kbars(self, **kwargs):
        values = dict(ts=["2026-10-30 09:00:00", "2026-10-30 09:01:00"],
                      Open=[10, 11], High=[11, 12], Low=[9, 10],
                      Close=[10, 11], Volume=[100, 200])
        if self.broken:
            values["Volume"] = [100]
        return SimpleNamespace(**values)

class ExportTests(unittest.TestCase):
    def run_export(self, broken=False):
        with tempfile.TemporaryDirectory() as tmp:
            watch = Path(tmp) / "watch.csv"
            watch.write_text("code,name\n1303,南亞\n", encoding="utf-8")
            out = Path(tmp) / "raw.csv"
            result = export(FakeApi(broken), "2026-10-30", out, watchlist=watch)
            with out.open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            return result, rows

    def test_success_preserves_raw_volume(self):
        result, rows = self.run_export()
        self.assertEqual(result["rows"], 2)
        self.assertEqual(rows[0]["volume_raw"], "100")
        self.assertFalse(result["volume_unit_verified"])
        self.assertFalse(result["ready_for_rotation"])

    def test_broken_stock_does_not_export_partial_rows(self):
        result, rows = self.run_export(broken=True)
        self.assertEqual(rows, [])
        self.assertEqual(result["rows"], 0)
        self.assertEqual(result["failed"][0]["error_type"], "ValueError")

if __name__ == "__main__":
    unittest.main()
