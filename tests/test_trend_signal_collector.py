import json
import sys
import types

from backend.dexscreener import DexScreenerTokenSnapshot, snapshot_to_forge_signals
from backend.trend_signal_collector import TrendSignalCollector


def test_collector_normalizes_market_social_security_and_whale_signals(monkeypatch):
    candles = []
    price = 100.0
    for idx in range(30):
        price += 1.0
        candles.append(
            {
                "timestamp": idx,
                "open": price - 0.5,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price,
                "volume": 100 + idx * 5,
            }
        )

    trading_data = types.ModuleType("tools.trading_data")
    trading_data.fetch_historical = lambda asset, interval="1h", limit=72: json.dumps(candles)
    trading_data.fetch_ticker = lambda asset: json.dumps(
        {
            "symbol": f"{asset.upper()}USDT",
            "price": 130.0,
            "price_change_pct_24h": 9.5,
            "volume_24h": 25_000,
        }
    )
    monkeypatch.setitem(sys.modules, "tools.trading_data", trading_data)

    sentiment_engine = types.ModuleType("monitoring.sentiment_engine")
    sentiment_engine.analyze_sentiment = lambda asset: {"aggregate_score": 0.42}
    monkeypatch.setitem(sys.modules, "monitoring.sentiment_engine", sentiment_engine)

    security_tools = types.ModuleType("tools.security_tools")
    security_tools.audit_token_contract = lambda token_address, chain="base": (
        "HONEYPOT: ✅ No\n"
        "Mintable: ✅ No\n"
        "Hidden Owner: ✅ No\n"
        "✅ RECOMMENDATION: LOW RISK. Basic security checks passed."
    )
    monkeypatch.setitem(sys.modules, "tools.security_tools", security_tools)

    whale_tracker = types.ModuleType("monitoring.whale_tracker")
    whale_tracker.check_whale_stats = lambda token_address: {
        "large_tx_count": 3,
        "smart_money_count": 4,
        "top_holder_pct": 22,
    }
    monkeypatch.setitem(sys.modules, "monitoring.whale_tracker", whale_tracker)

    dexscreener = types.ModuleType("backend.dexscreener")

    class FakeDexScreenerClient:
        def token_snapshot(self, chain, token_address):
            return None

    dexscreener.DexScreenerClient = FakeDexScreenerClient
    dexscreener.snapshot_to_forge_signals = lambda snapshot: {}
    monkeypatch.setitem(sys.modules, "backend.dexscreener", dexscreener)

    signals = TrendSignalCollector().collect("forge", token_address="0xabc", historical_limit=30)

    assert signals.market["price_change_pct"] > 20
    assert signals.market["volume_growth_pct"] > 0
    assert signals.market["liquidity_usd"] > 0
    assert signals.social["sentiment_score"] == 0.42
    assert signals.security["contract_risk_score"] == 15
    assert signals.security["honeypot"] is False
    assert signals.onchain["top_holder_pct"] == 22
    assert signals.onchain["whale_exchange_inflow_pct"] == 7.5
    assert signals.narrative["catalyst_score"] > 0
    assert "historical_ohlcv" in signals.data_quality["sources"]


def test_collector_uses_dexscreener_contract_resolution(monkeypatch):
    trading_data = types.ModuleType("tools.trading_data")
    trading_data.fetch_historical = lambda asset, interval="1h", limit=72: "[error] unavailable"
    trading_data.fetch_ticker = lambda asset: "[error] unavailable"
    monkeypatch.setitem(sys.modules, "tools.trading_data", trading_data)

    sentiment_engine = types.ModuleType("monitoring.sentiment_engine")
    sentiment_engine.analyze_sentiment = lambda asset: {"aggregate_score": 0.2 if asset == "TOSHI" else 0.0}
    monkeypatch.setitem(sys.modules, "monitoring.sentiment_engine", sentiment_engine)

    security_tools = types.ModuleType("tools.security_tools")
    security_tools.audit_token_contract = lambda token_address, chain="base": "✅ RECOMMENDATION: LOW RISK."
    monkeypatch.setitem(sys.modules, "tools.security_tools", security_tools)

    whale_tracker = types.ModuleType("monitoring.whale_tracker")
    whale_tracker.check_whale_stats = lambda token_address: {}
    monkeypatch.setitem(sys.modules, "monitoring.whale_tracker", whale_tracker)

    dexscreener = types.ModuleType("backend.dexscreener")

    class FakeDexScreenerClient:
        def token_snapshot(self, chain, token_address):
            return DexScreenerTokenSnapshot(
                chain_id=chain,
                token_address=token_address,
                symbol="TOSHI",
                name="Toshi",
                pair_address="0xpair",
                dex_id="uniswap",
                url="https://dexscreener.com/base/0xpair",
                price_usd=0.001,
                liquidity_usd=500_000,
                volume_24h=250_000,
                price_change_24h=12.5,
                buys_24h=120,
                sells_24h=80,
                pair_age_hours=240,
            )

    dexscreener.DexScreenerClient = FakeDexScreenerClient
    dexscreener.snapshot_to_forge_signals = snapshot_to_forge_signals
    monkeypatch.setitem(sys.modules, "backend.dexscreener", dexscreener)

    signals = TrendSignalCollector().collect("0xabc", token_address="0xabc", chain="base")

    assert signals.metadata["resolved_asset"] == "TOSHI"
    assert signals.metadata["dexscreener"]["pair_address"] == "0xpair"
    assert signals.market["price_change_pct"] == 12.5
    assert signals.market["liquidity_usd"] == 500_000
    assert signals.social["sentiment_score"] == 0.2
    assert signals.security["dex_manipulation_risk_score"] < 50
    assert "dexscreener" in signals.data_quality["sources"]


def test_collector_degrades_without_token_address(monkeypatch):
    trading_data = types.ModuleType("tools.trading_data")
    trading_data.fetch_historical = lambda asset, interval="1h", limit=72: "[error] unavailable"
    trading_data.fetch_ticker = lambda asset: "[error] unavailable"
    monkeypatch.setitem(sys.modules, "tools.trading_data", trading_data)

    sentiment_engine = types.ModuleType("monitoring.sentiment_engine")
    sentiment_engine.analyze_sentiment = lambda asset: {"aggregate_score": -0.1}
    monkeypatch.setitem(sys.modules, "monitoring.sentiment_engine", sentiment_engine)

    signals = TrendSignalCollector().collect("missing")

    assert signals.social["sentiment_score"] == -0.1
    assert signals.security == {}
    assert signals.onchain == {}
    assert any("token_address not supplied" in error for error in signals.data_quality["errors"])
