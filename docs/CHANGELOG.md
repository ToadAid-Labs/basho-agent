# Changelog

All notable changes to the Telegram Trading Bot will be documented in this file.

## [1.6.0] - 2026-04-19

### Added
- **Alpha Validator (Council Voting)**: Introduced a "Devil's Advocate" agent role. Trade proposals now require a unanimous consensus vote between the Risk Manager and the Validator to reduce noise and false signals.
- **Process Shield (Stability)**: Implemented a robust PID Lock system. Prevents multiple instances of the bot or orchestrator from running simultaneously, eliminating Telegram `Conflict` errors and ensuring 24/7 reliability.
- **Institutional Triple Screen**: Overhauled the multi-timeframe signal tool. It now confirms trend alignment across **1h, 4h, 1d, and 1w** timeframes using real market data from multiple exchanges.
- **Region-Resilient Market Data**: Integrated **Kraken** and **Coinbase** as primary failover sources for historical data. Automatically bypasses region-specific blocks (like Binance 451/403 errors).
- **Background awareness**: The AI Agent is now fully aware of its background processes via a new global registry and system prompt injection.

### Fixed
- **Historical Data Failover**: Resolved the 403 Forbidden issues by implementing an automatic multi-exchange polling strategy.
- **UI Responsiveness**: Fixed a bug where the "Portfolio" tab would display a raw error for new users; now it guides them to create a paper account.

## [1.5.1] - 2026-04-19

### Added
- **Session Persistence**: Implemented disk-based session memory (`~/.agent/telegram_sessions/`) for Telegram conversations. The agent now remembers context across service restarts and reboots.
- **Persistent Typing Indicator**: The Telegram bot now Resends the "typing..." indicator every 5 seconds while the AI is thinking or executing tools, providing better visual feedback during long-running local model inferences (Ollama).

### Fixed
- **Critical Import Error**: Resolved a `NameError` in `core/agent.py` where `get_provider` was missing its import, which caused background alert processors to crash.
- **Trade Execution Syntax**: Fixed a malformed line continuation character in `tools/trading_control.py` that caused a `SyntaxError` during paper trade execution.
- **Process Conflict**: Improved bot startup logic to prevent multiple instances from polling Telegram simultaneously, resolving `Conflict` errors.

## [1.5.0] - 2026-04-18

### Added
- **Phase 7.1 Autonomous Trading Cycle**: Implemented a "Master Orchestrator" background loop that proactively scans the market, verifies setups via the Risk Manager, and sends "one-tap execution" trade proposals to the user via Telegram DM.
- **Phase 7.2 Council of Models**: 
    - Updated the `Agent` class to support role-specific default providers (Gemini for Researcher, OpenAI for Executor, Claude for Risk Manager) with a unified "One-Brain" fallback for easier user setup.
    - Added `verify_with_council` tool for cross-model consensus and validation of trade plans.
- **Phase 7.3 Strategy Attribution & Pruning**:
    - Added `audit_strategy_performance` to group and analyze PnL/win-rate across different trading styles.
    - Added `prune_wisdom_ledger` which uses the Risk Manager to identify and retire underperforming or redundant rules in the Wisdom Ledger.
- **Agent Tutor Mode**: Introduced a specialized `tutor` role and `tutor_explain_activity` tool to explain technical indicators and AI decision logic to users.
- **ToadAid Integration**: Created `TOADAID.md` and updated `README.md` to align the project architecture with the mission of stillness, wisdom, and clarity.
- **Swing Trading Architect**: Created `get_swing_setup` tool for multi-day trade planning using Fibonacci levels, RSI divergence detection, and volatility-adjusted stops.
- **Pro Indicator Suite**: Added `get_pro_indicators` (SuperTrend, ADX, RSI), `analyze_market_structure` (S/R zones, FVG), and `get_multi_timeframe_signal` for institutional-grade technical analysis.
- **Rug-Pull Auditor**: `audit_token_contract` uses GoPlus Security API to detect honeypots and contract risks.
- **Intelligent Alert System**: `set_smart_alert` allows agents to register background watchers for price, sentiment, and whale moves.
- **Strategy Optimizer**: `optimize_strategy_parameters` automates threshold fine-tuning via grid-search backtesting.
- **Alpha News Summarizer**: `get_daily_alpha` provides aggregated market catalysts from RSS and social feeds.
- **Advanced Execution**: Added `rebalance_portfolio` for automated weight management and `copy_trade_wallet` for whale-tracking simulations.
- **Autonomous Orchestration Tools**: Added `trigger_autonomous_cycle` to manually invoke the full auto-pilot scanning process.

