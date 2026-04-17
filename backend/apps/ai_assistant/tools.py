from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from langchain_core.tools import tool

from apps.analytics.selectors import (
    get_company_metric_snapshots,
    get_grouped_latest_metrics,
    get_latest_metric_snapshot,
)
from apps.market_data.selectors import (
    get_company_by_ticker,
    get_company_detail_counts,
    get_company_latest_basic_metric_snapshot,
    get_company_latest_financial_period_payload,
    get_company_latest_profile_snapshot,
    get_company_latest_quote_snapshot,
    search_companies,
)


# -----------------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------------

def _company_payload(company) -> dict[str, Any]:
    return {
        "id": str(company.id),
        "ticker": company.ticker,
        "finnhub_symbol": company.finnhub_symbol,
        "name": company.name,
        "country": company.country,
        "currency_code": company.currency_code,
        "exchange": company.exchange,
        "primary_exchange": company.primary_exchange,
        "ipo_date": company.ipo_date.isoformat() if company.ipo_date else None,
        "logo_url": company.logo_url,
        "web_url": company.web_url,
        "industry": company.industry,
        "is_active": company.is_active,
        "created_at": company.created_at.isoformat(),
        "updated_at": company.updated_at.isoformat(),
    }


def _metric_snapshot_payload(snapshot) -> dict[str, Any]:
    if snapshot is None:
        return {
            "metric_code": None,
            "metric_name": None,
            "metric_value": None,
            "unit": None,
            "as_of_date": None,
            "period_type": None,
            "calculation_version": None,
            "notes": None,
        }

    return {
        "metric_code": snapshot.metric_code,
        "metric_name": snapshot.metric_name,
        "metric_value": str(snapshot.metric_value) if snapshot.metric_value is not None else None,
        "unit": snapshot.unit,
        "as_of_date": snapshot.as_of_date.isoformat() if snapshot.as_of_date else None,
        "period_type": snapshot.period_type,
        "calculation_version": snapshot.calculation_version,
        "notes": snapshot.notes,
    }


def _basic_metric_values_preview(snapshot, max_items: int = 20) -> dict[str, Any]:
    if snapshot is None or not snapshot.metric_values:
        return {}
    items = list(snapshot.metric_values.items())[:max_items]
    return {key: value for key, value in items}


def _not_found_payload(kind: str, value: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": "not_found",
            "message": f"{kind} '{value}' was not found.",
        },
    }


# -----------------------------------------------------------------------------
# Tool input schemas
# -----------------------------------------------------------------------------

class CompanyLookupInput(BaseModel):
    query: str = Field(..., description="Ticker, company name, or symbol fragment to search for.")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of companies to return.")


class CompanyTickerInput(BaseModel):
    ticker: str = Field(..., description="Ticker symbol, for example AAPL.")


class ComputedMetricsInput(BaseModel):
    ticker: str = Field(..., description="Ticker symbol, for example AAPL.")
    metric_codes: list[str] = Field(
        default_factory=list,
        description="Optional list of metric codes to fetch. Empty means use latest available metrics."
    )
    latest_only: bool = Field(
        default=True,
        description="If true, return only the latest snapshot per metric code."
    )
    period_type: str | None = Field(
        default=None,
        description="Optional period type filter: annual or quarterly."
    )
    limit: int = Field(default=50, ge=1, le=200, description="Maximum number of metric rows to return.")


class CompareCompaniesInput(BaseModel):
    tickers: list[str] = Field(
        ...,
        min_length=2,
        max_length=20,
        description="List of company tickers to compare."
    )
    metric_codes: list[str] = Field(
        default_factory=list,
        description="Optional list of metric codes to compare. Empty uses default comparison metrics."
    )
    period_type: str | None = Field(
        default=None,
        description="Optional period type filter: annual or quarterly."
    )


# -----------------------------------------------------------------------------
# Default metric groups
# -----------------------------------------------------------------------------

VALUATION_METRIC_CODES = [
    "valuation_market_cap_estimate",
    "valuation_enterprise_value_estimate",
    "valuation_price_to_earnings",
    "valuation_price_to_book",
    "valuation_price_to_sales",
    "valuation_ev_to_sales",
    "valuation_ev_to_fcf",
]

