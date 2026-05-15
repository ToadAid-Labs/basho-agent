"""Read-only Base Insider Hunt detector.

What it detects:
- high-gain, low-unit-price Base tokens
- early wallet clusters before the first major volume spike
- repeated high-ROI wallet behavior across a configurable 30-day lookback
- coordinated new-token buys that pass contract-risk gating

Required data for production accuracy:
- token discovery with 48h gain, unit price, liquidity, liquidity status, and freshness timestamp
- timestamped candles for spike detection
- timestamped buy events with wallet labels or flags for router/deployer/contract exclusion
- per-wallet trade history with invested value and exit or estimated current value
- recent wallet-buy monitoring data
- contract-audit fields for mintability, taxes, source verification, honeypot risk, owner controls, and liquidity state

Current provider limitation:
- the default TWAK adapter can discover candidate tokens and fetch market snapshots/audits,
  but it cannot yet resolve early buyers or wallet history reliably enough for production use

Why watchlist-only:
- signals are intentionally fail-closed and are never allowed to execute trades, construct
  transactions, access keys, or recommend automatic execution
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from core.tools import register_tool

logger = logging.getLogger(__name__)

WATCHLIST_WARNING = (
    "This is a high-risk watchlist signal, not financial advice. No trade has been executed."
)
INSIDER_HUNT_METADATA = {
    "read_only": True,
    "requires_human_confirmation": True,
    "live_execution": False,
    "tool_class": "watchlist",
}


def _run_twak(args: list[str]) -> str:
    """Helper to run twak commands."""
    try:
        result = subprocess.run(
            ["twak"] + args,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            return f"[error] twak: {result.stderr or result.stdout}"
        return result.stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"[error] {type(exc).__name__}: {exc}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_address(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        if value > 1_000_000_000_000:
            value = value / 1000.0
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            return _parse_timestamp(int(raw))
        raw = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _normalize_liquidity_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"burned", "locked", "unlocked", "unknown"}:
        return raw
    if "unlock" in raw:
        return "unlocked"
    if "burn" in raw:
        return "burned"
    if "lock" in raw:
        return "locked"
    return "unknown"


def _normalize_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    raw = str(value or "").strip().lower()
    if raw in {"1", "true", "yes", "y", "detected"}:
        return True
    if raw in {"0", "false", "no", "n", "none"}:
        return False
    return None


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _is_suspect_wallet_label(event: dict[str, Any]) -> bool:
    label = " ".join(
        str(event.get(key, "")).lower()
        for key in ("wallet_label", "address_type", "tag", "notes")
    )
    return any(word in label for word in ("router", "pair", "lp", "contract", "deployer"))


@dataclass
class HuntConfig:
    chain: str = "base"
    min_gain_pct_48h: float = 1000.0
    max_unit_price: float = 0.01
    preferred_low_unit_price: float = 0.0001
    min_liquidity_usd: float = 25_000.0
    early_buyer_min_usd: float = 500.0
    early_buyer_limit: int = 50
    wallet_lookback_days: int = 30
    min_wallet_distinct_tokens: int = 10
    min_wallet_win_rate: float = 0.70
    min_wallet_average_roi: float = 5.0
    cluster_window_hours: int = 4
    min_cluster_wallets: int = 4
    max_buy_sell_tax_pct: float = 5.0
    stale_market_data_hours: int = 6
    spike_window_candles: int = 4
    spike_multiplier: float = 3.0
    monitoring_lookback_hours: int = 24
    candidate_limit: int = 20
    max_winner_tokens: int = 5


@dataclass
class CandidateToken:
    address: str
    symbol: str
    name: Optional[str] = None
    chain: str = "base"
    unit_price: float = 0.0
    liquidity_usd: float = 0.0
    liquidity_status: str = "unknown"
    price_change_pct_48h: Optional[float] = None
    market_timestamp: Optional[datetime] = None
    data_sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class BuyEvent:
    wallet_address: str
    token_address: str
    amount_usd: float
    timestamp: Optional[datetime]
    tx_hash: str = ""
    symbol: Optional[str] = None
    token_name: Optional[str] = None
    unit_price: Optional[float] = None
    chain: str = "base"
    wallet_label: str = ""
    is_contract: bool = False
    is_router: bool = False
    is_deployer: bool = False
    counterparty: str = ""
    data_sources: list[str] = field(default_factory=list)


@dataclass
class WalletScore:
    wallet_address: str
    distinct_tokens: int
    win_rate: float
    average_roi_multiple: float
    confidence: str
    is_alpha: bool
    trades_evaluated: int
    assumptions: list[str] = field(default_factory=list)


@dataclass
class RejectionRecord:
    stage: str
    token_address: str
    reason: str
    symbol: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


class InsiderDataProvider:
    """Provider seam for production adapters and tests."""

    def discover_candidate_tokens(self, config: HuntConfig) -> list[CandidateToken]:
        return []

    def get_early_buyer_context(self, token: CandidateToken, config: HuntConfig) -> dict[str, Any]:
        return {"buy_events": [], "volume_candles": [], "data_sources": []}

    def get_wallet_trade_history(self, wallet_address: str, config: HuntConfig) -> list[dict[str, Any]]:
        return []

    def get_recent_wallet_buys(self, wallet_addresses: list[str], config: HuntConfig) -> list[BuyEvent]:
        return []

    def get_token_snapshot(self, token_address: str, chain: str) -> Optional[CandidateToken]:
        return None

    def get_token_audit(self, token_address: str, chain: str) -> Any:
        return None


class TwakInsiderDataProvider(InsiderDataProvider):
    """Best-effort adapter that still fails closed when the data is insufficient."""

    def discover_candidate_tokens(self, config: HuntConfig) -> list[CandidateToken]:
        raw = _run_twak(
            [
                "trending",
                "--category",
                "memes",
                "--sort",
                "price_change",
                "--limit",
                str(config.candidate_limit),
                "--json",
            ]
        )
        if raw.startswith("[error]"):
            logger.error("insider_hunt token discovery failed: %s", raw)
            return []
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("insider_hunt token discovery returned invalid json")
            return []

        tokens: list[CandidateToken] = []
        for row in rows if isinstance(rows, list) else []:
            address = _normalize_address(row.get("assetId") or row.get("address") or row.get("tokenAddress"))
            if not address:
                continue
            price_change_48h = row.get("priceChange48h")
            warnings: list[str] = []
            if price_change_48h is None and row.get("priceChange24h") is not None:
                price_change_48h = row.get("priceChange24h")
                warnings.append("48h price change unavailable; using 24h proxy.")
            tokens.append(
                CandidateToken(
                    address=address,
                    symbol=str(row.get("symbol") or address[:6]).upper(),
                    name=row.get("name"),
                    chain=config.chain,
                    unit_price=_safe_float(row.get("priceUsd") or row.get("price")),
                    liquidity_usd=_safe_float(row.get("liquidityUsd") or row.get("liquidity")),
                    liquidity_status=_normalize_liquidity_status(row.get("liquidityStatus")),
                    price_change_pct_48h=_safe_float(price_change_48h, default=0.0),
                    market_timestamp=_utcnow(),
                    data_sources=["twak"],
                    warnings=warnings,
                )
            )
        return tokens

    def get_early_buyer_context(self, token: CandidateToken, config: HuntConfig) -> dict[str, Any]:
        return {
            "buy_events": [],
            "volume_candles": [],
            "data_sources": ["twak"],
            "error": "Current provider cannot determine early buyers before the initial volume spike.",
        }

    def get_wallet_trade_history(self, wallet_address: str, config: HuntConfig) -> list[dict[str, Any]]:
        logger.info(
            "insider_hunt wallet history unavailable for %s with current TWAK adapter; failing closed",
            wallet_address,
        )
        return []

    def get_recent_wallet_buys(self, wallet_addresses: list[str], config: HuntConfig) -> list[BuyEvent]:
        logger.info(
            "insider_hunt recent wallet monitoring unavailable for %d wallets with current TWAK adapter; failing closed",
            len(wallet_addresses),
        )
        return []

    def get_token_snapshot(self, token_address: str, chain: str) -> Optional[CandidateToken]:
        try:
            from backend.dexscreener import DexScreenerClient

            snapshot = DexScreenerClient().token_snapshot(chain, token_address)
            if not snapshot:
                return None
            return CandidateToken(
                address=_normalize_address(snapshot.token_address),
                symbol=str(snapshot.symbol or token_address[:6]).upper(),
                name=snapshot.name,
                chain=chain,
                unit_price=snapshot.price_usd,
                liquidity_usd=snapshot.liquidity_usd,
                liquidity_status="unknown",
                price_change_pct_48h=None,
                market_timestamp=_utcnow(),
                data_sources=["dexscreener"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("insider_hunt token snapshot lookup failed for %s: %s", token_address, exc)
            return None

    def get_token_audit(self, token_address: str, chain: str) -> Any:
        try:
            from tools.security_tools import audit_token_contract

            return audit_token_contract(token_address=token_address, chain=chain)
        except Exception as exc:  # noqa: BLE001
            logger.error("insider_hunt audit lookup failed for %s: %s", token_address, exc)
            return None


class StaticInsiderDataProvider(InsiderDataProvider):
    """Fixture-friendly provider used by tests and local dry runs."""

    def __init__(
        self,
        candidates: Optional[list[CandidateToken]] = None,
        early_buyer_contexts: Optional[dict[str, dict[str, Any]]] = None,
        wallet_histories: Optional[dict[str, list[dict[str, Any]]]] = None,
        recent_wallet_buys: Optional[list[BuyEvent]] = None,
        token_snapshots: Optional[dict[str, CandidateToken]] = None,
        audits: Optional[dict[str, Any]] = None,
        fail_on: Optional[set[str]] = None,
    ):
        self.candidates = candidates or []
        self.early_buyer_contexts = early_buyer_contexts or {}
        self.wallet_histories = wallet_histories or {}
        self.recent_wallet_buys = recent_wallet_buys or []
        self.token_snapshots = token_snapshots or {}
        self.audits = audits or {}
        self.fail_on = fail_on or set()

    def _maybe_fail(self, name: str) -> None:
        if name in self.fail_on:
            raise RuntimeError(f"{name} provider failure")

    def discover_candidate_tokens(self, config: HuntConfig) -> list[CandidateToken]:
        self._maybe_fail("discover_candidate_tokens")
        return list(self.candidates)

    def get_early_buyer_context(self, token: CandidateToken, config: HuntConfig) -> dict[str, Any]:
        self._maybe_fail("get_early_buyer_context")
        return self.early_buyer_contexts.get(
            token.address, {"buy_events": [], "volume_candles": [], "data_sources": []}
        )

    def get_wallet_trade_history(self, wallet_address: str, config: HuntConfig) -> list[dict[str, Any]]:
        self._maybe_fail("get_wallet_trade_history")
        return self.wallet_histories.get(_normalize_address(wallet_address), [])

    def get_recent_wallet_buys(self, wallet_addresses: list[str], config: HuntConfig) -> list[BuyEvent]:
        self._maybe_fail("get_recent_wallet_buys")
        allowed = set(_normalize_address(wallet) for wallet in wallet_addresses)
        return [event for event in self.recent_wallet_buys if _normalize_address(event.wallet_address) in allowed]

    def get_token_snapshot(self, token_address: str, chain: str) -> Optional[CandidateToken]:
        self._maybe_fail("get_token_snapshot")
        return self.token_snapshots.get(_normalize_address(token_address))

    def get_token_audit(self, token_address: str, chain: str) -> Any:
        self._maybe_fail("get_token_audit")
        return self.audits.get(_normalize_address(token_address))


def detect_initial_volume_spike(
    volume_candles: list[dict[str, Any]],
    config: HuntConfig,
) -> Optional[datetime]:
    ordered = sorted(
        (
            {
                "timestamp": _parse_timestamp(candle.get("timestamp")),
                "volume": _safe_float(candle.get("volume")),
            }
            for candle in volume_candles
        ),
        key=lambda item: item["timestamp"] or datetime.max.replace(tzinfo=timezone.utc),
    )
    ordered = [item for item in ordered if item["timestamp"] is not None]
    if len(ordered) <= config.spike_window_candles:
        return None

    for idx in range(config.spike_window_candles, len(ordered)):
        baseline_slice = ordered[idx - config.spike_window_candles:idx]
        baseline = sum(item["volume"] for item in baseline_slice) / float(config.spike_window_candles)
        if baseline <= 0:
            continue
        if ordered[idx]["volume"] >= baseline * config.spike_multiplier:
            return ordered[idx]["timestamp"]
    return None


def extract_early_buyers(
    buy_events: list[BuyEvent],
    volume_candles: list[dict[str, Any]],
    config: HuntConfig,
) -> tuple[list[BuyEvent], Optional[datetime], list[str]]:
    spike_time = detect_initial_volume_spike(volume_candles, config)
    warnings: list[str] = []
    if spike_time is None:
        warnings.append("Unable to determine the initial volume spike.")
        return [], None, warnings

    filtered: list[BuyEvent] = []
    seen_wallets: set[str] = set()
    seen_hashes: set[str] = set()
    for event in sorted(buy_events, key=lambda item: item.timestamp or datetime.max.replace(tzinfo=timezone.utc)):
        wallet = _normalize_address(event.wallet_address)
        if not wallet or wallet in seen_wallets:
            continue
        if event.tx_hash and event.tx_hash in seen_hashes:
            continue
        if event.timestamp is None or event.timestamp >= spike_time:
            continue
        if event.amount_usd < config.early_buyer_min_usd:
            continue
        if event.is_contract or event.is_router or event.is_deployer or _is_suspect_wallet_label(asdict(event)):
            continue
        if _normalize_address(event.counterparty) == wallet:
            continue
        seen_wallets.add(wallet)
        if event.tx_hash:
            seen_hashes.add(event.tx_hash)
        filtered.append(event)
        if len(filtered) >= config.early_buyer_limit:
            break
    return filtered, spike_time, warnings


def score_wallet(wallet_address: str, trade_history: list[dict[str, Any]], config: HuntConfig) -> WalletScore:
    token_metrics: dict[str, dict[str, Any]] = {}
    assumptions: list[str] = []
    estimated = False

    for trade in trade_history:
        token_address = _normalize_address(trade.get("token_address") or trade.get("address"))
        invested_usd = _safe_float(trade.get("invested_usd") or trade.get("entry_value_usd") or trade.get("cost_basis_usd"))
        if not token_address or invested_usd <= 0:
            continue

        exit_value_usd = trade.get("exit_value_usd")
        if exit_value_usd is None:
            exit_value_usd = trade.get("realized_value_usd")
        realized = exit_value_usd is not None
        if exit_value_usd is None:
            exit_value_usd = trade.get("current_value_usd") or trade.get("estimated_value_usd")
            if exit_value_usd is not None:
                estimated = True

        if exit_value_usd is None:
            continue

        metric = token_metrics.setdefault(
            token_address,
            {"invested_usd": 0.0, "exit_value_usd": 0.0, "realized": True},
        )
        metric["invested_usd"] += invested_usd
        metric["exit_value_usd"] += _safe_float(exit_value_usd)
        metric["realized"] = metric["realized"] and realized

    roi_values: list[float] = []
    wins = 0
    for metric in token_metrics.values():
        invested = metric["invested_usd"]
        exit_value = metric["exit_value_usd"]
        if invested <= 0:
            continue
        roi_multiple = exit_value / invested
        roi_values.append(roi_multiple)
        if roi_multiple > 1.0:
            wins += 1
        if not metric["realized"]:
            estimated = True

    distinct_tokens = len(roi_values)
    win_rate = wins / distinct_tokens if distinct_tokens else 0.0
    average_roi = sum(roi_values) / distinct_tokens if distinct_tokens else 0.0

    if estimated:
        assumptions.append("ROI includes unrealized or estimated token values where realized exits were unavailable.")
    confidence = "estimated" if estimated else "high"
    is_alpha = (
        distinct_tokens >= config.min_wallet_distinct_tokens
        and win_rate > config.min_wallet_win_rate
        and average_roi > config.min_wallet_average_roi
    )

    return WalletScore(
        wallet_address=_normalize_address(wallet_address),
        distinct_tokens=distinct_tokens,
        win_rate=round(win_rate, 4),
        average_roi_multiple=round(average_roi, 4),
        confidence=confidence,
        is_alpha=is_alpha,
        trades_evaluated=distinct_tokens,
        assumptions=assumptions,
    )


def detect_clusters(
    buy_events: list[BuyEvent],
    token_snapshots: dict[str, CandidateToken],
    config: HuntConfig,
) -> list[dict[str, Any]]:
    window = timedelta(hours=config.cluster_window_hours)
    grouped: dict[str, list[BuyEvent]] = {}
    for event in buy_events:
        token = _normalize_address(event.token_address)
        if token:
            grouped.setdefault(token, []).append(event)

    clusters: list[dict[str, Any]] = []
    for token_address, events in grouped.items():
        snapshot = token_snapshots.get(token_address)
        if not snapshot:
            continue
        if snapshot.unit_price <= 0 or snapshot.unit_price > config.max_unit_price:
            continue
        if snapshot.liquidity_usd < config.min_liquidity_usd:
            continue

        ordered = sorted(events, key=lambda event: event.timestamp or datetime.max.replace(tzinfo=timezone.utc))
        for idx, start in enumerate(ordered):
            if start.timestamp is None:
                continue
            wallets: dict[str, BuyEvent] = {}
            for candidate in ordered[idx:]:
                if candidate.timestamp is None:
                    continue
                if candidate.timestamp - start.timestamp > window:
                    break
                wallet = _normalize_address(candidate.wallet_address)
                if wallet and wallet not in wallets:
                    wallets[wallet] = candidate
            if len(wallets) < config.min_cluster_wallets:
                continue
            cluster_events = list(wallets.values())
            clusters.append(
                {
                    "token_address": token_address,
                    "symbol": snapshot.symbol,
                    "token_name": snapshot.name,
                    "unit_price": snapshot.unit_price,
                    "liquidity_usd": snapshot.liquidity_usd,
                    "liquidity_status": snapshot.liquidity_status,
                    "events": cluster_events,
                    "wallet_addresses": sorted(wallets.keys()),
                    "started_at": min(event.timestamp for event in cluster_events if event.timestamp is not None),
                    "ended_at": max(event.timestamp for event in cluster_events if event.timestamp is not None),
                    "data_sources": _dedupe_preserve_order(
                        source for event in cluster_events for source in event.data_sources
                    ),
                }
            )
            break
    return clusters


def _regex_flag(text: str, truthy_pattern: str, falsy_pattern: str) -> Optional[bool]:
    if re.search(truthy_pattern, text, flags=re.IGNORECASE):
        return True
    if re.search(falsy_pattern, text, flags=re.IGNORECASE):
        return False
    return None


def parse_audit_result(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        buy_tax = _first_present(raw, "buy_tax_pct", "buy_tax")
        sell_tax = _first_present(raw, "sell_tax_pct", "sell_tax")
        return {
            "is_mintable": _normalize_bool(_first_present(raw, "is_mintable")),
            "buy_tax_pct": _safe_float(buy_tax, default=-1.0),
            "sell_tax_pct": _safe_float(sell_tax, default=-1.0),
            "source_verified": _normalize_bool(_first_present(raw, "source_verified", "is_open_source")),
            "honeypot": _normalize_bool(_first_present(raw, "honeypot", "is_honeypot")),
            "trading_can_be_disabled": _normalize_bool(
                _first_present(raw, "trading_can_be_disabled", "can_take_back_ownership")
            ),
            "can_blacklist_wallets": _normalize_bool(_first_present(raw, "can_blacklist_wallets")),
            "liquidity_status": _normalize_liquidity_status(_first_present(raw, "liquidity_status")),
            "fetched_at": _parse_timestamp(raw.get("fetched_at")),
            "summary": raw.get("summary") or "",
        }

    text = str(raw)
    buy_sell = re.search(r"Buy Tax:\s*([0-9.]+)%\s*\|\s*Sell Tax:\s*([0-9.]+)%", text, flags=re.IGNORECASE)
    summary = " ".join(line.strip() for line in text.splitlines() if line.strip())
    return {
        "is_mintable": _regex_flag(text, r"Mintable:\s*(?:⚠️\s*)?Yes", r"Mintable:\s*(?:✅\s*)?No"),
        "buy_tax_pct": _safe_float(buy_sell.group(1), default=-1.0) if buy_sell else -1.0,
        "sell_tax_pct": _safe_float(buy_sell.group(2), default=-1.0) if buy_sell else -1.0,
        "source_verified": _regex_flag(text, r"(?:source code|source)\s*(?:verified|is verified)", r"(?:source code|source)\s*(?:unverified|not verified)"),
        "honeypot": _regex_flag(text, r"HONEYPOT:\s*(?:🚨\s*)?YES", r"HONEYPOT:\s*(?:✅\s*)?No"),
        "trading_can_be_disabled": _regex_flag(text, r"trading(?:\s+\w+){0,3}\s+can be disabled", r"trading(?:\s+\w+){0,3}\s+cannot be disabled"),
        "can_blacklist_wallets": _regex_flag(text, r"blacklist(?:\s+\w+){0,3}\s+yes", r"blacklist(?:\s+\w+){0,3}\s+no"),
        "liquidity_status": _normalize_liquidity_status("locked" if "Locked Liquidity" in text else "unknown"),
        "fetched_at": None,
        "summary": summary,
    }


def evaluate_security(
    cluster: dict[str, Any],
    audit_result: dict[str, Any],
    config: HuntConfig,
) -> tuple[bool, Optional[str], dict[str, Any]]:
    critical_fields = (
        "is_mintable",
        "buy_tax_pct",
        "sell_tax_pct",
        "source_verified",
        "honeypot",
        "trading_can_be_disabled",
        "can_blacklist_wallets",
    )
    for field_name in critical_fields:
        value = audit_result.get(field_name)
        if value is None or value == -1.0:
            return False, "rejected_insufficient_security_data", audit_result

    if audit_result["honeypot"]:
        return False, "rejected_honeypot_risk", audit_result
    if audit_result["is_mintable"]:
        return False, "rejected_mintable_contract", audit_result
    if audit_result["buy_tax_pct"] > config.max_buy_sell_tax_pct:
        return False, "rejected_buy_tax_above_threshold", audit_result
    if audit_result["sell_tax_pct"] > config.max_buy_sell_tax_pct:
        return False, "rejected_sell_tax_above_threshold", audit_result
    if audit_result["source_verified"] is not True:
        return False, "rejected_unverified_source_code", audit_result
    if audit_result["trading_can_be_disabled"]:
        return False, "rejected_owner_can_disable_trading", audit_result
    if audit_result["can_blacklist_wallets"]:
        return False, "rejected_owner_can_blacklist_wallets", audit_result

    liquidity_status = _normalize_liquidity_status(
        cluster.get("liquidity_status") or audit_result.get("liquidity_status")
    )
    if cluster.get("liquidity_usd", 0.0) < config.min_liquidity_usd:
        return False, "rejected_low_liquidity", audit_result
    if liquidity_status == "unlocked":
        return False, "rejected_unlocked_liquidity", audit_result

    return True, None, audit_result


def calculate_confidence_score(
    cluster: dict[str, Any],
    alpha_scores: dict[str, WalletScore],
    config: HuntConfig,
) -> float:
    wallet_count = len(cluster["wallet_addresses"])
    avg_roi = (
        sum(alpha_scores[wallet].average_roi_multiple for wallet in cluster["wallet_addresses"]) / wallet_count
    )
    score = 0.55
    score += min(max(wallet_count - config.min_cluster_wallets, 0) * 0.05, 0.15)
    score += min(avg_roi / 20.0, 0.15)
    if cluster["unit_price"] <= config.preferred_low_unit_price:
        score += 0.05
    if cluster["liquidity_status"] in {"locked", "burned"}:
        score += 0.05
    return round(min(score, 0.95), 2)


class InsiderHuntEngine:
    def __init__(self, provider: Optional[InsiderDataProvider] = None, config: Optional[HuntConfig] = None):
        self.provider = provider or TwakInsiderDataProvider()
        self.config = config or HuntConfig()

    def run(self) -> dict[str, Any]:
        generated_at = _utcnow().isoformat()
        rejections: list[RejectionRecord] = []
        alpha_wallets: dict[str, WalletScore] = {}
        aggregated_sources: list[str] = []

        try:
            candidates = self.provider.discover_candidate_tokens(self.config)
        except Exception as exc:  # noqa: BLE001
            logger.exception("insider_hunt token discovery failed")
            return self._error_payload(
                "token_discovery_failed",
                str(exc),
                generated_at,
                data_sources_used=aggregated_sources,
            )

        deduped_candidates: dict[str, CandidateToken] = {}
        for token in candidates:
            address = _normalize_address(token.address)
            if address and address not in deduped_candidates:
                deduped_candidates[address] = token

        qualifying_candidates: list[CandidateToken] = []
        for token in deduped_candidates.values():
            aggregated_sources = _dedupe_preserve_order(aggregated_sources + token.data_sources)
            valid, reason = self._validate_candidate_token(token)
            if not valid:
                logger.info("insider_hunt rejected candidate %s at discovery: %s", token.address, reason)
                rejections.append(RejectionRecord("token_discovery", token.address, reason, symbol=token.symbol))
                continue
            qualifying_candidates.append(token)

        qualifying_candidates = sorted(
            qualifying_candidates,
            key=lambda token: token.price_change_pct_48h or 0.0,
            reverse=True,
        )[: self.config.max_winner_tokens]

        for token in qualifying_candidates:
            try:
                context = self.provider.get_early_buyer_context(token, self.config)
            except Exception as exc:  # noqa: BLE001
                logger.exception("insider_hunt early buyer extraction failed for %s", token.address)
                rejections.append(
                    RejectionRecord(
                        "early_buyer_extraction",
                        token.address,
                        "rejected_early_buyer_provider_failure",
                        symbol=token.symbol,
                        details={"error": str(exc)},
                    )
                )
                continue

            buy_events = [_coerce_buy_event(item, token) for item in context.get("buy_events", [])]
            volume_candles = context.get("volume_candles", [])
            aggregated_sources = _dedupe_preserve_order(
                aggregated_sources + list(context.get("data_sources", []))
            )
            early_buyers, spike_time, warnings = extract_early_buyers(buy_events, volume_candles, self.config)
            if warnings:
                token.warnings.extend(warnings)
            if not early_buyers:
                logger.info("insider_hunt rejected %s at early buyer stage", token.address)
                rejections.append(
                    RejectionRecord(
                        "early_buyer_extraction",
                        token.address,
                        "rejected_insufficient_early_buyer_data",
                        symbol=token.symbol,
                        details={"spike_detected_at": spike_time.isoformat() if spike_time else None},
                    )
                )
                continue

            for buyer in early_buyers:
                wallet = _normalize_address(buyer.wallet_address)
                if wallet in alpha_wallets:
                    continue
                try:
                    history = self.provider.get_wallet_trade_history(wallet, self.config)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("insider_hunt wallet history lookup failed for %s", wallet)
                    continue
                score = score_wallet(wallet, history, self.config)
                if score.is_alpha:
                    alpha_wallets[wallet] = score

        if not alpha_wallets:
            return self._no_signal_payload(generated_at, rejections, aggregated_sources)

        try:
            recent_buys = self.provider.get_recent_wallet_buys(list(alpha_wallets.keys()), self.config)
        except Exception as exc:  # noqa: BLE001
            logger.exception("insider_hunt cluster monitoring failed")
            return self._error_payload(
                "cluster_monitoring_failed",
                str(exc),
                generated_at,
                rejections,
                aggregated_sources,
            )

        recent_token_addresses = {
            _normalize_address(event.token_address)
            for event in recent_buys
            if _normalize_address(event.token_address)
        }
        token_snapshots: dict[str, CandidateToken] = {}
        for token_address in recent_token_addresses:
            try:
                snapshot = self.provider.get_token_snapshot(token_address, self.config.chain)
            except Exception as exc:  # noqa: BLE001
                logger.warning("insider_hunt token snapshot lookup failed for %s: %s", token_address, exc)
                snapshot = None
            if snapshot:
                token_snapshots[token_address] = snapshot
                aggregated_sources = _dedupe_preserve_order(aggregated_sources + snapshot.data_sources)

        clusters = detect_clusters(recent_buys, token_snapshots, self.config)
        if not clusters:
            return self._no_signal_payload(generated_at, rejections, aggregated_sources)

        signals: list[dict[str, Any]] = []
        for cluster in clusters:
            try:
                audit_raw = self.provider.get_token_audit(cluster["token_address"], self.config.chain)
            except Exception:  # noqa: BLE001
                logger.exception("insider_hunt audit lookup failed for %s", cluster["token_address"])
                signals.append(
                    self._format_signal(
                        cluster,
                        alpha_wallets,
                        "rejected",
                        0.0,
                        "rejected_insufficient_security_data",
                        {},
                        generated_at,
                    )
                )
                continue

            audit_result = parse_audit_result(audit_raw)
            allowed, rejection_reason, audit_summary = evaluate_security(cluster, audit_result, self.config)
            if not allowed:
                logger.info(
                    "insider_hunt rejected cluster %s at security stage: %s",
                    cluster["token_address"],
                    rejection_reason,
                )
                signals.append(
                    self._format_signal(
                        cluster,
                        alpha_wallets,
                        "rejected",
                        0.0,
                        rejection_reason,
                        audit_summary,
                        generated_at,
                    )
                )
                continue

            confidence = calculate_confidence_score(cluster, alpha_wallets, self.config)
            signals.append(
                self._format_signal(
                    cluster,
                    alpha_wallets,
                    "ok",
                    confidence,
                    None,
                    audit_summary,
                    generated_at,
                )
            )

        final_status = "ok" if any(signal["status"] == "ok" for signal in signals) else "no_signal"
        max_confidence = max((signal["confidence_score"] for signal in signals), default=0.0)
        aggregated_sources = _dedupe_preserve_order(
            aggregated_sources
            + [source for signal in signals for source in signal.get("data_sources_used", [])]
        )
        return {
            "status": final_status,
            "chain": "Base",
            "generated_at": generated_at,
            "confidence_score": max_confidence,
            "data_sources_used": aggregated_sources,
            "signals": signals,
            "rejections": [asdict(rejection) for rejection in rejections],
            "warning": WATCHLIST_WARNING,
        }

    def _validate_candidate_token(self, token: CandidateToken) -> tuple[bool, str]:
        gain = token.price_change_pct_48h
        if gain is None or gain < self.config.min_gain_pct_48h:
            return False, "rejected_gain_below_threshold"
        if token.unit_price <= 0 or token.unit_price > self.config.max_unit_price:
            return False, "rejected_unit_price_above_threshold"
        if token.market_timestamp is None:
            return False, "rejected_incomplete_market_data"
        if _utcnow() - token.market_timestamp > timedelta(hours=self.config.stale_market_data_hours):
            return False, "rejected_stale_market_data"
        return True, ""

    def _format_signal(
        self,
        cluster: dict[str, Any],
        alpha_wallets: dict[str, WalletScore],
        status: str,
        confidence_score: float,
        rejection_reason: Optional[str],
        audit_summary: dict[str, Any],
        generated_at: str,
    ) -> dict[str, Any]:
        liquidity_status = _normalize_liquidity_status(
            cluster.get("liquidity_status") or audit_summary.get("liquidity_status")
        )
        return {
            "status": status,
            "chain": "Base",
            "token_symbol": cluster.get("symbol"),
            "token_name": cluster.get("token_name"),
            "token_address": cluster.get("token_address"),
            "unit_price": cluster.get("unit_price"),
            "liquidity_amount": cluster.get("liquidity_usd"),
            "liquidity_status": liquidity_status,
            "number_of_alpha_wallets": len(cluster.get("wallet_addresses", [])),
            "alpha_wallet_summaries": [
                {
                    "wallet_address": wallet,
                    "distinct_tokens": alpha_wallets[wallet].distinct_tokens,
                    "win_rate": alpha_wallets[wallet].win_rate,
                    "average_roi_multiple": alpha_wallets[wallet].average_roi_multiple,
                    "confidence": alpha_wallets[wallet].confidence,
                    "assumptions": alpha_wallets[wallet].assumptions,
                }
                for wallet in cluster.get("wallet_addresses", [])
                if wallet in alpha_wallets
            ],
            "audit_result_summary": audit_summary,
            "detection_timestamp": generated_at,
            "confidence_score": confidence_score,
            "rejection_reason": rejection_reason,
            "data_sources_used": list(cluster.get("data_sources", [])),
            "warning": WATCHLIST_WARNING,
        }

    def _no_signal_payload(
        self,
        generated_at: str,
        rejections: Optional[list[RejectionRecord]] = None,
        data_sources_used: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        return {
            "status": "no_signal",
            "chain": "Base",
            "generated_at": generated_at,
            "confidence_score": 0.0,
            "data_sources_used": list(data_sources_used or []),
            "signals": [],
            "rejections": [asdict(rejection) for rejection in (rejections or [])],
            "warning": WATCHLIST_WARNING,
        }

    def _error_payload(
        self,
        reason: str,
        error: str,
        generated_at: str,
        rejections: Optional[list[RejectionRecord]] = None,
        data_sources_used: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        return {
            "status": "error",
            "chain": "Base",
            "generated_at": generated_at,
            "confidence_score": 0.0,
            "data_sources_used": list(data_sources_used or []),
            "error_reason": reason,
            "error": error,
            "signals": [],
            "rejections": [asdict(rejection) for rejection in (rejections or [])],
            "warning": WATCHLIST_WARNING,
        }


def _coerce_buy_event(item: Any, token: CandidateToken) -> BuyEvent:
    if isinstance(item, BuyEvent):
        return item
    row = item if isinstance(item, dict) else {}
    return BuyEvent(
        wallet_address=str(row.get("wallet_address") or row.get("buyer") or ""),
        token_address=_normalize_address(row.get("token_address") or token.address),
        amount_usd=_safe_float(row.get("amount_usd") or row.get("notional_usd")),
        timestamp=_parse_timestamp(row.get("timestamp")),
        tx_hash=str(row.get("tx_hash") or row.get("hash") or ""),
        symbol=row.get("symbol") or token.symbol,
        token_name=row.get("token_name") or token.name,
        unit_price=_safe_float(row.get("unit_price"), default=token.unit_price),
        chain=str(row.get("chain") or token.chain),
        wallet_label=str(row.get("wallet_label") or ""),
        is_contract=bool(row.get("is_contract", False)),
        is_router=bool(row.get("is_router", False)),
        is_deployer=bool(row.get("is_deployer", False)),
        counterparty=str(row.get("counterparty") or ""),
        data_sources=list(row.get("data_sources", [])),
    )


@register_tool(
    name="hunt_insider_wallets",
    description=(
        "Read-only Base watchlist detector for low-unit-price cluster-buy signals. It scans recent winner tokens, "
        "tries to extract early buyers before a defined volume spike, scores wallets on 30-day ROI and win rate, "
        "detects multi-wallet clusters, and applies fail-closed contract-risk filters. It requires market, wallet, "
        "and audit data to be complete enough for confidence; otherwise it returns no_signal or rejected output. "
        "It does not execute trades."
    ),
    metadata=INSIDER_HUNT_METADATA,
    input_schema={
        "type": "object",
        "properties": {
            "min_gain_pct": {
                "type": "number",
                "description": "Minimum 48h gain percentage for candidate winner tokens.",
                "default": 1000.0,
            },
            "max_unit_price": {
                "type": "number",
                "description": "Maximum unit price for candidate and flagged tokens.",
                "default": 0.01,
            },
            "min_liquidity_usd": {
                "type": "number",
                "description": "Minimum liquidity threshold for cluster candidates.",
                "default": 25000.0,
            },
            "candidate_limit": {
                "type": "integer",
                "description": "Maximum number of market winners to inspect before wallet scoring.",
                "default": 20,
            },
        },
    },
)
def hunt_insider_wallets(
    min_gain_pct: float = 1000.0,
    max_unit_price: float = 0.01,
    min_liquidity_usd: float = 25_000.0,
    candidate_limit: int = 20,
) -> str:
    config = HuntConfig(
        min_gain_pct_48h=min_gain_pct,
        max_unit_price=max_unit_price,
        min_liquidity_usd=min_liquidity_usd,
        candidate_limit=candidate_limit,
    )
    result = InsiderHuntEngine(config=config).run()
    return json.dumps(result, indent=2)


@register_tool(
    name="verify_alpha_wallet",
    description=(
        "Score a wallet against the Insider Hunt alpha-wallet thresholds using 30-day trade history. "
        "Read-only analysis only."
    ),
    metadata=INSIDER_HUNT_METADATA,
    input_schema={
        "type": "object",
        "properties": {
            "address": {"type": "string", "description": "The wallet address to analyze."},
            "chain": {
                "type": "string",
                "description": "The blockchain network. Default is Base.",
                "default": "base",
            },
        },
        "required": ["address"],
    },
)
def verify_alpha_wallet(address: str, chain: str = "base") -> str:
    config = HuntConfig(chain=chain)
    provider = TwakInsiderDataProvider()
    try:
        history = provider.get_wallet_trade_history(address, config)
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {
                "status": "error",
                "chain": chain,
                "wallet_address": _normalize_address(address),
                "error": str(exc),
                "warning": WATCHLIST_WARNING,
            },
            indent=2,
        )

    score = score_wallet(address, history, config)
    status = "ok" if history else "no_signal"
    return json.dumps(
        {
            "status": status,
            "chain": chain,
            "wallet_address": score.wallet_address,
            "distinct_tokens": score.distinct_tokens,
            "win_rate": score.win_rate,
            "average_roi_multiple": score.average_roi_multiple,
            "confidence": score.confidence,
            "is_alpha": score.is_alpha,
            "assumptions": score.assumptions,
            "warning": WATCHLIST_WARNING,
        },
        indent=2,
    )


@register_tool(
    name="add_alpha_wallet",
    description="Manually add a known high-performance wallet address to the persistent alpha-wallet list.",
    input_schema={
        "type": "object",
        "properties": {
            "address": {"type": "string", "description": "The wallet address to add."},
            "chain": {
                "type": "string",
                "description": "The blockchain network (e.g., ethereum, solana, base).",
                "default": "base",
            },
            "notes": {
                "type": "string",
                "description": "Optional notes about why this wallet is being added.",
                "default": "",
            },
        },
        "required": ["address"],
    },
)
def add_alpha_wallet(address: str, chain: str = "base", notes: str = "") -> str:
    try:
        from memory.wallets import WalletStore

        store = WalletStore()
        store.add_wallet(address, chain, notes=notes)
        return f"Successfully added {address} on {chain} to Alpha Wallets list."
    except Exception as exc:  # noqa: BLE001
        return f"[error] Failed to add wallet: {exc}"
