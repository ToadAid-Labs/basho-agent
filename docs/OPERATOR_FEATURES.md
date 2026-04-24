# Operator Feature Sheet

This document is an operator-facing view of the current system. It is grounded in
the repository's current code paths, registered tools, Telegram menus, backend
routes, and background loops.

It is not a roadmap. It is a statement of what the system currently has.

## 1. Interfaces

### Telegram Bot
- Freeform AI chat
- Menu-driven interaction
- Inline actions for market, wallet, risk, paper trading, live trading, Forge, and settings
- Image/chart upload handling for vision-based analysis

### Web Dashboard
- Flask-based web UI
- Login-protected dashboard
- Provider auth pages for Gemini/OpenAI flows
- Forge/watchlist dashboard controls

### CLI
- `agent.py` chat / bot entrypoint
- Local terminal chat loop

## 2. Model Providers

The agent can run on:
- Gemini
- OpenAI
- OpenAI Codex
- Anthropic
- Ollama

Current provider selection is environment-driven and loaded through the shared
provider factory in `core/provider.py`.

## 3. Core Agent Features

- Tool-calling conversational agent
- Persistent session history
- Provider-specific session resume
- User-aware context injection for Telegram users
- Role-based sub-agents:
  - researcher
  - executor
  - risk_manager
  - validator
- Strategy-file memory
- Wisdom ledger / commandments
- Background-process awareness in prompt context

## 4. Telegram Operator Surface

The Telegram bot currently exposes these menu areas:
- Dashboard
- Portfolio
- Market
- Paper Trading
- Learn / Explain
- Risk
- Live Trading
- Wallet
- Forge
- Agent Tools
- Settings

Representative Telegram actions currently wired in code include:
- price checks for BTC / ETH / SOL
- custom token price lookups
- token search
- swap quote lookup
- wallet status / addresses / balances / gas balances
- token risk checks
- paper buy / sell
- paper portfolio and trade history
- strategy PnL
- prediction accuracy
- market regime
- backtests
- wisdom ledger access
- Forge watch add/list/run
- Forge alerts view

## 5. Market Data and Research Tools

Registered market/research tools include:
- `check_price`
- `list_trading_symbols`
- `fetch_ticker`
- `fetch_historical`
- `get_supported_symbols`
- `calculate_bollinger_bands`
- `get_orderbook`
- `web_search`
- `web_fetch`
- `get_daily_alpha`
- `check_market_sentiment`
- `check_whale_activity`
- `check_smart_money_holdings`
- `hunt_insider_wallets`
- `verify_alpha_wallet`
- `add_alpha_wallet`

These cover price lookup, candles, sentiment, web/news research, whale activity,
and alpha-wallet workflows.

## 6. Trading, Risk, and Strategy Features

### Paper Trading
- Create paper trading account
- Execute paper trades
- View paper portfolio status
- View paper trade history

### Risk and Positioning
- `check_risk_limits`
- `calculate_kelly_risk`
- `calculate_position_size`
- halt / resume trading controls

### Strategy Memory
- `read_strategy`
- `write_strategy`
- `write_wisdom_commandment`

### Strategy Evaluation
- `run_model_backtest`
- `run_walk_forward_backtest`
- `optimize_strategy_parameters`
- `audit_strategy_performance`
- `prune_wisdom_ledger`
- `trade_decision_engine`

## 7. Technical Analysis Features

Registered analysis tools include:
- `analyze_market_trend`
- `get_pro_indicators`
- `analyze_market_structure`
- `get_multi_timeframe_signal`
- `get_swing_setup`
- `analyze_chart_vision`

These cover trend summaries, structured indicator output, multi-timeframe checks,
market structure, swing setup generation, and chart/image analysis.

## 8. On-Chain / Wallet Features

Registered wallet and swap tools include:
- `get_wallet_status`
- `create_agent_wallet`
- `get_wallet_addresses`
- `get_wallet_balance`
- `transfer_tokens`
- `swap_tokens`
- `check_onchain_risk`
- `trust_search_token`
- `trust_get_token_price`
- `trust_get_swap_quote`
- `copy_trade_wallet`
- `rebalance_portfolio`

Operationally, this gives the system:
- wallet creation and inspection
- token balance lookup
- transfer and swap support
- token search and quote support
- on-chain risk checks

## 9. Security Features

Registered security-related tools include:
- `audit_token_contract`
- `check_onchain_risk`
- token-risk actions exposed in Telegram wallet/live/risk menus