GROWTH_METRIC_CODES = [
    "growth_revenue_yoy",
    "growth_gross_profit_yoy",
    "growth_net_income_yoy",
    "growth_cfo_yoy",
    "growth_fcf_yoy",
    "trend_revenue_growth_positive",
    "trend_profitability_improving",
]

RISK_METRIC_CODES = [
    "risk_negative_net_income_flag",
    "risk_negative_cfo_flag",
    "risk_high_leverage_flag",
    "risk_low_liquidity_flag",
    "risk_margin_compression_flag",
    "risk_revenue_decline_flag",
    "summary_quality_score",
]

DEFAULT_COMPARE_METRIC_CODES = [
    "profitability_net_margin",
    "growth_revenue_yoy",
    "liquidity_current_ratio",
    "leverage_debt_to_equity",
    "cashflow_fcf_margin",
    "valuation_price_to_earnings",
    "summary_quality_score",
]


# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------

@tool("company_lookup_tool", args_schema=CompanyLookupInput)
def company_lookup_tool(query: str, limit: int = 10) -> dict[str, Any]:
    """
    Search stored companies by ticker, company name, or Finnhub symbol.

    Use this when the user provides an ambiguous name or partial ticker and you
    need a grounded company match from the local database.
    """
    companies = search_companies(query=query.strip(), limit=limit)
    return {
        "ok": True,
        "query": query,
        "count": len(companies),
        "results": [_company_payload(company) for company in companies],
    }


@tool("get_company_overview_tool", args_schema=CompanyTickerInput)
def get_company_overview_tool(ticker: str) -> dict[str, Any]:
    """
    Return a structured overview of one company from stored company, snapshot,
    and normalized-period metadata.

    Use this to give the agent a compact factual overview before deeper metric
    analysis.
    """
    normalized_ticker = ticker.strip().upper()
    company = get_company_by_ticker(normalized_ticker)
    if company is None:
        return _not_found_payload("Company", normalized_ticker)

    latest_profile = get_company_latest_profile_snapshot(company)
    latest_quote = get_company_latest_quote_snapshot(company)
    latest_basic = get_company_latest_basic_metric_snapshot(company)
    latest_period = get_company_latest_financial_period_payload(company)

    return {
        "ok": True,
        "company": _company_payload(company),
        "latest_profile": {
            "fetched_at": latest_profile.fetched_at.isoformat() if latest_profile else None,
            "market_capitalization": str(latest_profile.market_capitalization) if latest_profile and latest_profile.market_capitalization is not None else None,
            "share_outstanding": str(latest_profile.share_outstanding) if latest_profile and latest_profile.share_outstanding is not None else None,
            "industry": latest_profile.industry if latest_profile else None,
            "country": latest_profile.country if latest_profile else None,
            "exchange": latest_profile.exchange if latest_profile else None,
            "web_url": latest_profile.web_url if latest_profile else None,
        },
        "latest_quote": {
            "fetched_at": latest_quote.fetched_at.isoformat() if latest_quote else None,
            "current_price": str(latest_quote.current_price) if latest_quote and latest_quote.current_price is not None else None,
            "change": str(latest_quote.change) if latest_quote and latest_quote.change is not None else None,
            "percent_change": str(latest_quote.percent_change) if latest_quote and latest_quote.percent_change is not None else None,
            "quote_timestamp": latest_quote.quote_timestamp.isoformat() if latest_quote and latest_quote.quote_timestamp else None,
        },
        "latest_basic_metrics_preview": _basic_metric_values_preview(latest_basic),
        "counts": get_company_detail_counts(company),
        "latest_financial_period": latest_period,
    }


