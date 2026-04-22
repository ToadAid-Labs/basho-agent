# Trend Prediction Forge

Trend Prediction Forge is an AI-assisted research layer for token and narrative
forecasting. It predicts attention, momentum, and risk regimes from structured
signals. It does not issue guaranteed price targets and should not be treated as
financial advice.

## Agent Tools

`forge_token_prediction` returns:

- `attention_score`: likelihood of increased attention or narrative velocity
- `momentum_score`: likelihood of near-term trend continuation
- `risk_score`: manipulation, security, liquidity, and concentration risk
- `confidence`: signal coverage and signal agreement
- `direction`: compact forecast label
- `drivers`: positive factors behind the forecast
- `warnings`: guardrails and failure modes

`forge_signal_template` returns the expected input schema for upstream data
collectors.

`forge_resolve_contract` resolves a token contract through DexScreener and
returns symbol, token name, best pair, DEX URL, price, liquidity, volume, market
cap, FDV, pair age, boosts, and derived forge signals.

`forge_live_token_prediction` collects available signals from the existing
market data, sentiment, security, and whale integrations, then runs the same
deterministic forecast engine. It returns both the forecast and the exact
`signal_inputs` used to produce it.

`forge_record_live_prediction` collects live signals, generates a forecast, and
stores it in the trend prediction ledger.

`forge_evaluate_due_predictions` evaluates due ledger records by recollecting
current signals and comparing the realized forecast regime with the original
prediction.

`forge_prediction_ledger_summary` reports pending/evaluated counts, direction
accuracy, score error, and per-mode breakdowns.

`forge_backtest_trend_model` fetches historical 1h candles and replays them
through the forge to measure directional accuracy.

`forge_add_watch`, `forge_list_watches`, `forge_delete_watch`, and
`forge_run_watchlist` manage recurring Forge scans. Watches can record multiple
horizons and modes on a cadence and emit threshold alert events.

## Signal Inputs

```json
{
  "market": {
    "price_change_pct": 12.0,
    "volume_growth_pct": 180.0,
    "liquidity_usd": 4000000,
    "volatility_pct": 9.0,
    "rsi": 62.0
  },
  "social": {
    "mention_growth_pct": 220.0,
    "engagement_growth_pct": 190.0,
    "sentiment_score": 0.58,
    "unique_author_count": 480,
    "bot_ratio": 0.08
  },
  "onchain": {
    "top_holder_pct": 18.0,
    "whale_exchange_inflow_pct": 2.0,
    "holder_growth_pct": 14.0
  },
  "security": {
    "contract_risk_score": 12.0,
    "honeypot": false
  },
  "narrative": {
    "catalyst_score": 82.0
  }
}
```

## Design Guardrails

- Attention and price are scored separately.
- High risk can override a strong trend.
- Thin liquidity and honeypot signals are surfaced as explicit warnings.
- Confidence drops when data coverage is weak or signals disagree.
- The scoring engine is deterministic so it can be tested and backtested.

## Live Collection

The live collector currently uses existing repository integrations:

- `backend.dexscreener.DexScreenerClient` for contract-address token/pair
  resolution
- `tools.trading_data.fetch_historical` for 1h OHLCV candles
- `tools.trading_data.fetch_ticker` for ticker fallback context
- `monitoring.sentiment_engine.analyze_sentiment` for social/news sentiment
- `tools.security_tools.audit_token_contract` for GoPlus security output
- `monitoring.whale_tracker.check_whale_stats` for whale/on-chain activity

Missing network access, missing credentials, or unsupported assets do not stop
the forecast. The tool records source failures under `data_quality.errors` and
continues with the signals it has.

When `token_address` is supplied, the collector asks DexScreener for the best
liquidity pair on the requested chain. If a symbol is resolved, the forecast uses
that symbol even when the caller supplied only a contract address.

Contract-only example:

```json
{
  "token_address": "0x...",
  "chain": "base",
  "horizon": "24h",
  "mode": "composite"
}
```

DexScreener-derived fields include:

- resolved token symbol/name
- best pair address and URL
- price in USD
- liquidity in USD
- 24h volume
- 24h price change
- 24h buys/sells and buy/sell imbalance
- FDV and market cap
- pair age
- active boosts
- derived `dex_manipulation_risk_score`

## Prediction Ledger

The ledger stores JSON records at `~/.agent/trend_prediction_ledger.json` by
default. Set `TREND_PREDICTION_LEDGER_PATH` to override this for tests or
isolated deployments.

