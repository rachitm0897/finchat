from __future__ import annotations

from django.contrib import admin

from apps.fundamentals.models import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFinancialPeriod,
    IncomeStatement,
)


@admin.register(CompanyFinancialPeriod)
class CompanyFinancialPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "period_type",
        "fiscal_year",
        "fiscal_quarter",
        "period_end_date",
        "currency_code",
    )
    search_fields = ("company__ticker", "company__name")
    list_filter = ("period_type", "currency_code", "source_name")


@admin.register(IncomeStatement)
class IncomeStatementAdmin(admin.ModelAdmin):
    list_display = ("company", "period", "revenue", "gross_profit", "operating_income", "net_income")
    search_fields = ("company__ticker",)
    list_filter = ("source_name",)


@admin.register(BalanceSheet)
class BalanceSheetAdmin(admin.ModelAdmin):
    list_display = ("company", "period", "total_assets", "total_liabilities", "total_shareholders_equity")
    search_fields = ("company__ticker",)
    list_filter = ("source_name",)


@admin.register(CashFlowStatement)
class CashFlowStatementAdmin(admin.ModelAdmin):
    list_display = ("company", "period", "cash_from_operating_activities", "capital_expenditure", "free_cash_flow")
    search_fields = ("company__ticker",)
    list_filter = ("source_name",)