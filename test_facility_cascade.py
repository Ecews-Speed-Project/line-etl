import unittest
from treatment_report import aggregate,COUNTS

class FacilityCascadeTests(unittest.TestCase):
    def test_facility_identity_boundaries_and_reconciliation(self):
        rows=[('Active',180,'2026-09-01','2026-09-30',49,25,'DELTA','General Hospital','A'),
              ('Active',180,'2026-09-01','2026-09-30',1000,12,'Delta','General Hospital','A'),
              ('Active',179,'2026-09-01','2026-09-30',50,25,'Delta','General Hospital','B'),
              ('Active',180,None,'2026-08-31',50,25,'Ekiti','General Hospital','A'),
              ('Active',180,'2026-09-01','2026-09-30',50,25,None,None,None),
              ('LTFU',180,'2026-09-01','2026-09-30',10,25,'Delta','Inactive facility','C')]
        report=aggregate(rows,'2026-09-30',start_date='2026-09-01')
        facilities=report['facilities']
        group=next(f for f in facilities if f['state']=='Delta' and f['datim_code']=='A')
        self.assertEqual(group['txcurr'],2)
        self.assertEqual(group['suppression_rate'],50)
        self.assertEqual(group['unsuppressed'],1)
        self.assertEqual(group['sample_collection_rate'],100)
        self.assertIsNone(next(f for f in facilities if f['datim_code']=='B')['coverage'])
        self.assertTrue(any(f['facility']=='Unknown facility' for f in facilities))
        for key in COUNTS:
            self.assertEqual(sum(f[key] for f in facilities),report['groups']['all'][key])
            for state,values in report['states'].items():
                self.assertEqual(sum(f[key] for f in facilities if f['state']==state),values[key])

    def test_legacy_rows_keep_unknown_facility(self):
        report=aggregate([('Active',180,None,None,None,25,'Delta')],'2026-09-30')
        self.assertEqual(report['facilities'][0]['facility'],'Unknown facility')
        self.assertEqual(report['facilities'][0]['txcurr'],1)

class CascadeDashboardIntegrationTests(unittest.TestCase):
    def test_weekly_and_quarterly_return_facility_cascade(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from routes_treatment import router
        from routes_quarterly import router as quarterly
        from routes_pages import display
        app=FastAPI();app.include_router(router);app.include_router(quarterly)
        for prefix,schema in [('', 'public'),('/quarterly','quarterly')]:
            report=aggregate([('Active',180,'2026-09-01','2026-09-01',25,25,'Delta','Clinic','D1')],'2026-09-30')
            with patch('routes_treatment.calculate',return_value=report),patch('routes_treatment.database_connection'),patch('report_template.brief_view',return_value={}):
                response=TestClient(app).post(prefix+'/api/treatment-report',data=dict(snapshot_id='a'*64,sheet='Sheet1',schema=schema))
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['facilities'][0]['vl_suppression'],1)
            html=display('dashboard.html',bool(prefix)).body.decode()
            self.assertIn('/static/viral-cascade.js',html)
            if prefix:self.assertIn('data-api-prefix="/quarterly"',html)
