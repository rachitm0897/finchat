from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from django.db import transaction

from apps.fundamentals.models import (
    BalanceSheet,
    CashFlowStatement,
    CompanyFinancialPeriod,
    IncomeStatement,
)
from apps.market_data.models import Company

logger = logging.getLogger(__name__)


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _safe_date(value: Any) -> date | None:
    if value in (None, ""):
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y-%m",
        "%Y/%m",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt in ("%Y-%m", "%Y/%m"):
                return date(parsed.year, parsed.month, 1)
            return parsed.date()
        except ValueError:
            continue

    # last-resort fallback for common ISO-like timestamps
    try:
        normalized = text.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return None


def _first_present(mapping: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _normalize_concept_name(raw: str) -> str:
    text = str(raw).strip()

    # remove namespace prefix patterns like us-gaap_ or ifrs-full_
    if "_" in text:
        prefix, rest = text.split("_", 1)
        if prefix.lower() in {"us-gaap", "usgaap", "ifrs-full", "ifrsfull", "dei"}:
            text = rest

    # remove colon namespace variants if ever present
    if ":" in text:
        text = text.split(":")[-1]

    return (
        text.strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace(".", "")
        .replace("/", "")
        .replace("&", "and")
        .replace("(", "")
        .replace(")", "")
        .replace(",", "")
    )


INCOME_ALIASES: dict[str, tuple[str, ...]] = {
    "revenue": (
        "revenue",
        "revenues",
        "salesrevenue",
        "salesrevenuenet",
        "totalrevenue",
        "revenuefromcontractwithcustomerexcludingassessedtax",
        "netsales",
    ),
    "cost_of_revenue": (
        "costofrevenue",
        "costofgoodsandservicessold",
        "costofgoodssold",
        "costofsales",
    ),
    "gross_profit": (
        "grossprofit",
        "grossmargin",
    ),
    "operating_expense": (
        "operatingexpenses",
        "operatingexpense",
        "totaloperatingexpenses",
    ),
    "selling_general_and_administrative": (
        "sellinggeneralandadministrativeexpense",
        "sgaexpense",
        "sellinggeneralandadministrative",
    ),
    "research_and_development": (
        "researchanddevelopmentexpense",
        "researchdevelopmentexpense",
        "rdexpense",
    ),
    "depreciation_and_amortization": (
        "depreciationdepletionandamortization",
        "depreciationandamortization",
        "depreciation",
        "amortization",
    ),
    "operating_income": (
        "operatingincomeloss",
        "operatingincome",
    ),
    "interest_expense": (
        "interestexpense",
        "interestanddebtexpense",
    ),
    "pretax_income": (
        "incomebeforetaxes",
        "pretaxincome",
        "incomebeforetaxexpensebenefit",
    ),
    "income_tax_expense": (
        "incometaxexpensebenefit",
        "incometaxes",
        "incometaxexpense",
    ),
    "net_income": (
        "netincomeloss",
        "netincome",
        "profitloss",
        "netincomelossavailabletocommonstockholdersbasic",
    ),
    "diluted_eps": (
        "earningspersharediluted",
        "dilutedeps",
    ),
    "weighted_average_diluted_shares": (
        "weightedaveragenumberofdilutedsharesoutstanding",
        "weightedaveragenumberofdilutedshares",
    ),
}

BALANCE_ALIASES: dict[str, tuple[str, ...]] = {
    "cash_and_cash_equivalents": (
        "cashandcashequivalentsatcarryingvalue",
        "cashandcashequivalents",
        "cash",
    ),
    "short_term_investments": (
        "marketablesecuritiescurrent",
        "availableforsalesecuritiescurrent",
        "shortterminvestments",
        "marketablesecurities",
    ),
    "accounts_receivable": (
        "accountsreceivablenetcurrent",
        "receivablesnetcurrent",
        "accountsreceivable",
        "accountsreceivablenet",
    ),
    "inventory": (
        "inventorynet",
        "inventories",
        "inventory",
    ),
    "other_current_assets": (
        "otherassetscurrent",
        "othercurrentassets",
    ),
    "total_current_assets": (
        "assetscurrent",
        "totalcurrentassets",
    ),
    "property_plant_and_equipment": (
        "propertyplantandequipmentnet",
        "propertyplantandequipmentgross",
        "propertyplantandequipment",
    ),
    "goodwill": (
        "goodwill",
    ),
    "intangible_assets": (
        "finitelivedintangibleassetsnet",
        "intangibleassetsnetexcludinggoodwill",
        "intangibleassetsnet",
        "intangibleassets",
    ),
    "total_non_current_assets": (
        "assetsnoncurrent",
        "totalnoncurrentassets",
    ),
    "total_assets": (
        "assets",
        "totalassets",
    ),
    "accounts_payable": (
        "accountspayablecurrent",
        "accountspayable",
    ),
    "short_term_debt": (
        "shorttermborrowings",
        "longtermdebtcurrent",
        "shorttermdebt",
        "commercialpaper",
    ),
    "other_current_liabilities": (
        "otherliabilitiescurrent",
        "othercurrentliabilities",
    ),
    "total_current_liabilities": (
        "liabilitiescurrent",
        "totalcurrentliabilities",
    ),
    "long_term_debt": (
        "longtermdebtnoncurrent",
        "longtermdebt",
    ),
    "total_non_current_liabilities": (
        "liabilitiesnoncurrent",
        "totalnoncurrentliabilities",
    ),
    "total_liabilities": (
        "liabilities",
        "totalliabilities",
    ),
    "retained_earnings": (
        "retainedearningsaccumulateddeficit",
        "retainedearnings",
    ),
    "total_shareholders_equity": (
        "stockholdersequity",
        "stockholdersequityincludingportionattributabletononcontrollinginterest",
        "equity",
        "totalequity",
        "totalshareholdersequity",
    ),
    "total_liabilities_and_equity": (
        "liabilitiesandstockholdersequity",
        "totalliabilitiesandequity",
    ),
}

CASHFLOW_ALIASES: dict[str, tuple[str, ...]] = {
    "net_income": (
        "netincomeloss",
        "netincome",
    ),
    "depreciation_and_amortization": (
        "depreciationdepletionandamortization",
        "depreciationamortizationandaccretionnet",
        "depreciationandamortization",
    ),
    "stock_based_compensation": (
        "sharebasedcompensation",
        "stockbasedcompensation",
        "sharebasedcompensationexpense",
    ),
    "changes_in_working_capital": (
        "changesinoperatingassetsandliabilitiesnet",
        "changeinworkingcapital",
        "changesinworkingcapital",
    ),
    "cash_from_operating_activities": (
        "netcashprovidedbyusedinoperatingactivities",
        "netcashprovidedbyusedinoperatingactivitiescontinuingoperations",
        "netcashfromoperatingactivities",
    ),
    "capital_expenditure": (
        "paymentstoacquirepropertyplantandequipment",
        "purchaseofpropertyplantandequipment",
        "capitalexpenditures",
        "capex",
    ),
    "acquisitions": (
        "paymentstoacquirebusinessesnetofcashacquired",
        "businessacquisitionnetofcashacquired",
        "acquisitionsnet",
    ),
    "cash_from_investing_activities": (
        "netcashprovidedbyusedininvestingactivities",
        "netcashfrominvestingactivities",
    ),
    "debt_issued_or_repaid_net": (
        "debtissuedorrepaidnet",
        "proceedsfromissuanceoflongtermdebt",
        "repaymentsoflongtermdebt",
    ),
    "dividends_paid": (
        "paymentsofdividends",
        "dividendspaid",
    ),
    "share_repurchases": (
        "paymentstorepurchasecommonstock",
        "commonstockrepurchased",
        "repurchaseofcommonstock",
        "sharerepurchase",
    ),
    "cash_from_financing_activities": (
        "netcashprovidedbyusedinfinancingactivities",
        "netcashfromfinancingactivities",
    ),
    "net_change_in_cash": (
        "cashcashequivalentsrestrictedcashandrestrictedcashequivalentsperiodincreasedecreaseincludingexchangerateeffect",
        "cashcashequivalentsrestrictedcashandrestrictedcashequivalentsperiodincreasedecrease",
        "netchangeincash",
    ),
    "free_cash_flow": (
        "freecashflow",
    ),
}


@dataclass(slots=True)
class ParsedStatementRecord:
    period_type: str
    fiscal_year: int
    fiscal_quarter: int | None
    period_end_date: date
    currency_code: str
    source_period_key: str
    income_statement: dict[str, Decimal | None]
    balance_sheet: dict[str, Decimal | None]
    cash_flow_statement: dict[str, Decimal | None]
    source_payload_json: dict[str, Any]


class FinnhubFinancialStatementParser:
    """
    Converts Finnhub /stock/financials-reported payloads into normalized records.

    The parser is intentionally defensive because reported financial payloads can
    vary by issuer and filing structure.
    """

    @classmethod
    def parse(cls, payload: dict[str, Any], default_currency: str = "USD") -> list[ParsedStatementRecord]:
        data_rows = payload.get("data") or []
        parsed_records: list[ParsedStatementRecord] = []

        for row in data_rows:
            report = row.get("report") or {}
            bs_items = cls._extract_statement_items(report, statement_keys=("bs", "balanceSheet"))
            ic_items = cls._extract_statement_items(report, statement_keys=("ic", "incomeStatement"))
            cf_items = cls._extract_statement_items(report, statement_keys=("cf", "cashFlowStatement"))

            end_date = _safe_date(
                _first_present(
                    row,
                    ("endDate", "end_date", "period", "date"),
                )
            )
            if end_date is None:
                logger.warning(
                    "Skipping statement row because end date could not be parsed. raw_end_date=%s row=%s",
                    row.get("endDate") or row.get("end_date") or row.get("period") or row.get("date"),
                    row,
                )
                continue

            year_value = _first_present(row, ("year", "fiscalYear", "fiscal_year"))
            quarter_value = _first_present(row, ("quarter", "fiscalQuarter", "fiscal_quarter"))
            form_value = str(_first_present(row, ("form", "formType")) or "").upper()

            fiscal_year = cls._derive_year(year_value, end_date)
            fiscal_quarter = cls._derive_quarter(quarter_value, end_date, form_value)
            period_type = (
                CompanyFinancialPeriod.PERIOD_TYPE_QUARTERLY
                if fiscal_quarter is not None
                else CompanyFinancialPeriod.PERIOD_TYPE_ANNUAL
            )

            currency_code = (
                str(_first_present(row, ("currency", "ccy", "currencyCode")) or default_currency).upper()
            )

            income_data = cls._map_statement(ic_items, INCOME_ALIASES)
            balance_data = cls._map_statement(bs_items, BALANCE_ALIASES)
            cashflow_data = cls._map_statement(cf_items, CASHFLOW_ALIASES)

            if balance_data.get("total_current_assets") is None:
                components = [
                    balance_data.get("cash_and_cash_equivalents"),
                    balance_data.get("short_term_investments"),
                    balance_data.get("accounts_receivable"),
                    balance_data.get("inventory"),
                    balance_data.get("other_current_assets"),
                ]
                present_components = [x for x in components if x is not None]
                if present_components:
                    balance_data["total_current_assets"] = sum(present_components, Decimal("0"))

            # derive a few values if absent
            if cashflow_data.get("free_cash_flow") is None:
                cfo = cashflow_data.get("cash_from_operating_activities")
                capex = cashflow_data.get("capital_expenditure")
                if cfo is not None and capex is not None:
                    cashflow_data["free_cash_flow"] = cfo - abs(capex)

            source_period_key = f"{period_type}:{fiscal_year}:{fiscal_quarter or 0}:{end_date.isoformat()}"

            parsed_records.append(
                ParsedStatementRecord(
                    period_type=period_type,
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                    period_end_date=end_date,
                    currency_code=currency_code,
                    source_period_key=source_period_key,
                    income_statement=income_data,
                    balance_sheet=balance_data,
                    cash_flow_statement=cashflow_data,
                    source_payload_json=row,
                )
            )

        return parsed_records

    @staticmethod
    def _extract_statement_items(report: dict[str, Any], statement_keys: tuple[str, ...]) -> list[dict[str, Any]]:
        for key in statement_keys:
            items = report.get(key)
            if isinstance(items, list):
                return items
        return []

    @staticmethod
    def _derive_year(year_value: Any, end_date: date) -> int:
        if year_value not in (None, ""):
            try:
                return int(year_value)
            except (TypeError, ValueError):
                pass
        return end_date.year

    @staticmethod
    def _derive_quarter(quarter_value: Any, end_date: date, form_value: str) -> int | None:
        if quarter_value not in (None, ""):
            try:
                q = int(quarter_value)
                if q in (1, 2, 3, 4):
                    return q
            except (TypeError, ValueError):
                pass

        if form_value in {"10-K", "20-F", "40-F", "ANNUAL"}:
            return None

        month = end_date.month
        derived = ((month - 1) // 3) + 1
        if derived in (1, 2, 3, 4):
            return derived
        return None

    @classmethod
    def _map_statement(
        cls,
        items: list[dict[str, Any]],
        alias_map: dict[str, tuple[str, ...]],
    ) -> dict[str, Decimal | None]:
        concept_values: dict[str, Decimal | None] = {}

        for item in items:
            raw_concept = (
                item.get("concept")
                or item.get("label")
                or item.get("name")
                or item.get("field")
                or item.get("conceptName")
                or ""
            )

            concept_name = _normalize_concept_name(str(raw_concept))
            if not concept_name:
                continue

            value = _safe_decimal(
                _first_present(item, ("value", "amount", "v"))
            )
            if value is None:
                continue

            if concept_name not in concept_values:
                concept_values[concept_name] = value

            # also index normalized label separately if available
            raw_label = item.get("label")
            if raw_label:
                label_name = _normalize_concept_name(str(raw_label))
                if label_name and label_name not in concept_values:
                    concept_values[label_name] = value

        result: dict[str, Decimal | None] = {}

        for target_field, aliases in alias_map.items():
            result[target_field] = None

            # exact alias match first
            for alias in aliases:
                normalized_alias = _normalize_concept_name(alias)
                if normalized_alias in concept_values:
                    result[target_field] = concept_values[normalized_alias]
                    break

            if result[target_field] is not None:
                continue

            # fallback: substring match
            for alias in aliases:
                normalized_alias = _normalize_concept_name(alias)
                for concept_key, concept_value in concept_values.items():
                    if normalized_alias in concept_key or concept_key in normalized_alias:
                        result[target_field] = concept_value
                        break
                if result[target_field] is not None:
                    break

        logger.info(
            "Mapped statement fields: %s",
            {k: str(v) for k, v in result.items() if v is not None},
        )

        return result


class FinancialStatementIngestionService:
    def __init__(self, company: Company) -> None:
        self.company = company

    @transaction.atomic
    def ingest_reported_financials(
        self,
        payload: dict[str, Any],
        source_name: str = "finnhub",
        default_currency: str = "USD",
    ) -> dict[str, int]:
        records = FinnhubFinancialStatementParser.parse(
            payload=payload,
            default_currency=default_currency,
        )

        periods_written = 0
        income_written = 0
        balance_written = 0
        cashflow_written = 0

        for record in records:
            period, period_created = CompanyFinancialPeriod.objects.update_or_create(
                company=self.company,
                period_type=record.period_type,
                fiscal_year=record.fiscal_year,
                fiscal_quarter=record.fiscal_quarter,
                period_end_date=record.period_end_date,
                defaults={
                    "currency_code": record.currency_code,
                    "source_name": source_name,
                    "source_period_key": record.source_period_key,
                },
            )
            if period_created:
                periods_written += 1

            _, income_created = IncomeStatement.objects.update_or_create(
                company=self.company,
                period=period,
                defaults={
                    "source_name": source_name,
                    "source_payload_json": record.source_payload_json,
                    **record.income_statement,
                },
            )
            if income_created:
                income_written += 1

            _, balance_created = BalanceSheet.objects.update_or_create(
                company=self.company,
                period=period,
                defaults={
                    "source_name": source_name,
                    "source_payload_json": record.source_payload_json,
                    **record.balance_sheet,
                },
            )
            if balance_created:
                balance_written += 1

            _, cashflow_created = CashFlowStatement.objects.update_or_create(
                company=self.company,
                period=period,
                defaults={
                    "source_name": source_name,
                    "source_payload_json": record.source_payload_json,
                    **record.cash_flow_statement,
                },
            )
            if cashflow_created:
                cashflow_written += 1

        return {
            "periods_written": periods_written,
            "income_written": income_written,
            "balance_written": balance_written,
            "cashflow_written": cashflow_written,
            "records_seen": len(records),
        }