from __future__ import annotations

from apps.backtesting.models import BacktestRun


def get_backtest_run_by_id(run_id: str) -> BacktestRun | None:
    return (
        BacktestRun.objects.select_related("company", "strategy_config", "job_run")
        .prefetch_related("result")
        .filter(id=run_id)
        .first()
    )


def list_backtest_runs(*, ticker: str | None = None, limit: int = 20):
    qs = BacktestRun.objects.select_related("company", "strategy_config", "job_run").order_by("-created_at")
    if ticker:
        qs = qs.filter(company__ticker=ticker.strip().upper())
    return list(qs[:limit])