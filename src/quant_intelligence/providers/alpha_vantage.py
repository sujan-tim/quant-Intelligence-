"""Alpha Vantage adapter for user-authorized historical or entitled market data.

See https://www.alphavantage.co/documentation/ for endpoint and entitlement terms.
No Alpha Vantage code or data is bundled with this project.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .base import AssetInfo, Bar

_BASE_URL = "https://www.alphavantage.co/query"
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.^_-]{0,19}$")
Entitlement = Literal["historical", "delayed", "realtime"]


class MarketDataError(Exception):
    """A provider request or response could not be used safely."""


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    volume: int
    latest_trading_day: date
    source: str
    requested_entitlement: Entitlement


def _normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not _SYMBOL_PATTERN.fullmatch(normalized):
        raise ValueError("Invalid stock symbol")
    return normalized


def _fetch_json(params: dict[str, str]) -> dict:
    url = f"{_BASE_URL}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=15) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError):
        # Do not include the request URL or provider exception: they may contain the API key.
        raise MarketDataError("Alpha Vantage request failed") from None
    if not isinstance(payload, dict):
        raise MarketDataError("Alpha Vantage returned an invalid response")
    return payload


class AlphaVantageProvider:
    """Fetch genuine equity bars; freshness depends on the user's API entitlement.

    The free/default entitlement is historical end-of-day data, not a live feed.
    Delayed and realtime require a premium key with the corresponding entitlement.
    """

    name = "alpha_vantage"

    def __init__(
        self,
        api_key: str,
        symbols: list[str],
        entitlement: Entitlement = "historical",
        fetch_json: Callable[[dict[str, str]], dict] | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Alpha Vantage API key is required")
        if entitlement not in {"historical", "delayed", "realtime"}:
            raise ValueError("Unsupported market data entitlement")
        self._api_key = api_key.strip()
        self._symbols = list(dict.fromkeys(_normalize_symbol(symbol) for symbol in symbols))
        self.entitlement = entitlement
        self._fetch = fetch_json or _fetch_json

    def assets(self) -> list[AssetInfo]:
        # A ticker is not a verified company name. Keep it explicit until a
        # separate company profile endpoint is added.
        return [AssetInfo(symbol=symbol, name=symbol) for symbol in self._symbols]

    def _request(self, function: str, symbol: str) -> dict:
        symbol = _normalize_symbol(symbol)
        if symbol not in self._symbols:
            raise ValueError("Symbol is not configured for this provider")
        params = {"function": function, "symbol": symbol, "apikey": self._api_key}
        if function == "TIME_SERIES_DAILY":
            params["outputsize"] = "compact"
        if self.entitlement != "historical":
            params["entitlement"] = self.entitlement
        payload = self._fetch(params)
        if not isinstance(payload, dict):
            raise MarketDataError("Alpha Vantage returned an invalid response")
        if "Note" in payload or "Information" in payload:
            raise MarketDataError("Alpha Vantage rate limit or entitlement error")
        if "Error Message" in payload:
            raise MarketDataError("Alpha Vantage rejected the stock symbol or request")
        return payload

    def daily_bars(self, symbol: str) -> list[Bar]:
        payload = self._request("TIME_SERIES_DAILY", symbol)
        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict) or not series:
            raise MarketDataError("No daily bars were returned for this stock")
        try:
            bars = [
                Bar(
                    date=date.fromisoformat(day),
                    open=float(values["1. open"]),
                    high=float(values["2. high"]),
                    low=float(values["3. low"]),
                    close=float(values["4. close"]),
                    volume=int(values["5. volume"]),
                )
                for day, values in series.items()
            ]
        except (KeyError, ValueError, TypeError) as exc:
            raise MarketDataError("Alpha Vantage returned malformed daily bars") from exc
        for bar in bars:
            if (
                bar.open <= 0
                or bar.close <= 0
                or bar.low <= 0
                or bar.volume < 0
                or bar.low > min(bar.open, bar.close)
                or bar.high < max(bar.open, bar.close)
            ):
                raise MarketDataError("Alpha Vantage returned an invalid daily bar")
        return sorted(bars, key=lambda bar: bar.date)

    def quote(self, symbol: str) -> Quote:
        payload = self._request("GLOBAL_QUOTE", symbol)
        quote = payload.get("Global Quote")
        if not isinstance(quote, dict) or not quote:
            raise MarketDataError("No quote was returned for this stock")
        try:
            result = Quote(
                symbol=_normalize_symbol(quote["01. symbol"]),
                price=float(quote["05. price"]),
                volume=int(quote["06. volume"]),
                latest_trading_day=date.fromisoformat(quote["07. latest trading day"]),
                source=self.name,
                requested_entitlement=self.entitlement,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise MarketDataError("Alpha Vantage returned a malformed quote") from exc
        if result.symbol != _normalize_symbol(symbol) or result.price <= 0 or result.volume < 0:
            raise MarketDataError("Alpha Vantage returned an invalid quote")
        return result
