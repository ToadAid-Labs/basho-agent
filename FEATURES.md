# AI Trading Bot: Features & Capabilities Manifest

This document serves as the authoritative source of truth for the project's current feature set, tool integrations, and architectural components.

Related operator docs:
- `docs/OPERATOR_FEATURES.md`
- `docs/USER_CAPABILITIES.md`
- `docs/OPERATOR_CHECKLIST.md`
- `ROADMAP.md` (Future Vision)

## 🧠 Predator-Grade AI Intelligence (v2.0)
- **Neural Signal Synthesizer**: A self-correcting neural layer that learns from historical P&L to generate a "Conviction Score" for every trade.
- **Neural Cross-Check**: The agent automatically vetoes signals that match historical "failed clusters" (e.g., high volatility + bearish sentiment).
- **Consensus Council**: Multi-brain verification requiring unanimous approval from specialized "Researcher," "Risk Manager," and "Validator" agents.

## ⚡ Predator Tier Tools (Institutional Edge)
- **Order Book Imbalance (OBI) Scanner**: Real-time analysis of Binance/Coinbase limit order books to detect massive buy/sell "walls" and hidden institutional pressure.
- **Statistical Arbitrage (Pair Trading)**: Real-time Z-Score calculation for correlated pairs (e.g., ETH/SOL). Triggers mean-reversion trades when spreads hit statistical extremes.
- **On-Chain Graph Intelligence**: Detects "Cluster Buys" where multiple smart-money wallets move into the same asset simultaneously—unmasking coordinated insider rotations.
- **RL-Policy Agent**: Reinforcement Learning simulation engine that discover non-obvious profit patterns using millions of historical episodes.

## 🤖 Core AI Agent & Orchestration
- **Cognitive Architecture**: Modular "Agent Loop" supporting multiple LLM providers (Anthropic, OpenAI, Gemini, Ollama).
- **Role-Based Specialization**: Specialized prompts and toolsets for Researchers, Analysts, and Executors.
- **Persistent Memory**: Session-based history and long-term "Wisdom Ledger" where the agent writes its own "Trading Commandments."
- **Context Awareness**: Deeply aware of user-specific portfolio state, risk limits, and Telegram ID.

## 📱 Telegram Interface (v1.3.0)
- **Hybrid Interaction**: Supports both free-form AI chat and structured button-based menus.
- **Predator Dashboard**: Real-time equity, realized/unrealized P&L, win-rate statistics, and "Alpha Clusters" notifications.
- **Forecasting Brain Controls**: Dedicated menu to record predictions, evaluate accuracy, and detect market regime.
- **Scannable Wallet QRs**: On-chain wallet addresses rendered as interactive QR codes.
- **Security**: Password-protected execution for all sensitive on-chain operations.

## 💰 Trading & Execution Layer
- **Multi-Regime Strategies**: Adaptive logic that swaps between Trend-Following and Mean-Reversion based on ADX/ATR regime detection.
- **Shielded Execution**: Default routing through MEV-protected RPCs (Flashbots, Jito) to eliminate front-running and sandwich attacks.
- **Advanced Position Management**: ATR-based trailing stops, multi-stage take-profits, and automatic "Breakeven" logic.
- **Trust Wallet Integration**: Seamless cross-chain swaps and transfers across Base, Ethereum, Solana, and BSC.

## 📊 Analytics & Insights
- **Macro Watcher**: Tracks global context (DXY, SPX, BTC Correlation) to determine global Risk-On/Risk-Off regimes.
- **Market Structure Detection**: Automated detection of Support/Resistance zones, Order Blocks, and Fair Value Gaps (FVG).
- **Pro Indicator Suite**: Integration of SuperTrend, ADX, RSI Divergence, and Fibonacci "Golden Pocket" zones.
- **Data Augmentation**: Models trained on "Black Swan" event data to recognize extreme volatility before breakouts.

## ⚙️ Backend & Infrastructure
- **Self-Optimizing Workers**: Background loops that periodically run grid-search to tune strategy parameters for current market conditions.
- **Accuracy Tracker**: Persistent ledger evaluating every AI prediction against realized price action.
- **Modular API Layer**: Flask-based REST API providing data to Telegram, Web, and CLI interfaces.
- **Database**: High-performance SQLite/SQLAlchemy schema for tracking users, trades, and neural learnings.
