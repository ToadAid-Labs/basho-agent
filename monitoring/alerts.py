"""
Alert system for real-time trading notifications.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import json


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    SUCCESS = "success"


class AlertPriority(Enum):
    """Alert priority levels (backward compatibility alias)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts."""
    OPPORTUNITY = "opportunity"
    EXECUTION = "execution"
    PERFORMANCE = "performance"
    RISK = "risk"
    SYSTEM = "system"
    WHALE = "whale"
    MARKET = "market"


@dataclass
class Alert:
    """Represents a single alert."""
    alert_id: str
    alert_type: AlertType
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    acknowledged: bool = False
    sent: bool = False

    def to_dict(self) -> dict:
        """Convert alert to dictionary."""
        return {
            'alert_id': self.alert_id,
            'alert_type': self.alert_type.value,
            'level': self.level.value,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'acknowledged': self.acknowledged,
            'sent': self.sent
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Alert':
        """Create alert from dictionary."""
        return cls(
            alert_id=data['alert_id'],
            alert_type=AlertType(data['alert_type']),
            level=AlertLevel(data['level']),
            title=data['title'],
            message=data['message'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            metadata=data.get('metadata', {}),
            acknowledged=data.get('acknowledged', False),
            sent=data.get('sent', False)
        )


@dataclass
class TradingAlert(Alert):
    """Alert specific to trading operations."""
    token_address: str = ""
    amount: float = 0.0
    dex: str = ""
    expected_profit: float = 0.0
    execution_time: float = 0.0

    def to_dict(self) -> dict:
        """Convert trading alert to dictionary."""
        base_dict = super().to_dict()
        base_dict.update({
            'token_address': self.token_address,
            'amount': self.amount,
            'dex': self.dex,
            'expected_profit': self.expected_profit,
            'execution_time': self.execution_time
        })
        return base_dict


class AlertSystem:
    """Manages and dispatches alerts."""

    def __init__(self):
        self.alerts: List[Alert] = []
        self.handlers: List[callable] = []
        self.max_history: int = 1000
        self.acknowledgement_thresholds = {
            AlertLevel.INFO: 0.9,
            AlertLevel.WARNING: 0.7,
            AlertLevel.CRITICAL: 0.5
        }

    def add_handler(self, handler: callable):
        """Add an alert handler callback."""
        self.handlers.append(handler)

    def remove_handler(self, handler: callable):
        """Remove an alert handler."""
        if handler in self.handlers:
            self.handlers.remove(handler)

    def add_alert(self, alert: Alert):
        """Add a new alert."""
        self.alerts.insert(0, alert)

        # Maintain max history
        if len(self.alerts) > self.max_history:
            self.alerts = self.alerts[:self.max_history]

        # Dispatch to handlers if not already sent
        if not alert.sent:
            alert.sent = True
            self._dispatch_alert(alert)

        # Clean up old acknowledged alerts
        self._cleanup_old_alerts()

        return alert

    def _dispatch_alert(self, alert: Alert):
        """Dispatch alert to all handlers."""
        for handler in self.handlers:
            try:
                handler(alert)
            except Exception as e:
                print(f"Error in alert handler: {e}")

    def _cleanup_old_alerts(self):
        """Remove old acknowledged alerts."""
        threshold = self.acknowledgement_thresholds.get(alert.level, 0.8)
        total = len([a for a in self.alerts if not a.acknowledged])

        if total == 0:
            return

        # Calculate which alerts should be cleaned
        for i, alert in enumerate(self.alerts):
            if not alert.acknowledged:
                ratio = (i + 1) / total
                if ratio < threshold:
                    alert.acknowledged = True

    def get_alerts_by_type(self, alert_type: AlertType) -> List[Alert]:
        """Get alerts of specific type."""
        return [a for a in self.alerts if a.alert_type == alert_type]

    def get_alerts_by_level(self, level: AlertLevel) -> List[Alert]:
        """Get alerts of specific level."""
        return [a for a in self.alerts if a.level == level]

    def get_pending_alerts(self) -> List[Alert]:
        """Get unacknowledged alerts."""
        return [a for a in self.alerts if not a.acknowledged]

    def acknowledge_alert(self, alert_id: str):
        """Mark an alert as acknowledged."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                break

    def get_summary(self) -> dict:
        """Get alert summary statistics."""
        total = len(self.alerts)
        pending = len([a for a in self.alerts if not a.acknowledged])

        by_level = {level: 0 for level in AlertLevel}
        for alert in self.alerts:
            by_level[alert.level] += 1

        return {
            'total_alerts': total,
            'pending_alerts': pending,
            'by_level': {k.value: v for k, v in by_level.items()},
            'by_type': {k.value: 0 for k in AlertType},
            'recent': self._get_recent_alerts(10)
        }

    def _get_recent_alerts(self, count: int) -> List[dict]:
        """Get recent alerts."""
        return [alert.to_dict() for alert in self.alerts[:count]]

    def clear_all(self):
        """Clear all alerts."""
        self.alerts.clear()

    def clear_by_type(self, alert_type: AlertType):
        """Clear alerts of specific type."""
        self.alerts = [a for a in self.alerts if a.alert_type != alert_type]

    def export_alerts(self, filename: str):
        """Export alerts to JSON file."""
        with open(filename, 'w') as f:
            json.dump([alert.to_dict() for alert in self.alerts], f, indent=2)

    def import_alerts(self, filename: str):
        """Import alerts from JSON file."""
        with open(filename, 'r') as f:
            data = json.load(f)
            self.alerts = [Alert.from_dict(d) for d in data]


# Alias for backward compatibility
AlertManager = AlertSystem