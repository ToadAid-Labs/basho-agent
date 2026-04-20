"""
Whale Tracker Tool
Integrates the WhaleTracker with the AI Agent.
"""

from core.tools import register_tool
from monitoring.whale_tracker import check_whale_stats
import json

@register_tool(
    name="check_whale_activity",
    description="Check for large on-chain transactions and 'Smart Money' wallet activity for a specific token address on the Base chain.",
    input_schema={
        "type": "object",
        "properties": {
            "token_address": {
                "type": "string",
                "description": "The contract address of the token to check.",
            },
        },
        "required": ["token_address"],
    },
)
def check_whale_activity(token_address: str) -> str:
    """Check whale activity for a token."""
    try:
        results = check_whale_stats(token_address)
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error checking whale activity: {e}"

@register_tool(
    name="check_smart_money_holdings",
    description="Scan known high-win-rate ('Smart Money') wallets on the Base chain for their current token holdings, which can be used as a signal for copy-trading.",
    input_schema={
        "type": "object",
        "properties": {
            "chain": {
                "type": "string",
                "description": "The blockchain network to check (defaults to 'base').",
            },
        },
    },
)
def check_smart_money_holdings(chain: str = "base") -> str:
    """Check what smart money is holding."""
    try:
        from monitoring.whale_tracker import get_smart_money_holdings
        results = get_smart_money_holdings(chain)
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error checking smart money holdings: {e}"
