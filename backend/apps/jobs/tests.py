from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.jobs.models import JobRun
from apps.jobs.services import JobDispatchService
from apps.market_data.services import CompanyIngestionService
from apps.market_data.tests import (
    sample_basic_payload,
    sample_financials_payload,
    sample_profile_payload,
    sample_quote_payload,
)


class JobDispatchTests(TestCase):
    @patch("apps.market_data.services.FinnhubClient")
    def setUp(self, mock_client_cls):
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

    def test_sync_analytics_job_dispatch(self):
        result = JobDispatchService().dispatch_analytics_refresh_job(
            ticker="AAPL",
            async_mode=False,
            calculation_version="v1",
        )

        self.assertEqual(result.mode, "sync")
        self.assertEqual(result.result["job_status"], JobRun.STATUS_SUCCESS)

        job = JobRun.objects.get(id=result.job_id)
        self.assertEqual(job.status, JobRun.STATUS_SUCCESS)

    @patch("apps.jobs.tasks.run_ingestion_job_task.delay")
    def test_async_ingestion_job_dispatch(self, mock_delay):
        class DummyTaskResult:
            id = "celery-task-123"

        mock_delay.return_value = DummyTaskResult()

        result = JobDispatchService().dispatch_ingestion_job(
            ticker="AAPL",
            async_mode=True,
        )

        self.assertEqual(result.mode, "async")
        self.assertEqual(result.celery_task_id, "celery-task-123")

        job = JobRun.objects.get(id=result.job_id)
        self.assertEqual(job.celery_task_id, "celery-task-123")