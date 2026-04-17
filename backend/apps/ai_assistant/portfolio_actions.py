from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any

from django.conf import settings
from pydantic import BaseModel, Field

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None

from apps.analytics.selectors import get_latest_metric_snapshot
from apps.market_data.models import Company


class PortfolioActionPlan(BaseModel):
    objective: str = Field(default="screen")
    tickers: list[str] = Field(default_factory=list)
    filters: dict[str, str | float | int | None] = Field(default_factory=dict)
    ranking_metric: str = Field(default="summary_quality_score")
    notes: str = Field(default="")


def _provider() -> str:
    return (getattr(settings, "LLM_PROVIDER", "") or os.getenv("LLM_PROVIDER", "openai")).strip().lower()


@lru_cache(maxsize=1)
def _chat_model():
    if ChatOpenAI is None:
        raise ValueError("langchain_openai is not installed correctly.")

    provider = _provider()
    model_name = (getattr(settings, "LLM_MODEL_NAME", "") or os.getenv("LLM_MODEL_NAME", "")).strip()

    if not model_name:
        raise ValueError("LLM_MODEL_NAME is not configured.")

    if provider == "openrouter":
        api_key = (
            getattr(settings, "LLM_API_KEY", "")
            or os.getenv("OPENROUTER_API_KEY", "")
            or os.getenv("LLM_API_KEY", "")
        )
        if not api_key:
            raise ValueError("LLM_API_KEY or OPENROUTER_API_KEY is not configured.")

        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            temperature=0,
        )

    api_key = (
        os.getenv("OPENAI_API_KEY", "")
        or getattr(settings, "LLM_API_KEY", "")
        or os.getenv("LLM_API_KEY", "")
    )
    if not api_key:
        raise ValueError("OPENAI_API_KEY or LLM_API_KEY is not configured.")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        temperature=0,
    )


