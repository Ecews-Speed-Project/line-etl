from datetime import date
import unittest
from unittest.mock import patch
from io import BytesIO
from zipfile import ZipFile
from fastapi.testclient import TestClient
from app import app
from treatment_report import aggregate,window


class TreatmentTests(unittest.TestCase):
    def test_cumulative_filters_and_boundaries(self):
        rows=[('Active','180','2025-09-19','2026-09-19','49','19'),
              (' active ','180','2026-09-19','2025-09-19','50','20'),
              ('Active','181','2026-09-20','2026-09-19','999','30'),
              ('Active','180',None,'2026-09-19','1000',None),
              ('Active','179','2026-09-01','2026-09-01','0','10'),
              ('LTFU','180','2026-09-01','2026-09-01','10','10'),
              ('Active','180','2026-09-01','2025-09-18','10','30'),
              ('Active','180','2026-09-01','2026-09-19','bad','30'),
              ('Active','180','2026-09-01','2026-09-19','-1','30')]
        report=aggregate(rows,'2026-09-19');g=report['groups']['all']
        self.assertEqual([g[k] for k in ['txcurr','eligible','sample_collected','result','vl_suppression','undetectable','llv','unsuppressed']], [8,7,5,4,3,1,2,1])
        self.assertAlmostEqual(g['coverage'],400/7)
        self.assertEqual(g['suppression_rate'],75)
        self.assertEqual(g['undetectable_rate'],25)
        self.assertEqual(g['llv_rate'],50)
        self.assertEqual(report['groups']['paediatrics']['txcurr'],2)
        self.assertEqual(report['quality']['active_unknown_age'],1)

    def test_state_totals_and_weighted_rates(self):
        rows=[('Active','180',None,'2026-09-19','49','19','DELTA'),
              ('Active','180',None,'2026-09-19','1000','20','delta'),
              ('Active','180',None,None,None,'20','Ekiti'),
              ('Active','180',None,'2026-09-19','50','20',None)]
        report=aggregate(rows,'2026-09-19')
        self.assertEqual(report['states']['Delta']['txcurr'],2)
        self.assertEqual(report['states']['Delta']['suppression_rate'],50)
        self.assertEqual(report['states']['Unknown state']['llv'],1)
        for key in ['txcurr','eligible','result','vl_suppression','unsuppressed']:
            self.assertEqual(sum(g[key] for g in report['states'].values()),report['groups']['all'][key])
        self.assertEqual(report['groups']['all']['coverage'],75)

    def test_paediatric_age_boundaries_and_subtotals(self):
        ages=['0','0.99','1','4.99','5','9.99','10','14.99','15','19.99','20',None,'-1']
        rows=[('Active','180','2026-09-19','2026-09-19','49',age,'Delta') for age in ages]
        report=aggregate(rows,'2026-09-19');state=report['paediatric_states']['Delta']
        self.assertEqual([g['txcurr'] for g in state['bands'].values()],[2,2,2,2,2])
        self.assertEqual(state['total']['txcurr'],10)
        self.assertEqual(state['total'],report['groups']['paediatrics'])
        self.assertEqual(state['total']['sample_collection_rate'],100)
        for key in ['txcurr','eligible','result','sample_collected']:
            self.assertEqual(sum(g[key] for g in state['bands'].values()),state['total'][key])
        empty=aggregate([('Active','0',None,None,None,'3','Ekiti')],'2026-09-19')
        self.assertIsNone(empty['paediatric_states']['Ekiti']['total']['sample_collection_rate'])

    def test_empty_denominators_and_leap_year(self):
        result=aggregate([],'2026-09-19')['groups']['all']
        self.assertIsNone(result['coverage']);self.assertIsNone(result['suppression_rate'])
        self.assertEqual(window('2024-02-29'),(date(2023,2,28),date(2024,2,29)))

    def test_decimal_llv_and_invalid_assay_values(self):
        rows=[('Active','180',None,'2026-09-19',v,'30') for v in ['999.9','NaN','Infinity','<50',None]]
        result=aggregate(rows,'2026-09-19')['groups']['all']
        self.assertEqual(result['result'],1);self.assertEqual(result['llv'],1)

    def test_report_route_and_word_export(self):
        report=aggregate([('Active','180','2026-09-19','2026-09-19','25','19')],'2026-09-19')
        report['source']=dict(file='test.xlsx',sheet='Sheet1',period='2026-09-19',rows=1,snapshot_id='a'*64)
        with patch.dict('os.environ',{'APP_ACCESS_PASSWORD':''}),patch('routes_treatment.calculate',return_value=report):
            client=TestClient(app)
            fields={'snapshot_id':'a'*64,'sheet':'Sheet1'}
            response=client.post('/api/treatment-report',data=fields)
            self.assertEqual(response.json()['groups']['all']['result'],1)
            response=client.post('/api/treatment-report',data=dict(fields,word='true'))
            self.assertEqual(response.status_code,200)
            self.assertIn('.docx',response.headers['content-disposition'])
            with ZipFile(BytesIO(response.content)) as archive:
                xml=archive.read('word/document.xml').decode()
                self.assertIn('Key findings from',xml)
                self.assertIn('100%',xml)
                self.assertIn('word/media/image3.png',archive.namelist())

    def test_brief_template_slots_and_preserved_package(self):
        from report_template import brief_view,TEMPLATE,NS
        from report_document import build
        from lxml import etree
        report=aggregate([('Active','180',None,'2026-09-19','25','19','Delta'),('Active','180',None,'2026-09-19','1000','20','Delta')],'2027-01-01')
        report['source']=dict(file='test.xlsx',period='2027-01-01')
        view=brief_view(report);paras={p['index']:''.join(r['text'] for r in p['runs']) for p in view['paragraphs']}
        self.assertIn('@1ST January 2027',paras[0])
        self.assertIn('100%'+chr(160)+'Coverage',paras[21])
        self.assertIn('50% Suppression',paras[21])
        self.assertIn('N/A',paras[6]);self.assertNotIn('76',paras[6])
        self.assertEqual(len(view['tables']),4)
        with ZipFile(TEMPLATE) as original,ZipFile(BytesIO(build(report))) as final:
            changed={'word/document.xml','word/_rels/document.xml.rels','[Content_Types].xml'}
            for name in original.namelist():
                if name not in changed and not name.startswith('word/media/'):
                    self.assertEqual(original.read(name),final.read(name),name)
            self.assertFalse(any(n.endswith('.emf') for n in final.namelist()))
            root=etree.fromstring(final.read('word/document.xml'))
            self.assertIsNone(root.find('.//w:sectPr/w:r',NS))

    def test_bad_dates_and_nonnumeric_values_are_not_guessed(self):
        from treatment_report import calendar_date,number
        self.assertIsNone(calendar_date('2026-09-19junk'))
        self.assertIsNone(calendar_date('19/09/2026'))
        self.assertIsNone(number('1_80'))
