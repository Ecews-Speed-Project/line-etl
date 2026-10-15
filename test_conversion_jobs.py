import io
import gzip
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from openpyxl import Workbook
from app import app
import conversion_jobs


class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root_patch=patch('conversion_jobs.JOB_ROOT',Path(self.temp.name))
        self.root_patch.start()
        self.auth_patch=patch.dict('os.environ',{'APP_ACCESS_PASSWORD':''})
        self.auth_patch.start()
        self.client=TestClient(app)

    def tearDown(self):
        self.auth_patch.stop()
        self.root_patch.stop()
        self.temp.cleanup()

    def wait(self,job_id):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            result=self.client.get('/api/conversions/'+job_id).json()
            if result['state'] in ('completed','failed'):return result
            time.sleep(.02)
        self.fail('Conversion worker did not finish')

    def test_disk_upload_progress_download_and_cleanup(self):
        book=Workbook()
        book.active.append(['State','number'])
        for n in range(1100):book.active.append(['AKWA IBOM',n])
        book.active.append(['CROSS RIVER','#DIV/0!'])
        content=io.BytesIO();book.save(content)
        job=self.client.post('/api/conversions',json={'filename':'test.xlsx'}).json()
        job_id=job['id']
        response=self.client.put('/api/conversions/'+job_id+'/file',content=content.getvalue())
        self.assertEqual(response.status_code,200)
        self.assertTrue((Path(self.temp.name)/job_id/'test.xlsx').exists())
        result=self.wait(job_id)
        self.assertEqual(result['state'],'completed')
        self.assertEqual(result['records'],1101)
        self.assertEqual(result['processed'],1101)
        self.assertEqual(result['bytes_received'],len(content.getvalue()))
        doc=self.client.get('/api/conversions/'+job_id+'/download').json()
        compressed=self.client.get('/api/conversions/'+job_id+'/download?compressed=true')
        self.assertEqual(compressed.status_code,200)
        self.assertNotIn('content-encoding',compressed.headers)
        self.assertEqual(json.loads(gzip.decompress(compressed.content)),doc)
        self.assertEqual(doc['records'][0]['data']['State'],'Akwa ibom')
        report=self.client.get('/api/conversions/'+job_id+'/errors').json()
        self.assertEqual(report['total'],1)
        self.assertEqual(report['issues'][0]['cell'],'B1102')
        self.assertEqual(self.client.delete('/api/conversions/'+job_id).status_code,200)
        self.assertFalse((Path(self.temp.name)/job_id).exists())

    def test_upload_limit_and_invalid_workbook(self):
        job=self.client.post('/api/conversions',json={'filename':'test.xlsx'}).json()['id']
        with patch('web_common.MAX_SIZE',3):
            response=self.client.put('/api/conversions/'+job+'/file',content=b'1234')
        self.assertEqual(response.status_code,400)
        self.assertFalse((Path(self.temp.name)/job/'upload.part').exists())
        self.assertEqual(self.client.get('/api/conversions/'+job).json()['state'],'failed')
        job=self.client.post('/api/conversions',json={'filename':'bad.xlsx'}).json()['id']
        self.client.put('/api/conversions/'+job+'/file',content=b'not a workbook')
        self.assertEqual(self.wait(job)['state'],'failed')
        self.assertEqual(self.client.get('/api/conversions/'+job+'/download').status_code,409)

    def test_invalid_filename_and_interrupted_job(self):
        self.assertEqual(self.client.post('/api/conversions',json={'filename':'test.exe'}).status_code,400)
        self.assertEqual(self.client.get('/api/conversions/not-a-job').status_code,404)
        job=conversion_jobs.create('test.xlsx')
        with conversion_jobs.LOCK:
            conversion_jobs.JOBS.pop(job['id'])
        self.assertEqual(self.client.get('/api/conversions/'+job['id']).json()['phase'],'interrupted')


if __name__=='__main__':unittest.main()
