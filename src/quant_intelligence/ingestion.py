from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Asset, PriceBar, SignalSnapshot
from .providers.base import Bar, MarketDataProvider
from .signals import calculate


@dataclass(frozen=True)
class IngestionResult:
    source: str
    assets: int
    bars_created: int
    bars_updated: int
    snapshots: int


def ingest(provider: MarketDataProvider, session: Session) -> IngestionResult:
    """Upsert a provider batch atomically; recalculate the latest snapshot per asset."""
    created = updated = snapshots = 0
    assets = provider.assets()
    for info in assets:
        asset = session.scalar(select(Asset).where(Asset.symbol == info.symbol))
        if asset is None:
            asset = Asset(symbol=info.symbol, name=info.name, source=provider.name)
            session.add(asset)
            session.flush()
        else:
            asset.name = info.name
            asset.source = provider.name
        incoming = sorted(provider.daily_bars(info.symbol), key=lambda bar: bar.date)
        if not incoming:
            continue
        if len({bar.date for bar in incoming}) != len(incoming):
            raise ValueError(f"Duplicate bar dates for {info.symbol}")
        existing = {
            bar.date: bar
            for bar in session.scalars(select(PriceBar).where(PriceBar.asset_id == asset.id))
        }
        for bar in incoming:
            if (
                bar.volume < 0
                or bar.low > min(bar.open, bar.close)
                or bar.high < max(bar.open, bar.close)
            ):
                raise ValueError(f"Invalid OHLCV bar for {info.symbol} on {bar.date}")
            row = existing.get(bar.date)
            if row is None:
                row = PriceBar(asset_id=asset.id, date=bar.date)
                session.add(row)
                created += 1
            else:
                updated += 1
            row.open, row.high, row.low, row.close, row.volume = (
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
            )
        session.flush()
        all_bars = list(
            session.scalars(
                select(PriceBar).where(PriceBar.asset_id == asset.id).order_by(PriceBar.date)
            )
        )
        latest = all_bars[-1]
        values = calculate(
            [Bar(row.date, row.open, row.high, row.low, row.close, row.volume) for row in all_bars]
        )
        snapshot = session.scalar(
            select(SignalSnapshot).where(
                SignalSnapshot.asset_id == asset.id, SignalSnapshot.date == latest.date
            )
        )
        if snapshot is None:
            snapshot = SignalSnapshot(asset_id=asset.id, date=latest.date)
            session.add(snapshot)
        for key, value in vars(values).items():
            setattr(snapshot, key, value)
        snapshots += 1
    session.commit()
    return IngestionResult(provider.name, len(assets), created, updated, snapshots)
