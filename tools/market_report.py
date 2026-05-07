import json
from typing import Any, Dict, List, Optional

from core.tools import register_tool
from tools.news_tools import get_daily_alpha
from tools.technical_analysis import detect_market_regime, get_multi_timeframe_signal, get_pro_indicators
from tools.trading_data import fetch_ticker


def _safe_json_load(raw: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _ticker_snapshot(symbol: str) -> Dict[str, Any]:
    raw = fetch_ticker(symbol)
    data = _safe_json_load(raw)
    if not data:
        return {"symbol": symbol, "ok": False, "error": raw}
    try:
        price = float(data.get("price", 0.0) or 0.0)
    except Exception:
        price = 0.0
    try:
        change_24h = float(data.get("change_24h", 0.0) or 0.0)
    except Exception:
        change_24h = 0.0
    return {
        "symbol": symbol,
        "ok": True,
        "price": price,
        "change_24h": change_24h,
    }


def _indicator_snapshot(symbol: str) -> Dict[str, Any]:
    raw = get_pro_indicators(symbol)
    data = _safe_json_load(raw)
    if not data:
        return {"ok": False, "error": raw}
    return {
        "ok": True,
        "trend": str(data.get("trend", "UNKNOWN")).upper(),
        "trend_strength": str(data.get("trend_strength", "UNKNOWN")),
        "momentum": str(data.get("momentum", "UNKNOWN")),
        "summary": str(data.get("summary", "")).strip(),
    }


def _mtf_snapshot(symbol: str) -> Dict[str, Any]:
    raw = get_multi_timeframe_signal(symbol)
    data = _safe_json_load(raw)
    if not data:
        return {"ok": False, "error": raw}
    return {
        "ok": True,
        "recommendation": str(data.get("aggregated_recommendation", "UNKNOWN")).upper(),
        "signals": data.get("signals", {}),
    }


def _regime_snapshot(symbol: str) -> Dict[str, Any]:
    raw = detect_market_regime(symbol)
    data = _safe_json_load(raw)
    if not data:
        return {"ok": False, "error": raw}
    return {
        "ok": True,
        "regime": str(data.get("regime", "UNKNOWN")).upper(),
        "reasoning": str(data.get("reasoning", "")).strip(),
        "recommended_strategy": str(data.get("recommended_strategy", "")).strip(),
    }


def _asset_report(symbol: str) -> str:
    ticker = _ticker_snapshot(symbol)
    indicators = _indicator_snapshot(symbol)
    mtf = _mtf_snapshot(symbol)
    regime = _regime_snapshot(symbol)

    lines = [f"{symbol.upper()}"]
    if ticker["ok"]:
        lines.append(f"Price: ${ticker['price']:,.2f} ({ticker['change_24h']:+.2f}% 24h)")
    else:
        lines.append(f"Price: unavailable ({ticker['error']})")

    if indicators["ok"]:
        lines.append(f"Trend: {indicators['trend']} | {indicators['trend_strength']}")
        lines.append(f"Momentum: {indicators['momentum']}")
    else:
        lines.append(f"Indicators: unavailable ({indicators['error']})")

    if mtf["ok"]:
        lines.append(f"MTF: {mtf['recommendation']}")
    else:
        lines.append(f"MTF: unavailable ({mtf['error']})")

    if regime["ok"]:
        lines.append(f"Regime: {regime['regime']}")
        if regime["recommended_strategy"]:
            lines.append(f"Strategy: {regime['recommended_strategy']}")
    else:
        lines.append(f"Regime: unavailable ({regime['error']})")

    return "\n".join(lines)


@register_tool(
    name="market_report",
    description="Generate a concise multi-asset market report in one tool call using price, trend, regime, and catalyst summaries.",
    input_schema={
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Symbols to include in the report.",
                "default": ["BTC", "ETH", "SOL"],
            }
        },
    },
)
def market_report(symbols: Optional[List[str]] = None) -> str:
    selected = [str(sym).upper().strip() for sym in (symbols or ["BTC", "ETH", "SOL"]) if str(sym).strip()]
    if not selected:
        selected = ["BTC", "ETH", "SOL"]
    selected = selected[:3]

    sections = ["MARKET REPORT", ""]
    for symbol in selected:
        sections.append(_asset_report(symbol))
        sections.append("")

    alpha = get_daily_alpha(selected)
    sections.append("Catalysts")
    sections.append(alpha)
    return "\n".join(section for section in sections if section is not None).strip()
