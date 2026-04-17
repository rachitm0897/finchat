from __future__ import annotations
from django.test import TestCase

# Create your tests here.


from django.test import TestCase

from apps.fundamentals.services import FinnhubFinancialStatementParser
from apps.market_data.tests import sample_financials_payload


class FinancialStatementParserTests(TestCase):
    def test_parser_extracts_expected_values(self):
        payload = sample_financials_payload()
        rows = FinnhubFinancialStatementParser.parse(payload, default_currency="USD")

        self.assertEqual(len(rows), 1)
        row = rows[0]

        self.assertEqual(row.period_type, "annual")
        self.assertEqual(row.fiscal_year, 2025)
        self.assertIsNone(row.fiscal_quarter)
        self.assertEqual(str(row.period_end_date), "2025-09-27")
        self.assertEqual(row.currency_code, "USD")

        self.assertIsNotNone(row.income_statement["revenue"])
        self.assertIsNotNone(row.balance_sheet["total_assets"])
        self.assertIsNotNone(row.cash_flow_statement["cash_from_operating_activities"])