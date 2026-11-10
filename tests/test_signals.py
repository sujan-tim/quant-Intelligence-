from datetime import date, timedelta

import pytest

from quant_intelligence.providers.base import Bar
from quant_intelligence.signals import calculate


def bars(closes, volumes=None):
    volumes = volumes or [100] * len(closes)
    return [
        Bar(date(2024, 1, 1) + timedelta(days=i), close, close, close, close, volumes[i])
        for i, close in enumerate(closes)
    ]


def test_insufficient_history_is_explicit():
    result = calculate(bars([1, 2, 3]))
    assert all(value is None for value in vars(result).values())


def test_sma_rsi_and_volume_spike():
    result = calculate(bars(list(range(1, 61)), [100] * 59 + [300]))
    assert result.sma_20 == pytest.approx(50.5)
    assert result.sma_50 == pytest.approx(35.5)
    assert result.rsi_14 == 100
    assert result.volume_ratio_20 == 3
    assert result.macd is not None and result.macd_signal is not None


def test_flat_prices_have_neutral_rsi():
    assert calculate(bars([10] * 20)).rsi_14 == 50
