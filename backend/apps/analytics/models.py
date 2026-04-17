from __future__ import annotations

import uuid

from django.db import models

from apps.fundamentals.models import CompanyFinancialPeriod
from apps.market_data.models import Company


class ComputedMetricSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="computed_metric_snapshots",
    )
    period = models.ForeignKey(
        CompanyFinancialPeriod,
        on_delete=models.CASCADE,
        related_name="computed_metric_snapshots",
        null=True,
        blank=True,
    )

    as_of_date = models.DateField()
    period_type = models.CharField(max_length=16)
    metric_code = models.CharField(max_length=64)
    metric_name = models.CharField(max_length=128)
    metric_value = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    unit = models.CharField(max_length=32, default="number")
    calculation_version = models.CharField(max_length=64, default="v1")
    source_trace = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["company", "metric_code", "-as_of_date"]
        indexes = [
            models.Index(fields=["company", "metric_code", "-as_of_date"]),
            models.Index(fields=["company", "period"]),
            models.Index(fields=["metric_code", "period_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "period", "metric_code", "calculation_version"],
                name="uq_computed_metric_company_period_code_version",
            )
        ]

    def __str__(self) -> str:
        return f"{self.company.ticker} {self.metric_code} {self.as_of_date}"


class ValuationSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="valuation_snapshots",
    )
    period = models.ForeignKey(
        CompanyFinancialPeriod,
        on_delete=models.SET_NULL,
        related_name="valuation_snapshots",
        null=True,
        blank=True,
    )

    as_of_date = models.DateField()
    valuation_model = models.CharField(max_length=64)
    scenario_name = models.CharField(max_length=64, default="base")
    calculation_version = models.CharField(max_length=64, default="v1")

    enterprise_value = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    equity_value = models.DecimalField(max_digits=24, decimal_places=4, null=True, blank=True)
    implied_share_price = models.DecimalField(max_digits=24, decimal_places=6, null=True, blank=True)
    upside_downside_percent = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    assumptions_json = models.JSONField(default=dict, blank=True)
    output_json = models.JSONField(default=dict, blank=True)
    source_trace = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["company", "-as_of_date", "valuation_model", "scenario_name"]
        indexes = [
            models.Index(fields=["company", "-as_of_date"]),
            models.Index(fields=["valuation_model", "scenario_name"]),
            models.Index(fields=["company", "period"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "period", "valuation_model", "scenario_name", "calculation_version"],
                name="uq_valuation_company_period_model_scenario_version",
            )
        ]

    def __str__(self) -> str:
        return f"{self.company.ticker} {self.valuation_model} {self.scenario_name}"