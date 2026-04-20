"""
Sentiment Analysis Tool
Integrates the SentimentEngine with the AI Agent.
"""

from core.tools import register_tool
from monitoring.sentiment_engine import analyze_sentiment
import json

@register_tool(
    name="check_market_sentiment",
    description="Check the current social and news sentiment for a specific cryptocurrency. Returns a score between -1 (bearish) and 1 (bullish).",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "The cryptocurrency symbol (e.g., 'BTC', 'ETH', 'SOL').",
            },
        },
        "required": ["symbol"],
    },
)
def check_market_sentiment(symbol: str) -> str:
    """Analyze sentiment for a token."""
    try:
        results = analyze_sentiment(symbol)
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error analyzing sentiment: {e}"
