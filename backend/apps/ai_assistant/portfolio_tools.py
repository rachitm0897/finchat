from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from apps.ai_assistant.portfolio_actions import PortfolioActionService


class PortfolioActionInput(BaseModel):
    query: str = Field(..., description="Natural-language portfolio instruction.")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of matching companies to return.")


@tool("get_portfolio_actions_tool", args_schema=PortfolioActionInput)
def get_portfolio_actions_tool(query: str, limit: int = 10) -> dict[str, Any]:
    """
    Turn a natural-language portfolio instruction into deterministic portfolio
    screening and ranking actions.
    """
    try:
        payload = PortfolioActionService().execute_action_query(query=query, limit=limit)
        return {"ok": True, "data": payload}
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "code": "portfolio_action_error",
                "message": str(exc),
            },
        }