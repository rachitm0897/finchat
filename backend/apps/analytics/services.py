from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from apps.analytics.formulas import (
    abs_decimal,
    average_two,
    flag,
    pct_change,
    quantize_metric,
    safe_div,
    sum_present,
)
from apps.analytics.models import ComputedMetricSnapshot
from apps.fundamentals.models import CompanyFinancialPeriod
from apps.market_data.models import Company, CompanyQuoteSnapshot

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MetricDefinition:
    metric_code: str
    metric_name: str
    metric_value: Decimal | None
    unit: str
    notes: str = ""
    source_trace: dict[str, Any] | None = None


@dataclass(slots=True)
class CompanyMetricComputationResult:
    ticker: str
    company_id: str
    periods_seen: int
    metrics_written: int
    metrics_updated: int
    metrics_skipped: int


def _maybe_related(period: CompanyFinancialPeriod, attr: str):
    try:
        return getattr(period, attr)
    except ObjectDoesNotExist:
        return None


def _metric(
    metric_code: str,
    metric_name: str,
    metric_value: Decimal | None,
    unit: str,
    notes: str = "",
    source_trace: dict[str, Any] | None = None,
) -> MetricDefinition:
    return MetricDefinition(
        metric_code=metric_code,
        metric_name=metric_name,
        metric_value=quantize_metric(metric_value),
        unit=unit,
        notes=notes,
        source_trace=source_trace or {},
    )


