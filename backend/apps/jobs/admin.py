from __future__ import annotations

from django.contrib import admin

from apps.jobs.models import JobRun


@admin.register(JobRun)
class JobRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job_type",
        "status",
        "company",
        "requested_by",
        "started_at",
        "finished_at",
        "created_at",
    )
    search_fields = ("celery_task_id", "idempotency_key", "requested_by", "company__ticker")
    list_filter = ("job_type", "status")