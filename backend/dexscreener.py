"""
DexScreener client and normalization helpers.

Docs reference:
https://docs.dexscreener.com/api/reference
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests


DEXSCREENER_BASE_URL = "https://api.dexscreener.com"


@dataclass(frozen=True)
class DexScreenerTokenSnapshot:
    chain_id: str
    token_address: str
    symbol: str | None = None
    name: str | None = None
    pair_address: str | None = None
    dex_id: str | None = None
    url: str | None = None
    price_usd: float = 0.0
    liquidity_usd: float = 0.0
    volume_24h: float = 0.0
    price_change_24h: float = 0.0
    buys_24h: float = 0.0
    sells_24h: float = 0.0
    fdv: float = 0.0
    market_cap: float = 0.0
    pair_age_hours: float | None = None
    boost_active: float = 0.0
    raw_pair: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "token_address": self.token_address,
            "symbol": self.symbol,
            "name": self.name,
            "pair_address": self.pair_address,
            "dex_id": self.dex_id,
            "url": self.url,
            "price_usd": self.price_usd,
            "liquidity_usd": self.liquidity_usd,
            "volume_24h": self.volume_24h,
            "price_change_24h": self.price_change_24h,
            "buys_24h": self.buys_24h,
            "sells_24h": self.sells_24h,
            "fdv": self.fdv,
            "market_cap": self.market_cap,
            "pair_age_hours": self.pair_age_hours,
            "boost_active": self.boost_active,
        }


class DexScreenerClient:
    """Small client for token-address oriented DexScreener lookups."""

    def __init__(self, base_url: str = DEXSCREENER_BASE_URL, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def token_pairs(self, chain_id: str, token_address: str) -> list[dict[str, Any]]:
        chain_id = quote(chain_id.strip(), safe="")
        token_address = quote(token_address.strip(), safe="")
        url = f"{self.base_url}/token-pairs/v1/{chain_id}/{token_address}"
        response = requests.get(url, timeout=self.timeout, headers={"User-Agent": "TrendForge/1.0"})
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []

    def token_snapshot(self, chain_id: str, token_address: str) -> DexScreenerTokenSnapshot | None:
        pairs = self.token_pairs(chain_id, token_address)
        if not pairs:
            return None
        return snapshot_from_pairs(chain_id, token_address, pairs)


def snapshot_from_pairs(
    chain_id: str,
    token_address: str,
    pairs: list[dict[str, Any]],
) -> DexScreenerTokenSnapshot | None:
    if not pairs:
        return None

    best = max(pairs, key=lambda pair: _safe_float(pair.get("liquidity", {}).get("usd")))
    base_token = best.get("baseToken") if isinstance(best.get("baseToken"), dict) else {}
    quote_token = best.get("quoteToken") if isinstance(best.get("quoteToken"), dict) else {}
    token_address_lower = token_address.lower()
    token = base_token
    if quote_token.get("address", "").lower() == token_address_lower:
        token = quote_token

    txns_24h = best.get("txns", {}).get("h24", {}) if isinstance(best.get("txns"), dict) else {}
    volume = best.get("volume", {}) if isinstance(best.get("volume"), dict) else {}
    price_change = best.get("priceChange", {}) if isinstance(best.get("priceChange"), dict) else {}
    liquidity = best.get("liquidity", {}) if isinstance(best.get("liquidity"), dict) else {}
    boosts = best.get("boosts", {}) if isinstance(best.get("boosts"), dict) else {}

    return DexScreenerTokenSnapshot(
        chain_id=best.get("chainId") or chain_id,
        token_address=token.get("address") or token_address,
        symbol=token.get("symbol"),
        name=token.get("name"),
        pair_address=best.get("pairAddress"),
        dex_id=best.get("dexId"),
        url=best.get("url"),
        price_usd=_safe_float(best.get("priceUsd")),
        liquidity_usd=_safe_float(liquidity.get("usd")),
        volume_24h=_safe_float(volume.get("h24")),
        price_change_24h=_safe_float(price_change.get("h24")),
        buys_24h=_safe_float(txns_24h.get("buys")),
        sells_24h=_safe_float(txns_24h.get("sells")),
        fdv=_safe_float(best.get("fdv")),
        market_cap=_safe_float(best.get("marketCap")),
        pair_age_hours=_pair_age_hours(best.get("pairCreatedAt")),
        boost_active=_safe_float(boosts.get("active")),
        raw_pair=best,
    )


def snapshot_to_forge_signals(snapshot: DexScreenerTokenSnapshot) -> dict[str, dict[str, Any]]:
    txns = snapshot.buys_24h + snapshot.sells_24h
    buy_sell_imbalance = 0.0
    if txns > 0:
        buy_sell_imbalance = (snapshot.buys_24h - snapshot.sells_24h) / txns

    volume_growth_proxy = 0.0
    if snapshot.liquidity_usd > 0:
        volume_growth_proxy = min((snapshot.volume_24h / snapshot.liquidity_usd) * 100.0, 300.0)

    market = {
        "price_change_pct": snapshot.price_change_24h,
        "volume_growth_pct": volume_growth_proxy,
        "liquidity_usd": snapshot.liquidity_usd,
        "volatility_pct": abs(snapshot.price_change_24h),
        "rsi": _price_change_to_rsi_proxy(snapshot.price_change_24h),
        "price_usd": snapshot.price_usd,
        "volume_24h": snapshot.volume_24h,
        "fdv": snapshot.fdv,
        "market_cap": snapshot.market_cap,
        "pair_age_hours": snapshot.pair_age_hours,
        "buy_sell_imbalance": round(buy_sell_imbalance, 4),
    }

    social = {
        "mention_growth_pct": min(txns, 500.0),
        "engagement_growth_pct": min(snapshot.volume_24h / 1_000.0, 500.0),
        "unique_author_count": int(min(txns, 500.0)),
    }

    manipulation_risk = _manipulation_risk(snapshot, buy_sell_imbalance)
    security = {"dex_manipulation_risk_score": manipulation_risk}
    narrative = {"catalyst_score": min(max(snapshot.boost_active * 20.0 + volume_growth_proxy * 0.15, 0.0), 100.0)}

    return {
        "market": market,
        "social": social,
        "security": security,
        "narrative": narrative,
        "metadata": snapshot.to_dict(),
    }


def _manipulation_risk(snapshot: DexScreenerTokenSnapshot, buy_sell_imbalance: float) -> float:
    risk = 0.0
    if snapshot.liquidity_usd <= 0:
        risk += 35.0
    elif snapshot.liquidity_usd < 50_000:
        risk += 35.0
    elif snapshot.liquidity_usd < 250_000:
        risk += 20.0

    if snapshot.pair_age_hours is not None:
        if snapshot.pair_age_hours < 24:
            risk += 25.0
        elif snapshot.pair_age_hours < 168:
            risk += 12.0

    if snapshot.liquidity_usd > 0 and snapshot.volume_24h / snapshot.liquidity_usd > 5:
        risk += 20.0
    if abs(snapshot.price_change_24h) > 40:
        risk += 15.0
    if abs(buy_sell_imbalance) > 0.65 and (snapshot.buys_24h + snapshot.sells_24h) >= 20:
        risk += 10.0

    return round(max(0.0, min(risk, 100.0)), 2)


def _price_change_to_rsi_proxy(price_change_pct: float) -> float:
    return round(max(1.0, min(99.0, 50.0 + price_change_pct)), 4)


def _pair_age_hours(pair_created_at: Any) -> float | None:
    created_ms = _safe_float(pair_created_at)
    if created_ms <= 0:
        return None
    created = datetime.fromtimestamp(created_ms / 1000.0, tz=timezone.utc)
    age = datetime.now(timezone.utc) - created
    return round(max(age.total_seconds() / 3600.0, 0.0), 2)


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
