import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from openpyxl import Workbook, load_workbook
from header_mapping import TARGET, propose, standardize


class MappingTests(unittest.TestCase):
    def test_conservative_suggestions_and_ambiguity(self):
        report = propose(['IP', 'IPTOutcome', 'Other_Test\\_(TB-LAM_LF-LAM_etc)', 'First_INH_Pickupdate', 'Last_INH_Pickupdate'])
        self.assertEqual(report['mapping']['IP'], 'IP')
        self.assertIsNone(report['mapping']['TPTOutcome'])
        self.assertEqual(report['suggestions']['TPTOutcome'], 'IPTOutcome')
        self.assertIsNone(report['mapping']['TPT_Startdate'])
        self.assertEqual(report['mapping']['Other_Test_(TB-LAM_LF-LAM_etc)'], 'Other_Test\\_(TB-LAM_LF-LAM_etc)')
        report = propose(['PATIENT ID', 'patient-id'])
        self.assertIsNone(report['mapping']['patient_id'])
        self.assertEqual(report['statuses']['patient_id'], 'ambiguous')

    def test_export_and_flags(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / 'old.xlsx'
            book = Workbook()
            book.active.append(['IP', 'IPTOutcome', 'Surname'])
            book.active.append(['ECEWS', 'Completed', 'Example'])
            book.save(source)
            mapping = propose(['IP', 'IPTOutcome', 'Surname'])['mapping']
            mapping['TPTOutcome'] = 'IPTOutcome'
            with self.assertRaisesRegex(ValueError, 'missing'):
                standardize(source, folder, mapping)
            result = standardize(source, folder, mapping, allow_missing=True)
            with zipfile.ZipFile(result) as archive:
                doc = json.loads(archive.read('linelist.json'))
                report = json.loads(archive.read('mapping_report.json'))
                original = json.loads(archive.read('original_data.json'))
            self.assertEqual(doc['headers'], TARGET)
            self.assertEqual(doc['records'][0]['data']['TPTOutcome'], 'Completed')
            self.assertIsNone(doc['records'][0]['data']['TPT_Startdate'])
            self.assertIn('Surname', report['unmapped_source'])
            self.assertEqual(original['records'][0]['data']['Surname'], 'Example')
            sheet = load_workbook(folder / 'current_linelist.xlsx', read_only=True)
            self.assertEqual(list(next(sheet.active.values)), TARGET)
            sheet.close()
            mapping['TPTOutcomeDate'] = 'IPTOutcome'
            with self.assertRaisesRegex(ValueError, 'only one'):
                standardize(source, folder, mapping, allow_missing=True)


if __name__ == '__main__':
    unittest.main()
