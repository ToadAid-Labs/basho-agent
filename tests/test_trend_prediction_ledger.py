from datetime import datetime, timedelta, timezone

from backend.trend_prediction import TrendPredictionEngine
from backend.trend_prediction_ledger import TrendPredictionLedger


def _signals(price_change=9.0, volume_growth=120.0, sentiment=0.35):
    return {
        "market": {
            "price_change_pct": price_change,
            "volume_growth_pct": volume_growth,
            "liquidity_usd": 2_000_000,
            "volatility_pct": 8,
            "rsi": 58,
        },
        "social": {
            "mention_growth_pct": 100,
            "engagement_growth_pct": 80,
            "sentiment_score": sentiment,
            "unique_author_count": 200,
            "bot_ratio": 0.05,
        },
        "onchain": {
            "top_holder_pct": 20,
            "whale_exchange_inflow_pct": 3,
            "holder_growth_pct": 8,
        },
        "security": {"contract_risk_score": 10, "honeypot": False},
        "narrative": {"catalyst_score": 60},
        "data_quality": {"sources": ["test"], "errors": []},
    }


def test_ledger_records_forecast_and_summarizes_pending(tmp_path):
    ledger = TrendPredictionLedger(path=tmp_path / "trend_ledger.json")
    inputs = _signals()
    forecast = TrendPredictionEngine().forecast(
        asset="forge",
        horizon="1h",
        mode="composite",
        market=inputs["market"],
        social=inputs["social"],
        onchain=inputs["onchain"],
        security=inputs["security"],
        narrative=inputs["narrative"],
    )

    record = ledger.record(
        forecast=forecast,
        signal_inputs={key: inputs[key] for key in ["market", "social", "onchain", "security", "narrative"]},
        data_quality=inputs["data_quality"],
        token_address="0xabc",
    )
    summary = ledger.summary()

    assert record["prediction_id"].startswith("trend_")
    assert record["status"] == "pending"
    assert summary["total_predictions"] == 1
    assert summary["pending"] == 1
    assert summary["evaluated"] == 0


def test_ledger_evaluates_due_forecast(tmp_path):
    ledger = TrendPredictionLedger(path=tmp_path / "trend_ledger.json")
    inputs = _signals()
    forecast = TrendPredictionEngine().forecast(
        asset="forge",
        horizon="1h",
        mode="momentum",
        market=inputs["market"],
        social=inputs["social"],
        onchain=inputs["onchain"],
        security=inputs["security"],
        narrative=inputs["narrative"],
    )
    ledger.record(
        forecast=forecast,
        signal_inputs={key: inputs[key] for key in ["market", "social", "onchain", "security", "narrative"]},
        data_quality=inputs["data_quality"],
    )

    records = ledger.load()
    records[0]["due_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    ledger.save(records)

    evaluated = ledger.evaluate_due(lambda record: _signals(price_change=10.0, volume_growth=130.0))
    summary = ledger.summary()

    assert len(evaluated) == 1
    assert evaluated[0]["status"] == "evaluated"
    assert evaluated[0]["actual_forecast"]["mode"] == "momentum"
    assert evaluated[0]["direction_correct"] is True
    assert evaluated[0]["score_error"] >= 0
    assert summary["evaluated"] == 1
    assert summary["direction_accuracy_pct"] == 100.0
    assert summary["mode_breakdown"]["momentum"]["evaluated"] == 1


def test_ledger_respects_due_time(tmp_path):
    ledger = TrendPredictionLedger(path=tmp_path / "trend_ledger.json")
    inputs = _signals()
    forecast = TrendPredictionEngine().forecast(
        asset="forge",
        horizon="24h",
        mode="attention",
        market=inputs["market"],
        social=inputs["social"],
        onchain=inputs["onchain"],
        security=inputs["security"],
        narrative=inputs["narrative"],
    )
    ledger.record(
        forecast=forecast,
        signal_inputs={key: inputs[key] for key in ["market", "social", "onchain", "security", "narrative"]},
    )

    assert ledger.evaluate_due(lambda record: _signals()) == []
    assert ledger.summary()["pending"] == 1