@tool("get_computed_metrics_tool", args_schema=ComputedMetricsInput)
def get_computed_metrics_tool(
    ticker: str,
    metric_codes: list[str] | None = None,
    latest_only: bool = True,
    period_type: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Return stored computed financial metrics for one company.

    This tool reads only from ComputedMetricSnapshot and does not recalculate
    any values. Use it whenever the agent needs grounded financial indicators.
    """
    normalized_ticker = ticker.strip().upper()
    company = get_company_by_ticker(normalized_ticker)
    if company is None:
        return _not_found_payload("Company", normalized_ticker)

    metric_codes = metric_codes or []
    snapshots = get_company_metric_snapshots(
        company=company,
        metric_codes=metric_codes,
        latest_only=latest_only,
        period_type=period_type,
        limit=limit,
    )

    return {
        "ok": True,
        "company": _company_payload(company),
        "query": {
            "metric_codes": metric_codes,
            "latest_only": latest_only,
            "period_type": period_type,
            "limit": limit,
        },
        "count": len(snapshots),
        "results": [_metric_snapshot_payload(snapshot) for snapshot in snapshots],
    }


@tool("get_valuation_summary_tool", args_schema=CompanyTickerInput)
def get_valuation_summary_tool(ticker: str) -> dict[str, Any]:
    """
    Return the latest stored valuation-related metrics for one company.

    This tool does not compute valuation. It only reads stored valuation-style
    metrics from ComputedMetricSnapshot.
    """
    normalized_ticker = ticker.strip().upper()
    company = get_company_by_ticker(normalized_ticker)
    if company is None:
        return _not_found_payload("Company", normalized_ticker)

    metrics = get_grouped_latest_metrics(company=company, metric_codes=VALUATION_METRIC_CODES)

    return {
        "ok": True,
        "company": _company_payload(company),
        "metric_group": "valuation_summary",
        "results": metrics,
    }


@tool("get_growth_summary_tool", args_schema=CompanyTickerInput)
def get_growth_summary_tool(ticker: str) -> dict[str, Any]:
    """
    Return the latest stored growth and trend metrics for one company.

    This tool reads existing computed growth outputs and trend signals without
    recalculating them.
    """
    normalized_ticker = ticker.strip().upper()
    company = get_company_by_ticker(normalized_ticker)
    if company is None:
        return _not_found_payload("Company", normalized_ticker)

    metrics = get_grouped_latest_metrics(company=company, metric_codes=GROWTH_METRIC_CODES)

    return {
        "ok": True,
        "company": _company_payload(company),
        "metric_group": "growth_summary",
        "results": metrics,
    }


@tool("get_risk_flags_tool", args_schema=CompanyTickerInput)
def get_risk_flags_tool(ticker: str) -> dict[str, Any]:
    """
    Return the latest stored risk flags and quality score for one company.

    Risk flags are deterministic values already stored in ComputedMetricSnapshot.
    """
    normalized_ticker = ticker.strip().upper()
    company = get_company_by_ticker(normalized_ticker)
    if company is None:
        return _not_found_payload("Company", normalized_ticker)

    metrics = get_grouped_latest_metrics(company=company, metric_codes=RISK_METRIC_CODES)

    return {
        "ok": True,
        "company": _company_payload(company),
        "metric_group": "risk_flags",
        "results": metrics,
    }


@tool("compare_companies_tool", args_schema=CompareCompaniesInput)
def compare_companies_tool(
    tickers: list[str],
    metric_codes: list[str] | None = None,
    period_type: str | None = None,
) -> dict[str, Any]:
    """
    Compare multiple companies using the latest stored computed metrics.

    This tool is for structured comparison across companies and uses only stored
    metric snapshots. It does not ingest data and does not recompute analytics.
    """
    normalized_tickers = []
    seen = set()
    for item in tickers:
        ticker = item.strip().upper()
        if ticker and ticker not in seen:
            normalized_tickers.append(ticker)
            seen.add(ticker)

    metric_codes = metric_codes or DEFAULT_COMPARE_METRIC_CODES

    results = []
    missing = []

    for ticker in normalized_tickers:
        company = get_company_by_ticker(ticker)
        if company is None:
            missing.append(ticker)
            continue

        row_metrics = get_grouped_latest_metrics(
            company=company,
            metric_codes=metric_codes,
            period_type=period_type,
        )

        results.append(
            {
                "company": _company_payload(company),
                "metrics": row_metrics,
            }
        )

    return {
        "ok": True,
        "requested_tickers": normalized_tickers,
        "missing_tickers": missing,
        "metric_codes": metric_codes,
        "period_type": period_type,
        "results": results,
    }


# -----------------------------------------------------------------------------
# Registry helper for LangGraph / agent assembly
# -----------------------------------------------------------------------------

def get_financial_tools():
    """
    Return the complete financial tool registry for LangChain / LangGraph use.
    """
    return [
        company_lookup_tool,
        get_company_overview_tool,
        get_computed_metrics_tool,
        get_valuation_summary_tool,
        get_growth_summary_tool,
        get_risk_flags_tool,
        compare_companies_tool,
    ]