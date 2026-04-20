# AI Trading Bot: Future Roadmap (v1.3 & Beyond)

This roadmap outlines the strategic direction for transforming the bot from a static tool into a self-evolving AI Trading System.

## 🧠 Phase 1: The "Forecasting Brain" Evolution
*Objective: Increase the mathematical accuracy of trade signals through continuous learning.*

### 1A Forecasting Ledger MVP ✅
- **Prediction Ledger**: Record symbol, current price, predicted price, confidence, model version, and horizon.
- **Accuracy Evaluator**: Evaluate due predictions against live prices and track direction correctness plus error.
- **Confidence Modifier**: Summarize recent prediction quality into a conservative confidence adjustment.
- **Regime Detection**: Classify markets as trending, ranging, volatile, or unknown from recent candles with ticker fallback.
- **Agent Tools**: `record_price_prediction`, `evaluate_price_predictions`, `get_prediction_accuracy`, and `detect_market_regime`.

### 1.1 Model Accuracy Tracker ✅
- **Feedback Loop**: Implement a system that compares the AI's 24h price predictions against actual market outcomes.
- **Backpropagation logic**: Use the prediction error to adjust model weights or trigger an emergency retraining session if accuracy drops below a threshold.
- **Confidence Scoring**: Add a "Confidence Level" (0-100%) to every AI signal based on historical performance of similar patterns.

### 1.2 Multi-Cycle Training
- **Data Augmentation**: Intentionally feed the model historical "Black Swan" events (flash crashes, parabolic runs) so it recognizes extreme volatility.
- **Regime Detection**: Train the model to identify if the current market is "Ranging" or "Trending" and switch strategies accordingly.

---

## 🦉 Phase 2: The "Agent Wisdom Store"
*Objective: Give the LLM "long-term memory" and the ability to learn from its own successes and failures.*

### 2.1 The "Post-Mortem" Loop ✅
- **Automatic Reflection**: When a trade is closed, the system triggers a hidden "Reflection Prompt" to the Agent.
- **Analysis**: The Agent reviews the indicators, news, and logic it used at the time of entry versus the final P&L.

### 2.2 The "Wisdom Ledger" (`memory/wisdom.json`) ✅
- **Permanent Knowledge**: A JSON-based store of "lessons learned."
- **Example**: `"Never trade low-liquidity meme coins on Base during high network congestion."`
- **Dynamic Rule Generation**: The Agent can write its own "Trading Commandments" to this file.

### 2.3 Context Injection ✅
- **Memory Loading**: At the start of every new session, the Agent reads the `wisdom.json` file.
- **Execution**: The Agent proactively warns the user: *"I noticed you're looking at SOL. My past data shows we often lose money when buying SOL at this RSI level. Should we wait?"*

---

## 🛠️ Phase 3: Infrastructure Expansion
*Objective: Support higher volumes and more complex agentic behaviors.*

### 3.1 Multi-Agent Orchestration ✅
- **The Researcher**: An agent dedicated solely to web-scraping and sentiment analysis.
- **The Executor**: An agent focused strictly on gas-optimization and order execution.
- **The Risk Manager**: An agent that can "veto" trades if they violate the Wisdom Ledger.
- **Delegation**: Main agent delegates tasks cleanly via the `delegate_task` tool based on specialized roles.

### 3.2 Advanced WebUI ✅
- **Real-time Wisdom Feed**: A UI component showing the "Lessons" the AI is currently learning in the dashboard.
- **Accuracy Charts**: Visual tracking of the Forecasting Brain's performance over time using Chart.js inside the AI insights modal.

---

## 🌐 Phase 4: Advanced Data & Social Intelligence
*Objective: Equip the agent with multi-modal inputs and real-time social context.*

### 4.1 Multi-Modal Chart Analysis ✅
- **Vision Integration**: Give the Researcher agent the ability to take screenshots of live TradingView charts and use LLM vision models (e.g., GPT-4o, Gemini 1.5 Pro) to identify complex technical patterns like Elliott Waves and Head & Shoulders.

