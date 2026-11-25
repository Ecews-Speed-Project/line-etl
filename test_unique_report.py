import unittest
import copy
from unittest.mock import patch
from treatment_report import aggregate
class UniqueReportTests(unittest.TestCase):
 def test_only_enrolled_all_indicators_and_original_unchanged(self):
  rows=[('Active',180,'2026-11-01','2026-11-01',25,10,'Delta','Clinic','A',status) for status in ['ENROLLED',' enrolled ','DUPLICATE','ADJUDICATIONWAITING',None]]
  report=aggregate(rows,'2026-11-23',unique_only=True)
  for group in [report['groups']['all'],report['states']['Delta'],report['facilities'][0],report['groups']['paediatrics']]:
   self.assertEqual(group['txcurr'],2);self.assertEqual(group['vl_suppression'],2);self.assertEqual(group['ipi_suppressed'],2);self.assertEqual(group['ipi_suppression_rate'],100)
  self.assertEqual(aggregate(rows,'2026-11-23')['groups']['all']['txcurr'],5)
  self.assertEqual(aggregate([rows[0][:-1]],'2026-11-23',unique_only=True)['groups']['all']['txcurr'],0)
 def test_both_routes_forward_unique_filter_to_comparison_and_activity(self):
  from fastapi import FastAPI
  from fastapi.testclient import TestClient
  from routes_treatment import router
  from routes_quarterly import router as quarterly
  app=FastAPI();app.include_router(router);app.include_router(quarterly)
  for prefix,schema in [('', 'public'),('/quarterly','quarterly')]:
   report=aggregate([], '2026-11-23');report['source']={'period':'FY27Q1'}
   payload=dict(snapshot_id='a'*64,sheet='Data',schema=schema,unique_only='true')
   if not prefix:payload.update(comparison_snapshot_id='b'*64,comparison_sheet='Prior')
   with patch('routes_treatment.calculate',side_effect=lambda *args,**kwargs:copy.deepcopy(report)) as calculate,patch('routes_treatment.database_connection'),patch('report_template.brief_view',return_value={}):
    response=TestClient(app).post(prefix+'/api/treatment-report',data=payload)
   self.assertEqual(response.status_code,200,response.text)
   for call in calculate.call_args_list:self.assertTrue(call.kwargs['unique_only'])
