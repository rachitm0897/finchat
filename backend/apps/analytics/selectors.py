from __future__ import annotations

from django.db.models import F, Window
from django.db.models.functions import RowNumber

from apps.analytics.models import ComputedMetricSnapshot
from apps.market_data.models import Company


def get_latest_metric_snapshot(
    company: Company,
    metric_code: str,
    period_type: str | None = None,
) -> ComputedMetricSnapshot | None:
    queryset = ComputedMetricSnapshot.objects.filter(company=company, metric_code=metric_code)
    if period_type:
        queryset = queryset.filter(period_type=period_type)
    return queryset.select_related("period").order_by("-as_of_date", "-created_at").first()


def get_latest_metric_value(company: Company, metric_code: str, period_type: str | None = None):
    snapshot = get_latest_metric_snapshot(company=company, metric_code=metric_code, period_type=period_type)
    return snapshot.metric_value if snapshot else None


def get_company_metric_snapshots(
    company: Company,
    metric_codes: list[str] | None = None,
    latest_only: bool = True,
    period_type: str | None = None,
    limit: int = 100,
):
    queryset = ComputedMetricSnapshot.objects.filter(company=company).select_related("period")

    if metric_codes:
        queryset = queryset.filter(metric_code__in=metric_codes)

    if period_type:
        queryset = queryset.filter(period_type=period_type)

    if not latest_only:
        return list(queryset.order_by("metric_code", "-as_of_date", "-created_at")[:limit])

    ranked = queryset.annotate(
        row_num=Window(
            expression=RowNumber(),
            partition_by=[F("metric_code")],
            order_by=[F("as_of_date").desc(), F("created_at").desc()],
        )
    ).filter(row_num=1).order_by("metric_code")

    return list(ranked[:limit])


def get_latest_metrics_map(
    company: Company,
    metric_codes: list[str],
    period_type: str | None = None,
) -> dict[str, ComputedMetricSnapshot | None]:
    rows = get_company_metric_snapshots(
        company=company,
        metric_codes=metric_codes,
        latest_only=True,
        period_type=period_type,
        limit=max(len(metric_codes), 1),
    )
    found = {row.metric_code: row for row in rows}
    return {metric_code: found.get(metric_code) for metric_code in metric_codes}


def get_metric_history(
    company: Company,
    metric_code: str,
    period_type: str | None = None,
    limit: int = 20,
):
    queryset = ComputedMetricSnapshot.objects.filter(
        company=company,
        metric_code=metric_code,
    ).select_related("period")

    if period_type:
        queryset = queryset.filter(period_type=period_type)

    return list(queryset.order_by("-as_of_date", "-created_at")[:limit])


def get_grouped_latest_metrics(
    company: Company,
    metric_codes: list[str],
    period_type: str | None = None,
) -> list[dict]:
    snapshots = get_latest_metrics_map(company=company, metric_codes=metric_codes, period_type=period_type)
    results = []

    for code in metric_codes:
        snap = snapshots.get(code)
        if snap is None:
            results.append(
                {
                    "metric_code": code,
                    "metric_name": code,
                    "metric_value": None,
                    "unit": "",
                    "as_of_date": None,
                    "period_type": None,
                    "calculation_version": None,
                    "notes": "",
                }
            )
        else:
            results.append(
                {
                    "metric_code": snap.metric_code,
                    "metric_name": snap.metric_name,
                    "metric_value": snap.metric_value,
                    "unit": snap.unit,
                    "as_of_date": snap.as_of_date,
                    "period_type": snap.period_type,
                    "calculation_version": snap.calculation_version,
                    "notes": snap.notes,
                }
            )

    return results