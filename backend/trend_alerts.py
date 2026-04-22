"""
Persistent alert event store for Trend Prediction Forge.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_ALERT_EVENTS_PATH = Path.home() / ".agent" / "trend_forge_alerts.json"


def _alerts_path() -> Path:
    return Path(os.path.expanduser(os.getenv("TREND_FORGE_ALERTS_PATH", str(DEFAULT_ALERT_EVENTS_PATH))))


class TrendForgeAlertStore:
    """JSON-backed store for emitted Forge alert events."""

    def __init__(self, path: Path | None = None):
        self.path = path or _alerts_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save([])

    def load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text())
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def save(self, alerts: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(alerts, indent=2, sort_keys=True))

    def add_many(self, alerts: list[dict[str, Any]], max_events: int = 1000) -> int:
        if not alerts:
            return 0
        records = self.load()
        records.extend(alerts)
        records = records[-max_events:]
        self.save(records)
        return len(alerts)

    def list(
        self,
        asset: str | None = None,
        watch_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        records = self.load()
        if asset:
            records = [record for record in records if record.get("asset", "").upper() == asset.upper()]
        if watch_id:
            records = [record for record in records if record.get("watch_id") == watch_id]
        return records[-max(1, int(limit)):]

    def clear(self) -> int:
        count = len(self.load())
        self.save([])
        return count
