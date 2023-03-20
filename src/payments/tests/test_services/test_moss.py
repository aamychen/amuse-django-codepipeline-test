from datetime import datetime, timezone
from unittest import TestCase

from payments.services.moss import MossReport


class MossReportTest(TestCase):
    def test_get_period(self):
        report_1 = MossReport(year=2022, quarter=1, month=1, country='SE')

        period_start, period_end = report_1._get_period()

        self.assertEqual(period_start, datetime(2022, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(period_end, datetime(2022, 2, 1, tzinfo=timezone.utc))

        report_2 = MossReport(year=2022, quarter=1, month=None, country='SE')

        period_start, period_end = report_2._get_period()

        self.assertEqual(period_start, datetime(2022, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(period_end, datetime(2022, 4, 1, tzinfo=timezone.utc))

        report_3 = MossReport(year=2022, quarter=2, month=None, country='SE')

        period_start, period_end = report_3._get_period()

        self.assertEqual(period_start, datetime(2022, 4, 1, tzinfo=timezone.utc))
        self.assertEqual(period_end, datetime(2022, 7, 1, tzinfo=timezone.utc))

        report_4 = MossReport(year=2022, quarter=3, month=None, country='SE')

        period_start, period_end = report_4._get_period()

        self.assertEqual(period_start, datetime(2022, 7, 1, tzinfo=timezone.utc))
        self.assertEqual(period_end, datetime(2022, 10, 1, tzinfo=timezone.utc))

        report_5 = MossReport(year=2022, quarter=4, month=None, country='SE')

        period_start, period_end = report_5._get_period()

        self.assertEqual(period_start, datetime(2022, 10, 1, tzinfo=timezone.utc))
        self.assertEqual(period_end, datetime(2023, 1, 1, tzinfo=timezone.utc))

    def test_get_financial_period(self):
        report_1 = MossReport(None, 5, None, 'SE')
        today = datetime.utcnow()
        self.assertEqual(report_1.year, today.year)
        self.assertEqual(report_1.quarter, 2)
        self.assertEqual(report_1.month, 5)
        self.assertEqual(len(report_1.countries), 1)

        report_2 = MossReport(2022, 8, None, 'SE')
        self.assertEqual(report_2.year, 2022)
        self.assertEqual(report_2.quarter, 3)
        self.assertEqual(report_2.month, 8)
        self.assertEqual(len(report_1.countries), 1)

        report_3 = MossReport(2022, 11, None, None)
        self.assertEqual(report_3.year, 2022)
        self.assertEqual(report_3.quarter, 4)
        self.assertEqual(report_3.month, 11)
        self.assertGreater(len(report_3.countries), 1)
