from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from langchain_core.tools import tool

from apps.analytics.product_services import SmartAnalysisService


class CompanyTickerInput(BaseModel):
    ticker: str = Field(..., description="Ticker symbol, for example AAPL.")


class PeerRankingInput(BaseModel):
    tickers: list[str] = Field(..., description="List of tickers to rank.")
    metric_codes: list[str] = Field(default_factory=list, description="Optional metric codes for ranking.")


class ScenarioInput(BaseModel):
    ticker: str = Field(..., description="Ticker symbol.")
    years: int = Field(default=3, ge=1, le=10, description="Projection horizon in years.")


@tool("get_analysis_summary_tool", args_schema=CompanyTickerInput)
def get_analysis_summary_tool(ticker: str) -> dict[str, Any]:
    """
    Return a deterministic company analysis summary built from stored metrics
    and normalized statements.
    """
    try:
        payload = SmartAnalysisService().build_company_analysis_summary(ticker)
        return {"ok": True, "data": payload}
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "code": "analysis_summary_error",
                "message": str(exc),
            },
        }


@tool("get_peer_ranking_tool", args_schema=PeerRankingInput)
def get_peer_ranking_tool(tickers: list[str], metric_codes: list[str] | None = None) -> dict[str, Any]:
    """
    Rank peer companies across deterministic stored metrics.
    """
    try:
        payload = SmartAnalysisService().build_peer_ranking(tickers, metric_codes=metric_codes or [])
        return {"ok": True, "data": payload}
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "code": "peer_ranking_error",
                "message": str(exc),
            },
        }


@tool("get_scenario_analysis_tool", args_schema=ScenarioInput)
def get_scenario_analysis_tool(ticker: str, years: int = 3) -> dict[str, Any]:
    """
    Return deterministic bull/base/bear style scenario analysis using only
    stored statements and stored computed metrics.
    """
    try:
        payload = SmartAnalysisService().build_scenario_analysis(ticker=ticker, years=years)
        return {"ok": True, "data": payload}
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "code": "scenario_analysis_error",
                "message": str(exc),
            },
        }