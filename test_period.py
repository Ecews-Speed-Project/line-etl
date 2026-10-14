from datetime import date
import unittest
from upload_json import parse_period


class PeriodTests(unittest.TestCase):
    def test_valid_calendar_date(self):
        self.assertEqual(parse_period('2024-02-29'), date(2024,2,29))
        self.assertEqual(parse_period(date(2026,10,14)), date(2026,10,14))

    def test_reject_invalid_or_ambiguous_period(self):
        for value in [None, '', '14/10/2026', '20261014', '2026-02-29', '2026-10-14T00:00:00']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_period(value)


if __name__ == '__main__':
    unittest.main()
