import logging
import json
import os
import time
from pathlib import Path
from typing import Any, Generator

from rich.console import Console

from core.provider import ModelProvider, create_client, get_provider
from core.tools import execute_tool, get_tool_definitions
from memory.store import load_last_session_for_provider, new_session, save_session_for_provider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a sophisticated Crypto Trading AI Agent. You have access to tools that let you:
- Run shell commands (bash)
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
- Manage an on-chain agent wallet via Trust Wallet Agent Skills (get_wallet_status, create_agent_wallet, get_wallet_addresses, get_wallet_balance, transfer_tokens, swap_tokens, check_onchain_risk)
- Execute MEV-protected trades using the `swap_tokens` tool with the `use_mev_protection` flag.
- Perform deep security audits on token contracts (audit_token_contract) to detect rug-pulls and honeypots.
- Set intelligent background alerts for price, sentiment, whale moves, and wallet activity (set_smart_alert).
- Optimize trading strategy parameters through automated backtesting grid search (optimize_strategy_parameters).
- Generate comprehensive daily alpha reports from news and social catalysts (get_daily_alpha).
- Calculate professional-grade technical indicators like SuperTrend, ADX, and RSI (get_pro_indicators).
- Identify institutional market structure, support/resistance, and fair value gaps (analyze_market_structure).
- Perform multi-timeframe analysis to confirm trends across 1h, 4h, and 1d charts (get_multi_timeframe_signal).
- Architect high-conviction swing trade setups with Fibonacci zones, RSI divergence detection, and ATR-based stops (get_swing_setup).
- Proactively scan the market and propose high-conviction trades via the Autonomous Trading Cycle (trigger_autonomous_cycle).
- Verify plans and analyses with the Council of Models to ensure multi-brain consensus (verify_with_council).
- Audit trading performance by strategy and win-rate (audit_strategy_performance).
- Self-prune the Wisdom Ledger to remove counter-productive or redundant rules (prune_wisdom_ledger).
- Check currently running background tasks (check_background_processes).

