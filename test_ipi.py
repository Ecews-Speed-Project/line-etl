import unittest
from treatment_report import aggregate
class IpiTests(unittest.TestCase):
 def test_independent_window_eligibility_and_boundaries(self):
  cases=[('Active',0,'2025-11-23',999),('Active',None,'2026-11-23',0),('Active',180,'2025-11-22',25),('Active',180,'2026-11-24',25),('Active',180,'2026-11-01',1000),('Active',180,'2026-11-01',-1),('Active',180,'bad',25),('Active',180,'2026-11-01','NaN'),('LTFU',180,'2026-11-01',25)]
  rows=[(status,days,None,day,vl,10,'Delta','Clinic','D1') for status,days,day,vl in cases]
  r=aggregate(rows,'2026-11-23',start_date='2026-11-01')
  for g in [r['groups']['all'],r['groups']['paediatrics'],r['states']['Delta'],r['facilities'][0],r['paediatric_states']['Delta']['total']]:
   self.assertEqual(g['ipi_suppressed'],2);self.assertEqual(g['ipi_suppression_rate'],25)
  empty=aggregate([], '2026-11-23');self.assertIsNone(empty['groups']['all']['ipi_suppression_rate'])
