from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class FinnhubClientError(Exception):
    """Base exception for Finnhub client failures."""


class FinnhubMissingAPIKeyError(FinnhubClientError):
    """Raised when FINNHUB_API_KEY is not configured."""


class FinnhubAPIError(FinnhubClientError):
    """Raised when Finnhub returns an API or transport error."""


class FinnhubRateLimitError(FinnhubAPIError):
    """Raised when Finnhub rate-limits the request."""


class FinnhubNotFoundError(FinnhubAPIError):
    """Raised when the symbol appears invalid or no data is returned."""


@dataclass(slots=True)
class FinnhubResponse:
    endpoint_name: str
    params: dict[str, Any]
    status_code: int | None
    payload: Any


class FinnhubClient:
    """
    Thin transport client around Finnhub's REST API.

    Endpoints used:
    - /stock/profile2
    - /quote
    - /stock/metric
    - /stock/financials-reported
    - /search

    Finnhub documents company profile, quote/basic financials, and reported
    financials endpoints in its stock API docs. :contentReference[oaicite:1]{index=1}
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.5,
    ) -> None:
        self.api_key = api_key or getattr(settings, "FINNHUB_API_KEY", "")
        self.base_url = (base_url or getattr(settings, "FINNHUB_BASE_URL", "")).rstrip("/")
        self.timeout = timeout or int(getattr(settings, "HTTP_TIMEOUT_SECONDS", 20))
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

        if not self.api_key:
            raise FinnhubMissingAPIKeyError(
                "FINNHUB_API_KEY is not configured. Set it in .env before running ingestion."
            )

        if not self.base_url:
            raise FinnhubClientError("FINNHUB_BASE_URL is not configured.")

    def _request(self, path: str, endpoint_name: str, params: dict[str, Any]) -> FinnhubResponse:
        url = f"{self.base_url}/{path.lstrip('/')}"
        final_params = {**params, "token": self.api_key}

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(url, params=final_params, timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = exc
                logger.warning(
                    "Finnhub transport error for endpoint=%s attempt=%s error=%s",
                    endpoint_name,
                    attempt + 1,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (attempt + 1))
                    continue
                raise FinnhubAPIError(
                    f"Transport error calling Finnhub endpoint '{endpoint_name}': {exc}"
                ) from exc

            status_code = response.status_code

            if status_code == 429:
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (attempt + 1))
                    continue
                raise FinnhubRateLimitError(
                    f"Finnhub rate limit reached for endpoint '{endpoint_name}'."
                )

            if status_code >= 400:
                text = response.text[:500]
                raise FinnhubAPIError(
                    f"Finnhub API error for endpoint '{endpoint_name}': HTTP {status_code} - {text}"
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise FinnhubAPIError(
                    f"Finnhub returned non-JSON response for endpoint '{endpoint_name}'."
                ) from exc

            if isinstance(payload, dict) and payload.get("error"):
                error_msg = str(payload.get("error"))
                if "limit" in error_msg.lower():
                    raise FinnhubRateLimitError(error_msg)
                raise FinnhubAPIError(
                    f"Finnhub returned API error for endpoint '{endpoint_name}': {error_msg}"
                )

            return FinnhubResponse(
                endpoint_name=endpoint_name,
                params=params,
                status_code=status_code,
                payload=payload,
            )

        if last_error:
            raise FinnhubAPIError(str(last_error)) from last_error
        raise FinnhubAPIError(f"Unknown error calling endpoint '{endpoint_name}'.")

    def get_company_profile(self, symbol: str) -> FinnhubResponse:
        return self._request(
            path="/stock/profile2",
            endpoint_name="company_profile",
            params={"symbol": symbol},
        )

    def get_quote(self, symbol: str) -> FinnhubResponse:
        return self._request(
            path="/quote",
            endpoint_name="quote",
            params={"symbol": symbol},
        )

    def get_basic_financials(self, symbol: str) -> FinnhubResponse:
        return self._request(
            path="/stock/metric",
            endpoint_name="basic_financials",
            params={"symbol": symbol, "metric": "all"},
        )

    def get_financials_reported(
        self,
        symbol: str,
        frequency: str | None = None,
    ) -> FinnhubResponse:
        params: dict[str, Any] = {"symbol": symbol}
        if frequency:
            params["freq"] = frequency

        return self._request(
            path="/stock/financials-reported",
            endpoint_name="financials_reported",
            params=params,
        )
    def get_stock_candles(
        self,
        *,
        symbol: str,
        resolution: str,
        from_timestamp: int,
        to_timestamp: int,
    ) -> FinnhubResponse:
        return self._request(
            path="/stock/candle",
            endpoint_name="stock_candle",
            params={
                "symbol": symbol,
                "resolution": resolution,
                "from": from_timestamp,
                "to": to_timestamp,
            },
        )

    def search_symbol(self, query: str) -> FinnhubResponse:
        return self._request(
            path="/search",
            endpoint_name="symbol_search",
            params={"q": query},
        )