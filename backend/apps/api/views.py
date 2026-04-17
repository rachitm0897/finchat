from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai_assistant.services import ChatSessionService, FinancialAssistantGraphService
from apps.analytics.selectors import (
    get_company_metric_snapshots,
    get_latest_metric_snapshot,
)
from apps.analytics.services import MetricComputationService
from apps.api.serializers import (
    ChatMessageCreateRequestSerializer,
    ChatMessageSerializer,
    ChatQueryRequestSerializer,
    ChatSessionCreateRequestSerializer,
    ChatSessionSerializer,
    CompanyBasicMetricSnapshotSerializer,
    CompanyComparisonRowSerializer,
    CompanyDetailResponseSerializer,
    CompanyIngestRequestSerializer,
    CompanyMetricsQuerySerializer,
    CompanyProfileSnapshotSerializer,
    CompanyQuoteSnapshotSerializer,
    CompanySearchQuerySerializer,
    CompanySerializer,
    CompareCompaniesRequestSerializer,
    ComputedMetricSnapshotSerializer,
    ComputeAnalyticsRequestSerializer,
    JobRunSerializer,
    TickerUniverseSearchQuerySerializer,
    TickerUniverseSearchResultSerializer,
)
from apps.jobs.selectors import get_job_run_by_id
from apps.jobs.services import JobDispatchService
from apps.market_data.clients.finnhub import (
    FinnhubAPIError,
    FinnhubMissingAPIKeyError,
    FinnhubNotFoundError,
    FinnhubRateLimitError,
    # FinnhubTickerSearchService,
)
from apps.market_data.selectors import (
    get_company_by_ticker,
    get_company_detail_counts,
    get_company_latest_basic_metric_snapshot,
    get_company_latest_financial_period_payload,
    get_company_latest_profile_snapshot,
    get_company_latest_quote_snapshot,
    search_companies,
)
from apps.market_data.services import CompanyIngestionService, FinnhubTickerSearchService
from apps.core.observability import ObservabilityService



def success_response(data, http_status=status.HTTP_200_OK):
    return Response({"ok": True, "data": data}, status=http_status)


def error_response(code: str, message: str, details=None, http_status=status.HTTP_400_BAD_REQUEST):
    payload = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
    return Response(payload, status=http_status)


