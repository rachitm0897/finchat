from __future__ import annotations

import re
from typing import Any


class SessionMemoryService:
    PRONOUN_PATTERN = re.compile(r"\b(it|that company|that stock|the company|the stock)\b", re.IGNORECASE)

    def resolve_companies(
        self,
        *,
        query: str,
        planned_companies: list[str],
        session_context: dict[str, Any] | None,
    ) -> list[str]:
        companies = list(planned_companies or [])
        context = session_context or {}
        memory = context.get("memory") or {}
        last_companies = memory.get("last_companies_used") or []

        if companies:
            return companies

        if self.PRONOUN_PATTERN.search(query) and last_companies:
            return list(last_companies)

        return []

    def build_memory_update(
        self,
        *,
        existing_context: dict[str, Any] | None,
        resolved_companies: list[str],
        metric_codes_used: list[str],
        intent: str | None,
        analysis_modes: list[str] | None,
        query: str,
    ) -> dict[str, Any]:
        context = dict(existing_context or {})
        context["memory"] = {
            "last_companies_used": resolved_companies,
            "last_metric_codes_used": metric_codes_used,
            "last_intent": intent,
            "last_analysis_modes": analysis_modes or [],
            "last_user_query": query,
        }
        return context