from __future__ import annotations

from apps.jobs.models import JobRun


def get_job_run_by_id(job_id: str) -> JobRun | None:
    return JobRun.objects.filter(id=job_id).first()


def get_job_run_by_celery_task_id(celery_task_id: str) -> JobRun | None:
    return JobRun.objects.filter(celery_task_id=celery_task_id).first()


def list_recent_job_runs(limit: int = 20):
    return list(JobRun.objects.order_by("-created_at")[:limit])