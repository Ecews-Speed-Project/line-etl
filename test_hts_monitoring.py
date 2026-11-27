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
 def test_excel_uses_same_counts_and_linkage_as_csv(self):
  from io import BytesIO
  from openpyxl import Workbook
  book=Workbook();sheet=book.active
  sheet.append(['State','LGA','Facility','HTS_TST_POS','TX_NEW total','TX_NEW unique'])
  sheet.append(['Delta','LGA','Clinic',100,98,97])
  output=BytesIO();book.save(output);book.close()
  result=parse(output.getvalue())
  self.assertEqual(result['total']['linkage'],98)
  self.assertEqual(result['total']['unique_linkage'],97)
 def test_word_report_recomputes_totals_and_contains_summary(self):
  from fastapi import FastAPI
  from fastapi.testclient import TestClient
  from routes_hts import router
  from io import BytesIO
  from docx import Document
  app=FastAPI();app.include_router(router)
  row=dict(state='Delta',lga='LGA',facility='Clinic',hts_pos=100,txnew=98,unique=97,prints=97,no_prints=1,non_unique=1)
  response=TestClient(app).post('/api/hts-monitoring/word',json={'facilities':[row],'source':'Test period'})
  self.assertEqual(response.status_code,200,response.text)
  doc=Document(BytesIO(response.content));text=' '.join(p.text for p in doc.paragraphs)
  self.assertIn('Key Observation and Action Required',text);self.assertIn('Conclusive remark',text);self.assertIn('97.0%',text)
  self.assertIn('98.0%',' '.join(c.text for t in doc.tables for row in t.rows for c in row.cells))
  self.assertEqual(len(doc.tables),4)

 def test_no_print_header_is_used_in_state_and_overall_totals(self):
  data=b'State,LGA,Facility,HTS_TST_POS,TX_NEW total,TX_NEW unique,Print capture,No Print,TX_NEW non-unique\nDelta,L,A,10,9,6,7,2,3\nDelta,L,B,5,4,3,1,3,1\n'
  report=parse(data)
  self.assertEqual(report['total']['no_prints'],5)
  self.assertEqual(report['total']['prints'],8)
  self.assertEqual(report['states'][0]['no_prints'],5)
  self.assertEqual(report['facilities'][0]['no_prints'],2)
 def test_no_print_heading_ignores_case_and_spaces(self):
  report=parse(b'State,LGA,Facility,HTS_TST_POS,TX_NEW total,TX_NEW unique, no  PRINT \nDelta,L,A,10,9,6,4\n')
  self.assertEqual(report['total']['no_prints'],4)

 def test_word_top_five_unique_rankings(self):
  from hts_word_report import unique_rankings
  rows=[dict(facility=f'Clinic {i:02}',lga='LGA',hts_pos=100,unique_linkage=i*10) for i in range(8)]
  rows.append(dict(facility='No positives',lga='LGA',hts_pos=0,unique_linkage=None))
  self.assertEqual([r['unique_linkage'] for r in unique_rankings(rows)],[70,60,50,40,30])
  self.assertEqual([r['unique_linkage'] for r in unique_rankings(rows,False)],[0,10,20,30,40])
  self.assertEqual(unique_rankings([rows[-1]]),[])

 def test_narrative_proportions_and_zero_denominators(self):
  from hts_word_report import performance_paragraphs
  g=dict(hts_pos=200,txnew=100,unique=80,prints=90,no_prints=10,non_unique=10)
  text=' '.join(performance_paragraphs(g,'Delta'))
  for value in ['50.0%','40.0%','90.0%','10.0%','11.1%']:self.assertIn(value,text)
  self.assertIn('uploaded reporting period',text)
  zero={k:0 for k in g};self.assertIn('N/A',' '.join(performance_paragraphs(zero,'Delta')))

 def test_precomputed_ecews_and_state_subtotals_are_not_counted(self):
  data=b'State,LGA,Facility,HTS_TST_POS,TX_NEW total,TX_NEW unique,Prints captured,No prints,TX_NEW non-unique\nDelta,L,A,10,9,8,8,1,1\nEkiti,L,B,5,4,3,3,1,1\nOsun,L,C,5,5,4,4,1,1\nTotal: ECEWS SPEED,,,20,18,15,15,3,3\nDelta,,Total Delta,10,9,8,8,1,1\n'
  result=parse(data)
  self.assertEqual([r['state'] for r in result['states']],['Delta','Ekiti','Osun'])
  self.assertEqual(result['excluded_summary_rows'],2)
  self.assertEqual(len(result['facilities']),3)
  for key in ['hts_pos','txnew','unique','prints','no_prints','non_unique']:
   self.assertEqual(result['total'][key],sum(row[key] for row in result['states']))
  self.assertEqual(result['total']['hts_pos'],20)
  self.assertEqual(result['total']['no_prints'],3)
  self.assertEqual(result['total']['linkage'],90)
  self.assertEqual(result['total']['unique_linkage'],75)
 def test_word_download_excludes_summary_rows_from_existing_payload(self):
  from fastapi import FastAPI
  from fastapi.testclient import TestClient
  from routes_hts import router
  from io import BytesIO
  from docx import Document
  app=FastAPI();app.include_router(router)
  rows=[dict(state='Delta',lga='L',facility='Clinic',hts_pos=10,txnew=9,unique=8,prints=8,no_prints=1,non_unique=1),dict(state='Total: ECEWS SPEED',lga='',facility='',hts_pos=10,txnew=9,unique=8,prints=8,no_prints=1,non_unique=1)]
  response=TestClient(app).post('/api/hts-monitoring/word',json={'facilities':rows,'source':'Fixture'})
  self.assertEqual(response.status_code,200)
  doc=Document(BytesIO(response.content));text=' '.join(p.text for p in doc.paragraphs)+' '.join(c.text for t in doc.tables for row in t.rows for c in row.cells)
  self.assertNotIn('Total: ECEWS SPEED',text)
  self.assertIn('90.0%',text)
  self.assertIn('ECEWS total',text)
