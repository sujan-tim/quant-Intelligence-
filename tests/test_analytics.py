from datetime import date, timedelta

import pytest

from quant_intelligence.analytics import backtest_sma_cross, forecast_next_close
from quant_intelligence.providers.base import Bar


def make_bars(closes: list[float], opens: list[float] | None = None) -> list[Bar]:
    opens = opens or closes
    return [
        Bar(
            date=date(2024, 1, 1) + timedelta(days=index),
            open=opens[index],
            high=max(opens[index], close),
            low=min(opens[index], close),
            close=close,
            volume=100,
        )
        for index, close in enumerate(closes)
    ]


def test_forecast_is_clear_last_close_baseline():
    result = forecast_next_close(make_bars([100 + index for index in range(50)]))
    assert result.predicted_close == 149
    assert result.historical_move_band_low < 149 < result.historical_move_band_high
    assert result.observations == 49
    assert result.method == "last_close_baseline"


def test_forecast_flat_history_has_zero_width_band():
    result = forecast_next_close(make_bars([50] * 40), horizon_bars=5)
    assert result.historical_move_band_low == result.historical_move_band_high == 50
    assert result.historical_mean_abs_move_pct == 0


def test_backtest_fills_next_open_without_same_day_close_lookahead():
    original = make_bars([100 + index for index in range(60)])
    changed = original.copy()
    bar = changed[50]
    changed[50] = Bar(bar.date, bar.open, 300, bar.low, 300, bar.volume)

    baseline = backtest_sma_cross(original, fee_bps=0, slippage_bps=0)
    altered = backtest_sma_cross(changed, fee_bps=0, slippage_bps=0)
    assert baseline.trades[0].date == original[50].date
    assert baseline.trades[0].side == "buy"
    assert baseline.trades[0].price == altered.trades[0].price == original[50].open
    assert baseline.trades[0].quantity == altered.trades[0].quantity


def test_costs_reduce_backtest_return_and_flat_market_does_not_trade():
    rising = make_bars([100 + index for index in range(60)])
    no_cost = backtest_sma_cross(rising, fee_bps=0, slippage_bps=0)
    with_cost = backtest_sma_cross(rising, fee_bps=10, slippage_bps=5)
    assert with_cost.ending_equity < no_cost.ending_equity
    assert with_cost.trades[0].fee > 0
    flat = backtest_sma_cross(make_bars([100] * 60))
    assert flat.trades == []
    assert flat.total_return_pct == 0


def test_benchmark_starts_when_strategy_first_becomes_eligible():
    bars = make_bars([100 + index for index in range(60)])
    result = backtest_sma_cross(bars, fee_bps=0, slippage_bps=0)
    expected = (bars[-1].close / bars[50].open - 1) * 100
    assert result.buy_hold_return_pct == pytest.approx(expected)


def test_history_and_parameter_validation():
    with pytest.raises(ValueError, match="51 bars"):
        backtest_sma_cross(make_bars([100] * 50))
    with pytest.raises(ValueError, match="20 historical"):
        forecast_next_close(make_bars([100] * 20))
    with pytest.raises(ValueError, match="positive"):
        backtest_sma_cross(make_bars([100] * 60), initial_cash=0)
