from __future__ import annotations

from django.db.models import Q

from apps.market_data.models import Company


def search_companies(query: str, limit: int = 20):
    queryset = Company.objects.all().order_by("ticker")

    if query:
        normalized = query.strip()
        queryset = queryset.filter(
            Q(ticker__icontains=normalized)
            | Q(name__icontains=normalized)
            | Q(finnhub_symbol__icontains=normalized)
        ).order_by("ticker")

    return list(queryset[:limit])


def get_company_by_ticker(ticker: str) -> Company | None:
    normalized = ticker.strip().upper()
    if not normalized:
        return None

    return (
        Company.objects.filter(ticker=normalized).first()
        or Company.objects.filter(finnhub_symbol=normalized).first()
        or Company.objects.filter(name__iexact=ticker.strip()).first()
    )


def get_company_latest_profile_snapshot(company: Company):
    return company.profile_snapshots.filter(is_latest=True).order_by("-fetched_at").first()


def get_company_latest_quote_snapshot(company: Company):
    return company.quote_snapshots.filter(is_latest=True).order_by("-fetched_at").first()


def get_company_latest_basic_metric_snapshot(company: Company):
    return company.basic_metric_snapshots.filter(is_latest=True).order_by("-fetched_at").first()


def get_company_detail_counts(company: Company) -> dict:
    return {
        "profile_snapshots": company.profile_snapshots.count(),
        "quote_snapshots": company.quote_snapshots.count(),
        "basic_metric_snapshots": company.basic_metric_snapshots.count(),
        "financial_periods": company.financial_periods.count(),
        "income_statements": company.income_statements.count(),
        "balance_sheets": company.balance_sheets.count(),
        "cash_flow_statements": company.cash_flow_statements.count(),
        "computed_metric_snapshots": company.computed_metric_snapshots.count(),
        "valuation_snapshots": company.valuation_snapshots.count(),
        "chat_sessions": company.chat_sessions.count(),
        "job_runs": company.job_runs.count(),
    }


def get_company_latest_financial_period_payload(company: Company) -> dict | None:
    period = company.financial_periods.order_by("-period_end_date").first()
    if not period:
        return None

    return {
        "id": str(period.id),
        "period_type": period.period_type,
        "fiscal_year": period.fiscal_year,
        "fiscal_quarter": period.fiscal_quarter,
        "period_end_date": period.period_end_date,
        "currency_code": period.currency_code,
        "source_name": period.source_name,
        "source_period_key": period.source_period_key,
        "created_at": period.created_at,
        "updated_at": period.updated_at,
    }