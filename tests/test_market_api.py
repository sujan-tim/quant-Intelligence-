from datetime import date

from quant_intelligence.main import app
from quant_intelligence.providers.alpha_vantage import Quote
from quant_intelligence.providers.base import AssetInfo
from quant_intelligence.providers.demo import DemoProvider
from quant_intelligence.settings import Settings, get_settings


def test_market_import_requires_key(client):
    response = client.post("/v1/ingestions/market", json={"symbol": "AAPL"})
    assert response.status_code == 503
    assert "QIP_ALPHA_VANTAGE_API_KEY" in response.json()["detail"]


def test_market_import_and_analytics_routes(client, monkeypatch):
    from quant_intelligence import api

    class FakeProvider:
        name = "alpha_vantage"

        def __init__(self, api_key, symbols, entitlement):
            assert api_key == "test-key"
            assert symbols == ["REAL"]
            assert entitlement == "historical"

        def assets(self):
            return [AssetInfo("REAL", "REAL")]

        def daily_bars(self, symbol):
            assert symbol == "REAL"
            return DemoProvider().daily_bars("DEMOA")

        def quote(self, symbol):
            assert symbol == "REAL"
            return Quote("REAL", 101.0, 1000, date(2024, 3, 30), self.name, "historical")

    monkeypatch.setattr(api, "AlphaVantageProvider", FakeProvider)
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, alpha_vantage_api_key="test-key"
    )
    imported = client.post("/v1/ingestions/market", json={"symbol": "REAL"})
    assert imported.status_code == 200
    assert imported.json()["latest_bar_date"] == "2024-03-30"
    assert imported.json()["requested_entitlement"] == "historical"
    assert client.get("/v1/assets/REAL/signals/latest").json()["source"] == "alpha_vantage"
    quote = client.get("/v1/market/quote/REAL")
    assert quote.status_code == 200
    assert quote.json()["latest_trading_day"] == "2024-03-30"
    assert quote.json()["requested_entitlement"] == "historical"

    forecast = client.get("/v1/assets/REAL/forecast?horizon=5")
    assert forecast.status_code == 200
    assert forecast.json()["method"] == "last_close_baseline"
    assert forecast.json()["source"] == "alpha_vantage"

    backtest = client.post("/v1/backtests", json={"symbol": "REAL"})
    assert backtest.status_code == 200
    assert backtest.json()["strategy"] == "long_only_sma20_above_sma50_next_open"
    assert backtest.json()["source"] == "alpha_vantage"
    assert backtest.json()["trades"]
