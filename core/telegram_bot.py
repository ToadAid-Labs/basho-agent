import logging
import os
import time
import sys
import json
import io
import requests
import uuid
import asyncio
import re
import tempfile
import subprocess
import struct
import zlib
from pathlib import Path
from threading import Thread
from typing import Any, Optional, Dict, List
from datetime import datetime

import telegram
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, ApplicationHandlerStop

from core.agent import Agent
from core.provider import ModelProvider, create_client, get_provider

logger = logging.getLogger(__name__)
load_dotenv()

# Flask backend configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")
API_TIMEOUT = 15  # seconds
AGENT_TIMEOUT = int(os.getenv("TELEGRAM_AGENT_TIMEOUT_SECONDS", "120"))
MAX_TELEGRAM_IMAGE_BYTES = int(os.getenv("TELEGRAM_MAX_IMAGE_BYTES", str(10 * 1024 * 1024)))
CHART_REQUEST_RE = re.compile(r"\b(chart|candlestick|candle|price\s+chart)\b", re.IGNORECASE)
SYMBOL_RE = re.compile(r"\b(BTC|ETH|SOL|BNB|XRP|ADA|DOGE|AVAX|LINK|MATIC|ARB|OP|PEPE|WIF|BONK)\b", re.IGNORECASE)
SYMBOL_ALIASES = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "ether": "ETH",
    "solana": "SOL",
}

def _get_session_dir() -> Path:
    path = Path.home() / ".agent" / "telegram_sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _load_user_session(chat_id: int) -> tuple[str | None, list[dict[str, Any]]]:
    """Load session for a specific Telegram user."""
    try:
        from memory.store import load_last_session_for_thread

        sid, messages = load_last_session_for_thread(f"telegram:{chat_id}")
        if sid:
            return sid, messages
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to load SQLite Telegram session for %s: %s", chat_id, e)

    session_file = _get_session_dir() / f"user_{chat_id}.json"
    if not session_file.exists():
        return None, []
    try:
        data = json.loads(session_file.read_text())
        return data.get("session_id"), data.get("messages", [])
    except (json.JSONDecodeError, OSError):
        return None, []

def _save_user_session(chat_id: int, sid: str, messages: list[dict[str, Any]]) -> None:
    """Persist a Telegram user's session."""
    session_file = _get_session_dir() / f"user_{chat_id}.json"
    session_file.write_text(json.dumps({"session_id": sid, "messages": messages}))


def _get_wallet_addresses_text() -> str:
    """Fetch wallet addresses with terminal QR blocks from twak."""
    try:
        result = subprocess.run(
            ["twak", "wallet", "addresses"],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
            timeout=45,
        )
    except Exception as e:  # noqa: BLE001
        return f"Error: {type(e).__name__}: {e}"

    if result.returncode != 0:
        return f"Error: {(result.stderr or result.stdout).strip()}"
    return result.stdout.strip()


def _parse_wallet_address_cards(output: str) -> list[dict[str, Any]]:
    """Parse twak wallet address boxes into chains, address, and terminal QR lines."""
    cards: list[dict[str, Any]] = []
    current: list[str] = []
    in_box = False

    for line in output.splitlines():
        if line.startswith("╭"):
            current = []
            in_box = True
            continue
        if line.startswith("╰") and in_box:
            card = _parse_wallet_address_card(current)
            if card:
                cards.append(card)
            current = []
            in_box = False
            continue
        if in_box and "│" in line:
            first = line.find("│")
            last = line.rfind("│")
            if first != last:
                current.append(line[first + 1:last].rstrip())

    return cards


def _parse_wallet_address_card(lines: list[str]) -> Optional[dict[str, Any]]:
    chains_parts: list[str] = []
    address = ""
    qr_lines: list[str] = []
    collecting_chains = False
    collecting_qr = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Chains"):
            collecting_chains = True
            chains_parts.append(stripped.removeprefix("Chains").strip())
            continue
        if stripped.startswith("Address"):
            collecting_chains = False
            collecting_qr = True
            address = stripped.removeprefix("Address").strip()
            continue
        if collecting_chains and not collecting_qr:
            chains_parts.append(stripped)
            continue
        if collecting_qr and any(ch in line for ch in ("█", "▄", "▀")):
            qr_lines.append(line.strip())

    if not address or not qr_lines:
        return None

    chains = " ".join(part for part in chains_parts if part)
    chains = re.sub(r"\s+", " ", chains).strip()
    return {"chains": chains or "chains unknown", "address": address, "qr_lines": qr_lines}


def _render_terminal_qr_png(qr_lines: list[str], address: str) -> str:
    """Render terminal QR block characters into a scannable PNG."""
    module_size = 12
    quiet_modules = 4
    width_modules = max(len(line) for line in qr_lines)
    height_modules = len(qr_lines) * 2
    side_modules = max(width_modules, height_modules)
    image_modules = side_modules + quiet_modules * 2
    image_size = image_modules * module_size

    pixels = bytearray([255] * (image_size * image_size * 3))
    x_offset = quiet_modules + (side_modules - width_modules) // 2
    y_offset = quiet_modules + (side_modules - height_modules) // 2

    def fill_module(mx: int, my: int) -> None:
        x0 = mx * module_size
        y0 = my * module_size
        for y in range(y0, y0 + module_size):
            for x in range(x0, x0 + module_size):
                idx = (y * image_size + x) * 3
                pixels[idx:idx + 3] = b"\x00\x00\x00"

    for row_idx, raw_line in enumerate(qr_lines):
        line = raw_line.ljust(width_modules)
        for col_idx, char in enumerate(line):
            mx = x_offset + col_idx
            top_my = y_offset + row_idx * 2
            bottom_my = top_my + 1
            if char == "█":
                fill_module(mx, top_my)
                fill_module(mx, bottom_my)
            elif char == "▀":
                fill_module(mx, top_my)
            elif char == "▄":
                fill_module(mx, bottom_my)

    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", address[:24])
    path = Path(tempfile.gettempdir()) / f"wallet_qr_{safe_name}_{uuid.uuid4().hex[:8]}.png"
    _write_rgb_png(path, image_size, image_size, bytes(pixels))
    return str(path)


