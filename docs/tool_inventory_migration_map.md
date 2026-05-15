# Tool Inventory And Migration Map

## Executive Summary
This repo has a wide `tools/` surface, but it is not uniformly safe or portable. The toolset splits into five broad buckets:

1. Read-only market/analysis tools with relatively clean seams.
2. Paper-trading and alerting tools that mutate local state but avoid live execution.
3. Wallet and swap tools that are explicitly sensitive and should not be first ports.
4. Orchestration/delegation surfaces that can cause tool fanout if copied naively.
5. Placeholder, weakly tested, or repo-coupled modules that are not good first migrations.

The safest and highest-value first ports into `~/coder` are not the full trading stack. They are:
- `planner_guard / tool_policy` from `core/`, not `tools/`
- read-only market data fetchers
- contract security/audit checks
- fail-closed signal formatting/policy patterns from Insider Hunt
- low-risk alerting and wallet-activity monitoring
- paper-trading ledger/risk surfaces only after the guard layer exists

Module-level safety below uses the highest-risk public surface in that file. Mixed files are called out explicitly.

## Full Tool Table
| Module | Public surface | Purpose | Expected inputs | Output shape | External deps / env / data sources | Safety class | Usefulness for `~/coder` | Migration difficulty | Recommended destination | Failure behavior | Test coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `alert_tools.py` | `set_smart_alert`, `list_alerts`, `delete_alert` | Local background alert CRUD, including wallet-activity alerts | `alert_type`, `user_id`, `symbol`/`wallet_address`, `value`, `chain` | Human-readable status string or JSON string list | `memory.alerts.AlertStore`; optional `tools.wallet_activity` | `state_mutating` | `high` | `easy` | `alerting` | Returns error strings; seeds wallet cursor best-effort | No direct module test; wallet alert path covered indirectly by `test_wallet_activity_alerts.py` |
| `arbitrage_tools.py` | `analyze_pair_correlation` | Statistical arbitrage / correlation analysis | `asset_a`, `asset_b`, `lookback_days` | Likely JSON/text string | `pandas`, `numpy`, `backend.portfolio_dashboard` | `read_only` | `low` | `medium` | `analysis` | Analysis failure returns string | No obvious dedicated tests |
| `backtest_tool.py` | `run_model_backtest`, `run_walk_forward_backtest`, `PricePredictionStrategy` | Historical model backtests | thresholds, train/test windows | Text/JSON summary string | `pandas`, `numpy`, `monitoring.backtesting`, `backend.price_prediction` | `read_only` | `medium` | `hard` | `paper_trading` | Returns error text on exceptions | `test_trend_backtest.py` and backend tests touch related backtest code, not this tool directly |
| `bash.py` | `bash`, `read_file`, `write_file` | Generic shell and filesystem access | shell command, file path, content | Raw stdout/stderr or file text | `subprocess`, local filesystem | `state_mutating` | `do_not_port_yet` | `hard` | `not_recommended` | Propagates shell/file errors as strings | Mentioned in Telegram tests; not a migration target |
| `copy_trading.py` | `copy_trade_wallet` | Mirrors whale activity into paper trading | wallet address, `user_id`, mirror amount, chain | Status string | `tools.trading_control.execute_paper_trade` | `paper_only` | `low` | `medium` | `paper_trading` | Returns error/status string; simulates rather than verifies real wallet data | No obvious dedicated tests |
| `graph_intelligence_tools.py` | `detect_coordinated_moves`, `analyze_wallet_cluster` | Cluster/graph-style wallet analysis | chain, time window, wallet address | JSON string | `monitoring.whale_tracker.WhaleTracker`, `requests` | `unknown` | `low` | `hard` | `not_recommended` | Mostly placeholder/mock logic; returns error strings | No tests |
| `insider_hunter.py` | `hunt_insider_wallets`, `verify_alpha_wallet`, `add_alpha_wallet`, `InsiderHuntEngine` | Fail-closed Base watchlist detector plus alpha-wallet scoring; one helper mutates wallet list | gain/price/liquidity thresholds; wallet address/chain; notes | Structured JSON string with `status`, timestamps, signals, confidence, sources, warning | `subprocess`/`twak`, `backend.dexscreener`, `tools.security_tools`, `memory.wallets` | `state_mutating` | `high` | `medium` | `analysis` | Fails closed with `no_signal`/`rejected`/`error`; read-only detector is strong, `add_alpha_wallet` mutates state | Strong targeted coverage in `test_insider_hunter.py` |
| `macro_tools.py` | `get_macro_context`, `calculate_asset_correlation` | Macro regime context and asset/index correlation | optional macro index, include events | Text or JSON-style string | `requests`, Yahoo-style market fetches | `read_only` | `medium` | `easy` | `market_data` | Returns fallback/error strings | No direct tests |
| `market_data.py` | `MarketDataAnalyzer` class | Thin helper wrapper over Trust market data | token address, chain | Python dict/float helpers | `tools.trust.TrustWalletAPI` | `read_only` | `low` | `easy` | `market_data` | Mostly returns `0.0` or error dicts; several placeholder methods | No tests |
| `market_report.py` | `market_report` and snapshot helpers | Multi-asset composite market report | optional symbol list | Human-readable report string | `tools.trading_data`, `tools.technical_analysis`, `tools.news_tools` | `read_only` | `medium` | `medium` | `analysis` | Degrades via helper parsing; fanout-prone by design | `test_market_report.py`, guard coverage in `test_agent_context.py` |
| `news_tools.py` | `get_daily_alpha` | Aggregated crypto catalyst/news summary | optional symbols list | Text report string | RSS/news feeds, `monitoring.sentiment_engine` | `read_only` | `medium` | `medium` | `analysis` | Network/parser failures likely become error string | No direct tests |
| `optimization_tools.py` | `optimize_strategy_parameters` | Grid search parameter optimization | symbol, threshold range, days | Text/JSON summary string | `monitoring.backtesting`, `tools.backtest_tool` | `read_only` | `low` | `hard` | `risk` | Returns error/status strings | No direct tests |
| `orchestration.py` | `delegate_task`, `verify_with_council` | Spawns specialized sub-agents / second-opinion flows | role, task, provider, context | Status/analysis string | `core.agent`, `core.provider` | `state_mutating` | `do_not_port_yet` | `hard` | `not_recommended` | Can amplify context/tool fanout; repo-specific agent coupling | No direct tests |
| `orchestration_tools.py` | `trigger_autonomous_cycle`, `check_background_processes` | Background autonomous trading cycle controls | chat_id, none | Status/JSON string | `core.orchestrator` | `state_mutating` | `do_not_port_yet` | `hard` | `not_recommended` | Triggers background work; broad orchestration risk | No direct tests |
| `order_book_tools.py` | `analyze_order_book` | Binance depth / wall analysis | symbol, wall multiple | Text/JSON string | `requests` to Binance depth endpoint | `read_only` | `medium` | `easy` | `market_data` | Returns error string on API failure | No direct tests |
| `performance_audit.py` | `audit_strategy_performance`, `prune_wisdom_ledger` | Paper-PnL attribution and wisdom pruning | `user_id`, `perform_removal` | Text/JSON summary string | `backend.paper_trading`, `memory.wisdom`, `core.agent` | `state_mutating` | `medium` | `medium` | `memory/reflection` | Mixed read/write; pruning can mutate commandment store | No direct tests |
| `prediction_tools.py` | `TechnicalIndicators`, `PricePredictionModel`, `MarketStateAnalyzer` | ML library code, not registered tools | OHLCV DataFrames, model state | Python objects, model artifacts | `numpy`, `pandas`, `sklearn`, `joblib`; writes `~/.agent/models` | `unknown` | `low` | `hard` | `not_recommended` | Heavy internal ML lib with disk writes and no tool wrapper | No direct tests |
| `rebalance.py` | `rebalance_portfolio` | Paper portfolio rebalance | `user_id`, target allocation JSON | Status string | `tools.trading_control`, paper account data | `paper_only` | `medium` | `medium` | `paper_trading` | Mutates paper holdings; error strings on parse/validation issues | No direct tests |
| `reflection.py` | `generate_post_mortem`, `trigger_post_mortem` | Writes trade post-mortem learnings | trade data dict | Side-effect only / `None` | `memory.wisdom`, `core.agent`, threading | `state_mutating` | `medium` | `medium` | `memory/reflection` | Background write behavior; no tool registration | No tests |
| `rl_policy_tools.py` | `get_rl_policy_recommendation`, `run_policy_simulation` | RL-themed recommendations/simulations | symbol, timeframe, strategy | Text/JSON string | `random`; apparently heuristic/mock | `unknown` | `low` | `medium` | `not_recommended` | Weak provenance, likely simulated output | No tests |
| `security_tools.py` | `audit_token_contract` | GoPlus contract risk audit | token address, chain | Human-readable audit text | `requests` to GoPlus API | `read_only` | `high` | `easy` | `risk` | Returns API/error strings; unsupported chain check | Indirect coverage in `test_trend_signal_collector.py`; stronger behavior now also reflected in Insider Hunt parsing |
| `sentiment_tool.py` | `check_market_sentiment` | Sentiment lookup for a symbol | symbol | JSON/text string | `monitoring.sentiment_engine` | `read_only` | `medium` | `easy` | `analysis` | Returns sentiment result or error string | No direct tests |
| `strategy_tools.py` | `read_strategy`, `write_strategy`, `calculate_position_size`, `write_wisdom_commandment` | Strategy-file persistence plus simple sizing | symbol/content; balance/risk/price; commandment text | File text or status string | local filesystem under `workspace/agent_memory`, `memory.wisdom` | `state_mutating` | `medium` | `easy` | `planning` | Read/write surfaces mutate local memory; sizing is clean read-only logic | `test_strategy_memory_and_paper_trading.py` covers strategy memory path indirectly |
| `swing_tools.py` | `get_swing_setup` | Swing-trade setup with fib zones / ATR / RSI divergence | symbol, timeframe | JSON string | `pandas`, `pandas_ta`, `backend.portfolio_dashboard` | `read_only` | `medium` | `medium` | `analysis` | Parsing/market-data failures return string | No direct tests |
| `technical_analysis.py` | `get_pro_indicators`, `analyze_market_structure`, `get_multi_timeframe_signal`, `detect_market_regime` | Technical indicator and structure suite | symbol, lookback/period | Mostly JSON string | `pandas`, `pandas_ta`, `backend.portfolio_dashboard` | `read_only` | `high` | `medium` | `analysis` | Indicator failures degrade to error strings; fanout risk if used naively | Indirect via `test_trade_decision_engine.py`, `test_market_report.py`, guard tests |
| `trade_decision.py` | `trade_decision_engine` | Composite trade/no-trade decision with sizing | symbol, optional account/token_address/risk settings | Structured JSON string | `tools.trading_data`, `technical_analysis`, `swing_tools`, `trading_control`, optional whale checks | `read_only` | `high` | `medium` | `planning` | Read-only but internally fans out into many tools; safe only with planner guard | Good direct coverage in `test_trade_decision_engine.py` |
| `trade_learning.py` | `synthesize_trade_learnings`, `get_conviction_signal` | Learn from past trades / derive conviction score | limit, symbol, strategy, current RSI/sentiment | JSON/text string | `backend.database`, `backend.portfolio_dashboard`, `pandas` | `read_only` | `medium` | `medium` | `memory/reflection` | Depends on local DB state; can fail if historical data absent | No direct tests |
| `trading_control.py` | `check_price`, `list_trading_symbols`, `create_paper_trading_account`, `get_portfolio_status`, `execute_paper_trade`, `check_risk_limits`, `analyze_market_trend`, `get_trade_history`, `calculate_kelly_risk`, `resume_trading`, `halt_trading` | Canonical paper-trading and execution gate module | user IDs, symbols, trade params, risk inputs | Human-readable status strings | `backend.paper_trading`, `risk_management`, `execution_layer`, `tools.trading_data`, `tools.trust` | `paper_only` | `high` | `medium` | `paper_trading` | Mixed read/write; `halt_trading` / `resume_trading` mutate state; no live order placement here | Indirect/direct coverage in `test_strategy_memory_and_paper_trading.py`, `test_traceback.py`, agent tests |
| `trading_data.py` | `fetch_ticker`, `fetch_historical`, `get_supported_symbols`, `calculate_bollinger_bands`, `get_orderbook` | Core read-only market data layer | symbol, interval, limit, band params | JSON strings | `urllib` to Binance/Bybit-style endpoints; fallback to Trust for some ticker paths | `read_only` | `high` | `easy` | `market_data` | Returns `[error]` or JSON string; relatively clean seam | Indirect coverage in `test_trend_signal_collector.py` and downstream tests |
| `trend_prediction_tools.py` | `forge_*` prediction, ledger, watchlist, alert tools | State-aware trend prediction and watchlist stack | asset/address/horizon/mode; watch IDs; force flags | Mostly structured JSON strings | Many repo-specific backend services: trend engine, ledger, watchlist, DexScreener | `state_mutating` | `medium` | `hard` | `analysis` | Strong repo coupling; some methods mutate ledger/watchlist/alerts | Good direct coverage in `test_trend_prediction.py` |
| `trust.py` | `TrustWalletAPI`, `trust_search_token`, `trust_get_token_price`, `trust_get_swap_quote`, safe helpers | Read-only Trust market-data/search/quote layer | query, token symbol/address, amount, chain | JSON strings | `requests`, `dotenv`; env: `TWAK_ACCESS_ID`, `TWAK_HMAC_SECRET`, `MOCK_API` | `read_only` | `high` | `medium` | `market_data` | API/auth/network failures returned as strings or `None` helpers | Covered indirectly by `test_api.py`, `test_setup.py`, Telegram tests |
| `trust_wallet.py` | wallet status/balance tools plus `transfer_tokens`, `swap_tokens`, `check_onchain_risk` | Wallet portfolio, tracked token balance, transfers, swaps | chain, amount, token, execute flag, symbol | Status strings, portfolio text | `twak` CLI; env: `TWAK_WALLET_PASSWORD`, `TWAK_WALLET_SESSION`, `USE_MEV_PROTECTION`, `PRIVATE_RPC_URL`, timeouts | `wallet_sensitive` | `do_not_port_yet` | `hard` | `execution_gate` | Explicit live execution path for swaps/transfers; must stay gated | Strong direct coverage in `test_trust_wallet.py`, plus Telegram/execution tests |
| `tutor_tools.py` | `tutor_explain_activity` | Explain recent trading activity pedagogically | `user_id`, limit | Text string | `backend.paper_trading`, `memory.wisdom` | `read_only` | `low` | `easy` | `memory/reflection` | Returns explanation/error string | No direct tests |
| `vision_analysis.py` | `analyze_chart_vision`, `generate_price_chart_image`, `ChartImageResult` | Vision-LLM chart reading | symbol, periods | Text string | Provider APIs; env: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MODEL_PROVIDER` | `read_only` | `medium` | `hard` | `analysis` | External model dependency; provider failures as strings | Mentioned in Telegram tests, not deeply asserted |
| `wallet_activity.py` | `BaseScanWalletActivityTracker`, `get_latest_wallet_activity`, `check_wallet_activity` | Read-only Base wallet polling helper | wallet address, chain, cursor | Python dicts / snapshot dataclass | `requests`; env: `BASESCAN_API_KEY` | `read_only` | `high` | `easy` | `alerting` | Raises or returns structured activity state; good fail messages for missing/invalid keys | Strong direct coverage in `test_wallet_activity_alerts.py` |
| `web.py` | `web_search`, `web_fetch` | Generic web search/fetch | query, URL, max chars | Text strings | `urllib` and public web | `read_only` | `low` | `easy` | `not_recommended` | Generic uncontrolled web surface; existing platforms usually already provide this | No direct tests |
| `whale_tracker_tool.py` | `check_whale_activity`, `check_smart_money_holdings` | Canonical whale/smart-money read-only lookups | token address, chain | JSON string | `monitoring.whale_tracker` | `read_only` | `medium` | `medium` | `analysis` | Returns JSON or error string | No direct tests |
| `__init__.py` | none | Package marker only | none | none | none | `read_only` | `low` | `easy` | `not_recommended` | N/A | N/A |

## Best First Ports
Biasing toward small, safe, testable seams for `~/coder`, the best first ports are:

1. `core.tool_policy` + agent planner guard
   - Not under `tools/`, but the safest first migration seam.
   - Prevents fanout before any analysis tools are added.
   - Already shaped for intent gating, max tool calls, and fail-closed blocking of live execution.

2. `tools/trading_data.py`
   - Best canonical read-only market data seam.
   - Simple inputs, JSON string outputs, relatively low coupling.
   - Useful for ticker, historical candles, order book, and basic symbol support.

3. `tools/security_tools.py`
   - High-signal, low-risk contract audit capability.
   - Small surface area, easy to metadata-mark as read-only.
   - Useful as a common risk gate for later signal tools.

4. Read-only portions of `tools/insider_hunter.py`
   - Specifically: fail-closed output contract, confidence handling, signal formatting, audit parsing, cluster policy.
   - Do **not** port `add_alpha_wallet` in the first seam.

5. `tools/wallet_activity.py`
   - Good low-risk alerting helper with strong targeted tests.
   - Useful for wallet-watch alerts without enabling wallet execution.

6. `tools/alert_tools.py`
   - Low-risk local-state mutation only.
   - Useful after planner guard exists.
   - Good fit for agent-side watchlists and notifications.

7. Read-only / paper-safe subset of `tools/trading_control.py`
   - Start with `check_price`, `get_portfolio_status`, `check_risk_limits`, `get_trade_history`, `calculate_kelly_risk`.
   - Delay `halt_trading` / `resume_trading` until the target repo has a paper ledger.

8. `tools/technical_analysis.py`
   - High utility if the target repo accepts `pandas` / `pandas_ta`.
   - Needs guardrails because it is often over-called and participates in fanout.

9. `tools/strategy_tools.py` read-only/sizing subset
   - `calculate_position_size` is an easy, useful port.
   - `read_strategy` may be useful if `~/coder` already has an equivalent memory directory.

10. `tools/trust.py` read-only market subset
   - Search/price/quote are useful if the target repo wants Trust market data.
   - Requires API credential handling and clearer provenance notes.

## Tools Not Safe To Port Yet
- `tools/trust_wallet.py`
  - Wallet-sensitive; includes live transfer and swap execution.
- `tools/bash.py`
  - Generic command/file mutation surface, not a safe migration candidate.
- `tools/orchestration.py`
  - Delegation/fanout risk before planner guard and metadata controls are mature.
- `tools/orchestration_tools.py`
  - Triggers autonomous cycles and background work.
- `tools/graph_intelligence_tools.py`
  - Placeholder/mock behavior; weak data provenance.
- `tools/rl_policy_tools.py`
  - Weak provenance; likely simulated rather than production-grounded.
- `tools/prediction_tools.py`
  - Heavy ML library, writes model artifacts, unwrapped by tools.
- `tools/copy_trading.py`
  - Encourages mirrored trading behavior before execution governance is mature.
- `tools/rebalance.py`
  - Paper-state mutation is fine later, but not before the ledger/risk model is ported.
- `tools/trend_prediction_tools.py`
  - Valuable later, but tightly coupled to many backend services and mutable ledgers/watchlists.

## Required Environment Variables And Data Sources
Known env vars or operator prerequisites referenced by the tool surface:

- `TWAK_ACCESS_ID`
- `TWAK_HMAC_SECRET`
- `MOCK_API`
- `TWAK_WALLET_PASSWORD`
- `TWAK_WALLET_SESSION`
- `USE_MEV_PROTECTION`
- `PRIVATE_RPC_URL`
- `TWAK_DIRECT_BALANCE_TIMEOUT_SECONDS`
- `TWAK_PORTFOLIO_CHAIN_TIMEOUT_SECONDS`
- `BASESCAN_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `MODEL_PROVIDER`

