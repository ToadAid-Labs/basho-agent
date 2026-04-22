"""
Service helpers for Trend Prediction Forge.

These functions are shared by agent tools, Flask routes, and background loops.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.trend_backtest import ForgeTrendBacktester
from backend.trend_alerts import TrendForgeAlertStore
from backend.trend_prediction import TrendPredictionEngine
from backend.trend_prediction_ledger import TrendPredictionLedger
from backend.trend_signal_collector import TrendSignalCollector
from backend.trend_watchlist import TrendForgeWatchlist


def collect_live_forecast(
    asset: str | None = None,
    token_address: str | None = None,
    chain: str = "base",
    horizon: str = "24h",
    mode: str = "composite",
    historical_limit: int = 72,
) -> dict[str, Any]:
    lookup_asset = asset or token_address
    if not lookup_asset:
        raise ValueError("asset or token_address is required")

    collector = TrendSignalCollector()
    signals = collector.collect(
        asset=lookup_asset,
        token_address=token_address,
        chain=chain,
        historical_limit=historical_limit,
    )
    forecast_asset = signals.metadata.get("resolved_asset") or asset or token_address
    forecast = TrendPredictionEngine().forecast(
        asset=forecast_asset,
        horizon=horizon,
        mode=mode,
        market=signals.market,
        social=signals.social,
        onchain=signals.onchain,
        security=signals.security,
        narrative=signals.narrative,
    )
    return {
        "forecast": forecast,
        "signal_inputs": {
            "market": signals.market,
            "social": signals.social,
            "onchain": signals.onchain,
            "security": signals.security,
            "narrative": signals.narrative,
        },
        "metadata": signals.metadata,
        "data_quality": signals.data_quality,
    }


def record_live_prediction(
    asset: str | None = None,
    token_address: str | None = None,
    chain: str = "base",
    horizon: str = "24h",
    mode: str = "composite",
    historical_limit: int = 72,
    ledger: TrendPredictionLedger | None = None,
) -> dict[str, Any]:
    payload = collect_live_forecast(
        asset=asset,
        token_address=token_address,
        chain=chain,
        horizon=horizon,
        mode=mode,
        historical_limit=historical_limit,
    )
    ledger = ledger or TrendPredictionLedger()
    return ledger.record(
        forecast=payload["forecast"],
        signal_inputs=payload["signal_inputs"],
        data_quality=payload["data_quality"],
        metadata=payload["metadata"],
        token_address=token_address,
        chain=chain,
    )


def evaluate_due_predictions(
    asset: str | None = None,
    evaluate_all: bool = False,
    ledger: TrendPredictionLedger | None = None,
) -> list[dict[str, Any]]:
    ledger = ledger or TrendPredictionLedger()

    def lookup(record: dict[str, Any]) -> dict[str, Any]:
        signals = TrendSignalCollector().collect(
            asset=record["asset"],
            token_address=record.get("token_address"),
            chain=record.get("chain", "base"),
        )
        return signals.to_dict()

    return ledger.evaluate_due(
        signal_lookup=lookup,
        asset=asset,
        evaluate_all=evaluate_all,
    )


def run_live_backtest(
    asset: str,
    horizon: str = "24h",
    mode: str = "composite",
    lookback: int = 72,
    stride: int = 6,
    limit: int = 500,
) -> dict[str, Any]:
    from tools.trading_data import fetch_historical

    raw = fetch_historical(asset, interval="1h", limit=limit)
    if raw.startswith("[error]"):
        return {"error": raw}

    import json

    candles = json.loads(raw)
    return ForgeTrendBacktester().run(
        asset=asset,
        candles=candles,
        horizon=horizon,
        mode=mode,
        lookback=lookback,
        stride=stride,
    ).to_dict()


def process_due_watchlist(
    watchlist: TrendForgeWatchlist | None = None,
    ledger: TrendPredictionLedger | None = None,
    alert_store: TrendForgeAlertStore | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Record forecasts for due watchlist entries and return alert events."""
    watchlist = watchlist or TrendForgeWatchlist()
    ledger = ledger or TrendPredictionLedger()
    alert_store = alert_store or TrendForgeAlertStore()
    now = datetime.now(timezone.utc)
    processed: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []

    for watch in watchlist.list(active_only=True):
        if not force and not _watch_due(watch, now):
            continue

        watch_records: list[dict[str, Any]] = []
        watch_alerts: list[dict[str, Any]] = []
        for horizon in watch.get("horizons", ["24h"]):
            for mode in watch.get("modes", ["composite"]):
                record = record_live_prediction(
                    asset=watch.get("asset"),
                    token_address=watch.get("token_address"),
                    chain=watch.get("chain", "base"),
                    horizon=horizon,
                    mode=mode,
                    ledger=ledger,
                )
                watch_records.append(record)
                watch_alerts.extend(_alerts_for_record(watch, record))

        update_fields = {"last_recorded_at": now.isoformat()}
        if watch_alerts:
            update_fields["last_alerted_at"] = now.isoformat()
            update_fields["last_alerts"] = watch_alerts[-10:]
        watchlist.update(watch["watch_id"], **update_fields)

        processed.append(
            {
                "watch_id": watch["watch_id"],
                "records": len(watch_records),
                "alerts": watch_alerts,
            }
        )
        alerts.extend(watch_alerts)

    stored_alerts = alert_store.add_many(alerts)
    return {"processed": processed, "alerts": alerts, "stored_alerts": stored_alerts}


def list_forge_alerts(
    asset: str | None = None,
    watch_id: str | None = None,
    limit: int = 50,
    alert_store: TrendForgeAlertStore | None = None,
) -> list[dict[str, Any]]:
    alert_store = alert_store or TrendForgeAlertStore()
    return alert_store.list(asset=asset, watch_id=watch_id, limit=limit)


def clear_forge_alerts(alert_store: TrendForgeAlertStore | None = None) -> int:
    alert_store = alert_store or TrendForgeAlertStore()
    return alert_store.clear()


def _watch_due(watch: dict[str, Any], now: datetime) -> bool:
    last_recorded = watch.get("last_recorded_at")
    if not last_recorded:
        return True
    try:
        last = datetime.fromisoformat(last_recorded.replace("Z", "+00:00"))
    except ValueError:
        return True
    interval_seconds = int(watch.get("interval_minutes", 60)) * 60
    return (now - last).total_seconds() >= interval_seconds


def _alerts_for_record(watch: dict[str, Any], record: dict[str, Any]) -> list[dict[str, Any]]:
    forecast = record.get("forecast", {})
    thresholds = watch.get("thresholds") or {}
    alerts: list[dict[str, Any]] = []

    checks = {
        "attention_score": forecast.get("attention_score"),
        "risk_score": forecast.get("risk_score"),
        "confidence": forecast.get("confidence"),
    }
    for key, value in checks.items():
        threshold = thresholds.get(key)
        if threshold is None or value is None:
            continue
        if float(value) >= float(threshold):
            alerts.append(
                {
                    "watch_id": watch.get("watch_id"),
                    "asset": record.get("asset"),
                    "token_address": record.get("token_address"),
                    "metric": key,
                    "value": value,
                    "threshold": threshold,
                    "prediction_id": record.get("prediction_id"),
                    "direction": forecast.get("direction"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
    return alerts
