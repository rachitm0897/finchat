from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings

from apps.core.observability import ObservabilityService, timed_tool_execution

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langgraph.graph import END, START, StateGraph
    from langchain_openai import ChatOpenAI
except Exception:
    HumanMessage = None
    SystemMessage = None
    StateGraph = None
    START = None
    END = None
    ChatOpenAI = None

from apps.ai_assistant.advanced_tools import (
    get_analysis_summary_tool,
    get_peer_ranking_tool,
    get_scenario_analysis_tool,
)
from apps.ai_assistant.domain_services import (
    AnalyticsReadService,
    BacktestBridgeService,
    ExplainabilityService,
    PeerBenchmarkService,
    PortfolioAnalysisService,
    RiskDetectionService,
    SessionMemoryService,
)
from apps.ai_assistant.prompts import PLANNER_SYSTEM_PROMPT
from apps.ai_assistant.schemas import FinancialAssistantState, PlannerOutput
from apps.ai_assistant.tools import (
    compare_companies_tool,
    company_lookup_tool,
    get_company_overview_tool,
    get_computed_metrics_tool,
    get_growth_summary_tool,
    get_risk_flags_tool,
    get_valuation_summary_tool,
)
from apps.market_data.selectors import get_company_by_ticker

TOOL_REGISTRY = {
    "company_lookup_tool": company_lookup_tool,
    "get_company_overview_tool": get_company_overview_tool,
    "get_computed_metrics_tool": get_computed_metrics_tool,
    "get_valuation_summary_tool": get_valuation_summary_tool,
    "get_growth_summary_tool": get_growth_summary_tool,
    "get_risk_flags_tool": get_risk_flags_tool,
    "compare_companies_tool": compare_companies_tool,
    "get_analysis_summary_tool": get_analysis_summary_tool,
    "get_peer_ranking_tool": get_peer_ranking_tool,
    "get_scenario_analysis_tool": get_scenario_analysis_tool,
}

VALUATION_DETAIL_METRICS = [
    "valuation_price_to_earnings",
    "valuation_price_to_book",
    "valuation_price_to_sales",
    "valuation_ev_to_sales",
    "valuation_ev_to_fcf",
    "summary_quality_score",
]

GROWTH_DETAIL_METRICS = [
    "growth_revenue_yoy",
    "growth_gross_profit_yoy",
    "growth_net_income_yoy",
    "growth_cfo_yoy",
    "growth_fcf_yoy",
    "trend_revenue_growth_positive",
]

RISK_DETAIL_METRICS = [
    "risk_negative_net_income_flag",
    "risk_negative_cfo_flag",
    "risk_high_leverage_flag",
    "risk_low_liquidity_flag",
    "risk_margin_compression_flag",
    "risk_revenue_decline_flag",
    "leverage_debt_to_equity",
    "liquidity_current_ratio",
    "cashflow_fcf_margin",
    "summary_quality_score",
]

GENERAL_DETAIL_METRICS = [
    "valuation_price_to_earnings",
    "growth_revenue_yoy",
    "profitability_net_margin",
    "leverage_debt_to_equity",
    "cashflow_fcf_margin",
    "summary_quality_score",
]

COMPARE_DEFAULT_METRICS = [
    "profitability_net_margin",
    "growth_revenue_yoy",
    "leverage_debt_to_equity",
    "cashflow_fcf_margin",
    "valuation_price_to_earnings",
    "summary_quality_score",
]


def _format_chat_history(chat_history: list[dict[str, str]] | None) -> str:
    if not chat_history:
        return "No prior chat history."
    return "\n".join(f"{row.get('role', 'unknown')}: {row.get('content', '')}" for row in chat_history[-8:])


def _get_provider() -> str:
    return (getattr(settings, "LLM_PROVIDER", "") or os.getenv("LLM_PROVIDER", "openai")).strip().lower()


@lru_cache(maxsize=1)
def get_chat_model():
    if ChatOpenAI is None:
        raise ValueError(
            "langchain_openai / langgraph dependencies are not installed correctly."
        )

    provider = _get_provider()
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

    return ChatOpenAI(model=model_name, api_key=api_key, temperature=0)


