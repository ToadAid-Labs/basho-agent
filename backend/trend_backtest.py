"""
Backtesting harness for Trend Prediction Forge.

The harness replays historical candles through the deterministic forge engine
and measures whether the forecast direction matched the later realized return.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.trend_prediction import TrendPredictionEngine
from backend.trend_signal_collector import _market_from_candles


POSITIVE_DIRECTIONS = {"up_trend_likely", "watch_positive_bias"}
NEGATIVE_DIRECTIONS = {"down_or_fading", "avoid_high_risk"}


@dataclass(frozen=True)
class ForgeBacktestResult:
    asset: str
    horizon: str
    mode: str
    samples: int
    accuracy_pct: float | None
    mean_future_return_pct: float | None
    mean_score: float | None
    predictions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "horizon": self.horizon,
            "mode": self.mode,
            "samples": self.samples,
            "accuracy_pct": self.accuracy_pct,
            "mean_future_return_pct": self.mean_future_return_pct,
            "mean_score": self.mean_score,
            "predictions": self.predictions,
        }


class ForgeTrendBacktester:
    """Replay candles through the forge and score directional usefulness."""

    HORIZON_CANDLES = {
        "1h": 1,
        "4h": 4,
        "24h": 24,
        "7d": 168,
    }

    def run(
        self,
        asset: str,
        candles: list[dict[str, Any]],
        horizon: str = "24h",
        mode: str = "composite",
        lookback: int = 72,
        stride: int = 6,
        return_threshold_pct: float = 0.0,
        max_predictions: int = 200,
    ) -> ForgeBacktestResult:
        if horizon not in self.HORIZON_CANDLES:
            raise ValueError(f"horizon must be one of {sorted(self.HORIZON_CANDLES)}")
        if lookback < 20:
            raise ValueError("lookback must be at least 20 candles")
        if stride < 1:
            raise ValueError("stride must be at least 1")

        horizon_candles = self.HORIZON_CANDLES[horizon]
        if len(candles) < lookback + horizon_candles + 1:
            return ForgeBacktestResult(
                asset=asset.upper(),
                horizon=horizon,
                mode=mode,
                samples=0,
                accuracy_pct=None,
                mean_future_return_pct=None,
                mean_score=None,
                predictions=[],
            )

        engine = TrendPredictionEngine()
        predictions: list[dict[str, Any]] = []

        end = len(candles) - horizon_candles
        for idx in range(lookback, end, stride):
            if len(predictions) >= max_predictions:
                break

            history = candles[idx - lookback:idx]
            current = _close(candles[idx - 1])
            future = _close(candles[idx + horizon_candles - 1])
            if current <= 0 or future <= 0:
                continue

            market = _market_from_candles(history)
            forecast = engine.forecast(
                asset=asset,
                horizon=horizon,
                mode=mode,
                market=market,
                social={},
                onchain={},
                security={},
                narrative={},
            ).to_dict()

            future_return_pct = (future - current) / current * 100.0
            predicted_up = forecast["direction"] in POSITIVE_DIRECTIONS
            predicted_down = forecast["direction"] in NEGATIVE_DIRECTIONS
            actual_up = future_return_pct > return_threshold_pct
            actual_down = future_return_pct < -return_threshold_pct

            if predicted_up:
                correct = actual_up
            elif predicted_down:
                correct = actual_down
            else:
                correct = not actual_up and not actual_down

            predictions.append(
                {
                    "index": idx,
                    "direction": forecast["direction"],
                    "score": _score_for_mode(forecast, mode),
                    "future_return_pct": round(future_return_pct, 4),
                    "correct": correct,
                }
            )

        if not predictions:
            return ForgeBacktestResult(
                asset=asset.upper(),
                horizon=horizon,
                mode=mode,
                samples=0,
                accuracy_pct=None,
                mean_future_return_pct=None,
                mean_score=None,
                predictions=[],
            )

        hits = sum(1 for prediction in predictions if prediction["correct"])
        returns = [prediction["future_return_pct"] for prediction in predictions]
        scores = [prediction["score"] for prediction in predictions]

        return ForgeBacktestResult(
            asset=asset.upper(),
            horizon=horizon,
            mode=mode,
            samples=len(predictions),
            accuracy_pct=round(hits / len(predictions) * 100.0, 2),
            mean_future_return_pct=round(sum(returns) / len(returns), 4),
            mean_score=round(sum(scores) / len(scores), 4),
            predictions=predictions,
        )


def _close(candle: dict[str, Any]) -> float:
    try:
        return float(candle.get("close", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _score_for_mode(forecast: dict[str, Any], mode: str) -> float:
    if mode == "attention":
        return float(forecast["attention_score"])
    if mode == "momentum":
        return float(forecast["momentum_score"])
    if mode == "risk":
        return float(forecast["risk_score"])
    return float(forecast["composite_score"])
