from __future__ import annotations

from django.contrib import admin

from apps.backtesting.models import BacktestPriceBar, BacktestResult, BacktestRun, StrategyConfig


@admin.register(StrategyConfig)
class StrategyConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "strategy_type", "is_active", "created_at")
    list_filter = ("strategy_type", "is_active")
    search_fields = ("name", "strategy_type")


@admin.register(BacktestRun)
class BacktestRunAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "strategy_type", "status", "start_date", "end_date", "created_at")
    list_filter = ("strategy_type", "status", "resolution")
    search_fields = ("company__ticker", "name")


@admin.register(BacktestResult)
class BacktestResultAdmin(admin.ModelAdmin):
    list_display = ("id", "backtest_run", "created_at")
    search_fields = ("backtest_run__company__ticker",)


@admin.register(BacktestPriceBar)
class BacktestPriceBarAdmin(admin.ModelAdmin):
    list_display = ("company", "resolution", "start_at", "close_price", "volume", "fetched_at")
    list_filter = ("resolution", "source_name")
    search_fields = ("company__ticker", "symbol")