Important external services and data sources:
- Binance / Bybit-style market endpoints via `urllib` or `requests`
- Trust Wallet market APIs
- TWAK CLI for wallet and market flows
- GoPlus Security API
- BaseScan API
- DexScreener
- RSS/news feeds and repo-local monitoring/backtesting services

## Test Coverage Notes
- Strongest direct tool coverage:
  - `insider_hunter.py`
  - `trust_wallet.py`
  - `wallet_activity.py`
  - `trade_decision.py`
  - `trend_prediction_tools.py`
  - `market_report.py`
- Moderate/indirect coverage:
  - `trading_data.py`
  - `security_tools.py`
  - `strategy_tools.py`
  - `trading_control.py`
  - `trust.py`
- Sparse or absent direct coverage:
  - `alert_tools.py`
  - `macro_tools.py`
  - `news_tools.py`
  - `technical_analysis.py`
  - `swing_tools.py`
  - `whale_tracker_tool.py`
  - most orchestration, reflection, RL, graph-intelligence, arbitrage, optimization, and copy-trading modules

Coverage caveat:
- This inventory used explicit test-file references and direct inspection. Some modules may be exercised indirectly through backend/integration tests without being named directly.

## Overlap And Conflict Notes
### `market_data.py` vs `trading_data.py`
- `trading_data.py` is the more canonical surface.
- It is registered as tools, has cleaner read-only seams, and is referenced by downstream report/decision code.
- `market_data.py` is a thin helper wrapper around Trust and contains placeholder volume/liquidity/volatility methods.
- Recommendation: port `trading_data.py` first; ignore `market_data.py` unless a class wrapper is needed later.

