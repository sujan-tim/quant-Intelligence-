from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session
from .ingestion import IngestionResult, ingest
from .models import Asset, PriceBar, SignalSnapshot
from .providers.demo import DemoProvider
from .ranking import rank
from .settings import Settings, get_settings

router = APIRouter(prefix="/v1")
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    symbol: str
    name: str
    source: str


class BarResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class SignalResponse(BaseModel):
    date: date
    symbol: str
    source: str
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None
    sma_20: float | None
    sma_50: float | None
    volume_ratio_20: float | None
    score: float
    rsi_oversold: bool
    macd_bullish: bool
    sma_bullish: bool
    volume_spike: bool


def _latest_signal(session: Session, asset: Asset) -> SignalSnapshot | None:
    return session.scalar(
        select(SignalSnapshot)
        .where(SignalSnapshot.asset_id == asset.id)
        .order_by(SignalSnapshot.date.desc())
        .limit(1)
    )


def _signal_response(asset: Asset, snapshot: SignalSnapshot, settings: Settings) -> SignalResponse:
    result = rank(snapshot, settings)
    return SignalResponse(
        date=snapshot.date,
        symbol=asset.symbol,
        source=asset.source,
        rsi_14=snapshot.rsi_14,
        macd=snapshot.macd,
        macd_signal=snapshot.macd_signal,
        sma_20=snapshot.sma_20,
        sma_50=snapshot.sma_50,
        volume_ratio_20=snapshot.volume_ratio_20,
        **vars(result),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ingestions/demo", response_model=IngestionResult)
def ingest_demo(session: SessionDep, settings: SettingsDep) -> IngestionResult:
    if not settings.demo_provider_enabled:
        raise HTTPException(status_code=403, detail="Demo provider is disabled")
    return ingest(DemoProvider(), session)


@router.get("/assets", response_model=list[AssetResponse])
def assets(session: SessionDep) -> list[Asset]:
    return list(session.scalars(select(Asset).order_by(Asset.symbol)))


def _asset_or_404(session: Session, symbol: str) -> Asset:
    asset = session.scalar(select(Asset).where(Asset.symbol == symbol.upper()))
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/assets/{symbol}/bars", response_model=list[BarResponse])
def bars(
    symbol: str,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[PriceBar]:
    asset = _asset_or_404(session, symbol)
    return list(
        session.scalars(
            select(PriceBar)
            .where(PriceBar.asset_id == asset.id)
            .order_by(PriceBar.date.desc())
            .limit(limit)
        )
    )


@router.get("/assets/{symbol}/signals/latest", response_model=SignalResponse)
def latest_signal(
    symbol: str,
    session: SessionDep,
    settings: SettingsDep,
) -> SignalResponse:
    asset = _asset_or_404(session, symbol)
    snapshot = _latest_signal(session, asset)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No signal snapshot")
    return _signal_response(asset, snapshot, settings)


@router.get("/rankings", response_model=list[SignalResponse])
def rankings(
    session: SessionDep,
    settings: SettingsDep,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[SignalResponse]:
    rows = []
    for asset in session.scalars(select(Asset).order_by(Asset.symbol)):
        snapshot = _latest_signal(session, asset)
        if snapshot is not None:
            rows.append(_signal_response(asset, snapshot, settings))
    return sorted(rows, key=lambda row: (-row.score, row.symbol))[:limit]