def heuristic_plan(query: str, chat_history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    lower = query.lower()

    intent = "general_analysis"
    analysis_modes: list[str] = []
    needs_comparison = False

    if any(token in lower for token in ["backtest", "moving average", "ma crossover", "strategy test"]):
        intent = "backtesting"
    elif any(token in lower for token in ["portfolio", "basket", "holdings"]):
        intent = "portfolio_analysis"
    elif any(token in lower for token in ["compare", "vs", "versus", "better than", "rank"]):
        intent = "comparison"
        needs_comparison = True
    elif any(token in lower for token in ["strength", "weakness", "pros and cons"]):
        intent = "strength_weakness"
    elif any(token in lower for token in ["valuation", "cheap", "expensive", "multiple", "p/e", "ev"]):
        intent = "valuation"
    elif any(token in lower for token in ["growth", "growing", "yoy", "trend", "expansion"]):
        intent = "growth"
    elif any(token in lower for token in ["risk", "risky", "red flag", "leverage", "liquidity", "downside"]):
        intent = "risk"

    if "valuation" in lower or intent == "valuation":
        analysis_modes.append("valuation")
    if "growth" in lower or intent == "growth":
        analysis_modes.append("growth")
    if "risk" in lower or intent == "risk" or "weakness" in lower:
        analysis_modes.append("risk")

    uppercase_tickers = re.findall(r"\b[A-Z]{1,6}\b", query)
    stopwords = {"I", "A", "AN", "THE", "AND", "OR", "OF", "TO", "IN", "ON", "FOR", "VS"}
    companies = [token for token in uppercase_tickers if token not in stopwords]

    if not companies and chat_history:
        joined = " ".join(row.get("content", "") for row in chat_history[-6:])
        companies = [token for token in re.findall(r"\b[A-Z]{1,6}\b", joined) if token not in stopwords]

    return {
        "intent": intent,
        "companies": companies,
        "needs_comparison": needs_comparison or len(companies) > 1,
        "analysis_modes": list(dict.fromkeys(analysis_modes)),
        "requested_metric_codes": [],
        "notes": "Heuristic fallback planner output.",
    }


def classify_query_node(state: FinancialAssistantState) -> dict[str, Any]:
    query = state["user_query"]
    chat_history = state.get("chat_history", [])
    model = get_chat_model()
    planner = model.with_structured_output(PlannerOutput)

    try:
        result = planner.invoke(
            [
                SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Current user query:\n{query}\n\n"
                        f"Recent chat history:\n{_format_chat_history(chat_history)}"
                    )
                ),
            ]
        )
        planner_output = result.model_dump()
        ObservabilityService().increment_intent(planner_output.get("intent", "unknown"))
    except Exception as exc:
        planner_output = heuristic_plan(query, chat_history=chat_history)
        planner_output["notes"] = f"{planner_output['notes']} Planner fallback used due to: {exc}"

    return {"planner_output": planner_output, "errors": state.get("errors", [])}


def resolve_companies_node(state: FinancialAssistantState) -> dict[str, Any]:
    planner_output = state.get("planner_output", {})
    candidates = planner_output.get("companies", []) or []
    query = state["user_query"]
    session_context = state.get("session_context", {}) or {}
    errors = list(state.get("errors", []))

    resolved_candidates = SessionMemoryService().resolve_companies(
        query=query,
        planned_companies=candidates,
        session_context=session_context,
    )

    resolved: list[str] = []
    lookup_results: dict[str, Any] = {}

    def add_lookup(candidate: str):
        result = company_lookup_tool.invoke({"query": candidate, "limit": 5})
        lookup_results[candidate] = result
        if result.get("ok") and result.get("results"):
            top = result["results"][0]
            ticker = top.get("ticker")
            if ticker and ticker not in resolved:
                resolved.append(ticker)

    for candidate in resolved_candidates:
        add_lookup(candidate)

    if not resolved:
        fallback = company_lookup_tool.invoke({"query": query, "limit": 5})
        lookup_results["__fallback__"] = fallback
        if fallback.get("ok"):
            for row in fallback.get("results", [])[:5]:
                ticker = row.get("ticker")
                if ticker and ticker not in resolved:
                    resolved.append(ticker)

    if not resolved:
        errors.append("No stored company could be resolved from the query.")

    return {
        "resolved_companies": resolved,
        "company_lookup_results": lookup_results,
        "errors": errors,
    }


def _choose_metric_codes(intent: str, analysis_modes: list[str], explicit_metric_codes: list[str]) -> list[str]:
    if explicit_metric_codes:
        return explicit_metric_codes
    if intent == "valuation":
        return VALUATION_DETAIL_METRICS
    if intent == "growth":
        return GROWTH_DETAIL_METRICS
    if intent == "risk":
        return RISK_DETAIL_METRICS
    if intent in {"comparison", "portfolio_analysis"}:
        return COMPARE_DEFAULT_METRICS
    if intent == "strength_weakness":
        return list(dict.fromkeys(GENERAL_DETAIL_METRICS + GROWTH_DETAIL_METRICS + RISK_DETAIL_METRICS))
    if "valuation" in analysis_modes:
        return list(dict.fromkeys(GENERAL_DETAIL_METRICS + VALUATION_DETAIL_METRICS))
    return GENERAL_DETAIL_METRICS