The system uses these for:
- honeypot / rug-pull style screening
- contract safety checks
- wallet-side token risk review

## 10. Alerts and Monitoring

Registered alert tools:
- `set_smart_alert`
- `list_alerts`
- `delete_alert`

Supported alert types in the backend include:
- price up / price down
- sentiment spike
- wallet activity

Monitoring subsystems present in the repo include:
- sentiment engine
- whale tracker
- market analyzer
- alert stores

## 11. Forge / Prediction Suite

The Trend Prediction Forge currently includes:
- `forge_token_prediction`
- `forge_signal_template`
- `forge_resolve_contract`
- `forge_live_token_prediction`
- `forge_record_live_prediction`
- `forge_evaluate_due_predictions`
- `forge_prediction_ledger_summary`
- `forge_backtest_trend_model`
- `forge_add_watch`
- `forge_list_watches`
- `forge_delete_watch`
- `forge_run_watchlist`
- `forge_list_alerts`
- `forge_clear_alerts`

Operationally this provides:
- token forecast generation
- live prediction recording
- evaluation of due predictions
- accuracy summaries
- recurring watchlists
- watch-triggered alert generation
- prediction-model backtesting

## 12. Background Loops

The Flask backend currently starts these background threads:
- `accuracy_tracker_loop()`
- `trend_forge_tracker_loop()`
- `sentiment_tracker_loop()`
- `alert_processor_loop()`

What they do:

### Accuracy Tracker
- Evaluates due predictions
- Can trigger retraining-related workflows when accuracy drops

### Trend Forge Tracker
- Evaluates due Forge predictions
- Processes due watchlist entries
- Emits Forge alerts

### Sentiment Tracker
- Scans BTC / ETH / SOL sentiment on an interval
- Can invoke the agent for risk-manager review on extreme sentiment

### Alert Processor
- Scans active user alerts
- Triggers researcher summaries when alert conditions are met

## 13. Autonomous / Council Features

The repo contains:
- `trigger_autonomous_cycle`
- `check_background_processes`
- `delegate_task`
- `verify_with_council`

There is also a background orchestrator implementation in `core/orchestrator.py`.

Important operational note:
- The autonomous orchestrator loop exists in code.
- The backend startup path currently comments out automatic orchestrator thread launch.
- Manual triggering is still available through registered tools.

## 14. Workspace / Memory Assets

The workspace currently includes:
- strategy memory files in `workspace/agent_memory/`
- Tobyworld archive files
- mission briefing strategy file
- user config
- account ledger
- tasks and agent policy files
- contracts registry

This means the system can persist operator notes, symbol strategies, and domain-
specific context outside ephemeral chat history.

## 15. Current Tobyworld-Related Operational State

From current repo + runtime state conventions, the system is set up to support:
- Mission briefing anchored to `workspace/tobyworld_master_archive.md`
- Tobyworld Trinity strategy context
- 4h Forge watch support for TOBY / PATIENCE / TABOSHI
- ETH and SOL as additional macro watch markers

## 16. Operational Strengths

- Broad tool surface already exists
- Telegram UI is much stronger than a plain chat bot
- Forge/watchlist/prediction stack is real and test-covered
- Wallet / Trust integration is already present
- Multiple provider backends reduce provider lock-in

## 17. Known Gaps / Partial Areas

These are not missing from the codebase entirely, but they are not yet a fully
polished operator experience:

- No single built-in health command that reports:
  - provider auth state
  - active watches
  - last Forge run
  - pending / evaluated prediction counts
  - recent errors
- Some operator answers still mix hard facts with narrative phrasing
- Global vs user-scoped watch ownership is functional but not fully modeled as a
  first-class operational concept
- Background state still depends on process restarts to pick up some code changes

## 18. Recommended Operator Usage

Best current operator pattern:

1. Use Telegram for everyday operations and quick checks.
2. Use the web dashboard for provider auth and Forge/watch management.
3. Use strategy memory files for persistent instructions and domain notes.
4. Use Forge watches for recurring token monitoring.
5. Use paper trading and backtests before trusting new strategy logic.
6. Treat narrative market interpretation as secondary to the raw tool output.

## 19. Bottom Line

This is currently a multi-interface crypto agent platform with:
- chat + menu operations
- market research
- technical analysis
- paper trading
- wallet tooling
- security screening
- alerting
- prediction/watchlist infrastructure
- persistent memory
- multiple model-provider backends

It is already feature-rich enough for active operator use. The next maturity step
is not raw feature count. It is operational observability and cleaner health
reporting.
