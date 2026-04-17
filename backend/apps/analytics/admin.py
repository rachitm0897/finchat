from __future__ import annotations

from django.contrib import admin

from apps.analytics.models import ComputedMetricSnapshot, ValuationSnapshot


@admin.register(ComputedMetricSnapshot)
class ComputedMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "metric_code",
        "metric_name",
        "as_of_date",
        "period",
        "metric_value",
        "calculation_version",
    )
    search_fields = ("company__ticker", "metric_code", "metric_name")
    list_filter = ("period_type", "unit", "calculation_version")


@admin.register(ValuationSnapshot)
class ValuationSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "valuation_model",
        "scenario_name",
        "as_of_date",
        "implied_share_price",
        "calculation_version",
    )
    search_fields = ("company__ticker", "valuation_model", "scenario_name")
    list_filter = ("valuation_model", "scenario_name", "calculation_version")