class MetricComputationService:
    """
    Deterministic financial metric engine.

    Reads:
    - CompanyFinancialPeriod + related normalized statements
    - latest stored CompanyQuoteSnapshot for market-based ratios

    Writes:
    - ComputedMetricSnapshot
    """

    def __init__(self, calculation_version: str = "v1") -> None:
        self.calculation_version = calculation_version

    def compute_metrics_for_company(self, company: Company) -> CompanyMetricComputationResult:
        periods = list(
            company.financial_periods.select_related(
                "income_statement",
                "balance_sheet",
                "cash_flow_statement",
            ).order_by("period_end_date")
        )

        periods_seen = len(periods)
        metrics_written = 0
        metrics_updated = 0
        metrics_skipped = 0

        if not periods:
            return CompanyMetricComputationResult(
                ticker=company.ticker,
                company_id=str(company.id),
                periods_seen=0,
                metrics_written=0,
                metrics_updated=0,
                metrics_skipped=0,
            )

        periods_by_key = {
            (p.period_type, p.fiscal_year, p.fiscal_quarter): p
            for p in periods
        }

        latest_quote = company.quote_snapshots.filter(is_latest=True).order_by("-fetched_at").first()

        for period in periods:
            comparable_prior = self._get_prior_period(periods_by_key=periods_by_key, current_period=period)
            metric_defs = self._compute_period_metrics(
                company=company,
                period=period,
                prior_period=comparable_prior,
                latest_quote=latest_quote,
                latest_period=period == periods[-1],
            )

            written, updated, skipped = self._persist_metrics(
                company=company,
                period=period,
                metric_definitions=metric_defs,
            )
            metrics_written += written
            metrics_updated += updated
            metrics_skipped += skipped

        return CompanyMetricComputationResult(
            ticker=company.ticker,
            company_id=str(company.id),
            periods_seen=periods_seen,
            metrics_written=metrics_written,
            metrics_updated=metrics_updated,
            metrics_skipped=metrics_skipped,
        )

    def compute_metrics_for_ticker(self, ticker: str) -> CompanyMetricComputationResult:
        company = Company.objects.get(ticker=ticker.strip().upper())
        return self.compute_metrics_for_company(company=company)

    def compute_metrics_for_all_companies(self, active_only: bool = False) -> dict[str, Any]:
        queryset = Company.objects.all().order_by("ticker")
        if active_only:
            queryset = queryset.filter(is_active=True)

        results: list[CompanyMetricComputationResult] = []
        for company in queryset:
            results.append(self.compute_metrics_for_company(company=company))

        return {
            "companies_processed": len(results),
            "results": results,
        }

    def _get_prior_period(
        self,
        periods_by_key: dict[tuple[str, int, int | None], CompanyFinancialPeriod],
        current_period: CompanyFinancialPeriod,
    ) -> CompanyFinancialPeriod | None:
        previous_year = current_period.fiscal_year - 1
        key = (current_period.period_type, previous_year, current_period.fiscal_quarter)
        return periods_by_key.get(key)

    def _compute_period_metrics(
        self,
        company: Company,
        period: CompanyFinancialPeriod,
        prior_period: CompanyFinancialPeriod | None,
        latest_quote: CompanyQuoteSnapshot | None,
        latest_period: bool,
    ) -> list[MetricDefinition]:
        income = _maybe_related(period, "income_statement")
        balance = _maybe_related(period, "balance_sheet")
        cashflow = _maybe_related(period, "cash_flow_statement")

        prior_income = _maybe_related(prior_period, "income_statement") if prior_period else None
        prior_balance = _maybe_related(prior_period, "balance_sheet") if prior_period else None
        prior_cashflow = _maybe_related(prior_period, "cash_flow_statement") if prior_period else None

        metrics: list[MetricDefinition] = []

        # ---------------------------------------------------------------------
        # Pull current values
        # ---------------------------------------------------------------------
        revenue = getattr(income, "revenue", None)
        gross_profit = getattr(income, "gross_profit", None)
        operating_income = getattr(income, "operating_income", None)
        net_income = getattr(income, "net_income", None)
        diluted_eps = getattr(income, "diluted_eps", None)
        diluted_shares = getattr(income, "weighted_average_diluted_shares", None)

        current_assets = getattr(balance, "total_current_assets", None)
        current_liabilities = getattr(balance, "total_current_liabilities", None)
        cash_and_equivalents = getattr(balance, "cash_and_cash_equivalents", None)
        short_term_investments = getattr(balance, "short_term_investments", None)
        accounts_receivable = getattr(balance, "accounts_receivable", None)
        inventory = getattr(balance, "inventory", None)
        total_assets = getattr(balance, "total_assets", None)
        total_liabilities = getattr(balance, "total_liabilities", None)
        total_equity = getattr(balance, "total_shareholders_equity", None)
        short_term_debt = getattr(balance, "short_term_debt", None)
        long_term_debt = getattr(balance, "long_term_debt", None)

        cfo = getattr(cashflow, "cash_from_operating_activities", None)
        capex = getattr(cashflow, "capital_expenditure", None)
        fcf = getattr(cashflow, "free_cash_flow", None)

        prior_revenue = getattr(prior_income, "revenue", None)
        prior_gross_profit = getattr(prior_income, "gross_profit", None)
        prior_net_income = getattr(prior_income, "net_income", None)
        prior_total_assets = getattr(prior_balance, "total_assets", None)
        prior_total_equity = getattr(prior_balance, "total_shareholders_equity", None)
        prior_cfo = getattr(prior_cashflow, "cash_from_operating_activities", None)
        prior_fcf = getattr(prior_cashflow, "free_cash_flow", None)

        average_assets = average_two(total_assets, prior_total_assets)
        average_equity = average_two(total_equity, prior_total_equity)
        total_debt = sum_present(short_term_debt, long_term_debt)
        cash_like = sum_present(cash_and_equivalents, short_term_investments)

        # ---------------------------------------------------------------------
        # Profitability ratios
        # ---------------------------------------------------------------------
        gross_margin = safe_div(gross_profit, revenue)
        operating_margin = safe_div(operating_income, revenue)
        net_margin = safe_div(net_income, revenue)
        roa = safe_div(net_income, average_assets)
        roe = safe_div(net_income, average_equity)

        metrics.extend(
            [
                _metric(
                    "profitability_gross_margin",
                    "Gross Margin",
                    gross_margin,
                    "ratio",
                    "Gross profit divided by revenue.",
                    {"inputs": ["income_statement.gross_profit", "income_statement.revenue"]},
                ),
                _metric(
                    "profitability_operating_margin",
                    "Operating Margin",
                    operating_margin,
                    "ratio",
                    "Operating income divided by revenue.",
                    {"inputs": ["income_statement.operating_income", "income_statement.revenue"]},
                ),
                _metric(
                    "profitability_net_margin",
                    "Net Margin",
                    net_margin,
                    "ratio",
                    "Net income divided by revenue.",
                    {"inputs": ["income_statement.net_income", "income_statement.revenue"]},
                ),
                _metric(
                    "profitability_return_on_assets",
                    "Return on Assets",
                    roa,
                    "ratio",
                    "Net income divided by average total assets.",
                    {"inputs": ["income_statement.net_income", "balance_sheet.total_assets"]},
                ),
                _metric(
                    "profitability_return_on_equity",
                    "Return on Equity",
                    roe,
                    "ratio",
                    "Net income divided by average shareholders' equity.",
                    {"inputs": ["income_statement.net_income", "balance_sheet.total_shareholders_equity"]},
                ),
            ]
        )

        # ---------------------------------------------------------------------
        # Growth metrics (YoY on comparable period)
        # ---------------------------------------------------------------------
        revenue_growth = pct_change(revenue, prior_revenue)
        gross_profit_growth = pct_change(gross_profit, prior_gross_profit)
        net_income_growth = pct_change(net_income, prior_net_income)
        cfo_growth = pct_change(cfo, prior_cfo)
        fcf_growth = pct_change(fcf, prior_fcf)

        metrics.extend(
            [
                _metric(
                    "growth_revenue_yoy",
                    "Revenue YoY Growth",
                    revenue_growth,
                    "pct",
                    "Comparable-period year-over-year revenue growth.",
                    {"inputs": ["income_statement.revenue", "prior_income_statement.revenue"]},
                ),
                _metric(
                    "growth_gross_profit_yoy",
                    "Gross Profit YoY Growth",
                    gross_profit_growth,
                    "pct",
                    "Comparable-period year-over-year gross profit growth.",
                    {"inputs": ["income_statement.gross_profit", "prior_income_statement.gross_profit"]},
                ),
                _metric(
                    "growth_net_income_yoy",
                    "Net Income YoY Growth",
                    net_income_growth,
                    "pct",
                    "Comparable-period year-over-year net income growth.",
                    {"inputs": ["income_statement.net_income", "prior_income_statement.net_income"]},
                ),
                _metric(
                    "growth_cfo_yoy",
                    "Cash From Operations YoY Growth",
                    cfo_growth,
                    "pct",
                    "Comparable-period year-over-year cash from operations growth.",
                    {"inputs": ["cash_flow_statement.cash_from_operating_activities", "prior_cash_flow_statement.cash_from_operating_activities"]},
                ),
                _metric(
                    "growth_fcf_yoy",
                    "Free Cash Flow YoY Growth",
                    fcf_growth,
                    "pct",
                    "Comparable-period year-over-year free cash flow growth.",
                    {"inputs": ["cash_flow_statement.free_cash_flow", "prior_cash_flow_statement.free_cash_flow"]},
                ),
            ]
        )

        # ---------------------------------------------------------------------
        # Leverage ratios
        # ---------------------------------------------------------------------
        debt_to_equity = safe_div(total_debt, total_equity)
        debt_to_assets = safe_div(total_debt, total_assets)

        metrics.extend(
            [
                _metric(
                    "leverage_debt_to_equity",
                    "Debt to Equity",
                    debt_to_equity,
                    "ratio",
                    "Total debt divided by shareholders' equity.",
                    {"inputs": ["balance_sheet.short_term_debt", "balance_sheet.long_term_debt", "balance_sheet.total_shareholders_equity"]},
                ),
                _metric(
                    "leverage_debt_to_assets",
                    "Debt to Assets",
                    debt_to_assets,
                    "ratio",
                    "Total debt divided by total assets.",
                    {"inputs": ["balance_sheet.short_term_debt", "balance_sheet.long_term_debt", "balance_sheet.total_assets"]},
                ),
            ]
        )

        # ---------------------------------------------------------------------
        # Liquidity ratios
        # ---------------------------------------------------------------------
        current_ratio = safe_div(current_assets, current_liabilities)
        cash_ratio = safe_div(cash_like, current_liabilities)
        working_capital = None
        if current_assets is not None and current_liabilities is not None:
            working_capital = current_assets - current_liabilities

        metrics.extend(
            [
                _metric(
                    "liquidity_current_ratio",
                    "Current Ratio",
                    current_ratio,
                    "ratio",
                    "Current assets divided by current liabilities.",
                    {"inputs": ["balance_sheet.total_current_assets", "balance_sheet.total_current_liabilities"]},
                ),
                _metric(
                    "liquidity_cash_ratio",
                    "Cash Ratio",
                    cash_ratio,
                    "ratio",
                    "Cash and short-term investments divided by current liabilities.",
                    {"inputs": ["balance_sheet.cash_and_cash_equivalents", "balance_sheet.short_term_investments", "balance_sheet.total_current_liabilities"]},
                ),
                _metric(
                    "liquidity_working_capital",
                    "Working Capital",
                    working_capital,
                    "currency",
                    "Current assets minus current liabilities.",
                    {"inputs": ["balance_sheet.total_current_assets", "balance_sheet.total_current_liabilities"]},
                ),
            ]
        )

        # ---------------------------------------------------------------------
        # Efficiency ratios
        # ---------------------------------------------------------------------
        asset_turnover = safe_div(revenue, average_assets)
        receivables_to_revenue = safe_div(accounts_receivable, revenue)
        inventory_to_revenue = safe_div(inventory, revenue)

        metrics.extend(
            [
                _metric(
                    "efficiency_asset_turnover",
                    "Asset Turnover",
                    asset_turnover,
                    "ratio",
                    "Revenue divided by average total assets.",
                    {"inputs": ["income_statement.revenue", "balance_sheet.total_assets"]},
                ),
                _metric(
                    "efficiency_receivables_to_revenue",
                    "Receivables to Revenue",
                    receivables_to_revenue,
                    "ratio",
                    "Accounts receivable divided by revenue.",
                    {"inputs": ["balance_sheet.accounts_receivable", "income_statement.revenue"]},
                ),
                _metric(
                    "efficiency_inventory_to_revenue",
                    "Inventory to Revenue",
                    inventory_to_revenue,
                    "ratio",
                    "Inventory divided by revenue.",
                    {"inputs": ["balance_sheet.inventory", "income_statement.revenue"]},
                ),
            ]
        )

        # ---------------------------------------------------------------------
        # Cash flow metrics
        # ---------------------------------------------------------------------
        cfo_margin = safe_div(cfo, revenue)
        fcf_margin = safe_div(fcf, revenue)
        capex_to_cfo = safe_div(abs_decimal(capex), abs_decimal(cfo))
        cash_conversion = safe_div(cfo, net_income)

        metrics.extend(
            [
                _metric(
                    "cashflow_cfo_margin",
                    "Cash From Operations Margin",
                    cfo_margin,
                    "ratio",
                    "Cash from operations divided by revenue.",
                    {"inputs": ["cash_flow_statement.cash_from_operating_activities", "income_statement.revenue"]},
                ),
                _metric(
                    "cashflow_fcf_margin",
                    "Free Cash Flow Margin",
                    fcf_margin,
                    "ratio",
                    "Free cash flow divided by revenue.",
                    {"inputs": ["cash_flow_statement.free_cash_flow", "income_statement.revenue"]},
                ),
                _metric(
                    "cashflow_capex_to_cfo",
                    "Capex to CFO",
                    capex_to_cfo,
                    "ratio",
                    "Absolute capital expenditure divided by absolute cash from operations.",
                    {"inputs": ["cash_flow_statement.capital_expenditure", "cash_flow_statement.cash_from_operating_activities"]},
                ),
                _metric(
                    "cashflow_cash_conversion",
                    "Cash Conversion",
                    cash_conversion,
                    "ratio",
                    "Cash from operations divided by net income.",
                    {"inputs": ["cash_flow_statement.cash_from_operating_activities", "income_statement.net_income"]},
                ),
            ]
        )

        # ---------------------------------------------------------------------
        # Valuation ratios
        # Only compute on the latest period so current market price is not mixed
        # into every historical period row.
        # ---------------------------------------------------------------------
        if latest_period and latest_quote:
            current_price = latest_quote.current_price

            market_cap_estimate = None
            if current_price is not None and diluted_shares is not None:
                market_cap_estimate = current_price * diluted_shares

            book_value_per_share = safe_div(total_equity, diluted_shares)
            sales_per_share = safe_div(revenue, diluted_shares)
            enterprise_value_estimate = None
            if market_cap_estimate is not None:
                enterprise_value_estimate = market_cap_estimate
                if total_debt is not None:
                    enterprise_value_estimate += total_debt
                if cash_like is not None:
                    enterprise_value_estimate -= cash_like

            price_to_earnings = safe_div(current_price, diluted_eps)
            price_to_book = safe_div(current_price, book_value_per_share)
            price_to_sales = safe_div(current_price, sales_per_share)
            ev_to_sales = safe_div(enterprise_value_estimate, revenue)
            ev_to_fcf = safe_div(enterprise_value_estimate, fcf)

            metrics.extend(
                [
                    _metric(
                        "valuation_market_cap_estimate",
                        "Market Capitalization Estimate",
                        market_cap_estimate,
                        "currency",
                        "Estimated as current share price multiplied by weighted average diluted shares.",
                        {"inputs": ["quote_snapshot.current_price", "income_statement.weighted_average_diluted_shares"]},
                    ),
                    _metric(
                        "valuation_enterprise_value_estimate",
                        "Enterprise Value Estimate",
                        enterprise_value_estimate,
                        "currency",
                        "Estimated as market cap plus total debt minus cash and short-term investments.",
                        {"inputs": ["quote_snapshot.current_price", "income_statement.weighted_average_diluted_shares", "balance_sheet.short_term_debt", "balance_sheet.long_term_debt", "balance_sheet.cash_and_cash_equivalents", "balance_sheet.short_term_investments"]},
                    ),
                    _metric(
                        "valuation_price_to_earnings",
                        "Price to Earnings",
                        price_to_earnings,
                        "ratio",
                        "Current share price divided by diluted EPS.",
                        {"inputs": ["quote_snapshot.current_price", "income_statement.diluted_eps"]},
                    ),
                    _metric(
                        "valuation_price_to_book",
                        "Price to Book",
                        price_to_book,
                        "ratio",
                        "Current share price divided by book value per share.",
                        {"inputs": ["quote_snapshot.current_price", "balance_sheet.total_shareholders_equity", "income_statement.weighted_average_diluted_shares"]},
                    ),
                    _metric(
                        "valuation_price_to_sales",
                        "Price to Sales",
                        price_to_sales,
                        "ratio",
                        "Current share price divided by revenue per share.",
                        {"inputs": ["quote_snapshot.current_price", "income_statement.revenue", "income_statement.weighted_average_diluted_shares"]},
                    ),
                    _metric(
                        "valuation_ev_to_sales",
                        "EV to Sales",
                        ev_to_sales,
                        "ratio",
                        "Estimated enterprise value divided by revenue.",
                        {"inputs": ["quote_snapshot.current_price", "income_statement.revenue", "balance_sheet.short_term_debt", "balance_sheet.long_term_debt", "balance_sheet.cash_and_cash_equivalents", "balance_sheet.short_term_investments"]},
                    ),
                    _metric(
                        "valuation_ev_to_fcf",
                        "EV to FCF",
                        ev_to_fcf,
                        "ratio",
                        "Estimated enterprise value divided by free cash flow.",
                        {"inputs": ["quote_snapshot.current_price", "cash_flow_statement.free_cash_flow", "balance_sheet.short_term_debt", "balance_sheet.long_term_debt", "balance_sheet.cash_and_cash_equivalents", "balance_sheet.short_term_investments"]},
                    ),
                ]
            )

        # ---------------------------------------------------------------------
        # Risk flags
        # Stored as 1 or 0
        # ---------------------------------------------------------------------
        gross_margin_prior = safe_div(prior_gross_profit, prior_revenue)

        negative_net_income_flag = net_income is not None and net_income < Decimal("0")
        negative_cfo_flag = cfo is not None and cfo < Decimal("0")
        high_leverage_flag = debt_to_equity is not None and debt_to_equity > Decimal("2")
        low_liquidity_flag = current_ratio is not None and current_ratio < Decimal("1")
        margin_compression_flag = (
            gross_margin is not None
            and gross_margin_prior is not None
            and gross_margin < gross_margin_prior
        )
        revenue_decline_flag = revenue_growth is not None and revenue_growth < Decimal("0")

        metrics.extend(
            [
                _metric(
                    "risk_negative_net_income_flag",
                    "Risk Flag: Negative Net Income",
                    flag(negative_net_income_flag),
                    "flag",
                    "1 if net income is negative, else 0.",
                    {"inputs": ["income_statement.net_income"]},
                ),
                _metric(
                    "risk_negative_cfo_flag",
                    "Risk Flag: Negative Cash From Operations",
                    flag(negative_cfo_flag),
                    "flag",
                    "1 if cash from operations is negative, else 0.",
                    {"inputs": ["cash_flow_statement.cash_from_operating_activities"]},
                ),
                _metric(
                    "risk_high_leverage_flag",
                    "Risk Flag: High Leverage",
                    flag(high_leverage_flag),
                    "flag",
                    "1 if debt to equity exceeds 2.0, else 0.",
                    {"inputs": ["balance_sheet.short_term_debt", "balance_sheet.long_term_debt", "balance_sheet.total_shareholders_equity"]},
                ),
                _metric(
                    "risk_low_liquidity_flag",
                    "Risk Flag: Low Liquidity",
                    flag(low_liquidity_flag),
                    "flag",
                    "1 if current ratio is below 1.0, else 0.",
                    {"inputs": ["balance_sheet.total_current_assets", "balance_sheet.total_current_liabilities"]},
                ),
                _metric(
                    "risk_margin_compression_flag",
                    "Risk Flag: Margin Compression",
                    flag(margin_compression_flag),
                    "flag",
                    "1 if gross margin declined versus comparable prior period, else 0.",
                    {"inputs": ["income_statement.gross_profit", "income_statement.revenue", "prior_income_statement.gross_profit", "prior_income_statement.revenue"]},
                ),
                _metric(
                    "risk_revenue_decline_flag",
                    "Risk Flag: Revenue Decline",
                    flag(revenue_decline_flag),
                    "flag",
                    "1 if comparable-period revenue growth is negative, else 0.",
                    {"inputs": ["income_statement.revenue", "prior_income_statement.revenue"]},
                ),
            ]
        )

        # ---------------------------------------------------------------------
        # Summary trend signals
        # Stored as 1 or 0 plus a simple quality score.
        # ---------------------------------------------------------------------
        revenue_growth_positive = revenue_growth is not None and revenue_growth > Decimal("0")
        profitability_positive = net_margin is not None and net_margin > Decimal("0")
        cashflow_positive = cfo is not None and cfo > Decimal("0")

        prior_net_margin = safe_div(prior_net_income, prior_revenue)
        profitability_improving = (
            net_margin is not None
            and prior_net_margin is not None
            and net_margin > prior_net_margin
        )

        available_quality_checks = [
            current_ratio is not None,
            debt_to_equity is not None,
            net_margin is not None,
            cfo is not None,
            fcf is not None,
            revenue_growth is not None,
        ]

        quality_score_components = [
            current_ratio is not None and current_ratio >= Decimal("1"),
            debt_to_equity is not None and debt_to_equity < Decimal("2"),
            net_margin is not None and net_margin > Decimal("0"),
            cfo is not None and cfo > Decimal("0"),
            fcf is not None and fcf > Decimal("0"),
            revenue_growth is not None and revenue_growth > Decimal("0"),
        ]

        quality_score = None
        checks_available_count = sum(1 for x in available_quality_checks if x)
        if checks_available_count > 0:
            positive_checks = sum(1 for x in quality_score_components if x)
            quality_score = Decimal(positive_checks) / Decimal(checks_available_count) * Decimal("100")

        metrics.extend(
            [
                _metric(
                    "trend_revenue_growth_positive",
                    "Trend Signal: Positive Revenue Growth",
                    flag(revenue_growth_positive),
                    "flag",
                    "1 if comparable-period revenue growth is positive, else 0.",
                    {"inputs": ["income_statement.revenue", "prior_income_statement.revenue"]},
                ),
                _metric(
                    "trend_profitability_positive",
                    "Trend Signal: Positive Profitability",
                    flag(profitability_positive),
                    "flag",
                    "1 if net margin is positive, else 0.",
                    {"inputs": ["income_statement.net_income", "income_statement.revenue"]},
                ),
                _metric(
                    "trend_cashflow_positive",
                    "Trend Signal: Positive Cash Flow",
                    flag(cashflow_positive),
                    "flag",
                    "1 if cash from operations is positive, else 0.",
                    {"inputs": ["cash_flow_statement.cash_from_operating_activities"]},
                ),
                _metric(
                    "trend_profitability_improving",
                    "Trend Signal: Improving Profitability",
                    flag(profitability_improving),
                    "flag",
                    "1 if net margin improved versus comparable prior period, else 0.",
                    {"inputs": ["income_statement.net_income", "income_statement.revenue", "prior_income_statement.net_income", "prior_income_statement.revenue"]},
                ),
                _metric(
                    "summary_quality_score",
                    "Summary Quality Score",
                    quality_score,
                    "score",
                    "Simple deterministic score from 0 to 100 based on profitability, growth, leverage, liquidity, and cash flow checks.",
                    {"checks": ["current_ratio>=1", "debt_to_equity<2", "net_margin>0", "cfo>0", "fcf>0", "revenue_growth>0"]},
                ),
            ]
        )

        return metrics

    @transaction.atomic
    def _persist_metrics(
        self,
        company: Company,
        period: CompanyFinancialPeriod,
        metric_definitions: list[MetricDefinition],
    ) -> tuple[int, int, int]:
        written = 0
        updated = 0
        skipped = 0

        as_of_date = period.period_end_date or timezone.now().date()

        for metric_def in metric_definitions:
            if metric_def.metric_value is None:
                skipped += 1
                continue

            obj, created = ComputedMetricSnapshot.objects.update_or_create(
                company=company,
                period=period,
                metric_code=metric_def.metric_code,
                calculation_version=self.calculation_version,
                defaults={
                    "as_of_date": as_of_date,
                    "period_type": period.period_type,
                    "metric_name": metric_def.metric_name,
                    "metric_value": metric_def.metric_value,
                    "unit": metric_def.unit,
                    "source_trace": metric_def.source_trace or {},
                    "notes": metric_def.notes,
                },
            )
            if created:
                written += 1
            else:
                updated += 1

        return written, updated, skipped