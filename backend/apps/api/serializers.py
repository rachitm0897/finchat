from __future__ import annotations

from rest_framework import serializers

from apps.ai_assistant.models import ChatMessage, ChatSession
from apps.analytics.models import ComputedMetricSnapshot
from apps.jobs.models import JobRun
from apps.market_data.models import (
    Company,
    CompanyBasicMetricSnapshot,
    CompanyProfileSnapshot,
    CompanyQuoteSnapshot,
)


class CompanySearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, default="")
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)

    def validate_q(self, value: str) -> str:
        return value.strip()
class TickerUniverseSearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=True, allow_blank=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=15)

    def validate_q(self, value: str) -> str:
        value = value.strip()
        if len(value) < 1:
            raise serializers.ValidationError("q must not be empty.")
        return value


class TickerUniverseSearchResultSerializer(serializers.Serializer):
    ticker = serializers.CharField()
    symbol = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    exchange = serializers.CharField()
    type = serializers.CharField()
    currency = serializers.CharField()
    country = serializers.CharField()
    source = serializers.CharField()
    is_ingested = serializers.BooleanField()

class CompanyIngestRequestSerializer(serializers.Serializer):
    ticker = serializers.CharField(max_length=32)
    ingest_statements = serializers.BooleanField(required=False, default=True)
    async_mode = serializers.BooleanField(required=False, default=False)

    def validate_ticker(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Ticker must not be empty.")
        return value


class ComputeAnalyticsRequestSerializer(serializers.Serializer):
    ticker = serializers.CharField(max_length=32)
    calc_version = serializers.CharField(required=False, default="v1", max_length=64)
    async_mode = serializers.BooleanField(required=False, default=False)

    def validate_ticker(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Ticker must not be empty.")
        return value

    def validate_calc_version(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("calc_version must not be empty.")
        return value


class CompanyMetricsQuerySerializer(serializers.Serializer):
    metric_codes = serializers.CharField(required=False, allow_blank=True, default="")
    latest_only = serializers.BooleanField(required=False, default=True)
    period_type = serializers.ChoiceField(
        required=False,
        allow_null=True,
        choices=[("annual", "annual"), ("quarterly", "quarterly")],
    )
    limit = serializers.IntegerField(required=False, min_value=1, max_value=500, default=100)

    def validate_metric_codes(self, value: str) -> list[str]:
        value = value.strip()
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]


class CompareCompaniesRequestSerializer(serializers.Serializer):
    tickers = serializers.ListField(
        child=serializers.CharField(max_length=32),
        min_length=2,
        max_length=20,
    )
    metric_codes = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        allow_empty=True,
        default=list,
    )
    period_type = serializers.ChoiceField(
        required=False,
        allow_null=True,
        choices=[("annual", "annual"), ("quarterly", "quarterly")],
        default=None,
    )

    def validate_tickers(self, value: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for item in value:
            ticker = item.strip().upper()
            if not ticker:
                continue
            if ticker not in seen:
                normalized.append(ticker)
                seen.add(ticker)
        if len(normalized) < 2:
            raise serializers.ValidationError("Provide at least two unique tickers.")
        return normalized

    def validate_metric_codes(self, value: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for item in value:
            code = item.strip()
            if not code:
                continue
            if code not in seen:
                normalized.append(code)
                seen.add(code)
        return normalized


class ChatQueryRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    chat_history = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
    )

    def validate_message(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("message must not be empty.")
        return value


class ChatSessionCreateRequestSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, default="")
    context_json = serializers.DictField(required=False, default=dict)
    user_identifier = serializers.CharField(required=False, allow_blank=True, default="")


class ChatMessageCreateRequestSerializer(serializers.Serializer):
    content = serializers.CharField()

    def validate_content(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("content must not be empty.")
        return value


class JobStatusQuerySerializer(serializers.Serializer):
    pass


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "ticker",
            "finnhub_symbol",
            "name",
            "country",
            "currency_code",
            "exchange",
            "primary_exchange",
            "ipo_date",
            "market_identifier_code",
            "logo_url",
            "web_url",
            "industry",
            "is_active",
            "created_at",
            "updated_at",
        ]


class CompanyProfileSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfileSnapshot
        fields = [
            "id",
            "source_name",
            "endpoint_name",
            "fetched_at",
            "is_latest",
            "symbol",
            "status_code",
            "country",
            "currency_code",
            "exchange",
            "ipo_date",
            "market_capitalization",
            "name",
            "phone",
            "share_outstanding",
            "ticker",
            "web_url",
            "logo_url",
            "industry",
            "created_at",
        ]


class CompanyQuoteSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyQuoteSnapshot
        fields = [
            "id",
            "source_name",
            "endpoint_name",
            "fetched_at",
            "is_latest",
            "symbol",
            "status_code",
            "current_price",
            "change",
            "percent_change",
            "high_price",
            "low_price",
            "open_price",
            "previous_close_price",
            "quote_timestamp",
            "created_at",
        ]


class CompanyBasicMetricSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyBasicMetricSnapshot
        fields = [
            "id",
            "source_name",
            "endpoint_name",
            "fetched_at",
            "is_latest",
            "symbol",
            "status_code",
            "metric_values",
            "created_at",
        ]


class ComputedMetricSnapshotSerializer(serializers.ModelSerializer):
    period_end_date = serializers.DateField(source="period.period_end_date", read_only=True)
    fiscal_year = serializers.IntegerField(source="period.fiscal_year", read_only=True)
    fiscal_quarter = serializers.IntegerField(source="period.fiscal_quarter", read_only=True)

    class Meta:
        model = ComputedMetricSnapshot
        fields = [
            "id",
            "company",
            "period",
            "period_end_date",
            "fiscal_year",
            "fiscal_quarter",
            "as_of_date",
            "period_type",
            "metric_code",
            "metric_name",
            "metric_value",
            "unit",
            "calculation_version",
            "source_trace",
            "notes",
            "created_at",
        ]


class CompanyDetailResponseSerializer(serializers.Serializer):
    company = CompanySerializer()
    latest_profile = CompanyProfileSnapshotSerializer(allow_null=True)
    latest_quote = CompanyQuoteSnapshotSerializer(allow_null=True)
    latest_basic_metrics = CompanyBasicMetricSnapshotSerializer(allow_null=True)
    counts = serializers.DictField()
    latest_financial_period = serializers.DictField(allow_null=True)


class CompanyComparisonMetricSerializer(serializers.Serializer):
    metric_code = serializers.CharField()
    metric_name = serializers.CharField()
    metric_value = serializers.DecimalField(max_digits=24, decimal_places=8, allow_null=True)
    unit = serializers.CharField()
    as_of_date = serializers.DateField(allow_null=True)
    period_type = serializers.CharField(allow_null=True)
    calculation_version = serializers.CharField(allow_null=True)


class CompanyComparisonRowSerializer(serializers.Serializer):
    company = CompanySerializer()
    metrics = CompanyComparisonMetricSerializer(many=True)


class JobRunSerializer(serializers.ModelSerializer):
    company = CompanySerializer(allow_null=True)

    class Meta:
        model = JobRun
        fields = [
            "id",
            "company",
            "job_type",
            "status",
            "celery_task_id",
            "idempotency_key",
            "request_payload_json",
            "result_payload_json",
            "error_payload_json",
            "requested_by",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "session",
            "role",
            "content",
            "message_index",
            "model_name",
            "token_usage_input",
            "token_usage_output",
            "grounding_json",
            "tool_name",
            "tool_arguments_json",
            "source_trace",
            "error_message",
            "created_at",
        ]


class ChatSessionSerializer(serializers.ModelSerializer):
    companies = CompanySerializer(many=True)

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "title",
            "status",
            "user_identifier",
            "context_json",
            "created_at",
            "updated_at",
            "last_message_at",
            "companies",
        ]