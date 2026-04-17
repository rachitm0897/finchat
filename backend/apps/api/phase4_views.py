from __future__ import annotations

from rest_framework import status
from rest_framework.views import APIView

from apps.analytics.trend_services import TrendAnalyticsService
from apps.analytics.valuation_services import DCFValuationService
from apps.ai_assistant.portfolio_actions import PortfolioActionService
from apps.api.phase4_serializers import (
    ComparisonVisualsRequestSerializer,
    DCFRequestSerializer,
    PortfolioActionRequestSerializer,
    TrendQuerySerializer,
)
from apps.api.views import error_response, success_response


class CompanyTrendView(APIView):
    permission_classes = []

    def get(self, request, ticker: str, *args, **kwargs):
        serializer = TrendQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid trend query.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = TrendAnalyticsService().build_company_trends(
                ticker=ticker,
                period_type=serializer.validated_data["period_type"],
                limit=serializer.validated_data["limit"],
            )
        except Exception as exc:
            return error_response(
                code="trend_error",
                message="Failed to build company trends.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(payload)


class ComparisonVisualsView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = ComparisonVisualsRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid comparison visuals request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = TrendAnalyticsService().build_comparison_visuals(
                tickers=serializer.validated_data["tickers"],
                period_type=serializer.validated_data["period_type"],
            )
        except Exception as exc:
            return error_response(
                code="comparison_visuals_error",
                message="Failed to build comparison visuals.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(payload)


class DCFValuationView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = DCFRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid DCF request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = DCFValuationService().build_dcf(**serializer.validated_data)
        except Exception as exc:
            return error_response(
                code="dcf_error",
                message="Failed to build DCF valuation.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(payload)


class PortfolioActionsView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = PortfolioActionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid portfolio action request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = PortfolioActionService().execute_action_query(
                query=serializer.validated_data["query"],
                limit=serializer.validated_data["limit"],
            )
        except Exception as exc:
            return error_response(
                code="portfolio_action_error",
                message="Failed to execute portfolio action query.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(payload)