def _write_rgb_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    """Write an RGB PNG using only the Python standard library."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind)
        checksum = zlib.crc32(data, checksum)
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum & 0xFFFFFFFF)

    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(rgb[start:start + stride])

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), level=9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


class TelegramBot:
    """Enhanced Telegram bot wrapper with AI Agent integration and trading menu."""

    def __init__(self, provider: ModelProvider | None = None, backend_url: str = BACKEND_URL):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set. Add it to your .env file.")
        
        self.token = token
        self._provider_locked = provider is not None
        self.provider = provider or get_provider()
        self._agents: dict[int, Agent] = {}
        self.backend_url = backend_url
        self.user_sessions: dict[int, dict] = {}
        self.wallet_cache: dict[str, dict[str, Any]] = {}
        self._handled_chart_messages: set[tuple[int, int]] = set()

    def _get_agent(self, chat_id: int) -> Agent:
        """Get or create an Agent for this Telegram user."""
        if not self._provider_locked:
            current_provider = get_provider()
            if current_provider != self.provider:
                logger.info(
                    "Telegram bot provider changed from %s to %s after env reload.",
                    self.provider.value,
                    current_provider.value,
                )
                self.provider = current_provider

        existing_agent = self._agents.get(chat_id)
        if existing_agent is not None and existing_agent.provider != self.provider:
            logger.info("Rebuilding Telegram agent for chat %s with provider %s.", chat_id, self.provider.value)
            self._agents.pop(chat_id, None)

        if chat_id not in self._agents:
            sid, history = _load_user_session(chat_id)
            if sid is None:
                sid = uuid.uuid4().hex[:12]
            try:
                self._agents[chat_id] = Agent(provider=self.provider, sid=sid, user_id=chat_id, history=history)
            except ValueError as exc:
                fallback_provider = self._fallback_provider_for_error(exc)
                if fallback_provider is None:
                    raise
                logger.warning(
                    "Primary Telegram provider %s failed for chat %s, retrying with %s: %s",
                    self.provider.value,
                    chat_id,
                    fallback_provider.value,
                    exc,
                )
                self.provider = fallback_provider
                self._agents[chat_id] = Agent(provider=self.provider, sid=sid, user_id=chat_id, history=history)
        return self._agents[chat_id]

    def _fallback_provider_for_error(self, exc: Exception) -> Optional[ModelProvider]:
        message = str(exc)
        if self._provider_locked:
            return None
        if self.provider == ModelProvider.GEMINI and "reauthentication" in message.lower():
            token_path = os.path.expanduser(os.getenv("OPENAI_CODEX_TOKEN_PATH", "~/.agent_openai_codex_auth.json"))
            if os.path.exists(token_path):
                return ModelProvider.OPENAI_CODEX
        return None

    async def _call_api(self, endpoint: str, method: str = "GET", params: Optional[dict] = None, json_data: Optional[dict] = None) -> dict:
        """Make API call to the backend Flask server."""
        try:
            url = f"{self.backend_url}{endpoint}"
            if method == "GET":
                response = requests.get(url, params=params, timeout=API_TIMEOUT)
            elif method == "POST":
                response = requests.post(url, json=json_data, timeout=API_TIMEOUT)
            else:
                raise ValueError(f"Unsupported method: {method}")

            try:
                data = response.json()
            except ValueError:
                data = {"error": response.text or response.reason}
            if response.status_code >= 400:
                if isinstance(data, dict):
                    data.setdefault("success", False)
                    data.setdefault("error", response.reason)
                    return data
                return {"error": str(data), "success": False}
            response.raise_for_status()
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"API call failed ({method} {endpoint}): {e}")
            return {"error": str(e), "success": False}

    async def _call_api_candidates(self, candidates: list[tuple[str, dict]]) -> dict:
        """Try multiple GET endpoints and return the first successful response."""
        errors = []
        for endpoint, params in candidates:
            data = await self._call_api(endpoint, params=params)
            if data.get("success"):
                return data
            errors.append(f"{endpoint}: {data.get('error', 'unknown error')}")
        return {"success": False, "error": " | ".join(errors)}

    def _get_main_menu(self) -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("📊 Dashboard", callback_data="view:dashboard"),
                InlineKeyboardButton("💼 Portfolio", callback_data="view:portfolio")
            ],
            [
                InlineKeyboardButton("💹 Market", callback_data="menu:market"),
                InlineKeyboardButton("🧪 Paper Trading", callback_data="menu:paper")
            ],
            [
                InlineKeyboardButton("🎓 Learn & Explain", callback_data="action:tutor_mode"),
                InlineKeyboardButton("🛡 Risk", callback_data="menu:risk")
            ],
            [
                InlineKeyboardButton("⚡ Live Trading", callback_data="menu:live"),
                InlineKeyboardButton("👛 Wallet", callback_data="menu:wallet")
            ],
            [
                InlineKeyboardButton("🔮 Forge", callback_data="menu:forge"),
                InlineKeyboardButton("🤖 Agent Tools", callback_data="menu:agent"),
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        welcome_text = (
            "🤖 **AI Crypto Trading Bot**\n\n"
            "Welcome! I am your AI assistant for crypto trading. "
            "You can talk to me directly to ask about prices, trends, or to execute trades, "
            "or use the menu below for quick actions."
        )
        await update.message.reply_text(welcome_text, reply_markup=self._get_main_menu(), parse_mode="MarkdownV2", disable_web_page_preview=True)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages (pass to AI Agent)."""
        chat_id = update.effective_chat.id
        message = update.message
        chat = update.effective_chat
        message_key = self._message_key(update)
        if message_key in self._handled_chart_messages:
            raise ApplicationHandlerStop

        text = (message.text or "").strip()

        if not text:
            return

        # In group chats, stay silent unless the bot is explicitly called.
        # This prevents the agent from answering random group messages.
        if chat and chat.type in ("group", "supergroup"):
            bot_username = (context.bot.username or "").lower()
            allowed_mentions = {"@agent", "@tobycoder_bot"}
            if bot_username:
                allowed_mentions.add(f"@{bot_username}")

            is_mentioned = False
            if message.entities:
                for entity in message.entities:
                    if entity.type == "mention":
                        mention_text = text[entity.offset:entity.offset + entity.length].lower()
                        if mention_text in allowed_mentions:
                            is_mentioned = True
                            break

            is_reply_to_bot = (
                message.reply_to_message
                and message.reply_to_message.from_user
                and message.reply_to_message.from_user.id == context.bot.id
            )

            if not (is_mentioned or is_reply_to_bot):
                return

            # Remove the mention before sending the prompt to the agent.
            for mention in sorted(allowed_mentions, key=len, reverse=True):
                text = re.sub(rf"{re.escape(mention)}\b", "", text, flags=re.IGNORECASE).strip()
            if not text:
                text = "help"

        session = self.user_sessions.get(chat_id, {})
        
        # Handle specific input modes
        if session.get("mode") == "wait_buy_symbol":
            await self._process_quick_trade(update, context, "buy", text)
            return
        elif session.get("mode") == "wait_sell_symbol":
            await self._process_quick_trade(update, context, "sell", text)
            return
        elif session.get("mode") == "wait_market_price":
            await self._process_market_price(update, text)
            return
        elif session.get("mode") == "wait_market_search":
            await self._process_market_search(update, text)
            return
        elif session.get("mode") == "wait_swap_quote":
            await self._process_swap_quote(update, text)
            return
        elif session.get("mode") == "wait_token_risk":
            await self._process_token_risk(update, text)
            return
        elif session.get("mode") == "wait_record_prediction":
            await self._process_record_prediction(update, text)
            return
        elif session.get("mode") == "wait_forge_contract":
            await self._process_forge_contract(update, text)
            return
        elif session.get("mode") == "wait_forge_record":
            await self._process_forge_record(update, text)
            return
        elif session.get("mode") == "wait_forge_watch":
            await self._process_forge_watch(update, text)
            return
        elif session.get("mode") == "wait_forge_backtest":
            await self._process_forge_backtest(update, text)
            return

        if self._is_tobyworld_archive_request(text):
            await self._handle_tobyworld_archive_request(update)
            return

        if self._is_wake_check(text):
            print(f"Received Telegram wake check from {chat_id}: {text[:120]}", flush=True)
            await update.message.reply_text(
                "Awake. Telegram is connected and the bot process is running."
            )
            return

        if self._is_chart_request(text):
            self._mark_chart_message_handled(message_key)
            try:
                await self._handle_chart_request(update, context, text)
            finally:
                self._mark_chart_message_handled(message_key)
            raise ApplicationHandlerStop

        # Default: AI Chat
        print(f"Received Telegram message from {chat_id}: {text[:120]}", flush=True)
        status_message = None
        try:
            status_message = await update.message.reply_text("⌛ Working on that...")
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to send working status to %s: %s", chat_id, e)
        
        result_holder = [""]
        error_holder = [""]
        agent = self._get_agent(chat_id)

        def run_agent():
            try:
                result_holder[0] = agent.chat(text)
            except Exception as e:
                error_holder[0] = str(e)

        thread = Thread(target=run_agent, daemon=True)
        thread.start()
        
        # Keep sending "typing" indicator while thread is alive
        start_time = time.time()
        while thread.is_alive():
            if time.time() - start_time > AGENT_TIMEOUT:
                break
            
            try:
                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            except Exception:
                pass
            
            # Wait up to 5 seconds for thread to finish
            thread.join(timeout=5)

        if thread.is_alive():
            if message_key in self._handled_chart_messages:
                return
            await update.message.reply_text(
                f"⚠️ AI Agent is still working after {AGENT_TIMEOUT} seconds. "
                "The request was left running in the background. Try a smaller request "
                "or raise TELEGRAM_AGENT_TIMEOUT_SECONDS."
            )
            print(f"Telegram agent timed out for {chat_id} after {AGENT_TIMEOUT}s", flush=True)
            return

        if error_holder[0]:
            if message_key in self._handled_chart_messages:
                return
            await update.message.reply_text(f"❌ AI Error: {error_holder[0]}")
            return

        if message_key in self._handled_chart_messages:
            return
        response = self._prepare_telegram_response(result_holder[0] or "(no response)")
        if status_message is not None:
            try:
                await status_message.delete()
            except Exception:
                pass

        # Split and send response
        for chunk in self._telegram_chunks(response):
            await update.message.reply_text(chunk, parse_mode="MarkdownV2", disable_web_page_preview=True)
            
        _save_user_session(chat_id, agent.sid, agent.messages)

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle button clicks."""
        query = update.callback_query
        await query.answer()
        
        chat_id = query.message.chat_id
        data = query.data
        parts = data.split(":", 1)
        category = parts[0]
        action = parts[1] if len(parts) > 1 else None

        if category == "view":
            if action == "dashboard":
                await self._show_dashboard(query)
            elif action == "portfolio":
                await self._show_portfolio(query)
        elif category == "menu":
            if action in ("trade", "paper"):
                await self._show_paper_menu(query)
            elif action == "analysis":
                await self._show_market_menu(query)
            elif action == "market":
                await self._show_market_menu(query)
            elif action == "live":
                await self._show_live_menu(query)
            elif action == "risk":
                await self._show_risk_menu(query)
            elif action == "agent":
                await self._show_agent_menu(query)
            elif action == "forge":
                await self._show_forge_menu(query)
            elif action == "settings":
                await self._show_settings_menu(query)
            elif action == "wallet":
                await self._show_wallet_menu(query)
            elif action == "main":
                await query.edit_message_text("Main Menu", reply_markup=self._get_main_menu())
        elif category == "proposal":
            await self._handle_proposal_callback(query, action)
        elif category == "action":
            if action == "reset_ai":
                if chat_id in self._agents: del self._agents[chat_id]
                from memory.store import reset_sessions_for_thread
                reset_sessions_for_thread(f"telegram:{chat_id}")
                _get_session_dir().joinpath(f"user_{chat_id}.json").unlink(missing_ok=True)
                await query.edit_message_text("🔄 AI session reset!", reply_markup=self._get_main_menu())
            elif action == "wallet_status":
                await query.edit_message_text("⌛ Fetching wallet status...")
                from tools.trust_wallet import get_wallet_status
                res = await self._run_blocking(get_wallet_status, timeout=45)
                await self._show_result(query, "👛 Wallet Status", {"Status": res}, "menu:wallet")
            elif action == "wallet_addresses":
                await self._handle_wallet_addresses(query, refresh=False)
            elif action == "wallet_refresh":
                await self._handle_wallet_addresses(query, refresh=True)
            elif action == "wallet_balance":
                await query.edit_message_text("⌛ Fetching portfolio...")
                from tools.trust_wallet import get_wallet_balance
                res = await self._run_blocking(get_wallet_balance, timeout=60)
                await self._show_result(query, "👛 On-chain Portfolio", {"Portfolio": res}, "menu:wallet")
            elif action == "wallet_gas":
                await query.edit_message_text("⌛ Fetching native gas balances...")
                from tools.trust_wallet import get_wallet_balance
                parts = []
                for chain in ("ethereum", "base", "solana"):
                    res = await self._run_blocking(lambda c=chain: get_wallet_balance(c), timeout=30)
                    parts.append(f"{chain}:\n{res}")
                await self._show_result(query, "⛽ Native Gas Balances", {"Balances": "\n\n".join(parts)}, "menu:wallet")
            elif action == "create_account":
                res = await self._call_api("/api/paper-trading/initialize", "POST", json_data={"telegram_id": chat_id})
                msg = "✅ Account created!" if res.get("success") else f"❌ Error: {res.get('error')}"
                await query.edit_message_text(msg, reply_markup=self._paper_back_menu())
            elif action == "quick_buy":
                self.user_sessions[chat_id] = {"mode": "wait_buy_symbol"}
                await query.edit_message_text("🛒 Enter symbol and amount to BUY (e.g., BTC 1000):")
            elif action == "quick_sell":
                self.user_sessions[chat_id] = {"mode": "wait_sell_symbol"}
                await query.edit_message_text("🛒 Enter symbol and amount to SELL (e.g., BTC 0.5):")
            elif action == "paper_history":
                await self._force_agent_action(chat_id, "Show my paper trade history using my Telegram user ID.", query.message)
            elif action == "paper_strategy_pnl":
                await self._force_agent_action(chat_id, "Summarize my paper trading performance by strategy and symbol using my Telegram user ID.", query.message)
            elif action == "market_price_eth":
                await self._show_trust_price(query, "ETH", "ethereum")
            elif action == "market_price_btc":
                await self._show_trust_price(query, "BTC", "bitcoin")
            elif action == "market_price_sol":
                await self._show_trust_price(query, "SOL", "solana")
            elif action == "market_price_custom":
                self.user_sessions[chat_id] = {"mode": "wait_market_price"}
                await query.edit_message_text("💹 Enter token and optional chain (e.g., ETH ethereum, SOL solana, BTC bitcoin):")
            elif action == "market_search":
                self.user_sessions[chat_id] = {"mode": "wait_market_search"}
                await query.edit_message_text("🔎 Enter token search and optional chain (e.g., ETH ethereum, PEPE ethereum):")
            elif action == "swap_quote":
                self.user_sessions[chat_id] = {"mode": "wait_swap_quote"}
                await query.edit_message_text("💱 Enter quote as: amount FROM TO chain\nExample: 0.01 ETH USDC ethereum")
            elif action == "trending":
                await self._force_agent_action(chat_id, "Use Trust Wallet tools to show trending tokens. Keep it concise.", query.message)
            elif action == "trends":
                await query.edit_message_text("🔍 Analyzing market trends... (this may take a moment)")
                await self._force_agent_action(chat_id, "Analyze the market trends for the top 5 cryptocurrencies and give me a summary.", query.message)
            elif action == "wisdom_ledger":
                from memory.wisdom import WisdomStore
                commandments = WisdomStore().get_commandments()
                if not commandments:
                    text = "🧠 Wisdom Ledger\n\nThe ledger is currently empty. No lessons learned yet."
                else:
                    text = "🧠 Wisdom Ledger (Commandments)\n\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(commandments))
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu:agent")]]))
            elif action == "tutor_mode":
                await query.edit_message_text("🎓 Entering Tutor Mode... (The Agent will now explain its logic)")
                await self._force_agent_action(chat_id, "Act as my Trading Tutor. Use the tutor_explain_activity tool to review our recent performance and teach me something new about our current strategy.", query.message, role="tutor")
            elif action == "risk_check":
                await query.edit_message_text("🛡️ Checking portfolio risk...")
                await self._force_agent_action(chat_id, "Check my portfolio risk limits and concentration.", query.message)
            elif action == "token_risk":
                self.user_sessions[chat_id] = {"mode": "wait_token_risk"}
                await query.edit_message_text("🛡 Enter token asset ID/address and optional chain (e.g., ETH ethereum, 0x... base):")
            elif action == "position_sizing":
                await self._force_agent_action(chat_id, "Help me size a swing trade conservatively. Ask for missing entry, stop, portfolio value, and risk percent if needed.", query.message)
            elif action == "kelly":
                await self._force_agent_action(chat_id, "Explain and calculate conservative fractional Kelly risk. Ask for confidence and risk/reward if needed.", query.message)
            elif action == "run_backtest":
                await self._force_agent_action(chat_id, "Run or prepare a portfolio-level backtest for the current strategy idea. Ask for missing strategy details if needed.", query.message)
            elif action == "prediction_accuracy":
                await self._force_agent_action(chat_id, "Evaluate due price predictions, then show my prediction accuracy summary. Use evaluate_price_predictions and get_prediction_accuracy.", query.message)
            elif action == "record_prediction":
                self.user_sessions[chat_id] = {"mode": "wait_record_prediction"}
                await query.edit_message_text("🎯 Enter prediction as: SYMBOL PREDICTED_PRICE CONFIDENCE [HOURS]\nExample: ETH 2600 0.65 24")
            elif action == "forge_contract":
                self.user_sessions[chat_id] = {"mode": "wait_forge_contract"}
                await query.edit_message_text("🔮 Enter contract and optional chain:\n0x... base")
            elif action == "forge_record":
                self.user_sessions[chat_id] = {"mode": "wait_forge_record"}
                await query.edit_message_text(
                    "📝 Enter forecast target:\n"
                    "ETH ethereum 1h composite\n"
                    "or\n"
                    "0x... base 24h risk"
                )
            elif action == "forge_ledger":
                await query.edit_message_text("⌛ Checking Forge ledger...")
                from tools.trend_prediction_tools import forge_evaluate_due_predictions, forge_prediction_ledger_summary
                await self._run_blocking(lambda: forge_evaluate_due_predictions(), timeout=60)
                res = await self._run_blocking(lambda: forge_prediction_ledger_summary(), timeout=30)
                await self._show_result(query, "🔮 Forge Ledger", {"Ledger": res}, "menu:forge")
            elif action == "forge_add_watch":
                self.user_sessions[chat_id] = {"mode": "wait_forge_watch"}
                await query.edit_message_text(
                    "👁 Enter watch:\n"
                    "ETH ethereum 1h,4h,24h composite,risk\n"
                    "or\n"
                    "0x... base 1h,24h composite,risk"
                )
            elif action == "forge_list_watches":
                from tools.trend_prediction_tools import forge_list_watches
                res = await self._run_blocking(lambda: forge_list_watches(active_only=False, user_id=None), timeout=30)
                await self._show_result(query, "👁 Forge Watches", {"Watches": res}, "menu:forge")
            elif action == "forge_alerts":
                from tools.trend_prediction_tools import forge_list_alerts
                res = await self._run_blocking(lambda: forge_list_alerts(limit=20), timeout=30)
                await self._show_result(query, "🚨 Forge Alerts", {"Alerts": res}, "menu:forge")
            elif action == "forge_run_watchlist":
                await query.edit_message_text("⌛ Running Forge watchlist...")
                from tools.trend_prediction_tools import forge_run_watchlist
                res = await self._run_blocking(lambda: forge_run_watchlist(force=True), timeout=120)
                await self._show_result(query, "👁 Forge Watchlist Run", {"Result": res}, "menu:forge")
            elif action == "forge_backtest":
                self.user_sessions[chat_id] = {"mode": "wait_forge_backtest"}
                await query.edit_message_text("🧪 Enter backtest:\nETH 24h composite\nSOL 4h momentum")
            elif action == "market_regime":
                await self._force_agent_action(chat_id, "Detect the current market regime for BTC and ETH using detect_market_regime. Keep it concise.", query.message)
            elif action == "trade_plan":
                await self._force_agent_action(chat_id, "Generate a concise swing-trading plan using current market data, risk rules, and portfolio context.", query.message)
            elif action == "review_positions":
                await self._force_agent_action(chat_id, "Review my open positions, risk, and next actions using my Telegram user ID.", query.message)
            elif action == "live_history":
                await self._force_agent_action(chat_id, "Use Trust Wallet Agent Kit to show recent wallet transaction history. Keep it concise.", query.message)
            elif action == "live_swap_help":
                await query.edit_message_text(
                    "To execute a live swap, type a full instruction to the agent, including chain, amount, from token, to token, slippage, and explicit confirmation.\n\n"
                    "Example:\nQuote first: swap quote 0.01 ETH to USDC on ethereum\n\n"
                    "Only execute after reviewing the quote.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu:live")]]),
                )
            elif action == "live_transfer_help":
                await query.edit_message_text(
                    "To transfer live funds, type a full instruction to the agent with chain, recipient address, amount, token, and explicit confirmation.\n\n"
                    "Start with a tiny test transfer. Never send funds before checking address and chain twice.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu:live")]]),
                )
            elif action == "settings_summary":
                await self._show_settings_summary(query)
            elif action == "settings_mode":
                await query.edit_message_text("Mode is currently conservative: paper trading is one-tap; live transfer/swap requires typed confirmation through the agent.", reply_markup=self._settings_back_menu())
            elif action == "settings_refresh_cache":
                self.wallet_cache.clear()
                await query.edit_message_text("✅ Wallet cache cleared.", reply_markup=self._settings_back_menu())

    async def _handle_proposal_callback(self, query: telegram.CallbackQuery, action_data: str) -> None:
        """Handle execution or rejection of a proactive trade proposal."""
        chat_id = query.message.chat_id
        parts = action_data.split(":", 1)
        sub_action = parts[0]
        proposal_id = parts[1] if len(parts) > 1 else None
        
        from memory.proposals import ProposalStore
        store = ProposalStore()
        proposal = store.get_proposal(proposal_id)
        
        if not proposal:
            await query.edit_message_text("❌ Proposal not found or expired.")
            return
            
        if sub_action == "reject":
            store.update_proposal(proposal_id, "rejected")
            await query.edit_message_text(f"❌ Proposal for #{proposal['symbol']} rejected.")
            return
            
        if sub_action == "execute":
            await query.edit_message_text(f"⏳ Executing swing trade for #{proposal['symbol']}...")
            
            # Setup executor agent
            agent = self._get_agent(chat_id)
            symbol = proposal["symbol"]
            setup = proposal["setup"]
            plan = setup.get("trade_plan", {})
            
            # Formulate the instruction
            try:
                entry_range = plan.get("entry_range", "0-0")
                if "-" in entry_range:
                    entry_price = float(entry_range.split("-")[1].strip())
                else:
                    entry_price = float(setup.get("analysis", {}).get("current_price", 0))
            except:
                entry_price = float(setup.get("analysis", {}).get("current_price", 0))

            instruction = (
                f"Execute a paper BUY for {symbol}. "
                f"Entry Price: {entry_price}. "
                f"Stop Loss: {plan.get('stop_loss')}. "
                f"Take Profit: {plan.get('take_profit')}. "
                f"Reason: {proposal['reason']}. "
                "Use a conservative size based on my portfolio balance (e.g. 2% risk)."
            )
            
            # Run the agent to perform the execution
            result_holder = [None]
            error_holder = [None]
            
            def run_chat():
                try:
                    result_holder[0] = agent.chat(instruction)
                except Exception as e:
                    error_holder[0] = str(e)
            
            thread = Thread(target=run_chat)
            thread.start()
            
            start_time = time.time()
            while thread.is_alive():
                if (time.time() - start_time) > AGENT_TIMEOUT:
                    break
                
                try:
                    await query.message.chat.send_action("typing")
                except Exception:
                    pass
                
                # Wait or check again
                thread.join(timeout=5)
                
            if error_holder[0]:
                await query.message.reply_text(f"❌ Execution Error: {error_holder[0]}")
            else:
                store.update_proposal(proposal_id, "executed")
                await query.message.reply_text(f"✅ **Trade Executed!**\n\n{result_holder[0]}")
                _save_user_session(chat_id, agent.sid, agent.messages)

    async def _force_agent_action(self, chat_id: int, prompt: str, message: telegram.Message, role: str | None = None):
        """Force the agent to perform an action and reply to the message."""
        if role:
            # Create a temporary agent with the specific role
            agent = Agent(provider=self.provider, user_id=chat_id, role=role)
        else:
            agent = self._get_agent(chat_id)
        
        result_holder = [""]
        def run_agent():
            result_holder[0] = agent.chat(prompt)
            
        thread = Thread(target=run_agent)
        thread.start()
        
        start_time = time.time()
        while thread.is_alive():
            if (time.time() - start_time) > AGENT_TIMEOUT:
                break
                
            try:
                await message.chat.send_action("typing")
            except Exception:
                pass
            
            thread.join(timeout=5)

        if thread.is_alive():
            await message.reply_text(
                f"⚠️ AI Agent is still working after {AGENT_TIMEOUT} seconds. "
                "Try a smaller request or raise TELEGRAM_AGENT_TIMEOUT_SECONDS."
            )
            return
        
        response = self._prepare_telegram_response(result_holder[0] or "⚠️ AI Agent timed out or returned no response.")
        for chunk in self._telegram_chunks(response):
            await message.reply_text(chunk, parse_mode="MarkdownV2", disable_web_page_preview=True)

    async def _handle_image_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle Telegram photo/document image uploads through a narrow vision path."""
        message = update.message
        chat_id = update.effective_chat.id
        prompt = (message.caption or "").strip() or "What is in this image? Give a concise, user-safe summary."

        try:
            image_bytes, mime_type = await self._download_telegram_image(message, context)
        except ValueError as e:
            await message.reply_text(str(e))
            return
        except Exception as e:  # noqa: BLE001
            logger.error("Telegram image download failed: %s", e, exc_info=True)
            await message.reply_text("I could not download that image. Please try a smaller JPG or PNG.")
            return

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        try:
            summary = await asyncio.wait_for(
                asyncio.to_thread(self._analyze_image_bytes, image_bytes, mime_type, prompt),
                timeout=AGENT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            await message.reply_text("Image analysis timed out. Please try a smaller image or a more specific question.")
            return
        except Exception as e:  # noqa: BLE001
            logger.error("Image analysis failed: %s", e, exc_info=True)
            await message.reply_text("I could not analyze that image with the current vision provider.")
            return

        response = self._prepare_telegram_response(summary or "I could not find anything useful in that image.")
        for chunk in self._telegram_chunks(response):
            await message.reply_text(chunk, parse_mode="MarkdownV2", disable_web_page_preview=True)

    async def _handle_unsupported_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("I can analyze image uploads only. Please send a JPG, PNG, or WebP image.")

    async def _download_telegram_image(self, message: telegram.Message, context: ContextTypes.DEFAULT_TYPE) -> tuple[bytes, str]:
        if message.photo:
            photo = message.photo[-1]
            if photo.file_size and photo.file_size > MAX_TELEGRAM_IMAGE_BYTES:
                raise ValueError("That image is too large for this bot to analyze. Please send a smaller image.")
            file = await context.bot.get_file(photo.file_id)
            data = await file.download_as_bytearray()
            return bytes(data), "image/jpeg"

        document = message.document
        if document and document.mime_type and document.mime_type.startswith("image/"):
            if document.file_size and document.file_size > MAX_TELEGRAM_IMAGE_BYTES:
                raise ValueError("That image is too large for this bot to analyze. Please send a smaller image.")
            file = await context.bot.get_file(document.file_id)
            data = await file.download_as_bytearray()
            return bytes(data), document.mime_type

        raise ValueError("I can analyze JPG, PNG, and WebP image uploads only.")

    def _analyze_image_bytes(self, image_bytes: bytes, mime_type: str, prompt: str) -> str:
        if self.provider != ModelProvider.GEMINI:
            return "Image analysis is currently available with the Gemini provider only."
        client = getattr(self, "_vision_client", None)
        if client is None:
            client = create_client(self.provider)
            self._vision_client = client
        if not hasattr(client, "analyze_image"):
            return "Image analysis is currently available with the Gemini provider only."
        return client.analyze_image(image_bytes, mime_type, prompt)

    def _is_chart_request(self, text: str) -> bool:
        return bool(CHART_REQUEST_RE.search(text) and self._extract_chart_symbol(text))

    def _extract_chart_symbol(self, text: str) -> str | None:
        symbol_match = SYMBOL_RE.search(text)
        if symbol_match:
            return symbol_match.group(1).upper()
        lower_text = text.lower()
        for name, symbol in SYMBOL_ALIASES.items():
            if re.search(rf"\b{re.escape(name)}\b", lower_text):
                return symbol
        return None

    def _is_tobyworld_archive_request(self, text: str) -> bool:
        lower_text = text.lower()
        return "tobyworld_master_archive.md" in lower_text or (
            "tobyworld" in lower_text and "voice" in lower_text
        )

    def _is_wake_check(self, text: str) -> bool:
        normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        words = set(normalized.split())
        if not words:
            return False
        wake_words = {"awake", "wake", "alive", "online", "ping", "status", "there", "hello", "hi"}
        return bool(words & wake_words) and len(words) <= 8

    async def _handle_tobyworld_archive_request(self, update: Update) -> None:
        archive_path = Path(__file__).resolve().parents[1] / "workspace" / "tobyworld_master_archive.md"
        try:
            archive_text = archive_path.read_text(encoding="utf-8").strip()
        except OSError:
            await update.message.reply_text("I could not read `workspace/tobyworld_master_archive.md` right now.")
            return

        excerpt = archive_text[:1200].strip()
        if len(archive_text) > len(excerpt):
            excerpt += "\n\n[archive loaded; excerpt trimmed]"

        await update.message.reply_text(
            "Read `workspace/tobyworld_master_archive.md`. Voice context restored.\n\n"
            f"{excerpt}",
            disable_web_page_preview=True,
        )

    def _message_key(self, update: Update) -> tuple[int, int]:
        chat_id = update.effective_chat.id if update.effective_chat else 0
        message_id = update.message.message_id if update.message else 0
        return chat_id, message_id

    def _mark_chart_message_handled(self, message_key: tuple[int, int]) -> None:
        if message_key == (0, 0):
            return
        self._handled_chart_messages.add(message_key)
        if len(self._handled_chart_messages) > 500:
            self._handled_chart_messages = set(list(self._handled_chart_messages)[-250:])

    async def _handle_chart_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
        symbol = self._extract_chart_symbol(text)
        if not symbol:
            await update.message.reply_text("Tell me which symbol to chart, for example: BTC chart.")
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
        try:
            from tools.vision_analysis import generate_price_chart_image

            chart = await asyncio.wait_for(
                asyncio.to_thread(generate_price_chart_image, symbol, 100),
                timeout=60,
            )
        except asyncio.TimeoutError:
            await update.message.reply_text(f"I could not generate the {symbol} chart before timing out.")
            return
        except Exception as e:  # noqa: BLE001
            logger.error("Chart request failed for %s: %s", symbol, e, exc_info=True)
            await update.message.reply_text(f"I could not generate the {symbol} chart right now.")
            return

        if chart.error or not chart.image_bytes:
            await update.message.reply_text(chart.error or f"I could not generate the {symbol} chart right now.")
            return

        photo = io.BytesIO(chart.image_bytes)
        photo.name = f"{symbol.lower()}_chart.png"
        await update.message.reply_photo(photo=photo, caption=f"{symbol} chart")
        return

    async def _run_blocking(self, func, timeout: int = 45) -> str:
        try:
            return await asyncio.wait_for(asyncio.to_thread(func), timeout=timeout)
        except asyncio.TimeoutError:
            return f"Timed out after {timeout}s. Try Refresh Cache or run the command locally."
        except Exception as e:  # noqa: BLE001
            return f"Error: {type(e).__name__}: {e}"

    def _clean_response(self, text: str) -> str:
        """Remove LLM formatting artifacts before sending to Telegram."""
        if not isinstance(text, str):
            text = str(text)

        # 1. Remove common JSON-like or Dict-like wrappers if they leaked into the string
        # Handles {'type': 'text', 'text': '...'} or {"type": "text", "text": "..."}
        text = re.sub(r"\{['\"]type['\"]:\s*['\"]text['\"],\s*['\"]text['\"]:\s*['\"]", "", text)
        
        # 2. Remove trailing markers
        text = re.sub(r"['\"]\}\s*$", "", text)
        text = re.sub(r",?\s*['\"]thought_signature['\"]:\s*None", "", text)
        text = re.sub(r"\[\s*['\"]thought_signature['\"]:\s*None\s*\]", "", text)
        text = re.sub(
            r"\[Tool call recorded without Gemini thought signature:\s*[^\]]+\]\s*",
            "",
            text,
        )
        
        # 3. Fix literal \n strings (backslash + n) into actual newlines
        text = text.replace("\\n", "\n")
        
        # 4. Remove excessive leading/trailing whitespace
        return text.strip()

    def _format_for_telegram(self, text: str) -> str:
        """Shape cleaned agent text into mobile-friendly Telegram output."""
        if not isinstance(text, str):
            text = str(text)

        # Preserve fenced code blocks while cleaning prose around them.
        code_blocks: list[str] = []

        def stash_code_block(match: re.Match) -> str:
            code_blocks.append(match.group(0).strip())
            return f"\n\n__TOADAID_CODE_BLOCK_{len(code_blocks) - 1}__\n\n"

        text = re.sub(r"```[\s\S]*?```", stash_code_block, text)

        # Remove markdown headings and excessive emphasis that tends to render noisily on mobile.
        text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"__(.*?)__", r"\1", text)

        # Normalize bullet styles without touching code blocks.
        text = re.sub(r"^\s*[-*•]\s+", "• ", text, flags=re.MULTILINE)

        # Normalize whitespace.
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
        shaped: list[str] = []
        for paragraph in paragraphs:
            if re.fullmatch(r"__TOADAID_CODE_BLOCK_\d+__", paragraph):
                shaped.append(paragraph)
                continue

            lines = paragraph.split("\n")
            if all(line.lstrip().startswith("• ") for line in lines if line.strip()):
                shaped.append("\n".join(line.strip() for line in lines if line.strip()))
                continue

            # Break long prose paragraphs on sentence boundaries for mobile readability.
            if len(paragraph) <= 420:
                shaped.append(paragraph)
                continue

            sentence_parts = re.split(r"(?<=[.!?。！？])\s+", paragraph)
            current = ""
            for sentence in sentence_parts:
                sentence = sentence.strip()
                if not sentence:
                    continue
                if current and len(current) + len(sentence) + 1 > 320:
                    shaped.append(current.strip())
                    current = sentence
                else:
                    current = f"{current} {sentence}".strip()
            if current:
                shaped.append(current.strip())

        text = "\n\n".join(shaped)

        for idx, block in enumerate(code_blocks):
            text = text.replace(f"__TOADAID_CODE_BLOCK_{idx}__", block)

        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _escape_markdownv2(self, text: str) -> str:
        """Escape special characters for Telegram MarkdownV2."""
        SPECIAL_CHARS = r"\_*[]()~`>#+-=|{}.!"
        for char in SPECIAL_CHARS:
            text = text.replace(char, f"\\{char}")
        return text

    def _prepare_telegram_response(self, text: str) -> str:
        """Apply safety, cleanup, and Telegram-specific formatting in one place."""
        text = self._user_safe_agent_response(text)
        text = self._clean_response(text)
        text = self._format_for_telegram(text)
        return self._escape_markdownv2(text)

    def _user_safe_agent_response(self, text: str) -> str:
        """Block raw tool dumps and artifacts."""
        if not isinstance(text, str):
            text = str(text)

        raw_tool_markers = (
            "Tool result from ",
            "[stdout]",
            "[stderr]",
            "[exit code:",
            "Error executing tool '",
            "assistantReplies[",
        )
        if any(marker in text for marker in raw_tool_markers):
            logger.warning("Blocked artifact from Telegram response")
            return "I could not complete that request safely."

        return text

    def _telegram_chunks(self, text: str, max_len: int = 4090) -> list[str]:
        chunks = []
        while text:
            if len(text) <= max_len:
                chunks.append(text)
                break
            
            # Try to break at newline
            break_point = text.rfind("\n", 0, max_len)
            if break_point == -1:
                break_point = max_len - 100  # Fallback
            
            chunks.append(text[:break_point])
            text = text[break_point:].lstrip()
        
        return chunks

    def _format_message(self, title: str, data: dict) -> str:
        """Format a message with a title and a dictionary of data."""
        message = f"**{title}**\n\n"
        for key, value in data.items():
            if isinstance(value, float):
                value = f"{value:,.2f}"
            elif isinstance(value, int):
                value = f"{value:,}"
            message += f"**{key}:**\t\t`{value}`\n"
        return message

    async def _show_result(self, query, title: str, result: dict, back_callback: str) -> None:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=back_callback)]])
        text = self._format_message(title, result)
        if len(text) <= 4090:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="MarkdownV2", disable_web_page_preview=True)
            return

        await query.edit_message_text(text[:3900] + "\n\n[truncated]", reply_markup=kb, parse_mode="MarkdownV2", disable_web_page_preview=True)
        for i in range(3900, len(text), 4090):
            await query.message.reply_text(text[i:i+4090], parse_mode="MarkdownV2", disable_web_page_preview=True)

    async def _handle_wallet_addresses(self, query, refresh: bool) -> None:
        cache_key = "wallet_addresses"
        cached = self.wallet_cache.get(cache_key)
        if cached and not refresh:
            await query.edit_message_text("📍 Wallet Addresses (cached)", reply_markup=self._main_back_menu())
            await self._send_wallet_address_qrs(query, cached["value"])
            return

        await query.edit_message_text("⌛ Fetching addresses...")
        res = await self._run_blocking(_get_wallet_addresses_text, timeout=45)
        if not res.startswith("Timed out") and not res.startswith("Error"):
            self.wallet_cache[cache_key] = {"value": res, "timestamp": time.time()}
            await query.edit_message_text("📍 Wallet Addresses", reply_markup=self._main_back_menu())
            await self._send_wallet_address_qrs(query, res)
            return
        await self._show_result(query, "📍 Wallet Addresses", {"Addresses": res}, "menu:wallet")

    async def _send_wallet_address_qrs(self, query, wallet_output: str) -> None:
        cards = _parse_wallet_address_cards(wallet_output)
        if not cards:
            await query.message.reply_text(wallet_output[:4090], disable_web_page_preview=True)
            return

        for card in cards:
            image_path = _render_terminal_qr_png(card["qr_lines"], card["address"])
            caption = f"{card['chains']}\n{card['address']}"
            try:
                with open(image_path, "rb") as photo:
                    await query.message.reply_photo(photo=photo, caption=caption[:1024])
            finally:
                try:
                    Path(image_path).unlink(missing_ok=True)
                except OSError:
                    pass

        await query.message.reply_text("Use the Wallet menu to refresh cached addresses.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu:wallet")]]))

    async def _show_trust_price(self, query, symbol: str, chain: str) -> None:
            await query.edit_message_text(f"⌛ Fetching {symbol} price on {chain}...")
            from tools.trust import trust_get_token_price
            res = await self._run_blocking(lambda: trust_get_token_price(token_symbol=symbol, chain=chain), timeout=30)
            await self._show_result(query, f"💹 {symbol} Price", {"Price": res}, "menu:market")

    async def _show_dashboard(self, query):
        chat_id = query.from_user.id
        await query.edit_message_text("⌛ Fetching dashboard...")
        
        data = await self._call_api_candidates([
            ("/api/paper-trading/performance", {"telegram_id": chat_id}),
            (f"/api/paper-trading/statistics/{chat_id}", {}),
            ("/api/portfolio", {"telegram_id": chat_id}),
        ])
        
        if not data.get("success"):
            if "Account not found" in data.get("error", ""):
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("🆕 Create Account", callback_data="action:create_account")]])
                await query.edit_message_text("No trading account found. Create one to start!", reply_markup=kb)
                return
            await query.edit_message_text(f"❌ Error: {data.get('error')}")
            return

        stats = data.get("statistics", data)
        if "balance" in data and "available" in data:
            stats = {
                **data,
                "equity": data.get("balance", 0),
                "total_pnl": 0,
                "win_rate": 0,
                "total_trades": 0,
            }

        dash = (
            "📊 **Trading Dashboard**\n\n"
            f"💰 Equity: `${stats.get('equity', stats.get('total_value', 0)):,.2f}`\n"
            f"📈 Total P&L: `${stats.get('total_pnl', stats.get('total_pnl_percent', 0)):+,.2f}`\n"
            f"🎯 Win Rate: `{stats.get('win_rate', 0):.1f}%`\n"
            f"🔄 Total Trades: `{stats.get('total_trades', 0)}`\n"
            f"🕒 Last Update: `{datetime.now().strftime('%H:%M:%S')}`"
        )
        
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu:main")]])
        await query.edit_message_text(dash, reply_markup=kb, parse_mode="MarkdownV2", disable_web_page_preview=True)

    async def _show_portfolio(self, query):
        chat_id = query.from_user.id
        await query.edit_message_text("⌛ Fetching portfolio...")
        
        data = await self._call_api("/api/portfolio", params={"telegram_id": chat_id})
        
        if not data.get("success"):
            if "Account not found" in data.get("error", ""):
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("🆕 Create Account", callback_data="action:create_account")]])
                await query.edit_message_text("No paper trading account found. Create one to start tracking your portfolio!", reply_markup=kb)
                return
            await query.edit_message_text(f"❌ Error: {data.get('error')}")
            return

        text = ["💼 **Portfolio Holdings**\n"]
        text.append(f"Available Cash: `${data.get('available', 0):,.2f}`\n")
        
        positions = data.get("positions", [])
        if not positions:
            text.append("\n_No open positions._")
        for p in positions:
            text.append(f"• **{p['symbol']}**: {p['quantity']:.4f} @ ${p['entry_price']:.2f} (P&L: ${p['unrealized_pnl']:+,.2f})")
            
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu:main")]])
        await query.edit_message_text("\n".join(text), reply_markup=kb, parse_mode="MarkdownV2", disable_web_page_preview=True)

    def _main_back_menu(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu:main")]])

    def _paper_back_menu(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu:paper")]])

    def _settings_back_menu(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu:settings")]])

    async def _show_trade_menu(self, query):
        await self._show_paper_menu(query)

    async def _show_paper_menu(self, query):
        kb = [
            [InlineKeyboardButton("🆕 Create Account", callback_data="action:create_account")],
            [InlineKeyboardButton("📈 Buy", callback_data="action:quick_buy"),
             InlineKeyboardButton("📉 Sell", callback_data="action:quick_sell")],
            [InlineKeyboardButton("💼 Portfolio", callback_data="view:portfolio"),
             InlineKeyboardButton("📜 Trade History", callback_data="action:paper_history")],
            [InlineKeyboardButton("📊 Strategy PnL", callback_data="action:paper_strategy_pnl")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu:main")]
        ]
        await query.edit_message_text("🧪 Paper Trading\n\nSimulated trades only. No real funds move from this menu.", reply_markup=InlineKeyboardMarkup(kb))

    async def _show_analysis_menu(self, query):
        await self._show_market_menu(query)

    async def _show_market_menu(self, query):
        kb = [
            [InlineKeyboardButton("ETH", callback_data="action:market_price_eth"),
             InlineKeyboardButton("BTC", callback_data="action:market_price_btc"),
             InlineKeyboardButton("SOL", callback_data="action:market_price_sol")],
            [InlineKeyboardButton("💹 Custom Price", callback_data="action:market_price_custom"),
             InlineKeyboardButton("🔎 Search Token", callback_data="action:market_search")],
            [InlineKeyboardButton("💱 Quote Swap", callback_data="action:swap_quote"),
             InlineKeyboardButton("🔥 Trending", callback_data="action:trending")],
            [InlineKeyboardButton("📈 Market Trends", callback_data="action:trends")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu:main")]
        ]
        await query.edit_message_text("💹 Market\n\nLive prices, token search, swap quotes, and market summaries.", reply_markup=InlineKeyboardMarkup(kb))

    async def _show_wallet_menu(self, query):
        kb = [
            [InlineKeyboardButton("ℹ️ Status", callback_data="action:wallet_status"),
             InlineKeyboardButton("📍 Addresses", callback_data="action:wallet_addresses")],
            [InlineKeyboardButton("💰 Portfolio", callback_data="action:wallet_balance"),
             InlineKeyboardButton("⛽ Gas Balances", callback_data="action:wallet_gas")],
            [InlineKeyboardButton("💹 ETH Price", callback_data="action:market_price_eth"),
             InlineKeyboardButton("💱 Quote Swap", callback_data="action:swap_quote")],
            [InlineKeyboardButton("🛡 Token Risk", callback_data="action:token_risk"),
             InlineKeyboardButton("🔄 Refresh Cache", callback_data="action:wallet_refresh")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu:main")]
        ]
        await query.edit_message_text("👛 Wallet\n\nAddresses are cached after the first successful fetch. Live transfers and swaps require typed confirmation.", reply_markup=InlineKeyboardMarkup(kb))

    async def _show_live_menu(self, query):
        kb = [
            [InlineKeyboardButton("💱 Quote Swap", callback_data="action:swap_quote")],
            [InlineKeyboardButton("🛡 Token Risk", callback_data="action:token_risk"),
             InlineKeyboardButton("📜 Tx History", callback_data="action:live_history")],
            [InlineKeyboardButton("⚡ Execute Swap", callback_data="action:live_swap_help"),
             InlineKeyboardButton("📤 Transfer", callback_data="action:live_transfer_help")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu:main")]
        ]
        await query.edit_message_text(
            "⚡ Live Trading\n\nQuote-only actions are available here. Executing swaps or transfers must be typed to the agent with confirmation details.",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    async def _show_risk_menu(self, query):
        kb = [
            [InlineKeyboardButton("🛡 Portfolio Risk", callback_data="action:risk_check")],
            [InlineKeyboardButton("📐 Position Sizing", callback_data="action:position_sizing"),
             InlineKeyboardButton("🧮 Kelly", callback_data="action:kelly")],
            [InlineKeyboardButton("🔎 Token Risk", callback_data="action:token_risk"),
             InlineKeyboardButton("📉 Drawdown", callback_data="action:risk_check")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu:main")]
        ]
        await query.edit_message_text("🛡 Risk\n\nPortfolio limits, token checks, sizing, and conservative Kelly guidance.", reply_markup=InlineKeyboardMarkup(kb))

    async def _show_agent_menu(self, query):
        kb = [
            [InlineKeyboardButton("🧠 Wisdom Ledger", callback_data="action:wisdom_ledger")],
            [InlineKeyboardButton("🧪 Run Backtest", callback_data="action:run_backtest")],
            [InlineKeyboardButton("🎯 Prediction Accuracy", callback_data="action:prediction_accuracy"),
             InlineKeyboardButton("🧭 Market Regime", callback_data="action:market_regime")],
            [InlineKeyboardButton("📝 Record Prediction", callback_data="action:record_prediction")],
            [InlineKeyboardButton("🧭 Trade Plan", callback_data="action:trade_plan"),
             InlineKeyboardButton("👀 Review Positions", callback_data="action:review_positions")],
            [InlineKeyboardButton("📈 Market Trends", callback_data="action:trends"),
             InlineKeyboardButton("🔄 Reset AI", callback_data="action:reset_ai")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu:main")]
        ]
        await query.edit_message_text("🤖 Agent Tools\n\nAsk the AI to analyze, backtest, plan, or review your portfolio.", reply_markup=InlineKeyboardMarkup(kb))

    async def _show_forge_menu(self, query):
        kb = [
            [InlineKeyboardButton("🔎 Contract Check", callback_data="action:forge_contract"),
             InlineKeyboardButton("📝 Record Forecast", callback_data="action:forge_record")],
            [InlineKeyboardButton("📜 Ledger Accuracy", callback_data="action:forge_ledger"),
             InlineKeyboardButton("🧪 Backtest", callback_data="action:forge_backtest")],
            [InlineKeyboardButton("👁 Add Watch", callback_data="action:forge_add_watch"),
             InlineKeyboardButton("📋 List Watches", callback_data="action:forge_list_watches")],
            [InlineKeyboardButton("🚨 Latest Alerts", callback_data="action:forge_alerts"),
             InlineKeyboardButton("▶️ Run Watchlist", callback_data="action:forge_run_watchlist")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu:main")]
        ]
        await query.edit_message_text(
            "🔮 Trend Prediction Forge\n\nContract intelligence, forecast ledger, watchlists, alerts, and backtests.",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    async def _show_settings_menu(self, query):
        kb = [
            [InlineKeyboardButton("📋 Current Settings", callback_data="action:settings_summary")],
            [InlineKeyboardButton("🧪 Mode: Paper / Live", callback_data="action:settings_mode")],
            [InlineKeyboardButton("🔄 Refresh Wallet Cache", callback_data="action:settings_refresh_cache")],
            [InlineKeyboardButton("🔄 Reset AI Session", callback_data="action:reset_ai")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu:main")]
        ]
        await query.edit_message_text("⚙️ Settings\n\nRuntime defaults, cache controls, and safety mode.", reply_markup=InlineKeyboardMarkup(kb))

    async def _show_settings_summary(self, query):
        summary = {
            "Provider": self.provider.value,
            "Backend": self.backend_url,
            "Default chain": "ethereum",
            "Telegram agent timeout": f"{AGENT_TIMEOUT}s",
            "API timeout": f"{API_TIMEOUT}s",
            "Live trading": "confirmation required",
            "Wallet cache entries": len(self.wallet_cache)
        }
        await self._show_result(query, "⚙️ Current Settings", summary, "menu:settings")

    async def _process_market_price(self, update: Update, text: str):
        chat_id = update.effective_chat.id
        try:
            parts = text.split()
            if not parts:
                await update.message.reply_text("Format: TOKEN [chain], e.g. ETH ethereum")
                return
            symbol = parts[0].upper()
            chain = parts[1].lower() if len(parts) > 1 else "ethereum"
            await update.message.reply_text(f"⌛ Fetching {symbol} price on {chain}...")
            from tools.trust import trust_get_token_price
            res = await self._run_blocking(lambda: trust_get_token_price(token_symbol=symbol, chain=chain), timeout=30)
            for i in range(0, len(res), 4090):
                await update.message.reply_text(res[i:i+4090], disable_web_page_preview=True)
        finally:
            self.user_sessions.pop(chat_id, None)

    async def _process_market_search(self, update: Update, text: str):
        chat_id = update.effective_chat.id
        try:
            parts = text.split()
            if not parts:
                await update.message.reply_text("Format: QUERY [chain], e.g. ETH ethereum")
                return
            chain = parts[-1].lower() if len(parts) > 1 and parts[-1].lower() in {"ethereum", "base", "solana", "bitcoin", "bsc", "polygon", "arbitrum"} else "ethereum"
            query = " ".join(parts[:-1]) if chain != "ethereum" or (len(parts) > 1 and parts[-1].lower() == "ethereum") else text
            await update.message.reply_text(f"⌛ Searching {query} on {chain}...")
            from tools.trust import trust_search_token
            res = await self._run_blocking(lambda: trust_search_token(query, chain=chain), timeout=30)
            for i in range(0, len(res), 4090):
                await update.message.reply_text(res[i:i+4090], disable_web_page_preview=True)
        finally:
            self.user_sessions.pop(chat_id, None)

    async def _process_swap_quote(self, update: Update, text: str):
        chat_id = update.effective_chat.id
        try:
            parts = text.split()
            if len(parts) < 4:
                await update.message.reply_text("Format: amount FROM TO chain\nExample: 0.01 ETH USDC ethereum")
                return
            amount, from_token, to_token, chain = parts[0], parts[1].upper(), parts[2].upper(), parts[3].lower()
            await update.message.reply_text(f"⌛ Quoting {amount} {from_token} to {to_token} on {chain}...")
            from tools.trust import trust_get_swap_quote
            res = await self._run_blocking(lambda: trust_get_swap_quote(from_token, to_token, amount, chain=chain), timeout=45)
            for i in range(0, len(res), 4090):
                await update.message.reply_text(res[i:i+4090], disable_web_page_preview=True)
        finally:
            self.user_sessions.pop(chat_id, None)

    async def _process_token_risk(self, update: Update, text: str):
        chat_id = update.effective_chat.id
        try:
            parts = text.split()
            if not parts:
                await update.message.reply_text("Format: ASSET_ID_OR_ADDRESS [chain], e.g. ETH ethereum")
                return
            asset_id = parts[0]
            chain = parts[1].lower() if len(parts) > 1 else "ethereum"
            await update.message.reply_text(f"⌛ Checking risk for {asset_id} on {chain}...")
            from tools.trust_wallet import check_onchain_risk
            res = await self._run_blocking(lambda: check_onchain_risk(asset_id, chain), timeout=45)
            for i in range(0, len(res), 4090):
                await update.message.reply_text(res[i:i+4090], disable_web_page_preview=True)
        finally:
            self.user_sessions.pop(chat_id, None)

    async def _process_record_prediction(self, update: Update, text: str):
        chat_id = update.effective_chat.id
        try:
            parts = text.split()
            if len(parts) < 3:
                await update.message.reply_text("Format: SYMBOL PREDICTED_PRICE CONFIDENCE [HOURS]\nExample: ETH 2600 0.65 24")
                return
            symbol = parts[0].upper()
            predicted_price = float(parts[1])
            confidence = float(parts[2])
            horizon_hours = int(parts[3]) if len(parts) > 3 else 24
            from tools.prediction_tools import record_price_prediction

            res = await self._run_blocking(
                lambda: record_price_prediction(symbol, predicted_price, confidence, horizon_hours=horizon_hours),
                timeout=30,
            )
            await update.message.reply_text(res[:4090], disable_web_page_preview=True)
        finally:
            self.user_sessions.pop(chat_id, None)

    async def _process_forge_contract(self, update: Update, text: str):
        chat_id = update.effective_chat.id
        try:
            parts = text.split()
            if not parts:
                await update.message.reply_text("Format: CONTRACT [chain]\nExample: 0x... base")
                return
            token_address = parts[0]
            chain = parts[1].lower() if len(parts) > 1 else "base"
            await update.message.reply_text(f"⌛ Resolving contract on {chain}...")
            from tools.trend_prediction_tools import forge_live_token_prediction, forge_resolve_contract

            resolved = await self._run_blocking(lambda: forge_resolve_contract(token_address, chain), timeout=45)
            forecast = await self._run_blocking(
                lambda: forge_live_token_prediction(token_address=token_address, chain=chain, horizon="24h", mode="composite"),
                timeout=90,
            )
            await self._send_chunked(update, f"🔎 Contract Resolve\n{resolved}")
            await self._send_chunked(update, f"🔮 Forge Forecast\n{forecast}")
        finally:
            self.user_sessions.pop(chat_id, None)

    async def _process_forge_record(self, update: Update, text: str):
        chat_id = update.effective_chat.id
        try:
            target = self._parse_forge_target(text)
            if not target:
                await update.message.reply_text("Format: ASSET_OR_CONTRACT [chain] [horizon] [mode]\nExample: ETH ethereum 1h composite")
                return
            await update.message.reply_text("⌛ Recording Forge forecast...")
            from tools.trend_prediction_tools import forge_record_live_prediction

            res = await self._run_blocking(
                lambda: forge_record_live_prediction(
                    asset=target["asset"],
                    token_address=target["token_address"],
                    chain=target["chain"],
                    horizon=target["horizon"],
                    mode=target["mode"],
                ),
                timeout=90,
            )
            await self._send_chunked(update, res)
        finally:
            self.user_sessions.pop(chat_id, None)

    async def _process_forge_watch(self, update: Update, text: str):
        chat_id = update.effective_chat.id
        try:
            target = self._parse_forge_target(text)
            if not target:
                await update.message.reply_text("Format: ASSET_OR_CONTRACT [chain] [horizons_csv] [modes_csv]\nExample: ETH ethereum 1h,4h composite,risk")
                return
            horizons = target.get("horizons") or [target["horizon"]]
            modes = target.get("modes") or [target["mode"]]
            await update.message.reply_text("⌛ Adding Forge watch...")
            from tools.trend_prediction_tools import forge_add_watch

            res = await self._run_blocking(
                lambda: forge_add_watch(
                    asset=target["asset"],
                    token_address=target["token_address"],
                    chain=target["chain"],
                    horizons=horizons,
                    modes=modes,
                    user_id=chat_id,
                ),
                timeout=30,
            )
            await self._send_chunked(update, res)
        finally:
            self.user_sessions.pop(chat_id, None)

    async def _process_forge_backtest(self, update: Update, text: str):
        chat_id = update.effective_chat.id
        try:
            parts = text.split()
            if not parts:
                await update.message.reply_text("Format: ASSET [horizon] [mode]\nExample: ETH 24h composite")
                return
            asset = parts[0].upper()
            horizon = parts[1].lower() if len(parts) > 1 else "24h"
            mode = parts[2].lower() if len(parts) > 2 else "composite"
            await update.message.reply_text(f"⌛ Running Forge backtest for {asset}...")
            from tools.trend_prediction_tools import forge_backtest_trend_model

            res = await self._run_blocking(
                lambda: forge_backtest_trend_model(asset=asset, horizon=horizon, mode=mode),
                timeout=120,
            )
            await self._send_chunked(update, res)
        finally:
            self.user_sessions.pop(chat_id, None)

    def _parse_forge_target(self, text: str) -> dict | None:
        parts = text.split()
        if not parts:
            return None

        valid_horizons = {"1h", "4h", "24h", "7d"}
        valid_modes = {"attention", "momentum", "risk", "composite"}
        known_chains = {"base", "ethereum", "eth", "bsc", "polygon", "arbitrum", "optimism", "solana"}

        first = parts[0]
        asset = None
        token_address = None
        chain = "base"
        cursor = 1

        if first.lower().startswith("0x") or len(first) > 32:
            token_address = first
        else:
            asset = first.upper()

        if cursor < len(parts) and parts[cursor].lower() in known_chains:
            chain = parts[cursor].lower()
            cursor += 1

        horizon = "24h"
        mode = "composite"
        horizons = None
        modes = None

        if cursor < len(parts):
            value = parts[cursor].lower()
            if "," in value:
                horizons = [item for item in value.split(",") if item in valid_horizons]
                if horizons:
                    horizon = horizons[0]
                cursor += 1
            elif value in valid_horizons:
                horizon = value
                cursor += 1

        if cursor < len(parts):
            value = parts[cursor].lower()
            if "," in value:
                modes = [item for item in value.split(",") if item in valid_modes]
                if modes:
                    mode = modes[0]
            elif value in valid_modes:
                mode = value

        return {
            "asset": asset,
            "token_address": token_address,
            "chain": chain,
            "horizon": horizon,
            "mode": mode,
            "horizons": horizons,
            "modes": modes,
        }

    async def _send_chunked(self, update: Update, text: str):
        text = self._prepare_telegram_response(text)
        for chunk in self._telegram_chunks(text):
            await update.message.reply_text(chunk, parse_mode="MarkdownV2", disable_web_page_preview=True)

    async def _process_quick_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
        chat_id = update.effective_chat.id
        clear_session = False
        try:
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text(
                    "❌ Format: `SYMBOL AMOUNT`\n"
                    "For BUY, amount is USD, e.g. `BTC 500`.\n"
                    "For SELL, amount is coin quantity, e.g. `BTC 0.01`."
                )
                return

            symbol = parts[0].upper()
            amount = float(parts[1])
            
            if action == "buy":
                await update.message.reply_text(f"⏳ Executing paper BUY for ${amount:,.2f} of {symbol}...")
            else:
                await update.message.reply_text(f"⏳ Executing paper SELL for {amount} {symbol}...")
            
            res = await self._call_api("/api/paper-trading/place-order", "POST", json_data={
                "telegram_id": chat_id,
                "action": action,
                "symbol": symbol,
                "quantity": amount if action == "sell" else None,
                "amount_usd": amount if action == "buy" else None
            })
            
            if res.get("success"):
                order = res.get("order") if isinstance(res.get("order"), dict) else res
                message = self._format_message("✅ Trade Successful!", {
                    "Action": action.upper(),
                    "Symbol": order.get('symbol', symbol),
                    "Quantity": float(order.get('quantity', 0)),
                    "Price": f"${float(order.get('entry_price', order.get('exit_price', 0))):,.2f}",
                    "Total": f"${float(order.get('total', 0)):,.2f}"
                })
                await update.message.reply_text(message, parse_mode="MarkdownV2", disable_web_page_preview=True)
                clear_session = True
            else:
                await update.message.reply_text(f"❌ Trade failed: {res.get('error')}")
                if "Account not found" in str(res.get("error", "")):
                    await update.message.reply_text(
                        "Create a paper account first: Paper Trading -> Create Account.",
                        reply_markup=self._paper_back_menu(),
                    )
                    clear_session = True
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        finally:
            if clear_session:
                self.user_sessions.pop(chat_id, None)

    def run(self) -> None:
        """Start the bot with PID locking."""
        from core.orchestrator import PIDLock
        lock = PIDLock("telegram_bot")
        if not lock.acquire():
            print("❌ Error: Telegram bot is already running. Exiting.")
            sys.exit(1)

        try:
            app = Application.builder().token(self.token).build()
            app.add_handler(CommandHandler("start", self._handle_start))
            app.add_handler(CallbackQueryHandler(self._handle_callback))
            app.add_handler(MessageHandler((filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND, self._handle_image_message))
            app.add_handler(MessageHandler(filters.ATTACHMENT & ~filters.COMMAND, self._handle_unsupported_media))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
            logger.info("Bot starting...")
            app.run_polling(drop_pending_updates=True)
        finally:
            lock.release()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    TelegramBot().run()