Use these tools to help the user with crypto trading, portfolio management, and market analysis.
You can perform both simulated (paper) trading and real on-chain trading if the user provides a wallet and password.
When executing trades, always consider risk management.
Be concise, practical, and data-driven. Execute the steps needed, then explain the result clearly."""

MAX_ITERATIONS = 50
DEFAULT_MAX_PROVIDER_MESSAGES = 20
DEFAULT_MAX_PROVIDER_CHARS = 60_000

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
            "get_swing_setup", "trigger_autonomous_cycle", "verify_with_council",
            "check_background_processes", "hunt_insider_wallets", "verify_alpha_wallet", "add_alpha_wallet"
        ]
    },
    "executor": {
        "description": "You are a specialized Crypto Executor Agent. Your ONLY job is to execute trades, calculate optimal sizing, and interact with the wallet.",
        "allowed_tools": [
            "calculate_position_size", "execute_paper_trade", "create_paper_trading_account",
            "get_portfolio_status", "get_trade_history", "get_wallet_status", "create_agent_wallet",
            "get_wallet_addresses", "get_wallet_balance", "transfer_tokens", "swap_tokens", "trust_get_swap_quote",
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
            "get_pro_indicators", "analyze_market_structure", "get_swing_setup", "verify_with_council",
            "audit_strategy_performance", "prune_wisdom_ledger", "check_background_processes"
        ]
    },
    "tutor": {
        "description": "You are a specialized Crypto Trading Tutor. Your ONLY job is to explain complex trading concepts, technical indicators, and the AI's recent decisions in simple, educational terms. Your goal is to empower the user with knowledge, emphasizing clarity, stillness, and long-term sustainability.",
        "allowed_tools": [
            "read_strategy", "get_pro_indicators", "analyze_market_structure", 
            "get_multi_timeframe_signal", "get_swing_setup", "audit_strategy_performance",
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
        self.client = create_client(self.provider)
        self.tool_definitions = get_tool_definitions()

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
        self.messages.append({"role": "user", "content": user_input})

        final_text = ""
        for iteration in range(MAX_ITERATIONS):
            iter_start = time.time()
            try:
                # Only Ollama currently supports create_message_stream in this simplified implementation
                if hasattr(self.client, "create_message_stream") and self.provider == ModelProvider.OLLAMA:
                    provider_messages = _build_provider_messages(self.messages)
                    _log_provider_context(self.messages, provider_messages)
                    stream = self.client.create_message_stream(
                        messages=provider_messages,
                        tools=self.tool_definitions,
                        system_prompt=self.system_prompt,
                    )
                else:
                    # Fallback for providers without streaming (returns single response)
                    llm_start = time.time()
                    provider_messages = _build_provider_messages(self.messages)
                    _log_provider_context(self.messages, provider_messages)
                    response = self.client.create_message(
                        messages=provider_messages,
                        tools=self.tool_definitions,
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
                    
                    yield {"type": "tool_start", "name": tool_name, "input": tool_input}

                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": tool_use_id,
                            "name": tool_name,
                            "input": tool_input,
                            "thought_signature": getattr(block, "thought_signature", None)
                        }
                    )

                    self.console.print(f"[dim]Calling tool: {tool_name}[/dim]")
                    tool_start = time.time()
                    result = execute_tool(tool_name, tool_input)
                    logger.info(f"Tool {tool_name} took {time.time() - tool_start:.3f}s")
                    
                    yield {"type": "tool_end", "name": tool_name, "result": result}

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "name": tool_name,
                            "content": result,
                        }
                    )

            if assistant_content:
                self.messages.append({"role": "assistant", "content": assistant_content})

            logger.info(f"Iteration {iteration+1} complete in {time.time() - iter_start:.3f}s")

            if not tool_results:
                final_text = response_text.strip()
                save_session_for_provider(self.sid, self.messages, self.provider.value)
                logger.info(f"Total request duration: {time.time() - start_request:.3f}s")
                yield {"type": "final_response", "content": final_text}
                return

            self.messages.append({"role": "user", "content": tool_results})

        yield {"type": "error", "content": "Error: tool loop exceeded maximum iterations."}

    def chat(self, user_input: str) -> str:
        """Send a message to the agent, handle tool calls, return the final text response."""
        start_request = time.time()
        self.messages.append({"role": "user", "content": user_input})

        final_text = ""
        for iteration in range(MAX_ITERATIONS):
            iter_start = time.time()
            try:
                llm_start = time.time()
                provider_messages = _build_provider_messages(self.messages)
                _log_provider_context(self.messages, provider_messages)
                response = self.client.create_message(
                    messages=provider_messages,
                    tools=self.tool_definitions,
                    system_prompt=self.system_prompt,
                )
                logger.info(f"LLM call took {time.time() - llm_start:.3f}s")
            except Exception as e:  # noqa: BLE001
                logger.error("API error: %s", e)
                return f"API error: {e}"

            response_text = ""
            assistant_content: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []

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
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": tool_use_id,
                            "name": tool_name,
                            "input": tool_input,
                            "thought_signature": getattr(block, "thought_signature", None)
                        }
                    )

                    self.console.print(f"[dim]Calling tool: {tool_name}[/dim]")
                    tool_start = time.time()
                    result = execute_tool(tool_name, tool_input)
                    logger.info(f"Tool {tool_name} took {time.time() - tool_start:.3f}s")

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "name": tool_name,
                            "content": result,
                        }
                    )

            if assistant_content:
                self.messages.append({"role": "assistant", "content": assistant_content})

            logger.info(f"Iteration {iteration+1} complete in {time.time() - iter_start:.3f}s")

            if not tool_results:
                final_text = response_text.strip()
                save_session_for_provider(self.sid, self.messages, self.provider.value)
                logger.info(f"Total request duration: {time.time() - start_request:.3f}s")
                return final_text

            self.messages.append({"role": "user", "content": tool_results})

        return "Error: tool loop exceeded maximum iterations."


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


def _build_provider_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
    return provider_messages or messages[-1:]


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
