"""
Agent tools for state-aware token and trend prediction.
"""

from __future__ import annotations

import json
from typing import Any

from backend.trend_backtest import ForgeTrendBacktester
from backend.dexscreener import DexScreenerClient
from backend.trend_prediction_ledger import TrendPredictionLedger
from backend.trend_signal_collector import TrendSignalCollector
from backend.trend_prediction import TrendPredictionEngine
from backend.trend_watchlist import TrendForgeWatchlist
from backend.trend_forge_service import clear_forge_alerts, list_forge_alerts, process_due_watchlist
from core.tools import register_tool


def _dict(value: dict[str, Any] | None) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_arg(value: Any, default: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@register_tool(
    name="forge_token_prediction",
    description=(
        "Generate an AI-assisted token trend forecast with attention, momentum, "
        "risk, confidence, drivers, and warnings. This is research only, not "
        "financial advice."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "asset": {
                "type": "string",
                "description": "Token symbol, contract address, or trend keyword.",
            },
            "horizon": {
                "type": "string",
                "enum": ["1h", "4h", "24h", "7d"],
                "default": "24h",
                "description": "Forecast horizon.",
            },
            "mode": {
                "type": "string",
                "enum": ["attention", "momentum", "risk", "composite"],
                "default": "composite",
                "description": "Primary prediction lens.",
            },
            "market": {
                "type": "object",
                "description": (
                    "Optional market signals: price_change_pct, volume_growth_pct, "
                    "liquidity_usd, volatility_pct, rsi."
                ),
            },
            "social": {
                "type": "object",
                "description": (
                    "Optional social signals: mention_growth_pct, engagement_growth_pct, "
                    "sentiment_score (-1..1), unique_author_count, bot_ratio."
                ),
            },
            "onchain": {
                "type": "object",
                "description": (
                    "Optional on-chain signals: top_holder_pct, whale_exchange_inflow_pct, "
                    "holder_growth_pct."
                ),
            },
            "security": {
                "type": "object",
                "description": "Optional security signals: contract_risk_score, honeypot.",
            },
            "narrative": {
                "type": "object",
                "description": "Optional narrative/event signals: catalyst_score.",
            },
        },
        "required": ["asset"],
    },
)
def forge_token_prediction(
    asset: str,
    horizon: str = "24h",
    mode: str = "composite",
    market: dict[str, Any] | None = None,
    social: dict[str, Any] | None = None,
    onchain: dict[str, Any] | None = None,
    security: dict[str, Any] | None = None,
    narrative: dict[str, Any] | None = None,
) -> str:
    """Return a structured trend forecast for the agent."""
    engine = TrendPredictionEngine()
    forecast = engine.forecast(
        asset=asset,
        horizon=horizon,
        mode=mode,
        market=_dict(market),
        social=_dict(social),
        onchain=_dict(onchain),
        security=_dict(security),
        narrative=_dict(narrative),
    )
    return json.dumps(forecast.to_dict(), indent=2)


@register_tool(
    name="forge_signal_template",
    description=(
        "Return the expected signal schema for forge_token_prediction so another "
        "agent or workflow can populate market, social, on-chain, security, and "
        "narrative inputs consistently."
    ),
    input_schema={
        "type": "object",
        "properties": {},
    },
)
def forge_signal_template() -> str:
    """Provide the scoring input contract."""
    template = {
        "market": {
            "price_change_pct": 0.0,
            "volume_growth_pct": 0.0,
            "liquidity_usd": 0.0,
            "volatility_pct": 0.0,
            "rsi": 50.0,
        },
        "social": {
            "mention_growth_pct": 0.0,
            "engagement_growth_pct": 0.0,
            "sentiment_score": 0.0,
            "unique_author_count": 0,
            "bot_ratio": 0.0,
        },
        "onchain": {
            "top_holder_pct": 0.0,
            "whale_exchange_inflow_pct": 0.0,
            "holder_growth_pct": 0.0,
        },
        "security": {
            "contract_risk_score": 0.0,
            "honeypot": False,
        },
        "narrative": {
            "catalyst_score": 0.0,
        },
    }
    return json.dumps(template, indent=2)


