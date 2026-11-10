from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from .providers.base import Bar


@dataclass(frozen=True)
class Indicators:
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None
    sma_20: float | None
    sma_50: float | None
    volume_ratio_20: float | None


def _ema(values: Sequence[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    current = sum(values[:period]) / period
    result = [current]
    multiplier = 2 / (period + 1)
    for value in values[period:]:
        current = (value - current) * multiplier + current
        result.append(current)
    return result


def _rsi(closes: Sequence[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    changes = [b - a for a, b in pairwise(closes)]
    avg_gain = sum(max(change, 0) for change in changes[:period]) / period
    avg_loss = sum(max(-change, 0) for change in changes[:period]) / period
    for change in changes[period:]:
        avg_gain = (avg_gain * (period - 1) + max(change, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0)) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def calculate(bars: Sequence[Bar]) -> Indicators:
    """Calculate latest indicators from oldest-to-newest daily bars."""
    closes = [bar.close for bar in bars]
    sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
    sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
    macd = macd_signal = None
    if len(closes) >= 34:
        ema_12 = _ema(closes, 12)
        ema_26 = _ema(closes, 26)
        macd_values = [short - long for short, long in zip(ema_12[14:], ema_26)]
        macd = macd_values[-1]
        macd_signal = _ema(macd_values, 9)[-1]
    volume_ratio_20 = None
    if len(bars) >= 21:
        baseline = sum(bar.volume for bar in bars[-21:-1]) / 20
        volume_ratio_20 = bars[-1].volume / baseline if baseline > 0 else None
    return Indicators(_rsi(closes), macd, macd_signal, sma_20, sma_50, volume_ratio_20)
