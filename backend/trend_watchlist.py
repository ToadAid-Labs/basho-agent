"""
Persistent watchlist for Trend Prediction Forge.

Watchlist entries define assets/contracts the Forge should record on a cadence
and threshold alerts that should be emitted when forecast scores cross levels.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_WATCHLIST_PATH = Path.home() / ".agent" / "trend_forge_watchlist.json"
DEFAULT_THRESHOLDS = {
    "attention_score": 75.0,
    "risk_score": 70.0,
    "confidence": 0.7,
}


def _watchlist_path() -> Path:
    return Path(os.path.expanduser(os.getenv("TREND_FORGE_WATCHLIST_PATH", str(DEFAULT_WATCHLIST_PATH))))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ForgeWatch:
    watch_id: str
    asset: str | None = None
    token_address: str | None = None
    chain: str = "base"
    horizons: list[str] = field(default_factory=lambda: ["1h", "4h", "24h"])
    modes: list[str] = field(default_factory=lambda: ["composite", "risk"])
    interval_minutes: int = 60
    thresholds: dict[str, float] = field(default_factory=lambda: DEFAULT_THRESHOLDS.copy())
    user_id: int | None = None
    is_active: bool = True
    created_at: str = field(default_factory=_utcnow)
    last_recorded_at: str | None = None
    last_alerted_at: str | None = None
    last_alerts: list[dict[str, Any]] = field(default_factory=list)


class TrendForgeWatchlist:
    """JSON-backed watchlist store."""

    def __init__(self, path: Path | None = None):
        self.path = path or _watchlist_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save([])

    def load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text())
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def save(self, records: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(records, indent=2, sort_keys=True))

    def add(
        self,
        asset: str | None = None,
        token_address: str | None = None,
        chain: str = "base",
        horizons: list[str] | None = None,
        modes: list[str] | None = None,
        interval_minutes: int = 60,
        thresholds: dict[str, float] | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        if not asset and not token_address:
            raise ValueError("asset or token_address is required")
        watch = ForgeWatch(
            watch_id=f"watch_{uuid.uuid4().hex[:8]}",
            asset=asset.upper() if asset else None,
            token_address=token_address,
            chain=chain,
            horizons=horizons or ["1h", "4h", "24h"],
            modes=modes or ["composite", "risk"],
            interval_minutes=max(1, int(interval_minutes)),
            thresholds=thresholds or DEFAULT_THRESHOLDS.copy(),
            user_id=user_id,
        )
        records = self.load()
        payload = asdict(watch)
        records.append(payload)
        self.save(records)
        return payload

    def list(self, active_only: bool = False, user_id: int | None = None) -> list[dict[str, Any]]:
        records = self.load()
        if active_only:
            records = [record for record in records if record.get("is_active", True)]
        if user_id is not None:
            records = [record for record in records if record.get("user_id") == user_id]
        return records

    def update(self, watch_id: str, **kwargs: Any) -> bool:
        records = self.load()
        for record in records:
            if record.get("watch_id") == watch_id:
                record.update(kwargs)
                self.save(records)
                return True
        return False

    def delete(self, watch_id: str) -> bool:
        records = self.load()
        kept = [record for record in records if record.get("watch_id") != watch_id]
        self.save(kept)
        return len(kept) != len(records)
