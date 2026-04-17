from __future__ import annotations

from rest_framework import serializers


class TrendQuerySerializer(serializers.Serializer):
    period_type = serializers.ChoiceField(
        choices=[("annual", "annual"), ("quarterly", "quarterly")],
        default="annual",
    )
    limit = serializers.IntegerField(required=False, min_value=3, max_value=20, default=8)


class ComparisonVisualsRequestSerializer(serializers.Serializer):
    tickers = serializers.ListField(
        child=serializers.CharField(max_length=32),
        min_length=2,
        max_length=20,
    )
    period_type = serializers.ChoiceField(
        choices=[("annual", "annual"), ("quarterly", "quarterly")],
        default="annual",
    )

    def validate_tickers(self, value):
        normalized = []
        seen = set()
        for item in value:
            ticker = item.strip().upper()
            if ticker and ticker not in seen:
                normalized.append(ticker)
                seen.add(ticker)
        if len(normalized) < 2:
            raise serializers.ValidationError("Provide at least two unique tickers.")
        return normalized


class DCFRequestSerializer(serializers.Serializer):
    ticker = serializers.CharField(max_length=32)
    years_stage_1 = serializers.IntegerField(required=False, min_value=1, max_value=10, default=5)
    years_stage_2 = serializers.IntegerField(required=False, min_value=1, max_value=10, default=5)
    growth_stage_1 = serializers.CharField(required=False, default="0.10")
    growth_stage_2 = serializers.CharField(required=False, default="0.05")
    terminal_growth = serializers.CharField(required=False, default="0.03")
    wacc = serializers.CharField(required=False, default="0.10")

    def validate_ticker(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Ticker must not be empty.")
        return value


class PortfolioActionRequestSerializer(serializers.Serializer):
    query = serializers.CharField()
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=10)

    def validate_query(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("query must not be empty.")
        return value