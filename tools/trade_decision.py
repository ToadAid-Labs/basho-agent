import json
import re
from typing import Any, Dict, Optional

from core.tools import register_tool
from backend.paper_trading import get_paper_trading_account
from tools.trading_data import fetch_ticker
from tools.technical_analysis import (
    get_multi_timeframe_signal,
    analyze_market_structure,
    get_pro_indicators,
)
from tools.swing_tools import get_swing_setup
from tools.trading_control import analyze_market_trend


def _safe_json_load(raw: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _extract_float(pattern: str, text: str) -> Optional[float]:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _parse_mtf_signal(raw: str) -> Dict[str, Any]:
    data = _safe_json_load(raw) or {}
    recommendation = str(data.get("aggregated_recommendation", "NEUTRAL")).upper()
    return {
        "raw": data,
        "recommendation": recommendation,
        "bullish": recommendation in {"STRONG_BUY", "ACCUMULATE"},
        "bearish": recommendation in {"STRONG_SELL", "DISTRIBUTE"},
    }


def _parse_pro_indicators(raw: str) -> Dict[str, Any]:
    data = _safe_json_load(raw) or {}
    momentum = str(data.get("momentum", ""))
    rsi = _extract_float(r"RSI:\s*([0-9]+(?:\.[0-9]+)?)", momentum)
    trend = str(data.get("trend", "NEUTRAL")).upper()
    strength_text = str(data.get("trend_strength", "")).upper()
    return {
        "raw": data,
        "trend": trend,
        "strong": "STRONG" in strength_text,
        "rsi": rsi,
        "overbought": rsi is not None and rsi >= 70.0,
        "oversold": rsi is not None and rsi <= 30.0,
    }


def _parse_swing_setup(raw: str) -> Dict[str, Any]:
    data = _safe_json_load(raw) or {}
    trade_plan = data.get("trade_plan", {}) if isinstance(data.get("trade_plan"), dict) else {}
    golden_pocket = (
        data.get("golden_pocket_zone", {})
        if isinstance(data.get("golden_pocket_zone"), dict)
        else {}
    )
    entry_low = _extract_float(
        r"([0-9]+(?:\.[0-9]+)?)\s*-\s*[0-9]+(?:\.[0-9]+)?",
        str(trade_plan.get("entry_range", "")),
    )
    entry_high = _extract_float(
        r"[0-9]+(?:\.[0-9]+)?\s*-\s*([0-9]+(?:\.[0-9]+)?)",
        str(trade_plan.get("entry_range", "")),
    )
    entry_mid = (
        (entry_low + entry_high) / 2.0
        if entry_low is not None and entry_high is not None
        else None
    )
    return {
        "raw": data,
        "setup_quality": str(data.get("setup_quality", "LOW")).upper(),
        "current_price": float(
            data.get("analysis", {}).get("current_price", data.get("current_price", entry_mid or 0.0))
            if isinstance(data.get("analysis"), dict)
            else data.get("current_price", entry_mid or 0.0)
        ),
        "stop_loss": float(trade_plan.get("stop_loss", 0.0) or 0.0),
        "take_profit": float(trade_plan.get("take_profit", 0.0) or 0.0),
        "entry_low": entry_low,
        "entry_high": entry_high,
        "rr_ratio": _extract_float(r"1:([0-9]+(?:\.[0-9]+)?)", str(trade_plan.get("risk_reward_ratio", ""))),
        "in_zone": str(golden_pocket.get("status", "")).upper() == "IN_ZONE",
    }


def _parse_market_trend(raw: str) -> Dict[str, Any]:
    text = raw or ""
    text_upper = text.upper()
    if "POTENTIAL BUY" in text_upper or "BOLLINGER STATUS: BELOW" in text_upper:
        bias = "BULLISH"
    elif "POTENTIAL SELL" in text_upper or "BOLLINGER STATUS: ABOVE" in text_upper:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"
    return {"raw": text, "bias": bias}


def _parse_structure(raw: str) -> Dict[str, Any]:
    data = _safe_json_load(raw) or {}
    supports = [float(v) for v in data.get("major_support", []) if isinstance(v, (int, float))]
    resistances = [float(v) for v in data.get("major_resistance", []) if isinstance(v, (int, float))]
    current_price = float(data.get("current_price", 0.0) or 0.0)
    nearest_support = max((s for s in supports if s <= current_price), default=None)
    nearest_resistance = min((r for r in resistances if r >= current_price), default=None)
    return {
        "raw": data,
        "supports": supports,
        "resistances": resistances,
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
    }


def _confidence_from_score(score: float) -> float:
    confidence = 0.5 + (score / 12.0)
    return max(0.05, min(0.95, confidence))


def _kelly_fraction(confidence: float, reward_risk: float) -> float:
    if reward_risk <= 0:
        return 0.0
    p = confidence
    q = 1.0 - p
    raw = (reward_risk * p - q) / reward_risk
    return max(0.0, raw)


def _fetch_current_price(symbol: str) -> Optional[float]:
    raw = fetch_ticker(symbol)
    data = _safe_json_load(raw)
    if not data:
        return None
    try:
        return float(data.get("price", 0.0))
    except Exception:
        return None


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _position_value(account: Any, symbol: str, price: float) -> float:
    try:
        quantity = float(account.positions.get(symbol, 0))
        return quantity * price
    except Exception:
        return 0.0


@register_tool(
    name="trade_decision_engine",
    description="Combine technical trend, momentum, structure, whale flow, and risk controls into one trade-or-no-trade decision with position sizing.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Trading symbol to analyze (e.g. BTC, ETH, SOL).",
            },
            "user_id": {
                "type": "integer",
                "description": "Optional paper account user ID for balance and concentration checks.",
            },
            "token_address": {
                "type": "string",
                "description": "Optional on-chain token address for whale flow checks.",
            },
            "chain": {
                "type": "string",
                "description": "Chain for token_address checks.",
                "default": "base",
            },
            "account_balance": {
                "type": "number",
                "description": "Fallback account balance to size against if no user_id account is available.",
                "default": 10000.0,
            },
            "risk_per_trade_pct": {
                "type": "number",
                "description": "Target risk per trade as a percentage of account equity.",
                "default": 1.0,
            },
            "max_position_size_pct": {
                "type": "number",
                "description": "Maximum notional position size as a percentage of account equity.",
                "default": 10.0,
            },
            "min_reward_risk": {
                "type": "number",
                "description": "Minimum acceptable reward/risk ratio.",
                "default": 1.5,
            },
        },
        "required": ["symbol"],
    },
)
def trade_decision_engine(
    symbol: str,
    user_id: Optional[int] = None,
    token_address: Optional[str] = None,
    chain: str = "base",
    account_balance: float = 10000.0,
    risk_per_trade_pct: float = 1.0,
    max_position_size_pct: float = 10.0,
    min_reward_risk: float = 1.5,
) -> str:
    """Generate a composite trade decision from the existing signal stack."""
    symbol = _normalize_symbol(symbol)

    ticker_price = _fetch_current_price(symbol)
    pro_raw = get_pro_indicators(symbol)
    mtf_raw = get_multi_timeframe_signal(symbol)
    swing_raw = get_swing_setup(symbol)
    trend_raw = analyze_market_trend(symbol)
    structure_raw = analyze_market_structure(symbol)

    pro = _parse_pro_indicators(pro_raw)
    mtf = _parse_mtf_signal(mtf_raw)
    swing = _parse_swing_setup(swing_raw)
    trend = _parse_market_trend(trend_raw)
    structure = _parse_structure(structure_raw)

    current_price = (
        ticker_price
        if ticker_price is not None and ticker_price > 0
        else swing.get("current_price")
        if swing.get("current_price", 0.0) > 0
        else None
    )
    if current_price is None and swing.get("entry_low") is not None and swing.get("entry_high") is not None:
        current_price = (float(swing["entry_low"]) + float(swing["entry_high"])) / 2.0

    account = get_paper_trading_account(user_id) if user_id is not None else None
    available_capital = float(account.cash) if account is not None else float(account_balance)

    score = 0.0
    reasons = []
    vetoes = []

    if pro["trend"] == "UP":
        score += 2.0
        reasons.append("Primary trend is UP.")
    elif pro["trend"] == "DOWN":
        score -= 2.0
        reasons.append("Primary trend is DOWN.")

    if pro["strong"]:
        score += 0.5 if pro["trend"] == "UP" else -0.5
        reasons.append("Trend strength is high.")

    rsi = pro["rsi"]
    if rsi is not None:
        reasons.append(f"RSI is {rsi:.1f}.")
        if rsi <= 30.0:
            score += 1.5
            reasons.append("RSI is oversold.")
        elif rsi >= 80.0:
            score -= 2.0
            reasons.append("RSI is deeply overbought.")
        elif rsi >= 70.0:
            score -= 1.2
            reasons.append("RSI is overbought.")
        elif 45.0 <= rsi <= 60.0:
            score += 0.5
            reasons.append("RSI is in a constructive range.")

    if mtf["bullish"]:
        score += 2.0
        reasons.append("Multi-timeframe signal is bullish.")
    elif mtf["bearish"]:
        score -= 2.0
        reasons.append("Multi-timeframe signal is bearish.")

    setup_quality = swing["setup_quality"]
    if setup_quality.startswith("PREMIUM"):
        score += 2.5
        reasons.append("Swing setup is premium.")
    elif setup_quality.startswith("HIGH"):
        score += 1.25
        reasons.append("Swing setup is high quality.")
    else:
        score -= 0.5
        reasons.append("Swing setup is weak.")

    if swing["in_zone"]:
        score += 1.0
        reasons.append("Price is inside the swing entry zone.")
    else:
        score -= 0.5
        reasons.append("Price is outside the ideal swing zone.")

    if trend["bias"] == "BULLISH":
        score += 0.75
        reasons.append("Bollinger trend bias is bullish.")
    elif trend["bias"] == "BEARISH":
        score -= 0.75
        reasons.append("Bollinger trend bias is bearish.")

    if structure["nearest_support"] is not None and current_price:
        support_distance_pct = abs(current_price - structure["nearest_support"]) / current_price * 100.0
        if support_distance_pct <= 2.0:
            score += 0.75
            reasons.append("Price is close to support.")

    if structure["nearest_resistance"] is not None and current_price:
        resistance_distance_pct = abs(structure["nearest_resistance"] - current_price) / current_price * 100.0
        if resistance_distance_pct <= 2.0:
            score -= 0.75
            reasons.append("Price is close to resistance.")

    whale_signal = None
    if token_address:
        try:
            from tools.whale_tracker_tool import check_whale_activity

            whale_raw = check_whale_activity(token_address)
            whale_signal = _safe_json_load(whale_raw) or {}
            whale_state = str(whale_signal.get("signal", "NEUTRAL")).upper()
            if whale_state == "STRONG_BUY":
                score += 1.5
                reasons.append("Whale flow is strongly positive.")
            elif whale_state == "ACCUMULATING":
                score += 1.0
                reasons.append("Whale flow indicates accumulation.")
            elif whale_state == "ERROR":
                vetoes.append("Whale scan failed; ignoring flow signal.")
        except Exception as exc:
            vetoes.append(f"Whale scan unavailable: {exc}")

    if symbol == "BTC" and rsi is not None and rsi >= 99.0:
        vetoes.append("BTC RSI is 99 or higher; no long trade allowed.")

    if account is not None:
        total_value = float(
            account.get_total_value({sym: _fetch_current_price(sym) or 0.0 for sym in account.positions})
        )
        current_allocation = 0.0
        if current_price and symbol in account.positions and total_value > 0:
            current_allocation = _position_value(account, symbol, current_price) / total_value * 100.0
            if current_allocation > max_position_size_pct:
                vetoes.append(
                    f"Existing {symbol} allocation is {current_allocation:.1f}% which exceeds the limit."
                )
                score -= 1.5
        if total_value <= 0:
            available_capital = float(account.cash)

    confidence = _confidence_from_score(score)
    reward_risk = swing["rr_ratio"] or min_reward_risk
    reward_risk = max(reward_risk, min_reward_risk)
    kelly = _kelly_fraction(confidence, reward_risk)
    conservative_kelly_pct = kelly * 25.0

    requested_risk_pct = min(float(risk_per_trade_pct), float(max_position_size_pct))
    recommended_risk_pct = min(requested_risk_pct, conservative_kelly_pct) if kelly > 0 else 0.0

    stop_loss = swing["stop_loss"] if swing["stop_loss"] > 0 else None
    take_profit = swing["take_profit"] if swing["take_profit"] > 0 else None
    quantity = 0.0
    notional = 0.0
    actual_risk_pct = 0.0

    if current_price and stop_loss and current_price > 0:
        stop_distance = abs(current_price - stop_loss)
        if stop_distance > 0 and recommended_risk_pct > 0:
            risk_dollars = available_capital * (recommended_risk_pct / 100.0)
            quantity = risk_dollars / stop_distance
            notional = quantity * current_price
            max_notional = available_capital * (max_position_size_pct / 100.0)
            if notional > max_notional and current_price > 0:
                quantity = max_notional / current_price
                notional = quantity * current_price
            actual_risk_pct = (quantity * stop_distance / available_capital) * 100.0 if available_capital > 0 else 0.0

    action = "WAIT"
    direction = "NEUTRAL"
    if not vetoes:
        if score >= 4.0 and confidence >= 0.6:
            action = "BUY"
            direction = "LONG"
        elif score <= -4.0 and confidence >= 0.6:
            action = "SELL"
            direction = "REDUCE"
        else:
            action = "WAIT"
            direction = "NEUTRAL"

    if action == "BUY" and symbol == "BTC" and rsi is not None and rsi >= 99.0:
        action = "WAIT"
        direction = "NEUTRAL"

    if action != "BUY":
        quantity = 0.0
        notional = 0.0
        actual_risk_pct = 0.0
        recommended_risk_pct = 0.0

    summary = "No trade."
    if action == "BUY":
        summary = "Long setup is aligned across trend, momentum, and structure."
    elif action == "SELL":
        summary = "Bearish conditions favor reducing or avoiding long exposure."
    elif vetoes:
        summary = "Trade vetoed by guardrails."

    result = {
        "symbol": symbol,
        "action": action,
        "direction": direction,
        "confidence": round(confidence, 4),
        "score": round(score, 4),
        "summary": summary,
        "current_price": round(current_price, 8) if current_price else None,
        "account": {
            "user_id": user_id,
            "available_capital": round(available_capital, 2),
        },
        "signals": {
            "pro_indicators": {
                "trend": pro["trend"],
                "rsi": rsi,
                "strong": pro["strong"],
            },
            "multi_timeframe": mtf["raw"],
            "swing_setup": swing["raw"],
            "market_trend": trend["raw"],
            "market_structure": structure["raw"],
            "whale_activity": whale_signal,
        },
        "risk_plan": {
            "risk_per_trade_pct": round(requested_risk_pct, 4),
            "kelly_fraction_pct": round(conservative_kelly_pct, 4),
            "recommended_risk_pct": round(recommended_risk_pct, 4),
            "max_position_size_pct": round(float(max_position_size_pct), 4),
            "entry": round(current_price, 8) if current_price else None,
            "stop_loss": round(stop_loss, 8) if stop_loss else None,
            "take_profit": round(take_profit, 8) if take_profit else None,
            "reward_risk": round(reward_risk, 4),
            "quantity": round(quantity, 8),
            "notional": round(notional, 2),
            "actual_risk_pct": round(actual_risk_pct, 4),
        },
        "reasons": reasons,
        "vetoes": vetoes,
    }

    return json.dumps(result, indent=2)
