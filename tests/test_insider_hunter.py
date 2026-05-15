from __future__ import annotations

from datetime import timedelta

from core.tools import get_tool_metadata
from tools.insider_hunter import (
    WATCHLIST_WARNING,
    BuyEvent,
    CandidateToken,
    HuntConfig,
    InsiderHuntEngine,
    StaticInsiderDataProvider,
    detect_clusters,
    extract_early_buyers,
    parse_audit_result,
    score_wallet,
    _utcnow,
)


def _token(
    address: str,
    symbol: str = "WIN",
    unit_price: float = 0.00001,
    liquidity_usd: float = 100_000.0,
    liquidity_status: str = "locked",
    gain: float = 1500.0,
    market_timestamp=None,
):
    return CandidateToken(
        address=address,
        symbol=symbol,
        name=f"{symbol} Token",
        unit_price=unit_price,
        liquidity_usd=liquidity_usd,
        liquidity_status=liquidity_status,
        price_change_pct_48h=gain,
        market_timestamp=market_timestamp if market_timestamp is not None else _utcnow(),
        data_sources=["fixture"],
    )


def _buy_at(wallet: str, token: str, amount_usd: float, timestamp, tx_hash: str, **kwargs):
    return BuyEvent(
        wallet_address=wallet,
        token_address=token,
        amount_usd=amount_usd,
        timestamp=timestamp,
        tx_hash=tx_hash,
        data_sources=["fixture"],
        **kwargs,
    )


def _alpha_history(multiplier: float = 6.0) -> list[dict]:
    return [
        {
            "token_address": f"0x{i:040x}",
            "invested_usd": 100.0,
            "exit_value_usd": 100.0 * multiplier,
        }
        for i in range(10)
    ]


def _early_buyer_context(token_address: str) -> dict:
    base = _utcnow() - timedelta(hours=20)
    return {
        "buy_events": [
            _buy_at("0xa", token_address, 600.0, base + timedelta(minutes=5), "0x1"),
            _buy_at("0xb", token_address, 600.0, base + timedelta(minutes=6), "0x2"),
            _buy_at("0xc", token_address, 600.0, base + timedelta(minutes=7), "0x3"),
            _buy_at("0xd", token_address, 600.0, base + timedelta(minutes=8), "0x4"),
        ],
        "volume_candles": [
            {"timestamp": (base + timedelta(minutes=0)).isoformat(), "volume": 10},
            {"timestamp": (base + timedelta(minutes=15)).isoformat(), "volume": 12},
            {"timestamp": (base + timedelta(minutes=30)).isoformat(), "volume": 15},
            {"timestamp": (base + timedelta(minutes=45)).isoformat(), "volume": 20},
            {"timestamp": (base + timedelta(minutes=60)).isoformat(), "volume": 90},
        ],
        "data_sources": ["fixture"],
    }


def test_wallet_scoring_requires_explicit_win_rate_and_roi_thresholds():
    config = HuntConfig()
    score = score_wallet("0xwallet", _alpha_history(), config)

    assert score.is_alpha is True
    assert score.distinct_tokens == 10
    assert score.win_rate == 1.0
    assert score.average_roi_multiple == 6.0


def test_wallet_scoring_marks_estimated_roi_when_realized_values_missing():
    config = HuntConfig()
    history = [
        {
            "token_address": f"0x{i:040x}",
            "invested_usd": 100.0,
            "current_value_usd": 700.0,
        }
        for i in range(10)
    ]

    score = score_wallet("0xwallet", history, config)

    assert score.is_alpha is True
    assert score.confidence == "estimated"
    assert score.assumptions


