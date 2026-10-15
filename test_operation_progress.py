import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from operation_progress import create,callback,get


class ProgressTests(unittest.TestCase):
    def test_progress_lifecycle_and_reuse(self):
        job=create('upload')
        report=callback(job['id'],'upload')
        report(dict(phase='inserting',processed=500,total=1000,inserted=490,skipped=10))
        self.assertEqual(get(job['id'])['processed'],500)
        with self.assertRaises(ValueError):callback(job['id'],'upload')
        report(dict(phase='completed',state='completed',processed=1000))
        self.assertEqual(get(job['id'])['state'],'completed')

    def test_progress_routes(self):
        with patch.dict('os.environ',{'APP_ACCESS_PASSWORD':''}):
            client=TestClient(app)
            response=client.post('/api/progress/flatten')
            self.assertEqual(response.status_code,200)
            self.assertEqual(client.get('/api/progress/'+response.json()['id']).status_code,200)
            self.assertEqual(client.post('/api/progress/invalid').status_code,400)
            self.assertEqual(client.get('/api/progress/unknown').status_code,404)
