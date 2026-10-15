import gzip
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from upload_json import read_document
from json_compression import compress_json


class GzipTests(unittest.TestCase):
    def document(self):
        return dict(format_version=1,source_sha256='d'*64,source_file='test.xlsx',sheet='Sheet1',
                    headers=['State'],records=[dict(source_row=2,data={'State':'Akwa ibom'})])

    def test_gzip_matches_plain_and_limits_expansion(self):
        with tempfile.TemporaryDirectory() as folder:
            plain=Path(folder)/'test.json';compressed=Path(folder)/'test.json.gz'
            plain.write_text(json.dumps(self.document()),encoding='utf-8')
            compress_json(plain,compressed)
            self.assertEqual(read_document(plain),read_document(compressed))
            # Detect compressed content even if its temporary filename is .json.
            disguised=Path(folder)/'review.json';disguised.write_bytes(compressed.read_bytes())
            self.assertEqual(read_document(disguised),self.document())
            compressed.write_bytes(compressed.read_bytes()[:-5])
            with self.assertRaisesRegex(ValueError,'gzip'):read_document(compressed)
            with gzip.open(compressed,'wb') as output:output.write(b' '*2*1024*1024)
            with patch.dict(os.environ,{'LINELIST_MAX_JSON_MB':'1'}):
                with self.assertRaisesRegex(ValueError,'Expanded JSON'):read_document(compressed)
            compressed.write_bytes(b'not a gzip file')
            with self.assertRaisesRegex(ValueError,'gzip'):read_document(compressed)

    def test_review_and_upload_accept_compressed_json(self):
        data=gzip.compress(json.dumps(self.document()).encode())
        with patch.dict(os.environ,{'APP_ACCESS_PASSWORD':''}):
            client=TestClient(app)
            response=client.post('/api/review-json',files={'file':('test.json.gz',data)})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['rows'],1)
            with patch('routes_upload.upload',return_value=1) as uploader:
                response=client.post('/api/upload',files={'file':('test.json.gz',data)},data={'period':'2026-10-15'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(uploader.call_args.kwargs['document'],self.document())
            response=client.post('/api/review-json',files={'file':('bad.json.gz',b'broken')})
            self.assertEqual(response.status_code,400)