def test_extract_early_buyers_filters_duplicates_and_post_spike_buys():
    config = HuntConfig(spike_window_candles=2, spike_multiplier=3.0)
    token = _token("0xwinner")
    base = _utcnow() - timedelta(hours=10)
    candles = [
        {"timestamp": base.isoformat(), "volume": 10},
        {"timestamp": (base + timedelta(minutes=15)).isoformat(), "volume": 12},
        {"timestamp": (base + timedelta(minutes=30)).isoformat(), "volume": 80},
    ]
    buyers = [
        _buy_at("0x1", token.address, 600.0, base + timedelta(minutes=5), "0x1"),
        _buy_at("0x1", token.address, 700.0, base + timedelta(minutes=6), "0xdup"),
        _buy_at("0x2", token.address, 300.0, base + timedelta(minutes=10), "0x2"),
        _buy_at("0x3", token.address, 600.0, base + timedelta(minutes=40), "0x3"),
        _buy_at("0xrouter", token.address, 800.0, base + timedelta(minutes=8), "0x4", is_router=True),
    ]

    early_buyers, spike_time, warnings = extract_early_buyers(buyers, candles, config)

    assert warnings == []
    assert spike_time == base + timedelta(minutes=30)
    assert [event.wallet_address for event in early_buyers] == ["0x1"]


def test_cluster_detection_uses_same_four_hour_window_and_dedupes_wallets():
    config = HuntConfig(cluster_window_hours=4, min_cluster_wallets=4)
    token = _token("0xcluster", symbol="CLSTR")
    base = _utcnow()
    events = [
        _buy_at("0xa", token.address, 1000.0, base, "0x1"),
        _buy_at("0xb", token.address, 1000.0, base + timedelta(minutes=30), "0x2"),
        _buy_at("0xc", token.address, 1000.0, base + timedelta(hours=1), "0x3"),
        _buy_at("0xd", token.address, 1000.0, base + timedelta(hours=3), "0x4"),
        _buy_at("0xd", token.address, 1000.0, base + timedelta(hours=3, minutes=5), "0x4dup"),
        _buy_at("0xe", token.address, 1000.0, base + timedelta(hours=5), "0x5"),
    ]

    clusters = detect_clusters(events, {token.address: token}, config)

    assert len(clusters) == 1
    assert len(clusters[0]["wallet_addresses"]) == 4


def test_price_threshold_and_duplicate_candidates_fail_closed():
    rejected = _token("0xdup", unit_price=0.02)
    provider = StaticInsiderDataProvider(candidates=[rejected, rejected])

    result = InsiderHuntEngine(provider=provider, config=HuntConfig()).run()

    assert result["status"] == "no_signal"
    assert any(item["reason"] == "rejected_unit_price_above_threshold" for item in result["rejections"])


def test_rejects_mintable_contracts():
    winner = _token("0xwinner")
    target = _token("0xtarget", symbol="RISK")
    provider = StaticInsiderDataProvider(
        candidates=[winner],
        early_buyer_contexts={winner.address: _early_buyer_context(winner.address)},
        wallet_histories={wallet: _alpha_history() for wallet in ("0xa", "0xb", "0xc", "0xd")},
        recent_wallet_buys=[
            _buy_at("0xa", target.address, 700.0, _utcnow() - timedelta(hours=3), "0x11"),
            _buy_at("0xb", target.address, 700.0, _utcnow() - timedelta(hours=2), "0x12"),
            _buy_at("0xc", target.address, 700.0, _utcnow() - timedelta(hours=1), "0x13"),
            _buy_at("0xd", target.address, 700.0, _utcnow() - timedelta(minutes=30), "0x14"),
        ],
        token_snapshots={target.address: target},
        audits={
            target.address: {
                "is_mintable": True,
                "buy_tax_pct": 1.0,
                "sell_tax_pct": 1.0,
                "source_verified": True,
                "honeypot": False,
                "trading_can_be_disabled": False,
                "can_blacklist_wallets": False,
            }
        },
    )

    result = InsiderHuntEngine(provider=provider).run()

    assert result["signals"][0]["status"] == "rejected"
    assert result["signals"][0]["rejection_reason"] == "rejected_mintable_contract"