## [1.4.0] - 2026-04-18

### Added
- **Phase 1.1 Model Accuracy Tracker**: Replaced mock data generation with real Trust Wallet price anchoring. Background daemon thread automatically evaluates predictions and retrains the ML model. Active confidence scoring scales signal conviction.
- **Phase 2 Agent Wisdom Store**: Post-mortem loop extracts lessons from closed paper trades. Agent persists rules as "Commandments" in a `wisdom.json` ledger. Context injection provides the LLM with long-term memory across sessions.
- **Phase 3 Infrastructure Expansion**: Multi-agent orchestration with `delegate_task` tool, dividing the AI into `researcher`, `executor`, and `risk_manager` roles. 
- **Advanced WebUI**: Real-time Wisdom Feed component and Chart.js Forecast Accuracy history now displayed on the dashboard.
- **Strategy Management Tools**: `read_strategy`, `write_strategy`, and `calculate_position_size` added to Agent Tools for robust paper-trade journaling and exact sizing calculation.
- **Agent Super-Tools**:
    - **Rug-Pull Auditor**: `audit_token_contract` uses GoPlus Security API to detect honeypots and contract risks.
    - **Intelligent Alert System**: `set_smart_alert` allows agents to register background watchers for price, sentiment, and whale moves.
    - **Strategy Optimizer**: `optimize_strategy_parameters` automates threshold fine-tuning via grid-search backtesting.
    - **Alpha News Summarizer**: `get_daily_alpha` provides aggregated market catalysts from RSS and social feeds.
    - **Pro Indicator Suite**: Added `get_pro_indicators` (SuperTrend, ADX, RSI), `analyze_market_structure` (S/R zones, FVG), and `get_multi_timeframe_signal` for institutional-grade technical analysis.
    - **Swing Trading Architect**: Created `get_swing_setup` tool for multi-day trade planning using Fibonacci levels, RSI divergence detection, and volatility-adjusted stops.
- **Phase 7.1 Autonomous Trading Cycle**: Implemented a "Master Orchestrator" background loop that proactively scans the market, verifies setups via the Risk Manager, and sends "one-tap execution" trade proposals to the user via Telegram DM.
- **Phase 7.2 Council of Models**: 
    - Updated the `Agent` class to support role-specific default providers (Gemini for Researcher, OpenAI for Executor, Claude for Risk Manager).
    - Added `verify_with_council` tool for cross-model consensus and validation of trade plans.
    - Updated `delegate_task` to support optional provider overrides per task.
- **Phase 7.3 Strategy Attribution & Pruning**:
    - Added `audit_strategy_performance` to group and analyze PnL/win-rate across different trading styles.
    - Added `prune_wisdom_ledger` which uses the Risk Manager to identify and retire underperforming or redundant rules in the Wisdom Ledger.
- **Autonomous Orchestration Tools**: Added `trigger_autonomous_cycle` to manually invoke the full auto-pilot scanning process.

### Changed
- Refactored `Agent` class to support constrained system prompts and filtered tool access based on designated `role`.
- Roadmap explicitly maps out new objectives for Phase 4 (Advanced Data), Phase 5 (Execution & Arbitrage), and Phase 6 (Risk Management).

## [1.3.0-alpha] - 2026-04-18

