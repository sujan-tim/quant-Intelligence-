from dataclasses import dataclass

from .models import SignalSnapshot
from .settings import Settings


@dataclass(frozen=True)
class RankedSignal:
    score: float
    rsi_oversold: bool
    macd_bullish: bool
    sma_bullish: bool
    volume_spike: bool


def rank(snapshot: SignalSnapshot, settings: Settings) -> RankedSignal:
    rsi = snapshot.rsi_14 is not None and snapshot.rsi_14 <= 30
    macd = (
        snapshot.macd is not None
        and snapshot.macd_signal is not None
        and snapshot.macd > snapshot.macd_signal
    )
    sma = (
        snapshot.sma_20 is not None
        and snapshot.sma_50 is not None
        and snapshot.sma_20 > snapshot.sma_50
    )
    volume = (
        snapshot.volume_ratio_20 is not None
        and snapshot.volume_ratio_20 >= settings.volume_spike_threshold
    )
    weights = [
        settings.rsi_weight,
        settings.macd_weight,
        settings.sma_weight,
        settings.volume_weight,
    ]
    total = sum(weights)
    score = sum(weight for active, weight in zip((rsi, macd, sma, volume), weights) if active)
    return RankedSignal(round(score / total * 100, 2) if total else 0.0, rsi, macd, sma, volume)
