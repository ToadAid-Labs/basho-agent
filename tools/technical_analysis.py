import pandas as pd
import pandas_ta as ta
import numpy as np
import json
import logging
from typing import Dict, List, Any, Optional
from core.tools import register_tool
from backend.portfolio_dashboard import PortfolioTracker

logger = logging.getLogger(__name__)

def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame has correct types for pandas_ta."""
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    return df

@register_tool(
    name="get_pro_indicators",
    description="Calculate advanced technical indicators for a symbol, including SuperTrend (Trend), ADX (Strength), RSI (Momentum), and ATR (Volatility). Provides a professional-grade market health snapshot.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Asset symbol (e.g., BTC)."},
            "period": {"type": "integer", "description": "Number of candles to analyze (default 200).", "default": 200}
        },
        "required": ["symbol"],
    },
)
def get_pro_indicators(symbol: str, period: int = 200) -> str:
    """Calculate professional-grade indicators."""
    try:
        tracker = PortfolioTracker()
        df = tracker._fetch_real_ohlcv(symbol, period)
        if df.empty:
            return f"Error: Could not fetch data for {symbol}."
            
        df = _prepare_df(df)
        
        # 1. Trend: SuperTrend
        st = ta.supertrend(df['high'], df['low'], df['close'], length=10, multiplier=3.0)
        curr_st = st.iloc[-1]
        trend_signal = "UP" if curr_st.iloc[0] < df['close'].iloc[-1] else "DOWN"
        
        # 2. Strength: ADX
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        curr_adx = adx.iloc[-1]
        strength = "STRONG" if curr_adx.iloc[0] > 25 else "WEAK"
        
        # 3. Momentum: RSI
        rsi = ta.rsi(df['close'], length=14)
        curr_rsi = rsi.iloc[-1]
        momentum = "OVERBOUGHT" if curr_rsi > 70 else "OVERSOLD" if curr_rsi < 30 else "NEUTRAL"
        
        # 4. Volatility: ATR %
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        curr_atr_pct = (atr.iloc[-1] / df['close'].iloc[-1]) * 100
        
        result = {
            "symbol": symbol.upper(),
            "trend": trend_signal,
            "trend_strength": f"{strength} (ADX: {curr_adx.iloc[0]:.2f})",
            "momentum": f"{momentum} (RSI: {curr_rsi:.2f})",
            "volatility": f"{curr_atr_pct:.2f}% (ATR)",
            "summary": f"The market is in a {strength} {trend_signal} trend with {momentum} momentum."
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Pro indicators error: {e}")
        return f"Error calculating indicators: {e}"

@register_tool(
    name="analyze_market_structure",
    description="Automatically identify key Support/Resistance levels, Order Blocks, and Fair Value Gaps (FVG) from price action. Essential for institutional-style supply and demand trading.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Asset symbol."},
            "lookback": {"type": "integer", "description": "Candles to look back for levels.", "default": 300}
        },
        "required": ["symbol"],
    },
)
def analyze_market_structure(symbol: str, lookback: int = 300) -> str:
    """Identify key zones and structure."""
    try:
        tracker = PortfolioTracker()
        df = tracker._fetch_real_ohlcv(symbol, lookback)
        if df.empty:
            return f"Error: Could not fetch data for {symbol}."
            
        # Support/Resistance via Pivots
        df = _prepare_df(df)
        highs = df['high'].values
        lows = df['low'].values
        
        resistance = []
        support = []
        
        # Simple local minima/maxima for S/R
        for i in range(5, len(df)-5):
            if highs[i] == max(highs[i-5:i+6]):
                resistance.append(float(highs[i]))
            if lows[i] == min(lows[i-5:i+6]):
                support.append(float(lows[i]))
        
        # FVGs (Fair Value Gaps)
        fvgs = []
        for i in range(1, len(df)-1):
            # Bullish FVG
            if df['low'].iloc[i+1] > df['high'].iloc[i-1] and df['close'].iloc[i] > df['open'].iloc[i]:
                fvgs.append({"type": "BULLISH_GAP", "top": float(df['low'].iloc[i+1]), "bottom": float(df['high'].iloc[i-1])})
            # Bearish FVG
            if df['high'].iloc[i+1] < df['low'].iloc[i-1] and df['close'].iloc[i] < df['open'].iloc[i]:
                fvgs.append({"type": "BEARISH_GAP", "top": float(df['low'].iloc[i-1]), "bottom": float(df['high'].iloc[i+1])})
                
        result = {
            "symbol": symbol.upper(),
            "major_resistance": sorted(list(set(resistance)))[-3:],
            "major_support": sorted(list(set(support)))[:3],
            "recent_fair_value_gaps": fvgs[-3:],
            "current_price": float(df['close'].iloc[-1])
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error analyzing market structure: {e}"

@register_tool(
    name="get_multi_timeframe_signal",
    description="Institutional-grade trend analysis using the Triple Screen method. Confirms trend alignment across 1h, 4h, 1d, and 1w timeframes using real market data. Vital for catching the 'Big Waves' in a bull market.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Asset symbol (e.g., BTC, ETH)."}
        },
        "required": ["symbol"],
    },
)
@register_tool(
    name="detect_market_regime",
    description="Classify the current market regime for a symbol as TRENDING, RANGING, VOLATILE, or UNKNOWN. Analyzes recent price action, ADX strength, and ATR volatility to help the agent decide which strategy (Trend-Following vs. Mean-Reversion) to use.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Asset symbol (e.g., BTC, ETH)."},
            "lookback": {"type": "integer", "description": "Number of candles to analyze (default 100).", "default": 100}
        },
        "required": ["symbol"],
    },
)
def detect_market_regime(symbol: str, lookback: int = 100) -> str:
    """Detect market regime: Trending, Ranging, or Volatile."""
    try:
        from monitoring.market_analyzer import MarketAnalyzer
        tracker = PortfolioTracker()
        df = tracker._fetch_real_ohlcv(symbol, lookback)
        if df.empty:
            return f"Error: Could not fetch data for {symbol}."
            
        df = _prepare_df(df)
        
        # 1. Volatility check (ATR)
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        curr_atr_pct = (atr.iloc[-1] / df['close'].iloc[-1]) * 100
        
        # 2. Trend Strength check (ADX)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        curr_adx = adx_df.iloc[-1].iloc[0] # ADX_14
        
        # 3. Market Structure (Range vs Breakout)
        # Calculate Bollinger Band Width
        bb = ta.bbands(df['close'], length=20, std=2)
        bb_width = (bb['BBU_20_2.0'] - bb['BBL_20_2.0']) / bb['BBM_20_2.0']
        curr_bbw = bb_width.iloc[-1]
        
        # Determine regime
        regime = "UNKNOWN"
        reason = "Insufficient data"
        
        if curr_atr_pct > 4.5: # Threshold for high volatility
            regime = "VOLATILE"
            reason = f"ATR is extremely high ({curr_atr_pct:.2f}%). Expect whipsaws."
        elif curr_adx > 25:
            regime = "TRENDING"
            direction = "UP" if df['close'].iloc[-1] > df['close'].iloc[-10] else "DOWN"
            reason = f"ADX is strong ({curr_adx:.2f}). Market is clearly trending {direction}."
        elif curr_bbw < 0.05:
            regime = "RANGING"
            reason = f"Bollinger Band Width is narrow ({curr_bbw:.3f}). Market is consolidating in a tight range."
        else:
            regime = "RANGING (Neutral)"
            reason = f"ADX is weak ({curr_adx:.2f}) and volatility is moderate. No clear trend detected."
            
        result = {
            "symbol": symbol.upper(),
            "regime": regime,
            "metrics": {
                "adx": round(curr_adx, 2),
                "atr_pct": round(curr_atr_pct, 2),
                "bb_width": round(curr_bbw, 3)
            },
            "reasoning": reason,
            "recommended_strategy": "Momentum/Trend-Following" if regime == "TRENDING" else "Mean-Reversion/Grid" if regime == "RANGING" else "Wait/Risk-Off"
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Regime detection error: {e}")
        return f"Error detecting market regime: {e}"

def get_multi_timeframe_signal(symbol: str) -> str:
    """Institutional trend confirmation across 1h, 4h, 1d, and 1w."""
    try:
        from tools.trading_data import fetch_historical
        timeframes = ["1h", "4h", "1d", "1w"]
        signals = {}
        
        for tf in timeframes:
            # Fetch last 50 candles for trend calculation
            raw_data = fetch_historical(symbol, interval=tf, limit=50)
            if raw_data.startswith("[error]"):
                signals[tf] = "DATA_ERROR"
                continue
            
            data = json.loads(raw_data)
            if not data:
                signals[tf] = "EMPTY_DATA"
                continue
                
            df = pd.DataFrame(data)
            df = _prepare_df(df)
            
            # Use EMA 20/50 for trend direction
            ema20 = ta.ema(df['close'], length=20)
            ema50 = ta.ema(df['close'], length=50)
            
            if ema20.iloc[-1] > ema50.iloc[-1]:
                signals[tf] = "BULLISH"
            elif ema20.iloc[-1] < ema50.iloc[-1]:
                signals[tf] = "BEARISH"
            else:
                signals[tf] = "NEUTRAL"
        
        # Summary Logic
        summary = "NEUTRAL"
        bullish_count = sum(1 for s in signals.values() if s == "BULLISH")
        bearish_count = sum(1 for s in signals.values() if s == "BEARISH")
        
        if signals.get("1w") == "BULLISH" and signals.get("1d") == "BULLISH":
            summary = "INSTITUTIONAL_BULLISH (Long Opportunity)"
            if bullish_count >= 3:
                summary = "STRONG_BUY (Triple Screen Alignment)"
        elif signals.get("1w") == "BEARISH" and signals.get("1d") == "BEARISH":
            summary = "INSTITUTIONAL_BEARISH (Short Opportunity)"
            if bearish_count >= 3:
                summary = "STRONG_SELL (Triple Screen Alignment)"
                
        return json.dumps({
            "symbol": symbol.upper(),
            "timeframe_signals": signals,
            "institutional_summary": summary,
            "recommendation": "Look for entries" if "BULLISH" in summary else "Wait or exit" if "BEARISH" in summary else "Neutral"
        }, indent=2)
    except Exception as e:
        logger.error(f"MTF signal error: {e}")
        return f"Error calculating institutional signals: {e}"
