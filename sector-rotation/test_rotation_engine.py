import unittest,sys,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from rotation_engine import compute,STATUS
class TestRotation(unittest.TestCase):
 def test_unverified_must_not_pass(self):
  h=[{"snapshot_date":f"2026-10-{i:02}","date_status":"twse_calendar_verified_quotes_source_date_unverified","quotes":{"1101":{"close":20}}} for i in range(1,23)]
  self.assertEqual(compute(h,[{"id":"1101","industry":"01","market":"上市"}])["status"],"HOLD_INSUFFICIENT_VERIFIED_SESSIONS")
 def test_duplicate_dates_rejected(self):
  h=[{"trade_date":"2026-10-01","date_status":STATUS,"quotes":{}}]*21
  with self.assertRaises(ValueError):compute(h,[])
 def test_20_days_not_enough(self):
  h=[{"trade_date":f"2026-10-{i:02}","date_status":STATUS,"quotes":{}} for i in range(1,21)]
  self.assertEqual(compute(h,[])["status"],"HOLD_INSUFFICIENT_VERIFIED_SESSIONS")
if __name__=="__main__":unittest.main()
