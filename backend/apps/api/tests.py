from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.analytics.services import MetricComputationService
from apps.market_data.models import Company
from apps.market_data.services import CompanyIngestionService
from apps.market_data.tests import (
    sample_basic_payload,
    sample_financials_payload,
    sample_profile_payload,
    sample_quote_payload,
)


class ApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

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

        company = Company.objects.get(ticker="AAPL")
        MetricComputationService(calculation_version="v1").compute_metrics_for_company(company)

    def test_api_root(self):
        response = self.client.get("/api/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_company_search(self):
        response = self.client.get("/api/companies/search/", {"q": "AAPL"})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertGreaterEqual(data["count"], 1)

    def test_company_detail(self):
        response = self.client.get("/api/companies/AAPL/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["company"]["ticker"], "AAPL")

    def test_company_metrics(self):
        response = self.client.get(
            "/api/companies/AAPL/metrics/",
            {"metric_codes": "profitability_gross_margin", "latest_only": "true"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertGreaterEqual(data["count"], 1)

    def test_compute_analytics_endpoint(self):
        response = self.client.post(
            "/api/analytics/compute/",
            {"ticker": "AAPL", "calc_version": "v1"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["ticker"], "AAPL")

    def test_compare_companies_validation(self):
        response = self.client.post(
            "/api/companies/compare/",
            {"tickers": ["AAPL"]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])