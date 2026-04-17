from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.analytics.services import MetricComputationService
from apps.jobs.models import JobRun
from apps.market_data.models import Company
from apps.market_data.services import CompanyIngestionService
from datetime import date, datetime
from decimal import Decimal
from apps.backtesting.services import BacktestExecutionService

@dataclass(slots=True)
class JobDispatchResult:
    job_id: str
    status: str
    mode: str
    celery_task_id: str | None
    result: dict[str, Any]


class JobStatusService:
    @staticmethod
    def mark_running(job: JobRun, celery_task_id: str | None = None) -> JobRun:
        job.status = JobRun.STATUS_RUNNING
        job.started_at = timezone.now()
        if celery_task_id:
            job.celery_task_id = celery_task_id
        job.save(update_fields=["status", "started_at", "celery_task_id", "updated_at"])
        return job

    @staticmethod
    def mark_success(job: JobRun, result_payload: dict[str, Any]) -> JobRun:
        job.status = JobRun.STATUS_SUCCESS
        job.result_payload_json = result_payload
        job.finished_at = timezone.now()
        job.error_payload_json = {}
        job.save(update_fields=["status", "result_payload_json", "finished_at", "error_payload_json", "updated_at"])
        return job

    @staticmethod
    def mark_failed(job: JobRun, error_payload: dict[str, Any]) -> JobRun:
        job.status = JobRun.STATUS_FAILED
        job.error_payload_json = error_payload
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_payload_json", "finished_at", "updated_at"])
        return job


