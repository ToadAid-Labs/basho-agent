"""
Signal collection helpers for Trend Prediction Forge.

Collectors convert existing tool outputs into the normalized signal schema used
by backend.trend_prediction. Network-backed sources are optional: failures are
captured in data_quality instead of breaking the forecast.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CollectedSignals:
    market: dict[str, Any] = field(default_factory=dict)
    social: dict[str, Any] = field(default_factory=dict)
    onchain: dict[str, Any] = field(default_factory=dict)
    security: dict[str, Any] = field(default_factory=dict)
    narrative: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    data_quality: dict[str, Any] = field(default_factory=lambda: {"sources": [], "errors": []})

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "social": self.social,
            "onchain": self.onchain,
            "security": self.security,
            "narrative": self.narrative,
            "metadata": self.metadata,
            "data_quality": self.data_quality,
        }


class TrendSignalCollector:
    """Collect live-ish signals through existing repo integrations."""

    def collect(
        self,
        asset: str,
        token_address: str | None = None,
        chain: str = "base",
        historical_limit: int = 72,
    ) -> CollectedSignals:
        signals = CollectedSignals()
        resolved_asset = asset
        if token_address:
            resolved_asset = self._collect_dexscreener(token_address, chain, signals) or asset
        self._collect_market(asset, signals, historical_limit)
        if resolved_asset != asset:
            signals.metadata["resolved_asset"] = resolved_asset
        self._collect_social(resolved_asset, signals)

        if token_address:
            self._collect_security(token_address, chain, signals)
            self._collect_whale_activity(token_address, signals)
        else:
            signals.data_quality["errors"].append("token_address not supplied; skipped security and whale signals")

        signals.narrative = self._derive_narrative(signals)
        return signals

    def _collect_dexscreener(self, token_address: str, chain: str, signals: CollectedSignals) -> str | None:
        try:
            from backend.dexscreener import DexScreenerClient, snapshot_to_forge_signals

            snapshot = DexScreenerClient().token_snapshot(chain, token_address)
            if snapshot is None:
                signals.data_quality["errors"].append(
                    f"dexscreener returned no pairs for {chain}:{token_address}"
                )
                return None

            normalized = snapshot_to_forge_signals(snapshot)
            signals.market.update(normalized["market"])
            signals.social.update(normalized["social"])
            signals.security.update(normalized["security"])
            signals.narrative.update(normalized["narrative"])
            signals.metadata["dexscreener"] = normalized["metadata"]
            signals.data_quality["sources"].append("dexscreener")
            return snapshot.symbol
        except Exception as exc:  # noqa: BLE001
            signals.data_quality["errors"].append(f"dexscreener collection failed: {type(exc).__name__}: {exc}")
            return None

    def _collect_market(self, asset: str, signals: CollectedSignals, historical_limit: int) -> None:
        try:
            from tools.trading_data import fetch_historical, fetch_ticker

            raw_history = fetch_historical(asset, interval="1h", limit=historical_limit)
            candles = _json_or_none(raw_history)
            if isinstance(candles, list) and len(candles) >= 20:
                signals.market.update(_market_from_candles(candles))
                signals.data_quality["sources"].append("historical_ohlcv")
            else:
                signals.data_quality["errors"].append(f"historical_ohlcv unavailable for {asset}")

            raw_ticker = fetch_ticker(asset)
            ticker = _json_or_none(raw_ticker)
            if isinstance(ticker, dict):
                if ticker.get("price_change_pct_24h") is not None:
                    signals.market.setdefault("price_change_pct", _safe_float(ticker["price_change_pct_24h"]))
                price = _safe_float(ticker.get("price"))
                volume = _safe_float(ticker.get("volume_24h"))
                if price > 0 and volume > 0:
                    signals.market.setdefault("liquidity_usd", price * volume)
                signals.data_quality["sources"].append("ticker")
        except Exception as exc:  # noqa: BLE001
            signals.data_quality["errors"].append(f"market collection failed: {type(exc).__name__}: {exc}")

    def _collect_social(self, asset: str, signals: CollectedSignals) -> None:
        try:
            from monitoring.sentiment_engine import analyze_sentiment

            sentiment = analyze_sentiment(asset)
            aggregate = _safe_float(sentiment.get("aggregate_score"))
            signals.social.update(
                {
                    "sentiment_score": max(-1.0, min(aggregate, 1.0)),
                    "mention_growth_pct": 0.0,
                    "engagement_growth_pct": 0.0,
                    "unique_author_count": 0,
                    "bot_ratio": 0.0,
                }
            )
            signals.data_quality["sources"].append("sentiment_engine")
        except Exception as exc:  # noqa: BLE001
            signals.data_quality["errors"].append(f"sentiment collection failed: {type(exc).__name__}: {exc}")

    def _collect_security(self, token_address: str, chain: str, signals: CollectedSignals) -> None:
        try:
            from tools.security_tools import audit_token_contract

            raw = audit_token_contract(token_address=token_address, chain=chain)
            security = _security_from_audit_text(raw)
            if "dex_manipulation_risk_score" in signals.security:
                security["dex_manipulation_risk_score"] = signals.security["dex_manipulation_risk_score"]
            signals.security.update(security)
            signals.data_quality["sources"].append("goplus_security")
        except Exception as exc:  # noqa: BLE001
            signals.data_quality["errors"].append(f"security collection failed: {type(exc).__name__}: {exc}")

    def _collect_whale_activity(self, token_address: str, signals: CollectedSignals) -> None:
        try:
            from monitoring.whale_tracker import check_whale_stats

            whale = check_whale_stats(token_address)
            signals.onchain.update(_onchain_from_whale_stats(whale))
            signals.data_quality["sources"].append("whale_tracker")
        except Exception as exc:  # noqa: BLE001
            signals.data_quality["errors"].append(f"whale collection failed: {type(exc).__name__}: {exc}")

    def _derive_narrative(self, signals: CollectedSignals) -> dict[str, Any]:
        sentiment = _safe_float(signals.social.get("sentiment_score"))
        volume_growth = _safe_float(signals.market.get("volume_growth_pct"))
        price_change = _safe_float(signals.market.get("price_change_pct"))
        catalyst_score = max(0.0, min(100.0, sentiment * 35.0 + volume_growth * 0.20 + price_change * 0.50))
        return {"catalyst_score": round(catalyst_score, 2)}


def _market_from_candles(candles: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [_safe_float(c.get("close")) for c in candles if _safe_float(c.get("close")) > 0]
    volumes = [_safe_float(c.get("volume")) for c in candles if _safe_float(c.get("volume")) >= 0]
    if len(closes) < 20:
        return {}

    first = closes[0]
    last = closes[-1]
    price_change_pct = ((last - first) / first * 100.0) if first else 0.0
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1]]
    volatility_pct = _stddev(returns) * math.sqrt(24.0) * 100.0 if returns else 0.0

    recent_volume = sum(volumes[-6:]) / min(len(volumes), 6) if volumes else 0.0
    baseline = volumes[:-6] or volumes
    baseline_volume = sum(baseline) / len(baseline) if baseline else 0.0
    volume_growth_pct = ((recent_volume - baseline_volume) / baseline_volume * 100.0) if baseline_volume else 0.0

    liquidity_usd = last * recent_volume if last > 0 and recent_volume > 0 else 0.0

    return {
        "price_change_pct": round(price_change_pct, 4),
        "volume_growth_pct": round(volume_growth_pct, 4),
        "liquidity_usd": round(liquidity_usd, 2),
        "volatility_pct": round(volatility_pct, 4),
        "rsi": round(_rsi(closes), 4),
    }


def _security_from_audit_text(raw: str) -> dict[str, Any]:
    text = raw.lower()
    risk = 0.0
    honeypot = "honeypot: 🚨 yes" in text or "honeypot: yes" in text
    if honeypot:
        risk = 100.0
    if "high risk" in text:
        risk = max(risk, 75.0)
    if "do not trade" in text or "extreme risk" in text:
        risk = max(risk, 95.0)
    if "mintable: ⚠️ yes" in text or "hidden owner: ⚠️ yes" in text:
        risk = max(risk, 65.0)
    if "low risk" in text:
        risk = max(risk, 15.0)
    if raw.startswith("Error") or "no audit data found" in text:
        risk = max(risk, 35.0)
    return {"contract_risk_score": risk, "honeypot": honeypot}


def _onchain_from_whale_stats(whale: Any) -> dict[str, Any]:
    if not isinstance(whale, dict):
        return {}

    large_tx_count = _safe_float(
        whale.get("large_tx_count")
        or whale.get("large_transactions")
        or whale.get("large_transaction_count")
        or 0
    )
    smart_money_count = _safe_float(whale.get("smart_money_count") or whale.get("smart_money_wallets") or 0)
    whale_exchange_inflow_pct = min(35.0, large_tx_count * 2.5)
    holder_growth_pct = min(25.0, smart_money_count * 1.5)

    return {
        "top_holder_pct": _safe_float(whale.get("top_holder_pct") or whale.get("top_holders_pct") or 0),
        "whale_exchange_inflow_pct": round(whale_exchange_inflow_pct, 4),
        "holder_growth_pct": round(holder_growth_pct, 4),
    }


def _json_or_none(raw: str) -> Any:
    if not isinstance(raw, str) or raw.startswith("[error]") or raw.startswith("Error"):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def _rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) <= period:
        return 50.0

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-period:]
    gains = [delta for delta in recent if delta > 0]
    losses = [-delta for delta in recent if delta < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
