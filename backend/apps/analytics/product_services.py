from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.analytics.selectors import get_latest_metrics_map
from apps.market_data.models import Company
from apps.core.cache_keys import analysis_summary_key
from apps.core.cache_utils import CacheService


def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_metric_value_from_map(metrics_map: dict[str, Any], metric_code: str) -> Decimal | None:
    snap = metrics_map.get(metric_code)
    if not snap:
        return None
    return _to_decimal(snap.metric_value)


class SmartAnalysisService:
    """
    Deterministic higher-level product analytics built on top of stored
    computed metrics and normalized statements.
    """

    DEFAULT_PEER_METRICS = [
        "profitability_net_margin",
        "growth_revenue_yoy",
        "liquidity_current_ratio",
        "leverage_debt_to_equity",
        "cashflow_fcf_margin",
        "valuation_price_to_earnings",
        "summary_quality_score",
    ]

    METRIC_DIRECTIONS = {
        "profitability_net_margin": "desc",
        "growth_revenue_yoy": "desc",
        "liquidity_current_ratio": "desc",
        "leverage_debt_to_equity": "asc",
        "cashflow_fcf_margin": "desc",
        "valuation_price_to_earnings": "asc",
        "summary_quality_score": "desc",
        "valuation_ev_to_fcf": "asc",
        "valuation_price_to_book": "asc",
        "growth_net_income_yoy": "desc",
        "growth_fcf_yoy": "desc",
    }

    def build_company_analysis_summary(self, ticker: str) -> dict[str, Any]:
        normalized_ticker = ticker.strip().upper()
        cache_key = analysis_summary_key(normalized_ticker)

        def _builder() -> dict[str, Any]:
            company = Company.objects.filter(ticker=normalized_ticker).first()
            if company is None:
                raise ValueError(f"Company '{ticker}' not found.")

            metric_codes = [
                "profitability_net_margin",
                "profitability_gross_margin",
                "growth_revenue_yoy",
                "growth_net_income_yoy",
                "cashflow_fcf_margin",
                "liquidity_current_ratio",
                "leverage_debt_to_equity",
                "valuation_price_to_earnings",
                "valuation_ev_to_fcf",
                "summary_quality_score",
                "risk_negative_net_income_flag",
                "risk_negative_cfo_flag",
                "risk_high_leverage_flag",
                "risk_low_liquidity_flag",
                "risk_margin_compression_flag",
                "risk_revenue_decline_flag",
            ]

            latest_metrics = get_latest_metrics_map(company=company, metric_codes=metric_codes, period_type="annual")
            metrics = {code: _latest_metric_value_from_map(latest_metrics, code) for code in metric_codes}

            strengths: list[str] = []
            weaknesses: list[str] = []
            warnings: list[str] = []

            net_margin = metrics["profitability_net_margin"]
            revenue_growth = metrics["growth_revenue_yoy"]
            fcf_margin = metrics["cashflow_fcf_margin"]
            current_ratio = metrics["liquidity_current_ratio"]
            debt_to_equity = metrics["leverage_debt_to_equity"]
            pe_ratio = metrics["valuation_price_to_earnings"]
            quality_score = metrics["summary_quality_score"]

            if net_margin is not None and net_margin > Decimal("0.15"):
                strengths.append("Strong net margin.")
            elif net_margin is not None and net_margin < Decimal("0.05"):
                weaknesses.append("Thin net margin.")

            if revenue_growth is not None and revenue_growth > Decimal("0.08"):
                strengths.append("Healthy year-over-year revenue growth.")
            elif revenue_growth is not None and revenue_growth < Decimal("0"):
                weaknesses.append("Negative year-over-year revenue growth.")

            if fcf_margin is not None and fcf_margin > Decimal("0.10"):
                strengths.append("Healthy free cash flow margin.")
            elif fcf_margin is not None and fcf_margin < Decimal("0"):
                weaknesses.append("Negative free cash flow margin.")

            if current_ratio is not None and current_ratio < Decimal("1"):
                weaknesses.append("Weak near-term liquidity profile.")
            elif current_ratio is not None and current_ratio > Decimal("1.5"):
                strengths.append("Comfortable liquidity profile.")

            if debt_to_equity is not None and debt_to_equity > Decimal("2"):
                weaknesses.append("High balance-sheet leverage.")
            elif debt_to_equity is not None and debt_to_equity < Decimal("1"):
                strengths.append("Moderate leverage.")

            if quality_score is not None and quality_score >= Decimal("70"):
                strengths.append("High deterministic quality score.")
            elif quality_score is not None and quality_score < Decimal("40"):
                weaknesses.append("Low deterministic quality score.")

            risk_flags = {
                "negative_net_income": metrics["risk_negative_net_income_flag"],
                "negative_cfo": metrics["risk_negative_cfo_flag"],
                "high_leverage": metrics["risk_high_leverage_flag"],
                "low_liquidity": metrics["risk_low_liquidity_flag"],
                "margin_compression": metrics["risk_margin_compression_flag"],
                "revenue_decline": metrics["risk_revenue_decline_flag"],
            }

            for key, value in risk_flags.items():
                if value is None:
                    warnings.append(f"Risk flag '{key}' is unavailable.")

            latest_period = company.financial_periods.order_by("-period_end_date").first()
            latest_income = company.income_statements.select_related("period").order_by("-period__period_end_date").first()
            latest_balance = company.balance_sheets.select_related("period").order_by("-period__period_end_date").first()
            latest_cashflow = company.cash_flow_statements.select_related("period").order_by("-period__period_end_date").first()

            return {
                "ticker": company.ticker,
                "company": {
                    "id": str(company.id),
                    "ticker": company.ticker,
                    "name": company.name,
                    "industry": company.industry,
                    "country": company.country,
                    "currency_code": company.currency_code,
                },
                "latest_period": {
                    "period_type": latest_period.period_type if latest_period else None,
                    "fiscal_year": latest_period.fiscal_year if latest_period else None,
                    "fiscal_quarter": latest_period.fiscal_quarter if latest_period else None,
                    "period_end_date": latest_period.period_end_date.isoformat() if latest_period and latest_period.period_end_date else None,
                },
                "key_metrics": {
                    "net_margin": str(net_margin) if net_margin is not None else None,
                    "revenue_growth_yoy": str(revenue_growth) if revenue_growth is not None else None,
                    "fcf_margin": str(fcf_margin) if fcf_margin is not None else None,
                    "current_ratio": str(current_ratio) if current_ratio is not None else None,
                    "debt_to_equity": str(debt_to_equity) if debt_to_equity is not None else None,
                    "price_to_earnings": str(pe_ratio) if pe_ratio is not None else None,
                    "quality_score": str(quality_score) if quality_score is not None else None,
                },
                "latest_financials": {
                    "revenue": str(latest_income.revenue) if latest_income and latest_income.revenue is not None else None,
                    "net_income": str(latest_income.net_income) if latest_income and latest_income.net_income is not None else None,
                    "total_assets": str(latest_balance.total_assets) if latest_balance and latest_balance.total_assets is not None else None,
                    "total_equity": str(latest_balance.total_shareholders_equity) if latest_balance and latest_balance.total_shareholders_equity is not None else None,
                    "cash_from_operations": str(latest_cashflow.cash_from_operating_activities) if latest_cashflow and latest_cashflow.cash_from_operating_activities is not None else None,
                    "free_cash_flow": str(latest_cashflow.free_cash_flow) if latest_cashflow and latest_cashflow.free_cash_flow is not None else None,
                },
                "strengths": strengths,
                "weaknesses": weaknesses,
                "risk_flags": {key: (str(value) if value is not None else None) for key, value in risk_flags.items()},
                "coverage_warnings": warnings,
            }

        return CacheService.get_or_set(cache_key, _builder, timeout=60 * 15)

    def build_peer_ranking(
        self,
        tickers: list[str],
        metric_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in tickers:
            t = item.strip().upper()
            if t and t not in seen:
                normalized.append(t)
                seen.add(t)

        metric_codes = metric_codes or self.DEFAULT_PEER_METRICS

        companies = list(Company.objects.filter(ticker__in=normalized))
        by_ticker = {c.ticker: c for c in companies}
        missing = [t for t in normalized if t not in by_ticker]

        company_metrics_map: dict[str, dict[str, Any]] = {
            ticker: get_latest_metrics_map(
                company=company,
                metric_codes=metric_codes,
                period_type="annual",
            )
            for ticker, company in by_ticker.items()
        }

        rankings: list[dict[str, Any]] = []
        composite_scores: dict[str, Decimal] = {ticker: Decimal("0") for ticker in by_ticker.keys()}
        composite_counts: dict[str, int] = {ticker: 0 for ticker in by_ticker.keys()}

        for metric_code in metric_codes:
            metric_rows = []
            for ticker, company in by_ticker.items():
                metrics_map = company_metrics_map.get(ticker, {})
                value = _latest_metric_value_from_map(metrics_map, metric_code)
                metric_rows.append(
                    {
                        "ticker": ticker,
                        "company_name": company.name,
                        "metric_code": metric_code,
                        "metric_value": value,
                    }
                )

            direction = self.METRIC_DIRECTIONS.get(metric_code, "desc")
            comparable_rows = [row for row in metric_rows if row["metric_value"] is not None]

            comparable_rows.sort(
                key=lambda row: row["metric_value"],
                reverse=(direction == "desc"),
            )

            total_comparable = len(comparable_rows)

            for rank, row in enumerate(comparable_rows, start=1):
                row["rank"] = rank
                row["percentile"] = (
                    (Decimal(total_comparable - rank) / Decimal(max(total_comparable - 1, 1))) * Decimal("100")
                    if total_comparable > 1 else Decimal("100")
                )
                composite_scores[row["ticker"]] += Decimal(total_comparable - rank + 1)
                composite_counts[row["ticker"]] += 1

            for row in metric_rows:
                if "rank" not in row:
                    row["rank"] = None
                    row["percentile"] = None

            rankings.append(
                {
                    "metric_code": metric_code,
                    "direction": direction,
                    "rows": [
                        {
                            "ticker": row["ticker"],
                            "company_name": row["company_name"],
                            "metric_value": str(row["metric_value"]) if row["metric_value"] is not None else None,
                            "rank": row["rank"],
                            "percentile": str(row["percentile"]) if row["percentile"] is not None else None,
                        }
                        for row in metric_rows
                    ],
                }
            )

        overall = []
        for ticker, company in by_ticker.items():
            avg_score = None
            if composite_counts[ticker] > 0:
                avg_score = composite_scores[ticker] / Decimal(composite_counts[ticker])

            overall.append(
                {
                    "ticker": ticker,
                    "company_name": company.name,
                    "composite_score": str(avg_score) if avg_score is not None else None,
                }
            )

        overall.sort(
            key=lambda row: Decimal(row["composite_score"]) if row["composite_score"] is not None else Decimal("-999999"),
            reverse=True,
        )

        for idx, row in enumerate(overall, start=1):
            row["overall_rank"] = idx

        return {
            "requested_tickers": normalized,
            "missing_tickers": missing,
            "metric_codes": metric_codes,
            "rankings": rankings,
            "overall_ranking": overall,
        }

    def build_scenario_analysis(
        self,
        ticker: str,
        years: int = 3,
        scenarios: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        company = Company.objects.filter(ticker=ticker.strip().upper()).first()
        if company is None:
            raise ValueError(f"Company '{ticker}' not found.")

        latest_income = company.income_statements.select_related("period").order_by("-period__period_end_date").first()
        latest_balance = company.balance_sheets.select_related("period").order_by("-period__period_end_date").first()

        if latest_income is None:
            raise ValueError("No normalized income statement available for scenario analysis.")

        scenario_metric_codes = [
            "cashflow_fcf_margin",
            "valuation_price_to_earnings",
            "valuation_ev_to_fcf",
        ]
        metrics_map = get_latest_metrics_map(
            company=company,
            metric_codes=scenario_metric_codes,
            period_type="annual",
        )

        revenue = _to_decimal(latest_income.revenue)
        diluted_shares = _to_decimal(latest_income.weighted_average_diluted_shares)
        fcf_margin = _latest_metric_value_from_map(metrics_map, "cashflow_fcf_margin")
        current_pe = _latest_metric_value_from_map(metrics_map, "valuation_price_to_earnings")
        current_ev_fcf = _latest_metric_value_from_map(metrics_map, "valuation_ev_to_fcf")

        cash = _to_decimal(getattr(latest_balance, "cash_and_cash_equivalents", None)) if latest_balance else None
        short_term_investments = _to_decimal(getattr(latest_balance, "short_term_investments", None)) if latest_balance else None
        short_term_debt = _to_decimal(getattr(latest_balance, "short_term_debt", None)) if latest_balance else None
        long_term_debt = _to_decimal(getattr(latest_balance, "long_term_debt", None)) if latest_balance else None

        total_cash = (cash or Decimal("0")) + (short_term_investments or Decimal("0"))
        total_debt = (short_term_debt or Decimal("0")) + (long_term_debt or Decimal("0"))
        net_cash = total_cash - total_debt

        if revenue is None:
            raise ValueError("Latest revenue is unavailable for scenario analysis.")
        if diluted_shares is None or diluted_shares == 0:
            raise ValueError("Diluted share count is unavailable for scenario analysis.")
        if fcf_margin is None:
            raise ValueError("FCF margin is unavailable for scenario analysis.")

        default_exit_multiple = current_ev_fcf if current_ev_fcf is not None else Decimal("18")

        scenarios = scenarios or [
            {
                "name": "bear",
                "revenue_growth": "-0.03",
                "fcf_margin": str(max(fcf_margin - Decimal("0.03"), Decimal("0"))),
                "exit_multiple": str(max(default_exit_multiple - Decimal("4"), Decimal("8"))),
            },
            {
                "name": "base",
                "revenue_growth": "0.05",
                "fcf_margin": str(fcf_margin),
                "exit_multiple": str(default_exit_multiple),
            },
            {
                "name": "bull",
                "revenue_growth": "0.10",
                "fcf_margin": str(fcf_margin + Decimal("0.03")),
                "exit_multiple": str(default_exit_multiple + Decimal("4")),
            },
        ]

        output_scenarios = []
        for scenario in scenarios:
            growth = _to_decimal(scenario.get("revenue_growth"))
            margin = _to_decimal(scenario.get("fcf_margin"))
            multiple = _to_decimal(scenario.get("exit_multiple"))

            if growth is None or margin is None or multiple is None:
                continue

            projected_revenue = revenue * ((Decimal("1") + growth) ** years)
            projected_fcf = projected_revenue * margin
            enterprise_value = projected_fcf * multiple
            equity_value = enterprise_value + net_cash
            implied_share_price = equity_value / diluted_shares

            output_scenarios.append(
                {
                    "name": scenario.get("name", "scenario"),
                    "years": years,
                    "revenue_growth": str(growth),
                    "fcf_margin": str(margin),
                    "exit_multiple": str(multiple),
                    "projected_revenue": str(projected_revenue),
                    "projected_fcf": str(projected_fcf),
                    "enterprise_value": str(enterprise_value),
                    "equity_value": str(equity_value),
                    "implied_share_price": str(implied_share_price),
                }
            )

        return {
            "ticker": company.ticker,
            "assumptions_source": {
                "latest_revenue": str(revenue),
                "latest_fcf_margin": str(fcf_margin),
                "latest_price_to_earnings": str(current_pe) if current_pe is not None else None,
                "latest_ev_to_fcf": str(current_ev_fcf) if current_ev_fcf is not None else None,
                "net_cash": str(net_cash),
                "diluted_shares": str(diluted_shares),
            },
            "scenarios": output_scenarios,
        }