### `trade_decision.py` vs `strategy_tools.py` vs `prediction_tools.py`
- `trade_decision.py` is the canonical composite decision surface.
- `strategy_tools.py` is mostly persistence and sizing, not decision logic.
- `prediction_tools.py` is a lower-level ML library with no registered tools and heavier coupling to local model storage.
- Recommendation: if porting decision logic, use `trade_decision.py` only after planner guard exists; port `calculate_position_size` from `strategy_tools.py` separately; delay `prediction_tools.py`.

### `whale_tracker_tool.py` vs `graph_intelligence_tools.py`
- `whale_tracker_tool.py` appears more canonical and production-oriented.
- `graph_intelligence_tools.py` explicitly contains placeholder/mock graph logic and weak provenance.
- Recommendation: keep `whale_tracker_tool.py`; defer or discard `graph_intelligence_tools.py`.

### `trading_control.py` vs execution-like modules
- `trading_control.py` is the canonical paper-trading / execution-gate surface.
- `trust_wallet.py` is the live wallet-sensitive execution surface and must stay separate.
- `trust.py` is read-only market data and quote lookup, not execution governance.
- Recommendation: port paper-safe pieces from `trading_control.py` later; do not mix them with `trust_wallet.py` in an early seam.

### `market_report.py` vs direct analysis tools
- `market_report.py` is useful for operator convenience but is inherently fanout-prone.
- `technical_analysis.py` and `trading_data.py` are safer primitive seams.
- Recommendation: port primitives first, then add a guarded composite report later if needed.