@register_tool(
    name="forge_resolve_contract",
    description=(
        "Resolve a token contract through DexScreener and return symbol, name, "
        "best pair, DEX URL, price, liquidity, volume, market cap, FDV, pair age, "
        "and derived Forge market/risk signals."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "token_address": {"type": "string", "description": "Token contract address."},
            "chain": {"type": "string", "default": "base", "description": "DexScreener chain id."},
        },
        "required": ["token_address"],
    },
)
def forge_resolve_contract(token_address: str, chain: str = "base") -> str:
    """Resolve contract metadata and DEX market context."""
    try:
        from backend.dexscreener import snapshot_to_forge_signals

        snapshot = DexScreenerClient().token_snapshot(chain, token_address)
        if snapshot is None:
            return json.dumps(
                {
                    "token_address": token_address,
                    "chain": chain,
                    "found": False,
                    "error": "DexScreener returned no pairs for this token.",
                },
                indent=2,
            )
        normalized = snapshot_to_forge_signals(snapshot)
        return json.dumps(
            {
                "found": True,
                "metadata": normalized["metadata"],
                "signals": {
                    "market": normalized["market"],
                    "social": normalized["social"],
                    "security": normalized["security"],
                    "narrative": normalized["narrative"],
                },
            },
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return f"Error resolving contract: {type(exc).__name__}: {exc}"


@register_tool(
    name="forge_live_token_prediction",
    description=(
        "Collect available live signals from existing market, sentiment, security, "
        "and whale integrations, then generate a Trend Prediction Forge forecast. "
        "Works best with a symbol plus contract address. Research only, not "
        "financial advice."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "asset": {
                "type": "string",
                "description": "Optional token symbol or market symbol, e.g. BTC, ETH, SOL, or TOSHI.",
            },
            "token_address": {
                "type": "string",
                "description": "Optional token contract address for security and whale signals.",
            },
            "chain": {
                "type": "string",
                "default": "base",
                "description": "Chain for contract/security checks. Defaults to base.",
            },
            "horizon": {
                "type": "string",
                "enum": ["1h", "4h", "24h", "7d"],
                "default": "24h",
                "description": "Forecast horizon.",
            },
            "mode": {
                "type": "string",
                "enum": ["attention", "momentum", "risk", "composite"],
                "default": "composite",
                "description": "Primary prediction lens.",
            },
            "historical_limit": {
                "type": "integer",
                "default": 72,
                "description": "Number of 1h candles to request for market signal generation.",
            },
        },
    },
)
def forge_live_token_prediction(
    asset: str | None = None,
    token_address: str | None = None,
    chain: str = "base",
    horizon: str = "24h",
    mode: str = "composite",
    historical_limit: int = 72,
) -> str:
    """Collect live signals and return a forecast."""
    lookup_asset = asset or token_address
    if not lookup_asset:
        return "Error: asset or token_address is required."

    collector = TrendSignalCollector()
    signals = collector.collect(
        asset=lookup_asset,
        token_address=token_address,
        chain=chain,
        historical_limit=historical_limit,
    )
    forecast_asset = signals.metadata.get("resolved_asset") or asset or token_address

    engine = TrendPredictionEngine()
    forecast = engine.forecast(
        asset=forecast_asset,
        horizon=horizon,
        mode=mode,
        market=signals.market,
        social=signals.social,
        onchain=signals.onchain,
        security=signals.security,
        narrative=signals.narrative,
    )

    payload = forecast.to_dict()
    payload["signal_inputs"] = {
        "market": signals.market,
        "social": signals.social,
        "onchain": signals.onchain,
        "security": signals.security,
        "narrative": signals.narrative,
    }
    payload["metadata"] = signals.metadata
    payload["data_quality"] = signals.data_quality
    return json.dumps(payload, indent=2)


@register_tool(
    name="forge_record_live_prediction",
    description=(
        "Collect live signals, generate a Trend Prediction Forge forecast, and "
        "record it in the trend prediction ledger for later evaluation."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "asset": {"type": "string", "description": "Optional token symbol or market symbol."},
            "token_address": {"type": "string", "description": "Optional token contract address."},
            "chain": {"type": "string", "default": "base", "description": "Chain for contract checks."},
            "horizon": {
                "type": "string",
                "enum": ["1h", "4h", "24h", "7d"],
                "default": "24h",
                "description": "Forecast horizon.",
            },
            "mode": {
                "type": "string",
                "enum": ["attention", "momentum", "risk", "composite"],
                "default": "composite",
                "description": "Primary prediction lens.",
            },
            "historical_limit": {
                "type": "integer",
                "default": 72,
                "description": "Number of 1h candles to request.",
            },
        },
    },
)
def forge_record_live_prediction(
    asset: str | None = None,
    token_address: str | None = None,
    chain: str = "base",
    horizon: str = "24h",
    mode: str = "composite",
    historical_limit: int = 72,
) -> str:
    """Collect, forecast, and persist a prediction record."""
    lookup_asset = asset or token_address
    if not lookup_asset:
        return "Error: asset or token_address is required."

    collector = TrendSignalCollector()
    signals = collector.collect(
        asset=lookup_asset,
        token_address=token_address,
        chain=chain,
        historical_limit=historical_limit,
    )
    forecast_asset = signals.metadata.get("resolved_asset") or asset or token_address

    engine = TrendPredictionEngine()
    forecast = engine.forecast(
        asset=forecast_asset,
        horizon=horizon,
        mode=mode,
        market=signals.market,
        social=signals.social,
        onchain=signals.onchain,
        security=signals.security,
        narrative=signals.narrative,
    )

    signal_inputs = {
        "market": signals.market,
        "social": signals.social,
        "onchain": signals.onchain,
        "security": signals.security,
        "narrative": signals.narrative,
    }
    record = TrendPredictionLedger().record(
        forecast=forecast,
        signal_inputs=signal_inputs,
        data_quality=signals.data_quality,
        metadata=signals.metadata,
        token_address=token_address,
        chain=chain,
    )
    return json.dumps(record, indent=2)


