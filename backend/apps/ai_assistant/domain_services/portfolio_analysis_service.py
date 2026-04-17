from __future__ import annotations

from typing import Any

from apps.ai_assistant.domain_services.analytics_read_service import AnalyticsReadService
from apps.market_data.models import Company


class PortfolioAnalysisService:
    def __init__(self) -> None:
        self.reader = AnalyticsReadService()

    def analyze(self, *, tickers: list[str]) -> dict[str, Any]:
        normalized = []
        seen = set()
        for ticker in tickers:
            t = ticker.strip().upper()
            if t and t not in seen:
                normalized.append(t)
                seen.add(t)

        companies = list(Company.objects.filter(ticker__in=normalized))
        if not companies:
            return {}

        rows: list[dict[str, Any]] = []
        for company in companies:
            metrics = self.reader.to_display_numbers(
                self.reader.get_metrics_map(
                    company=company,
                    metric_codes=[
                        "valuation_price_to_earnings",
                        "growth_revenue_yoy",
                        "leverage_debt_to_equity",
                        "summary_quality_score",
                    ],
                )
            )
            rows.append(
                {
                    "ticker": company.ticker,
                    "name": company.name,
                    "metrics": metrics,
                }
            )

        def avg(metric_code: str) -> float | None:
            values = [row["metrics"].get(metric_code) for row in rows if row["metrics"].get(metric_code) is not None]
            if not values:
                return None
            return round(sum(values) / len(values), 4)

        average_quality = avg("summary_quality_score")
        average_leverage = avg("leverage_debt_to_equity")

        if average_quality is None:
            growth_profile = "insufficient_data"
        elif average_quality >= 70:
            growth_profile = "higher_quality_growth"
        elif average_quality >= 45:
            growth_profile = "mixed_quality_growth"
        else:
            growth_profile = "lower_quality_growth"

        if average_leverage is None:
            risk_exposure = "insufficient_data"
        elif average_leverage >= 2:
            risk_exposure = "high"
        elif average_leverage >= 1:
            risk_exposure = "moderate"
        else:
            risk_exposure = "low"

        return {
            "company_count": len(rows),
            "companies": rows,
            "aggregate_metrics": {
                "average_valuation_price_to_earnings": avg("valuation_price_to_earnings"),
                "average_growth_revenue_yoy": avg("growth_revenue_yoy"),
                "average_leverage_debt_to_equity": average_leverage,
                "average_quality_score": average_quality,
            },
            "growth_profile": growth_profile,
            "risk_exposure": risk_exposure,
        }