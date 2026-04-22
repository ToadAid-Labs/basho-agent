"""
State-aware trend prediction for token and narrative intelligence.

This module scores attention, momentum, risk, and confidence from structured
signals. It is deliberately probabilistic: the output is a research forecast,
not financial advice and not a guaranteed price target.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _num(signals: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = signals.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _norm_pct(value: float, full_scale: float) -> float:
    """Map a percent-style value onto 0..100 with a symmetric full scale."""
    if full_scale <= 0:
        return 50.0
    return _clamp(50.0 + (value / full_scale * 50.0))


def _norm_positive(value: float, full_scale: float) -> float:
    if full_scale <= 0:
        return 0.0
    return _clamp(value / full_scale * 100.0)


@dataclass(frozen=True)
class TrendForecast:
    asset: str
    horizon: str
    mode: str
    direction: str
    attention_score: float
    momentum_score: float
    risk_score: float
    confidence: float
    composite_score: float
    drivers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    signal_quality: str = "limited"
    generated_at: str = field(default_factory=_utc_now)
    disclaimer: str = "Research forecast only. Not financial advice."

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "horizon": self.horizon,
            "mode": self.mode,
            "direction": self.direction,
            "attention_score": round(self.attention_score, 2),
            "momentum_score": round(self.momentum_score, 2),
            "risk_score": round(self.risk_score, 2),
            "confidence": round(self.confidence, 3),
            "composite_score": round(self.composite_score, 2),
            "drivers": self.drivers,
            "warnings": self.warnings,
            "signal_quality": self.signal_quality,
            "generated_at": self.generated_at,
            "disclaimer": self.disclaimer,
        }


class TrendPredictionEngine:
    """Forge-style multi-signal prediction engine."""

    VALID_MODES = {"attention", "momentum", "risk", "composite"}
    VALID_HORIZONS = {"1h", "4h", "24h", "7d"}

    def forecast(
        self,
        asset: str,
        horizon: str = "24h",
        mode: str = "composite",
        market: Mapping[str, Any] | None = None,
        social: Mapping[str, Any] | None = None,
        onchain: Mapping[str, Any] | None = None,
        security: Mapping[str, Any] | None = None,
        narrative: Mapping[str, Any] | None = None,
    ) -> TrendForecast:
        asset = asset.upper().strip()
        horizon = horizon.lower().strip()
        mode = mode.lower().strip()

        if not asset:
            raise ValueError("asset is required")
        if horizon not in self.VALID_HORIZONS:
            raise ValueError(f"horizon must be one of {sorted(self.VALID_HORIZONS)}")
        if mode not in self.VALID_MODES:
            raise ValueError(f"mode must be one of {sorted(self.VALID_MODES)}")

        market = market or {}
        social = social or {}
        onchain = onchain or {}
        security = security or {}
        narrative = narrative or {}

        drivers: list[str] = []
        warnings: list[str] = []

        attention_score = self._attention_score(social, market, narrative, drivers, warnings)
        momentum_score = self._momentum_score(market, social, drivers, warnings)
        risk_score = self._risk_score(market, onchain, security, social, warnings)
        confidence = self._confidence(market, social, onchain, security, narrative, risk_score)

        composite = (
            attention_score * 0.34
            + momentum_score * 0.36
            + (100.0 - risk_score) * 0.20
            + confidence * 100.0 * 0.10
        )

        if mode == "attention":
            basis = attention_score
        elif mode == "momentum":
            basis = momentum_score
        elif mode == "risk":
            basis = risk_score
        else:
            basis = composite

        direction = self._direction(mode, basis, risk_score, confidence)
        signal_quality = self._signal_quality(market, social, onchain, security, narrative)

        if confidence < 0.45:
            warnings.append("Low confidence: signal coverage or agreement is limited.")
        if risk_score >= 70:
            warnings.append("High risk regime: avoid treating trend strength as trade approval.")
        if not drivers:
            drivers.append("Insufficient positive signal strength; forecast is mostly neutral.")

        return TrendForecast(
            asset=asset,
            horizon=horizon,
            mode=mode,
            direction=direction,
            attention_score=attention_score,
            momentum_score=momentum_score,
            risk_score=risk_score,
            confidence=confidence,
            composite_score=composite,
            drivers=_dedupe(drivers),
            warnings=_dedupe(warnings),
            signal_quality=signal_quality,
        )

    def _attention_score(
        self,
        social: Mapping[str, Any],
        market: Mapping[str, Any],
        narrative: Mapping[str, Any],
        drivers: list[str],
        warnings: list[str],
    ) -> float:
        mention_growth = _num(social, "mention_growth_pct")
        engagement_growth = _num(social, "engagement_growth_pct")
        sentiment = _num(social, "sentiment_score")
        unique_authors = _num(social, "unique_author_count")
        bot_ratio = _num(social, "bot_ratio")
        volume_growth = _num(market, "volume_growth_pct")
        catalyst_score = _num(narrative, "catalyst_score")

        score = (
            _norm_positive(mention_growth, 250.0) * 0.26
            + _norm_positive(engagement_growth, 300.0) * 0.18
            + _norm_pct(sentiment * 100.0, 100.0) * 0.16
            + _norm_positive(unique_authors, 250.0) * 0.14
            + _norm_positive(volume_growth, 180.0) * 0.16
            + _clamp(catalyst_score) * 0.10
        )

        if mention_growth >= 80:
            drivers.append(f"Social mentions accelerated {mention_growth:.0f}% versus baseline.")
        if engagement_growth >= 80:
            drivers.append(f"Engagement accelerated {engagement_growth:.0f}% versus baseline.")
        if sentiment >= 0.35:
            drivers.append("Recent social/news sentiment is strongly positive.")
        elif sentiment <= -0.35:
            warnings.append("Recent social/news sentiment is strongly negative.")
        if catalyst_score >= 65:
            drivers.append("Narrative or event catalyst strength is elevated.")
        if bot_ratio >= 0.35:
            score -= 15.0
            warnings.append("Possible inorganic attention: bot-like social ratio is elevated.")

        return _clamp(score)

    def _momentum_score(
        self,
        market: Mapping[str, Any],
        social: Mapping[str, Any],
        drivers: list[str],
        warnings: list[str],
    ) -> float:
        price_change = _num(market, "price_change_pct")
        volume_growth = _num(market, "volume_growth_pct")
        liquidity_usd = _num(market, "liquidity_usd")
        volatility = _num(market, "volatility_pct")
        rsi = _num(market, "rsi", 50.0)
        sentiment = _num(social, "sentiment_score")

        score = (
            _norm_pct(price_change, 25.0) * 0.30
            + _norm_positive(volume_growth, 200.0) * 0.22
            + _norm_positive(liquidity_usd, 2_000_000.0) * 0.16
            + _norm_pct(sentiment * 100.0, 100.0) * 0.12
            + _rsi_momentum(rsi) * 0.12
            + (100.0 - _norm_positive(volatility, 30.0)) * 0.08
        )

        if price_change >= 8:
            drivers.append(f"Price momentum is positive at {price_change:.1f}% over the measured window.")
        elif price_change <= -8:
            warnings.append(f"Price momentum is negative at {price_change:.1f}% over the measured window.")
        if volume_growth >= 100:
            drivers.append(f"Trading volume expanded {volume_growth:.0f}% versus baseline.")
        if liquidity_usd and liquidity_usd < 100_000:
            warnings.append("Liquidity is thin; price movement may be easy to manipulate.")
        if rsi >= 78:
            score -= 10.0
            warnings.append("RSI is extremely hot; trend may be crowded.")
        if volatility >= 25:
            score -= 8.0
            warnings.append("Volatility is extreme; trend continuation reliability is lower.")

        return _clamp(score)

    def _risk_score(
        self,
        market: Mapping[str, Any],
        onchain: Mapping[str, Any],
        security: Mapping[str, Any],
        social: Mapping[str, Any],
        warnings: list[str],
    ) -> float:
        holder_concentration = _num(onchain, "top_holder_pct")
        whale_exchange_inflow = _num(onchain, "whale_exchange_inflow_pct")
        holder_growth = _num(onchain, "holder_growth_pct")
        liquidity_usd = _num(market, "liquidity_usd")
        volatility = _num(market, "volatility_pct")
        contract_risk = _num(security, "contract_risk_score")
        dex_manipulation_risk = _num(security, "dex_manipulation_risk_score")
        honeypot = bool(security.get("honeypot", False))
        bot_ratio = _num(social, "bot_ratio")

        liquidity_risk = 0.0
        if liquidity_usd <= 0:
            liquidity_risk = 45.0
        elif liquidity_usd < 50_000:
            liquidity_risk = 80.0
        elif liquidity_usd < 250_000:
            liquidity_risk = 55.0
        elif liquidity_usd < 1_000_000:
            liquidity_risk = 30.0

        score = (
            _clamp(holder_concentration) * 0.20
            + _norm_positive(whale_exchange_inflow, 30.0) * 0.18
            + liquidity_risk * 0.17
            + _norm_positive(volatility, 35.0) * 0.14
            + max(_clamp(contract_risk), _clamp(dex_manipulation_risk)) * 0.18
            + _norm_positive(bot_ratio, 0.6) * 0.09
            + (100.0 - _norm_positive(holder_growth, 25.0)) * 0.04
        )

        if honeypot:
            score = 100.0
            warnings.append("Security signal indicates honeypot behavior.")
        if holder_concentration >= 45:
            warnings.append(f"Holder concentration is high: top holders control {holder_concentration:.1f}%.")
        if whale_exchange_inflow >= 10:
            warnings.append("Whale exchange inflows are elevated.")
        if contract_risk >= 65:
            warnings.append("Contract/security risk score is elevated.")
        if dex_manipulation_risk >= 65:
            warnings.append("DEX manipulation risk is elevated.")

        return _clamp(score)

    def _confidence(
        self,
        market: Mapping[str, Any],
        social: Mapping[str, Any],
        onchain: Mapping[str, Any],
        security: Mapping[str, Any],
        narrative: Mapping[str, Any],
        risk_score: float,
    ) -> float:
        groups = [market, social, onchain, security, narrative]
        populated_groups = sum(1 for group in groups if any(v not in (None, "", []) for v in group.values()))
        coverage = populated_groups / len(groups)

        market_agrees = _num(market, "price_change_pct") > 0 and _num(market, "volume_growth_pct") > 0
        social_agrees = _num(social, "mention_growth_pct") > 0 and _num(social, "sentiment_score") >= 0
        onchain_agrees = _num(onchain, "holder_growth_pct") >= 0 and _num(onchain, "whale_exchange_inflow_pct") < 10
        agreement = sum([market_agrees, social_agrees, onchain_agrees]) / 3.0

        risk_penalty = max(0.0, (risk_score - 55.0) / 100.0)
        confidence = 0.25 + coverage * 0.45 + agreement * 0.25 - risk_penalty
        return round(max(0.1, min(confidence, 0.95)), 3)

    def _direction(self, mode: str, basis: float, risk_score: float, confidence: float) -> str:
        if mode == "risk":
            if basis >= 70:
                return "risk_spiking"
            if basis >= 45:
                return "risk_elevated"
            return "risk_contained"

        if confidence < 0.35:
            return "uncertain"
        if risk_score >= 82:
            return "avoid_high_risk"
        if basis >= 72:
            return "up_trend_likely"
        if basis >= 57:
            return "watch_positive_bias"
        if basis <= 35:
            return "down_or_fading"
        return "neutral"

    def _signal_quality(
        self,
        market: Mapping[str, Any],
        social: Mapping[str, Any],
        onchain: Mapping[str, Any],
        security: Mapping[str, Any],
        narrative: Mapping[str, Any],
    ) -> str:
        populated = sum(1 for group in (market, social, onchain, security, narrative) if group)
        if populated >= 4:
            return "strong"
        if populated >= 2:
            return "moderate"
        return "limited"


def _rsi_momentum(rsi: float) -> float:
    if rsi <= 0:
        return 50.0
    if 45 <= rsi <= 65:
        return 72.0
    if 35 <= rsi < 45 or 65 < rsi <= 75:
        return 58.0
    if rsi < 35:
        return 38.0
    return 42.0


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
