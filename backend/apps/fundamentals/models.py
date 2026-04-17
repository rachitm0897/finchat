from __future__ import annotations

import uuid

from django.db import models

from apps.market_data.models import Company, CompanyBasicMetricSnapshot, CompanyProfileSnapshot


class CompanyFinancialPeriod(models.Model):
    PERIOD_TYPE_ANNUAL = "annual"
    PERIOD_TYPE_QUARTERLY = "quarterly"

    PERIOD_TYPE_CHOICES = [
        (PERIOD_TYPE_ANNUAL, "Annual"),
        (PERIOD_TYPE_QUARTERLY, "Quarterly"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="financial_periods",
    )

    period_type = models.CharField(max_length=16, choices=PERIOD_TYPE_CHOICES)
    fiscal_year = models.PositiveIntegerField()
    fiscal_quarter = models.PositiveSmallIntegerField(null=True, blank=True)
    period_end_date = models.DateField()
    currency_code = models.CharField(max_length=16)

    source_name = models.CharField(max_length=64, default="finnhub")
    source_period_key = models.CharField(max_length=128, blank=True)
    source_profile_snapshot = models.ForeignKey(
        CompanyProfileSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_periods",
    )
    source_basic_metric_snapshot = models.ForeignKey(
        CompanyBasicMetricSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_periods",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company", "-period_end_date"]
        indexes = [
            models.Index(fields=["company", "period_type", "-period_end_date"]),
            models.Index(fields=["company", "fiscal_year", "fiscal_quarter"]),
            models.Index(fields=["period_type", "period_end_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "period_type", "fiscal_year", "fiscal_quarter", "period_end_date"],
                name="uq_financial_period_company_period_unique",
            )
        ]

    def __str__(self) -> str:
        label = f"FY{self.fiscal_year}"
        if self.fiscal_quarter:
            label += f" Q{self.fiscal_quarter}"
        return f"{self.company.ticker} {label}"


class IncomeStatement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="income_statements",
    )
    period = models.OneToOneField(
        CompanyFinancialPeriod,
        on_delete=models.CASCADE,
        related_name="income_statement",
    )

    source_name = models.CharField(max_length=64, default="finnhub")
    source_payload_json = models.JSONField(default=dict, blank=True)

    revenue = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    cost_of_revenue = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    gross_profit = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    operating_expense = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    selling_general_and_administrative = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    research_and_development = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    depreciation_and_amortization = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    operating_income = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    interest_expense = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    pretax_income = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    income_tax_expense = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    net_income = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    diluted_eps = models.DecimalField(max_digits=24, decimal_places=6, null=True, blank=True)
    weighted_average_diluted_shares = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company", "-period__period_end_date"]
        indexes = [
            models.Index(fields=["company", "period"]),
        ]

    def __str__(self) -> str:
        return f"IncomeStatement({self.company.ticker}, {self.period.period_end_date})"


class BalanceSheet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="balance_sheets",
    )
    period = models.OneToOneField(
        CompanyFinancialPeriod,
        on_delete=models.CASCADE,
        related_name="balance_sheet",
    )

    source_name = models.CharField(max_length=64, default="finnhub")
    source_payload_json = models.JSONField(default=dict, blank=True)

    cash_and_cash_equivalents = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    short_term_investments = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    accounts_receivable = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    inventory = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    other_current_assets = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    total_current_assets = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)

    property_plant_and_equipment = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    goodwill = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    intangible_assets = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    total_non_current_assets = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    total_assets = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)

    accounts_payable = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    short_term_debt = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    other_current_liabilities = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    total_current_liabilities = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)

    long_term_debt = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    total_non_current_liabilities = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    total_liabilities = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)

    retained_earnings = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    total_shareholders_equity = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    total_liabilities_and_equity = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company", "-period__period_end_date"]
        indexes = [
            models.Index(fields=["company", "period"]),
        ]

    def __str__(self) -> str:
        return f"BalanceSheet({self.company.ticker}, {self.period.period_end_date})"


class CashFlowStatement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="cash_flow_statements",
    )
    period = models.OneToOneField(
        CompanyFinancialPeriod,
        on_delete=models.CASCADE,
        related_name="cash_flow_statement",
    )

    source_name = models.CharField(max_length=64, default="finnhub")
    source_payload_json = models.JSONField(default=dict, blank=True)

    net_income = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    depreciation_and_amortization = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    stock_based_compensation = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    changes_in_working_capital = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    cash_from_operating_activities = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)

    capital_expenditure = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    acquisitions = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    cash_from_investing_activities = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)

    debt_issued_or_repaid_net = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    dividends_paid = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    share_repurchases = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    cash_from_financing_activities = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)

    net_change_in_cash = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    free_cash_flow = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company", "-period__period_end_date"]
        indexes = [
            models.Index(fields=["company", "period"]),
        ]

    def __str__(self) -> str:
        return f"CashFlowStatement({self.company.ticker}, {self.period.period_end_date})"