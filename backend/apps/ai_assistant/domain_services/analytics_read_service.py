from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.analytics.selectors import get_company_metric_snapshots, get_latest_metric_snapshot
from apps.market_data.models import Company


class AnalyticsReadService:
    DEFAULT_KEY_METRICS = [
        "valuation_price_to_earnings",
        "valuation_price_to_book",
        "growth_revenue_yoy",
        "profitability_net_margin",
        "cashflow_fcf_margin",
        "leverage_debt_to_equity",
        "liquidity_current_ratio",
        "summary_quality_score",
    ]

    def get_metrics_map(
        self,
        *,
        company: Company,
        metric_codes: list[str] | None = None,
        period_type: str | None = "annual",
    ) -> dict[str, dict[str, Any]]:
        rows = get_company_metric_snapshots(
            company=company,
            metric_codes=metric_codes or self.DEFAULT_KEY_METRICS,
            latest_only=True,
            period_type=period_type,
            limit=200,
        )

        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            result[row.metric_code] = {
                "metric_code": row.metric_code,
                "metric_name": row.metric_name,
                "metric_value": row.metric_value,
                "unit": row.unit,
                "as_of_date": row.as_of_date,
                "period_type": row.period_type,
            }
        return result

    def get_metric_value(
        self,
        *,
        company: Company,
        metric_code: str,
        period_type: str | None = "annual",
    ) -> Decimal | None:
        snap = get_latest_metric_snapshot(company=company, metric_code=metric_code, period_type=period_type)
        return snap.metric_value if snap else None

    def to_display_numbers(self, metrics_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for code, row in metrics_map.items():
            value = row.get("metric_value")
            payload[code] = float(value) if value is not None else None
        return payload