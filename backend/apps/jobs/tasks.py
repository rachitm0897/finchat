from __future__ import annotations

from celery import shared_task

from apps.jobs.models import JobRun
from apps.jobs.services import JobStatusService
from apps.analytics.services import MetricComputationService
from apps.market_data.models import Company
from apps.market_data.services import CompanyIngestionService


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def run_ingestion_job_task(self, *, job_id: str, ticker: str, ingest_statements: bool = True):
    job = JobRun.objects.get(id=job_id)
    JobStatusService.mark_running(job, celery_task_id=self.request.id)

    try:
        result = CompanyIngestionService().ingest_company(
            ticker=ticker,
            ingest_statements=ingest_statements,
        )
        payload = {
            "ticker": result.ticker,
            "company_id": result.company_id,
            "company_created": result.company_created,
            "profile_snapshot_created": result.profile_snapshot_created,
            "quote_snapshot_created": result.quote_snapshot_created,
            "basic_metric_snapshot_created": result.basic_metric_snapshot_created,
            "statements_result": result.statements_result,
            "warnings": result.warnings,
        }
        JobStatusService.mark_success(job, payload)
        return payload
    except Exception as exc:
        JobStatusService.mark_failed(job, {"error": str(exc)})
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def run_analytics_refresh_job_task(self, *, job_id: str, ticker: str, calculation_version: str = "v1"):
    job = JobRun.objects.get(id=job_id)
    JobStatusService.mark_running(job, celery_task_id=self.request.id)

    try:
        company = Company.objects.get(ticker=ticker)
        result = MetricComputationService(
            calculation_version=calculation_version
        ).compute_metrics_for_company(company)

        payload = {
            "ticker": result.ticker,
            "company_id": result.company_id,
            "periods_seen": result.periods_seen,
            "metrics_written": result.metrics_written,
            "metrics_updated": result.metrics_updated,
            "metrics_skipped": result.metrics_skipped,
            "calculation_version": calculation_version,
        }
        JobStatusService.mark_success(job, payload)
        return payload
    except Exception as exc:
        JobStatusService.mark_failed(job, {"error": str(exc)})
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def run_report_generation_job_task(
    self,
    *,
    job_id: str,
    company_id: str | None = None,
    report_type: str = "company_summary",
    request_payload_json: dict | None = None,
):
    """
    Placeholder async report task.

    This preserves the orchestration contract and JobRun status handling.
    Wire it to the real report service when the report engine is finalized.
    """
    job = JobRun.objects.get(id=job_id)
    JobStatusService.mark_running(job, celery_task_id=self.request.id)

    try:
        payload = {
            "company_id": company_id,
            "report_type": report_type,
            "status": "placeholder",
            "message": "Report generation service is not wired yet.",
            "request_payload_json": request_payload_json or {},
        }
        JobStatusService.mark_success(job, payload)
        return payload
    except Exception as exc:
        JobStatusService.mark_failed(job, {"error": str(exc)})
        raise
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def run_backtest_job_task(
    self,
    *,
    job_id: str,
    backtest_run_id: str,
    use_stored_data: bool = True,
):
    from apps.backtesting.models import BacktestRun
    from apps.backtesting.services import BacktestExecutionService

    job = JobRun.objects.get(id=job_id)
    backtest_run = BacktestRun.objects.select_related("company", "strategy_config").get(id=backtest_run_id)
    JobStatusService.mark_running(job, celery_task_id=self.request.id)

    config_json = backtest_run.strategy_config.config_json if backtest_run.strategy_config else {}

    try:
        result = BacktestExecutionService().run_backtest(
            backtest_run=backtest_run,
            config_json=config_json,
            use_stored_data=use_stored_data,
        )
        payload = {
            "backtest_run_id": result.backtest_run_id,
            "ticker": result.ticker,
            "metrics": result.metrics,
            "summary": result.summary,
        }
        JobStatusService.mark_success(job, payload)
        return payload
    except Exception as exc:
        BacktestExecutionService().mark_failed(backtest_run=backtest_run, error=str(exc))
        JobStatusService.mark_failed(job, {"error": str(exc), "backtest_run_id": backtest_run_id})
        raise