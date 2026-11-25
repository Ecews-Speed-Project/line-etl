import unittest
from routes_hts import parse,DATA
class HtsTests(unittest.TestCase):
 @unittest.skipUnless(DATA.exists(),"Local supplied dataset not present")
 def test_supplied_totals(self):
  r=parse(DATA.read_bytes());self.assertEqual(len(r['facilities']),96);self.assertEqual((r['total']['hts_pos'],r['total']['txnew'],r['total']['unique']),(66,23,13));self.assertAlmostEqual(r['total']['linkage'],2300/66)
 def test_sum_before_rate_zero_and_duplicate_facility(self):
  r=parse(b'State,LGA,Facility,HTS_TST_POS,TX_NEW total,TX_NEW unique\nA,L,F,100,98,97\nA,L,G,0,3,2\nA,L,F,100,100,100\n')
  self.assertEqual(len(r['facilities']),2);self.assertEqual(r['facilities'][0]['linkage'],99);self.assertIsNone(r['facilities'][1]['linkage']);self.assertEqual(r['states'][0]['linkage'],100.5)
 def test_reject_invalid_counts_and_missing_headers(self):
  for data in [b'State,LGA,Facility,HTS_TST_POS,TX_NEW total,TX_NEW unique\nA,L,F,-1,2,1\n',b'State,Facility\nA,F\n']:
   with self.assertRaises(ValueError):parse(data)

 def test_api_upload_and_navigation(self):
  from fastapi import FastAPI
  from fastapi.testclient import TestClient
  from routes_hts import router
  from routes_pages import display
  app=FastAPI();app.include_router(router)
  client=TestClient(app)
  response=client.post('/api/hts-monitoring',content=b'State,LGA,Facility,HTS_TST_POS,TX_NEW total,TX_NEW unique\nA,L,F,100,98,97\n')
  self.assertEqual(response.status_code,200,response.text)
  self.assertEqual(response.json()['total']['linkage'],98)
  self.assertEqual(response.json()['total']['unique_linkage'],97)
  for quarterly in (False,True):self.assertIn('/hts-txnew',display('dashboard.html',quarterly).body.decode())
