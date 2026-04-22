import json

import pytest

from backend.trend_prediction import TrendPredictionEngine
from core.tools import execute_tool, get_tool_definitions, load_tools


def test_composite_forecast_promotes_strong_clean_trend():
    engine = TrendPredictionEngine()

    forecast = engine.forecast(
        asset="forge",
        horizon="24h",
        mode="composite",
        market={
            "price_change_pct": 12,
            "volume_growth_pct": 180,
            "liquidity_usd": 4_000_000,
            "volatility_pct": 9,
            "rsi": 62,
        },
        social={
            "mention_growth_pct": 220,
            "engagement_growth_pct": 190,
            "sentiment_score": 0.58,
            "unique_author_count": 480,
            "bot_ratio": 0.08,
        },
        onchain={
            "top_holder_pct": 18,
            "whale_exchange_inflow_pct": 2,
            "holder_growth_pct": 14,
        },
        security={"contract_risk_score": 12, "honeypot": False},
        narrative={"catalyst_score": 82},
    )

    result = forecast.to_dict()

    assert result["asset"] == "FORGE"
    assert result["direction"] == "up_trend_likely"
    assert result["attention_score"] >= 70
    assert result["momentum_score"] >= 65
    assert result["risk_score"] < 40
    assert result["confidence"] >= 0.7
    assert result["drivers"]


def test_honeypot_forces_high_risk_warning():
    engine = TrendPredictionEngine()

    forecast = engine.forecast(
        asset="risk",
        mode="composite",
        market={
            "price_change_pct": 25,
            "volume_growth_pct": 250,
            "liquidity_usd": 30_000,
            "volatility_pct": 35,
            "rsi": 86,
        },
        social={
            "mention_growth_pct": 500,
            "engagement_growth_pct": 400,
            "sentiment_score": 0.7,
            "unique_author_count": 35,
            "bot_ratio": 0.5,
        },
        onchain={
            "top_holder_pct": 72,
            "whale_exchange_inflow_pct": 35,
            "holder_growth_pct": -8,
        },
        security={"contract_risk_score": 95, "honeypot": True},
        narrative={"catalyst_score": 90},
    )

    result = forecast.to_dict()

    assert result["direction"] == "avoid_high_risk"
    assert result["risk_score"] == 100
    assert any("honeypot" in warning.lower() for warning in result["warnings"])
    assert result["confidence"] < 0.7


def test_dex_manipulation_risk_contributes_to_risk_score():
    engine = TrendPredictionEngine()

    forecast = engine.forecast(
        asset="thin",
        mode="risk",
        market={
            "price_change_pct": 55,
            "volume_growth_pct": 250,
            "liquidity_usd": 40_000,
            "volatility_pct": 55,
            "rsi": 92,
        },
        social={"bot_ratio": 0.2},
        security={"dex_manipulation_risk_score": 85},
    )

    result = forecast.to_dict()

    assert result["direction"] in {"risk_elevated", "risk_spiking"}
    assert result["risk_score"] >= 45
    assert any("dex manipulation" in warning.lower() for warning in result["warnings"])


def test_forge_tool_is_registered_and_returns_json():
    load_tools(force_reload=True)

    names = {tool["name"] for tool in get_tool_definitions()}
    assert "forge_token_prediction" in names

    raw = execute_tool(
        "forge_token_prediction",
        {
            "asset": "SOL",
            "horizon": "4h",
            "mode": "attention",
            "market": {"volume_growth_pct": 120, "liquidity_usd": 3_000_000},
            "social": {
                "mention_growth_pct": 160,
                "engagement_growth_pct": 100,
                "sentiment_score": 0.4,
                "unique_author_count": 300,
            },
        },
    )

    payload = json.loads(raw)
    assert payload["asset"] == "SOL"
    assert payload["mode"] == "attention"
    assert payload["attention_score"] > 50


def test_invalid_horizon_is_rejected():
    engine = TrendPredictionEngine()

    with pytest.raises(ValueError):
        engine.forecast(asset="BTC", horizon="30d")


def test_live_forge_tool_returns_forecast_with_signal_inputs(monkeypatch):
    from backend.trend_signal_collector import CollectedSignals
    from tools import trend_prediction_tools

    def fake_collect(self, asset, token_address=None, chain="base", historical_limit=72):
        return CollectedSignals(
            market={
                "price_change_pct": 8,
                "volume_growth_pct": 140,
                "liquidity_usd": 2_500_000,
                "volatility_pct": 8,
                "rsi": 59,
            },
            social={
                "mention_growth_pct": 120,
                "engagement_growth_pct": 95,
                "sentiment_score": 0.36,
                "unique_author_count": 180,
                "bot_ratio": 0.05,
            },
            onchain={
                "top_holder_pct": 20,
                "whale_exchange_inflow_pct": 3,
                "holder_growth_pct": 8,
            },
            security={"contract_risk_score": 10, "honeypot": False},
            narrative={"catalyst_score": 50},
            data_quality={"sources": ["test"], "errors": []},
        )

    monkeypatch.setattr(trend_prediction_tools.TrendSignalCollector, "collect", fake_collect)

    raw = trend_prediction_tools.forge_live_token_prediction(
        asset="forge",
        token_address="0xabc",
        horizon="24h",
        mode="composite",
    )
    payload = json.loads(raw)

    assert payload["asset"] == "FORGE"
    assert payload["signal_inputs"]["market"]["volume_growth_pct"] == 140
    assert payload["data_quality"]["sources"] == ["test"]
    assert payload["confidence"] > 0.5


