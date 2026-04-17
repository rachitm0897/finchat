from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


IntentType = Literal[
    "general_analysis",
    "valuation",
    "growth",
    "risk",
    "comparison",
    "strength_weakness",
    "portfolio_analysis",
    "backtesting",
]


class PlannerOutput(BaseModel):
    intent: IntentType = Field(..., description="Primary financial-analysis intent.")
    companies: list[str] = Field(default_factory=list, description="Candidate company names or tickers extracted from the query.")
    needs_comparison: bool = Field(default=False, description="Whether the query requires multi-company comparison.")
    analysis_modes: list[str] = Field(default_factory=list, description="Relevant analysis dimensions such as valuation, growth, risk.")
    requested_metric_codes: list[str] = Field(default_factory=list, description="Optional explicit metric codes requested or implied by the query.")
    notes: str = Field(default="", description="Short explanation of the plan.")


class FinancialAssistantState(TypedDict, total=False):
    user_query: str
    chat_history: list[dict[str, str]]
    session_context: dict[str, Any]

    planner_output: dict[str, Any]
    resolved_companies: list[str]
    company_lookup_results: dict[str, Any]

    tool_plan: list[dict[str, Any]]
    tool_results: dict[str, Any]
    structured_response: dict[str, Any]

    errors: list[str]
    final_answer: str
    final_payload: dict[str, Any]