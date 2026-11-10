from datetime import date

from quant_intelligence.models import SignalSnapshot
from quant_intelligence.ranking import rank
from quant_intelligence.settings import Settings


def test_configurable_weights_and_zero_total():
    snapshot = SignalSnapshot(
        asset_id=1,
        date=date(2024, 1, 1),
        rsi_14=25,
        macd=1,
        macd_signal=0,
        sma_20=5,
        sma_50=4,
        volume_ratio_20=1,
    )
    settings = Settings(
        _env_file=None,
        rsi_weight=2,
        macd_weight=1,
        sma_weight=1,
        volume_weight=4,
    )
    result = rank(snapshot, settings)
    assert result.score == 50
    assert result.volume_spike is False
    assert (
        rank(
            snapshot,
            Settings(_env_file=None, rsi_weight=0, macd_weight=0, sma_weight=0, volume_weight=0),
        ).score
        == 0
    )
