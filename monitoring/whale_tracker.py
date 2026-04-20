"""
Whale Tracker Module
Monitors large on-chain transactions and tracks "Smart Money" wallets on the Base chain.
"""

import os
from datetime import datetime, timezone
from typing import Dict, List, Any
import logging

from tools.trust import TrustWalletAPI
from memory.wallets import WalletStore

logger = logging.getLogger(__name__)

class WhaleTracker:
    """Monitor large transactions and known successful wallets using Trust Wallet API."""

    def __init__(self):
        self.whale_threshold_usd = float(os.getenv("WHALE_THRESHOLD_USD", "50000"))
        self.api = TrustWalletAPI()
        self.store = WalletStore()
        
        # Base wallets to always include
        self.static_wallets = [
            "0x1234567890abcdef1234567890abcdef12345678",
            "0xabcdef1234567890abcdef1234567890abcdef12",
            "0x9876543210fedcba9876543210fedcba98765432"
        ]

    def get_smart_money_wallets(self, chain: str) -> List[str]:
        """Combine static and dynamically discovered wallets."""
        dynamic = self.store.get_wallets_by_chain(chain)
        return list(set([w.lower() for w in self.static_wallets] + [w.lower() for w in dynamic]))

    def get_token_activity(self, token_address: str, chain: str = "base") -> Dict[str, Any]:
        """
        Analyze recent large movements and top holders for a specific token using Trust Wallet API.
        """
        try:
            # 1. Fetch top 100 holders
            holders = self.api.get_token_holders(token_address, chain=chain, limit=100)
            
            # 2. Check if any smart money wallets are in the top holders
            smart_money_active = False
            smart_money_holders = []
            
            total_supply_held_by_whales = 0.0
            smart_wallets = self.get_smart_money_wallets(chain)
            
            for holder in holders:
                address = holder.get("address", "").lower()
                balance = float(holder.get("balance", 0))
                
                # We can approximate concentration
                total_supply_held_by_whales += balance
                
                if address in smart_wallets:
                    smart_money_active = True
                    smart_money_holders.append({
                        "address": address,
                        "balance": balance
                    })

            # Check price to estimate USD values (if available)
            price_data = self.api.get_price(token_address, chain=chain)
            price = float(price_data.get("price", 0.0))
            
            whale_count = len(holders)
            
            signal = "NEUTRAL"
            if smart_money_active:
                signal = "STRONG_BUY"
            elif whale_count >= 50 and total_supply_held_by_whales > 0:
                # Basic heuristic
                signal = "ACCUMULATING"

            return {
                "token_address": token_address,
                "chain": chain,
                "price_usd": price,
                "top_holders_analyzed": len(holders),
                "smart_money_active": smart_money_active,
                "smart_money_holders": smart_money_holders,
                "signal": signal,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking whale stats for {token_address}: {e}")
            return {
                "error": str(e),
                "token_address": token_address,
                "signal": "ERROR"
            }

    def track_smart_money_buys(self, chain: str = "base") -> List[Dict]:
        """
        Scan known high-win-rate wallets for their token balances.
        This provides a signal of what smart money is holding.
        """
        results = []
        try:
            smart_wallets = self.get_smart_money_wallets(chain)
            for wallet in smart_wallets:
                balances = self.api.get_token_balances(wallet, chain=chain)
                for b in balances:
                    symbol = b.get("symbol", "UNKNOWN")
                    # Let's say we only care about new/interesting tokens
                    if symbol not in ["ETH", "USDC", "USDT", "DAI"]:
                        results.append({
                            "wallet": wallet,
                            "symbol": symbol,
                            "balance": b.get("balance"),
                            "chain": chain
                        })
        except Exception as e:
            logger.error(f"Error tracking smart money: {e}")
            
        return results

def check_whale_stats(token_address: str, chain: str = "base") -> Dict:
    """Helper for the AI Agent tool."""
    tracker = WhaleTracker()
    return tracker.get_token_activity(token_address, chain=chain)

def get_smart_money_holdings(chain: str = "base") -> List[Dict]:
    """Helper for the AI Agent tool."""
    tracker = WhaleTracker()
    return tracker.track_smart_money_buys(chain=chain)
