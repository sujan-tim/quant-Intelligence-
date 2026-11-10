from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class AssetInfo:
    symbol: str
    name: str


@dataclass(frozen=True)
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketDataProvider(Protocol):
    name: str

    def assets(self) -> list[AssetInfo]: ...

    def daily_bars(self, symbol: str) -> list[Bar]: ...