def test_rejects_tax_and_unverified_source():
    winner = _token("0xwinner")
    target = _token("0xtarget")
    provider = StaticInsiderDataProvider(
        candidates=[winner],
        early_buyer_contexts={winner.address: _early_buyer_context(winner.address)},
        wallet_histories={wallet: _alpha_history() for wallet in ("0xa", "0xb", "0xc", "0xd")},
        recent_wallet_buys=[
            _buy_at("0xa", target.address, 700.0, _utcnow() - timedelta(hours=3), "0x21"),
            _buy_at("0xb", target.address, 700.0, _utcnow() - timedelta(hours=2), "0x22"),
            _buy_at("0xc", target.address, 700.0, _utcnow() - timedelta(hours=1), "0x23"),
            _buy_at("0xd", target.address, 700.0, _utcnow() - timedelta(minutes=30), "0x24"),
        ],
        token_snapshots={target.address: target},
        audits={
            target.address: parse_audit_result(
                "Mintable: ✅ No\nBuy Tax: 6% | Sell Tax: 1%\nsource code unverified\nHONEYPOT: ✅ No\ntrading cannot be disabled\nblacklist no"
            )
        },
    )

    result = InsiderHuntEngine(provider=provider).run()

    assert result["signals"][0]["rejection_reason"] == "rejected_buy_tax_above_threshold"


def test_incomplete_market_data_returns_no_signal():
    incomplete = _token("0xincomplete", market_timestamp=None)
    incomplete.market_timestamp = None
    provider = StaticInsiderDataProvider(candidates=[incomplete])

    result = InsiderHuntEngine(provider=provider).run()

    assert result["status"] == "no_signal"
    assert result["confidence_score"] == 0.0
    assert "data_sources_used" in result
    assert any(item["reason"] == "rejected_incomplete_market_data" for item in result["rejections"])


def test_incomplete_audit_data_rejects_signal_and_output_stays_read_only():
    winner = _token("0xwinner")
    target = _token("0xtarget")
    provider = StaticInsiderDataProvider(
        candidates=[winner],
        early_buyer_contexts={winner.address: _early_buyer_context(winner.address)},
        wallet_histories={wallet: _alpha_history() for wallet in ("0xa", "0xb", "0xc", "0xd")},
        recent_wallet_buys=[
            _buy_at("0xa", target.address, 700.0, _utcnow() - timedelta(hours=3), "0x31"),
            _buy_at("0xb", target.address, 700.0, _utcnow() - timedelta(hours=2), "0x32"),
            _buy_at("0xc", target.address, 700.0, _utcnow() - timedelta(hours=1), "0x33"),
            _buy_at("0xd", target.address, 700.0, _utcnow() - timedelta(minutes=30), "0x34"),
        ],
        token_snapshots={target.address: target},
        audits={target.address: {"is_mintable": False}},
    )

    result = InsiderHuntEngine(provider=provider).run()

    assert result["signals"][0]["rejection_reason"] == "rejected_insufficient_security_data"
    assert result["signals"][0]["warning"] == WATCHLIST_WARNING
    assert result["signals"][0]["confidence_score"] == 0.0
    assert "data_sources_used" in result["signals"][0]
    assert "swap" not in str(result).lower()
    assert "buy now" not in str(result).lower()
    assert "guaranteed" not in str(result).lower()
    assert "auto-trade" not in str(result).lower()


def test_provider_failures_return_error():
    provider = StaticInsiderDataProvider(fail_on={"discover_candidate_tokens"})

    result = InsiderHuntEngine(provider=provider).run()

    assert result["status"] == "error"
    assert result["confidence_score"] == 0.0
    assert "data_sources_used" in result


def test_tool_registry_marks_insider_hunt_as_read_only_watchlist():
    metadata = get_tool_metadata("hunt_insider_wallets")

    assert metadata["read_only"] is True
    assert metadata["requires_human_confirmation"] is True
    assert metadata["live_execution"] is False


def test_no_signal_payload_always_includes_required_top_level_fields():
    provider = StaticInsiderDataProvider(candidates=[])

    result = InsiderHuntEngine(provider=provider).run()

    assert result["status"] == "no_signal"
    assert result["chain"] == "Base"
    assert "generated_at" in result
    assert "signals" in result
    assert "rejections" in result
    assert "confidence_score" in result
    assert "data_sources_used" in result
    assert result["warning"] == WATCHLIST_WARNING
