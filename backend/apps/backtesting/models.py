from __future__ import annotations

import uuid

from django.db import models

from apps.jobs.models import JobRun
from apps.market_data.models import Company


class StrategyConfig(models.Model):
    STRATEGY_SMA_CROSSOVER = "sma_crossover"

    STRATEGY_TYPE_CHOICES = [
        (STRATEGY_SMA_CROSSOVER, "SMA Crossover"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    strategy_type = models.CharField(max_length=64, choices=STRATEGY_TYPE_CHOICES)
    description = models.TextField(blank=True)
    config_json = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["strategy_type", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.strategy_type})"


class BacktestRun(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="backtest_runs",
    )
    strategy_config = models.ForeignKey(
        StrategyConfig,
        on_delete=models.SET_NULL,
        related_name="backtest_runs",
        null=True,
        blank=True,
    )
    job_run = models.OneToOneField(
        JobRun,
        on_delete=models.SET_NULL,
        related_name="backtest_run",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=255, blank=True)
    strategy_type = models.CharField(max_length=64)
    resolution = models.CharField(max_length=16, default="D")
    benchmark_symbol = models.CharField(max_length=32, blank=True)

    start_date = models.DateField()
    end_date = models.DateField()
    initial_capital = models.DecimalField(max_digits=24, decimal_places=4, default=10000)
    position_size = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    commission_bps = models.DecimalField(max_digits=12, decimal_places=6, default=10)

    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    request_payload_json = models.JSONField(default=dict, blank=True)
    summary_json = models.JSONField(default=dict, blank=True)
    error_payload_json = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["strategy_type", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"BacktestRun({self.company.ticker}, {self.strategy_type}, {self.status})"


class BacktestResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    backtest_run = models.OneToOneField(
        BacktestRun,
        on_delete=models.CASCADE,
        related_name="result",
    )

    metrics_json = models.JSONField(default=dict, blank=True)
    equity_curve_json = models.JSONField(default=list, blank=True)
    drawdown_curve_json = models.JSONField(default=list, blank=True)
    signal_curve_json = models.JSONField(default=list, blank=True)
    trades_json = models.JSONField(default=list, blank=True)
    monthly_return_table_json = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"BacktestResult({self.backtest_run_id})"


class BacktestPriceBar(models.Model):
    RESOLUTION_DAY = "D"

    RESOLUTION_CHOICES = [
        (RESOLUTION_DAY, "Daily"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="backtest_price_bars",
    )

    source_name = models.CharField(max_length=64, default="finnhub")
    symbol = models.CharField(max_length=32, db_index=True)
    resolution = models.CharField(max_length=16, choices=RESOLUTION_CHOICES, default=RESOLUTION_DAY)

    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField(db_index=True)

    open_price = models.DecimalField(max_digits=24, decimal_places=6)
    high_price = models.DecimalField(max_digits=24, decimal_places=6)
    low_price = models.DecimalField(max_digits=24, decimal_places=6)
    close_price = models.DecimalField(max_digits=24, decimal_places=6)
    volume = models.DecimalField(max_digits=24, decimal_places=6, default=0)

    payload_json = models.JSONField(default=dict, blank=True)
    fetched_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_at"]
        indexes = [
            models.Index(fields=["company", "resolution", "start_at"]),
            models.Index(fields=["symbol", "resolution", "start_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "resolution", "start_at"],
                name="uq_backtest_price_bar_company_resolution_start_at",
            )
        ]

    def __str__(self) -> str:
        return f"{self.company.ticker} {self.resolution} {self.start_at.isoformat()}"