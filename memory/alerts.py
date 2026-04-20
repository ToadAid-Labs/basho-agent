import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

DEFAULT_ALERTS_PATH = Path.home() / ".agent" / "alerts.json"

class AlertStore:
    """Manages persistent smart alerts for the agent."""

    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_ALERTS_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save([])

    def _load(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, data: List[Dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(data, indent=2))

    def add_alert(
        self,
        alert_type: str,
        symbol: str,
        condition: str,
        value: float | None,
        target_user_id: int,
        **extra_fields: Any,
    ) -> str:
        """Add a new alert."""
        alerts = self._load()
        alert_id = str(uuid.uuid4())[:8]
        new_alert = {
            "id": alert_id,
            "type": alert_type, # PRICE_UP, PRICE_DOWN, SENTIMENT_SPIKE, WHALE_MOVE
            "symbol": symbol.upper(),
            "condition": condition,
            "value": value,
            "user_id": target_user_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_triggered": None,
            "is_active": True,
        }
        for key, field_value in extra_fields.items():
            if field_value is not None:
                new_alert[key] = field_value
        alerts.append(new_alert)
        self._save(alerts)
        return alert_id

    def list_alerts(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all alerts, optionally filtered by user."""
        alerts = self._load()
        if user_id:
            return [a for a in alerts if a["user_id"] == user_id]
        return alerts

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert by ID."""
        alerts = self._load()
        initial_len = len(alerts)
        alerts = [a for a in alerts if a["id"] != alert_id]
        self._save(alerts)
        return len(alerts) < initial_len

    def update_alert(self, alert_id: str, **kwargs) -> bool:
        """Update alert fields."""
        alerts = self._load()
        for a in alerts:
            if a["id"] == alert_id:
                a.update(kwargs)
                self._save(alerts)
                return True
        return False
