"""
Trading data tools - Market data fetching and technical analysis.

Uses Binance, Kraken, and Coinbase public APIs for free market data.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from core.tools import register_tool
import urllib.request
import urllib.parse
import urllib.error
import json


@register_tool(
    name="fetch_ticker",
    description="Fetch current market data for a symbol (e.g., BTC, ETH, BTCUSDT, ETHUSDT). Returns price, 24h change, volume, high, low.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Trading symbol. Use format: BTCUSDT, ETHUSDT, or just BTC (auto-adds USDT).",
            }
        },
    },
)
def fetch_ticker(symbol: str) -> str:
    """Fetch current ticker data for a symbol."""
    raw_symbol = symbol.upper().removesuffix("USDT")
    try:
        # Normalize symbol to uppercase and add USDT if not present
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"

        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read())

        result = {
            "symbol": data["symbol"],
            "price": float(data["lastPrice"]),
            "price_change_24h": float(data["priceChange"]),
            "price_change_pct_24h": float(data["priceChangePercent"]),
            "volume_24h": float(data["volume"]),
            "high_24h": float(data["highPrice"]),
            "low_24h": float(data["lowPrice"]),
            "timestamp": data["quoteVolume"],
        }

        return json.dumps(result, indent=2)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"[error] Symbol {symbol} not found on Binance. Try checking get_supported_symbols()."
        fallback = _fetch_ticker_from_trust(raw_symbol)
        return fallback or f"[error] HTTP {e.code}: {e.reason}"
    except Exception as e:
        fallback = _fetch_ticker_from_trust(raw_symbol)
        return fallback or f"[error] {type(e).__name__}: {e}"


def _fetch_ticker_from_trust(symbol: str) -> Optional[str]:
    chain_by_symbol = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "bsc",
        "MATIC": "polygon",
    }
    chain = chain_by_symbol.get(symbol.upper(), "ethereum")
    try:
        from tools.trust import trust_get_token_price

        raw = trust_get_token_price(token_symbol=symbol.upper(), chain=chain)
        data = json.loads(raw)
        price = data.get("priceUsd") or data.get("price")
        if price is None:
            return None
        return json.dumps(
            {
                "symbol": f"{symbol.upper()}USD",
                "price": float(price),
                "price_change_24h": None,
                "price_change_pct_24h": data.get("priceChange24h"),
                "volume_24h": None,
                "high_24h": None,
                "low_24h": None,
                "source": "trust_wallet",
            },
            indent=2,
        )
    except Exception:
        return None


@register_tool(
    name="fetch_historical",
    description="Fetch historical OHLCV candle data for a symbol. Intervals: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Trading symbol (e.g., BTCUSDT)"},
            "interval": {
                "type": "string",
                "description": "Candle interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)",
                "default": "1h",
            },
            "limit": {
                "type": "integer",
                "description": "Number of candles to fetch (1-1000)",
                "default": 100,
            },
        },
    },
)
def fetch_historical(symbol: str, interval: str = "1h", limit: int = 100) -> str:
    """Fetch historical OHLCV data with multi-exchange failover (Kraken, Coinbase, Bybit)."""
    symbol = symbol.upper().strip()
    
    # 1. Try Binance (Original source)
    try:
        usdt_symbol = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
        url = f"https://api.binance.com/api/v3/klines?symbol={usdt_symbol}&interval={interval}&limit={min(limit, 1000)}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read())
            candles = [{"timestamp": c[0], "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4]), "volume": float(c[5]), "source": "binance"} for c in data]
            return json.dumps(candles, indent=2)
    except Exception:
        pass

    # 2. Try Kraken (Working in current region)
    try:
        # Kraken naming convention: BTC -> XBT
        kraken_symbol = symbol.removesuffix("USDT").removesuffix("USD")
        if kraken_symbol == "BTC": kraken_symbol = "XBT"
        pair = f"{kraken_symbol}USD"
        
        # Interval mapping
        k_interval = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}.get(interval, 60)
        
        url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={k_interval}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=8) as response:
            res_data = json.loads(response.read())
            if not res_data.get('error'):
                pair_key = list(res_data['result'].keys())[0]
                data = res_data['result'][pair_key][-limit:]
                candles = [{"timestamp": c[0]*1000, "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4]), "volume": float(c[6]), "source": "kraken"} for c in data]
                return json.dumps(candles, indent=2)
    except Exception:
        pass

    # 3. Try Coinbase (Working in current region)
    try:
        cb_symbol = symbol.removesuffix("USDT").removesuffix("USD")
        # Coinbase uses granularity in seconds
        gran = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}.get(interval, 3600)
        url = f"https://api.exchange.coinbase.com/products/{cb_symbol}-USD/candles?granularity={gran}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read())[:limit]
            # Coinbase returns newest first, reverse it
            data.reverse()
            candles = [{"timestamp": c[0]*1000, "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4]), "volume": float(c[5]), "source": "coinbase"} for c in data]
            return json.dumps(candles, indent=2)
    except Exception:
        pass

    # 4. Fallback to Bybit
    return _fetch_historical_from_bybit(symbol, interval, limit)


def _fetch_historical_from_bybit(symbol: str, interval: str, limit: int) -> str:
    """Fallback to Bybit Public API (V5)."""
    try:
        clean_symbol = symbol.removesuffix("USDT").removesuffix("USD")
        symbol = f"{clean_symbol}USDT"
        
        mapping = {"1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "2h": "120", "4h": "240", "1d": "D", "1w": "W"}
        bybit_interval = mapping.get(interval, "60")
        
        url = f"https://api.bybit.com/v5/market/kline?category=spot&symbol={symbol}&interval={bybit_interval}&limit={limit}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=8) as response:
            res_data = json.loads(response.read())
            
        if res_data.get("retCode") == 0:
            data_list = res_data.get("result", {}).get("list", [])
            data_list.reverse()
            candles = [{"timestamp": int(c[0]), "open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4]), "volume": float(c[5]), "source": "bybit"} for c in data_list]
            return json.dumps(candles, indent=2)
        
        return f"[error] All sources (Binance, Kraken, Coinbase, Bybit) failed to provide data for {symbol}."
    except Exception as e:
        return f"[error] Historical data fetch failed: {e}"


@register_tool(
    name="get_supported_symbols",
    description="List trading symbols available on Binance for the USDT market. Useful before fetching ticker data.",
    input_schema={"type": "object", "properties": {}},
)
def get_supported_symbols() -> str:
    """Get list of supported symbols (limited to top 100 for speed)."""
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read())

        # Filter USDT pairs and sort by volume
        usdt_pairs = [d for d in data if d["symbol"].endswith("USDT")]
        usdt_pairs.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)

        top_symbols = usdt_pairs[:100]
        result = {
            "total_available": len(usdt_pairs),
            "top_100_by_volume": [d["symbol"] for d in top_symbols],
        }

        return json.dumps(result, indent=2)
    except Exception as e:
        return f"[error] {type(e).__name__}: {e}"


def calculate_bollinger_bands_from_data(symbol: str, candles: list[dict], period: int = 20, multiplier: float = 2.0) -> dict:
    """Core logic to calculate Bollinger Bands from candle data."""
    closes = [c["close"] for c in candles]
    if len(closes) < period:
        raise ValueError(f"Insufficient data: got {len(closes)} candles, need at least {period}")

    # Calculate SMA
    sma = sum(closes[-period:]) / period

    # Calculate standard deviation
    variance = sum((x - sma) ** 2 for x in closes[-period:]) / period
    std_dev = variance ** 0.5

    upper = sma + (multiplier * std_dev)
    lower = sma - (multiplier * std_dev)
    current_price = closes[-1]

    return {
        "symbol": symbol,
        "period": period,
        "multiplier": multiplier,
        "sma": round(sma, 4),
        "upper_band": round(upper, 4),
        "lower_band": round(lower, 4),
        "current_price": round(current_price, 4),
        "status": "above" if current_price > upper else "below" if current_price < lower else "within",
    }


@register_tool(
    name="calculate_bollinger_bands",
    description="Calculate Bollinger Bands for a symbol using the specified period and standard deviation multiplier.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Trading symbol"},
            "period": {"type": "integer", "description": "SMA period (default 20)", "default": 20},
            "multiplier": {"type": "number", "description": "Std dev multiplier (default 2)", "default": 2},
        },
    },
)
def calculate_bollinger_bands(symbol: str, period: int = 20, multiplier: float = 2.0) -> str:
    """Calculate Bollinger Bands and return upper, middle, lower bands with current price."""
    try:
        # Fetch historical data (uses the new multi-source logic)
        candles_raw = fetch_historical(symbol, interval="1h", limit=period + 50)
        if candles_raw.startswith("[error]"):
            return candles_raw

        data = json.loads(candles_raw)
        bands = calculate_bollinger_bands_from_data(symbol, data, period, multiplier)
        return json.dumps(bands, indent=2)
    except Exception as e:
        return f"[error] Bollinger calculation failed: {e}"


@register_tool(
    name="get_orderbook",
    description="Get Level 2 order book for a symbol (top 5 bids and asks).",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Trading symbol"},
        },
    },
)
def get_orderbook(symbol: str) -> str:
    """Fetch current order book data."""
    try:
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"

        url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=5"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read())

        bids = [{"price": float(b[0]), "quantity": float(b[1])} for b in data["bids"][:5]]
        asks = [{"price": float(a[0]), "quantity": float(a[1])} for a in data["asks"][:5]]
        spread = float(data["bids"][0][0]) - float(data["asks"][0][0])

        result = {
            "symbol": symbol,
            "spread": round(spread, 4),
            "bids": bids,
            "asks": asks,
        }

        return json.dumps(result, indent=2)
    except Exception as e:
        return f"[error] {type(e).__name__}: {e}"