class JobDispatchService:
    """
    Dispatches ingestion, analytics, and report jobs in either:
    - sync mode for local execution
    - async mode through Celery for production-ready execution
    """

    @transaction.atomic
    def create_job_run(
        self,
        *,
        job_type: str,
        company: Company | None = None,
        request_payload_json: dict[str, Any] | None = None,
        requested_by: str = "",
        idempotency_key: str = "",
    ) -> JobRun:
        return JobRun.objects.create(
            company=company,
            job_type=job_type,
            status=JobRun.STATUS_PENDING,
            request_payload_json=request_payload_json or {},
            requested_by=requested_by,
            idempotency_key=idempotency_key,
        )

    def dispatch_ingestion_job(
        self,
        *,
        ticker: str,
        async_mode: bool = False,
        ingest_statements: bool = True,
        requested_by: str = "",
        idempotency_key: str = "",
    ) -> JobDispatchResult:
        normalized_ticker = ticker.strip().upper()
        company = Company.objects.filter(ticker=normalized_ticker).first()

        job = self.create_job_run(
            job_type=JobRun.JOB_TYPE_FINANCIAL_INGESTION,
            company=company,
            request_payload_json={
                "ticker": normalized_ticker,
                "ingest_statements": ingest_statements,
            },
            requested_by=requested_by,
            idempotency_key=idempotency_key,
        )

        if async_mode:
            from apps.jobs.tasks import run_ingestion_job_task

            task_result = run_ingestion_job_task.delay(
                job_id=str(job.id),
                ticker=normalized_ticker,
                ingest_statements=ingest_statements,
            )
            job.celery_task_id = task_result.id
            job.save(update_fields=["celery_task_id", "updated_at"])

            return JobDispatchResult(
                job_id=str(job.id),
                status=job.status,
                mode="async",
                celery_task_id=task_result.id,
                result={"message": "Ingestion job dispatched."},
            )

        result = self._run_ingestion_sync(
            job_id=str(job.id),
            ticker=normalized_ticker,
            ingest_statements=ingest_statements,
        )
        return JobDispatchResult(
            job_id=str(job.id),
            status=result["job_status"],
            mode="sync",
            celery_task_id=None,
            result=result,
        )

    def dispatch_analytics_refresh_job(
        self,
        *,
        ticker: str,
        async_mode: bool = False,
        calculation_version: str = "v1",
        requested_by: str = "",
        idempotency_key: str = "",
    ) -> JobDispatchResult:
        normalized_ticker = ticker.strip().upper()
        company = Company.objects.filter(ticker=normalized_ticker).first()

        job = self.create_job_run(
            job_type=JobRun.JOB_TYPE_ANALYTICS_COMPUTE,
            company=company,
            request_payload_json={
                "ticker": normalized_ticker,
                "calculation_version": calculation_version,
            },
            requested_by=requested_by,
            idempotency_key=idempotency_key,
        )

        if async_mode:
            from apps.jobs.tasks import run_analytics_refresh_job_task

            task_result = run_analytics_refresh_job_task.delay(
                job_id=str(job.id),
                ticker=normalized_ticker,
                calculation_version=calculation_version,
            )
            job.celery_task_id = task_result.id
            job.save(update_fields=["celery_task_id", "updated_at"])

            return JobDispatchResult(
                job_id=str(job.id),
                status=job.status,
                mode="async",
                celery_task_id=task_result.id,
                result={"message": "Analytics job dispatched."},
            )

        result = self._run_analytics_sync(
            job_id=str(job.id),
            ticker=normalized_ticker,
            calculation_version=calculation_version,
        )
        return JobDispatchResult(
            job_id=str(job.id),
            status=result["job_status"],
            mode="sync",
            celery_task_id=None,
            result=result,
        )
    def _run_backtest_sync(
        self,
        *,
        job_id: str,
        backtest_run_id: str,
        use_stored_data: bool = True,
    ) -> dict[str, Any]:
        job = JobRun.objects.get(id=job_id)
        JobStatusService.mark_running(job)

        from apps.backtesting.models import BacktestRun

        backtest_run = BacktestRun.objects.select_related("company", "strategy_config").get(id=backtest_run_id)
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
                "job_status": JobRun.STATUS_SUCCESS,
            }
            JobStatusService.mark_success(job, payload)
            return payload
        except Exception as exc:
            BacktestExecutionService().mark_failed(backtest_run=backtest_run, error=str(exc))
            JobStatusService.mark_failed(job, {"error": str(exc), "backtest_run_id": backtest_run_id})
            raise
        
    def dispatch_backtest_job(
        self,
        *,
        ticker: str,
        strategy_type: str,
        start_date: date,
        end_date: date,
        initial_capital: Decimal,
        position_size: Decimal,
        commission_bps: Decimal,
        resolution: str = "D",
        benchmark_symbol: str = "",
        config_json: dict[str, Any] | None = None,
        use_stored_data: bool = True,
        async_mode: bool = False,
        requested_by: str = "",
        idempotency_key: str = "",
    ) -> JobDispatchResult:
        normalized_ticker = ticker.strip().upper()
        company = Company.objects.filter(ticker=normalized_ticker).first()
        if company is None:
            raise ValueError(f"Company with ticker '{normalized_ticker}' does not exist. Ingest it first.")

        job = self.create_job_run(
            job_type=JobRun.JOB_TYPE_BACKTEST,
            company=company,
            request_payload_json={
                "ticker": normalized_ticker,
                "strategy_type": strategy_type,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "initial_capital": str(initial_capital),
                "position_size": str(position_size),
                "commission_bps": str(commission_bps),
                "resolution": resolution,
                "benchmark_symbol": benchmark_symbol,
                "config_json": config_json or {},
                "use_stored_data": use_stored_data,
            },
            requested_by=requested_by,
            idempotency_key=idempotency_key,
        )

        strategy_service = BacktestExecutionService()
        strategy_config = strategy_service.build_strategy_config(
            strategy_type=strategy_type,
            config_json=config_json or {},
        )
        backtest_run = strategy_service.create_run(
            company=company,
            strategy_type=strategy_type,
            strategy_config=strategy_config,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            position_size=position_size,
            commission_bps=commission_bps,
            resolution=resolution,
            benchmark_symbol=benchmark_symbol,
            request_payload_json={
                **(config_json or {}),
                "use_stored_data": use_stored_data,
            },
            job_run=job,
        )

        if async_mode:
            from apps.jobs.tasks import run_backtest_job_task

            task_result = run_backtest_job_task.delay(
                job_id=str(job.id),
                backtest_run_id=str(backtest_run.id),
                use_stored_data=use_stored_data,
            )
            job.celery_task_id = task_result.id
            job.save(update_fields=["celery_task_id", "updated_at"])

            return JobDispatchResult(
                job_id=str(job.id),
                status=job.status,
                mode="async",
                celery_task_id=task_result.id,
                result={"message": "Backtest job dispatched.", "backtest_run_id": str(backtest_run.id)},
            )

        result = self._run_backtest_sync(
            job_id=str(job.id),
            backtest_run_id=str(backtest_run.id),
            use_stored_data=use_stored_data,
        )
        return JobDispatchResult(
            job_id=str(job.id),
            status=result["job_status"],
            mode="sync",
            celery_task_id=None,
            result=result,
        )

    def dispatch_report_generation_job(
        self,
        *,
        company_id: str | None = None,
        report_type: str = "company_summary",
        async_mode: bool = False,
        requested_by: str = "",
        idempotency_key: str = "",
        request_payload_json: dict[str, Any] | None = None,
    ) -> JobDispatchResult:
        company = Company.objects.filter(id=company_id).first() if company_id else None

        payload = {
            "company_id": company_id,
            "report_type": report_type,
        }
        if request_payload_json:
            payload.update(request_payload_json)

        job = self.create_job_run(
            job_type=JobRun.JOB_TYPE_REPORT_GENERATION,
            company=company,
            request_payload_json=payload,
            requested_by=requested_by,
            idempotency_key=idempotency_key,
        )

        if async_mode:
            from apps.jobs.tasks import run_report_generation_job_task

            task_result = run_report_generation_job_task.delay(
                job_id=str(job.id),
                company_id=company_id,
                report_type=report_type,
                request_payload_json=payload,
            )
            job.celery_task_id = task_result.id
            job.save(update_fields=["celery_task_id", "updated_at"])

            return JobDispatchResult(
                job_id=str(job.id),
                status=job.status,
                mode="async",
                celery_task_id=task_result.id,
                result={"message": "Report generation job dispatched."},
            )

        result = self._run_report_sync(
            job_id=str(job.id),
            company_id=company_id,
            report_type=report_type,
            request_payload_json=payload,
        )
        return JobDispatchResult(
            job_id=str(job.id),
            status=result["job_status"],
            mode="sync",
            celery_task_id=None,
            result=result,
        )

    def _run_ingestion_sync(
        self,
        *,
        job_id: str,
        ticker: str,
        ingest_statements: bool,
    ) -> dict[str, Any]:
        job = JobRun.objects.get(id=job_id)
        JobStatusService.mark_running(job)

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
            return {
                "job_id": str(job.id),
                "job_status": JobRun.STATUS_SUCCESS,
                **payload,
            }
        except Exception as exc:
            error_payload = {"error": str(exc)}
            JobStatusService.mark_failed(job, error_payload)
            return {
                "job_id": str(job.id),
                "job_status": JobRun.STATUS_FAILED,
                "error": str(exc),
            }

    def _run_analytics_sync(
        self,
        *,
        job_id: str,
        ticker: str,
        calculation_version: str,
    ) -> dict[str, Any]:
        job = JobRun.objects.get(id=job_id)
        JobStatusService.mark_running(job)

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
            return {
                "job_id": str(job.id),
                "job_status": JobRun.STATUS_SUCCESS,
                **payload,
            }
        except Exception as exc:
            error_payload = {"error": str(exc)}
            JobStatusService.mark_failed(job, error_payload)
            return {
                "job_id": str(job.id),
                "job_status": JobRun.STATUS_FAILED,
                "error": str(exc),
            }

    def _run_report_sync(
        self,
        *,
        job_id: str,
        company_id: str | None,
        report_type: str,
        request_payload_json: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Placeholder sync report execution hook.

        This keeps the job contract stable now, even if the report engine
        is implemented later.
        """
        job = JobRun.objects.get(id=job_id)
        JobStatusService.mark_running(job)

        try:
            payload = {
                "company_id": company_id,
                "report_type": report_type,
                "status": "placeholder",
                "message": "Report generation service is not wired yet.",
                "request_payload_json": request_payload_json,
            }
            JobStatusService.mark_success(job, payload)
            return {
                "job_id": str(job.id),
                "job_status": JobRun.STATUS_SUCCESS,
                **payload,
            }
        except Exception as exc:
            error_payload = {"error": str(exc)}
            JobStatusService.mark_failed(job, error_payload)
            return {
                "job_id": str(job.id),
                "job_status": JobRun.STATUS_FAILED,
                "error": str(exc),
            }