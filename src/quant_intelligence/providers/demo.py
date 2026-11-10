import math
from datetime import date, timedelta

from .base import AssetInfo, Bar


class DemoProvider:
    """Fixed-date synthetic data for local development and tests only."""

    name = "demo"
    _assets = (
        AssetInfo("DEMOA", "Demo Trend A"),
        AssetInfo("DEMOB", "Demo Trend B"),
        AssetInfo("DEMOC", "Demo Trend C"),
    )

    def assets(self) -> list[AssetInfo]:
        return list(self._assets)

    def daily_bars(self, symbol: str) -> list[Bar]:
        if symbol not in {asset.symbol for asset in self._assets}:
            raise ValueError(f"Unknown demo symbol: {symbol}")
        offset = {"DEMOA": 0, "DEMOB": 1, "DEMOC": 2}[symbol]
        result = []
        for day in range(90):
            trend = day * (0.35 if offset == 0 else -0.12 if offset == 1 else 0.04)
            close = round(100 + 12 * offset + trend + 2.5 * math.sin(day / 5 + offset), 4)
            opened = round(close - 0.4, 4)
            volume = 100_000 + ((day * 7919 + offset * 1337) % 20_000)
            if day == 89 and offset == 2:
                volume *= 3
            result.append(
                Bar(
                    date(2024, 1, 1) + timedelta(days=day),
                    opened,
                    close + 1,
                    opened - 1,
                    close,
                    volume,
                )
            )
        return result
