from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analytics import backtest_sma_cross, forecast_next_close
from .db import get_session
from .ingestion import IngestionResult, ingest
from .models import Asset, PriceBar, SignalSnapshot
from .paper import PaperTradeError, place_order, portfolio
from .providers.alpha_vantage import AlphaVantageProvider, MarketDataError
from .providers.base import Bar
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


class PaperOrderRequest(BaseModel):
    symbol: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9.^_-]{0,19}$")
    side: str = Field(pattern=r"^(buy|sell)$")
    quantity: int = Field(gt=0, le=1000000)


class PaperOrderResponse(BaseModel):
    id: int
    mode: str
    symbol: str
    side: str
    quantity: int
    execution_price: float
    price_date: date
    source: str
    cash_after: float


class PaperPositionResponse(BaseModel):
    symbol: str
    quantity: int
    last_price: float
    price_date: date
    source: str
    market_value: float


class PaperOrderHistoryResponse(BaseModel):
    id: int
    symbol: str
    side: str
    quantity: int
    execution_price: float
    price_date: date
    source: str
    created_at: datetime


class PaperPortfolioResponse(BaseModel):
    mode: str
    execution_rule: str
    starting_cash: float
    cash: float
    market_value: float
    equity: float
    positions: list[PaperPositionResponse]
    orders: list[PaperOrderHistoryResponse]


class MarketIngestionRequest(BaseModel):
    symbol: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9.^_-]{0,19}$")


class BacktestRequest(BaseModel):
    symbol: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9.^_-]{0,19}$")
    initial_cash: float = Field(default=10000, gt=0)
    fee_bps: float = Field(default=10, ge=0, lt=10000)
    slippage_bps: float = Field(default=5, ge=0, lt=10000)


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


@router.post("/ingestions/market")
def ingest_market(
    request: MarketIngestionRequest, session: SessionDep, settings: SettingsDep
) -> dict:
    """Import real provider bars; default entitlement is historical end-of-day."""
    if not settings.alpha_vantage_api_key:
        raise HTTPException(
            status_code=503,
            detail="Set QIP_ALPHA_VANTAGE_API_KEY to import real market data",
        )
    provider = AlphaVantageProvider(
        settings.alpha_vantage_api_key,
        [request.symbol],
        entitlement=settings.market_data_entitlement,
    )
    try:
        result = ingest(provider, session)
    except MarketDataError as exc:
        session.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    asset = _asset_or_404(session, request.symbol)
    latest = session.scalar(
        select(PriceBar)
        .where(PriceBar.asset_id == asset.id)
        .order_by(PriceBar.date.desc())
        .limit(1)
    )
    return {
        **asdict(result),
        "symbol": asset.symbol,
        "latest_bar_date": latest.date if latest else None,
        "requested_entitlement": settings.market_data_entitlement,
        "notice": "Check the bar date. Historical/default data is not a live quote.",
    }


@router.get("/market/quote/{symbol}")
def market_quote(symbol: str, settings: SettingsDep) -> dict:
    """Request the provider's latest available quote without claiming freshness."""
    if not settings.alpha_vantage_api_key:
        raise HTTPException(
            status_code=503,
            detail="Set QIP_ALPHA_VANTAGE_API_KEY to request a market quote",
        )
    try:
        provider = AlphaVantageProvider(
            settings.alpha_vantage_api_key,
            [symbol],
            entitlement=settings.market_data_entitlement,
        )
        return asdict(provider.quote(symbol))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/assets", response_model=list[AssetResponse])
def assets(session: SessionDep) -> list[Asset]:
    return list(session.scalars(select(Asset).order_by(Asset.symbol)))


def _asset_or_404(session: Session, symbol: str) -> Asset:
    asset = session.scalar(select(Asset).where(Asset.symbol == symbol.upper()))
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


def _historical_bars(session: Session, asset: Asset) -> list[Bar]:
    rows = session.scalars(
        select(PriceBar).where(PriceBar.asset_id == asset.id).order_by(PriceBar.date)
    )
    return [Bar(row.date, row.open, row.high, row.low, row.close, row.volume) for row in rows]


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


@router.get("/assets/{symbol}/forecast")
def forecast(
    symbol: str,
    session: SessionDep,
    horizon: int = Query(default=5, ge=1, le=20),
) -> dict:
    asset = _asset_or_404(session, symbol)
    try:
        result = forecast_next_close(_historical_bars(session, asset), horizon_bars=horizon)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"symbol": asset.symbol, "source": asset.source, **asdict(result)}


@router.post("/backtests")
def backtest(request: BacktestRequest, session: SessionDep) -> dict:
    asset = _asset_or_404(session, request.symbol)
    try:
        result = backtest_sma_cross(
            _historical_bars(session, asset),
            initial_cash=request.initial_cash,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"symbol": asset.symbol, "source": asset.source, **asdict(result)}


@router.get("/paper/portfolio", response_model=PaperPortfolioResponse)
def paper_portfolio(session: SessionDep) -> dict:
    return portfolio(session)


@router.post("/paper/orders", response_model=PaperOrderResponse)
def paper_order(request: PaperOrderRequest, session: SessionDep) -> dict:
    try:
        return place_order(session, request.symbol, request.side, request.quantity)
    except PaperTradeError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