def test_live_forge_tool_accepts_contract_only(monkeypatch):
    from backend.trend_signal_collector import CollectedSignals
    from tools import trend_prediction_tools

    def fake_collect(self, asset, token_address=None, chain="base", historical_limit=72):
        return CollectedSignals(
            market={
                "price_change_pct": 5,
                "volume_growth_pct": 70,
                "liquidity_usd": 800_000,
                "volatility_pct": 7,
                "rsi": 55,
            },
            social={"sentiment_score": 0.2},
            onchain={},
            security={"dex_manipulation_risk_score": 15},
            narrative={"catalyst_score": 20},
            metadata={"resolved_asset": "TOSHI"},
            data_quality={"sources": ["dexscreener"], "errors": []},
        )

    monkeypatch.setattr(trend_prediction_tools.TrendSignalCollector, "collect", fake_collect)

    raw = trend_prediction_tools.forge_live_token_prediction(token_address="0xabc", chain="base")
    payload = json.loads(raw)

    assert payload["asset"] == "TOSHI"
    assert payload["metadata"]["resolved_asset"] == "TOSHI"
    assert payload["signal_inputs"]["security"]["dex_manipulation_risk_score"] == 15


def test_record_and_summarize_forge_prediction_tools(monkeypatch, tmp_path):
    from backend.trend_signal_collector import CollectedSignals
    from tools import trend_prediction_tools

    monkeypatch.setenv("TREND_PREDICTION_LEDGER_PATH", str(tmp_path / "trend_ledger.json"))

    def fake_collect(self, asset, token_address=None, chain="base", historical_limit=72):
        return CollectedSignals(
            market={
                "price_change_pct": 8,
                "volume_growth_pct": 140,
                "liquidity_usd": 2_500_000,
                "volatility_pct": 8,
                "rsi": 59,
            },
            social={
                "mention_growth_pct": 120,
                "engagement_growth_pct": 95,
                "sentiment_score": 0.36,
                "unique_author_count": 180,
                "bot_ratio": 0.05,
            },
            onchain={
                "top_holder_pct": 20,
                "whale_exchange_inflow_pct": 3,
                "holder_growth_pct": 8,
            },
            security={"contract_risk_score": 10, "honeypot": False},
            narrative={"catalyst_score": 50},
            data_quality={"sources": ["test"], "errors": []},
        )

    monkeypatch.setattr(trend_prediction_tools.TrendSignalCollector, "collect", fake_collect)

    raw_record = trend_prediction_tools.forge_record_live_prediction(
        asset="forge",
        token_address="0xabc",
        horizon="1h",
        mode="composite",
    )
    record = json.loads(raw_record)
    raw_summary = trend_prediction_tools.forge_prediction_ledger_summary()
    summary = json.loads(raw_summary)

    assert record["prediction_id"].startswith("trend_")
    assert record["status"] == "pending"
    assert summary["total_predictions"] == 1
    assert summary["pending"] == 1


def test_forge_watchlist_tools(monkeypatch, tmp_path):
    from tools import trend_prediction_tools

    monkeypatch.setenv("TREND_FORGE_WATCHLIST_PATH", str(tmp_path / "watchlist.json"))

    raw_watch = trend_prediction_tools.forge_add_watch(asset="eth", horizons=["1h"], modes=["composite"])
    watch = json.loads(raw_watch)
    raw_list = trend_prediction_tools.forge_list_watches()
    watches = json.loads(raw_list)
    delete_msg = trend_prediction_tools.forge_delete_watch(watch["watch_id"])

    assert watch["asset"] == "ETH"
    assert len(watches) == 1
    assert "Deleted forge watch" in delete_msg


def test_forge_summary_accepts_float_limit(monkeypatch, tmp_path):
    from tools import trend_prediction_tools

    monkeypatch.setenv("TREND_PREDICTION_LEDGER_PATH", str(tmp_path / "ledger.json"))

    summary = json.loads(trend_prediction_tools.forge_prediction_ledger_summary(limit=10.0))

    assert summary["total_predictions"] == 0


def test_forge_list_watches_falls_back_to_global_watches(monkeypatch, tmp_path):
    from tools import trend_prediction_tools

    monkeypatch.setenv("TREND_FORGE_WATCHLIST_PATH", str(tmp_path / "watchlist.json"))
    trend_prediction_tools.forge_add_watch(asset="toby", horizons=["4h"], modes=["composite"])

    watches = json.loads(trend_prediction_tools.forge_list_watches(active_only=True, user_id=6095539526.0))

    assert len(watches) == 1
    assert watches[0]["asset"] == "TOBY"


def test_forge_alert_tools(monkeypatch, tmp_path):
    from backend.trend_alerts import TrendForgeAlertStore
    from tools import trend_prediction_tools

    monkeypatch.setenv("TREND_FORGE_ALERTS_PATH", str(tmp_path / "alerts.json"))
    TrendForgeAlertStore().add_many([{"asset": "ETH", "watch_id": "watch_1", "metric": "risk_score", "value": 80}])

    raw_alerts = trend_prediction_tools.forge_list_alerts(asset="ETH")
    alerts = json.loads(raw_alerts)
    clear_msg = trend_prediction_tools.forge_clear_alerts()

    assert alerts[0]["metric"] == "risk_score"
    assert "Cleared 1" in clear_msg
