import json
import gzip
import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook
from excel_to_json import convert


class CdrExportTests(unittest.TestCase):
    def test_records_only_conversion_is_plain_row_array(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.xlsx'
            book=Workbook()
            book.active.title='First'
            book.active.append(['id','state'])
            book.active.append(['001','DELTA'])
            second=book.create_sheet('Second')
            second.append(['id','state'])
            second.append(['002','EKITI'])
            book.save(source)
            output=Path(folder)/'sheet.json'
            count=convert(source,output,'Second',records_only=True)
            self.assertEqual(count,1)
            self.assertEqual(json.loads(output.read_text()),[{'id':'002','state':'Ekiti'}])
            compressed=Path(folder)/'sheet.json.gz'
            with gzip.open(compressed,'wt',encoding='utf-8') as stream:
                json.dump(json.loads(output.read_text()),stream)
            with gzip.open(compressed,'rt',encoding='utf-8') as stream:
                self.assertEqual(json.load(stream),[{'id':'002','state':'Ekiti'}])
