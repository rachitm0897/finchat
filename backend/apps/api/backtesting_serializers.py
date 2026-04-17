from __future__ import annotations

from rest_framework import serializers

from apps.backtesting.models import BacktestResult, BacktestRun, StrategyConfig
from apps.market_data.models import Company


class BacktestRunRequestSerializer(serializers.Serializer):
    ticker = serializers.CharField()
    strategy_type = serializers.ChoiceField(
        choices=[
            ("sma_crossover", "sma_crossover"),
            ("support_resistance_rsi_volume", "support_resistance_rsi_volume"),
            ("momentum", "momentum"),
            ("mean_reversion", "mean_reversion"),
            ("portfolio_momentum", "portfolio_momentum"),
        ],
        default="sma_crossover",
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    initial_capital = serializers.DecimalField(max_digits=24, decimal_places=4, default="10000")
    position_size = serializers.DecimalField(max_digits=12, decimal_places=6, default="1")
    commission_bps = serializers.DecimalField(max_digits=12, decimal_places=6, default="10")
    resolution = serializers.ChoiceField(choices=[("D", "D")], default="D")
    async_mode = serializers.BooleanField(default=True)
    use_stored_data = serializers.BooleanField(default=True)
    benchmark_symbol = serializers.CharField(required=False, allow_blank=True, default="")
    config_json = serializers.DictField(required=False, default=dict)

    def validate_ticker(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("ticker must not be empty.")
        return value

    def validate(self, attrs):
        if attrs["start_date"] >= attrs["end_date"]:
            raise serializers.ValidationError("start_date must be before end_date.")

        strategy_type = attrs["strategy_type"]
        config_json = attrs.get("config_json") or {}

        if strategy_type == "sma_crossover":
            short_window = int(config_json.get("short_window", 20))
            long_window = int(config_json.get("long_window", 50))

            if short_window <= 0 or long_window <= 0:
                raise serializers.ValidationError("short_window and long_window must be positive integers.")
            if short_window >= long_window:
                raise serializers.ValidationError("short_window must be smaller than long_window.")

            attrs["config_json"] = {
                "short_window": short_window,
                "long_window": long_window,
            }
            return attrs

        if strategy_type == "support_resistance_rsi_volume":
            support_window = int(config_json.get("support_window", 20))
            resistance_window = int(config_json.get("resistance_window", 20))
            rsi_window = int(config_json.get("rsi_window", 14))
            rsi_buy = float(config_json.get("rsi_buy", 35))
            rsi_sell = float(config_json.get("rsi_sell", 65))
            volume_window = int(config_json.get("volume_window", 20))
            volume_multiplier = float(config_json.get("volume_multiplier", 1.5))
            buy_tolerance_pct = float(config_json.get("buy_tolerance_pct", 2.0))
            sell_tolerance_pct = float(config_json.get("sell_tolerance_pct", 2.0))

            if min(support_window, resistance_window, rsi_window, volume_window) <= 0:
                raise serializers.ValidationError("All lookback windows must be positive.")
            if not (0 < rsi_buy < 100 and 0 < rsi_sell < 100):
                raise serializers.ValidationError("RSI thresholds must be between 0 and 100.")
            if rsi_buy >= rsi_sell:
                raise serializers.ValidationError("rsi_buy must be smaller than rsi_sell.")
            if volume_multiplier <= 0:
                raise serializers.ValidationError("volume_multiplier must be positive.")
            if buy_tolerance_pct < 0 or sell_tolerance_pct < 0:
                raise serializers.ValidationError("Tolerance percentages must be non-negative.")

            attrs["config_json"] = {
                "support_window": support_window,
                "resistance_window": resistance_window,
                "rsi_window": rsi_window,
                "rsi_buy": rsi_buy,
                "rsi_sell": rsi_sell,
                "volume_window": volume_window,
                "volume_multiplier": volume_multiplier,
                "buy_tolerance_pct": buy_tolerance_pct,
                "sell_tolerance_pct": sell_tolerance_pct,
            }
            return attrs
        if strategy_type == "momentum":
            lookback_window = int(config_json.get("lookback_window", 90))
            top_n = int(config_json.get("top_n", 1))
            if lookback_window <= 1:
                raise serializers.ValidationError("lookback_window must be greater than 1.")
            if top_n <= 0:
                raise serializers.ValidationError("top_n must be positive.")
            attrs["config_json"] = {
                "lookback_window": lookback_window,
                "top_n": top_n,
            }
            return attrs

        if strategy_type == "mean_reversion":
            lookback_window = int(config_json.get("lookback_window", 20))
            z_entry = float(config_json.get("z_entry", 1.5))
            z_exit = float(config_json.get("z_exit", 0.25))
            if lookback_window <= 1:
                raise serializers.ValidationError("lookback_window must be greater than 1.")
            if z_entry <= 0 or z_exit < 0:
                raise serializers.ValidationError("z_entry must be positive and z_exit must be non-negative.")
            attrs["config_json"] = {
                "lookback_window": lookback_window,
                "z_entry": z_entry,
                "z_exit": z_exit,
            }
            return attrs

        if strategy_type == "portfolio_momentum":
            tickers = config_json.get("tickers") or []
            lookback_window = int(config_json.get("lookback_window", 90))
            rebalance_days = int(config_json.get("rebalance_days", 21))
            top_n = int(config_json.get("top_n", 3))
            if not tickers or not isinstance(tickers, list):
                raise serializers.ValidationError("portfolio_momentum requires config_json.tickers.")
            attrs["config_json"] = {
                "tickers": [str(t).strip().upper() for t in tickers if str(t).strip()],
                "lookback_window": lookback_window,
                "rebalance_days": rebalance_days,
                "top_n": top_n,
            }
            return attrs

        raise serializers.ValidationError("Unsupported strategy_type.")


class BacktestRunQuerySerializer(serializers.Serializer):
    ticker = serializers.CharField(required=False, allow_blank=True, default="")
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)


class CompanyLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "ticker", "name"]


class StrategyConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategyConfig
        fields = ["id", "name", "strategy_type", "description", "config_json", "is_active", "created_at", "updated_at"]


class BacktestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacktestResult
        fields = [
            "id",
            "metrics_json",
            "equity_curve_json",
            "drawdown_curve_json",
            "signal_curve_json",
            "trades_json",
            "monthly_return_table_json",
            "created_at",
            "updated_at",
        ]


class BacktestRunSerializer(serializers.ModelSerializer):
    company = CompanyLiteSerializer()
    strategy_config = StrategyConfigSerializer(allow_null=True)
    result = BacktestResultSerializer(allow_null=True)

    class Meta:
        model = BacktestRun
        fields = [
            "id",
            "company",
            "strategy_config",
            "job_run",
            "name",
            "strategy_type",
            "resolution",
            "benchmark_symbol",
            "start_date",
            "end_date",
            "initial_capital",
            "position_size",
            "commission_bps",
            "status",
            "request_payload_json",
            "summary_json",
            "error_payload_json",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
            "result",
        ]