class PortfolioActionService:
    """
    Convert a natural-language portfolio query into deterministic screening
    and ranking actions over stored computed metrics.
    """

    DEFAULT_LIMIT = 20

    def parse_action_query(self, query: str) -> PortfolioActionPlan:
        query = query.strip()
        if not query:
            raise ValueError("Query must not be empty.")

        try:
            planner = _chat_model().with_structured_output(PortfolioActionPlan)
            result = planner.invoke(
                f"""
Interpret this portfolio instruction into a structured screening action.

Query:
{query}

Allowed ranking metrics:
- summary_quality_score
- growth_revenue_yoy
- profitability_net_margin
- cashflow_fcf_margin
- valuation_price_to_earnings
- leverage_debt_to_equity
- liquidity_current_ratio

Allowed filters:
- min_quality_score
- min_revenue_growth
- min_net_margin
- min_fcf_margin
- max_debt_to_equity
- min_current_ratio
- max_price_to_earnings
"""
            )
            return result
        except Exception:
            return self._heuristic_plan(query)

    def _heuristic_plan(self, query: str) -> PortfolioActionPlan:
        q = query.lower()

        filters: dict[str, Any] = {}
        ranking_metric = "summary_quality_score"
        objective = "screen"

        if "growth" in q:
            filters["min_revenue_growth"] = 0.05
            ranking_metric = "growth_revenue_yoy"

        if "quality" in q:
            filters["min_quality_score"] = 60
            ranking_metric = "summary_quality_score"

        if "low debt" in q or "less debt" in q:
            filters["max_debt_to_equity"] = 1.0

        if "cheap" in q or "undervalued" in q:
            filters["max_price_to_earnings"] = 25
            ranking_metric = "valuation_price_to_earnings"

        if "cash flow" in q or "fcf" in q:
            filters["min_fcf_margin"] = 0.05
            ranking_metric = "cashflow_fcf_margin"

        tickers = [x for x in re.findall(r"\b[A-Z]{1,6}\b", query) if x not in {"I", "A", "AN", "THE"}]

        return PortfolioActionPlan(
            objective=objective,
            tickers=tickers,
            filters=filters,
            ranking_metric=ranking_metric,
            notes="Heuristic parser fallback.",
        )

    def execute_action_query(self, query: str, limit: int = 20) -> dict[str, Any]:
        plan = self.parse_action_query(query)

        companies = Company.objects.all().order_by("ticker")
        if plan.tickers:
            companies = companies.filter(ticker__in=plan.tickers)

        rows = []
        for company in companies:
            quality = self._metric_value(company, "summary_quality_score")
            revenue_growth = self._metric_value(company, "growth_revenue_yoy")
            net_margin = self._metric_value(company, "profitability_net_margin")
            fcf_margin = self._metric_value(company, "cashflow_fcf_margin")
            debt_to_equity = self._metric_value(company, "leverage_debt_to_equity")
            current_ratio = self._metric_value(company, "liquidity_current_ratio")
            pe_ratio = self._metric_value(company, "valuation_price_to_earnings")

            if not self._passes_filters(
                quality=quality,
                revenue_growth=revenue_growth,
                net_margin=net_margin,
                fcf_margin=fcf_margin,
                debt_to_equity=debt_to_equity,
                current_ratio=current_ratio,
                pe_ratio=pe_ratio,
                filters=plan.filters,
            ):
                continue

            rows.append(
                {
                    "ticker": company.ticker,
                    "company_name": company.name,
                    "summary_quality_score": quality,
                    "growth_revenue_yoy": revenue_growth,
                    "profitability_net_margin": net_margin,
                    "cashflow_fcf_margin": fcf_margin,
                    "leverage_debt_to_equity": debt_to_equity,
                    "liquidity_current_ratio": current_ratio,
                    "valuation_price_to_earnings": pe_ratio,
                }
            )

        ranking_metric = plan.ranking_metric or "summary_quality_score"
        reverse = ranking_metric not in {"valuation_price_to_earnings", "leverage_debt_to_equity"}
        rows.sort(
            key=lambda row: row.get(ranking_metric) if row.get(ranking_metric) is not None else (-999999 if reverse else 999999),
            reverse=reverse,
        )

        output = []
        for idx, row in enumerate(rows[:limit], start=1):
            output.append(
                {
                    "rank": idx,
                    "ticker": row["ticker"],
                    "company_name": row["company_name"],
                    "ranking_metric": ranking_metric,
                    "ranking_metric_value": row.get(ranking_metric),
                    "metrics": {
                        k: (str(v) if v is not None else None)
                        for k, v in row.items()
                        if k not in {"ticker", "company_name"}
                    },
                }
            )

        return {
            "query": query,
            "action_plan": plan.model_dump(),
            "count": len(output),
            "results": output,
        }

    def _metric_value(self, company: Company, metric_code: str) -> float | None:
        snap = get_latest_metric_snapshot(company=company, metric_code=metric_code, period_type="annual")
        if not snap or snap.metric_value is None:
            return None
        try:
            return float(snap.metric_value)
        except Exception:
            return None

    def _passes_filters(
        self,
        *,
        quality: float | None,
        revenue_growth: float | None,
        net_margin: float | None,
        fcf_margin: float | None,
        debt_to_equity: float | None,
        current_ratio: float | None,
        pe_ratio: float | None,
        filters: dict[str, Any],
    ) -> bool:
        if "min_quality_score" in filters and (quality is None or quality < float(filters["min_quality_score"])):
            return False
        if "min_revenue_growth" in filters and (revenue_growth is None or revenue_growth < float(filters["min_revenue_growth"])):
            return False
        if "min_net_margin" in filters and (net_margin is None or net_margin < float(filters["min_net_margin"])):
            return False
        if "min_fcf_margin" in filters and (fcf_margin is None or fcf_margin < float(filters["min_fcf_margin"])):
            return False
        if "max_debt_to_equity" in filters and (debt_to_equity is None or debt_to_equity > float(filters["max_debt_to_equity"])):
            return False
        if "min_current_ratio" in filters and (current_ratio is None or current_ratio < float(filters["min_current_ratio"])):
            return False
        if "max_price_to_earnings" in filters and (pe_ratio is None or pe_ratio > float(filters["max_price_to_earnings"])):
            return False
        return True