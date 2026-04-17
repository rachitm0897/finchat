from __future__ import annotations

from datetime import date
from typing import Any

from django.apps import apps as django_apps


class BacktestBridgeService:
    def is_available(self) -> bool:
        if not django_apps.is_installed("apps.backtesting"):
            return False
        try:
            from apps.jobs.services import JobDispatchService  # noqa: F401
            return hasattr(__import__("apps.jobs.services", fromlist=["JobDispatchService"]).JobDispatchService, "dispatch_backtest_job")
        except Exception:
            return False

    def run_simple_backtest(self, *, ticker: str) -> dict[str, Any]:
        if not self.is_available():
            return {
                "ok": False,
                "available": False,
                "message": "Backtesting app or dispatch_backtest_job is not installed in this backend snapshot.",
            }

        from apps.jobs.services import JobDispatchService

        result = JobDispatchService().dispatch_backtest_job(
            ticker=ticker,
            strategy_type="sma_crossover",
            start_date=date(2023, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=10000,
            position_size=1,
            commission_bps=10,
            async_mode=True,
        )
        return {
            "ok": True,
            "available": True,
            "job_id": result.job_id,
            "status": result.status,
            "celery_task_id": result.celery_task_id,
            "mode": result.mode,
        }