import json

import tools.trade_decision as trade_decision


def test_trade_decision_engine_buy_signal(monkeypatch):
    monkeypatch.setattr(trade_decision, "fetch_ticker", lambda symbol: json.dumps({"price": 100.0}))
    monkeypatch.setattr(
        trade_decision,
        "get_pro_indicators",
        lambda symbol: json.dumps(
            {
                "symbol": symbol,
                "trend": "UP",
                "trend_strength": "STRONG (ADX: 32.10)",
                "momentum": "NEUTRAL (RSI: 45.00)",
                "volatility": "2.00% (ATR)",
            }
        ),
    )
    monkeypatch.setattr(
        trade_decision,
        "get_multi_timeframe_signal",
        lambda symbol: json.dumps(
            {
                "symbol": symbol,
                "timeframe_signals": {"1h": "BULLISH", "4h": "BULLISH", "1d": "BULLISH"},
                "aggregated_recommendation": "STRONG_BUY",
            }
        ),
    )
    monkeypatch.setattr(
        trade_decision,
        "get_swing_setup",
        lambda symbol, timeframe="4h": json.dumps(
            {
                "symbol": symbol,
                "setup_quality": "PREMIUM (Bullish Pullback + RSI Divergence)",
                "analysis": {
                    "anchor_trend": "BULLISH",
                    "rsi_divergence": "BULLISH_DIVERGENCE",
                    "current_price": 100.0,
                },
                "golden_pocket_zone": {
                    "fib_0.5": 102.0,
                    "fib_0.618": 99.0,
                    "fib_0.786": 95.0,
                    "status": "IN_ZONE",
                },
                "trade_plan": {
                    "entry_range": "99.0 - 102.0",
                    "stop_loss": 95.0,
                    "take_profit": 120.0,
                    "risk_reward_ratio": "1:2.0",
                },
            }
        ),
    )
    monkeypatch.setattr(
        trade_decision,
        "analyze_market_trend",
        lambda symbol, period=24: "📊 Market Analysis for ETH\nBollinger Status: BELOW\n   🟢 Potential BUY - Price below lower band",
    )
    monkeypatch.setattr(
        trade_decision,
        "analyze_market_structure",
        lambda symbol, lookback=300: json.dumps(
            {
                "symbol": symbol,
                "major_resistance": [130.0, 140.0],
                "major_support": [96.0, 92.0],
                "recent_fair_value_gaps": [],
                "current_price": 100.0,
            }
        ),
    )

    result = json.loads(trade_decision.trade_decision_engine("ETH"))

    assert result["action"] == "BUY"
    assert result["direction"] == "LONG"
    assert result["risk_plan"]["quantity"] > 0
    assert result["risk_plan"]["stop_loss"] == 95.0
    assert result["risk_plan"]["take_profit"] == 120.0
    assert result["confidence"] > 0.6


def test_trade_decision_engine_btc_rsi_veto(monkeypatch):
    monkeypatch.setattr(trade_decision, "fetch_ticker", lambda symbol: json.dumps({"price": 50000.0}))
    monkeypatch.setattr(
        trade_decision,
        "get_pro_indicators",
        lambda symbol: json.dumps(
            {
                "symbol": symbol,
                "trend": "UP",
                "trend_strength": "STRONG (ADX: 40.00)",
                "momentum": "OVERBOUGHT (RSI: 99.00)",
                "volatility": "3.00% (ATR)",
            }
        ),
    )
    monkeypatch.setattr(
        trade_decision,
        "get_multi_timeframe_signal",
        lambda symbol: json.dumps(
            {
                "symbol": symbol,
                "timeframe_signals": {"1h": "BULLISH", "4h": "BULLISH", "1d": "BULLISH"},
                "aggregated_recommendation": "STRONG_BUY",
            }
        ),
    )
    monkeypatch.setattr(
        trade_decision,
        "get_swing_setup",
        lambda symbol, timeframe="4h": json.dumps(
            {
                "symbol": symbol,
                "setup_quality": "PREMIUM",
                "analysis": {"anchor_trend": "BULLISH", "current_price": 50000.0},
                "golden_pocket_zone": {"status": "IN_ZONE"},
                "trade_plan": {
                    "entry_range": "49000 - 51000",
                    "stop_loss": 47000.0,
                    "take_profit": 56000.0,
                    "risk_reward_ratio": "1:2.0",
                },
            }
        ),
    )
    monkeypatch.setattr(
        trade_decision,
        "analyze_market_trend",
        lambda symbol, period=24: "📊 Market Analysis for BTC\nBollinger Status: BELOW\n   🟢 Potential BUY - Price below lower band",
    )
    monkeypatch.setattr(
        trade_decision,
        "analyze_market_structure",
        lambda symbol, lookback=300: json.dumps(
            {
                "symbol": symbol,
                "major_resistance": [53000.0],
                "major_support": [48000.0],
                "recent_fair_value_gaps": [],
                "current_price": 50000.0,
            }
        ),
    )

    result = json.loads(trade_decision.trade_decision_engine("BTC"))

    assert result["action"] == "WAIT"
    assert any("BTC RSI is 99 or higher" in veto for veto in result["vetoes"])
