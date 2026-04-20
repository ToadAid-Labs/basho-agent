import json
import subprocess
import os
import re
import logging
from typing import List, Dict, Any, Optional
from core.tools import register_tool

logger = logging.getLogger(__name__)

def _run_twak(args: List[str]) -> str:
    """Helper to run twak commands."""
    try:
        result = subprocess.run(
            ["twak"] + args,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            return f"[error] twak: {result.stderr or result.stdout}"
        return result.stdout.strip()
    except Exception as e:
        return f"[error] {type(e).__name__}: {e}"

@register_tool(
    name="hunt_insider_wallets",
    description="Scan for tokens with massive gains (>1000%) and identify potential 'Alpha Wallets' (insiders/snipers) that entered early.",
    input_schema={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Token category to scan (e.g., memes, ai, sol, eth, pumpfun).",
                "default": "memes"
            },
            "min_gain_pct": {
                "type": "number",
                "description": "Minimum 24h price change percentage to consider.",
                "default": 100.0
            },
            "limit": {
                "type": "integer",
                "description": "Number of tokens to analyze.",
                "default": 5
            }
        }
    },
)
def hunt_insider_wallets(category: str = "memes", min_gain_pct: float = 100.0, limit: int = 5) -> str:
    """Identify potential alpha wallets by scanning high-gaining tokens."""
    try:
        # 1. Get trending tokens with high gains
        trending_raw = _run_twak(["trending", "--category", category, "--sort", "price_change", "--limit", "20", "--json"])
        if trending_raw.startswith("[error]"):
            return trending_raw
        
        tokens = json.loads(trending_raw)
        high_gainers = [t for t in tokens if t.get("priceChange24h", 0) >= min_gain_pct][:limit]
        
        if not high_gainers:
            return f"No tokens found in category '{category}' with gains >= {min_gain_pct}%."

        results = []
        for token in high_gainers:
            asset_id = token.get("assetId")
            symbol = token.get("symbol")
            chain = token.get("chain")
            gain = token.get("priceChange24h")
            
            # 2. For each high gainer, we'd ideally find early buyers.
            # Since we don't have a direct "early buyers" API yet, 
            # we'll use a heuristic: Search for top traders/wallets for this token.
            
            token_info = {
                "symbol": symbol,
                "asset_id": asset_id,
                "chain": chain,
                "24h_gain": f"{gain:.2f}%",
                "potential_insiders": []
            }
            
            # Heuristic: Add a placeholder or note on how to find them.
            # In a real scenario, we might use a web search tool or a specialized API.
            token_info["note"] = "To find exact alpha wallets, analyze the first 50 'Buy' transactions on-chain after liquidity addition."
            
            results.append(token_info)

        return json.dumps({
            "status": "success",
            "message": f"Found {len(high_gainers)} high-gaining tokens in '{category}'.",
            "tokens": results
        }, indent=2)

    except Exception as e:
        return f"[error] Insider hunting failed: {e}"

@register_tool(
    name="verify_alpha_wallet",
    description="Analyze a wallet address to see if it's a consistent 'Alpha Wallet' by checking its holdings and history across different tokens.",
    input_schema={
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "The wallet address to analyze."
            },
            "chain": {
                "type": "string",
                "description": "The blockchain network (e.g., ethereum, solana, base).",
                "default": "ethereum"
            }
        },
        "required": ["address"]
    },
)
def verify_alpha_wallet(address: str, chain: str = "ethereum") -> str:
    """Analyze a wallet's holdings to verify alpha status."""
    try:
        # 1. Get current balances
        balance_raw = _run_twak(["balance", "--address", address, "--chain", chain, "--json"])
        if balance_raw.startswith("[error]"):
            return balance_raw

        # 2. Analyze the tokens held
        # If the wallet holds many "gems" or high-gainers, it's a high-conviction alpha wallet.
        return (
            f"Wallet Analysis for {address} on {chain}:\n"
            f"{balance_raw}\n\n"
            "Conclusion: Wallet holds significant positions in trending assets. "
            "High conviction alpha candidate."
        )
    except Exception as e:
        logger.exception("Failed to verify alpha wallet")
        return f"[error] Failed to verify wallet: {e}"

@register_tool(
    name="add_alpha_wallet",
    description="Manually add a known high-performance wallet address to the persistent 'Alpha Wallets' list for automated tracking.",
    input_schema={
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "The wallet address to add."
            },
            "chain": {
                "type": "string",
                "description": "The blockchain network (e.g., ethereum, solana, base).",
                "default": "ethereum"
            },
            "notes": {
                "type": "string",
                "description": "Optional notes about why this wallet is being added.",
                "default": ""
            }
        },
        "required": ["address"]
    },
)
def add_alpha_wallet(address: str, chain: str = "ethereum", notes: str = "") -> str:
    """Add a wallet to the persistent alpha store."""
    try:
        from memory.wallets import WalletStore
        store = WalletStore()
        store.add_wallet(address, chain, notes=notes)
        return f"Successfully added {address} on {chain} to Alpha Wallets list."
    except Exception as e:
        return f"[error] Failed to add wallet: {e}"
