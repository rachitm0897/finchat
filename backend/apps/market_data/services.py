from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any

from django.db import transaction

from apps.fundamentals.services import FinancialStatementIngestionService
from apps.market_data.clients.finnhub import (
    FinnhubAPIError,
    FinnhubClient,
    FinnhubMissingAPIKeyError,
    FinnhubNotFoundError,
    FinnhubRateLimitError,
)
from apps.market_data.models import (
    Company,
    CompanyBasicMetricSnapshot,
    CompanyProfileSnapshot,
    CompanyQuoteSnapshot,
)

logger = logging.getLogger(__name__)


def _safe_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _safe_date(value: Any):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _safe_datetime_from_unix(value: Any) -> datetime | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _payload_hash(payload: Any) -> str:
    dumped = json.dumps(payload, sort_keys=True, default=str)
    return sha256(dumped.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class IngestionResult:
    company_id: str
    ticker: str
    company_created: bool
    profile_snapshot_created: bool
    quote_snapshot_created: bool
    basic_metric_snapshot_created: bool
    statements_result: dict[str, int]
    warnings: list[str]
@dataclass(slots=True)
class TickerSearchResult:
    ticker: str
    symbol: str
    name: str
    description: str
    exchange: str
    type: str
    currency: str
    country: str
    source: str
    is_ingested: bool


class FinnhubTickerSearchService:
    def __init__(self, client: FinnhubClient | None = None) -> None:
        self.client = client or FinnhubClient()

    def search_tickers(self, *, query: str, limit: int = 15) -> list[TickerSearchResult]:
        normalized_query = query.strip().upper()
        if not normalized_query:
            return []

        cache_key = f"ticker_search:{normalized_query}:{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        response = self.client.search_symbol(normalized_query)
        payload = response.payload or {}
        raw_results = payload.get("result") if isinstance(payload, dict) else []

        candidate_symbols = [
            str(item.get("symbol") or "").strip().upper()
            for item in raw_results
            if isinstance(item, dict)
        ]

        ingested_tickers = set(
            Company.objects.filter(
                ticker__in=candidate_symbols
            ).values_list("ticker", flat=True)
        )
        ingested_symbols = set(
            Company.objects.filter(
                finnhub_symbol__in=candidate_symbols
            ).values_list("finnhub_symbol", flat=True)
        )

        results: list[TickerSearchResult] = []
        seen: set[str] = set()

        for item in raw_results:
            if not isinstance(item, dict):
                continue

            symbol = str(item.get("symbol") or "").strip().upper()
            description = str(item.get("description") or "").strip()
            exchange = str(item.get("displaySymbol") or item.get("mic") or "").strip()
            instrument_type = str(item.get("type") or "").strip()
            currency = str(item.get("currency") or "").strip().upper()
            country = str(item.get("country") or "").strip().upper()

            if not symbol or symbol in seen:
                continue

            seen.add(symbol)

            results.append(
                TickerSearchResult(
                    ticker=symbol,
                    symbol=symbol,
                    name=description or symbol,
                    description=description or symbol,
                    exchange=exchange,
                    type=instrument_type,
                    currency=currency,
                    country=country,
                    source="finnhub",
                    is_ingested=(symbol in ingested_tickers or symbol in ingested_symbols),
                )
            )

            if len(results) >= limit:
                break

        cache.set(
            cache_key,
            results,
            timeout=int(getattr(settings, "TICKER_SEARCH_CACHE_TTL_SECONDS", 21600)),
        )
        return results

class CompanyIngestionService:
    def __init__(self, client: FinnhubClient | None = None) -> None:
        self.client = client or FinnhubClient()

    def ingest_company(
        self,
        ticker: str,
        *,
        ingest_statements: bool = True,
    ) -> IngestionResult:
        normalized_ticker = ticker.strip().upper()
        if not normalized_ticker:
            raise ValueError("Ticker must not be empty.")

        warnings: list[str] = []

        profile_response = self.client.get_company_profile(normalized_ticker)
        profile_payload = profile_response.payload or {}

        if not isinstance(profile_payload, dict) or not profile_payload:
            raise FinnhubNotFoundError(f"No company profile returned for ticker '{normalized_ticker}'.")

        # Finnhub profile endpoint typically returns a populated profile object for valid symbols. :contentReference[oaicite:2]{index=2}
        company_name = str(profile_payload.get("name") or "").strip()
        finnhub_symbol = str(profile_payload.get("ticker") or normalized_ticker).strip().upper()

        if not company_name and finnhub_symbol == normalized_ticker:
            search_response = self.client.search_symbol(normalized_ticker)
            results = search_response.payload.get("result") if isinstance(search_response.payload, dict) else None
            if not results:
                raise FinnhubNotFoundError(f"Ticker '{normalized_ticker}' does not appear to be valid on Finnhub.")
            warnings.append(
                f"Profile response was sparse for ticker '{normalized_ticker}'. Symbol search returned possible matches."
            )

        company, company_created = self._upsert_company_from_profile(
            ticker=normalized_ticker,
            profile_payload=profile_payload,
        )

        profile_snapshot_created = self._ingest_profile_snapshot(
            company=company,
            endpoint_name=profile_response.endpoint_name,
            params=profile_response.params,
            status_code=profile_response.status_code,
            payload=profile_payload,
        )

        quote_snapshot_created = False
        basic_metric_snapshot_created = False
        statements_result: dict[str, int] = {
            "periods_written": 0,
            "income_written": 0,
            "balance_written": 0,
            "cashflow_written": 0,
            "records_seen": 0,
        }

        try:
            quote_response = self.client.get_quote(normalized_ticker)
            quote_payload = quote_response.payload or {}
            if isinstance(quote_payload, dict) and any(
                quote_payload.get(key) not in (None, "", 0) for key in ("c", "pc", "h", "l", "o")
            ):
                quote_snapshot_created = self._ingest_quote_snapshot(
                    company=company,
                    endpoint_name=quote_response.endpoint_name,
                    params=quote_response.params,
                    status_code=quote_response.status_code,
                    payload=quote_payload,
                )
            else:
                warnings.append("Quote payload was empty or sparse.")
        except FinnhubRateLimitError:
            raise
        except FinnhubAPIError as exc:
            warnings.append(f"Quote fetch failed: {exc}")

        try:
            basic_response = self.client.get_basic_financials(normalized_ticker)
            basic_payload = basic_response.payload or {}
            if isinstance(basic_payload, dict) and basic_payload:
                basic_metric_snapshot_created = self._ingest_basic_metric_snapshot(
                    company=company,
                    endpoint_name=basic_response.endpoint_name,
                    params=basic_response.params,
                    status_code=basic_response.status_code,
                    payload=basic_payload,
                )
            else:
                warnings.append("Basic financials payload was empty.")
        except FinnhubRateLimitError:
            raise
        except FinnhubAPIError as exc:
            warnings.append(f"Basic financials fetch failed: {exc}")

        if ingest_statements:
            try:
                statements_response = self.client.get_financials_reported(normalized_ticker)
                statements_payload = statements_response.payload or {}
                if isinstance(statements_payload, dict) and statements_payload.get("data"):
                    default_currency = company.currency_code or "USD"
                    statements_result = FinancialStatementIngestionService(company).ingest_reported_financials(
                        payload=statements_payload,
                        source_name="finnhub",
                        default_currency=default_currency,
                    )
                else:
                    warnings.append("Reported financial statements payload was empty.")
            except FinnhubRateLimitError:
                raise
            except FinnhubAPIError as exc:
                warnings.append(f"Reported financial statements fetch failed: {exc}")

        return IngestionResult(
            company_id=str(company.id),
            ticker=company.ticker,
            company_created=company_created,
            profile_snapshot_created=profile_snapshot_created,
            quote_snapshot_created=quote_snapshot_created,
            basic_metric_snapshot_created=basic_metric_snapshot_created,
            statements_result=statements_result,
            warnings=warnings,
        )

    @transaction.atomic
    def _upsert_company_from_profile(
        self,
        ticker: str,
        profile_payload: dict[str, Any],
    ) -> tuple[Company, bool]:
        canonical_symbol = str(profile_payload.get("ticker") or ticker).strip().upper()
        requested_symbol = ticker.strip().upper()

        defaults = {
            "finnhub_symbol": canonical_symbol,
            "name": str(profile_payload.get("name") or canonical_symbol).strip(),
            "country": str(profile_payload.get("country") or "").strip(),
            "currency_code": str(profile_payload.get("currency") or "").strip().upper(),
            "exchange": str(profile_payload.get("exchange") or "").strip(),
            "primary_exchange": str(profile_payload.get("exchange") or "").strip(),
            "ipo_date": _safe_date(profile_payload.get("ipo")),
            "market_identifier_code": "",
            "logo_url": str(profile_payload.get("logo") or "").strip(),
            "web_url": str(profile_payload.get("weburl") or "").strip(),
            "industry": str(profile_payload.get("finnhubIndustry") or "").strip(),
            "is_active": True,
        }

        company = (
            Company.objects.filter(ticker=canonical_symbol).first()
            or Company.objects.filter(finnhub_symbol=canonical_symbol).first()
            or Company.objects.filter(ticker=requested_symbol).first()
            or Company.objects.filter(finnhub_symbol=requested_symbol).first()
        )

        if company is None:
            company = Company.objects.create(
                ticker=canonical_symbol,
                **defaults,
            )
            return company, True

        company.ticker = canonical_symbol
        for field, value in defaults.items():
            setattr(company, field, value)
        company.save()
        return company, False

    @transaction.atomic
    def _ingest_profile_snapshot(
        self,
        company: Company,
        endpoint_name: str,
        params: dict[str, Any],
        status_code: int | None,
        payload: dict[str, Any],
    ) -> bool:
        latest = company.profile_snapshots.filter(endpoint_name=endpoint_name, is_latest=True).first()
        new_hash = _payload_hash(payload)

        if latest and _payload_hash(latest.payload_json) == new_hash:
            return False

        company.profile_snapshots.filter(endpoint_name=endpoint_name, is_latest=True).update(is_latest=False)

        CompanyProfileSnapshot.objects.create(
            company=company,
            source_name="finnhub",
            endpoint_name=endpoint_name,
            fetched_at=datetime.now(tz=timezone.utc),
            is_latest=True,
            symbol=str(payload.get("ticker") or company.finnhub_symbol or company.ticker).strip().upper(),
            status_code=status_code,
            request_params=params,
            payload_json=payload,
            country=str(payload.get("country") or "").strip(),
            currency_code=str(payload.get("currency") or "").strip().upper(),
            exchange=str(payload.get("exchange") or "").strip(),
            ipo_date=_safe_date(payload.get("ipo")),
            market_capitalization=_safe_decimal(payload.get("marketCapitalization")),
            name=str(payload.get("name") or "").strip(),
            phone=str(payload.get("phone") or "").strip(),
            share_outstanding=_safe_decimal(payload.get("shareOutstanding")),
            ticker=str(payload.get("ticker") or company.ticker).strip().upper(),
            web_url=str(payload.get("weburl") or "").strip(),
            logo_url=str(payload.get("logo") or "").strip(),
            industry=str(payload.get("finnhubIndustry") or "").strip(),
        )
        return True

    @transaction.atomic
    def _ingest_quote_snapshot(
        self,
        company: Company,
        endpoint_name: str,
        params: dict[str, Any],
        status_code: int | None,
        payload: dict[str, Any],
    ) -> bool:
        latest = company.quote_snapshots.filter(endpoint_name=endpoint_name, is_latest=True).first()
        new_hash = _payload_hash(payload)

        if latest and _payload_hash(latest.payload_json) == new_hash:
            return False

        company.quote_snapshots.filter(endpoint_name=endpoint_name, is_latest=True).update(is_latest=False)

        CompanyQuoteSnapshot.objects.create(
            company=company,
            source_name="finnhub",
            endpoint_name=endpoint_name,
            fetched_at=datetime.now(tz=timezone.utc),
            is_latest=True,
            symbol=company.finnhub_symbol or company.ticker,
            status_code=status_code,
            request_params=params,
            payload_json=payload,
            current_price=_safe_decimal(payload.get("c")),
            change=_safe_decimal(payload.get("d")),
            percent_change=_safe_decimal(payload.get("dp")),
            high_price=_safe_decimal(payload.get("h")),
            low_price=_safe_decimal(payload.get("l")),
            open_price=_safe_decimal(payload.get("o")),
            previous_close_price=_safe_decimal(payload.get("pc")),
            quote_timestamp=_safe_datetime_from_unix(payload.get("t")),
        )
        return True

    @transaction.atomic
    def _ingest_basic_metric_snapshot(
        self,
        company: Company,
        endpoint_name: str,
        params: dict[str, Any],
        status_code: int | None,
        payload: dict[str, Any],
    ) -> bool:
        latest = company.basic_metric_snapshots.filter(endpoint_name=endpoint_name, is_latest=True).first()
        new_hash = _payload_hash(payload)

        if latest and _payload_hash(latest.payload_json) == new_hash:
            return False

        company.basic_metric_snapshots.filter(endpoint_name=endpoint_name, is_latest=True).update(is_latest=False)

        CompanyBasicMetricSnapshot.objects.create(
            company=company,
            source_name="finnhub",
            endpoint_name=endpoint_name,
            fetched_at=datetime.now(tz=timezone.utc),
            is_latest=True,
            symbol=company.finnhub_symbol or company.ticker,
            status_code=status_code,
            request_params=params,
            payload_json=payload,
            metric_values=payload.get("metric") if isinstance(payload, dict) else {},
        )
        return True


class CompanyBatchRefreshService:
    def __init__(self, client: FinnhubClient | None = None) -> None:
        self.client = client or FinnhubClient()

    def refresh_tickers(
        self,
        tickers: list[str],
        *,
        ingest_statements: bool = True,
        continue_on_error: bool = False,
    ) -> dict[str, Any]:
        service = CompanyIngestionService(client=self.client)
        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for raw_ticker in tickers:
            ticker = raw_ticker.strip().upper()
            if not ticker:
                continue

            try:
                result = service.ingest_company(ticker=ticker, ingest_statements=ingest_statements)
                results.append(
                    {
                        "ticker": result.ticker,
                        "company_id": result.company_id,
                        "company_created": result.company_created,
                        "profile_snapshot_created": result.profile_snapshot_created,
                        "quote_snapshot_created": result.quote_snapshot_created,
                        "basic_metric_snapshot_created": result.basic_metric_snapshot_created,
                        "statements_result": result.statements_result,
                        "warnings": result.warnings,
                    }
                )
            except (FinnhubMissingAPIKeyError, FinnhubRateLimitError):
                raise
            except Exception as exc:
                errors.append({"ticker": ticker, "error": str(exc)})
                if not continue_on_error:
                    raise

        return {
            "requested": len(tickers),
            "succeeded": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }