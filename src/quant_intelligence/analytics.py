"""Transparent historical baselines. Nothing here predicts future returns reliably."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from math import ceil, isfinite

from .providers.base import Bar


@dataclass(frozen=True)
class ForecastResult:
    as_of: date
    horizon_bars: int
    last_close: float
    predicted_close: float
    historical_move_band_low: float
    historical_move_band_high: float
    historical_mean_abs_move_pct: float
    observations: int
    method: str
    limitation: str


@dataclass(frozen=True)
class Trade:
    date: date
    side: str
    price: float
    quantity: float
    fee: float


@dataclass(frozen=True)
class EquityPoint:
    date: date
    equity: float
    invested: bool


@dataclass(frozen=True)
class BacktestResult:
    start_date: date
    end_date: date
    initial_cash: float
    ending_equity: float
    total_return_pct: float
    buy_hold_return_pct: float
    max_drawdown_pct: float
    fee_bps: float
    slippage_bps: float
    trades: list[Trade]
    equity_curve: list[EquityPoint]
    strategy: str
    limitation: str


def _validate_bars(bars: Sequence[Bar]) -> None:
    if any(left.date >= right.date for left, right in pairwise(bars)):
        raise ValueError("Bars must be ordered oldest to newest with unique dates")
    if any(
        not isfinite(bar.open) or not isfinite(bar.close) or bar.open <= 0 or bar.close <= 0
        for bar in bars
    ):
        raise ValueError("Open and close prices must be positive, finite values")


def forecast_next_close(
    bars: Sequence[Bar], horizon_bars: int = 1, lookback: int = 60
) -> ForecastResult:
    """Last-close baseline with a descriptive 90th-percentile historical movement band.

    `horizon_bars` counts observed bars (usually trading sessions), not calendar days.
    The band describes the sample and is not a calibrated prediction interval.
    """
    if not 1 <= horizon_bars <= 20:
        raise ValueError("horizon_bars must be between 1 and 20")
    if lookback < 20:
        raise ValueError("lookback must be at least 20")
    if len(bars) < horizon_bars + 21:
        raise ValueError("At least 20 historical movements are required")
    _validate_bars(bars)

    first = max(0, len(bars) - horizon_bars - lookback)
    absolute_moves = sorted(
        abs(bars[index + horizon_bars].close / bars[index].close - 1)
        for index in range(first, len(bars) - horizon_bars)
    )
    movement_90 = absolute_moves[ceil(0.9 * len(absolute_moves)) - 1]
    last = bars[-1].close
    return ForecastResult(
        as_of=bars[-1].date,
        horizon_bars=horizon_bars,
        last_close=last,
        predicted_close=last,
        historical_move_band_low=max(0.0, last * (1 - movement_90)),
        historical_move_band_high=last * (1 + movement_90),
        historical_mean_abs_move_pct=sum(absolute_moves) / len(absolute_moves) * 100,
        observations=len(absolute_moves),
        method="last_close_baseline",
        limitation=(
            "Baseline assumes no price change. Band shows the 90th percentile of past absolute "
            "movements over the selected horizon; it is not a probability guarantee or trade signal."
        ),
    )


def backtest_sma_cross(
    bars: Sequence[Bar],
    initial_cash: float = 10_000.0,
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
) -> BacktestResult:
    """Long-only SMA20/SMA50 strategy using prior close signals and next open fills.

    Buys use available cash and fractional shares. Positions are marked to each
    daily close. The benchmark buys at the first eligible open (bar 51)
    with the same entry costs, so both paths have the same starting window.
    """
    if len(bars) < 51:
        raise ValueError("At least 51 bars are required for a 20/50 SMA backtest")
    _validate_bars(bars)
    if not isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("initial_cash must be positive and finite")
    if not isfinite(fee_bps) or not 0 <= fee_bps < 10_000:
        raise ValueError("fee_bps must be between 0 and 10000")
    if not isfinite(slippage_bps) or not 0 <= slippage_bps < 10_000:
        raise ValueError("slippage_bps must be between 0 and 10000")

    fee_rate = fee_bps / 10_000
    slip_rate = slippage_bps / 10_000
    cash = initial_cash
    shares = 0.0
    trades: list[Trade] = []
    curve: list[EquityPoint] = []
    closes = [bar.close for bar in bars]

    for index, bar in enumerate(bars):
        # A decision at today's open can only use closing prices from earlier bars.
        wanted = (
            index >= 50
            and sum(closes[index - 20 : index]) / 20 > sum(closes[index - 50 : index]) / 50
        )
        if wanted and shares == 0:
            fill = bar.open * (1 + slip_rate)
            shares = cash / (fill * (1 + fee_rate))
            fee = shares * fill * fee_rate
            cash -= shares * fill + fee
            trades.append(Trade(bar.date, "buy", fill, shares, fee))
        elif not wanted and shares > 0:
            fill = bar.open * (1 - slip_rate)
            fee = shares * fill * fee_rate
            cash += shares * fill - fee
            trades.append(Trade(bar.date, "sell", fill, shares, fee))
            shares = 0.0
        curve.append(EquityPoint(bar.date, cash + shares * bar.close, shares > 0))

    benchmark_fill = bars[50].open * (1 + slip_rate)
    benchmark_shares = initial_cash / (benchmark_fill * (1 + fee_rate))
    buy_hold_equity = benchmark_shares * bars[-1].close
    peak = initial_cash
    max_drawdown = 0.0
    for point in curve:
        peak = max(peak, point.equity)
        max_drawdown = max(max_drawdown, (peak - point.equity) / peak)
    ending = curve[-1].equity
    return BacktestResult(
        start_date=bars[0].date,
        end_date=bars[-1].date,
        initial_cash=initial_cash,
        ending_equity=ending,
        total_return_pct=(ending / initial_cash - 1) * 100,
        buy_hold_return_pct=(buy_hold_equity / initial_cash - 1) * 100,
        max_drawdown_pct=max_drawdown * 100,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        trades=trades,
        equity_curve=curve,
        strategy="long_only_sma20_above_sma50_next_open",
        limitation=(
            "Historical single-asset simulation with fractional shares and fixed costs. "
            "Excludes dividends, corporate actions, taxes, market impact, and data revisions. "
            "Past performance does not predict future results."
        ),
    )
