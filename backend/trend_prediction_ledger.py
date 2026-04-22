"""
Persistent ledger for Trend Prediction Forge forecasts.

The ledger stores each forecast with the exact signal inputs used to produce it.
When a forecast is due, it recollects current signals and compares the realized
regime with the original predicted regime. This gives the agent an accuracy
memory for attention, momentum, risk, and composite forecasts.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from backend.trend_prediction import TrendForecast, TrendPredictionEngine


DEFAULT_LEDGER_PATH = Path.home() / ".agent" / "trend_prediction_ledger.json"
HORIZON_HOURS = {
    "1h": 1,
    "4h": 4,
    "24h": 24,
    "7d": 168,
}


def _ledger_path() -> Path:
    return Path(os.path.expanduser(os.getenv("TREND_PREDICTION_LEDGER_PATH", str(DEFAULT_LEDGER_PATH))))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class TrendPredictionRecord:
    prediction_id: str
    asset: str
    horizon: str
    mode: str
    created_at: str
    due_at: str
    forecast: dict[str, Any]
    signal_inputs: dict[str, Any]
    data_quality: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    token_address: str | None = None
    chain: str = "base"
    status: str = "pending"
    actual_forecast: dict[str, Any] | None = None
    actual_signal_inputs: dict[str, Any] | None = None
    actual_data_quality: dict[str, Any] | None = None
    actual_metadata: dict[str, Any] | None = None
    direction_correct: bool | None = None
    score_error: float | None = None
    evaluated_at: str | None = None


class TrendPredictionLedger:
    """JSON-backed forecast ledger for the forge."""

    def __init__(self, path: Path | None = None):
        self.path = path or _ledger_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def save(self, records: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(records, indent=2, sort_keys=True))

    def record(
        self,
        forecast: TrendForecast,
        signal_inputs: dict[str, Any],
        data_quality: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        token_address: str | None = None,
        chain: str = "base",
    ) -> dict[str, Any]:
        horizon = forecast.horizon
        if horizon not in HORIZON_HOURS:
            raise ValueError(f"Unsupported horizon for ledger: {horizon}")

        now = _utcnow()
        record = TrendPredictionRecord(
            prediction_id=f"trend_{uuid.uuid4().hex[:10]}",
            asset=forecast.asset,
            horizon=horizon,
            mode=forecast.mode,
            created_at=now.isoformat(),
            due_at=(now + timedelta(hours=HORIZON_HOURS[horizon])).isoformat(),
            forecast=forecast.to_dict(),
            signal_inputs=signal_inputs,
            data_quality=data_quality or {},
            metadata=metadata or {},
            token_address=token_address,
            chain=chain,
        )

        records = self.load()
        payload = asdict(record)
        records.append(payload)
        self.save(records)
        return payload

    def evaluate_due(
        self,
        signal_lookup: Callable[[dict[str, Any]], dict[str, Any]],
        asset: str | None = None,
        evaluate_all: bool = False,
    ) -> list[dict[str, Any]]:
        records = self.load()
        now = _utcnow()
        evaluated: list[dict[str, Any]] = []

        for record in records:
            if record.get("status") == "evaluated":
                continue
            if asset and record.get("asset", "").upper() != asset.upper():
                continue
            if not evaluate_all and _parse_dt(record["due_at"]) > now:
                continue

            actual = signal_lookup(record)
            if not isinstance(actual, dict):
                continue

            forecast = self._forecast_from_signals(record, actual)
            self._evaluate_record(record, forecast, actual, now)
            evaluated.append(record)

        if evaluated:
            self.save(records)
        return evaluated

    def summary(self, asset: str | None = None, limit: int = 100) -> dict[str, Any]:
        records = self.load()
        if asset:
            records = [r for r in records if r.get("asset", "").upper() == asset.upper()]

        evaluated = [r for r in records if r.get("status") == "evaluated"]
        pending = [r for r in records if r.get("status") != "evaluated"]
        recent = evaluated[-limit:]

        if not recent:
            return {
                "asset": asset.upper() if asset else "ALL",
                "total_predictions": len(records),
                "evaluated": 0,
                "pending": len(pending),
                "direction_accuracy_pct": None,
                "mean_score_error": None,
                "mode_breakdown": {},
                "note": "No evaluated trend predictions yet.",
            }

        hits = [r for r in recent if r.get("direction_correct") is True]
        errors = [float(r["score_error"]) for r in recent if r.get("score_error") is not None]
        mode_breakdown = _mode_breakdown(recent)

        return {
            "asset": asset.upper() if asset else "ALL",
            "total_predictions": len(records),
            "evaluated": len(evaluated),
            "pending": len(pending),
            "recent_window": len(recent),
            "direction_accuracy_pct": round(len(hits) / len(recent) * 100.0, 2),
            "mean_score_error": round(sum(errors) / len(errors), 4) if errors else None,
            "mode_breakdown": mode_breakdown,
            "history": sorted(recent, key=lambda r: r.get("evaluated_at", "")),
        }

    def _forecast_from_signals(self, record: dict[str, Any], actual: dict[str, Any]) -> TrendForecast:
        engine = TrendPredictionEngine()
        return engine.forecast(
            asset=record["asset"],
            horizon=record["horizon"],
            mode=record["mode"],
            market=actual.get("market", {}),
            social=actual.get("social", {}),
            onchain=actual.get("onchain", {}),
            security=actual.get("security", {}),
            narrative=actual.get("narrative", {}),
        )

    def _evaluate_record(
        self,
        record: dict[str, Any],
        actual_forecast: TrendForecast,
        actual: dict[str, Any],
        evaluated_at: datetime,
    ) -> None:
        actual_payload = actual_forecast.to_dict()
        expected_direction = record.get("forecast", {}).get("direction")
        actual_direction = actual_payload.get("direction")
        score_key = _score_key(record.get("mode", "composite"))
        expected_score = float(record.get("forecast", {}).get(score_key, 0.0))
        actual_score = float(actual_payload.get(score_key, 0.0))

        record.update(
            {
                "status": "evaluated",
                "actual_forecast": actual_payload,
                "actual_signal_inputs": {
                    "market": actual.get("market", {}),
                    "social": actual.get("social", {}),
                    "onchain": actual.get("onchain", {}),
                    "security": actual.get("security", {}),
                    "narrative": actual.get("narrative", {}),
                },
                "actual_data_quality": actual.get("data_quality", {}),
                "actual_metadata": actual.get("metadata", {}),
                "direction_correct": expected_direction == actual_direction,
                "score_error": abs(expected_score - actual_score),
                "evaluated_at": evaluated_at.isoformat(),
            }
        )


def _score_key(mode: str) -> str:
    if mode == "attention":
        return "attention_score"
    if mode == "momentum":
        return "momentum_score"
    if mode == "risk":
        return "risk_score"
    return "composite_score"


def _mode_breakdown(records: list[dict[str, Any]]) -> dict[str, Any]:
    breakdown: dict[str, Any] = {}
    for record in records:
        mode = record.get("mode", "unknown")
        stats = breakdown.setdefault(mode, {"evaluated": 0, "direction_hits": 0, "mean_score_error": None})
        stats["evaluated"] += 1
        if record.get("direction_correct") is True:
            stats["direction_hits"] += 1

    for mode, stats in breakdown.items():
        mode_records = [r for r in records if r.get("mode", "unknown") == mode]
        errors = [float(r["score_error"]) for r in mode_records if r.get("score_error") is not None]
        stats["direction_accuracy_pct"] = round(stats["direction_hits"] / stats["evaluated"] * 100.0, 2)
        stats["mean_score_error"] = round(sum(errors) / len(errors), 4) if errors else None
        del stats["direction_hits"]

    return breakdown
