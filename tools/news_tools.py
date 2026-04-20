import requests
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from core.tools import register_tool
from monitoring.sentiment_engine import SentimentEngine

logger = logging.getLogger(__name__)

RSS_FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CoinTelegraph": "https://cointelegraph.com/rss"
}

@register_tool(
    name="get_daily_alpha",
    description="Aggregates the latest high-impact news from CoinDesk, CoinTelegraph, and Reddit to provide a concise 'Alpha Report' of potential market catalysts (listings, regulations, upgrades).",
    input_schema={
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific symbols to focus on (e.g., ['BTC', 'ETH']).",
                "default": ["BTC", "ETH", "SOL"]
            }
        }
    },
)
def get_daily_alpha(symbols: List[str] = ["BTC", "ETH", "SOL"]) -> str:
    """Aggregate news and reddit data for an Alpha Report."""
    report = ["📰 DAILY ALPHA REPORT", "======================"]
    
    # 1. Fetch RSS News
    report.append("\n🔥 Top Market Headlines:")
    for source, url in RSS_FEEDS.items():
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")[:3]
            for item in items:
                title = item.find("title").text
                report.append(f"- [{source}] {title}")
        except Exception as e:
            logger.error(f"RSS error for {source}: {e}")
            
    # 2. Fetch Sentiment for specific symbols
    engine = SentimentEngine()
    report.append("\n📊 Focused Asset Sentiment (via Reddit/News):")
    for sym in symbols:
        try:
            res = engine.get_comprehensive_score(sym)
            score = res["aggregate_score"]
            signal = res["signal"]
            report.append(f"- {sym.upper()}: {signal} (Score: {score})")
        except Exception as e:
            logger.error(f"Sentiment error for {sym}: {e}")
            
    report.append("\n💡 Catalyst Observations:")
    # Simple logic to flag potential catalysts from headlines
    combined_text = " ".join(report).lower()
    catalysts = []
    if "etf" in combined_text: catalysts.append("ETF related developments detected.")
    if "fed" in combined_text or "inflation" in combined_text: catalysts.append("Macro/Fed news influencing markets.")
    if "sec" in combined_text or "regulation" in combined_text: catalysts.append("Regulatory pressure or updates detected.")
    if "upgrade" in combined_text or "mainnet" in combined_text: catalysts.append("Protocol tech upgrades mentioned.")
    
    if catalysts:
        for c in catalysts: report.append(f"- {c}")
    else:
        report.append("- No major specific catalysts identified in current headlines.")
        
    return "\n".join(report)