def build_tool_plan_node(state: FinancialAssistantState) -> dict[str, Any]:
    planner_output = state.get("planner_output", {})
    resolved_companies = state.get("resolved_companies", [])
    query = state["user_query"].lower()

    intent = planner_output.get("intent", "general_analysis")
    analysis_modes = planner_output.get("analysis_modes", []) or []
    requested_metric_codes = planner_output.get("requested_metric_codes", []) or []
    needs_comparison = planner_output.get("needs_comparison", False)

    tool_plan: list[dict[str, Any]] = []

    if not resolved_companies:
        return {"tool_plan": tool_plan}

    wants_scenario = any(token in query for token in ["scenario", "bull", "bear", "upside", "downside", "what if"])

    if intent in {"comparison", "portfolio_analysis"} or needs_comparison or len(resolved_companies) > 1:
        tool_plan.append(
            {
                "tool_name": "compare_companies_tool",
                "args": {
                    "tickers": resolved_companies,
                    "metric_codes": _choose_metric_codes(intent, analysis_modes, requested_metric_codes),
                    "period_type": "annual",
                },
            }
        )
        tool_plan.append(
            {
                "tool_name": "get_peer_ranking_tool",
                "args": {
                    "tickers": resolved_companies,
                    "metric_codes": _choose_metric_codes(intent, analysis_modes, requested_metric_codes),
                },
            }
        )
        return {"tool_plan": tool_plan}

    ticker = resolved_companies[0]
    metric_codes = _choose_metric_codes(intent, analysis_modes, requested_metric_codes)

    tool_plan.append({"tool_name": "get_company_overview_tool", "args": {"ticker": ticker}})
    tool_plan.append({"tool_name": "get_analysis_summary_tool", "args": {"ticker": ticker}})
    tool_plan.append(
        {
            "tool_name": "get_computed_metrics_tool",
            "args": {
                "ticker": ticker,
                "metric_codes": metric_codes,
                "latest_only": True,
                "period_type": "annual",
                "limit": 100,
            },
        }
    )

    if intent == "valuation":
        tool_plan.append({"tool_name": "get_valuation_summary_tool", "args": {"ticker": ticker}})
    if intent == "growth":
        tool_plan.append({"tool_name": "get_growth_summary_tool", "args": {"ticker": ticker}})
    if intent == "risk":
        tool_plan.append({"tool_name": "get_risk_flags_tool", "args": {"ticker": ticker}})
    if intent == "strength_weakness":
        tool_plan.append({"tool_name": "get_growth_summary_tool", "args": {"ticker": ticker}})
        tool_plan.append({"tool_name": "get_risk_flags_tool", "args": {"ticker": ticker}})
        tool_plan.append({"tool_name": "get_valuation_summary_tool", "args": {"ticker": ticker}})
    if wants_scenario:
        tool_plan.append({"tool_name": "get_scenario_analysis_tool", "args": {"ticker": ticker, "years": 3}})

    return {"tool_plan": tool_plan}


def execute_tools_node(state: FinancialAssistantState) -> dict[str, Any]:
    tool_plan = state.get("tool_plan", [])
    tool_results: dict[str, Any] = {}
    errors = list(state.get("errors", []))

    def _run_one(idx: int, step: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        tool_name = step["tool_name"]
        args = step.get("args", {})
        tool = TOOL_REGISTRY[tool_name]

        try:
            with timed_tool_execution(tool_name):
                result = tool.invoke(args)
            return (
                f"{idx}:{tool_name}",
                {
                    "tool_name": tool_name,
                    "args": args,
                    "result": result,
                },
            )
        except Exception as exc:
            return (
                f"{idx}:{tool_name}",
                {
                    "tool_name": tool_name,
                    "args": args,
                    "result": {
                        "ok": False,
                        "error": {
                            "code": "tool_execution_error",
                            "message": str(exc),
                        },
                    },
                    "local_error": f"Tool {tool_name} failed: {exc}",
                },
            )

    max_workers = min(max(len(tool_plan), 1), 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_run_one, idx, step) for idx, step in enumerate(tool_plan)]
        for future in as_completed(futures):
            key, value = future.result()
            if value.get("local_error"):
                errors.append(value["local_error"])
            tool_results[key] = {
                "tool_name": value["tool_name"],
                "args": value["args"],
                "result": value["result"],
            }

    ordered_tool_results = dict(sorted(tool_results.items(), key=lambda item: item[0]))
    return {"tool_results": ordered_tool_results, "errors": errors}


def _result_by_tool_name(tool_results: dict[str, Any], tool_name: str) -> dict[str, Any] | None:
    for row in tool_results.values():
        if row.get("tool_name") == tool_name:
            return row.get("result")
    return None


