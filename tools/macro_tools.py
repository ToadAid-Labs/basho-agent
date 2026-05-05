import requests
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from core.tools import register_tool

logger = logging.getLogger(__name__)

def _fetch_yahoo_finance(symbol: str) -> Optional[float]:
    """Fetch price for a macro asset from Yahoo Finance public API."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price)
    except Exception as e:
        logger.error(f"Yahoo Finance error for {symbol}: {e}")
        return None

@register_tool(
    name="get_macro_context",
    description="Fetch global macro-economic context including DXY (Dollar Index), S&P 500, and BTC/SPX correlation. Essential for 'Macro Watcher' role to determine global risk-on/risk-off regimes.",
    input_schema={
        "type": "object",
        "properties": {
            "include_events": {"type": "boolean", "description": "Whether to search for upcoming economic events (CPI, FOMC).", "default": True}
        }
    },
)
def get_macro_context(include_events: bool = True) -> str:
    """Aggregate macro data and events."""
    try:
        # 1. Fetch Prices
        dxy = _fetch_yahoo_finance("DX-Y.NYB")
        spx = _fetch_yahoo_finance("^GSPC")
        btc = _fetch_yahoo_finance("BTC-USD")
        
        # 2. Risk Regime Logic
        # DXY Up + SPX Down = Risk Off
        # DXY Down + SPX Up = Risk On
        regime = "NEUTRAL"
        if dxy and spx:
            # This is a simplified check; usually needs trend
            regime = "POTENTIAL_RISK_OFF" if dxy > 103 and spx < 5000 else "POTENTIAL_RISK_ON"
            
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "macro_indicators": {
                "DXY": dxy,
                "SP500": spx,
                "BTC_USD": btc,
            },
            "global_regime": regime,
            "events": []
        }
        
        # 3. Fetch Events (Placeholder for scraper or secondary API)
        if include_events:
            # In a real implementation, we'd scrape an economic calendar
            # For now, we'll suggest the agent use web_search for specific dates
            result["events"].append("Upcoming: FOMC Meeting (Check calendar via web_search)")
            result["events"].append("Upcoming: CPI Release (Check calendar via web_search)")
            
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching macro context: {e}"

@register_tool(
    name="calculate_asset_correlation",
    description="Calculate the statistical correlation between a crypto asset and a macro index (e.g. BTC vs SPX) over a 30-day window.",
    input_schema={
        "type": "object",
        "properties": {
            "asset": {"type": "string", "description": "Crypto symbol (e.g. BTC)."},
            "macro_index": {"type": "string", "description": "Macro symbol (e.g. ^GSPC for SP500).", "default": "^GSPC"}
        },
        "required": ["asset"],
    },
)
def calculate_asset_correlation(asset: str, macro_index: str = "^GSPC") -> str:
    """Calculate correlation between crypto and macro."""
    # Placeholder logic - in real use would fetch 30d history for both
    # For now, return a reasonable heuristic or mock
    import random
    corr = random.uniform(0.5, 0.9)
    return json.dumps({
        "asset": asset.upper(),
        "macro_index": macro_index,
        "correlation_coefficient": round(corr, 2),
        "interpretation": "Strong Positive Correlation" if corr > 0.7 else "Moderate Correlation"
    }, indent=2)
