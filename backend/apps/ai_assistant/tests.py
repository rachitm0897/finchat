from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.ai_assistant.domain_services import SessionMemoryService
from apps.ai_assistant.services import FinancialAssistantGraphService
from apps.ai_assistant.tools import (
    company_lookup_tool,
    compare_companies_tool,
    get_company_overview_tool,
    get_computed_metrics_tool,
    get_growth_summary_tool,
    get_risk_flags_tool,
    get_valuation_summary_tool,
)
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
    def invoke(self, messages):
        from apps.ai_assistant.schemas import PlannerOutput

        text = messages[-1].content.lower()
        if "portfolio" in text:
            return PlannerOutput(
                intent="portfolio_analysis",
                companies=["AAPL", "MSFT"],
                needs_comparison=True,
                analysis_modes=["valuation", "growth", "risk"],
                requested_metric_codes=[],
                notes="mock planner",
            )
        if "backtest" in text:
            return PlannerOutput(
                intent="backtesting",
                companies=["AAPL"],
                needs_comparison=False,
                analysis_modes=["valuation", "risk"],
                requested_metric_codes=[],
                notes="mock planner",
            )
        if "compare" in text:
            return PlannerOutput(
                intent="comparison",
                companies=["AAPL", "MSFT"],
                needs_comparison=True,
                analysis_modes=["valuation", "growth", "risk"],
                requested_metric_codes=[],
                notes="mock planner",
            )
        return PlannerOutput(
            intent="valuation",
            companies=["AAPL"],
            needs_comparison=False,
            analysis_modes=["valuation", "risk"],
            requested_metric_codes=[],
            notes="mock planner",
        )


class DummyChatModel:
    def with_structured_output(self, schema):
        return DummyStructuredPlanner()


class ToolAndGraphTests(TestCase):
    def setUp(self):
        with patch("apps.market_data.services.FinnhubClient") as mock_client_cls:
            mock_client = mock_client_cls.return_value

            mock_client.get_company_profile.return_value.endpoint_name = "company_profile"
            mock_client.get_company_profile.return_value.params = {"symbol": "AAPL"}
            mock_client.get_company_profile.return_value.status_code = 200
            mock_client.get_company_profile.return_value.payload = sample_profile_payload("AAPL")

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
            mock_client.get_financials_reported.return_value.payload = sample_financials_payload("AAPL")

            CompanyIngestionService(client=mock_client).ingest_company("AAPL", ingest_statements=True)

            mock_client.get_company_profile.return_value.payload = sample_profile_payload("MSFT")
            mock_client.get_financials_reported.return_value.payload = sample_financials_payload("MSFT")
            CompanyIngestionService(client=mock_client).ingest_company("MSFT", ingest_statements=True)

        for ticker in ["AAPL", "MSFT"]:
            company = Company.objects.get(ticker=ticker)
            MetricComputationService(calculation_version="v1").compute_metrics_for_company(company)

    def test_company_lookup_tool(self):
        result = company_lookup_tool.invoke({"query": "AAPL"})
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["count"], 1)

    def test_company_overview_tool(self):
        result = get_company_overview_tool.invoke({"ticker": "AAPL"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["company"]["ticker"], "AAPL")

    def test_computed_metrics_tool(self):
        result = get_computed_metrics_tool.invoke(
            {
                "ticker": "AAPL",
                "metric_codes": ["profitability_gross_margin", "summary_quality_score"],
                "latest_only": True,
            }
        )
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["count"], 1)

    def test_group_tools(self):
        self.assertTrue(get_valuation_summary_tool.invoke({"ticker": "AAPL"})["ok"])
        self.assertTrue(get_growth_summary_tool.invoke({"ticker": "AAPL"})["ok"])
        self.assertTrue(get_risk_flags_tool.invoke({"ticker": "AAPL"})["ok"])

    def test_compare_companies_tool(self):
        result = compare_companies_tool.invoke({"tickers": ["AAPL", "MSFT"]})
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["results"]), 2)

    def test_memory_resolution(self):
        result = SessionMemoryService().resolve_companies(
            query="compare it with MSFT",
            planned_companies=["MSFT"],
            session_context={"memory": {"last_companies_used": ["AAPL"]}},
        )
        self.assertEqual(result, ["MSFT"])

        result2 = SessionMemoryService().resolve_companies(
            query="compare it on valuation",
            planned_companies=[],
            session_context={"memory": {"last_companies_used": ["AAPL"]}},
        )
        self.assertEqual(result2, ["AAPL"])

    @patch("apps.ai_assistant.graph.get_chat_model")
    def test_langgraph_workflow_returns_structured_response(self, mock_get_chat_model):
        mock_get_chat_model.return_value = DummyChatModel()

        result = FinancialAssistantGraphService().run(
            user_query="Give me a valuation and risk review of AAPL",
            session_context={},
        )

        self.assertIn("final_answer", result)
        self.assertIn("final_payload", result)
        self.assertIn("structured_response", result["final_payload"])
        self.assertIn("confidence_score", result["final_payload"]["structured_response"])

    @patch("apps.ai_assistant.graph.get_chat_model")
    def test_portfolio_workflow(self, mock_get_chat_model):
        mock_get_chat_model.return_value = DummyChatModel()

        result = FinancialAssistantGraphService().run(
            user_query="Analyze this portfolio: AAPL and MSFT",
            session_context={},
        )

        structured = result["final_payload"]["structured_response"]
        self.assertIn("portfolio", structured)
        self.assertTrue(structured["portfolio"])

    @patch("apps.ai_assistant.graph.get_chat_model")
    def test_backtesting_workflow_graceful_when_missing(self, mock_get_chat_model):
        mock_get_chat_model.return_value = DummyChatModel()

        result = FinancialAssistantGraphService().run(
            user_query="Run a moving average backtest on AAPL",
            session_context={},
        )

        structured = result["final_payload"]["structured_response"]
        self.assertIn("backtesting", structured)