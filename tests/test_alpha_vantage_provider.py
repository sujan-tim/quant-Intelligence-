from datetime import date

import pytest

from quant_intelligence.providers.alpha_vantage import AlphaVantageProvider, MarketDataError


def _daily_payload():
    return {
        "Meta Data": {"1. Information": "Daily Prices"},
        "Time Series (Daily)": {
            "2026-11-12": {
                "1. open": "101.00",
                "2. high": "103.00",
                "3. low": "100.00",
                "4. close": "102.00",
                "5. volume": "125000",
            },
            "2026-11-11": {
                "1. open": "99.00",
                "2. high": "101.00",
                "3. low": "98.00",
                "4. close": "100.00",
                "5. volume": "100000",
            },
        },
    }


def test_daily_bars_are_sorted_and_query_is_historical_by_default():
    calls = []

    def fetch(params):
        calls.append(params)
        return _daily_payload()

    provider = AlphaVantageProvider("test-secret", ["aapl"], fetch_json=fetch)
    bars = provider.daily_bars("AAPL")
    assert [bar.date for bar in bars] == [date(2026, 11, 11), date(2026, 11, 12)]
    assert bars[-1].close == 102
    assert provider.assets()[0].name == "AAPL"
    assert calls[0] == {
        "function": "TIME_SERIES_DAILY",
        "symbol": "AAPL",
        "apikey": "test-secret",
        "outputsize": "compact",
    }


def test_realtime_entitlement_is_explicit():
    calls = []

    def fetch(params):
        calls.append(params)
        return {
            "Global Quote": {
                "01. symbol": "MSFT",
                "05. price": "250.50",
                "06. volume": "700000",
                "07. latest trading day": "2026-11-12",
            }
        }

    provider = AlphaVantageProvider("key", ["MSFT"], entitlement="realtime", fetch_json=fetch)
    quote = provider.quote("MSFT")
    assert quote.price == 250.5
    assert quote.latest_trading_day == date(2026, 11, 12)
    assert quote.requested_entitlement == "realtime"
    assert calls[0]["entitlement"] == "realtime"


def test_provider_errors_do_not_expose_key():
    provider = AlphaVantageProvider(
        "top-secret", ["AAPL"], fetch_json=lambda params: {"Information": "rate limit"}
    )
    with pytest.raises(MarketDataError) as exc:
        provider.daily_bars("AAPL")
    assert "top-secret" not in str(exc.value)


def test_malformed_data_is_rejected():
    provider = AlphaVantageProvider(
        "key", ["AAPL"], fetch_json=lambda params: {"Time Series (Daily)": {"bad-date": {}}}
    )
    with pytest.raises(MarketDataError):
        provider.daily_bars("AAPL")


def test_symbol_is_validated_before_request():
    with pytest.raises(ValueError):
        AlphaVantageProvider("key", ["AAPL&apikey=other"])