class ApiRootView(APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        return success_response(
            {
                "name": "Finchat API",
                "version": "0.1.0",
                "status": "ok",
                "endpoints": {
                    "company_search": "/api/companies/search/",
                    "company_detail": "/api/companies/<ticker>/",
                    "company_ingest": "/api/companies/ingest/",
                    "compute_analytics": "/api/analytics/compute/",
                    "company_metrics": "/api/companies/<ticker>/metrics/",
                    "compare_companies": "/api/companies/compare/",
                    "chat_query": "/api/chat/query/",
                    "chat_sessions": "/api/chat/sessions/",
                    "job_status": "/api/jobs/<job_id>/",
                },
            }
        )


class CompanySearchView(APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        serializer = CompanySearchQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid search query.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        query = serializer.validated_data["q"]
        limit = serializer.validated_data["limit"]

        companies = search_companies(query=query, limit=limit)
        data = CompanySerializer(companies, many=True).data

        return success_response(
            {
                "query": query,
                "count": len(data),
                "results": data,
            }
        )

class TickerUniverseSearchView(APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        serializer = TickerUniverseSearchQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid ticker universe search query.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        query = serializer.validated_data["q"]
        limit = serializer.validated_data["limit"]

        try:
            results = FinnhubTickerSearchService().search_tickers(query=query, limit=limit)
        except FinnhubMissingAPIKeyError as exc:
            return error_response(
                code="missing_api_key",
                message=str(exc),
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except FinnhubRateLimitError as exc:
            return error_response(
                code="rate_limit",
                message=str(exc),
                http_status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except FinnhubAPIError as exc:
            return error_response(
                code="finnhub_api_error",
                message=str(exc),
                http_status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            return error_response(
                code="ticker_search_error",
                message="Ticker universe search failed.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        data = TickerUniverseSearchResultSerializer(results, many=True).data
        return success_response(
            {
                "query": query,
                "count": len(data),
                "results": data,
            }
        )
class CompanyDetailView(APIView):
    permission_classes = []

    def get(self, request, ticker: str, *args, **kwargs):
        company = get_company_by_ticker(ticker)
        if company is None:
            return error_response(
                code="not_found",
                message=f"Company with ticker '{ticker.upper()}' was not found.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        latest_profile = get_company_latest_profile_snapshot(company)
        latest_quote = get_company_latest_quote_snapshot(company)
        latest_basic = get_company_latest_basic_metric_snapshot(company)

        payload = {
            "company": CompanySerializer(company).data,
            "latest_profile": CompanyProfileSnapshotSerializer(latest_profile).data if latest_profile else None,
            "latest_quote": CompanyQuoteSnapshotSerializer(latest_quote).data if latest_quote else None,
            "latest_basic_metrics": (
                CompanyBasicMetricSnapshotSerializer(latest_basic).data if latest_basic else None
            ),
            "counts": get_company_detail_counts(company),
            "latest_financial_period": get_company_latest_financial_period_payload(company),
        }

        response_serializer = CompanyDetailResponseSerializer(payload)
        return success_response(response_serializer.data)


class IngestCompanyView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = CompanyIngestRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid ingestion request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        ticker = serializer.validated_data["ticker"]
        ingest_statements = serializer.validated_data["ingest_statements"]
        async_mode = serializer.validated_data["async_mode"]

        if async_mode:
            try:
                dispatch = JobDispatchService().dispatch_ingestion_job(
                    ticker=ticker,
                    async_mode=True,
                    ingest_statements=ingest_statements,
                )
                job = get_job_run_by_id(dispatch.job_id)
                return success_response(
                    {
                        "mode": "async",
                        "job_id": dispatch.job_id,
                        "status": dispatch.status,
                        "celery_task_id": dispatch.celery_task_id,
                        "job": JobRunSerializer(job).data if job else None,
                    },
                    http_status=status.HTTP_202_ACCEPTED,
                )
            except Exception as exc:
                return error_response(
                    code="job_dispatch_error",
                    message="Failed to dispatch ingestion job.",
                    details={"error": str(exc)},
                    http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        try:
            result = CompanyIngestionService().ingest_company(
                ticker=ticker,
                ingest_statements=ingest_statements,
            )
        except FinnhubMissingAPIKeyError as exc:
            return error_response(
                code="missing_api_key",
                message=str(exc),
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except FinnhubNotFoundError as exc:
            return error_response(
                code="invalid_ticker",
                message=str(exc),
                http_status=status.HTTP_404_NOT_FOUND,
            )
        except FinnhubRateLimitError as exc:
            return error_response(
                code="rate_limit",
                message=str(exc),
                http_status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except FinnhubAPIError as exc:
            return error_response(
                code="finnhub_api_error",
                message=str(exc),
                http_status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            return error_response(
                code="ingestion_error",
                message="Company ingestion failed.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(
            {
                "mode": "sync",
                "ticker": result.ticker,
                "company_id": result.company_id,
                "company_created": result.company_created,
                "profile_snapshot_created": result.profile_snapshot_created,
                "quote_snapshot_created": result.quote_snapshot_created,
                "basic_metric_snapshot_created": result.basic_metric_snapshot_created,
                "statements_result": result.statements_result,
                "warnings": result.warnings,
            }
        )


class ComputeAnalyticsView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = ComputeAnalyticsRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid compute request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        ticker = serializer.validated_data["ticker"]
        calc_version = serializer.validated_data["calc_version"]
        async_mode = serializer.validated_data["async_mode"]

        company = get_company_by_ticker(ticker)
        if company is None:
            return error_response(
                code="not_found",
                message=f"Company with ticker '{ticker}' was not found.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if async_mode:
            try:
                dispatch = JobDispatchService().dispatch_analytics_refresh_job(
                    ticker=ticker,
                    async_mode=True,
                    calculation_version=calc_version,
                )
                job = get_job_run_by_id(dispatch.job_id)
                return success_response(
                    {
                        "mode": "async",
                        "job_id": dispatch.job_id,
                        "status": dispatch.status,
                        "celery_task_id": dispatch.celery_task_id,
                        "job": JobRunSerializer(job).data if job else None,
                    },
                    http_status=status.HTTP_202_ACCEPTED,
                )
            except Exception as exc:
                return error_response(
                    code="job_dispatch_error",
                    message="Failed to dispatch analytics job.",
                    details={"error": str(exc)},
                    http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        try:
            result = MetricComputationService(calculation_version=calc_version).compute_metrics_for_company(company)
        except Exception as exc:
            return error_response(
                code="analytics_error",
                message="Analytics computation failed.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(
            {
                "mode": "sync",
                "ticker": result.ticker,
                "company_id": result.company_id,
                "periods_seen": result.periods_seen,
                "metrics_written": result.metrics_written,
                "metrics_updated": result.metrics_updated,
                "metrics_skipped": result.metrics_skipped,
                "calc_version": calc_version,
            }
        )


class CompanyMetricsView(APIView):
    permission_classes = []

    def get(self, request, ticker: str, *args, **kwargs):
        company = get_company_by_ticker(ticker)
        if company is None:
            return error_response(
                code="not_found",
                message=f"Company with ticker '{ticker.upper()}' was not found.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CompanyMetricsQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid metrics query.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        metric_codes = serializer.validated_data["metric_codes"]
        latest_only = serializer.validated_data["latest_only"]
        period_type = serializer.validated_data.get("period_type")
        limit = serializer.validated_data["limit"]

        metric_snapshots = get_company_metric_snapshots(
            company=company,
            metric_codes=metric_codes,
            latest_only=latest_only,
            period_type=period_type,
            limit=limit,
        )

        data = ComputedMetricSnapshotSerializer(metric_snapshots, many=True).data
        return success_response(
            {
                "company": CompanySerializer(company).data,
                "count": len(data),
                "latest_only": latest_only,
                "period_type": period_type,
                "metric_codes": metric_codes,
                "results": data,
            }
        )


class CompareCompaniesView(APIView):
    permission_classes = []

    DEFAULT_COMPARE_METRICS = [
        "profitability_net_margin",
        "growth_revenue_yoy",
        "liquidity_current_ratio",
        "leverage_debt_to_equity",
        "cashflow_fcf_margin",
        "valuation_price_to_earnings",
        "summary_quality_score",
    ]

    def post(self, request, *args, **kwargs):
        serializer = CompareCompaniesRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid comparison request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        tickers = serializer.validated_data["tickers"]
        metric_codes = serializer.validated_data["metric_codes"] or self.DEFAULT_COMPARE_METRICS
        period_type = serializer.validated_data.get("period_type")

        comparison_rows = []
        missing = []

        for ticker in tickers:
            company = get_company_by_ticker(ticker)
            if company is None:
                missing.append(ticker)
                continue

            row_metrics = []
            for metric_code in metric_codes:
                snapshot = get_latest_metric_snapshot(
                    company=company,
                    metric_code=metric_code,
                    period_type=period_type,
                )
                if snapshot is None:
                    row_metrics.append(
                        {
                            "metric_code": metric_code,
                            "metric_name": metric_code,
                            "metric_value": None,
                            "unit": "",
                            "as_of_date": None,
                            "period_type": None,
                            "calculation_version": None,
                        }
                    )
                else:
                    row_metrics.append(
                        {
                            "metric_code": snapshot.metric_code,
                            "metric_name": snapshot.metric_name,
                            "metric_value": snapshot.metric_value,
                            "unit": snapshot.unit,
                            "as_of_date": snapshot.as_of_date,
                            "period_type": snapshot.period_type,
                            "calculation_version": snapshot.calculation_version,
                        }
                    )

            comparison_rows.append(
                {
                    "company": CompanySerializer(company).data,
                    "metrics": row_metrics,
                }
            )

        response_serializer = CompanyComparisonRowSerializer(comparison_rows, many=True)

        return success_response(
            {
                "requested_tickers": tickers,
                "missing_tickers": missing,
                "metric_codes": metric_codes,
                "period_type": period_type,
                "results": response_serializer.data,
            }
        )


class JobStatusView(APIView):
    permission_classes = []

    def get(self, request, job_id: str, *args, **kwargs):
        job = get_job_run_by_id(job_id)
        if job is None:
            return error_response(
                code="not_found",
                message=f"Job '{job_id}' was not found.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        return success_response(JobRunSerializer(job).data)


class ChatQueryView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = ChatQueryRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid chat request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        message = serializer.validated_data["message"]
        chat_history = serializer.validated_data.get("chat_history", [])

        try:
            result = FinancialAssistantGraphService().run(
                user_query=message,
                chat_history=chat_history,
            )
        except Exception as exc:
            return error_response(
                code="chat_error",
                message="Chat workflow failed.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(
            {
                "answer": result.get("final_answer", ""),
                "resolved_companies": result.get("resolved_companies", []),
                "planner_output": result.get("planner_output", {}),
                "tool_results": result.get("tool_results", {}),
                "errors": result.get("errors", []),
                "final_payload": result.get("final_payload", {}),
            }
        )


class ChatSessionCollectionView(APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        sessions = ChatSessionService().list_sessions(limit=20)
        return success_response(
            {
                "count": len(sessions),
                "results": ChatSessionSerializer(sessions, many=True).data,
            }
        )

    def post(self, request, *args, **kwargs):
        serializer = ChatSessionCreateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid chat session request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        result = ChatSessionService().create_session(
            title=serializer.validated_data["title"],
            context_json=serializer.validated_data["context_json"],
            user_identifier=serializer.validated_data["user_identifier"],
        )

        return success_response(
            {
                "session": ChatSessionSerializer(result.session).data,
            },
            http_status=status.HTTP_201_CREATED,
        )


class ChatSessionDetailView(APIView):
    permission_classes = []

    def get(self, request, session_id: str, *args, **kwargs):
        session = ChatSessionService().get_session(session_id)
        if session is None:
            return error_response(
                code="not_found",
                message=f"Chat session '{session_id}' was not found.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        return success_response(
            {
                "session": ChatSessionSerializer(session).data,
            }
        )


class ChatSessionMessagesView(APIView):
    permission_classes = []

    def get(self, request, session_id: str, *args, **kwargs):
        session = ChatSessionService().get_session(session_id)
        if session is None:
            return error_response(
                code="not_found",
                message=f"Chat session '{session_id}' was not found.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        messages = ChatSessionService().list_messages(session_id)
        return success_response(
            {
                "session": ChatSessionSerializer(session).data,
                "count": len(messages),
                "results": ChatMessageSerializer(messages, many=True).data,
            }
        )

    def post(self, request, session_id: str, *args, **kwargs):
        session = ChatSessionService().get_session(session_id)
        if session is None:
            return error_response(
                code="not_found",
                message=f"Chat session '{session_id}' was not found.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ChatMessageCreateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid chat message request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = ChatSessionService().send_message(
                session_id=session_id,
                content=serializer.validated_data["content"],
            )
        except Exception as exc:
            return error_response(
                code="chat_error",
                message="Failed to send chat message.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(
            {
                "session": ChatSessionSerializer(result.session).data,
                "user_message": ChatMessageSerializer(result.user_message).data,
                "assistant_message": ChatMessageSerializer(result.assistant_message).data,
                "reasoning_summary": result.reasoning_summary,
            }
        )
class SystemMetricsView(APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        payload = ObservabilityService().snapshot(
            tool_names=[
                "company_lookup_tool",
                "get_company_overview_tool",
                "get_computed_metrics_tool",
                "get_valuation_summary_tool",
                "get_growth_summary_tool",
                "get_risk_flags_tool",
                "compare_companies_tool",
                "get_analysis_summary_tool",
                "get_peer_ranking_tool",
                "get_scenario_analysis_tool",
            ],
            intents=[
                "general_analysis",
                "valuation",
                "growth",
                "risk",
                "comparison",
                "portfolio_analysis",
                "strength_weakness",
                "backtesting",
            ],
        )
        return success_response(payload)


api_root = ApiRootView.as_view()