Each record includes:

- original forecast and direction
- exact signal inputs used by the forge
- data quality metadata
- token address and chain when supplied
- due timestamp derived from `1h`, `4h`, `24h`, or `7d`
- actual forecast, actual signals, direction correctness, and score error after
  evaluation

## Background Evaluation

The Flask app starts a background Trend Prediction Forge tracker during
`initialize_app()`. It evaluates due ledger entries every hour by default.

Set `TREND_FORGE_EVALUATION_INTERVAL_SECONDS` to change the interval.

## API Routes

All routes require the existing dashboard login session.

- `GET /api/ai/forge/ledger?asset=ETH&limit=100`
  Returns ledger summary and evaluates currently due entries first.
- `POST /api/ai/forge/record`
  Records a live forecast. Body: `asset`, optional `token_address`, `chain`,
  `horizon`, `mode`, and `historical_limit`.
- `POST /api/ai/forge/evaluate`
  Evaluates due entries. Body: optional `asset` and `evaluate_all`.
- `POST /api/ai/forge/backtest`
  Runs a historical replay. Body: `asset`, optional `horizon`, `mode`,
  `lookback`, `stride`, and `limit`.
- `GET /api/ai/forge/watchlist`
  Lists Forge watchlist entries.
- `POST /api/ai/forge/watchlist`
  Adds a watch. Body: `asset` or `token_address`, optional `chain`, `horizons`,
  `modes`, `interval_minutes`, `thresholds`, and `user_id`.
- `DELETE /api/ai/forge/watchlist/<watch_id>`
  Deletes a watch.
- `POST /api/ai/forge/watchlist/run`
  Processes due watches. Body: optional `force`.
- `GET /api/ai/forge/alerts?asset=ETH&watch_id=watch_...&limit=50`
  Lists persisted Forge alert events.
- `DELETE /api/ai/forge/alerts`
  Clears persisted Forge alert events.

## Backtesting

The backtester replays historical OHLCV windows through the same deterministic
forge engine used in live forecasts. It compares the forecast direction against
the later realized return and reports:

- sample count
- directional accuracy
- mean future return
- mean forecast score
- per-sample direction, score, return, and correctness

## Watchlists

The watchlist is stored at `~/.agent/trend_forge_watchlist.json` by default.
Set `TREND_FORGE_WATCHLIST_PATH` to override it.

Alert events are stored at `~/.agent/trend_forge_alerts.json` by default. Set
`TREND_FORGE_ALERTS_PATH` to override it.

Each watch supports:

- `asset` and/or `token_address`
- `chain`
- `horizons`, such as `["1h", "4h", "24h"]`
- `modes`, such as `["composite", "risk"]`
- `interval_minutes`
- score thresholds for `attention_score`, `risk_score`, and `confidence`

The background Forge tracker processes due watches after it evaluates due ledger
records. Processing a watch records forecasts into the ledger and returns alert
events when configured thresholds are crossed.

Emitted alert events are persisted so Telegram, the API, and tools can show
recent Forge alerts after the watchlist run has completed.

## Telegram Menu

The Telegram main menu includes `Forge`, which opens:

- `Contract Check`
  Prompts for `CONTRACT [chain]`, resolves the contract, and runs a 24h
  composite forecast.
- `Record Forecast`
  Prompts for `ASSET_OR_CONTRACT [chain] [horizon] [mode]`.
- `Ledger Accuracy`
  Evaluates due records and shows the ledger summary.
- `Backtest`
  Prompts for `ASSET [horizon] [mode]`.
- `Add Watch`
  Prompts for `ASSET_OR_CONTRACT [chain] [horizons_csv] [modes_csv]`.
- `List Watches`
  Shows configured watches.
- `Latest Alerts`
  Shows persisted Forge alert events.
- `Run Watchlist`
  Forces active watches to record immediately.

Examples:

```text
ETH ethereum 1h composite
0x... base 24h risk
0x... base 1h,24h composite,risk
```

## Dashboard Panel

The portfolio dashboard includes a `Trend Prediction Forge` panel with:

- ledger direction accuracy
- pending forecast count
- active watch count
- recent alert count
- latest Forge alerts
- active watches
- quick actions for record forecast, add watch, run watchlist, and backtest

The dashboard uses the existing authenticated Forge API routes and writes action
responses to the panel output area.
