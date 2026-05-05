import pandas as pd
import numpy as np
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from core.tools import register_tool
from backend.portfolio_dashboard import PortfolioTracker

logger = logging.getLogger(__name__)

def _calculate_zscore(series: pd.Series) -> pd.Series:
    """Calculate Z-Score of a series."""
    return (series - series.mean()) / series.std()

@register_tool(
    name="analyze_pair_correlation",
    description="Analyze the statistical correlation and price spread between two assets (e.g., BTC vs ETH, SOL vs JUP) to identify mean-reversion opportunities. Returns Z-Score and hedge ratio for statistical arbitrage.",
    input_schema={
        "type": "object",
        "properties": {
            "asset_a": {"type": "string", "description": "First asset symbol (e.g., ETH)."},
            "asset_b": {"type": "string", "description": "Second asset symbol (e.g., SOL)."},
            "lookback_days": {"type": "integer", "description": "Number of days for historical analysis (default 30).", "default": 30}
        },
        "required": ["asset_a", "asset_b"],
    },
)
def analyze_pair_correlation(asset_a: str, asset_b: str, lookback_days: int = 30) -> str:
    """Analyze pair for statistical arbitrage."""
    try:
        tracker = PortfolioTracker()
        # Fetch OHLCV for both (1h interval)
        limit = lookback_days * 24
        df_a = tracker._fetch_real_ohlcv(asset_a, limit)
        df_b = tracker._fetch_real_ohlcv(asset_b, limit)
        
        if df_a.empty or df_b.empty:
            return f"Error: Could not fetch data for one or both assets ({asset_a}, {asset_b})."
            
        # Align dataframes
        combined = pd.DataFrame({
            'a': df_a['close'],
            'b': df_b['close']
        }).dropna()
        
        if len(combined) < 20:
            return "Error: Insufficient overlapping data for analysis."
            
        # 1. Calculate Correlation
        correlation = combined['a'].corr(combined['b'])
        
        # 2. Calculate Spread (Log Price Difference)
        # Using log prices helps handle different price scales
        combined['log_a'] = np.log(combined['a'])
        combined['log_b'] = np.log(combined['b'])
        
        # Simple Spread: Log(A) - Log(B)
        # Note: In institutional setups, we'd use a rolling hedge ratio (OLS)
        spread = combined['log_a'] - combined['log_b']
        
        # 3. Calculate Z-Score of Spread
        zscore = _calculate_zscore(spread).iloc[-1]
        
        # 4. Trading Signal
        # Z-Score > 2.0 -> Spread is wide (A is overvalued vs B) -> Short A, Long B
        # Z-Score < -2.0 -> Spread is narrow (A is undervalued vs B) -> Long A, Short B
        signal = "NEUTRAL"
        if zscore > 2.0:
            signal = f"SHORT {asset_a} / LONG {asset_b} (Mean Reversion)"
        elif zscore < -2.0:
            signal = f"LONG {asset_a} / SHORT {asset_b} (Mean Reversion)"
            
        result = {
            "pair": f"{asset_a.upper()}/{asset_b.upper()}",
            "correlation_30d": round(correlation, 4),
            "current_zscore": round(zscore, 2),
            "statistical_status": "EXTREME (Overbought A vs B)" if zscore > 2.5 else "EXTREME (Oversold A vs B)" if zscore < -2.5 else "NORMAL",
            "signal": signal,
            "metrics": {
                "avg_spread": round(spread.mean(), 4),
                "std_dev": round(spread.std(), 4),
                "last_spread": round(spread.iloc[-1], 4)
            },
            "interpretation": f"A Z-Score of {zscore:.2f} indicates the pair spread is {abs(zscore):.1f} standard deviations from its mean. {'Trade with caution' if abs(zscore) > 3.0 else ''}"
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Pair analysis error: {e}")
        return f"Error analyzing pair correlation: {e}"
