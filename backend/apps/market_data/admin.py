from __future__ import annotations

from django.contrib import admin

from apps.market_data.models import (
    Company,
    CompanyBasicMetricSnapshot,
    CompanyProfileSnapshot,
    CompanyQuoteSnapshot,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "ticker",
        "name",
        "finnhub_symbol",
        "currency_code",
        "primary_exchange",
        "is_active",
        "updated_at",
    )
    search_fields = ("ticker", "name", "finnhub_symbol")
    list_filter = ("is_active", "currency_code", "country", "primary_exchange")


@admin.register(CompanyProfileSnapshot)
class CompanyProfileSnapshotAdmin(admin.ModelAdmin):
    list_display = ("company", "fetched_at", "source_name", "endpoint_name", "is_latest")
    search_fields = ("company__ticker", "symbol", "name")
    list_filter = ("source_name", "endpoint_name", "is_latest")


@admin.register(CompanyQuoteSnapshot)
class CompanyQuoteSnapshotAdmin(admin.ModelAdmin):
    list_display = ("company", "fetched_at", "current_price", "percent_change", "is_latest")
    search_fields = ("company__ticker", "symbol")
    list_filter = ("source_name", "endpoint_name", "is_latest")


@admin.register(CompanyBasicMetricSnapshot)
class CompanyBasicMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ("company", "fetched_at", "source_name", "endpoint_name", "is_latest")
    search_fields = ("company__ticker", "symbol")
    list_filter = ("source_name", "endpoint_name", "is_latest")