@register_tool(
    name="forge_evaluate_due_predictions",
    description=(
        "Evaluate due Trend Prediction Forge ledger entries by recollecting "
        "current signals and comparing realized forecast regimes."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "asset": {"type": "string", "description": "Optional asset filter."},
            "evaluate_all": {
                "type": "boolean",
                "default": False,
                "description": "Evaluate all pending records even if they are not due yet.",
            },
        },
    },
)
def forge_evaluate_due_predictions(asset: str | None = None, evaluate_all: bool = False) -> str:
    """Evaluate due records with fresh collected signals."""
    collector = TrendSignalCollector()

    def lookup(record: dict[str, Any]) -> dict[str, Any]:
        signals = collector.collect(
            asset=record["asset"],
            token_address=record.get("token_address"),
            chain=record.get("chain", "base"),
        )
        return signals.to_dict()

    evaluated = TrendPredictionLedger().evaluate_due(
        signal_lookup=lookup,
        asset=asset,
        evaluate_all=evaluate_all,
    )
    return json.dumps({"evaluated": len(evaluated), "records": evaluated}, indent=2)


@register_tool(
    name="forge_prediction_ledger_summary",
    description="Summarize Trend Prediction Forge ledger accuracy, pending count, and score error.",
    input_schema={
        "type": "object",
        "properties": {
            "asset": {"type": "string", "description": "Optional asset filter."},
            "limit": {
                "type": "integer",
                "default": 100,
                "description": "Recent evaluated records to include in summary metrics.",
            },
        },
    },
)
def forge_prediction_ledger_summary(asset: str | None = None, limit: int = 100) -> str:
    """Return trend prediction ledger summary metrics."""
    limit = max(1, _int_arg(limit, 100))
    summary = TrendPredictionLedger().summary(asset=asset, limit=limit)
    return json.dumps(summary, indent=2)


@register_tool(
    name="forge_backtest_trend_model",
    description=(
        "Run a historical OHLCV backtest for the Trend Prediction Forge using "
        "existing market data integrations. Measures directional accuracy of "
        "attention, momentum, risk, or composite forecasts."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "asset": {"type": "string", "description": "Token/market symbol, e.g. ETH or SOL."},
            "horizon": {
                "type": "string",
                "enum": ["1h", "4h", "24h", "7d"],
                "default": "24h",
                "description": "Prediction horizon to test.",
            },
            "mode": {
                "type": "string",
                "enum": ["attention", "momentum", "risk", "composite"],
                "default": "composite",
                "description": "Forge forecast mode to test.",
            },
            "lookback": {
                "type": "integer",
                "default": 72,
                "description": "Candles used to build each forecast sample.",
            },
            "stride": {
                "type": "integer",
                "default": 6,
                "description": "Candles to skip between backtest samples.",
            },
            "limit": {
                "type": "integer",
                "default": 500,
                "description": "Historical candles to fetch.",
            },
        },
        "required": ["asset"],
    },
)
def forge_backtest_trend_model(
    asset: str,
    horizon: str = "24h",
    mode: str = "composite",
    lookback: int = 72,
    stride: int = 6,
    limit: int = 500,
) -> str:
    """Fetch historical candles and run a forge backtest."""
    try:
        from tools.trading_data import fetch_historical

        raw = fetch_historical(asset, interval="1h", limit=limit)
        if raw.startswith("[error]"):
            return raw
        candles = json.loads(raw)
        result = ForgeTrendBacktester().run(
            asset=asset,
            candles=candles,
            horizon=horizon,
            mode=mode,
            lookback=lookback,
            stride=stride,
        )
        return json.dumps(result.to_dict(), indent=2)
    except Exception as exc:  # noqa: BLE001
        return f"Error running forge backtest: {type(exc).__name__}: {exc}"


