# AI Trading Bot: Features & Capabilities Manifest

This document serves as the authoritative source of truth for the project's current feature set, tool integrations, and architectural components.

## 🤖 Core AI Agent
- **Cognitive Architecture**: Modular "Agent Loop" supporting multiple LLM providers (Anthropic, OpenAI, Gemini, Ollama).
- **Persistent Memory**: Session-based history stored in `~/.agent/sessions/` with the ability to resume conversations.
- **Tool-Calling Engine**: Dynamic tool discovery and execution system.
- **Context Awareness**: Aware of user-specific IDs (Telegram ID) for personalized data retrieval.

## 📱 Telegram Interface (v1.3.0-alpha)
- **Hybrid Interaction**: Supports both free-form AI chat and structured button-based menus.
- **Expanded Menu System**: Market, Paper Trading, Wallet, Risk, Live Trading, Agent Tools, and Settings menus.
- **Main Dashboard**: Real-time equity, realized/unrealized P&L, win-rate statistics, and account-not-found handling.
- **Portfolio Management**: View active positions, entry prices, and current market value.
- **Quick Trading**: Dedicated input modes for paper buy/sell with symbol/amount parsing and clear USD-vs-quantity messaging.
- **Wallet Portal**: Dedicated menu for wallet status, cached addresses, balances, gas balances, Trust Wallet prices, swap quotes, and token risk checks.
- **Scannable Wallet QRs**: Wallet addresses are rendered as Telegram image QR codes instead of terminal text blocks.
- **Forecasting Brain Controls**: Agent Tools menu can record predictions, evaluate accuracy, and detect market regime.
- **Security**: Password-protected execution for sensitive on-chain operations.

## 💰 Trading & Execution
- **Paper Trading Engine**: Full simulation environment with in-memory state and database persistence.
- **Real-time Pricing**: Aggregated data from Binance and Coinbase APIs with Trust Wallet Agent Kit fallback for blocked sources.
- **Order Management**: Support for Market Buy (Quantity or USD amount) and Market Sell orders.
- **Trade History**: Automated logging of all trades (Simulated and Real).

## 👛 Trust Wallet Agent Skills Integration
- **Multichain Support**: Wallet management for Base, Ethereum, Solana, BSC, Polygon, etc.
- **Market Data Tools**: Registered agent tools for Trust Wallet token search, token prices, and quote-only swaps.
- **On-chain Operations**:
    - **Wallet Creation/Import**: Securely generate or recover wallets via `twak` CLI.
    - **Transfers**: Send native tokens and ERC-20 assets across chains.
    - **Swaps**: DEX aggregation for optimal routing and execution.
    - **Risk Analysis**: On-chain security checks (honeypot, rug pull detection) via Trust Wallet's risk engine.

## 📊 Analytics & Insights
- **Market Analysis**: AI-driven summaries of top cryptocurrency trends and volatility.
- **Risk Management**: Portfolio concentration checks and risk limit monitoring.
- **Price Forecasting**: Gradient Boosting models for 24h price predictions with persistent Phase 1A accuracy ledger.
- **Forecast Accuracy**: Dashboard prediction modal shows evaluated/pending counts, direction accuracy, and confidence modifier.
- **Technical Indicators**: Integration of RSI, Moving Averages, and Volatility metrics via `ta` library.

## ⚙️ Backend & Infrastructure
- **API Layer**: Flask-based REST API providing data to both Telegram and Web interfaces.
- **Database**: SQLite with SQLAlchemy ORM for user profiles, portfolios, and trade history.
- **Background Workers**: Celery/Redis architecture for scheduled market data fetching and alerts.
- **Systemd Integration**: Pre-configured service templates for production deployment on Linux.
- **Web Dashboard**: (v1.1.0/Legacy) Mobile-responsive HTML5/JS dashboard for visual monitoring.

## 🛠️ Tooling & DevOps
- **`agent.py`**: Unified CLI entry point for Chat and Bot modes.
- **`setup.sh` / `setup.bat`**: Cross-platform environment initialization.
- **`install_service.sh`**: Automated systemd service generator for Linux.
- **`package.sh`**: Distribution script generating `.tar.gz` and `.zip` releases.
- **Testing Suite**: Unit and integration tests for API and Telegram logic.
