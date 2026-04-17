from __future__ import annotations

from typing import Any

from apps.ai_assistant.domain_services.analytics_read_service import AnalyticsReadService
from apps.analytics.services import MetricComputationService
from apps.market_data.models import Company


class PeerBenchmarkService:
    def __init__(self) -> None:
        self.reader = AnalyticsReadService()

    def get_peers(self, *, company: Company, limit: int = 4) -> list[Company]:
        qs = Company.objects.filter(is_active=True).exclude(id=company.id)

        if company.industry:
            qs = qs.filter(industry=company.industry)
        elif company.primary_exchange:
            qs = qs.filter(primary_exchange=company.primary_exchange)

        return list(qs.order_by("ticker")[:limit])

    def ensure_peer_metrics(self, *, peers: list[Company]) -> None:
        for peer in peers:
            existing = self.reader.get_metrics_map(
                company=peer,
                metric_codes=["valuation_price_to_earnings", "growth_revenue_yoy", "profitability_net_margin"],
            )
            if existing:
                continue
            MetricComputationService(calculation_version="v1").compute_metrics_for_company(peer)

    def compare(self, *, company: Company) -> dict[str, Any]:
        peers = self.get_peers(company=company)
        if not peers:
            return {}

        self.ensure_peer_metrics(peers=peers)

        company_metrics = self.reader.to_display_numbers(
            self.reader.get_metrics_map(
                company=company,
                metric_codes=[
                    "valuation_price_to_earnings",
                    "growth_revenue_yoy",
                    "profitability_net_margin",
                ],
            )
        )

        peer_rows: list[dict[str, Any]] = []
        for peer in peers:
            metrics = self.reader.to_display_numbers(
                self.reader.get_metrics_map(
                    company=peer,
                    metric_codes=[
                        "valuation_price_to_earnings",
                        "growth_revenue_yoy",
                        "profitability_net_margin",
                    ],
                )
            )
            peer_rows.append(
                {
                    "ticker": peer.ticker,
                    "name": peer.name,
                    "industry": peer.industry,
                    "metrics": metrics,
                }
            )

        def average_metric(metric_code: str) -> float | None:
            values = [
                row["metrics"].get(metric_code)
                for row in peer_rows
                if row["metrics"].get(metric_code) is not None
            ]
            if not values:
                return None
            return round(sum(values) / len(values), 4)

        peer_avg_pe = average_metric("valuation_price_to_earnings")
        peer_avg_growth = average_metric("growth_revenue_yoy")
        peer_avg_margin = average_metric("profitability_net_margin")

        valuation_relative = None
        if company_metrics.get("valuation_price_to_earnings") is not None and peer_avg_pe is not None:
            valuation_relative = (
                "cheaper_than_peers"
                if company_metrics["valuation_price_to_earnings"] < peer_avg_pe
                else "richer_than_peers"
            )

        return {
            "peer_count": len(peer_rows),
            "peer_rows": peer_rows,
            "peer_averages": {
                "valuation_price_to_earnings": peer_avg_pe,
                "growth_revenue_yoy": peer_avg_growth,
                "profitability_net_margin": peer_avg_margin,
            },
            "company_metrics": company_metrics,
            "valuation_relative": valuation_relative,
        }