from __future__ import annotations

from rest_framework import status
from rest_framework.views import APIView

from apps.api.backtesting_serializers import (
    BacktestRunQuerySerializer,
    BacktestRunRequestSerializer,
    BacktestRunSerializer,
)
from apps.api.views import error_response, success_response
from apps.backtesting.selectors import get_backtest_run_by_id, list_backtest_runs
from apps.backtesting.services import BacktestExecutionService, PortfolioBacktestService
from apps.jobs.selectors import get_job_run_by_id
from apps.jobs.services import JobDispatchService
from apps.market_data.models import Company


class BacktestRunView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = BacktestRunRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid backtest request.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        payload = serializer.validated_data

        if payload["strategy_type"] != "portfolio_momentum":
            company = Company.objects.filter(ticker=payload["ticker"]).first()
            if company is None:
                return error_response(
                    code="not_found",
                    message=f"Company with ticker '{payload['ticker']}' was not found.",
                    http_status=status.HTTP_404_NOT_FOUND,
                )

        if payload["async_mode"] and payload["strategy_type"] != "portfolio_momentum":
            try:
                dispatch = JobDispatchService().dispatch_backtest_job(
                    ticker=payload["ticker"],
                    strategy_type=payload["strategy_type"],
                    start_date=payload["start_date"],
                    end_date=payload["end_date"],
                    initial_capital=payload["initial_capital"],
                    position_size=payload["position_size"],
                    commission_bps=payload["commission_bps"],
                    resolution=payload["resolution"],
                    benchmark_symbol=payload["benchmark_symbol"],
                    config_json=payload["config_json"],
                    use_stored_data=payload["use_stored_data"],
                    async_mode=True,
                )
                job = get_job_run_by_id(dispatch.job_id)
                backtest_run = getattr(job, "backtest_run", None) if job else None
                return success_response(
                    {
                        "mode": "async",
                        "job_id": dispatch.job_id,
                        "status": dispatch.status,
                        "celery_task_id": dispatch.celery_task_id,
                        "backtest_run_id": str(backtest_run.id) if backtest_run else "",
                    },
                    http_status=status.HTTP_202_ACCEPTED,
                )
            except Exception as exc:
                return error_response(
                    code="job_dispatch_error",
                    message="Failed to dispatch backtest job.",
                    details={"error": str(exc)},
                    http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        if payload["strategy_type"] == "portfolio_momentum":
            try:
                portfolio_payload = PortfolioBacktestService().run_portfolio_momentum(
                    tickers=payload["config_json"]["tickers"],
                    start_date=payload["start_date"],
                    end_date=payload["end_date"],
                    initial_capital=payload["initial_capital"],
                    lookback_window=int(payload["config_json"].get("lookback_window", 90)),
                    rebalance_days=int(payload["config_json"].get("rebalance_days", 21)),
                    top_n=int(payload["config_json"].get("top_n", 3)),
                )
            except Exception as exc:
                return error_response(
                    code="portfolio_backtest_error",
                    message="Portfolio backtest execution failed.",
                    details={"error": str(exc)},
                    http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return success_response(
                {
                    "mode": "sync",
                    "portfolio_backtest": portfolio_payload,
                }
            )

        try:
            company = Company.objects.get(ticker=payload["ticker"])
            strategy_service = BacktestExecutionService()
            strategy_config = strategy_service.build_strategy_config(
                strategy_type=payload["strategy_type"],
                config_json=payload["config_json"],
            )
            backtest_run = strategy_service.create_run(
                company=company,
                strategy_type=payload["strategy_type"],
                strategy_config=strategy_config,
                start_date=payload["start_date"],
                end_date=payload["end_date"],
                initial_capital=payload["initial_capital"],
                position_size=payload["position_size"],
                commission_bps=payload["commission_bps"],
                resolution=payload["resolution"],
                benchmark_symbol=payload["benchmark_symbol"],
                request_payload_json={
                    **payload["config_json"],
                    "use_stored_data": payload["use_stored_data"],
                },
            )
            result = strategy_service.run_backtest(
                backtest_run=backtest_run,
                config_json=payload["config_json"],
                use_stored_data=payload["use_stored_data"],
            )
        except Exception as exc:
            return error_response(
                code="backtest_error",
                message="Backtest execution failed.",
                details={"error": str(exc)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        run = get_backtest_run_by_id(result.backtest_run_id)
        return success_response(
            {
                "mode": "sync",
                "backtest_run": BacktestRunSerializer(run).data if run else None,
            }
        )


class BacktestRunListView(APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        serializer = BacktestRunQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response(
                code="validation_error",
                message="Invalid backtest list query.",
                details=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        rows = list_backtest_runs(
            ticker=serializer.validated_data["ticker"] or None,
            limit=serializer.validated_data["limit"],
        )
        return success_response(
            {
                "count": len(rows),
                "results": BacktestRunSerializer(rows, many=True).data,
            }
        )


class BacktestRunDetailView(APIView):
    permission_classes = []

    def get(self, request, run_id: str, *args, **kwargs):
        run = get_backtest_run_by_id(run_id)
        if run is None:
            return error_response(
                code="not_found",
                message=f"Backtest run '{run_id}' was not found.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        return success_response(BacktestRunSerializer(run).data)