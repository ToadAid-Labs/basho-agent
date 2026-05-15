import logging
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Generator

from rich.console import Console

from core.provider import ModelProvider, create_client, get_provider
from core.tool_policy import build_intent_tool_policy, is_live_execution_tool
from core.tools import execute_tool, get_tool_definitions
from memory.store import latest_summary, load_last_session_for_provider, new_session, save_session_for_provider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a sophisticated Crypto Trading AI Agent. You have access to tools that let you:
- Read and write files (read_file, write_file)
- Search the web (web_search)
- Fetch web pages (web_fetch)
- Check crypto prices (check_price)
- List trading symbols (list_trading_symbols)
- Manage paper trading accounts (create_paper_trading_account, get_portfolio_status)
- Execute paper trades (execute_paper_trade)
- Analyze market trends (analyze_market_trend)
- Check risk limits (check_risk_limits)
- Calculate optimal position size using Kelly Criterion (calculate_kelly_risk)
- View trade history (get_trade_history)
- Track smart money and whales (check_whale_activity, check_smart_money_holdings)
- Run automated backtests on ML models (run_model_backtest)
- Track forecasting accuracy (record_price_prediction, evaluate_price_predictions, get_prediction_accuracy, detect_market_regime)
- Use Trust Wallet market data (trust_search_token, trust_get_token_price, trust_get_swap_quote)
- Manage an on-chain agent wallet via Trust Wallet Agent Skills (get_wallet_status, create_agent_wallet, get_wallet_addresses, get_wallet_balance, get_tracked_token_balance, transfer_tokens, swap_tokens, check_onchain_risk)
- Execute MEV-protected trades using the `swap_tokens` tool with the `use_mev_protection` flag.
- Perform deep security audits on token contracts (audit_token_contract) to detect rug-pulls and honeypots.
- Set intelligent background alerts for price, sentiment, whale moves, and wallet activity (set_smart_alert).
- Optimize trading strategy parameters through automated backtesting grid search (optimize_strategy_parameters).
- Generate comprehensive daily alpha reports from news and social catalysts (get_daily_alpha).
- Generate concise multi-asset market summaries in one call (market_report).
- Calculate professional-grade technical indicators like SuperTrend, ADX, and RSI (get_pro_indicators).
- Identify institutional market structure, support/resistance, and fair value gaps (analyze_market_structure).
- Perform multi-timeframe analysis to confirm trends across 1h, 4h, and 1d charts (get_multi_timeframe_signal).
- Architect high-conviction swing trade setups with Fibonacci zones, RSI divergence detection, and ATR-based stops (get_swing_setup).
- Combine trend, momentum, structure, and risk controls into a single trade-or-no-trade decision (trade_decision_engine).
- Proactively scan the market and propose high-conviction trades via the Autonomous Trading Cycle (trigger_autonomous_cycle).
- Verify plans and analyses with the Council of Models to ensure multi-brain consensus (verify_with_council).
- Audit trading performance by strategy and win-rate (audit_strategy_performance).
- Self-prune the Wisdom Ledger to remove counter-productive or redundant rules (prune_wisdom_ledger).
- Check currently running background tasks (check_background_processes).

