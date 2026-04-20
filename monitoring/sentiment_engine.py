"""
Sentiment Engine Module
Collects and analyzes social and news sentiment for specific crypto assets using NLP.
"""

import os
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from textblob import TextBlob

logger = logging.getLogger(__name__)

class SentimentEngine:
    """Analyze market sentiment from multiple web sources."""

    def __init__(self):
        self.news_api_key = os.getenv("NEWS_API_KEY")
        self.cache = {}

    def get_comprehensive_score(self, symbol: str) -> Dict:
        """
        Get an aggregated sentiment score from all sources.
        Returns a score between -1 (very bearish) and 1 (very bullish).
        """
        # Check cache (15 minutes for real-time responsiveness)
        cache_key = f"sentiment_{symbol}"
        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(minutes=15):
                return data

        # 1. Fetch from News
        news_score = self._fetch_news_sentiment(symbol)
        
        # 2. Fetch from Social
        social_score = self._fetch_social_sentiment(symbol)
        
        # Aggregated result
        agg_score = (news_score * 0.4) + (social_score * 0.6)
        
        result = {
            "symbol": symbol,
            "aggregate_score": round(agg_score, 2),
            "news_sentiment": round(news_score, 2),
            "social_sentiment": round(social_score, 2),
            "signal": "BULLISH" if agg_score > 0.3 else "BEARISH" if agg_score < -0.3 else "NEUTRAL",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.cache[cache_key] = (result, datetime.now())
        return result

    def _fetch_news_sentiment(self, symbol: str) -> float:
        """Fetch and analyze recent news headlines."""
        if not self.news_api_key:
            # Fallback mock logic if no API key
            texts = [f"{symbol} sees massive growth and bullish momentum!", f"Is {symbol} crashing heavily right now?"]
            return sum(TextBlob(t).sentiment.polarity for t in texts) / len(texts)
            
        try:
            url = f"https://newsapi.org/v2/everything?q={symbol}+crypto&sortBy=publishedAt&apiKey={self.news_api_key}"
            resp = requests.get(url, timeout=10)
            articles = resp.json().get("articles", [])[:10]
            
            if not articles: return 0.0
            
            score = 0.0
            for art in articles:
                text = (art['title'] + " " + (art['description'] or ""))
                # Use TextBlob for true NLP sentiment
                score += TextBlob(text).sentiment.polarity
            
            return max(min(score / len(articles), 1.0), -1.0)
        except Exception as e:
            logger.error(f"News fetch error: {e}")
            return 0.0

    def _fetch_social_sentiment(self, symbol: str) -> float:
        """Fetch social media chatter using Reddit JSON API."""
        try:
            url = f"https://www.reddit.com/r/CryptoCurrency/search.json?q={symbol}&restrict_sr=1&sort=new&limit=20"
            headers = {"User-Agent": "AITradingBot/1.0 (by /u/trader)"}
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code != 200:
                logger.warning(f"Reddit API returned status {resp.status_code}")
                return 0.0
                
            data = resp.json()
            posts = data.get("data", {}).get("children", [])
            
            if not posts:
                return 0.0
                
            score = 0.0
            for post in posts:
                post_data = post.get("data", {})
                title = post_data.get("title", "")
                selftext = post_data.get("selftext", "")
                text = f"{title} {selftext}"
                
                polarity = TextBlob(text).sentiment.polarity
                score += polarity
                
            return max(min(score / len(posts), 1.0), -1.0)
        except Exception as e:
            logger.error(f"Social fetch error: {e}")
            return 0.0

def analyze_sentiment(symbol: str) -> Dict:
    """Helper for the AI Agent tool."""
    engine = SentimentEngine()
    return engine.get_comprehensive_score(symbol)
