from __future__ import annotations

from django.http import HttpResponse
from rest_framework import status
from rest_framework.views import APIView

from apps.analytics.product_services import SmartAnalysisService
from apps.api.phase3_serializers import (
    PeerRankingRequestSerializer,
    ReportExportQuerySerializer,
    ScenarioAnalysisRequestSerializer,
)
from apps.report.export_services import CompanyReportExportService
from apps.api.views import error_response, success_response


class CompanyAnalysisSummaryView(APIView):
    permission_classes = []

    def get(self, request, ticker: str, *args, **kwargs):
        try:
            payload = SmartAnalysisService().build_company_analysis_summary(ticker)
        except Exception as exc:
            return error_response(
                code="analysis_summary_error",
                message="Failed to build company analysis summary.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(payload)


class PeerRankingView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = PeerRankingRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid peer ranking request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = SmartAnalysisService().build_peer_ranking(
                tickers=serializer.validated_data["tickers"],
                metric_codes=serializer.validated_data["metric_codes"],
            )
        except Exception as exc:
            return error_response(
                code="peer_ranking_error",
                message="Failed to build peer ranking.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(payload)


class ScenarioAnalysisView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = ScenarioAnalysisRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid scenario analysis request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = SmartAnalysisService().build_scenario_analysis(
                ticker=serializer.validated_data["ticker"],
                years=serializer.validated_data["years"],
            )
        except Exception as exc:
            return error_response(
                code="scenario_analysis_error",
                message="Failed to build scenario analysis.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(payload)


class ReportExportView(APIView):
    permission_classes = []

    def get(self, request, ticker: str, *args, **kwargs):
        serializer = ReportExportQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid report export request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        export_format = serializer.validated_data["format"]
        service = CompanyReportExportService()

        try:
            if export_format == "markdown":
                body = service.export_markdown(ticker)
                response = HttpResponse(body, content_type="text/markdown; charset=utf-8")
                response["Content-Disposition"] = f'attachment; filename="{ticker.upper()}_report.md"'
                return response

            body = service.export_json(ticker)
            response = HttpResponse(body, content_type="application/json; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{ticker.upper()}_report.json"'
            return response

        except Exception as exc:
            return error_response(
                code="report_export_error",
                message="Failed to export report.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )