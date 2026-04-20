# Operation Manual: AI Crypto Trading Agent

This document provides instructions on how to operate the AI Trading Agent through its various interfaces.

## 🚀 Quick Start

### For Linux Users:
1. **Configure Environment**: Copy `.env.example` to `.env` and fill in required credentials.
2. **Setup**: Run `./setup.sh` to install dependencies and initialize the database.
3. **Authenticate an AI provider**: Run `python3 agent.py login`.
4. **Start the full system**: Run `./run_bot.sh` to launch the Flask backend and Telegram bot together.
5. **Interact with Agent**:
   - **Console Chat**: `python3 agent.py chat`
   - **Specific Provider**: `python3 agent.py chat --provider openai-codex`
   - **Telegram Bot Only**: `python3 agent.py bot`
   - **Web Dashboard Only**: `python3 backend/app.py`

### For Windows Users:
1. **Configure Environment**: Copy `.env.example` to `.env` and fill in credentials.
2. **Setup**: Run `setup.bat` to install dependencies and initialize the database.
3. **Authenticate an AI provider**: Run `python agent.py login`.
4. **Start the full system**: Run `run_bot.bat` to launch the Flask backend and Telegram bot together.
5. **Interact with Agent**:
   - **Console Chat**: `python agent.py chat`
   - **Specific Provider**: `python agent.py chat --provider openai-codex`
   - **Telegram Bot Only**: `python agent.py bot`
   - **Web Dashboard Only**: `python backend/app.py`

---

## 🔐 AI Provider Authentication

Run the login wizard before starting the agent:

```bash
# Linux
python3 agent.py login

# Windows
python agent.py login
```

Available login choices:

1. **Google/Gemini Web Auth**: Browser OAuth for Gemini. Use this if you have a configured Google OAuth client.
2. **Gemini API Key**: Opens Google AI Studio and saves `GEMINI_API_KEY`.
3. **OpenAI ChatGPT/Codex Web Auth**: Browser OAuth for `openai-codex`. This is the recommended Codex path.
4. **OpenAI API Key**: Saves `OPENAI_API_KEY` for the standard OpenAI API provider.
5. **Anthropic API Key**: Saves `ANTHROPIC_API_KEY`.
6. **Local Ollama**: Sets `MODEL_PROVIDER=ollama`.

### Provider Commands

```bash
# Use the default provider from .env
python3 agent.py chat

# OpenAI Codex OAuth provider
python3 agent.py chat --provider openai-codex

# Gemini provider
python3 agent.py chat --provider gemini

# Standard OpenAI API-key provider
python3 agent.py chat --provider openai

# Anthropic provider
python3 agent.py chat --provider anthropic

# Ollama provider
python3 agent.py chat --provider ollama
```

Provider model environment variables:

- `MODEL_PROVIDER`: Default provider, for example `openai-codex`.
- `OPENAI_CODEX_MODEL`: Codex CLI model, default `gpt-5.4-mini`.
- `CODEX_BIN`: Codex CLI executable, default `codex`. Required for `openai-codex`.
- `OPENAI_CODEX_WORKDIR`: Directory passed to `codex exec --cd`, default is the project root.
- `OPENAI_CODEX_SANDBOX`: Codex shell sandbox, default `read-only`. Use `workspace-write` for local coding sessions.
- `OPENAI_CODEX_BYPASS_SANDBOX`: If `true`, runs `codex exec --dangerously-bypass-approvals-and-sandbox`. Default `false`.
- `OPENAI_CODEX_TIMEOUT_SECONDS`: Timeout for a nested `codex exec` call, default `900`.
- `OPENAI_MODEL`: Standard OpenAI API model, default `gpt-5.4-mini`.
- `GEMINI_MODEL`: Gemini model, default `gemini-2.5-flash`.
- `OLLAMA_TIMEOUT_SECONDS`: Timeout for local Ollama `/api/chat` calls, default `900`.
- `TELEGRAM_AGENT_TIMEOUT_SECONDS`: Timeout for Telegram AI replies, default `900`.

Provider sessions are isolated, so Gemini history does not leak into Codex history and vice versa.

---

## 💻 Console Interface (REPL)

If Telegram is down or you prefer a terminal, use the console chat:

```bash
# Linux
python3 agent.py chat

# Windows
python agent.py chat
```

In the console, you can talk to the agent naturally. It has access to all trading tools, web search, and technical analysis modules.

---

## 📱 Telegram Bot Usage

Recommended launchers:

```bash
# Linux: starts backend API in the background, then Telegram bot in foreground
./run_bot.sh

# Windows: starts backend API in a minimized window, then Telegram bot
run_bot.bat
```

Start only the bot: `python3 agent.py bot` (Linux) or `python agent.py bot` (Windows).

### Main Features
- **Conversational Trading**: "Buy $500 of BTC", "What's the trend for SOL?"
- **Interactive Menu**: Access dashboards, portfolios, and analysis via buttons.
- **👛 Wallet Management**: 
  - Access via the **Wallet** button in the main menu.
  - View status, public addresses, and on-chain portfolio balances.
  - Supported chains: Base, Ethereum, Solana, BSC, Polygon, and more.
- **On-chain Wallet**: Manage a secure agent wallet via **Trust Wallet Agent Skills**.
  - **Transfer**: Send tokens cross-chain.
  - **Swap**: Execute real on-chain swaps using the Trust Wallet aggregator.
  - **Risk Check**: Run security analysis on any token address before buying.

### 🛡️ Security Note
Real on-chain operations (Transfer/Swap) require you to provide your wallet password to the AI Agent during the conversation. This password is only used locally to sign the transaction via the `twak` CLI.

---

## 📊 Web Dashboard & AI Insights

The Web Dashboard is now password-protected and enhanced with AI features.

- **URL**: `http://localhost:5000`
- **Authentication**: Enter the password defined in your `.env` file (`DASHBOARD_PASSWORD`). Default is `admin123`.
- **Access**: After login, enter your Telegram ID to view your customized dashboard.

### 🔮 AI & Machine Learning Features
- **Price Forecasting**: Click "Analyze AI" next to any holding to see a 24-hour price prediction generated by our Gradient Boosting models.
- **Technical Analysis**: View deep-dive insights including RSI, volatility trends, and primary market structure analysis.
- **Smart Signals**: The AI provides specific BUY/SELL/HOLD recommendations based on expected returns and technical indicators.

---

## 🛠️ Maintenance & Developer Tools

### Shared Coding Workspace

The project includes a writable collaboration folder at `workspace/`.

Use it when running an AI coding agent beside the project:

```bash
cd trading-bot
codex
```

Recommended workspace paths:

- `workspace/agent_memory/`: Local agent work memory and handoff notes.
- `workspace/scratch/`: Temporary experiments and generated local outputs.
- `workspace/tasks/`: Task briefs and review checklists that are safe to keep.

Keep source edits in the normal project files. Do not store API keys, OAuth tokens, wallet secrets, or other credentials in `workspace/`. Private files created in `workspace/agent_memory/` and `workspace/scratch/` are ignored by default.

For a local Codex-backed coding session, set:

```bash
OPENAI_CODEX_WORKDIR=/path/to/trading-bot
OPENAI_CODEX_SANDBOX=workspace-write
OPENAI_CODEX_BYPASS_SANDBOX=false
```

If your machine blocks nested Codex sandboxing with a `bwrap` error, the last-resort local-only setting is `OPENAI_CODEX_BYPASS_SANDBOX=true`. Only use that on a trusted machine and trusted Telegram bot, because it lets Codex run commands without filesystem sandbox protection.

### Manual Command Bot
If you prefer a bot that uses explicit slash commands instead of AI chat:
```bash
python3 agent_bot_manual.py
```

### Seeding Test Data
Populate the dashboard with sample data:
```bash
python3 scripts/seed_test_data.py
```

### Packaging for Deployment
To create a clean installation package for another machine:
```bash
./scripts/package.sh
```
This generates `releases/trading-bot-v1.3.0-alpha.tar.gz`.

Release checklist:

1. Run `venv/bin/python -m pip check`.
2. Run `venv/bin/python -m pytest tests/test_web_auth.py`.
3. Smoke-test providers:
   - `python3 agent.py chat --provider openai-codex --session release-codex`
   - `python3 agent.py chat --provider gemini --session release-gemini`
4. Run `./scripts/package.sh`.
5. Confirm the archive exists in `releases/`.

---

## 🔌 Troubleshooting

- **API 404 Errors**: The system automatically enters **Mock Mode** if keys are missing or endpoints are down.
- **Database Reset**: `rm crypto_agent.db && python3 init_db.py`
- **Provider Confusion**: Run with a provider-specific fresh session, for example `python3 agent.py chat --provider gemini --session test-gemini`.
- **Google OAuth Scope Errors**: Use the login wizard again after updating code, or choose **Gemini API Key**.
- **Codex OAuth Token Missing**: Run `python3 agent.py login` and choose **OpenAI ChatGPT/Codex Web Auth**.
- **Logs**:
  - `agent.log`: AI Agent operations
  - `server.log`: Flask backend logs
  - `telegram_bot.log`: Telegram interface logs
