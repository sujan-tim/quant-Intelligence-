from sqlalchemy import func, select

from quant_intelligence.ingestion import ingest
from quant_intelligence.models import Asset, PriceBar, SignalSnapshot
from quant_intelligence.providers.demo import DemoProvider


def test_demo_provider_is_deterministic():
    provider = DemoProvider()
    assert provider.daily_bars("DEMOA") == provider.daily_bars("DEMOA")
    assert provider.daily_bars("DEMOA")[-1].date.isoformat() == "2024-03-30"


def test_ingestion_is_idempotent(session):
    first = ingest(DemoProvider(), session)
    second = ingest(DemoProvider(), session)
    assert first.assets == 3
    assert first.bars_created == 270
    assert second.bars_created == 0
    assert second.bars_updated == 270
    assert session.scalar(select(func.count()).select_from(Asset)) == 3
    assert session.scalar(select(func.count()).select_from(PriceBar)) == 270
    assert session.scalar(select(func.count()).select_from(SignalSnapshot)) == 3


def test_api_flow(client):
    assert client.get("/v1/health").json() == {"status": "ok"}
    response = client.post("/v1/ingestions/demo")
    assert response.status_code == 200
    assert response.json()["source"] == "demo"
    assets = client.get("/v1/assets").json()
    assert [asset["symbol"] for asset in assets] == ["DEMOA", "DEMOB", "DEMOC"]
    bars = client.get("/v1/assets/demoa/bars?limit=2").json()
    assert len(bars) == 2
    assert bars[0]["date"] > bars[1]["date"]
    signal = client.get("/v1/assets/DEMOC/signals/latest").json()
    assert signal["source"] == "demo"
    assert signal["volume_spike"] is True
    rankings = client.get("/v1/rankings").json()
    assert len(rankings) == 3
    assert [item["score"] for item in rankings] == sorted(
        [item["score"] for item in rankings], reverse=True
    )
    assert client.get("/v1/assets/UNKNOWN/bars").status_code == 404
    assert client.get("/v1/assets/DEMOA/bars?limit=0").status_code == 422
