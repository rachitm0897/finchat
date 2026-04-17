from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.analytics.selectors import get_latest_metric_snapshot
from apps.market_data.models import Company
from apps.core.cache_keys import valuation_key
from apps.core.cache_utils import CacheService

def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


class DCFValuationService:
    """
    Deterministic multi-stage DCF-style valuation using:
    - latest stored revenue
    - stored FCF margin
    - explicit WACC
    - multi-stage growth assumptions
    """

    def build_dcf(
        self,
        ticker: str,
        years_stage_1: int = 5,
        years_stage_2: int = 5,
        growth_stage_1: str = "0.10",
        growth_stage_2: str = "0.05",
        terminal_growth: str = "0.03",
        wacc: str = "0.10",
    ) -> dict[str, Any]:
        normalized_ticker = ticker.strip().upper()
        cache_key = valuation_key(
            normalized_ticker,
            years_stage_1,
            years_stage_2,
            growth_stage_1,
            growth_stage_2,
            terminal_growth,
            wacc,
        )

        def _builder() -> dict[str, Any]:
            company = Company.objects.filter(ticker=normalized_ticker).first()
            if company is None:
                raise ValueError(f"Company '{ticker}' not found.")

            latest_income = company.income_statements.select_related("period").order_by("-period__period_end_date").first()
            latest_balance = company.balance_sheets.select_related("period").order_by("-period__period_end_date").first()

            if latest_income is None:
                raise ValueError("Latest income statement unavailable for DCF.")

            revenue = _to_decimal(latest_income.revenue)
            diluted_shares = _to_decimal(latest_income.weighted_average_diluted_shares)

            if revenue is None:
                raise ValueError("Latest revenue unavailable for DCF.")
            if diluted_shares is None or diluted_shares == 0:
                raise ValueError("Diluted shares unavailable for DCF.")

            fcf_margin_snap = get_latest_metric_snapshot(
                company=company,
                metric_code="cashflow_fcf_margin",
                period_type="annual",
            )
            fcf_margin = _to_decimal(fcf_margin_snap.metric_value if fcf_margin_snap else None)
            if fcf_margin is None:
                raise ValueError("Stored FCF margin unavailable for DCF.")

            cash = _to_decimal(getattr(latest_balance, "cash_and_cash_equivalents", None) if latest_balance else None) or Decimal("0")
            short_term_investments = _to_decimal(getattr(latest_balance, "short_term_investments", None) if latest_balance else None) or Decimal("0")
            short_term_debt = _to_decimal(getattr(latest_balance, "short_term_debt", None) if latest_balance else None) or Decimal("0")
            long_term_debt = _to_decimal(getattr(latest_balance, "long_term_debt", None) if latest_balance else None) or Decimal("0")

            net_cash = (cash + short_term_investments) - (short_term_debt + long_term_debt)

            g1 = _to_decimal(growth_stage_1) or Decimal("0.10")
            g2 = _to_decimal(growth_stage_2) or Decimal("0.05")
            g_terminal = _to_decimal(terminal_growth) or Decimal("0.03")
            discount_rate = _to_decimal(wacc) or Decimal("0.10")

            if discount_rate <= g_terminal:
                raise ValueError("WACC must be greater than terminal growth.")

            yearly_rows = []
            projected_revenue = revenue
            discounted_fcf_total = Decimal("0")
            year_index = 0

            for _ in range(years_stage_1):
                year_index += 1
                projected_revenue = projected_revenue * (Decimal("1") + g1)
                projected_fcf = projected_revenue * fcf_margin
                discount_factor = (Decimal("1") + discount_rate) ** year_index
                discounted_fcf = projected_fcf / discount_factor
                discounted_fcf_total += discounted_fcf
                yearly_rows.append(
                    {
                        "year": year_index,
                        "growth_rate": str(g1),
                        "projected_revenue": str(projected_revenue),
                        "projected_fcf": str(projected_fcf),
                        "discount_factor": str(discount_factor),
                        "discounted_fcf": str(discounted_fcf),
                    }
                )

            for _ in range(years_stage_2):
                year_index += 1
                projected_revenue = projected_revenue * (Decimal("1") + g2)
                projected_fcf = projected_revenue * fcf_margin
                discount_factor = (Decimal("1") + discount_rate) ** year_index
                discounted_fcf = projected_fcf / discount_factor
                discounted_fcf_total += discounted_fcf
                yearly_rows.append(
                    {
                        "year": year_index,
                        "growth_rate": str(g2),
                        "projected_revenue": str(projected_revenue),
                        "projected_fcf": str(projected_fcf),
                        "discount_factor": str(discount_factor),
                        "discounted_fcf": str(discounted_fcf),
                    }
                )

            terminal_fcf = projected_revenue * (Decimal("1") + g_terminal) * fcf_margin
            terminal_value = terminal_fcf / (discount_rate - g_terminal)
            terminal_discount_factor = (Decimal("1") + discount_rate) ** year_index
            discounted_terminal_value = terminal_value / terminal_discount_factor

            enterprise_value = discounted_fcf_total + discounted_terminal_value
            equity_value = enterprise_value + net_cash
            implied_share_price = equity_value / diluted_shares

            return {
                "ticker": company.ticker,
                "company_name": company.name,
                "assumptions": {
                    "years_stage_1": years_stage_1,
                    "years_stage_2": years_stage_2,
                    "growth_stage_1": str(g1),
                    "growth_stage_2": str(g2),
                    "terminal_growth": str(g_terminal),
                    "wacc": str(discount_rate),
                    "base_revenue": str(revenue),
                    "base_fcf_margin": str(fcf_margin),
                    "net_cash": str(net_cash),
                    "diluted_shares": str(diluted_shares),
                },
                "projection_rows": yearly_rows,
                "valuation": {
                    "discounted_fcf_total": str(discounted_fcf_total),
                    "terminal_fcf": str(terminal_fcf),
                    "terminal_value": str(terminal_value),
                    "discounted_terminal_value": str(discounted_terminal_value),
                    "enterprise_value": str(enterprise_value),
                    "equity_value": str(equity_value),
                    "implied_share_price": str(implied_share_price),
                },
            }

        return CacheService.get_or_set(cache_key, _builder, timeout=60 * 30)
        