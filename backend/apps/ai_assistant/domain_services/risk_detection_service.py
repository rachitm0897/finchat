from __future__ import annotations

from typing import Any

from apps.ai_assistant.domain_services.analytics_read_service import AnalyticsReadService
from apps.market_data.models import Company


class RiskDetectionService:
    def __init__(self) -> None:
        self.reader = AnalyticsReadService()

    def detect(self, *, company: Company) -> list[str]:
        metrics = self.reader.to_display_numbers(
            self.reader.get_metrics_map(
                company=company,
                metric_codes=[
                    "risk_negative_net_income_flag",
                    "risk_negative_cfo_flag",
                    "risk_high_leverage_flag",
                    "risk_low_liquidity_flag",
                    "risk_margin_compression_flag",
                    "risk_revenue_decline_flag",
                    "leverage_debt_to_equity",
                    "liquidity_current_ratio",
                    "cashflow_fcf_margin",
                    "summary_quality_score",
                ],
            )
        )

        risks: list[str] = []

        if metrics.get("risk_margin_compression_flag") not in (None, 0):
            risks.append("Margins show compression in the latest stored analytics.")
        if metrics.get("risk_high_leverage_flag") not in (None, 0):
            risks.append("Leverage is elevated based on the latest stored debt metrics.")
        if metrics.get("risk_negative_cfo_flag") not in (None, 0):
            risks.append("Operating cash flow is negative in the latest stored period.")
        if metrics.get("risk_revenue_decline_flag") not in (None, 0):
            risks.append("Revenue trend is declining in the latest stored period.")
        if metrics.get("risk_low_liquidity_flag") not in (None, 0):
            risks.append("Liquidity is weak based on the latest stored ratios.")
        if metrics.get("cashflow_fcf_margin") is not None and metrics["cashflow_fcf_margin"] < 0:
            risks.append("Free cash flow margin is negative.")
        if metrics.get("summary_quality_score") is not None and metrics["summary_quality_score"] < 40:
            risks.append("Overall quality score is weak.")

        return risks