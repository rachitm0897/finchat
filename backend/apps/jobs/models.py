from __future__ import annotations

import uuid

from django.db import models

from apps.market_data.models import Company


class JobRun(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    JOB_TYPE_COMPANY_SYNC = "company_sync"
    JOB_TYPE_FINANCIAL_INGESTION = "financial_ingestion"
    JOB_TYPE_ANALYTICS_COMPUTE = "analytics_compute"
    JOB_TYPE_VALUATION = "valuation"
    JOB_TYPE_CHAT_ANALYSIS = "chat_analysis"
    JOB_TYPE_REPORT_GENERATION = "report_generation"
    JOB_TYPE_BACKTEST = "backtest"

    JOB_TYPE_CHOICES = [
        (JOB_TYPE_COMPANY_SYNC, "Company Sync"),
        (JOB_TYPE_FINANCIAL_INGESTION, "Financial Ingestion"),
        (JOB_TYPE_ANALYTICS_COMPUTE, "Analytics Compute"),
        (JOB_TYPE_VALUATION, "Valuation"),
        (JOB_TYPE_CHAT_ANALYSIS, "Chat Analysis"),
        (JOB_TYPE_REPORT_GENERATION, "Report Generation"),
        (JOB_TYPE_BACKTEST, "Backtest"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        related_name="job_runs",
        null=True,
        blank=True,
    )

    job_type = models.CharField(max_length=64, choices=JOB_TYPE_CHOICES)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)

    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True)

    request_payload_json = models.JSONField(default=dict, blank=True)
    result_payload_json = models.JSONField(default=dict, blank=True)
    error_payload_json = models.JSONField(default=dict, blank=True)

    requested_by = models.CharField(max_length=128, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["job_type", "status"]),
            models.Index(fields=["company", "-created_at"]),
            models.Index(fields=["requested_by"]),
            models.Index(fields=["celery_task_id"]),
            models.Index(fields=["idempotency_key"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["job_type", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uq_jobrun_jobtype_idempotency_nonempty",
            )
        ]

    def __str__(self) -> str:
        return f"{self.job_type} [{self.status}] {self.id}"