### `orchestration.py` / `orchestration_tools.py` vs planner guard
- The orchestration surfaces increase fanout and background side effects.
- The planner guard and tool policy should land before any delegation/autonomous-cycle capability.
- Recommendation: do not port orchestration before the guard layer is stable in `~/coder`.

## Suggested Staged Migration Plan Into `~/coder`
### Stage 1
- Port `planner_guard / tool_policy` from `core/`.
- Add tool metadata support: read-only, human confirmation, live execution flag.
- Add focused tests proving narrow intent plans and live-execution blocking.

### Stage 2
- Port `trading_data.py` read-only subset.
- Port `security_tools.py`.
- Standardize typed/fail-closed output envelopes for read-only tools.

### Stage 3
- Port read-only signal formatting and audit parsing patterns from `insider_hunter.py`.
- Port `wallet_activity.py`.
- Add low-risk alert store / watchlist alerting if the target repo wants local persistence.

### Stage 4
- Port `technical_analysis.py` and maybe `trade_decision.py`, but only behind planner guard.
- Keep fanout-limiting tests mandatory.

### Stage 5
- Port paper-ledger and risk surfaces from `trading_control.py`.
- Still no live wallet execution.

### Stage 6
- Reassess heavier or more coupled modules:
  - `trend_prediction_tools.py`
  - `news_tools.py`
  - `macro_tools.py`
  - `performance_audit.py`

