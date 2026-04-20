import json
import logging
from typing import Optional
from core.tools import register_tool
from memory.alerts import AlertStore

logger = logging.getLogger(__name__)

@register_tool(
    name="set_smart_alert",
    description="Set a proactive smart alert for the agent to watch in the background. Types: PRICE_UP (absolute price), PRICE_DOWN (absolute price), SENTIMENT_SPIKE (threshold -1 to 1), WHALE_MOVE (USD threshold), WALLET_ACTIVITY (new on-chain activity for a wallet address).",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Asset symbol for price/sentiment/whale alerts (e.g., BTC)."},
            "wallet_address": {"type": "string", "description": "Wallet address to monitor for on-chain activity."},
            "chain": {"type": "string", "description": "Blockchain network for wallet alerts, e.g. base. Defaults to base."},
            "alert_type": {
                "type": "string", 
                "enum": ["PRICE_UP", "PRICE_DOWN", "SENTIMENT_SPIKE", "WHALE_MOVE", "WALLET_ACTIVITY"],
                "description": "Type of event to watch for."
            },
            "value": {"type": "number", "description": "The threshold value for the alert. Not required for WALLET_ACTIVITY."},
            "user_id": {"type": "integer", "description": "The user ID to notify."}
        },
        "required": ["alert_type", "user_id"],
    },
)
def set_smart_alert(
    alert_type: str,
    user_id: int,
    symbol: Optional[str] = None,
    wallet_address: Optional[str] = None,
    chain: str = "base",
    value: Optional[float] = None,
) -> str:
    """Create a new background alert."""
    try:
        store = AlertStore()

        if alert_type == "WALLET_ACTIVITY":
            if not wallet_address:
                return "Error setting alert: wallet_address is required for WALLET_ACTIVITY alerts."

            latest_cursor = None
            try:
                from tools.wallet_activity import get_latest_wallet_activity

                snapshot = get_latest_wallet_activity(wallet_address, chain=chain)
                latest_cursor = snapshot.get("latest_tx_hash")
            except Exception as cursor_error:  # noqa: BLE001
                logger.warning("Failed to seed wallet activity cursor: %s", cursor_error)

            alert_id = store.add_alert(
                alert_type=alert_type,
                symbol=f"WALLET:{wallet_address[-8:]}",
                condition="activity",
                value=0.0,
                target_user_id=user_id,
                wallet_address=wallet_address,
                chain=chain,
                last_seen_tx_hash=latest_cursor,
                watch_mode="wallet_activity",
            )
            return (
                f"Successfully set WALLET_ACTIVITY alert for {wallet_address} on {chain.upper()}."
                f" Alert ID: {alert_id}"
            )

        if not symbol:
            return f"Error setting alert: symbol is required for {alert_type} alerts."
        if value is None:
            return f"Error setting alert: value is required for {alert_type} alerts."

        alert_id = store.add_alert(
            alert_type=alert_type,
            symbol=symbol,
            condition="above" if alert_type in ["PRICE_UP", "SENTIMENT_SPIKE", "WHALE_MOVE"] else "below",
            value=value,
            target_user_id=user_id,
        )
        return f"Successfully set {alert_type} alert for {symbol.upper()} at {value}. Alert ID: {alert_id}"
    except Exception as e:
        return f"Error setting alert: {e}"

@register_tool(
    name="list_alerts",
    description="List all active background alerts.",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "Optional user ID filter."}
        }
    },
)
def list_alerts_tool(user_id: Optional[int] = None) -> str:
    """List alerts."""
    try:
        store = AlertStore()
        alerts = store.list_alerts(user_id)
        if not alerts:
            return "No active alerts found."
        return json.dumps(alerts, indent=2)
    except Exception as e:
        return f"Error listing alerts: {e}"

@register_tool(
    name="delete_alert",
    description="Delete an active alert by its ID.",
    input_schema={
        "type": "object",
        "properties": {
            "alert_id": {"type": "string", "description": "The 8-character alert ID."}
        },
        "required": ["alert_id"],
    },
)
def delete_alert_tool(alert_id: str) -> str:
    """Delete alert."""
    try:
        store = AlertStore()
        if store.delete_alert(alert_id):
            return f"Successfully deleted alert {alert_id}."
        return f"Alert {alert_id} not found."
    except Exception as e:
        return f"Error deleting alert: {e}"
