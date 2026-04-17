from __future__ import annotations

import json
from typing import Any

from apps.analytics.product_services import SmartAnalysisService
from apps.market_data.models import Company


class CompanyReportExportService:
    """
    Simple export layer for deterministic product reporting.
    Supports JSON and Markdown exports for local demos and frontend download.
    """

    def build_company_report_payload(self, ticker: str) -> dict[str, Any]:
        summary = SmartAnalysisService().build_company_analysis_summary(ticker)
        scenario = SmartAnalysisService().build_scenario_analysis(ticker)
        return {
            "summary": summary,
            "scenario_analysis": scenario,
        }

    def export_json(self, ticker: str) -> str:
        payload = self.build_company_report_payload(ticker)
        return json.dumps(payload, indent=2, default=str)

    def export_markdown(self, ticker: str) -> str:
        payload = self.build_company_report_payload(ticker)
        summary = payload["summary"]
        scenario = payload["scenario_analysis"]

        lines = []
        lines.append(f"# {summary['company']['name']} ({summary['ticker']})")
        lines.append("")
        lines.append("## Company Overview")
        lines.append(f"- Industry: {summary['company'].get('industry') or 'N/A'}")
        lines.append(f"- Country: {summary['company'].get('country') or 'N/A'}")
        lines.append(f"- Currency: {summary['company'].get('currency_code') or 'N/A'}")
        lines.append(f"- Latest period end: {summary['latest_period'].get('period_end_date') or 'N/A'}")
        lines.append("")
        lines.append("## Key Metrics")
        for key, value in summary["key_metrics"].items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append("## Strengths")
        if summary["strengths"]:
            for item in summary["strengths"]:
                lines.append(f"- {item}")
        else:
            lines.append("- No clear strengths flagged.")
        lines.append("")
        lines.append("## Weaknesses")
        if summary["weaknesses"]:
            for item in summary["weaknesses"]:
                lines.append(f"- {item}")
        else:
            lines.append("- No clear weaknesses flagged.")
        lines.append("")
        lines.append("## Risk Flags")
        for key, value in summary["risk_flags"].items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append("## Scenario Analysis")
        for scenario_row in scenario["scenarios"]:
            lines.append(f"### {scenario_row['name'].title()}")
            lines.append(f"- Revenue growth: {scenario_row['revenue_growth']}")
            lines.append(f"- FCF margin: {scenario_row['fcf_margin']}")
            lines.append(f"- Exit multiple: {scenario_row['exit_multiple']}")
            lines.append(f"- Projected revenue: {scenario_row['projected_revenue']}")
            lines.append(f"- Projected FCF: {scenario_row['projected_fcf']}")
            lines.append(f"- Enterprise value: {scenario_row['enterprise_value']}")
            lines.append(f"- Equity value: {scenario_row['equity_value']}")
            lines.append(f"- Implied share price: {scenario_row['implied_share_price']}")
            lines.append("")
        return "\n".join(lines)