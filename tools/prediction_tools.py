"""
Phase 1A Forecasting Brain tools.
"""

import json
from typing import Optional

from core.tools import register_tool
from backend.prediction_tracker import PredictionLedger
from tools.trading_data import fetch_ticker, fetch_historical


def _current_price(symbol: str) -> Optional[float]:
    try:
        raw = fetch_ticker(symbol)
        if raw.startswith("[error]"):
            return None
        data = json.loads(raw)
        return float(data["price"])
    except Exception:
        return None


@register_tool(
    name="record_price_prediction",
    description="Record a price prediction so it can be evaluated after its horizon.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Symbol, e.g. BTC, ETH, SOL."},
            "predicted_price": {"type": "number", "description": "Predicted future price."},
            "confidence": {"type": "number", "description": "Prediction confidence from 0.0 to 1.0."},
            "horizon_hours": {"type": "integer", "description": "Prediction horizon in hours.", "default": 24},
            "current_price": {"type": "number", "description": "Current price. If omitted, tool fetches it."},
            "model_version": {"type": "string", "description": "Model/version label.", "default": "manual-v1"},
        },
        "required": ["symbol", "predicted_price", "confidence"],
    },
)
def record_price_prediction(
    symbol: str,
    predicted_price: float,
    confidence: float,
    horizon_hours: int = 24,
    current_price: Optional[float] = None,
    model_version: str = "manual-v1",
) -> str:
    price = current_price if current_price is not None else _current_price(symbol)
    if price is None:
        return f"Error: could not fetch current price for {symbol}."

    record = PredictionLedger().record(
        symbol=symbol,
        current_price=price,
        predicted_price=predicted_price,
        confidence=confidence,
        horizon_hours=horizon_hours,
        model_version=model_version,
    )
    return json.dumps(record, indent=2)


@register_tool(
    name="evaluate_price_predictions",
    description="Evaluate due recorded predictions against current prices.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Optional symbol filter."},
            "evaluate_all": {"type": "boolean", "description": "Evaluate pending predictions even if not due yet.", "default": False},
        },
    },
)
def evaluate_price_predictions(symbol: Optional[str] = None, evaluate_all: bool = False) -> str:
    evaluated = PredictionLedger().evaluate_due(_current_price, symbol=symbol, evaluate_all=evaluate_all)
    return json.dumps({"evaluated_count": len(evaluated), "evaluated": evaluated}, indent=2)


@register_tool(
    name="get_prediction_accuracy",
    description="Summarize prediction accuracy and confidence modifier.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Optional symbol filter."},
            "limit": {"type": "integer", "description": "Number of recent evaluated predictions to summarize.", "default": 100},
        },
    },
)
def get_prediction_accuracy(symbol: Optional[str] = None, limit: int = 100) -> str:
    return json.dumps(PredictionLedger().summary(symbol=symbol, limit=limit), indent=2)


@register_tool(
    name="detect_market_regime",
    description="Detect whether a symbol is trending, ranging, or volatile using recent candles.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Symbol, e.g. BTC, ETH, SOL."},
            "interval": {"type": "string", "description": "Candle interval.", "default": "4h"},
            "limit": {"type": "integer", "description": "Number of candles.", "default": 120},
        },
        "required": ["symbol"],
    },
)
def detect_market_regime(symbol: str, interval: str = "4h", limit: int = 120) -> str:
    raw = fetch_historical(symbol, interval=interval, limit=limit)
    if raw.startswith("[error]"):
        return _detect_regime_from_ticker(symbol, raw)

    candles = json.loads(raw)
    closes = [float(c["close"]) for c in candles if c.get("close") is not None]
    highs = [float(c["high"]) for c in candles if c.get("high") is not None]
    lows = [float(c["low"]) for c in candles if c.get("low") is not None]
    if len(closes) < 50:
        return "Error: not enough candle data to classify regime."

    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-50:]) / 50
    slope20 = (sma20 - (sum(closes[-40:-20]) / 20)) / sma20
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1]]
    recent_returns = returns[-20:]
    volatility = (sum((r - (sum(recent_returns) / len(recent_returns))) ** 2 for r in recent_returns) / len(recent_returns)) ** 0.5
    recent_high = max(highs[-20:])
    recent_low = min(lows[-20:])
    range_width = (recent_high - recent_low) / closes[-1]

    if abs(slope20) > 0.025 and abs((sma20 - sma50) / sma50) > 0.015:
        regime = "trending_up" if sma20 > sma50 else "trending_down"
    elif volatility > 0.04 or range_width > 0.18:
        regime = "volatile"
    else:
        regime = "ranging"

    confidence = min(1.0, max(0.35, abs(slope20) * 12 + min(range_width, 0.2)))
    result = {
        "symbol": symbol.upper(),
        "interval": interval,
        "regime": regime,
        "confidence": round(confidence, 3),
        "current_price": closes[-1],
        "sma20": round(sma20, 4),
        "sma50": round(sma50, 4),
        "sma20_slope_pct": round(slope20 * 100, 3),
        "recent_volatility": round(volatility, 5),
        "range_width_pct": round(range_width * 100, 3),
    }
    return json.dumps(result, indent=2)


def _detect_regime_from_ticker(symbol: str, reason: str) -> str:
    raw = fetch_ticker(symbol)
    if raw.startswith("[error]"):
        return reason
    data = json.loads(raw)
    change = data.get("price_change_pct_24h")
    price = data.get("price")
    if change is None:
        return json.dumps(
            {
                "symbol": symbol.upper(),
                "regime": "unknown",
                "confidence": 0.25,
                "current_price": price,
                "source": "ticker_fallback",
                "note": "Historical candles unavailable and ticker has no 24h change.",
            },
            indent=2,
        )

    change = float(change)
    if abs(change) > 8:
        regime = "volatile"
    elif change > 3:
        regime = "trending_up"
    elif change < -3:
        regime = "trending_down"
    else:
        regime = "ranging"
    return json.dumps(
        {
            "symbol": symbol.upper(),
            "regime": regime,
            "confidence": 0.4,
            "current_price": price,
            "price_change_pct_24h": change,
            "source": "ticker_fallback",
            "note": "Historical candles unavailable; regime estimated from 24h ticker only.",
        },
        indent=2,
    )
