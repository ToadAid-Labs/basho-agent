"""
Prediction tracking for Phase 1A Forecasting Brain.

Stores price predictions, evaluates them after their horizon, and summarizes
recent model accuracy. The ledger is intentionally simple JSON so it can run
without migrations.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


DEFAULT_LEDGER_PATH = Path.home() / ".agent" / "prediction_ledger.json"


def _ledger_path() -> Path:
    return Path(os.path.expanduser(os.getenv("PREDICTION_LEDGER_PATH", str(DEFAULT_LEDGER_PATH))))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class PredictionRecord:
    prediction_id: str
    symbol: str
    created_at: str
    horizon_hours: int
    due_at: str
    current_price: float
    predicted_price: float
    confidence: float
    model_version: str
    status: str = "pending"
    actual_price: Optional[float] = None
    absolute_error: Optional[float] = None
    percent_error: Optional[float] = None
    predicted_direction: Optional[str] = None
    actual_direction: Optional[str] = None
    direction_correct: Optional[bool] = None
    evaluated_at: Optional[str] = None


class PredictionLedger:
    """Persistent prediction ledger."""

    def __init__(self, path: Optional[Path] = None):
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
        symbol: str,
        current_price: float,
        predicted_price: float,
        confidence: float,
        horizon_hours: int = 24,
        model_version: str = "manual-v1",
    ) -> dict[str, Any]:
        now = _utcnow()
        due_at = now + timedelta(hours=horizon_hours)
        record = PredictionRecord(
            prediction_id=f"pred_{uuid.uuid4().hex[:10]}",
            symbol=symbol.upper(),
            created_at=now.isoformat(),
            horizon_hours=horizon_hours,
            due_at=due_at.isoformat(),
            current_price=float(current_price),
            predicted_price=float(predicted_price),
            confidence=max(0.0, min(float(confidence), 1.0)),
            model_version=model_version,
            predicted_direction=_direction(float(predicted_price), float(current_price)),
        )
        records = self.load()
        records.append(asdict(record))
        self.save(records)
        return asdict(record)

    def evaluate_due(
        self,
        price_lookup,
        symbol: Optional[str] = None,
        evaluate_all: bool = False,
    ) -> list[dict[str, Any]]:
        records = self.load()
        now = _utcnow()
        evaluated = []

        for record in records:
            if record.get("status") == "evaluated":
                continue
            if symbol and record.get("symbol", "").upper() != symbol.upper():
                continue
            if not evaluate_all and _parse_dt(record["due_at"]) > now:
                continue

            actual_price = price_lookup(record["symbol"])
            if actual_price is None:
                continue
            _evaluate_record(record, float(actual_price), now)
            evaluated.append(record)

        if evaluated:
            self.save(records)
        return evaluated

    def summary(self, symbol: Optional[str] = None, limit: int = 100) -> dict[str, Any]:
        records = self.load()
        if symbol:
            records = [r for r in records if r.get("symbol", "").upper() == symbol.upper()]
        evaluated = [r for r in records if r.get("status") == "evaluated"]
        pending = [r for r in records if r.get("status") != "evaluated"]
        recent = evaluated[-limit:]

        if not recent:
            return {
                "symbol": symbol.upper() if symbol else "ALL",
                "total_predictions": len(records),
                "evaluated": 0,
                "pending": len(pending),
                "direction_accuracy_pct": None,
                "mean_percent_error": None,
                "confidence_modifier": 0.75,
                "note": "No evaluated predictions yet. Confidence modifier is conservative.",
            }

        direction_hits = [r for r in recent if r.get("direction_correct") is True]
        percent_errors = [abs(float(r["percent_error"])) for r in recent if r.get("percent_error") is not None]
        direction_accuracy = len(direction_hits) / len(recent) * 100
        mean_percent_error = sum(percent_errors) / len(percent_errors) if percent_errors else None

        modifier = _confidence_modifier(direction_accuracy, mean_percent_error)
        
        # Sort recent records chronologically by evaluated_at
        recent_sorted = sorted(recent, key=lambda x: x.get("evaluated_at", ""))
        
        return {
            "symbol": symbol.upper() if symbol else "ALL",
            "total_predictions": len(records),
            "evaluated": len(evaluated),
            "pending": len(pending),
            "recent_window": len(recent),
            "direction_accuracy_pct": round(direction_accuracy, 2),
            "mean_percent_error": round(mean_percent_error, 4) if mean_percent_error is not None else None,
            "confidence_modifier": modifier,
            "history": recent_sorted
        }


def _evaluate_record(record: dict[str, Any], actual_price: float, evaluated_at: datetime) -> None:
    current_price = float(record["current_price"])
    predicted_price = float(record["predicted_price"])
    absolute_error = abs(predicted_price - actual_price)
    percent_error = (absolute_error / actual_price * 100) if actual_price else 0.0
    actual_direction = _direction(actual_price, current_price)
    predicted_direction = record.get("predicted_direction") or _direction(predicted_price, current_price)

    record.update(
        {
            "status": "evaluated",
            "actual_price": actual_price,
            "absolute_error": absolute_error,
            "percent_error": percent_error,
            "actual_direction": actual_direction,
            "predicted_direction": predicted_direction,
            "direction_correct": actual_direction == predicted_direction,
            "evaluated_at": evaluated_at.isoformat(),
        }
    )


def _direction(price: float, baseline: float) -> str:
    if price > baseline:
        return "up"
    if price < baseline:
        return "down"
    return "flat"


def _confidence_modifier(direction_accuracy_pct: float, mean_percent_error: Optional[float]) -> float:
    accuracy_component = direction_accuracy_pct / 100
    error_penalty = min((mean_percent_error or 0) / 10, 0.5)
    modifier = 0.5 + (accuracy_component * 0.6) - error_penalty
    return round(max(0.25, min(modifier, 1.25)), 3)