### Added
- Phase 1A Forecasting Ledger MVP with persistent prediction records and post-horizon evaluation.
- Auto-recording for dashboard AI predictions from `/api/ai/predictions/<symbol>`.
- Prediction accuracy API at `/api/ai/prediction-accuracy`.
- Dashboard Forecast Accuracy panel with evaluated/pending counts, direction accuracy, and confidence modifier.
- Telegram Agent Tools flow for manually recording predictions.
- Telegram Agent Tools buttons for prediction accuracy and market regime.

### Changed
- Roadmap now marks Phase 1A Forecasting Ledger MVP complete.

## [1.2.3] - 2026-04-18

### Fixed
- Wallet address QR images now render with the Python standard library, so the Telegram wallet address flow works in the bundled `venv` without requiring Pillow.

### Changed
- Removed the unnecessary Pillow runtime dependency from `requirements.txt`.

## [1.2.2] - 2026-04-18

### Added
- Expanded Telegram menu system for Market, Paper Trading, Wallet, Risk, Live Trading, Agent Tools, and Settings.
- Trust Wallet Agent Kit market-data tools for token search, token price, and quote-only swaps.
- Scannable wallet address QR images in Telegram, rendered from Trust Wallet wallet output.
- Wallet address cache and refresh flow to reduce repeated slow address lookups.
- Trust Wallet price fallback for BTC/ETH/SOL-style price checks when Binance/Coinbase are blocked.

### Fixed
- Dashboard now handles JSON 404 responses such as "Account not found" and shows a create-account path.
- Paper-trade input mode no longer exits after invalid input.
- Paper buy prompts clarify that buy amount is USD, not coin quantity.
- Paper trade success messages now read the backend's top-level order fields and show price, quantity, and total correctly.
- Telegram bot now reads `MODEL_PROVIDER` from `.env` instead of defaulting to Anthropic.

### Changed
- Live Trading menu separates quote-only actions from live execution guidance to reduce accidental on-chain transactions.

## [0.1.0] - 2026-01-20

### Added
- 🤖 Initial Telegram bot implementation
- 💱 Trust Wallet API integration for token trading
- 🔍 Token price checking functionality
- 📊 Token search capability
- 💱 Swap quotes via DEX
- 🛡️ Token security analysis
- 🔄 Conversion tool for token conversions
- 📱 Telegram commands: /start, /help, /price, /search, /quote, /security, /convert
- 🎨 Rich library for beautiful console and Telegram output
- 🔧 Comprehensive error handling
- 📝 Complete documentation (README.md, QUICKSTART.md)
- 🧪 Test script (test_setup.py)
- ⚙️ Setup automation (setup.sh)
- 🔐 Environment variable management (dotenv)
- 📋 Git configuration (.gitignore)

### Technical
- Async/await patterns for non-blocking operations
- Modular architecture with separate API client class
- Type hints for better code quality
- Modular command handlers
- Comprehensive logging and error handling
- Support for Base, Ethereum, Polygon, and BSC networks

### Security
- Credentials stored in .env file
- HMAC signature verification
- API key protection
- Input validation

## Future Enhancements

- [ ] Price alerts and notifications
- [ ] Portfolio tracking
- [ ] Multiple network support with selection
- [ ] Swap execution (not just quotes)
- [ ] Historical price data
- [ ] Token charts and analytics
- [ ] Transaction history
- [ ] User preferences and settings
- [ ] Admin commands for bot management
- [ ] Multiple language support
- [ ] Trading strategies and signals
- [ ] DEX aggregator integration
- [ ] NFT trading features
- [ ] Advanced security scoring
- [ ] Web dashboard
- [ ] Mobile app API
- [ ] Trading bot automation
- [ ] Gas price optimization
- [ ] Slippage protection
- [ ] Limit orders
- [ ] DCA (Dollar Cost Averaging) tools
- [ ] Tax reporting features
- [ ] Multi-signature support
- [ ] Advanced analytics and charts
- [ ] Social trading features

## License

MIT License - See main README for details.

## Disclaimer

⚠️ This project is for educational purposes only. Always DYOR (Do Your Own Research) and trade responsibly.
