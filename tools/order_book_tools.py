import requests
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from core.tools import register_tool

logger = logging.getLogger(__name__)

def _get_binance_depth(symbol: str, limit: int = 100) -> Dict[str, Any]:
    """Fetch order book depth from Binance."""
    try:
        # Binance symbol format: BTCUSDT
        formatted_symbol = f"{symbol.upper()}USDT"
        url = f"https://api.binance.com/api/v3/depth?symbol={formatted_symbol}&limit={limit}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Binance depth error for {symbol}: {e}")
        return {}

@register_tool(
    name="analyze_order_book",
    description="Analyze the real-time limit order book (depth) for a symbol to detect massive buy/sell walls and calculate Order Book Imbalance (OBI). Essential for predicting micro-trend reversals and institutional pressure.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Asset symbol (e.g., BTC, ETH)."},
            "wall_threshold_multiple": {
                "type": "number", 
                "description": "Multiplier of average order size to define a 'Wall' (default 5.0).",
                "default": 5.0
            }
        },
        "required": ["symbol"],
    },
)
def analyze_order_book(symbol: str, wall_threshold_multiple: float = 5.0) -> str:
    """Analyze order book for walls and imbalance."""
    try:
        depth = _get_binance_depth(symbol)
        if not depth:
            return f"Error: Could not fetch order book for {symbol}."
            
        bids = depth.get('bids', []) # [[price, qty], ...]
        asks = depth.get('asks', [])
        
        if not bids or not asks:
            return f"Error: Empty order book for {symbol}."
            
        # Convert to floats
        bid_data = [(float(p), float(q)) for p, q in bids]
        ask_data = [(float(p), float(q)) for p, q in asks]
        
        # 1. Calculate Total Volume at Depth
        total_bid_vol = sum(q for p, q in bid_data)
        total_ask_vol = sum(q for p, q in ask_data)
        
        # 2. Order Book Imbalance (OBI)
        # OBI = (Bid Vol - Ask Vol) / (Bid Vol + Ask Vol)
        # Ranges from -1 (extreme sell pressure) to +1 (extreme buy pressure)
        obi = (total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol)
        
        # 3. Detect Walls
        avg_bid_size = total_bid_vol / len(bid_data)
        avg_ask_size = total_ask_vol / len(ask_data)
        
        buy_walls = [
            {"price": p, "size": q, "multiple": q/avg_bid_size} 
            for p, q in bid_data if q > avg_bid_size * wall_threshold_multiple
        ]
        sell_walls = [
            {"price": p, "size": q, "multiple": q/avg_ask_size} 
            for p, q in ask_data if q > avg_ask_size * wall_threshold_multiple
        ]
        
        # 4. Spread
        best_bid = bid_data[0][0]
        best_ask = ask_data[0][0]
        spread = best_ask - best_bid
        spread_pct = (spread / best_ask) * 100
        
        result = {
            "symbol": symbol.upper(),
            "obi_score": round(obi, 4),
            "market_bias": "BULLISH (Heavy Bids)" if obi > 0.3 else "BEARISH (Heavy Asks)" if obi < -0.3 else "NEUTRAL",
            "liquidity": {
                "total_bids": round(total_bid_vol, 2),
                "total_asks": round(total_ask_vol, 2),
                "spread_pct": f"{spread_pct:.4f}%"
            },
            "walls": {
                "buy_walls": sorted(buy_walls, key=lambda x: x['multiple'], reverse=True)[:3],
                "sell_walls": sorted(sell_walls, key=lambda x: x['multiple'], reverse=True)[:3]
            },
            "interpretation": f"OBI of {obi:.2f} suggests {'strong buy' if obi > 0.5 else 'moderate buy' if obi > 0.1 else 'moderate sell' if obi < -0.1 else 'strong sell' if obi < -0.5 else 'neutral'} pressure."
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Order book analysis error: {e}")
        return f"Error analyzing order book: {e}"
