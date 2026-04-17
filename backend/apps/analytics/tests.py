from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.analytics.models import ComputedMetricSnapshot
from apps.analytics.selectors import get_latest_metric_snapshot
from apps.analytics.services import MetricComputationService
from apps.market_data.models import Company
from apps.market_data.services import CompanyIngestionService
from apps.market_data.tests import (
    sample_basic_payload,
    sample_financials_payload,
    sample_profile_payload,
    sample_quote_payload,
)


class AnalyticsComputationTests(TestCase):
    def setUp(self):
        with patch("apps.market_data.services.FinnhubClient") as mock_client_cls:
            mock_client = mock_client_cls.return_value

            mock_client.get_company_profile.return_value.endpoint_name = "company_profile"
            mock_client.get_company_profile.return_value.params = {"symbol": "AAPL"}
            mock_client.get_company_profile.return_value.status_code = 200
            mock_client.get_company_profile.return_value.payload = sample_profile_payload()

            mock_client.get_quote.return_value.endpoint_name = "quote"
            mock_client.get_quote.return_value.params = {"symbol": "AAPL"}
            mock_client.get_quote.return_value.status_code = 200
            mock_client.get_quote.return_value.payload = sample_quote_payload()

            mock_client.get_basic_financials.return_value.endpoint_name = "basic_financials"
            mock_client.get_basic_financials.return_value.params = {"symbol": "AAPL", "metric": "all"}
            mock_client.get_basic_financials.return_value.status_code = 200
            mock_client.get_basic_financials.return_value.payload = sample_basic_payload()

            mock_client.get_financials_reported.return_value.endpoint_name = "financials_reported"
            mock_client.get_financials_reported.return_value.params = {"symbol": "AAPL"}
            mock_client.get_financials_reported.return_value.status_code = 200
            mock_client.get_financials_reported.return_value.payload = sample_financials_payload()

            CompanyIngestionService(client=mock_client).ingest_company("AAPL", ingest_statements=True)

    def test_compute_metrics_for_company(self):
        company = Company.objects.get(ticker="AAPL")
        result = MetricComputationService(calculation_version="v1").compute_metrics_for_company(company)

        self.assertEqual(result.ticker, "AAPL")
        self.assertGreater(result.metrics_written + result.metrics_updated, 0)
        self.assertGreater(ComputedMetricSnapshot.objects.filter(company=company).count(), 0)

    def test_latest_metric_snapshot_selector(self):
        company = Company.objects.get(ticker="AAPL")
        MetricComputationService(calculation_version="v1").compute_metrics_for_company(company)

        snapshot = get_latest_metric_snapshot(company, "profitability_gross_margin")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.metric_code, "profitability_gross_margin")
        self.assertIsNotNone(snapshot.metric_value)

    def test_repeated_computation_updates_not_duplicates(self):
        company = Company.objects.get(ticker="AAPL")
        service = MetricComputationService(calculation_version="v1")

        service.compute_metrics_for_company(company)
        first_count = ComputedMetricSnapshot.objects.filter(company=company).count()

        service.compute_metrics_for_company(company)
        second_count = ComputedMetricSnapshot.objects.filter(company=company).count()

        self.assertEqual(first_count, second_count)