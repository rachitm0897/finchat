from __future__ import annotations

from rest_framework import serializers


class PeerRankingRequestSerializer(serializers.Serializer):
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


class ScenarioAnalysisRequestSerializer(serializers.Serializer):
    ticker = serializers.CharField(max_length=32)
    years = serializers.IntegerField(required=False, min_value=1, max_value=10, default=3)

    def validate_ticker(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Ticker must not be empty.")
        return value


class ReportExportQuerySerializer(serializers.Serializer):
    format = serializers.ChoiceField(choices=[("json", "json"), ("markdown", "markdown")], default="json")