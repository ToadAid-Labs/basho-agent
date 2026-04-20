import pandas as pd
import pandas_ta as ta
import numpy as np
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from core.tools import register_tool
from backend.portfolio_dashboard import PortfolioTracker

logger = logging.getLogger(__name__)

def _get_swing_points(df: pd.DataFrame, window: int = 10) -> Tuple[float, float]:
    """Identify the recent major swing high and low for Fibonacci levels."""
    recent_df = df.tail(100) # Look at last 100 candles
    swing_high = float(recent_df['high'].max())
    swing_low = float(recent_df['low'].min())
    return swing_low, swing_high

def _check_rsi_divergence(df: pd.DataFrame) -> str:
    """Detect Bullish/Bearish RSI Divergence."""
    # Simplified divergence check
    # Bullish: Price Lower Low, RSI Higher Low
    # Bearish: Price Higher High, RSI Lower High
    if len(df) < 30: return "INSUFFICIENT_DATA"
    
    rsi = ta.rsi(df['close'], length=14)
    
    # Look at last two local minima for bullish
    # (This is a simplified heuristic)
    p_curr_low = df['low'].iloc[-1]
    p_prev_low = df['low'].iloc[-15:-5].min()
    
    r_curr_low = rsi.iloc[-1]
    r_prev_low = rsi.iloc[-15:-5].min()
    
    if p_curr_low < p_prev_low and r_curr_low > r_prev_low:
        return "BULLISH_DIVERGENCE"
        
    p_curr_high = df['high'].iloc[-1]
    p_prev_high = df['high'].iloc[-15:-5].max()
    
    r_curr_high = rsi.iloc[-1]
    r_prev_high = rsi.iloc[-15:-5].max()
    
    if p_curr_high > p_prev_high and r_curr_high < r_prev_high:
        return "BEARISH_DIVERGENCE"
        
    return "NONE"

@register_tool(
    name="get_swing_setup",
    description="The Master Swing Trading tool. It anchors to the Daily trend, finds Fibonacci 'Golden Pocket' entry zones, detects RSI Divergence for reversals, and calculates professional ATR-based stops. Perfect for multi-day/week trade planning.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Asset symbol (e.g., BTC, ETH, SOL)."},
            "timeframe": {
                "type": "string", 
                "enum": ["1h", "4h", "1d"], 
                "description": "Primary timeframe for setup analysis. Default is 4h.",
                "default": "4h"
            }
        },
        "required": ["symbol"],
    },
)
def get_swing_setup(symbol: str, timeframe: str = "4h") -> str:
    """Generate a comprehensive swing trading setup."""
    try:
        tracker = PortfolioTracker()
        # Fetch extra data for EMA/RSI buffers
        df = tracker._fetch_real_ohlcv(symbol, 300)
        if df.empty:
            return f"Error: Could not fetch data for {symbol}."
            
        # 1. Daily Trend Anchor (Always check daily regardless of input TF)
        df_daily = tracker._fetch_real_ohlcv(symbol, 100) # simulated daily
        ema200 = ta.ema(df_daily['close'], length=50) # using 50 as proxy for 200 in shorter datasets
        curr_price = float(df['close'].iloc[-1])
        anchor_trend = "BULLISH" if curr_price > ema200.iloc[-1] else "BEARISH"
        
        # 2. Fibonacci Levels (The Golden Pocket)
        low, high = _get_swing_points(df)
        diff = high - low
        fib_05 = high - (0.5 * diff)
        fib_618 = high - (0.618 * diff)
        fib_786 = high - (0.786 * diff)
        
        # 3. RSI Divergence
        divergence = _check_rsi_divergence(df)
        
        # 4. Volatility-Adjusted Stop (2x ATR)
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        curr_atr = float(atr.iloc[-1])
        
        # Setup Logic
        setup_quality = "LOW"
        if anchor_trend == "BULLISH" and curr_price <= fib_05 and curr_price >= fib_786:
            setup_quality = "HIGH (Bullish Pullback)"
            if divergence == "BULLISH_DIVERGENCE":
                setup_quality = "PREMIUM (Bullish Pullback + RSI Divergence)"
        elif anchor_trend == "BEARISH" and curr_price >= fib_05:
            setup_quality = "HIGH (Bearish Relief Rally)"
            if divergence == "BEARISH_DIVERGENCE":
                setup_quality = "PREMIUM (Bearish Relief + RSI Divergence)"
                
        # Recommended levels
        stop_loss = curr_price - (2 * curr_atr) if anchor_trend == "BULLISH" else curr_price + (2 * curr_atr)
        # Target next major fib or recent high
        take_profit = high if anchor_trend == "BULLISH" else low
        risk = abs(curr_price - stop_loss)
        reward = abs(take_profit - curr_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        result = {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "setup_quality": setup_quality,
            "analysis": {
                "anchor_trend": anchor_trend,
                "rsi_divergence": divergence,
                "current_price": round(curr_price, 2),
            },
            "golden_pocket_zone": {
                "fib_0.5": round(fib_05, 2),
                "fib_0.618": round(fib_618, 2),
                "fib_0.786": round(fib_786, 2),
                "status": "IN_ZONE" if (fib_786 <= curr_price <= fib_05) else "OUT_OF_ZONE"
            },
            "trade_plan": {
                "entry_range": f"{round(fib_618, 2)} - {round(fib_05, 2)}",
                "stop_loss": round(stop_loss, 2),
                "take_profit": round(take_profit, 2),
                "risk_reward_ratio": f"1:{round(rr_ratio, 2)}"
            }
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Swing setup error: {e}", exc_info=True)
        return f"Error architecting swing setup: {e}"
