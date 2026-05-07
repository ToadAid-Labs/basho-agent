from tools import market_report as market_report_module


def test_market_report_combines_core_sections(monkeypatch):
    monkeypatch.setattr(
        market_report_module,
        "fetch_ticker",
        lambda symbol: '{"price": 3000, "change_24h": 2.5}',
    )
    monkeypatch.setattr(
        market_report_module,
        "get_pro_indicators",
        lambda symbol: '{"trend": "UP", "trend_strength": "STRONG (ADX: 30.00)", "momentum": "NEUTRAL (RSI: 55.00)", "summary": "Uptrend."}',
    )
    monkeypatch.setattr(
        market_report_module,
        "get_multi_timeframe_signal",
        lambda symbol: '{"aggregated_recommendation": "STRONG_BUY", "signals": {"1h": "BULLISH"}}',
    )
    monkeypatch.setattr(
        market_report_module,
        "detect_market_regime",
        lambda symbol: '{"regime": "TRENDING", "reasoning": "ADX strong.", "recommended_strategy": "Momentum/Trend-Following"}',
    )
    monkeypatch.setattr(
        market_report_module,
        "get_daily_alpha",
        lambda symbols: "ALPHA\n- ETF chatter\n- Risk-on tone",
    )

    result = market_report_module.market_report(["ETH"])

    assert "MARKET REPORT" in result
    assert "ETH" in result
    assert "Price: $3,000.00 (+2.50% 24h)" in result
    assert "Trend: UP | STRONG (ADX: 30.00)" in result
    assert "MTF: STRONG_BUY" in result
    assert "Regime: TRENDING" in result
    assert "Catalysts" in result
    assert "ETF chatter" in result
