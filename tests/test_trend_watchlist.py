from backend.trend_forge_service import process_due_watchlist
from backend.trend_alerts import TrendForgeAlertStore
from backend.trend_prediction_ledger import TrendPredictionLedger
from backend.trend_watchlist import TrendForgeWatchlist


def test_watchlist_add_list_delete(tmp_path):
    store = TrendForgeWatchlist(path=tmp_path / "watchlist.json")

    watch = store.add(asset="eth", horizons=["1h"], modes=["composite"], interval_minutes=15)

    assert watch["watch_id"].startswith("watch_")
    assert watch["asset"] == "ETH"
    assert store.list()[0]["interval_minutes"] == 15
    assert store.delete(watch["watch_id"]) is True
    assert store.list() == []


def test_process_due_watchlist_records_and_emits_alert(monkeypatch, tmp_path):
    store = TrendForgeWatchlist(path=tmp_path / "watchlist.json")
    ledger = TrendPredictionLedger(path=tmp_path / "ledger.json")
    alert_store = TrendForgeAlertStore(path=tmp_path / "alerts.json")
    store.add(
        asset="ETH",
        horizons=["1h"],
        modes=["composite"],
        thresholds={"attention_score": 1, "risk_score": 99, "confidence": 0.1},
    )

    from backend.trend_signal_collector import CollectedSignals
    import backend.trend_forge_service as service

    def fake_collect(self, asset, token_address=None, chain="base", historical_limit=72):
        return CollectedSignals(
            market={
                "price_change_pct": 8,
                "volume_growth_pct": 160,
                "liquidity_usd": 5_000_000,
                "volatility_pct": 5,
                "rsi": 58,
            },
            social={
                "mention_growth_pct": 180,
                "engagement_growth_pct": 120,
                "sentiment_score": 0.4,
                "unique_author_count": 300,
                "bot_ratio": 0.02,
            },
            onchain={"top_holder_pct": 10, "whale_exchange_inflow_pct": 1, "holder_growth_pct": 10},
            security={"contract_risk_score": 5},
            narrative={"catalyst_score": 70},
            data_quality={"sources": ["test"], "errors": []},
        )

    monkeypatch.setattr(service.TrendSignalCollector, "collect", fake_collect)

    result = process_due_watchlist(watchlist=store, ledger=ledger, alert_store=alert_store, force=True)

    assert result["processed"][0]["records"] == 1
    assert result["alerts"]
    assert result["stored_alerts"] == len(result["alerts"])
    assert alert_store.list()
    assert ledger.summary()["total_predictions"] == 1
    assert store.list()[0]["last_recorded_at"] is not None