### 4.2 Real-Time Sentiment Streams ✅
- **The "Hype" Oracle**: Integrate X (Twitter) API, Reddit (r/CryptoCurrency), and news feeds into a background worker.
- **NLP Scoring**: Stream mentions of portfolio assets, score them using a local fast NLP model, and alert the Risk Manager of sudden FUD or Hype before price action reflects it.

### 4.3 Pro Indicator Suite ✅
- **Advanced TA**: Integrated `pandas_ta` for industrial-grade technical analysis.
- **Market Structure**: Automated detection of Support/Resistance zones and Fair Value Gaps (FVG).
- **Multi-Timeframe Analysis**: "Triple Screen" confirmation across 1h, 4h, and 1d timeframes to ensure trade alignment with institutional trends.

### 4.4 Swing Trading Architect ✅
- **Setup Generation**: Master tool for multi-day planning using Fibonacci 'Golden Pocket' retracements.
- **Divergence Detection**: Automated RSI divergence scanning to identify trend reversals.
- **Risk Architect**: Built-in ATR-based volatility stops and reward-to-risk ratio calculation.

---

## ⚡ Phase 5: Execution & Arbitrage
*Objective: Automate portfolio management and mirror highly profitable on-chain entities.*

### 5.1 Automated Portfolio Rebalancing ✅
- **The Rebalancer Agent**: Define target asset allocations (e.g., 50% BTC, 30% ETH, 20% SOL). The agent calculates drift and automatically executes routing swaps via Trust Wallet / DEX aggregators to restore target weights during high volatility.

### 5.2 Copy Trading & Wallet Stalking ✅
- **Whale Tracking**: Expand the smart money tools to actively track known highly profitable wallets.
- **Mirroring**: Instantly trigger an analysis prompt to the Researcher if a tracked whale executes a massive DEX swap, allowing the bot to automatically mirror the trade.

### 5.3 MEV & Arbitrage Defense ✅
- **Private Mempools**: Implement advanced transaction signing that actively utilizes private RPC endpoints (like Flashbots) for EVM trades, eliminating front-running and sandwich attacks on live swaps.
- **Slippage Control**: Enforce strict slippage limits and MEV protection requirements at the tool level.

---

## 🛡️ Phase 6: Institutional Risk Management
*Objective: Implement fail-safes and dynamic strategy testing to protect capital.*

### 6.1 Walk-Forward Optimization ✅
- **Dynamic Backtesting**: Enhance the backtest tool to perform walk-forward optimization (train on 3 months, test on 1 month, adjust, repeat) to empirically prove the strategy survives shifting market regimes.

### 6.2 Dynamic Drawdown Halts ✅
- **Circuit Breakers**: Implement a hard halt at the execution layer. If the portfolio or a specific strategy hits a defined maximum drawdown (e.g., -15% in a week), the system auto-liquidates risky positions into stablecoins and revokes trading permissions until human review.
- **Halt & Resume**: Added `halt_trading` and `resume_trading` tools for manual and automated safety control.

---

## 🤖 Phase 7: The Autonomous Evolution
*Objective: Shift the agent from a reactive tool to a proactive, self-managing trading entity.*

### 7.1 The Autonomous Trading Cycle (Auto-Pilot) ✅
- **Master Orchestrator**: A background loop that runs every 4 hours to aggregate alpha, scan for setups, and propose trades to the user via Telegram DM.
- **Human-in-the-Loop Execution**: Proactive trade proposals that require a single-click "EXECUTE" confirmation from the user.
- **Verification**: Built-in Risk Manager verification against the Wisdom Ledger before any proposal is sent.

### 7.2 Council of Models (Provider Diversity) ✅
- **Specialized Brains**: Updated the delegation system to assign specific LLM providers to roles (Gemini for Research, OpenAI for Execution, Claude for Risk Management).
- **Consensus Logic**: Implemented the `verify_with_council` tool where one model reviews the output or trade plan of another for multi-brain verification.

### 7.3 Strategy Attribution & Pruning ✅
- **Performance Audit Tool**: Implemented `audit_strategy_performance` to analyze trade history and attribute win-rates to specific strategies (Swing, Copy-Trade, etc.).
- **Self-Pruning Wisdom**: Implemented `prune_wisdom_ledger`, allowing the agent to statistically correlate "Commandments" with PnL and retire rules that no longer serve the portfolio.

