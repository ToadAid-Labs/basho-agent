from __future__ import annotations

from typing import Any

LIVE_EXECUTION_TOOLS = {"swap_tokens", "transfer_tokens"}
BROAD_SCAN_TOOLS = {
    "market_report",
    "check_whale_activity",
    "check_smart_money_holdings",
    "get_pro_indicators",
    "analyze_market_structure",
    "get_multi_timeframe_signal",
}


def build_intent_tool_policy(user_input: str) -> dict[str, Any]:
    lowered = user_input.lower()

    reentry_markers = ("buy back", "buyback", "watch", "come down", "opportunity")
    if "degen" in lowered and any(marker in lowered for marker in reentry_markers):
        return {
            "mode": "tracked_token_reentry_watch",
            "focus": "token price first, then one compact re-entry check",
            "stages": [
                {"trust_get_token_price"},
                {"trade_decision_engine", "get_swing_setup"},
            ],
            "allowed_tools": {"trust_get_token_price", "trade_decision_engine", "get_swing_setup"},
            "max_tool_calls": 2,
            "stop_after_stage": 2,
            "allow_live_execution": False,
            "deferred": [
                "market report",
                "whale scan",
                "smart money scan",
                "manual structure/indicator fanout",
                "alerts",
            ],
        }

    if any(phrase in lowered for phrase in ("sell remaining", "swap remaining", "transfer remaining")) and "degen" in lowered:
        return {
            "mode": "sell_remaining_tracked",
            "focus": "direct tracked-token balance and execution prep",
            "stages": [
                {"get_tracked_token_balance"},
                {"trust_get_swap_quote"},
            ],
            "allowed_tools": {"get_tracked_token_balance", "trust_get_swap_quote"},
            "max_tool_calls": 2,
            "stop_after_stage": 2,
            "allow_live_execution": False,
            "deferred": ["wallet summary", "recent history", "alerts", "risk/market scan", "live execution"],
        }

    if "should i sell" in lowered:
        return {
            "mode": "sell_decision",
            "focus": "direct token balance and price",
            "stages": [
                {"get_tracked_token_balance"},
                {"trust_get_token_price"},
            ],
            "allowed_tools": {"get_tracked_token_balance", "trust_get_token_price"},
            "max_tool_calls": 2,
            "stop_after_stage": 2,
            "allow_live_execution": False,
            "deferred": ["recent history", "alerts", "risk/market scan"],
        }

    if "degen" in lowered and any(phrase in lowered for phrase in ("where is", "balance", "position", "holdings")):
        return {
            "mode": "tracked_token_position",
            "focus": "direct tracked-token balance",
            "stages": [
                {"get_tracked_token_balance"},
                {"trust_get_token_price"},
            ],
            "allowed_tools": {"get_tracked_token_balance", "trust_get_token_price"},
            "max_tool_calls": 2,
            "stop_after_stage": 2,
            "allow_live_execution": False,
            "deferred": ["wallet-wide portfolio scan", "recent history", "alerts", "risk/market scan"],
        }

    if "insider hunt" in lowered or "alpha wallet" in lowered:
        return {
            "mode": "insider_hunt_watchlist",
            "focus": "watchlist detection and contract-risk filtering",
            "stages": [
                {"hunt_insider_wallets"},
                {"verify_alpha_wallet"},
            ],
            "allowed_tools": {"hunt_insider_wallets", "verify_alpha_wallet", "add_alpha_wallet"},
            "max_tool_calls": 2,
            "stop_after_stage": 2,
            "allow_live_execution": False,
            "deferred": ["live trading", "swaps", "transfers", "auto-buy"],
        }

    if any(word in lowered for word in ("wallet", "portfolio")):
        return {
            "mode": "wallet_status",
            "focus": "wallet summary and tracked balances",
            "stages": [
                {"get_wallet_balance"},
                {"get_tracked_token_balance"},
            ],
            "allowed_tools": {"get_wallet_balance", "get_tracked_token_balance"},
            "max_tool_calls": 2,
            "stop_after_stage": 2,
            "allow_live_execution": False,
            "deferred": ["price lookup", "recent history", "alerts", "risk/market scan"],
        }

    return {
        "mode": "default",
        "focus": "",
        "stages": [],
        "allowed_tools": set(),
        "max_tool_calls": 0,
        "stop_after_stage": 0,
        "allow_live_execution": False,
        "deferred": [],
    }


def is_live_execution_tool(tool_name: str) -> bool:
    return tool_name in LIVE_EXECUTION_TOOLS
