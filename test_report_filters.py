import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes_treatment import router

class ReportFilterTests(unittest.TestCase):
    def test_activity_dates_control_iit_independently_of_vl_date(self):
        app=FastAPI();app.include_router(router)
        with patch('routes_treatment.calculate',return_value={}) as calculate, patch('routes_treatment.database_connection'), patch('report_template.brief_view',return_value={}):
            response=TestClient(app).post('/api/treatment-report',data=dict(snapshot_id='a'*64,sheet='Sheet1',end_date='2026-09-19',start_date='2026-08-01',activity_start_date='2026-10-01',activity_end_date='2026-10-17',iit_start_date='2020-01-01',iit_end_date='2020-01-02'))
        self.assertEqual(response.status_code,200,response.text)
        args=calculate.call_args
        self.assertEqual(args.args[5],'2026-09-19')
        self.assertEqual(args.kwargs['start_date'],'2026-08-01')
        self.assertEqual(args.kwargs['activity_start_date'],'2026-10-01')
        self.assertEqual(args.kwargs['iit_start_date'],'2026-10-01')
        self.assertEqual(args.kwargs['iit_end_date'],'2026-10-17')


    def test_explicit_vl_window_inclusive_and_independent(self):
        from treatment_report import aggregate,window
        rows=[('Active','180',d,d,'25','19','Delta') for d in ['2026-07-31','2026-08-01','2026-09-19','2026-09-20']]
        report=aggregate(rows,'2026-09-19',start_date='2026-08-01')
        self.assertEqual(report['start_date'],'2026-08-01')
        self.assertEqual(report['groups']['all']['txcurr'],4)
        self.assertEqual(report['groups']['all']['sample_collected'],2)
        self.assertEqual(report['groups']['all']['result'],2)
        self.assertEqual(report['groups']['all']['undetectable'],2)
        with self.assertRaises(ValueError):window('2026-08-01','2026-09-19')
