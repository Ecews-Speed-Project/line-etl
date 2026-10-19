import json,os,unittest
from datetime import date
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app

class QuarterlyTests(unittest.TestCase):
    def setUp(self):
        self.auth=patch.dict(os.environ,{'APP_ACCESS_PASSWORD':''});self.auth.start();self.addCleanup(self.auth.stop)
        self.client=TestClient(app)
        self.doc=dict(format_version=1,source_sha256='a'*64,source_file='quarter.xlsx',sheet='Line list',headers=['State'],records=[dict(source_row=2,data={'State':'Delta'})])
    def test_quarterly_pages_and_navigation(self):
        for path in ['upload','flat','errors']:
            response=self.client.get('/quarterly/'+path);self.assertEqual(response.status_code,200)
            self.assertIn('data-api-prefix="/quarterly"',response.text)
            self.assertIn('value="quarterly" readonly',response.text)
            self.assertIn('href="/quarterly/upload"',response.text)
            self.assertIn('href="/quarterly/flat"',response.text)
        self.assertIn('href="/quarterly/upload"',self.client.get('/').text)
        self.assertNotIn('data-api-prefix="/quarterly"',self.client.get('/upload').text)
    def test_upload_and_review_use_quarterly_scope(self):
        encoded=json.dumps(self.doc).encode()
        response=self.client.post('/quarterly/api/review-json',data={'schema':'quarterly'},files={'file':('quarter.json',encoded)})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['rows'],1)
        with patch('routes_upload.upload',return_value=1) as upload:
            response=self.client.post('/quarterly/api/upload',data={'schema':'quarterly','period':'FY26Q4'},files={'file':('quarter.json',encoded)})
            self.assertEqual(response.status_code,200)
            self.assertEqual(upload.call_args.args[1:3],('quarterly','linelist_records'))
            self.assertTrue(upload.call_args.kwargs['create_schema'])
            self.assertEqual(upload.call_args.kwargs['period'],'FY26Q4')
    def test_cross_workflow_requests_are_rejected(self):
        for fields in ({'schema':'public'},{},{'schema':'quarterly','source_table':'weekly_records'}):
            with patch('routes_flat.flatten') as flatten:
                r=self.client.post('/quarterly/api/flat/build',data=fields)
                self.assertEqual(r.status_code,400);flatten.assert_not_called()
    def test_quarterly_flat_and_corrections(self):
        for action,function in [('build','flatten'),('browse','browse'),('errors','type_errors')]:
            with patch('routes_flat.'+function,return_value={'ok':True}) as call:
                r=self.client.post('/quarterly/api/flat/'+action,data={'schema':'quarterly'})
                self.assertEqual(r.status_code,200);self.assertEqual(call.call_args.args[1],'quarterly')
        with patch('routes_flat.correct',return_value={'saved':True}) as call:
            data=dict(schema='quarterly',source_table='linelist_records',source_sha256='a'*64,sheet='Line list',source_row=2,heading='Current_Age',value='5')
            self.assertEqual(self.client.post('/quarterly/api/correct-type',data=data).status_code,200)
            self.assertEqual(call.call_args.args[1],'quarterly')
    def test_quarterly_api_requires_login(self):
        with patch.dict(os.environ,{'APP_ACCESS_PASSWORD':'private'}):
            self.assertEqual(self.client.post('/quarterly/api/flat/browse',data={'schema':'quarterly'}).status_code,401)

    def test_quarterly_dashboard_and_reports_are_scoped(self):
        from treatment_report import aggregate
        report=aggregate([('Active','180',None,'2026-09-30','20','15','Delta')],'2026-09-30')
        report['source']=dict(file='quarter.xlsx',period='2026-09-30',sheet='Line list',rows=1)
        page=self.client.get('/quarterly/dashboard')
        self.assertEqual(page.status_code,200)
        self.assertIn('Quarterly linelist dashboard',page.text)
        self.assertIn('href="/quarterly/dashboard" aria-current="page"',page.text)
        for endpoint in ['dashboard','treatment-report']:
            self.assertEqual(self.client.post('/quarterly/api/'+endpoint,data={'schema':'public'}).status_code,400)
        with patch('routes_dashboard.summary',return_value={'linelists':[]}) as summary:
            response=self.client.post('/quarterly/api/dashboard',data={'schema':'quarterly'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(summary.call_args.args[1],'quarterly')
        with patch('routes_treatment.calculate',return_value=report) as calculate:
            fields=dict(schema='quarterly',snapshot_id='a'*64,sheet='Line list',end_date='2026-09-30')
            response=self.client.post('/quarterly/api/treatment-report',data=fields)
            self.assertEqual(response.status_code,200)
            self.assertEqual(calculate.call_args.args[1],'quarterly')
            self.assertTrue(response.json()['brief']['header'].startswith('Quarterly'))
            response=self.client.post('/quarterly/api/treatment-report',data=dict(fields,word='true'))
            self.assertEqual(response.status_code,200)
            self.assertIn('quarterly_treatment_report_',response.headers['content-disposition'])
            from zipfile import ZipFile
            from io import BytesIO
            with ZipFile(BytesIO(response.content)) as document:
                self.assertIn(b'Quarterly',document.read('word/header1.xml'))
                self.assertNotIn(b'last week',document.read('word/document.xml'))
        self.assertIn('Linelist dashboard',self.client.get('/dashboard').text)

    def test_quarter_labels_and_weekly_dates(self):
        from periods import quarterly_period,quarter_end,parse_workflow_period
        self.assertEqual(quarterly_period(' fy26q1 '),'FY26Q1')
        self.assertEqual(quarter_end('FY26Q1'),'2025-12-31')
        self.assertEqual(quarter_end('FY26Q4'),'2026-09-30')
        self.assertEqual(parse_workflow_period('2026-09-30','public'),date(2026,9,30))
        for invalid in ['FY26Q0','FY26Q5','2026-09-30','']:
            with self.assertRaises(ValueError):quarterly_period(invalid)
        self.assertIn('placeholder="FY26Q4"',self.client.get('/quarterly/upload').text)
        self.assertIn('type="text" name="period"',self.client.get('/quarterly/flat').text)

    def test_weekly_report_uses_selected_quarter_snapshot(self):
        from treatment_report import aggregate
        from report_template import table_models
        weekly=aggregate([('Active','180',None,'2026-09-19','20','15','Delta')],'2026-09-19')
        weekly['source']=dict(file='weekly.xlsx',period='2026-09-19',sheet='Weekly',rows=1)
        baseline=aggregate([('Active','180',None,None,None,'15','Delta'),('Active','180',None,None,None,'30','Delta')],'2026-09-19')
        baseline['source']=dict(file='quarter.xlsx',period='FY26Q1',sheet='Quarter',rows=2)
        fields=dict(snapshot_id='a'*64,sheet='Weekly',end_date='2026-09-19',comparison_snapshot_id='b'*64,comparison_sheet='Quarter')
        with patch('routes_treatment.calculate',side_effect=[baseline,weekly]) as calculate:
            response=self.client.post('/api/treatment-report',data=fields)
            self.assertEqual(response.status_code,200)
            self.assertEqual(calculate.call_args_list[0].args[1:3],('quarterly','linelist_records'))
            self.assertEqual(calculate.call_args_list[1].args[1],'public')
            tables=response.json()['brief']['tables']
            self.assertEqual(tables[1]['headers'][1],'TxCurr-FY26Q1')
            self.assertEqual(tables[1]['rows'][0][1:3],['2','1'])
            self.assertEqual(tables[3]['rows'][0][1:3],['1','1'])
            self.assertEqual(tables[1]['rows'][0][9],'-1')
            self.assertEqual(tables[1]['rows'][0][8],'50.0%')
            self.assertEqual(tables[3]['rows'][0][8],'100.0%')
            self.assertEqual(tables[3]['rows'][0][9],'0')
        with patch('routes_treatment.calculate') as calculate:
            response=self.client.post('/api/treatment-report',data=dict(snapshot_id='a'*64,sheet='Weekly',comparison_snapshot_id='b'*64))
            self.assertEqual(response.status_code,400);calculate.assert_not_called()
        self.assertIn('Quarterly comparison linelist',self.client.get('/dashboard').text)

    def test_netnew_and_retention_boundaries(self):
        from comparison_metrics import compare_group
        def report(weekly,quarter):
            return {'groups':{'all':{'txcurr':weekly}},'comparison':{'groups':{'all':{'txcurr':quarter}}}}
        for weekly,quarter,netnew,rate in [(120,100,20,120),(80,100,-20,80),(0,100,-100,0),(0,0,0,None),(10,0,10,None)]:
            metrics=compare_group(report(weekly,quarter))
            self.assertEqual(metrics['netnew'],netnew);self.assertEqual(metrics['retention_rate'],rate)
        self.assertIsNone(compare_group({'groups':{'all':{'txcurr':10}}})['netnew'])
        missing={'groups':{'all':{'txcurr':10}},'states':{'Delta':{'txcurr':10}},'comparison':{'states':{},'groups':{'all':{'txcurr':10}}}}
        self.assertIsNone(compare_group(missing,'Delta')['retention_rate'])

    def test_iit_rate_formula_and_decimal_display(self):
        from comparison_metrics import compare_group,rate_text
        from treatment_report import aggregate
        from activity_indicators import ActivityCounts
        from report_template import table_models,brief_view
        r=aggregate([('Active',180,None,None,None,15,'Delta')],'2026-10-17')
        baseline=aggregate([('Active',180,None,None,None,15,'Delta')]*90,'2026-09-30')
        baseline['source']={'period':'FY26Q4'};r['comparison']=baseline
        counts=ActivityCounts('2026-07-01','2026-09-30')
        counts.groups['all'].update(txnew=10,iit=7);counts.groups['paediatrics'].update(txnew=10,iit=7)
        counts.states['Delta']=dict(counts.groups['all']);counts.paediatric_states['Delta']=dict(counts.groups['paediatrics'])
        r['activity']=counts.result()
        self.assertEqual(compare_group(r)['iit_rate'],7)
        self.assertEqual(rate_text(compare_group(r)['iit_rate']),'7.0%')
        self.assertEqual(table_models(r)[1]['rows'][0][7],'7.0%')
        self.assertEqual(table_models(r)[3]['rows'][-1][7],'7.0%')
        paragraphs={p['index']:''.join(run['text'] for run in p['runs']) for p in brief_view(r)['paragraphs']}
        self.assertIn('IIT rate is 7.0%',paragraphs[16])
        r['comparison']['groups']['all']['txcurr']=0
        self.assertEqual(compare_group(r)['iit_rate'],70)
        r['activity']['groups']['all']['txnew']=0
        self.assertIsNone(compare_group(r)['iit_rate'])
        r.pop('comparison');self.assertIsNone(compare_group(r)['iit_rate'])
