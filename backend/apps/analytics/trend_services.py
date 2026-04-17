from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.analytics.selectors import get_metric_history
from apps.market_data.models import Company


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


class TrendAnalyticsService:
    """
    Deterministic time-series analytics built from stored normalized statements
    and stored computed metrics.
    """

    DEFAULT_TREND_METRICS = [
        "growth_revenue_yoy",
        "profitability_gross_margin",
        "profitability_net_margin",
        "cashflow_fcf_margin",
    ]

    def build_company_trends(
        self,
        ticker: str,
        period_type: str = "annual",
        limit: int = 8,
    ) -> dict[str, Any]:
        company = Company.objects.filter(ticker=ticker.strip().upper()).first()
        if company is None:
            raise ValueError(f"Company '{ticker}' not found.")

        periods = list(
            company.financial_periods.filter(period_type=period_type)
            .order_by("period_end_date")[:limit]
        )

        if not periods:
            raise ValueError("No financial periods available for trend analysis.")

        income_map = {
            row.period_id: row
            for row in company.income_statements.select_related("period")
            .filter(period__period_type=period_type)
        }
        cashflow_map = {
            row.period_id: row
            for row in company.cash_flow_statements.select_related("period")
            .filter(period__period_type=period_type)
        }

        revenue_series = []
        fcf_series = []

        for period in periods:
            income = income_map.get(period.id)
            cashflow = cashflow_map.get(period.id)

            revenue_series.append(
                {
                    "period_end_date": period.period_end_date.isoformat() if period.period_end_date else None,
                    "fiscal_year": period.fiscal_year,
                    "fiscal_quarter": period.fiscal_quarter,
                    "value": _as_str(getattr(income, "revenue", None) if income else None),
                }
            )
            fcf_series.append(
                {
                    "period_end_date": period.period_end_date.isoformat() if period.period_end_date else None,
                    "fiscal_year": period.fiscal_year,
                    "fiscal_quarter": period.fiscal_quarter,
                    "value": _as_str(getattr(cashflow, "free_cash_flow", None) if cashflow else None),
                }
            )

        metric_series = {}
        for metric_code in self.DEFAULT_TREND_METRICS:
            rows = list(
                reversed(
                    get_metric_history(
                        company=company,
                        metric_code=metric_code,
                        period_type=period_type,
                        limit=limit,
                    )
                )
            )
            metric_series[metric_code] = [
                {
                    "period_end_date": row.as_of_date.isoformat() if row.as_of_date else None,
                    "fiscal_year": row.period.fiscal_year if row.period else None,
                    "fiscal_quarter": row.period.fiscal_quarter if row.period else None,
                    "metric_code": row.metric_code,
                    "metric_name": row.metric_name,
                    "unit": row.unit,
                    "value": _as_str(row.metric_value),
                }
                for row in rows
            ]

        return {
            "ticker": company.ticker,
            "period_type": period_type,
            "series": {
                "revenue": revenue_series,
                "free_cash_flow": fcf_series,
                "growth_revenue_yoy": metric_series.get("growth_revenue_yoy", []),
                "gross_margin": metric_series.get("profitability_gross_margin", []),
                "net_margin": metric_series.get("profitability_net_margin", []),
                "fcf_margin": metric_series.get("cashflow_fcf_margin", []),
            },
        }

    def build_comparison_visuals(
        self,
        tickers: list[str],
        period_type: str = "annual",
    ) -> dict[str, Any]:
        normalized = []
        seen = set()
        for item in tickers:
            ticker = item.strip().upper()
            if ticker and ticker not in seen:
                normalized.append(ticker)
                seen.add(ticker)

        companies = list(Company.objects.filter(ticker__in=normalized))
        found = {c.ticker: c for c in companies}
        missing = [t for t in normalized if t not in found]

        metric_codes = [
            "profitability_net_margin",
            "growth_revenue_yoy",
            "cashflow_fcf_margin",
            "liquidity_current_ratio",
            "leverage_debt_to_equity",
            "summary_quality_score",
        ]

        visuals = []
        for metric_code in metric_codes:
            rows = []
            for ticker in normalized:
                company = found.get(ticker)
                if not company:
                    rows.append(
                        {
                            "ticker": ticker,
                            "company_name": ticker,
                            "metric_code": metric_code,
                            "metric_value": None,
                        }
                    )
                    continue

                from apps.analytics.selectors import get_latest_metric_snapshot

                snap = get_latest_metric_snapshot(company=company, metric_code=metric_code, period_type=period_type)
                rows.append(
                    {
                        "ticker": ticker,
                        "company_name": company.name,
                        "metric_code": metric_code,
                        "metric_name": snap.metric_name if snap else metric_code,
                        "metric_value": _as_str(snap.metric_value if snap else None),
                        "unit": snap.unit if snap else "",
                    }
                )

            visuals.append(
                {
                    "metric_code": metric_code,
                    "rows": rows,
                }
            )

        return {
            "requested_tickers": normalized,
            "missing_tickers": missing,
            "period_type": period_type,
            "visuals": visuals,
        }