## Prompt for `~/coder` dual-mode agent repo
Use this as the first migration prompt:

```text
Codex, implement the smallest safe migration seam from the Python trading-agent repo into this repo.

Goal:
Port only the planner guard / tool policy layer first.

Requirements:
- Read-only by default.
- No live trading.
- No private key access.
- No wallet signing.
- No swap or transfer execution.
- Fail closed if intent is ambiguous.
- Prevent tool fanout.
- Enforce narrow intent-based allowed tool sets.
- Enforce per-intent max tool calls.
- Add stop conditions once enough evidence is gathered.
- Support clear internal tool metadata:
  - read_only = true/false
  - requires_human_confirmation = true/false
  - live_execution = true/false

Implementation constraints:
- Keep the seam small.
- Do not migrate broad orchestration or autonomous-cycle logic.
- Do not port live wallet tools.
- Do not port market-report fanout logic yet.
- Prefer one new policy module plus one narrow integration point in the agent/tool router.

Testing requirements:
- Add focused tests proving DEGEN watch / buyback style requests do not trigger broad market-report, whale, smart-money, or indicator fanout.
- Add tests proving live-execution tools are blocked by default unless explicitly routed through a future execution gate.
- Add tests proving the planner returns partial results after enough evidence rather than calling more tools.

Output requirements:
- Clear guard messages.
- Read-only by default.
- Human confirmation required for anything that would later become execution-capable.

Do not port any live trading or private-key code in this seam.
```
