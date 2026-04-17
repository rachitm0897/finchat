from __future__ import annotations


def company_metrics_key(ticker: str, period_type: str = "annual") -> str:
    return f"finchat:metrics:{ticker.strip().upper()}:{period_type}"


def valuation_key(
    ticker: str,
    years_stage_1: int,
    years_stage_2: int,
    growth_stage_1: str,
    growth_stage_2: str,
    terminal_growth: str,
    wacc: str,
) -> str:
    return (
        "finchat:valuation:"
        f"{ticker.strip().upper()}:"
        f"{years_stage_1}:{years_stage_2}:{growth_stage_1}:{growth_stage_2}:{terminal_growth}:{wacc}"
    )


def analysis_summary_key(ticker: str) -> str:
    return f"finchat:analysis-summary:{ticker.strip().upper()}"


def tool_latency_key(tool_name: str) -> str:
    return f"finchat:obs:tool:latency:{tool_name}"


def tool_success_key(tool_name: str) -> str:
    return f"finchat:obs:tool:success:{tool_name}"


def tool_failure_key(tool_name: str) -> str:
    return f"finchat:obs:tool:failure:{tool_name}"


def intent_count_key(intent: str) -> str:
    return f"finchat:obs:intent:{intent}"