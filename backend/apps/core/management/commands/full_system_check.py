from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from apps.ai_assistant.services import FinancialAssistantGraphService
from apps.analytics.services import MetricComputationService
from apps.market_data.models import Company
from apps.market_data.services import CompanyIngestionService
from apps.market_data.tests import (
    sample_basic_payload,
    sample_financials_payload,
    sample_profile_payload,
    sample_quote_payload,
)


class DummyStructuredPlanner:
    def __init__(self, ticker: str):
        self.ticker = ticker

    def invoke(self, messages):
        from apps.ai_assistant.schemas import PlannerOutput

        return PlannerOutput(
            intent="valuation",
            companies=[self.ticker],
            needs_comparison=False,
            analysis_modes=["valuation", "risk"],
            requested_metric_codes=[],
            notes="full system check mock planner",
        )


class DummyChatModel:
    def __init__(self, ticker: str):
        self.ticker = ticker

    def with_structured_output(self, schema):
        return DummyStructuredPlanner(self.ticker)

    def invoke(self, messages):
        class Result:
            content = "System check chat response generated from grounded tool outputs."

        return Result()


class Command(BaseCommand):
    help = "Run an end-to-end backend validation check."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ticker",
            default="AAPL",
            help="Ticker used for the system check flow.",
        )
        parser.add_argument(
            "--use-real-services",
            action="store_true",
            help="Use real Finnhub/LLM integrations instead of mocked local validation mode.",
        )
        parser.add_argument(
            "--show-details",
            action="store_true",
            help="Print full result payload JSON.",
        )

    def handle(self, *args, **options):
        ticker = str(options["ticker"]).strip().upper()
        use_real_services = bool(options["use_real_services"])
        show_details = bool(options["show_details"])

        results: dict[str, Any] = {
            "overall_ok": True,
            "checks": {},
        }

        def record(name: str, ok: bool, details: dict[str, Any]):
            results["checks"][name] = {
                "ok": ok,
                "details": details,
            }
            if not ok:
                results["overall_ok"] = False

        # 1. Apps load
        expected_apps = [
            "apps.core",
            "apps.market_data",
            "apps.fundamentals",
            "apps.analytics",
            "apps.ai_assistant",
            "apps.report",
            "apps.jobs",
            "apps.api",
        ]
        installed = list(settings.INSTALLED_APPS)
        missing_apps = [name for name in expected_apps if name not in installed]
        record(
            "apps_load",
            ok=not missing_apps,
            details={"missing_apps": missing_apps, "installed_count": len(installed)},
        )

        # 2. Database works
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
            record("database", ok=(row[0] == 1), details={"probe_result": row[0]})
        except Exception as exc:
            record("database", ok=False, details={"error": str(exc)})

        # 3. Environment variables
        env_checks = {
            "FINNHUB_API_KEY_present": bool(getattr(settings, "FINNHUB_API_KEY", "")),
            "LLM_MODEL_NAME_present": bool(getattr(settings, "LLM_MODEL_NAME", "")),
            "CELERY_BROKER_URL_present": bool(getattr(settings, "CELERY_BROKER_URL", "")),
        }
        if use_real_services:
            env_checks["LLM_API_KEY_present"] = bool(getattr(settings, "LLM_API_KEY", ""))
            env_ok = all(env_checks.values())
        else:
            env_ok = env_checks["LLM_MODEL_NAME_present"] and env_checks["CELERY_BROKER_URL_present"]

        record("environment", ok=env_ok, details=env_checks)

        # 4. Ingestion
        try:
            if use_real_services:
                ingestion_result = CompanyIngestionService().ingest_company(ticker=ticker, ingest_statements=True)
                ingest_payload = {
                    "ticker": ingestion_result.ticker,
                    "company_id": ingestion_result.company_id,
                    "statements_result": ingestion_result.statements_result,
                    "warnings": ingestion_result.warnings,
                }
                ingest_ok = True
            else:
                with patch("apps.market_data.services.FinnhubClient") as mock_client_cls:
                    mock_client = mock_client_cls.return_value

                    mock_client.get_company_profile.return_value.endpoint_name = "company_profile"
                    mock_client.get_company_profile.return_value.params = {"symbol": ticker}
                    mock_client.get_company_profile.return_value.status_code = 200
                    mock_client.get_company_profile.return_value.payload = sample_profile_payload(ticker)

                    mock_client.get_quote.return_value.endpoint_name = "quote"
                    mock_client.get_quote.return_value.params = {"symbol": ticker}
                    mock_client.get_quote.return_value.status_code = 200
                    mock_client.get_quote.return_value.payload = sample_quote_payload()

                    mock_client.get_basic_financials.return_value.endpoint_name = "basic_financials"
                    mock_client.get_basic_financials.return_value.params = {"symbol": ticker, "metric": "all"}
                    mock_client.get_basic_financials.return_value.status_code = 200
                    mock_client.get_basic_financials.return_value.payload = sample_basic_payload()

                    mock_client.get_financials_reported.return_value.endpoint_name = "financials_reported"
                    mock_client.get_financials_reported.return_value.params = {"symbol": ticker}
                    mock_client.get_financials_reported.return_value.status_code = 200
                    mock_client.get_financials_reported.return_value.payload = sample_financials_payload(ticker)

                    ingestion_result = CompanyIngestionService(client=mock_client).ingest_company(
                        ticker=ticker,
                        ingest_statements=True,
                    )

                ingest_payload = {
                    "ticker": ingestion_result.ticker,
                    "company_id": ingestion_result.company_id,
                    "statements_result": ingestion_result.statements_result,
                    "warnings": ingestion_result.warnings,
                }
                ingest_ok = True

            record("ingestion", ok=ingest_ok, details=ingest_payload)
        except Exception as exc:
            record("ingestion", ok=False, details={"error": str(exc)})

        # 5. Metrics compute
        try:
            company = Company.objects.get(ticker=ticker)
            metric_result = MetricComputationService(calculation_version="v1").compute_metrics_for_company(company)
            record(
                "analytics_compute",
                ok=(metric_result.metrics_written + metric_result.metrics_updated) > 0,
                details={
                    "ticker": metric_result.ticker,
                    "periods_seen": metric_result.periods_seen,
                    "metrics_written": metric_result.metrics_written,
                    "metrics_updated": metric_result.metrics_updated,
                    "metrics_skipped": metric_result.metrics_skipped,
                },
            )
        except Exception as exc:
            record("analytics_compute", ok=False, details={"error": str(exc)})

        # 6. Chat question
        try:
            if use_real_services:
                graph_result = FinancialAssistantGraphService().run(
                    user_query=f"Give me a valuation and risk review of {ticker}"
                )
            else:
                with patch("apps.ai_assistant.graph.get_chat_model", return_value=DummyChatModel(ticker)):
                    graph_result = FinancialAssistantGraphService().run(
                        user_query=f"Give me a valuation and risk review of {ticker}"
                    )

            answer = graph_result.get("final_answer", "")
            record(
                "chat_flow",
                ok=bool(answer),
                details={
                    "resolved_companies": graph_result.get("resolved_companies", []),
                    "answer_preview": answer[:300],
                },
            )
        except Exception as exc:
            record("chat_flow", ok=False, details={"error": str(exc)})

        # Final output
        if show_details:
            self.stdout.write(json.dumps(results, indent=2, default=str))
        else:
            self.stdout.write(f"overall_ok={results['overall_ok']}")
            for name, payload in results["checks"].items():
                self.stdout.write(f"[{'OK' if payload['ok'] else 'FAIL'}] {name}")