---

## 🚀 Phase 8: Alpha Optimization & Institutional Edge
*Objective: Transform the bot from a "scanner" into a "competitive predator" with superior execution and insider-tracking.*

### 8.1 Automated "Alpha Wallet" Discovery ✅
- **The Insider Hunter**: Implement a scanner that identifies tokens with >1000% gains in the last 7 days and extracts the "first-in" wallets that profited.
- **Dynamic Whitelisting**: Automatically update the `WhaleTracker` smart-money list with these high-performance wallets.
- **Signal Weighting**: Assign higher conviction scores to trade proposals that align with recent "insider" buy pressure.
- **Agent Tools**: `hunt_insider_wallets`, `verify_alpha_wallet`, `add_alpha_wallet`.

### 8.2 Live Position Management (The "Closer") ✅
- **ATR-Based Trailing Stops**: Automatically move stop-losses up in profit as price advances (volatility-adjusted).
- **Multi-Stage Take Profit**: Implement "Scale-Out" logic (e.g., sell 50% at TP1 to secure risk-free entry, let remainder ride).
- **Breakeven Logic**: Automatically move stop-loss to entry price once the trade hits a defined "Safety Buffer."
- **Agent Integration**: Risk Manager now proactively manages open positions across these multi-stage rules.

### 8.3 MEV Protection & Institutional Execution ✅
- **Solana Jito Integration**: Implemented conditional routing for Solana-based swaps to use Jito Bundles for sandwich protection.
- **EVM Flashbots / Private RPC**: Added `use_private_rpc` support for Ethereum and Base trades to eliminate front-running risk.
- **Priority Fee Optimizer**: Built-in `priority_fee_multiplier` to ensure institutional-grade transaction landing during high network congestion.
- **Agent Integration**: Execution layer now defaults to "Shielded Execution" for all AI-triggered trades.


### 8.4 Narrative & Correlation Guard ✅
- **Narrative Tracker**: Grouped assets into ecosystems (L1, MEME, AI, DEFI) to ensure balanced portfolio distribution.
- **Correlation Filter**: Implemented logic to limit the number of open positions in the same narrative to prevent systemic sector-wide exposure.
- **Exposure Limits**: Added `max_narrative_exposure_pct` to cap total capital allocated to a single crypto narrative.
- **Agent Integration**: Risk Manager now rejects trade proposals that would cause over-exposure to a specific narrative.

---

## 🧠 Phase 9: Multi-Agent Collaborative Intelligence
*Objective: Enhance the inter-agent collaboration layer to enable proactive "Strategy Room" decision-making.*

### 9.1 The "Hype Sniper" (Social Agent)
- **Proactive Scraper**: Develop an agent role that continuously scrapes specialized subreddits and Telegram "Alpha Channels" for early ticker mentions.
- **Sentiment/Volume Correlation**: Automatically flag symbols where social volume is spiking *before* price breakout, alerting the Researcher.

### 9.2 The "Alpha Validator" (The Verifier) ✅
- **Devil's Advocate**: Implemented a mandatory "Critique" step where a specialized Validator agent scrutinizes setups for hidden risks or logical flaws.
- **Consensus Voting**: Implemented "Council Consensus" logic requiring unanimous approval from Risk Manager and Validator before a proposal is sent.
- **Agent Role**: Added the `validator` role with tools for deep analysis of orderbooks and on-chain risk.

### 9.3 The "Macro Watcher"
- **Global Context**: Create an agent that tracks non-crypto data (DXY, BTC/SPX correlation, CPI release dates).
- **Regime Shift**: The Macro Watcher can trigger a "Global Risk-Off" mode, automatically increasing the strictness of the Risk Manager during high-macro-volatility windows.

### 9.4 The "Strategy Optimizer" (Parameter Tuner)
- **Live Tuning**: An agent that continuously runs small-scale walk-forward backtests on the last 7 days of data to suggest real-time adjustments to RSI/ATR/Bollinger thresholds based on the current market regime.