@register_tool(
    name="forge_add_watch",
    description=(
        "Add an asset or contract to the Trend Prediction Forge watchlist for "
        "recurring forecast recording and score-threshold alerts."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "asset": {"type": "string", "description": "Optional symbol, e.g. ETH or TOSHI."},
            "token_address": {"type": "string", "description": "Optional token contract address."},
            "chain": {"type": "string", "default": "base", "description": "Chain id."},
            "horizons": {
                "type": "array",
                "items": {"type": "string", "enum": ["1h", "4h", "24h", "7d"]},
                "default": ["1h", "4h", "24h"],
            },
            "modes": {
                "type": "array",
                "items": {"type": "string", "enum": ["attention", "momentum", "risk", "composite"]},
                "default": ["composite", "risk"],
            },
            "interval_minutes": {"type": "integer", "default": 60},
            "thresholds": {
                "type": "object",
                "description": "Optional thresholds for attention_score, risk_score, confidence.",
            },
            "user_id": {"type": "integer", "description": "Optional user id for ownership/filtering."},
        },
    },
)
def forge_add_watch(
    asset: str | None = None,
    token_address: str | None = None,
    chain: str = "base",
    horizons: list[str] | None = None,
    modes: list[str] | None = None,
    interval_minutes: int = 60,
    thresholds: dict[str, float] | None = None,
    user_id: int | None = None,
) -> str:
    try:
        interval_minutes = max(1, _int_arg(interval_minutes, 60))
        user_id = _int_arg(user_id, None) if user_id is not None else None
        watch = TrendForgeWatchlist().add(
            asset=asset,
            token_address=token_address,
            chain=chain,
            horizons=horizons,
            modes=modes,
            interval_minutes=interval_minutes,
            thresholds=thresholds,
            user_id=user_id,
        )
        return json.dumps(watch, indent=2)
    except Exception as exc:  # noqa: BLE001
        return f"Error adding forge watch: {type(exc).__name__}: {exc}"


@register_tool(
    name="forge_list_watches",
    description="List Trend Prediction Forge watchlist entries.",
    input_schema={
        "type": "object",
        "properties": {
            "active_only": {"type": "boolean", "default": False},
            "user_id": {"type": "integer", "description": "Optional user id filter."},
        },
    },
)
def forge_list_watches(active_only: bool = False, user_id: int | None = None) -> str:
    user_id = _int_arg(user_id, None) if user_id is not None else None
    watches = TrendForgeWatchlist().list(active_only=active_only, user_id=user_id)
    if user_id is not None and not watches:
        watches = TrendForgeWatchlist().list(active_only=active_only, user_id=None)
    return json.dumps(watches, indent=2)


@register_tool(
    name="forge_delete_watch",
    description="Delete a Trend Prediction Forge watch by watch_id.",
    input_schema={
        "type": "object",
        "properties": {"watch_id": {"type": "string", "description": "Watch id."}},
        "required": ["watch_id"],
    },
)
def forge_delete_watch(watch_id: str) -> str:
    deleted = TrendForgeWatchlist().delete(watch_id)
    return f"Deleted forge watch {watch_id}." if deleted else f"Forge watch {watch_id} not found."


@register_tool(
    name="forge_run_watchlist",
    description=(
        "Process due Trend Prediction Forge watchlist entries now. Set force=true "
        "to record all active watches regardless of cadence."
    ),
    input_schema={
        "type": "object",
        "properties": {"force": {"type": "boolean", "default": False}},
    },
)
def forge_run_watchlist(force: bool = False) -> str:
    result = process_due_watchlist(force=force)
    return json.dumps(result, indent=2)


@register_tool(
    name="forge_list_alerts",
    description="List persisted Trend Prediction Forge alert events.",
    input_schema={
        "type": "object",
        "properties": {
            "asset": {"type": "string", "description": "Optional asset filter."},
            "watch_id": {"type": "string", "description": "Optional watch id filter."},
            "limit": {"type": "integer", "default": 50},
        },
    },
)
def forge_list_alerts(asset: str | None = None, watch_id: str | None = None, limit: int = 50) -> str:
    alerts = list_forge_alerts(asset=asset, watch_id=watch_id, limit=limit)
    return json.dumps(alerts, indent=2)


@register_tool(
    name="forge_clear_alerts",
    description="Clear persisted Trend Prediction Forge alert events.",
    input_schema={"type": "object", "properties": {}},
)
def forge_clear_alerts() -> str:
    count = clear_forge_alerts()
    return f"Cleared {count} Forge alert events."