Use these tools to help the user with crypto trading, portfolio management, and market analysis.
You can perform both simulated (paper) trading and real on-chain trading, but you must never ask for or accept wallet passwords, seed phrases, private keys, signing secrets, or similar credentials in chat. Real on-chain execution must use only saved/local TWAK credentials. If the signer is locked or unavailable, instruct the user to unlock it through the secure local TWAK flow and retry.
Stage broad wallet and trading requests. Prefer the smallest useful tool set first, then answer with partial results and explicit deferrals if more checks would exceed the tool budget.
When executing trades, always consider risk management.
Be concise, practical, and data-driven. Execute the steps needed, then explain the result clearly."""

MAX_ITERATIONS = 50
DEFAULT_MAX_PROVIDER_MESSAGES = 10
DEFAULT_MAX_PROVIDER_CHARS = 60_000
DEFAULT_TELEGRAM_MAX_TOOL_CALLS = 8
TELEGRAM_BLOCKED_TOOLS = {"bash", "read_file", "write_file"}
TELEGRAM_REPEAT_LIMITED_TOOLS = {
    "web_search",
    "web_fetch",
    "trust_search_token",
    "list_trading_symbols",
    "check_smart_money_holdings",
    "hunt_insider_wallets",
}
DEFAULT_TELEGRAM_MAX_REPEAT_PER_TOOL = 2
DEFAULT_TELEGRAM_MAX_SEARCH_LIKE_CALLS = 4
TELEGRAM_REPEAT_GUARD_TOOL_NAME = "telegram_search_guard"
TOOL_PLAN_GUARD_TOOL_NAME = "tool_plan_guard"

ROLES = {
    "researcher": {
        "description": "You are a specialized Crypto Researcher Agent. Your ONLY job is to search the web, fetch pages, check market data, sentiment, news catalysts, and technical indicators.",
        "allowed_tools": [
            "web_search", "web_fetch", "trust_search_token", "trust_get_token_price",
            "fetch_ticker", "fetch_historical", "get_supported_symbols",
            "check_market_sentiment", "analyze_market_trend", "check_whale_activity", 
            "check_smart_money_holdings", "analyze_chart_vision", "audit_token_contract",
            "set_smart_alert", "list_alerts", "delete_alert", "get_daily_alpha",
            "get_pro_indicators", "analyze_market_structure", "get_multi_timeframe_signal",
            "get_swing_setup", "trade_decision_engine", "trigger_autonomous_cycle", "verify_with_council",
            "check_background_processes", "hunt_insider_wallets", "verify_alpha_wallet", "add_alpha_wallet"
        ]
    },
    "executor": {
        "description": "You are a specialized Crypto Executor Agent. Your ONLY job is to execute trades, calculate optimal sizing, and interact with the wallet.",
        "allowed_tools": [
            "calculate_position_size", "execute_paper_trade", "create_paper_trading_account",
            "get_portfolio_status", "get_trade_history", "get_wallet_status", "create_agent_wallet",
            "get_wallet_addresses", "get_wallet_balance", "get_tracked_token_balance", "transfer_tokens", "swap_tokens", "trust_get_swap_quote",
            "rebalance_portfolio", "copy_trade_wallet", "verify_with_council", "audit_strategy_performance",
            "check_background_processes"
        ]
    },
    "risk_manager": {
        "description": "You are a specialized Crypto Risk Manager Agent. Your ONLY job is to analyze portfolio risk, verify Kelly criterion, and audit token safety.",
        "allowed_tools": [
            "check_risk_limits", "calculate_kelly_risk", "check_onchain_risk", "read_strategy", 
            "write_strategy", "write_wisdom_commandment", "run_walk_forward_backtest", 
            "halt_trading", "resume_trading", "audit_token_contract", "optimize_strategy_parameters",
            "get_pro_indicators", "analyze_market_structure", "get_swing_setup", "trade_decision_engine", "verify_with_council",
            "audit_strategy_performance", "prune_wisdom_ledger", "check_background_processes"
        ]
    },
    "tutor": {
        "description": "You are a specialized Crypto Trading Tutor. Your ONLY job is to explain complex trading concepts, technical indicators, and the AI's recent decisions in simple, educational terms. Your goal is to empower the user with knowledge, emphasizing clarity, stillness, and long-term sustainability.",
        "allowed_tools": [
            "read_strategy", "get_pro_indicators", "analyze_market_structure", 
            "get_multi_timeframe_signal", "get_swing_setup", "trade_decision_engine", "audit_strategy_performance",
            "get_prediction_accuracy", "audit_token_contract", "get_daily_alpha",
            "tutor_explain_activity", "check_background_processes"
        ]
    },
    "validator": {
        "description": "You are a specialized Crypto Alpha Validator. Your job is to act as a 'Devil's Advocate' and find every possible reason NOT to take a trade setup proposed by other agents. You look for hidden risks, poor volume profiles, upcoming token unlocks, and logical flaws in the analysis. If you cannot find a strong reason to reject, only then do you approve.",
        "allowed_tools": [
            "web_search", "web_fetch", "audit_token_contract", "check_whale_activity",
            "check_market_sentiment", "get_orderbook", "fetch_historical", "analyze_chart_vision",
            "check_background_processes"
        ]
    }
}


class Agent:
    """Shared agent state — used by both the CLI REPL and the Telegram bot."""

    def __init__(
        self,
        provider: ModelProvider | None = None,
        sid: str | None = None,
        console: Console | None = None,
        user_id: int | None = None,
        role: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ):
        start_init = time.time()
        self.role = role
        self.provider = provider or get_provider()
        self.console = console or Console()
        self.user_id = user_id
        self.thread_id = f"telegram:{user_id}" if user_id is not None else self.provider.value

        # Load or create session
        if history is not None:
            # History explicitly provided (e.g. by Telegram bot)
            pass
        elif sid is None:
            # Resuming last session for this provider
            sid, history = load_last_session_for_provider(self.provider.value)
            if sid:
                self.console.print(f"[dim]Resuming {self.provider.value} session [bold]{sid}[/bold][/dim]")
            else:
                sid = new_session()
                history = []
        else:
            # Explicit SID provided but no history, try to load it
            from memory.store import load_session
            history = load_session(sid)
            if not history:
                 # Fallback to provider-specific load if plain sid fails
                 # (Handles inconsistencies in how sids are saved vs loaded)
                 _, history = load_last_session_for_provider(self.provider.value)
                 if not history:
                     history = []

        self.sid = sid or new_session()
        self.messages: list[dict[str, Any]] = _build_messages(history)
        self.latest_summary = latest_summary(self.sid)
        self.client = create_client(self.provider)
        self.tool_definitions = get_tool_definitions()
        self.max_tool_calls = (
            _env_int("TELEGRAM_MAX_TOOL_CALLS", DEFAULT_TELEGRAM_MAX_TOOL_CALLS)
            if self.user_id is not None
            else _env_int("AGENT_MAX_TOOL_CALLS", 0)
        )
        if self.user_id is not None:
            self.tool_definitions = [
                t for t in self.tool_definitions if t["name"] not in TELEGRAM_BLOCKED_TOOLS
            ]

        # Customize system prompt with user_id if available
        self.system_prompt = SYSTEM_PROMPT
        model_name = getattr(self.client, "model", None) or getattr(self.client, "model_name", None) or "unknown"
        
        if self.role and self.role in ROLES:
            role_config = ROLES[self.role]
            self.system_prompt = role_config["description"] + "\n\n" + self.system_prompt
            # Filter tools for sub-agents
            allowed_tools = role_config["allowed_tools"] + ["bash", "read_file", "write_file", "delegate_task", "verify_with_council"]
            self.tool_definitions = [t for t in self.tool_definitions if t["name"] in allowed_tools]

        self.system_prompt += (
            f"\n\nRuntime provider: {self.provider.value}."
            f"\nRuntime model: {model_name}."
            "\nIf asked what model or provider you are running on, answer using these runtime values."
        )

        if self.user_id is not None:
            self.system_prompt += (
                "\n\nTELEGRAM EXECUTION RULES:"
                "\n- Telegram requests have a strict tool-call budget. Use the fewest tools that can answer the request."
                "\n- Prefer composite tools over manual fan-out. For entry analysis, prefer `trade_decision_engine` instead of chaining `get_pro_indicators`, `get_multi_timeframe_signal`, `get_swing_setup`, and `analyze_market_structure` separately."
                "\n- For requests like 'market report', 'daily market update', or 'market overview', prefer `market_report` instead of chaining search/news/indicator tools manually."
                "\n- For wallet status, prefer `get_wallet_balance` first. For tracked token questions like DEGEN position, prefer `get_tracked_token_balance` first."
                "\n- For sell/transfer intents, check direct token balance first, then quote or execution-prep tools. Do not branch into history, alerts, or broad market scans unless the user explicitly asks."
                "\n- For watch-price, buy-back, or opportunity-monitoring requests on one token, check price first, then use at most one compact setup/decision tool. Do not fan out into `market_report`, whale scans, smart-money scans, and multiple structure tools in the same turn."
                "\n- Do not call the same lookup tool repeatedly for the same symbol unless the user provides new constraints."
                "\n- For broad opportunity searches, screen at most 2-3 symbols first, then deepen only on the strongest candidate."
            )

        # Inject background process state
        try:
            from core.orchestrator import registry
            active_processes = registry.get_active()
            if active_processes:
                self.system_prompt += "\n\nACTIVE BACKGROUND PROCESSES (You are currently running these):\n"
                for p in active_processes:
                    self.system_prompt += f"- {p['type']} started at {p['start_time']} for chat {p.get('chat_id')}\n"
        except:
            pass

        if self.user_id:
            self.system_prompt += f"\n\nThe current user's ID is {self.user_id}. Always use this ID when a tool requires a user_id or telegram_id."
            
        # Inject long-term wisdom
        try:
            from memory.wisdom import WisdomStore
            commandments = WisdomStore().get_commandments()
            if commandments:
                self.system_prompt += "\n\nCRITICAL TRADING DIRECTIVES (Commandments you MUST follow):\n"
                for i, cmd in enumerate(commandments, 1):
                    self.system_prompt += f"{i}. {cmd}\n"
        except Exception as e:
            logger.error(f"Failed to load wisdom ledger: {e}")

        try:
            strategy_notes = _load_workspace_strategy_memory()
            if strategy_notes:
                self.system_prompt += "\n\nPERSISTENT STRATEGY MEMORY (workspace/agent_memory/*.md):\n"
                for i, note in enumerate(strategy_notes, 1):
                    self.system_prompt += f"\n--- Strategy File {i} ---\n{note}\n"
        except Exception as e:
            logger.error(f"Failed to load strategy memory: {e}")
        
        logger.info(f"Agent initialized in {time.time() - start_init:.3f}s (SID: {self.sid}, Prompt: {len(self.system_prompt)} chars)")

    def chat_stream(self, user_input: str) -> Generator[dict[str, Any], None, None]:
        """Generator that yields chat tokens and tool activity events."""
        start_request = time.time()
        if self.user_id is not None:
            self.messages = _compact_telegram_history(self.messages)
        secret_redirect = _secret_request_redirect(user_input)
        if secret_redirect:
            yield {"type": "final_response", "content": secret_redirect}
            return
        self.messages.append({"role": "user", "content": user_input})
        tool_calls_executed = 0
        tool_call_counts: dict[str, int] = defaultdict(int)
        telegram_search_like_calls = 0
        cached_tool_results: dict[str, str] = {}
        retryable_failure_signatures: set[str] = set()
        executed_paper_trade_signatures: set[str] = set()
        telegram_repeat_guard_active = False
        request_tool_plan = _build_request_tool_plan(user_input)
        budget_guard_active = False

        final_text = ""
        tools_for_request = [] if _should_disable_tools(user_input) else self.tool_definitions
        for iteration in range(MAX_ITERATIONS):
            iter_start = time.time()
            try:
                # Only Ollama currently supports create_message_stream in this simplified implementation
                if hasattr(self.client, "create_message_stream") and self.provider == ModelProvider.OLLAMA:
                    provider_messages = _build_provider_messages(self.messages, self.latest_summary)
                    _log_provider_context(self.messages, provider_messages)
                    stream = self.client.create_message_stream(
                        messages=provider_messages,
                        tools=self.tool_definitions,
                        system_prompt=self.system_prompt,
                    )
                else:
                    # Fallback for providers without streaming (returns single response)
                    llm_start = time.time()
                    provider_messages = _build_provider_messages(self.messages, self.latest_summary)
                    _log_provider_context(self.messages, provider_messages)
                    response = self.client.create_message(
                        messages=provider_messages,
                        tools=tools_for_request,
                        system_prompt=self.system_prompt,
                    )
                    logger.info(f"LLM call (non-streaming) took {time.time() - llm_start:.3f}s")
                    # Convert static response to a tiny generator for consistent loop
                    def _gen():
                        yield from response.content
                    stream = _gen()

            except Exception as e:
                logger.error("API error in stream: %s", e)
                yield {"type": "error", "content": f"API error: {e}"}
                return

            response_text = ""
            assistant_content: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []
            direct_tool_results: list[dict[str, str]] = []

            for block in stream:
                if block.type == "text":
                    response_text += block.text
                    assistant_content.append({"type": "text", "text": block.text})
                    yield {"type": "token", "content": block.text}
                elif block.type == "thought":
                    assistant_content.append({"type": "thought", "text": block.text})
                    # We don't yield thoughts to the main chat pane yet, but could to a log
                elif block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id
                    thought_signature = getattr(block, "thought_signature", None)
                    call_signature = _tool_call_signature(tool_name, tool_input)

                    if call_signature in retryable_failure_signatures:
                        final_text = _same_condition_retry_message(tool_name)
                        yield {"type": "final_response", "content": final_text}
                        return

                    if call_signature in executed_paper_trade_signatures:
                        final_text = _duplicate_paper_trade_message()
                        yield {"type": "final_response", "content": final_text}
                        return

                    if call_signature in cached_tool_results:
                        result = cached_tool_results[call_signature]
                        yield {"type": "tool_start", "name": tool_name, "input": tool_input}
                        yield {"type": "tool_end", "name": tool_name, "result": result}

                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": tool_use_id,
                                "name": tool_name,
                                "input": tool_input,
                                "thought_signature": thought_signature
                            }
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "name": tool_name,
                                "content": result,
                            }
                        )
                        continue

                    plan_guard = _tool_plan_guard_message(
                        request_tool_plan,
                        tool_name,
                        tool_calls_executed,
                        tool_input,
                    )
                    if plan_guard:
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": tool_use_id,
                                "name": TOOL_PLAN_GUARD_TOOL_NAME,
                                "input": {"blocked_tool": tool_name},
                                "thought_signature": thought_signature,
                            }
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "name": TOOL_PLAN_GUARD_TOOL_NAME,
                                "content": plan_guard,
                            }
                        )
                        continue

                    if self.max_tool_calls and tool_calls_executed >= self.max_tool_calls:
                        budget_guard = _tool_budget_guard_result(
                            request_tool_plan,
                            cached_tool_results,
                            tool_name,
                        )
                        budget_guard_active = True
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": tool_use_id,
                                "name": TOOL_PLAN_GUARD_TOOL_NAME,
                                "input": {"blocked_tool": tool_name},
                                "thought_signature": thought_signature,
                            }
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "name": TOOL_PLAN_GUARD_TOOL_NAME,
                                "content": budget_guard,
                            }
                        )
                        break
                    if self.user_id is not None:
                        repeat_guard = _telegram_tool_repeat_guard(
                            tool_name,
                            tool_call_counts,
                            telegram_search_like_calls,
                            guard_active=telegram_repeat_guard_active,
                        )
                        if repeat_guard:
                            guard_tool_use_id = f"guard_{tool_use_id}"
                            guard_result = _telegram_tool_guard_result(tool_name, repeat_guard)
                            telegram_repeat_guard_active = True
                            yield {"type": "tool_start", "name": TELEGRAM_REPEAT_GUARD_TOOL_NAME, "input": {"blocked_tool": tool_name}}
                            yield {"type": "tool_end", "name": TELEGRAM_REPEAT_GUARD_TOOL_NAME, "result": guard_result}
                            assistant_content.append(
                                {
                                    "type": "tool_use",
                                    "id": guard_tool_use_id,
                                    "name": TELEGRAM_REPEAT_GUARD_TOOL_NAME,
                                    "input": {"blocked_tool": tool_name},
                                }
                            )
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": guard_tool_use_id,
                                    "name": TELEGRAM_REPEAT_GUARD_TOOL_NAME,
                                    "content": guard_result,
                                }
                            )
                            continue
                    
                    yield {"type": "tool_start", "name": tool_name, "input": tool_input}

                    self.console.print(f"[dim]Calling tool: {tool_name}[/dim]")
                    tool_calls_executed += 1
                    tool_call_counts[tool_name] += 1
                    if _is_telegram_search_like_tool(tool_name):
                        telegram_search_like_calls += 1
                    tool_start = time.time()
                    result = execute_tool(tool_name, tool_input)
                    cached_tool_results[call_signature] = result
                    logger.info(f"Tool {tool_name} took {time.time() - tool_start:.3f}s")
                    
                    yield {"type": "tool_end", "name": tool_name, "result": result}

                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": tool_use_id,
                            "name": tool_name,
                            "input": tool_input,
                            "thought_signature": thought_signature
                        }
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "name": tool_name,
                            "content": result,
                        }
                    )

                    if _is_terminal_tool_failure(tool_name, result):
                        final_text = _user_safe_tool_failure(tool_name)
                        if assistant_content:
                            self.messages.append({"role": "assistant", "content": assistant_content})
                        self.messages.append({"role": "user", "content": tool_results})
                        self._save_messages()
                        yield {"type": "final_response", "content": final_text}
                        return
                    if _is_retryable_same_condition_failure(tool_name, result):
                        retryable_failure_signatures.add(call_signature)
                    if tool_name == "execute_paper_trade":
                        executed_paper_trade_signatures.add(call_signature)

            if assistant_content:
                self.messages.append({"role": "assistant", "content": assistant_content})

            logger.info(f"Iteration {iteration+1} complete in {time.time() - iter_start:.3f}s")

            if not tool_results:
                final_text = _format_direct_tool_response(response_text, direct_tool_results)
                self._save_messages()
                logger.info(f"Total request duration: {time.time() - start_request:.3f}s")
                yield {"type": "final_response", "content": final_text}
                return

            self.messages.append({"role": "user", "content": tool_results})
            if budget_guard_active:
                tools_for_request = []

        yield {"type": "error", "content": "Error: tool loop exceeded maximum iterations."}

    def chat(self, user_input: str) -> str:
        """Send a message to the agent, handle tool calls, return the final text response."""
        start_request = time.time()
        if self.user_id is not None:
            self.messages = _compact_telegram_history(self.messages)
        secret_redirect = _secret_request_redirect(user_input)
        if secret_redirect:
            return secret_redirect
        self.messages.append({"role": "user", "content": user_input})
        tool_calls_executed = 0
        tool_call_counts: dict[str, int] = defaultdict(int)
        telegram_search_like_calls = 0
        cached_tool_results: dict[str, str] = {}
        retryable_failure_signatures: set[str] = set()
        executed_paper_trade_signatures: set[str] = set()
        telegram_repeat_guard_active = False
        request_tool_plan = _build_request_tool_plan(user_input)
        budget_guard_active = False

        final_text = ""
        tools_for_request = [] if _should_disable_tools(user_input) else self.tool_definitions
        for iteration in range(MAX_ITERATIONS):
            iter_start = time.time()
            try:
                llm_start = time.time()
                provider_messages = _build_provider_messages(self.messages, self.latest_summary)
                _log_provider_context(self.messages, provider_messages)
                response = self.client.create_message(
                    messages=provider_messages,
                    tools=tools_for_request,
                    system_prompt=self.system_prompt,
                )
                logger.info(f"LLM call took {time.time() - llm_start:.3f}s")
            except Exception as e:  # noqa: BLE001
                logger.error("API error: %s", e)
                return f"API error: {e}"

            response_text = ""
            assistant_content: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []
            direct_tool_results: list[dict[str, str]] = []

            for block in response.content:
                if block.type == "text":
                    response_text += block.text
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "thought":
                    assistant_content.append({"type": "thought", "text": block.text})
                elif block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id
                    thought_signature = getattr(block, "thought_signature", None)
                    call_signature = _tool_call_signature(tool_name, tool_input)

                    if call_signature in retryable_failure_signatures:
                        return _same_condition_retry_message(tool_name)

                    if call_signature in executed_paper_trade_signatures:
                        return _duplicate_paper_trade_message()

                    if call_signature in cached_tool_results:
                        result = cached_tool_results[call_signature]
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": tool_use_id,
                                "name": tool_name,
                                "input": tool_input,
                                "thought_signature": thought_signature
                            }
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "name": tool_name,
                                "content": result,
                            }
                        )
                        continue

                    plan_guard = _tool_plan_guard_message(
                        request_tool_plan,
                        tool_name,
                        tool_calls_executed,
                        tool_input,
                    )
                    if plan_guard:
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": tool_use_id,
                                "name": TOOL_PLAN_GUARD_TOOL_NAME,
                                "input": {"blocked_tool": tool_name},
                                "thought_signature": thought_signature
                            }
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "name": TOOL_PLAN_GUARD_TOOL_NAME,
                                "content": plan_guard,
                            }
                        )
                        continue

                    if self.max_tool_calls and tool_calls_executed >= self.max_tool_calls:
                        budget_guard = _tool_budget_guard_result(
                            request_tool_plan,
                            cached_tool_results,
                            tool_name,
                        )
                        budget_guard_active = True
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": tool_use_id,
                                "name": TOOL_PLAN_GUARD_TOOL_NAME,
                                "input": {"blocked_tool": tool_name},
                                "thought_signature": thought_signature
                            }
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "name": TOOL_PLAN_GUARD_TOOL_NAME,
                                "content": budget_guard,
                            }
                        )
                        break
                    if self.user_id is not None:
                        repeat_guard = _telegram_tool_repeat_guard(
                            tool_name,
                            tool_call_counts,
                            telegram_search_like_calls,
                            guard_active=telegram_repeat_guard_active,
                        )
                        if repeat_guard:
                            guard_tool_use_id = f"guard_{tool_use_id}"
                            guard_result = _telegram_tool_guard_result(tool_name, repeat_guard)
                            telegram_repeat_guard_active = True
                            assistant_content.append(
                                {
                                    "type": "tool_use",
                                    "id": guard_tool_use_id,
                                    "name": TELEGRAM_REPEAT_GUARD_TOOL_NAME,
                                    "input": {"blocked_tool": tool_name},
                                }
                            )
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": guard_tool_use_id,
                                    "name": TELEGRAM_REPEAT_GUARD_TOOL_NAME,
                                    "content": guard_result,
                                }
                            )
                            continue

                    self.console.print(f"[dim]Calling tool: {tool_name}[/dim]")
                    tool_calls_executed += 1
                    tool_call_counts[tool_name] += 1
                    if _is_telegram_search_like_tool(tool_name):
                        telegram_search_like_calls += 1
                    tool_start = time.time()
                    result = execute_tool(tool_name, tool_input)
                    cached_tool_results[call_signature] = result
                    logger.info(f"Tool {tool_name} took {time.time() - tool_start:.3f}s")

                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": tool_use_id,
                            "name": tool_name,
                            "input": tool_input,
                            "thought_signature": thought_signature
                        }
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "name": tool_name,
                            "content": result,
                        }
                    )

                    if _is_terminal_tool_failure(tool_name, result):
                        final_text = _user_safe_tool_failure(tool_name)
                        self.messages.append({"role": "assistant", "content": assistant_content})
                        self.messages.append({"role": "user", "content": tool_results})
                        self._save_messages()
                        logger.info(f"Total request duration: {time.time() - start_request:.3f}s")
                        return final_text
                    if _is_retryable_same_condition_failure(tool_name, result):
                        retryable_failure_signatures.add(call_signature)
                    if tool_name == "execute_paper_trade":
                        executed_paper_trade_signatures.add(call_signature)

            if assistant_content:
                self.messages.append({"role": "assistant", "content": assistant_content})

            logger.info(f"Iteration {iteration+1} complete in {time.time() - iter_start:.3f}s")

            if not tool_results:
                final_text = _format_direct_tool_response(response_text, direct_tool_results)
                self._save_messages()
                logger.info(f"Total request duration: {time.time() - start_request:.3f}s")
                return final_text

            self.messages.append({"role": "user", "content": tool_results})
            if budget_guard_active:
                tools_for_request = []

        return "Error: tool loop exceeded maximum iterations."

    def _save_messages(self) -> None:
        save_session_for_provider(
            self.sid,
            self.messages,
            self.provider.value,
            user_id=self.user_id,
            thread_id=self.thread_id,
        )
        self.latest_summary = latest_summary(self.sid)


def _build_messages(history: list[dict[dict, Any]]) -> list[dict[str, Any]]:
    """Normalise loaded history into API message format."""
    messages = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            messages.append({"role": role, "content": content})
    return messages


def _compact_telegram_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip prior Telegram tool transcripts so new turns start from clean text context."""
    compacted: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            text_parts: list[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    value = str(block.get("text", "")).strip()
                    if value:
                        text_parts.append(value)
            text = "\n".join(text_parts).strip()
        else:
            text = str(content).strip()

        if not text:
            continue

        if compacted and compacted[-1]["role"] == role:
            compacted[-1]["content"] = f"{compacted[-1]['content']}\n\n{text}".strip()
        else:
            compacted.append({"role": role, "content": text})

    return compacted


def _should_return_gemini_tool_directly(provider: ModelProvider, thought_signature: Any) -> bool:
    return False


def _should_disable_tools(user_input: str) -> bool:
    normalized = user_input.strip().lower()
    no_tool_markers = (
        "no tools",
        "without tools",
        "don't use tools",
        "do not use tools",
        "no tool calls",
    )
    return any(marker in normalized for marker in no_tool_markers)


def _is_terminal_tool_failure(tool_name: str, result: str) -> bool:
    if tool_name != "analyze_chart_vision":
        return False
    return isinstance(result, str) and result.strip().lower().startswith("error:")


def _tool_call_signature(tool_name: str, tool_input: dict[str, Any]) -> str:
    return json.dumps({"name": tool_name, "input": tool_input}, sort_keys=True, default=str)


def _is_retryable_same_condition_failure(tool_name: str, result: str) -> bool:
    if tool_name != "execute_paper_trade":
        return False
    return isinstance(result, str) and result.startswith("Cannot get current price for ")


def _same_condition_retry_message(tool_name: str) -> str:
    if tool_name == "execute_paper_trade":
        return (
            "I stopped because the paper trade was about to retry the same unresolved "
            "price request without new inputs. Resolve a price first and pass it as "
            "`entry_price`, or use a supported symbol."
        )
    return "I stopped because a tool was about to repeat the same failed request without new inputs."


def _duplicate_paper_trade_message() -> str:
    return (
        "I stopped because the same paper trade was already attempted in this request. "
        "Check the trade history or portfolio before placing another order."
    )


def _user_safe_tool_failure(tool_name: str) -> str:
    if tool_name == "analyze_chart_vision":
        return (
            "I could not generate the chart image right now. "
            "Chart support requires `mplfinance` and working market data."
        )
    return "I could not complete that tool request safely."


def _secret_request_redirect(user_input: str) -> str | None:
    lowered = user_input.lower()
    secret_markers = (
        "wallet password",
        "provide your password",
        "my password is",
        "seed phrase",
        "private key",
        "signing secret",
        "wallet secret",
        "secret key",
        "mnemonic phrase",
        "recovery phrase",
    )
    if any(marker in lowered for marker in secret_markers):
        return (
            "Do not send wallet passwords, seed phrases, private keys, or signing secrets in chat. "
            "Use the secure local TWAK flow to unlock the signer, then retry the on-chain action."
        )
    return None


def _build_request_tool_plan(user_input: str) -> dict[str, Any]:
    return build_intent_tool_policy(user_input)


def _tool_plan_guard_message(
    request_tool_plan: dict[str, Any],
    tool_name: str,
    tool_calls_executed: int,
    tool_input: dict[str, Any] | None = None,
) -> str | None:
    if is_live_execution_tool(tool_name) and not request_tool_plan.get("allow_live_execution", False):
        return (
            f"Tool policy blocked `{tool_name}`. "
            "Live execution is disabled for this request. Gather watchlist or execution-prep evidence only, "
            "then route any eventual execution through the explicit trading-control gate after human confirmation."
        )

    max_tool_calls = int(request_tool_plan.get("max_tool_calls") or 0)
    if max_tool_calls > 0 and tool_calls_executed >= max_tool_calls:
        focus = request_tool_plan.get("focus") or "the current request"
        return (
            f"Planner stop condition reached for {focus}. "
            "Enough evidence has been gathered for this intent. Answer with the narrow results already collected "
            "instead of calling more tools."
        )

    allowed_tools = request_tool_plan.get("allowed_tools") or set()
    if allowed_tools and tool_name not in allowed_tools:
        deferred = ", ".join(request_tool_plan.get("deferred") or [])
        focus = request_tool_plan.get("focus") or "the most important checks"
        deferred_suffix = f" Deferred for now: {deferred}." if deferred else ""
        return (
            f"Intent policy blocked `{tool_name}`. "
            f"Focus first on {focus}.{deferred_suffix} "
            "Use the narrow tool plan instead of branching into broader scans."
        )

    stages = request_tool_plan.get("stages") or []
    if not stages:
        return None

    stage_index = min(tool_calls_executed, len(stages) - 1)
    stage_allowed_tools = stages[stage_index]
    if tool_name in stage_allowed_tools:
        return None

    deferred = ", ".join(request_tool_plan.get("deferred") or [])
    focus = request_tool_plan.get("focus") or "the most important checks"
    deferred_suffix = f" Deferred for now: {deferred}." if deferred else ""
    return (
        f"Staged execution planner deferred `{tool_name}`. "
        f"Focus first on {focus}.{deferred_suffix} "
        "Use results already gathered, or call the next highest-priority tool instead."
    )


def _tool_budget_guard_result(
    request_tool_plan: dict[str, Any],
    cached_tool_results: dict[str, str],
    blocked_tool: str,
) -> str:
    executed_tools = []
    for signature in cached_tool_results:
        try:
            payload = json.loads(signature)
        except json.JSONDecodeError:
            continue
        name = payload.get("name")
        if name and name not in executed_tools:
            executed_tools.append(name)

    if not executed_tools:
        return _tool_budget_message()

    focus = request_tool_plan.get("focus") or "the most important pieces"
    deferred = list(request_tool_plan.get("deferred") or [])
    if blocked_tool not in executed_tools and blocked_tool not in deferred:
        deferred.insert(0, blocked_tool)
    deferred_text = ", ".join(deferred) if deferred else blocked_tool
    executed_text = ", ".join(executed_tools)
    return (
        f"Tool budget reached after checking {focus}. "
        f"Completed first: {executed_text}. "
        f"Deferred: {deferred_text}. "
        "Answer with the partial results already gathered instead of calling more tools."
    )


def _tool_budget_message() -> str:
    return (
        "I could not complete the full request within the tool budget. "
        "Use the partial results already gathered, then note what was deferred."
    )


def _is_telegram_search_like_tool(tool_name: str) -> bool:
    return tool_name in TELEGRAM_REPEAT_LIMITED_TOOLS


def _telegram_tool_repeat_guard(
    tool_name: str,
    tool_call_counts: dict[str, int],
    telegram_search_like_calls: int,
    guard_active: bool = False,
) -> str | None:
    if tool_name in TELEGRAM_REPEAT_LIMITED_TOOLS:
        if guard_active:
            return (
                "Telegram search guard is already active for this request. "
                "Do not call more search-style tools. Answer with the best result from prior tool outputs, "
                "or ask one concise clarifying question if the symbol or chain is still ambiguous."
            )
        max_repeat = _env_int(
            "TELEGRAM_MAX_REPEAT_PER_TOOL",
            DEFAULT_TELEGRAM_MAX_REPEAT_PER_TOOL,
        )
        if max_repeat > 0 and tool_call_counts.get(tool_name, 0) >= max_repeat:
            return (
                f"I stopped because the request kept repeating `{tool_name}` too many times. "
                "Refine the symbol, chain, or goal and try again."
            )

        max_search_like = _env_int(
            "TELEGRAM_MAX_SEARCH_LIKE_CALLS",
            DEFAULT_TELEGRAM_MAX_SEARCH_LIKE_CALLS,
        )
        if max_search_like > 0 and telegram_search_like_calls >= max_search_like:
            return (
                "I stopped because this Telegram request branched into too many search-style tool calls. "
                "Ask for one symbol, one chain, or one task at a time."
            )

    return None


def _telegram_tool_guard_result(tool_name: str, guard_message: str) -> str:
    return (
        f"Search guard intercepted `{tool_name}`.\n"
        f"{guard_message}\n"
        "Use the information already gathered in this request. "
        "Do not call additional search-style tools unless the user gives a new symbol, chain, or explicit correction. "
        "If details are still missing, ask one concise clarifying question instead of searching again."
    )


def _format_tool_result_text(tool_name: str, result: str) -> str:
    return f"Tool result from {tool_name}:\n{result}"


def _format_direct_tool_response(
    response_text: str,
    direct_tool_results: list[dict[str, str]],
) -> str:
    parts = []
    if response_text.strip():
        parts.append(response_text.strip())
    for tool_result in direct_tool_results:
        parts.append(_format_tool_result_text(tool_result["name"], tool_result["content"]))
    return "\n\n".join(parts).strip()


def _build_provider_messages(
    messages: list[dict[str, Any]],
    latest_summary: str | None = None,
) -> list[dict[str, Any]]:
    """Bound provider context without deleting persisted session history."""
    max_messages = _env_int("AGENT_MAX_PROVIDER_MESSAGES", DEFAULT_MAX_PROVIDER_MESSAGES)
    max_chars = _env_int("AGENT_MAX_PROVIDER_CHARS", DEFAULT_MAX_PROVIDER_CHARS)

    if max_messages <= 0 and max_chars <= 0:
        return messages

    selected: list[dict[str, Any]] = []
    total_chars = 0
    for msg in reversed(messages):
        msg_chars = _message_chars(msg)
        if selected and max_messages > 0 and len(selected) >= max_messages:
            break
        if selected and max_chars > 0 and total_chars + msg_chars > max_chars:
            break
        selected.append(msg)
        total_chars += msg_chars

    provider_messages = list(reversed(selected))
    while provider_messages and _contains_only_tool_results(provider_messages[0]):
        provider_messages.pop(0)
    provider_messages = provider_messages or messages[-1:]

    if latest_summary:
        summary_message = _summary_context_message(latest_summary)
        if max_chars <= 0 or _message_chars(summary_message) + sum(
            _message_chars(msg) for msg in provider_messages
        ) <= max_chars:
            provider_messages = [summary_message] + provider_messages

    return provider_messages


def _summary_context_message(summary: str) -> dict[str, str]:
    return {
        "role": "user",
        "content": (
            "Conversation continuity summary from earlier persisted turns. "
            "Use this as context, but prioritize the latest raw messages when they differ.\n\n"
            f"{summary}"
        ),
    }


def _log_provider_context(
    all_messages: list[dict[str, Any]],
    provider_messages: list[dict[str, Any]],
) -> None:
    logger.info(
        "Provider context: %d/%d messages, %d chars",
        len(provider_messages),
        len(all_messages),
        sum(_message_chars(msg) for msg in provider_messages),
    )


def _message_chars(msg: dict[str, Any]) -> int:
    try:
        return len(json.dumps(msg, ensure_ascii=False))
    except (TypeError, ValueError):
        return len(str(msg))


def _contains_only_tool_results(msg: dict[str, Any]) -> bool:
    content = msg.get("content")
    if not isinstance(content, list) or not content:
        return False
    return all(isinstance(block, dict) and block.get("type") == "tool_result" for block in content)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using %d", name, raw, default)
        return default


def _load_workspace_strategy_memory(max_chars_per_file: int = 4000) -> list[str]:
    """Load persistent strategy markdown files into the startup prompt."""
    memory_dir = Path(__file__).resolve().parents[1] / "workspace" / "agent_memory"
    if not memory_dir.exists():
        return []

    notes: list[str] = []
    for path in sorted(memory_dir.glob("*_strategy.md")):
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue

        if not content:
            continue

        if len(content) > max_chars_per_file:
            content = content[:max_chars_per_file].rstrip() + "\n...[truncated]"

        notes.append(f"FILE: {path.name}\n{content}")

    return notes
