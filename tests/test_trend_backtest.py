import pytest

from backend.trend_backtest import ForgeTrendBacktester


def _candles(count=160):
    price = 100.0
    candles = []
    for idx in range(count):
        price += 0.35
        candles.append(
            {
                "timestamp": idx,
                "open": price - 0.2,
                "high": price + 0.8,
                "low": price - 0.8,
                "close": price,
                "volume": 1_000 + idx * 4,
            }
        )
    return candles


def test_forge_backtester_scores_historical_windows():
    result = ForgeTrendBacktester().run(
        asset="ETH",
        candles=_candles(),
        horizon="4h",
        mode="momentum",
        lookback=30,
        stride=5,
    ).to_dict()

    assert result["asset"] == "ETH"
    assert result["samples"] > 0
    assert result["accuracy_pct"] is not None
    assert result["mean_score"] is not None
    assert result["predictions"][0]["future_return_pct"] > 0


def test_forge_backtester_rejects_short_lookback():
    with pytest.raises(ValueError):
        ForgeTrendBacktester().run(asset="ETH", candles=_candles(), lookback=10)
