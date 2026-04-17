from __future__ import annotations

from typing import Any


class ExplainabilityService:
    def compute_confidence(
        self,
        *,
        metrics: dict[str, Any],
        peer_summary: dict[str, Any] | None = None,
        risks: list[str] | None = None,
    ) -> float:
        present = sum(1 for value in metrics.values() if value is not None)
        total = max(len(metrics), 1)
        score = 0.45 + (present / total) * 0.35

        if peer_summary:
            score += 0.10
        if risks is not None:
            score += 0.10

        return round(min(score, 0.99), 2)

    def build_conclusion(
        self,
        *,
        ticker: str,
        metrics: dict[str, Any],
        peer_summary: dict[str, Any] | None = None,
        risks: list[str] | None = None,
        portfolio_summary: dict[str, Any] | None = None,
        backtest_summary: dict[str, Any] | None = None,
    ) -> str:
        if portfolio_summary:
            return f"The portfolio view for {portfolio_summary.get('company_count', 0)} companies is mixed and should be judged from the aggregate valuation, growth, and leverage profile."

        if backtest_summary:
            if backtest_summary.get("ok"):
                return f"A backtest request for {ticker} was accepted and dispatched."
            return f"A backtest request for {ticker} could not be executed in the current backend setup."

        valuation_relative = (peer_summary or {}).get("valuation_relative")
        if valuation_relative == "cheaper_than_peers":
            return f"{ticker} screens cheaper than its stored peers on current valuation metrics."
        if valuation_relative == "richer_than_peers":
            return f"{ticker} screens richer than its stored peers on current valuation metrics."

        if risks:
            return f"{ticker} has a mixed profile with identifiable financial risk signals."
        return f"{ticker} has a mixed but grounded profile based on stored analytics."

    def build_reasoning(
        self,
        *,
        metrics: dict[str, Any],
        peer_summary: dict[str, Any] | None = None,
        risks: list[str] | None = None,
        portfolio_summary: dict[str, Any] | None = None,
        backtest_summary: dict[str, Any] | None = None,
    ) -> list[str]:
        reasoning: list[str] = []

        pe = metrics.get("valuation_price_to_earnings")
        growth = metrics.get("growth_revenue_yoy")
        margin = metrics.get("profitability_net_margin")
        leverage = metrics.get("leverage_debt_to_equity")
        quality = metrics.get("summary_quality_score")

        if pe is not None:
            reasoning.append(f"Stored P/E is {pe}.")
        if growth is not None:
            reasoning.append(f"Stored revenue growth is {growth}.")
        if margin is not None:
            reasoning.append(f"Stored net margin is {margin}.")
        if leverage is not None:
            reasoning.append(f"Stored debt-to-equity is {leverage}.")
        if quality is not None:
            reasoning.append(f"Stored quality score is {quality}.")

        if peer_summary and peer_summary.get("peer_averages"):
            reasoning.append(
                "Peer benchmarking used stored peer averages for valuation, growth, and profitability."
            )

        if portfolio_summary and portfolio_summary.get("aggregate_metrics"):
            reasoning.append(
                "Portfolio conclusions were computed from aggregate averages across the resolved companies."
            )

        if backtest_summary:
            if backtest_summary.get("ok"):
                reasoning.append("A simple moving-average backtest request was dispatched through the job layer.")
            else:
                reasoning.append(backtest_summary.get("message", "Backtesting was not available."))

        if risks:
            reasoning.append("Risk summary was produced with deterministic risk-flag logic from stored analytics.")

        return reasoning[:6]

    def build_structured_response(
        self,
        *,
        conclusion: str,
        key_metrics: dict[str, Any],
        reasoning: list[str],
        confidence_score: float,
        peer_comparison: dict[str, Any] | None = None,
        portfolio_summary: dict[str, Any] | None = None,
        risk_summary: list[str] | None = None,
        backtesting: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "conclusion": conclusion,
            "key_metrics": key_metrics,
            "reasoning": reasoning,
            "confidence_score": confidence_score,
            "peer_comparison": peer_comparison or {},
            "portfolio": portfolio_summary or {},
            "risk_summary": risk_summary or [],
            "backtesting": backtesting or {},
        }

    def render_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            "Conclusion",
            payload.get("conclusion", "No grounded conclusion available."),
            "",
            "Key metrics used",
        ]

        key_metrics = payload.get("key_metrics", {}) or {}
        if key_metrics:
            for key, value in key_metrics.items():
                lines.append(f"- {key}: {value}")
        else:
            lines.append("- No stored key metrics were available.")

        lines.extend(["", "Reasoning"])
        reasoning = payload.get("reasoning", []) or []
        if reasoning:
            for item in reasoning:
                lines.append(f"- {item}")
        else:
            lines.append("- No grounded reasoning steps were available.")

        lines.extend(["", f"Confidence score: {payload.get('confidence_score', 0)}"])

        peer = payload.get("peer_comparison", {}) or {}
        if peer:
            lines.extend(["", "Peer comparison"])
            for key, value in peer.items():
                if key == "peer_rows":
                    continue
                lines.append(f"- {key}: {value}")

        risks = payload.get("risk_summary", []) or []
        lines.extend(["", "Risk summary"])
        if risks:
            for risk in risks:
                lines.append(f"- {risk}")
        else:
            lines.append("- No explicit risk flags were triggered from stored analytics.")

        portfolio = payload.get("portfolio", {}) or {}
        if portfolio:
            lines.extend(["", "Portfolio insights"])
            for key, value in portfolio.items():
                if key == "companies":
                    continue
                lines.append(f"- {key}: {value}")

        backtesting = payload.get("backtesting", {}) or {}
        if backtesting:
            lines.extend(["", "Backtesting"])
            for key, value in backtesting.items():
                lines.append(f"- {key}: {value}")

        return "\n".join(lines)