def build_structured_response_node(state: FinancialAssistantState) -> dict[str, Any]:
    planner_output = state.get("planner_output", {})
    resolved_companies = state.get("resolved_companies", [])
    tool_results = state.get("tool_results", {})
    intent = planner_output.get("intent", "general_analysis")

    explainability = ExplainabilityService()
    analytics_reader = AnalyticsReadService()

    if not resolved_companies:
        payload = explainability.build_structured_response(
            conclusion="No stored company could be resolved from the query.",
            key_metrics={},
            reasoning=["The local company universe could not match the requested company reference."],
            confidence_score=0.25,
        )
        return {"structured_response": payload}

    if intent == "portfolio_analysis" or len(resolved_companies) > 1:
        portfolio_summary = PortfolioAnalysisService().analyze(tickers=resolved_companies)
        payload = explainability.build_structured_response(
            conclusion=explainability.build_conclusion(
                ticker="portfolio",
                metrics={},
                portfolio_summary=portfolio_summary,
            ),
            key_metrics=(portfolio_summary or {}).get("aggregate_metrics", {}),
            reasoning=explainability.build_reasoning(
                metrics={},
                portfolio_summary=portfolio_summary,
            ),
            confidence_score=explainability.compute_confidence(metrics=(portfolio_summary or {}).get("aggregate_metrics", {})),
            portfolio_summary=portfolio_summary,
        )
        return {"structured_response": payload}

    ticker = resolved_companies[0]
    company = get_company_by_ticker(ticker)
    if company is None:
        payload = explainability.build_structured_response(
            conclusion=f"{ticker} could not be loaded from stored company data.",
            key_metrics={},
            reasoning=["The ticker was resolved at planning time but no stored company row was available at response time."],
            confidence_score=0.2,
        )
        return {"structured_response": payload}

    metrics_map = analytics_reader.to_display_numbers(
        analytics_reader.get_metrics_map(
            company=company,
            metric_codes=_choose_metric_codes(
                intent,
                planner_output.get("analysis_modes", []) or [],
                planner_output.get("requested_metric_codes", []) or [],
            ),
        )
    )
    peer_summary = PeerBenchmarkService().compare(company=company)
    risks = RiskDetectionService().detect(company=company)
    backtest_summary = None

    if intent == "backtesting" or any(token in state["user_query"].lower() for token in ["backtest", "moving average", "ma crossover"]):
        backtest_summary = BacktestBridgeService().run_simple_backtest(ticker=ticker)

    payload = explainability.build_structured_response(
        conclusion=explainability.build_conclusion(
            ticker=ticker,
            metrics=metrics_map,
            peer_summary=peer_summary,
            risks=risks,
            backtest_summary=backtest_summary,
        ),
        key_metrics=metrics_map,
        reasoning=explainability.build_reasoning(
            metrics=metrics_map,
            peer_summary=peer_summary,
            risks=risks,
            backtest_summary=backtest_summary,
        ),
        confidence_score=explainability.compute_confidence(
            metrics=metrics_map,
            peer_summary=peer_summary,
            risks=risks,
        ),
        peer_comparison=peer_summary,
        risk_summary=risks,
        backtesting=backtest_summary,
    )
    return {"structured_response": payload}


def generate_grounded_answer_node(state: FinancialAssistantState) -> dict[str, Any]:
    payload = state.get("structured_response", {}) or {}
    final_answer = ExplainabilityService().render_markdown(payload)

    return {
        "final_answer": final_answer,
        "final_payload": {
            "query": state["user_query"],
            "planner_output": state.get("planner_output", {}),
            "resolved_companies": state.get("resolved_companies", []),
            "tool_results": state.get("tool_results", {}),
            "structured_response": payload,
            "errors": state.get("errors", []),
            "answer": final_answer,
        },
    }


@lru_cache(maxsize=1)
def build_financial_assistant_graph():
    graph = StateGraph(FinancialAssistantState)

    graph.add_node("classify_query", classify_query_node)
    graph.add_node("resolve_companies", resolve_companies_node)
    graph.add_node("build_tool_plan", build_tool_plan_node)
    graph.add_node("execute_tools", execute_tools_node)
    graph.add_node("build_structured_response", build_structured_response_node)
    graph.add_node("generate_grounded_answer", generate_grounded_answer_node)

    graph.add_edge(START, "classify_query")
    graph.add_edge("classify_query", "resolve_companies")
    graph.add_edge("resolve_companies", "build_tool_plan")
    graph.add_edge("build_tool_plan", "execute_tools")
    graph.add_edge("execute_tools", "build_structured_response")
    graph.add_edge("build_structured_response", "generate_grounded_answer")
    graph.add_edge("generate_grounded_answer", END)

    return graph.compile()


def run_financial_assistant_graph(
    user_query: str,
    chat_history: list[dict[str, str]] | None = None,
    session_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    app = build_financial_assistant_graph()
    initial_state: FinancialAssistantState = {
        "user_query": user_query,
        "chat_history": chat_history or [],
        "session_context": session_context or {},
        "errors": [],
    }
    return app.invoke(initial_state)