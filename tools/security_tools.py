import requests
import json
import logging
from typing import Dict, Any, Optional
from core.tools import register_tool

logger = logging.getLogger(__name__)

# GoPlus Chain IDs
CHAIN_MAP = {
    "ethereum": "1",
    "eth": "1",
    "bsc": "56",
    "binance-smart-chain": "56",
    "base": "8453",
    "polygon": "137",
    "arbitrum": "42161",
    "optimism": "10",
    "avalanche": "43114"
}

@register_tool(
    name="audit_token_contract",
    description="Perform a deep security audit of a token's smart contract using the GoPlus Security API. Checks for honeypots, minting risks, liquidity locks, and creator permissions.",
    input_schema={
        "type": "object",
        "properties": {
            "token_address": {
                "type": "string",
                "description": "The contract address of the token to audit.",
            },
            "chain": {
                "type": "string",
                "description": "The blockchain network (e.g., 'ethereum', 'base', 'bsc'). Default is 'ethereum'.",
                "default": "ethereum"
            }
        },
        "required": ["token_address"],
    },
)
def audit_token_contract(token_address: str, chain: str = "ethereum") -> str:
    """Audit a token contract for security risks."""
    chain_id = CHAIN_MAP.get(chain.lower())
    if not chain_id:
        return f"Error: Unsupported chain '{chain}'. Supported chains: {', '.join(CHAIN_MAP.keys())}"
    
    url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={token_address}"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 1:
            return f"Error from GoPlus API: {data.get('message', 'Unknown error')}"
            
        result = data.get("result", {})
        if not result or token_address.lower() not in result:
            return f"No audit data found for address {token_address} on {chain}."
            
        audit = result[token_address.lower()]
        
        # Extract key flags
        is_honeypot = audit.get("is_honeypot") == "1"
        is_mintable = audit.get("is_mintable") == "1"
        can_take_back_ownership = audit.get("can_take_back_ownership") == "1"
        owner_change_balance = audit.get("owner_change_balance") == "1"
        hidden_owner = audit.get("hidden_owner") == "1"
        selfdestruct = audit.get("selfdestruct") == "1"
        external_call = audit.get("external_call") == "1"
        buy_tax = audit.get("buy_tax", "0")
        sell_tax = audit.get("sell_tax", "0")
        
        summary = [
            f"🛡️ Security Audit for {token_address} ({chain.upper()})",
            f"--------------------------------------------------",
            f"🚩 HONEYPOT: {'🚨 YES' if is_honeypot else '✅ No'}",
            f"💰 Buy Tax: {float(buy_tax)*100:.2f}% | Sell Tax: {float(sell_tax)*100:.2f}%",
            f"🛠️ Mintable: {'⚠️ Yes' if is_mintable else '✅ No'}",
            f"👤 Hidden Owner: {'⚠️ Yes' if hidden_owner else '✅ No'}",
            f"🔄 Can Take Back Ownership: {'⚠️ Yes' if can_take_back_ownership else '✅ No'}",
            f"💣 Self-Destruct: {'⚠️ Yes' if selfdestruct else '✅ No'}",
            f"📞 External Calls: {'⚠️ Yes' if external_call else '✅ No'}",
        ]
        
        # Check liquidity
        lp_holders = audit.get("lp_holders", [])
        if lp_holders:
            locked_lp = sum(float(h.get("percent", 0)) for h in lp_holders if h.get("is_locked") == 1)
            summary.append(f"🔒 Locked Liquidity: {locked_lp:.2f}%")
        else:
            summary.append(f"🔒 Locked Liquidity: Unknown/No LP data")

        # Recommendation
        if is_honeypot or float(sell_tax) > 0.5:
            summary.append("\n❌ RECOMMENDATION: DO NOT TRADE. Extreme risk of rug-pull or honeypot.")
        elif is_mintable or hidden_owner or can_take_back_ownership:
            summary.append("\n⚠️ RECOMMENDATION: HIGH RISK. Audit found multiple centralized control flags.")
        else:
            summary.append("\n✅ RECOMMENDATION: LOW RISK. Basic security checks passed.")
            
        return "\n".join(summary)
        
    except Exception as e:
        logger.error(f"Audit error: {e}")
        return f"Error performing audit: {e}"
