from types import SimpleNamespace

import pytest

from memory import alerts as alert_memory
from memory.alerts import AlertStore
from tools.wallet_activity import check_wallet_activity


def test_alert_store_persists_wallet_activity_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(alert_memory, "DEFAULT_ALERTS_PATH", tmp_path / "alerts.json")

    store = AlertStore()
    alert_id = store.add_alert(
        alert_type="WALLET_ACTIVITY",
        symbol="WALLET:DDDA0",
        condition="activity",
        value=0.0,
        target_user_id=6095539526,
        wallet_address="0x7daD356c8f480509d5761c208dC4ECb2518dDDA0",
        chain="base",
        last_seen_tx_hash="0xabc123",
        watch_mode="wallet_activity",
    )

    alerts = store.list_alerts()
    assert len(alerts) == 1
    assert alerts[0]["id"] == alert_id
    assert alerts[0]["wallet_address"] == "0x7daD356c8f480509d5761c208dC4ECb2518dDDA0"
    assert alerts[0]["chain"] == "base"
    assert alerts[0]["last_seen_tx_hash"] == "0xabc123"
    assert alerts[0]["watch_mode"] == "wallet_activity"


def test_wallet_activity_tracker_detects_new_transaction(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "1",
                "message": "OK",
                "result": [
                    {
                        "hash": "0xnewhash",
                        "blockNumber": "12345678",
                        "from": "0x1111111111111111111111111111111111111111",
                        "to": "0x7daD356c8f480509d5761c208dC4ECb2518dDDA0",
                        "value": "0",
                    }
                ],
            }

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("tools.wallet_activity.requests.Session", lambda: FakeSession())
    result = check_wallet_activity(
        wallet_address="0x7daD356c8f480509d5761c208dC4ECb2518dDDA0",
        chain="base",
        last_seen_tx_hash="0xoldhash",
    )

    assert result["has_new_activity"] is True
    assert result["latest_tx_hash"] == "0xnewhash"
    assert result["latest_block_number"] == 12345678

