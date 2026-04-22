import sqlite3

from memory.continuity import ContinuityStore
from memory import store as session_store


def test_continuity_store_persists_messages_across_instances(tmp_path):
    db_path = tmp_path / "continuity.sqlite3"
    first = ContinuityStore(db_path)
    messages = [
        {"role": "user", "content": "Track ETH into the CPI print."},
        {"role": "assistant", "content": [{"type": "text", "text": "Watching ETH risk."}]},
    ]

    first.save_messages("sid1", messages, user_id=123, thread_id="telegram:123")

    second = ContinuityStore(db_path)
    sid, loaded = second.load_last_session(thread_id="telegram:123")

    assert sid == "sid1"
    assert loaded == messages


def test_continuity_store_schema_has_summary_and_decision_seams(tmp_path):
    db_path = tmp_path / "continuity.sqlite3"
    ContinuityStore(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {"sessions", "messages", "summaries", "trading_decisions"} <= tables


def test_continuity_store_records_trading_decision_seam(tmp_path):
    db_path = tmp_path / "continuity.sqlite3"
    continuity = ContinuityStore(db_path)
    continuity.upsert_session("sid1", thread_id="anthropic")

    decision_id = continuity.record_trading_decision(
        session_id="sid1",
        symbol="ETH",
        action="WATCH",
        confidence=0.61,
        regime="neutral",
        forge_signals={"risk": 0.2},
        technical_snapshot={"rsi": 51},
        reasoning="Waiting for confirmation.",
        linked_prediction_id="pred_123",
        outcome_status="pending",
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT symbol, action, linked_prediction_id, forge_signals_json
            FROM trading_decisions
            WHERE id = ?
            """,
            (decision_id,),
        ).fetchone()

    assert row == ("ETH", "WATCH", "pred_123", '{"risk": 0.2}')


def test_continuity_store_creates_bounded_summary_without_deleting_messages(tmp_path):
    db_path = tmp_path / "continuity.sqlite3"
    continuity = ContinuityStore(db_path)
    messages = [{"role": "user", "content": f"message {i}"} for i in range(25)]

    continuity.save_messages("sid1", messages, thread_id="anthropic")
    summary = continuity.maybe_summarize(
        "sid1",
        raw_context_messages=10,
        threshold_messages=20,
    )

    assert summary
    assert "message 14" in summary
    assert len(continuity.load_messages("sid1")) == 25


def test_session_store_loads_sqlite_before_json_and_can_reset_thread(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_CONTINUITY_DB_PATH", str(tmp_path / "continuity.sqlite3"))
    monkeypatch.setattr(session_store, "SESSION_DIR", tmp_path / "sessions")

    session_store.save_session_for_provider(
        "sid1",
        [{"role": "user", "content": "Remember SOL watch."}],
        provider="anthropic",
        thread_id="telegram:7",
        user_id=7,
    )

    sid, messages = session_store.load_last_session_for_thread("telegram:7")
    assert sid == "sid1"
    assert messages[-1]["content"] == "Remember SOL watch."

    session_store.reset_sessions_for_thread("telegram:7")
    assert session_store.load_last_session_for_thread("telegram:7") == (None, [])
