import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _login(client):
    with client.session_transaction() as session:
        session["logged_in"] = True


def test_forge_ledger_summary_api(monkeypatch):
    import backend.app as app_module

    monkeypatch.setattr(app_module, "evaluate_due_predictions", lambda asset=None, evaluate_all=False: [])

    class FakeLedger:
        def summary(self, asset=None, limit=100):
            return {
                "asset": asset or "ALL",
                "total_predictions": 1,
                "evaluated": 0,
                "pending": 1,
            }

    monkeypatch.setattr(app_module, "TrendPredictionLedger", FakeLedger)

    client = app_module.app.test_client()
    _login(client)

    response = client.get("/api/ai/forge/ledger?asset=ETH")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["asset"] == "ETH"
    assert payload["newly_evaluated"] == 0


def test_record_forge_prediction_api_requires_asset():
    import backend.app as app_module

    client = app_module.app.test_client()
    _login(client)

    response = client.post("/api/ai/forge/record", json={})

    assert response.status_code == 400
    assert response.get_json()["error"] == "asset or token_address is required"


def test_forge_backtest_api(monkeypatch):
    import backend.app as app_module

    monkeypatch.setattr(
        app_module,
        "run_live_backtest",
        lambda **kwargs: {
            "asset": kwargs["asset"],
            "samples": 12,
            "accuracy_pct": 66.67,
        },
    )

    client = app_module.app.test_client()
    _login(client)

    response = client.post("/api/ai/forge/backtest", json={"asset": "SOL"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["asset"] == "SOL"
    assert payload["samples"] == 12


def test_forge_watchlist_api(monkeypatch, tmp_path):
    monkeypatch.setenv("TREND_FORGE_WATCHLIST_PATH", str(tmp_path / "watchlist.json"))

    import backend.app as app_module

    client = app_module.app.test_client()
    _login(client)

    create = client.post("/api/ai/forge/watchlist", json={"asset": "ETH", "horizons": ["1h"]})
    watch = create.get_json()
    listing = client.get("/api/ai/forge/watchlist").get_json()
    delete = client.delete(f"/api/ai/forge/watchlist/{watch['watch_id']}")

    assert create.status_code == 200
    assert watch["asset"] == "ETH"
    assert len(listing) == 1
    assert delete.get_json()["deleted"] is True


def test_forge_watchlist_run_api(monkeypatch):
    import backend.app as app_module

    monkeypatch.setattr(
        app_module,
        "process_due_watchlist",
        lambda force=False: {"processed": [{"watch_id": "watch_test", "records": 1, "alerts": []}], "alerts": []},
    )

    client = app_module.app.test_client()
    _login(client)

    response = client.post("/api/ai/forge/watchlist/run", json={"force": True})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["processed"][0]["records"] == 1


def test_forge_alerts_api(monkeypatch, tmp_path):
    monkeypatch.setenv("TREND_FORGE_ALERTS_PATH", str(tmp_path / "alerts.json"))

    from backend.trend_alerts import TrendForgeAlertStore
    import backend.app as app_module

    TrendForgeAlertStore().add_many([{"asset": "ETH", "watch_id": "watch_1", "metric": "risk_score", "value": 80}])

    client = app_module.app.test_client()
    _login(client)

    response = client.get("/api/ai/forge/alerts?asset=ETH")
    payload = response.get_json()
    clear = client.delete("/api/ai/forge/alerts")

    assert response.status_code == 200
    assert payload[0]["asset"] == "ETH"
    assert clear.get_json()["cleared"] == 1
