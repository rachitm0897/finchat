from __future__ import annotations

import uuid

from django.db import models


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ticker = models.CharField(max_length=32, unique=True)
    finnhub_symbol = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=64, blank=True)
    currency_code = models.CharField(max_length=16, blank=True)
    exchange = models.CharField(max_length=128, blank=True)
    primary_exchange = models.CharField(max_length=128, blank=True)
    ipo_date = models.DateField(null=True, blank=True)
    market_identifier_code = models.CharField(max_length=32, blank=True)
    logo_url = models.URLField(blank=True)
    web_url = models.URLField(blank=True)
    industry = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ticker"]
        indexes = [
            models.Index(fields=["ticker"]),
            models.Index(fields=["finnhub_symbol"]),
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.ticker} - {self.name}"


class CompanyProfileSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="profile_snapshots",
    )

    source_name = models.CharField(max_length=64, default="finnhub")
    endpoint_name = models.CharField(max_length=128, default="company_profile")
    fetched_at = models.DateTimeField()
    is_latest = models.BooleanField(default=False, db_index=True)

    symbol = models.CharField(max_length=32, db_index=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    request_params = models.JSONField(default=dict, blank=True)
    payload_json = models.JSONField(default=dict, blank=True)

    # flattened snapshot fields for convenient querying
    country = models.CharField(max_length=64, blank=True)
    currency_code = models.CharField(max_length=16, blank=True)
    exchange = models.CharField(max_length=128, blank=True)
    ipo_date = models.DateField(null=True, blank=True)
    market_capitalization = models.DecimalField(
        max_digits=24, decimal_places=4, null=True, blank=True
    )
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    share_outstanding = models.DecimalField(
        max_digits=24, decimal_places=4, null=True, blank=True
    )
    ticker = models.CharField(max_length=32, blank=True)
    web_url = models.URLField(blank=True)
    logo_url = models.URLField(blank=True)
    industry = models.CharField(max_length=128, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fetched_at"]
        indexes = [
            models.Index(fields=["company", "-fetched_at"]),
            models.Index(fields=["symbol", "-fetched_at"]),
            models.Index(fields=["source_name", "endpoint_name"]),
            models.Index(fields=["is_latest"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "fetched_at", "endpoint_name"],
                name="uq_profile_snapshot_company_fetched_endpoint",
            )
        ]

    def __str__(self) -> str:
        return f"ProfileSnapshot({self.company.ticker}, {self.fetched_at.isoformat()})"


class CompanyQuoteSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="quote_snapshots",
    )

    source_name = models.CharField(max_length=64, default="finnhub")
    endpoint_name = models.CharField(max_length=128, default="quote")
    fetched_at = models.DateTimeField()
    is_latest = models.BooleanField(default=False, db_index=True)

    symbol = models.CharField(max_length=32, db_index=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    request_params = models.JSONField(default=dict, blank=True)
    payload_json = models.JSONField(default=dict, blank=True)

    current_price = models.DecimalField(
        max_digits=24, decimal_places=6, null=True, blank=True
    )
    change = models.DecimalField(
        max_digits=24, decimal_places=6, null=True, blank=True
    )
    percent_change = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True
    )
    high_price = models.DecimalField(
        max_digits=24, decimal_places=6, null=True, blank=True
    )
    low_price = models.DecimalField(
        max_digits=24, decimal_places=6, null=True, blank=True
    )
    open_price = models.DecimalField(
        max_digits=24, decimal_places=6, null=True, blank=True
    )
    previous_close_price = models.DecimalField(
        max_digits=24, decimal_places=6, null=True, blank=True
    )
    quote_timestamp = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fetched_at"]
        indexes = [
            models.Index(fields=["company", "-fetched_at"]),
            models.Index(fields=["symbol", "-fetched_at"]),
            models.Index(fields=["quote_timestamp"]),
            models.Index(fields=["is_latest"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "fetched_at", "endpoint_name"],
                name="uq_quote_snapshot_company_fetched_endpoint",
            )
        ]

    def __str__(self) -> str:
        return f"QuoteSnapshot({self.company.ticker}, {self.fetched_at.isoformat()})"


class CompanyBasicMetricSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="basic_metric_snapshots",
    )

    source_name = models.CharField(max_length=64, default="finnhub")
    endpoint_name = models.CharField(max_length=128, default="basic_financials")
    fetched_at = models.DateTimeField()
    is_latest = models.BooleanField(default=False, db_index=True)

    symbol = models.CharField(max_length=32, db_index=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    request_params = models.JSONField(default=dict, blank=True)
    payload_json = models.JSONField(default=dict, blank=True)

    metric_values = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fetched_at"]
        indexes = [
            models.Index(fields=["company", "-fetched_at"]),
            models.Index(fields=["symbol", "-fetched_at"]),
            models.Index(fields=["source_name", "endpoint_name"]),
            models.Index(fields=["is_latest"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "fetched_at", "endpoint_name"],
                name="uq_basic_metric_snapshot_company_fetched_endpoint",
            )
        ]

    def __str__(self) -> str:
        return f"BasicMetricSnapshot({self.company.ticker}, {self.fetched_at.isoformat()})"