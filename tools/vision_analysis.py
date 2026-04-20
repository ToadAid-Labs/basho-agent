import io
import os
import base64
import logging
from typing import Optional
import pandas as pd

from core.tools import register_tool

logger = logging.getLogger(__name__)

# Try to import mplfinance, which might not be available in all envs
try:
    import mplfinance as mpf
except ImportError:
    mpf = None

def _generate_chart_image(df: pd.DataFrame, symbol: str) -> Optional[bytes]:
    """Generate a candlestick chart image from OHLCV data."""
    if mpf is None:
        logger.error("mplfinance is not installed. Cannot generate chart.")
        return None
        
    try:
        buf = io.BytesIO()
        mpf.plot(
            df,
            type='candle',
            style='charles',
            title=f'{symbol} Price Chart',
            ylabel='Price',
            volume=True,
            savefig=dict(fname=buf, dpi=100, format='png', bbox_inches='tight')
        )
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Failed to generate chart image: {e}")
        return None

def _analyze_with_anthropic(image_bytes: bytes, prompt: str) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )
    return response.content[0].text

def _analyze_with_openai(image_bytes: bytes, prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_image}",
                        },
                    },
                ],
            }
        ],
        max_tokens=1000,
    )
    return response.choices[0].message.content

def _analyze_with_gemini(image_bytes: bytes, prompt: str) -> str:
    try:
        # Try new google-genai
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type='image/png'),
                prompt
            ]
        )
        return response.text
    except ImportError:
        # Fallback to google.generativeai
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content([
            {"mime_type": "image/png", "data": image_bytes},
            prompt
        ])
        return response.text

@register_tool(
    name="analyze_chart_vision",
    description="Takes a live candlestick chart screenshot of a token and uses a Vision LLM to identify complex visual patterns (Elliott Waves, Head & Shoulders, S/R lines). Returns a concise visual analysis.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Trading symbol to chart (e.g., BTC, ETH)",
            },
            "periods": {
                "type": "integer",
                "description": "Number of hourly candles to chart. Default is 100.",
                "default": 100
            }
        },
        "required": ["symbol"],
    },
)
def analyze_chart_vision(symbol: str, periods: int = 100) -> str:
    """Generate a chart and analyze it using a Vision model."""
    try:
        from backend.portfolio_dashboard import PortfolioTracker
        tracker = PortfolioTracker()
        
        # Get OHLCV
        df = tracker._fetch_real_ohlcv(symbol, periods)
        if df.empty:
            return f"Error: Could not fetch data for {symbol}."
            
        # Ensure index is datetime for mplfinance
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
            
        # Generate chart
        image_bytes = _generate_chart_image(df, symbol)
        if not image_bytes:
            return "Error: Failed to generate chart image. Ensure mplfinance is installed."
            
        prompt = (
            "Analyze this candlestick chart. Identify any key technical patterns "
            "(like Elliott Waves, Head & Shoulders, double tops/bottoms, Support/Resistance zones), "
            "determine the overarching trend direction, and provide a very brief, concise actionable summary."
        )
        
        # Dispatch to the active provider based on env vars
        # Prioritize the active provider if set, otherwise fallback
        provider = os.getenv("MODEL_PROVIDER", "anthropic").lower()
        
        if provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
            return _analyze_with_anthropic(image_bytes, prompt)
        elif provider == "openai" and os.getenv("OPENAI_API_KEY"):
            return _analyze_with_openai(image_bytes, prompt)
        elif provider == "gemini" and os.getenv("GEMINI_API_KEY"):
            return _analyze_with_gemini(image_bytes, prompt)
            
        # Fallbacks if the specific provider key isn't set but others are
        if os.getenv("ANTHROPIC_API_KEY"):
            return _analyze_with_anthropic(image_bytes, prompt)
        elif os.getenv("OPENAI_API_KEY"):
            return _analyze_with_openai(image_bytes, prompt)
        elif os.getenv("GEMINI_API_KEY"):
            return _analyze_with_gemini(image_bytes, prompt)
            
        return "Error: No valid API key found for Anthropic, OpenAI, or Gemini to perform vision analysis."
    except Exception as e:
        logger.error(f"Error in analyze_chart_vision: {e}", exc_info=True)
        return f"Error analyzing chart visually: {e}"
