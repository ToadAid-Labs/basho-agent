from backend.trend_alerts import TrendForgeAlertStore


def test_alert_store_add_list_filter_and_clear(tmp_path):
    store = TrendForgeAlertStore(path=tmp_path / "alerts.json")
    alerts = [
        {"asset": "ETH", "watch_id": "watch_1", "metric": "risk_score", "value": 80},
        {"asset": "SOL", "watch_id": "watch_2", "metric": "attention_score", "value": 90},
    ]

    assert store.add_many(alerts) == 2
    assert len(store.list()) == 2
    assert store.list(asset="ETH")[0]["watch_id"] == "watch_1"
    assert store.list(watch_id="watch_2")[0]["asset"] == "SOL"
    assert store.clear() == 2
    assert store.list() == []
