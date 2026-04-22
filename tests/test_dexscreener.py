from datetime import datetime, timezone

from backend.dexscreener import snapshot_from_pairs, snapshot_to_forge_signals


def test_snapshot_selects_highest_liquidity_pair_and_normalizes_signals():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    pairs = [
        {
            "chainId": "base",
            "dexId": "small",
            "pairAddress": "0xsmall",
            "baseToken": {"address": "0xtoken", "name": "Token", "symbol": "TOK"},
            "priceUsd": "0.01",
            "liquidity": {"usd": 10_000},
            "volume": {"h24": 50_000},
            "priceChange": {"h24": 80},
            "txns": {"h24": {"buys": 200, "sells": 10}},
            "pairCreatedAt": now_ms,
        },
        {
            "chainId": "base",
            "dexId": "large",
            "url": "https://dexscreener.com/base/0xlarge",
            "pairAddress": "0xlarge",
            "baseToken": {"address": "0xtoken", "name": "Token", "symbol": "TOK"},
            "priceUsd": "0.02",
            "liquidity": {"usd": 500_000},
            "volume": {"h24": 250_000},
            "priceChange": {"h24": 12},
            "txns": {"h24": {"buys": 120, "sells": 80}},
            "fdv": 1_000_000,
            "marketCap": 900_000,
            "pairCreatedAt": now_ms,
            "boosts": {"active": 1},
        },
    ]

    snapshot = snapshot_from_pairs("base", "0xtoken", pairs)
    signals = snapshot_to_forge_signals(snapshot)

    assert snapshot.pair_address == "0xlarge"
    assert snapshot.symbol == "TOK"
    assert signals["market"]["price_change_pct"] == 12
    assert signals["market"]["liquidity_usd"] == 500_000
    assert signals["market"]["volume_24h"] == 250_000
    assert signals["market"]["buy_sell_imbalance"] == 0.2
    assert signals["security"]["dex_manipulation_risk_score"] > 0
    assert signals["metadata"]["url"] == "https://dexscreener.com/base/0xlarge"
