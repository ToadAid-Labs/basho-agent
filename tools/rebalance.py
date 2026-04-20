import json
from typing import Dict, Any
from decimal import Decimal
import logging
from core.tools import register_tool
from tools.trading_control import get_paper_trading_account, _get_live_price

logger = logging.getLogger(__name__)

@register_tool(
    name="rebalance_portfolio",
    description="Automatically rebalance the user's paper trading portfolio to match specific target percentage allocations. Provide target allocations as a dictionary (e.g., {\"BTC\": 50, \"ETH\": 30, \"USDC\": 20}).",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "integer",
                "description": "The user ID of the paper account."
            },
            "target_allocations": {
                "type": "string",
                "description": "JSON string of symbol to target percentage (0-100). E.g., '{\"BTC\": 50, \"ETH\": 50}'"
            }
        },
        "required": ["user_id", "target_allocations"],
    },
)
def rebalance_portfolio(user_id: int, target_allocations: str) -> str:
    """Automatically rebalance the portfolio to meet target weights."""
    try:
        targets = json.loads(target_allocations)
        
        # Validate targets
        total_pct = sum(targets.values())
        if not (99.0 <= total_pct <= 101.0):
            return f"Error: Target allocations must sum to ~100%. Provided targets sum to {total_pct}%."
            
        account = get_paper_trading_account(user_id)
        if not account:
            return f"No paper trading account found for user {user_id}."
            
        # Get live prices
        symbols = set(targets.keys()).union(set(account.positions.keys()))
        prices = {sym: _get_live_price(sym) for sym in symbols if sym != "USDC"}
        prices["USDC"] = 1.0 # Baseline stablecoin
        
        # Calculate total portfolio value
        total_value = float(account.cash)
        for sym, qty in account.positions.items():
            if sym in prices and prices[sym]:
                total_value += float(qty) * prices[sym]
                
        if total_value <= 0:
            return "Portfolio has no value to rebalance."
            
        # Determine exact target dollar values
        target_values = {}
        for sym, pct in targets.items():
            target_values[sym] = total_value * (pct / 100.0)
            
        # Determine current dollar values
        current_values = {}
        for sym in symbols:
            if sym == "USDC":
                current_values[sym] = float(account.cash)
            else:
                current_values[sym] = float(account.positions.get(sym, 0)) * prices.get(sym, 0)
                
        # Calculate differences and execute trades
        results = []
        for sym in symbols:
            target_val = target_values.get(sym, 0.0)
            current_val = current_values.get(sym, 0.0)
            diff = target_val - current_val
            
            # If difference is more than 1% of total value, rebalance
            if abs(diff) > (total_value * 0.01):
                if sym == "USDC":
                    continue # Handled by buying/selling other assets
                    
                price = prices.get(sym)
                if not price:
                    results.append(f"Could not fetch price for {sym}, skipping.")
                    continue
                    
                if diff > 0:
                    # Buy
                    qty = diff / price
                    success = account.open_position(sym, qty, price, strategy="REBALANCE")
                    if success:
                        results.append(f"Bought {qty:.6f} {sym} (${diff:.2f})")
                    else:
                        results.append(f"Failed to buy {sym}")
                elif diff < 0:
                    # Sell
                    qty = abs(diff) / price
                    success = account.close_position(sym, qty, price, notes="REBALANCE")
                    if success:
                        results.append(f"Sold {qty:.6f} {sym} (${abs(diff):.2f})")
                    else:
                        results.append(f"Failed to sell {sym}")
                        
        if not results:
            return f"Portfolio is already balanced according to targets: {targets}"
            
        return "Rebalancing execution complete:\n" + "\n".join(results)
    except json.JSONDecodeError:
        return "Error: target_allocations must be a valid JSON string."
    except Exception as e:
        logger.error(f"Error in rebalance_portfolio: {e}", exc_info=True)
        return f"Error executing rebalance: {e}"
