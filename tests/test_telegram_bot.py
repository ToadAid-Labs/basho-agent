import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import os
import json
from types import SimpleNamespace
from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes, ApplicationHandlerStop

# Mock the environment variable before importing TelegramBot
os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:ABCDEFGH"

try:
    from core.telegram_bot import TelegramBot
except ModuleNotFoundError as exc:  # pragma: no cover - optional integration dependency
    raise unittest.SkipTest(f"telegram bot module unavailable: {exc}")
from core.provider import ModelProvider

class TestTelegramBot(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = TelegramBot(provider=ModelProvider.OLLAMA)
        self.chat_id = 123456789

    def test_get_main_menu(self):
        """Test if the main menu keyboard is generated correctly."""
        markup = self.bot._get_main_menu()
        self.assertIsNotNone(markup)
        # Check if "📊 Dashboard" button exists
        buttons = []
        for row in markup.inline_keyboard:
            for button in row:
                buttons.append(button.text)
        self.assertIn("📊 Dashboard", buttons)
        self.assertIn("👛 Wallet", buttons)
        self.assertIn("🔮 Forge", buttons)

    def test_forge_target_parser_symbol_and_contract(self):
        symbol_target = self.bot._parse_forge_target("ETH ethereum 1h composite")
        contract_target = self.bot._parse_forge_target("0xabc base 1h,24h composite,risk")

        self.assertEqual(symbol_target["asset"], "ETH")
        self.assertIsNone(symbol_target["token_address"])
        self.assertEqual(symbol_target["chain"], "ethereum")
        self.assertEqual(symbol_target["horizon"], "1h")
        self.assertEqual(symbol_target["mode"], "composite")

        self.assertIsNone(contract_target["asset"])
        self.assertEqual(contract_target["token_address"], "0xabc")
        self.assertEqual(contract_target["chain"], "base")
        self.assertEqual(contract_target["horizons"], ["1h", "24h"])
        self.assertEqual(contract_target["modes"], ["composite", "risk"])

    async def test_show_forge_menu(self):
        query = AsyncMock()

        await self.bot._show_forge_menu(query)

        query.edit_message_text.assert_awaited_once()
        args, kwargs = query.edit_message_text.call_args
        self.assertIn("Trend Prediction Forge", args[0])
        buttons = [button.text for row in kwargs["reply_markup"].inline_keyboard for button in row]
        self.assertIn("🔎 Contract Check", buttons)
        self.assertIn("👁 Add Watch", buttons)
        self.assertIn("🚨 Latest Alerts", buttons)

    def test_chart_request_detection(self):
        self.assertTrue(self.bot._is_chart_request("pull a BTC chart and show me brother"))
        self.assertEqual(self.bot._extract_chart_symbol("show bitcoin chart"), "BTC")
        self.assertFalse(self.bot._is_chart_request("what is BTC doing?"))

    def test_user_safe_agent_response_blocks_raw_tool_output(self):
        response = self.bot._user_safe_agent_response("Tool result from bash:\n[stdout]\nsecret")

        self.assertIn("could not complete", response)
        self.assertNotIn("[stdout]", response)

    def test_clean_response_strips_gemini_unsigned_tool_markers(self):
        response = self.bot._clean_response(
            "[Tool call recorded without Gemini thought signature: read_strategy]"
            "[Tool call recorded without Gemini thought signature: read_strategy]"
            "Refreshed. Memory restored."
        )

        self.assertEqual(response, "Refreshed. Memory restored.")

    async def test_tobyworld_archive_request_bypasses_agent(self):
        update = MagicMock(spec=Update)
        update.effective_chat.id = self.chat_id
        update.message = AsyncMock(spec=Message)
        update.message.message_id = 7
        update.message.text = "brother, read your tobyworld_master_archive.md to get your voice back"
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        self.bot._get_agent = MagicMock(side_effect=AssertionError("generic agent path should not run"))

        await self.bot._handle_message(update, context)

        self.bot._get_agent.assert_not_called()
        update.message.reply_text.assert_awaited_once()
        self.assertIn("Voice context restored", update.message.reply_text.call_args.args[0])

    async def test_wake_check_bypasses_agent(self):
        update = MagicMock(spec=Update)
        update.effective_chat.id = self.chat_id
        update.message = AsyncMock(spec=Message)
        update.message.message_id = 8
        update.message.text = "wake up brother"
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        self.bot._get_agent = MagicMock(side_effect=AssertionError("generic agent path should not run"))

        await self.bot._handle_message(update, context)

        self.bot._get_agent.assert_not_called()
        update.message.reply_text.assert_awaited_once_with(
            "Awake. Telegram is connected and the bot process is running."
        )

    async def test_agent_creation_error_replies_after_working_status(self):
        update = MagicMock(spec=Update)
        update.effective_chat.id = self.chat_id
        update.message = AsyncMock(spec=Message)
        update.message.message_id = 9
        update.message.text = "No tools for this one. Reply in one short sentence: what is 2 + 2?"
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot.send_chat_action = AsyncMock()
        self.bot._get_agent = MagicMock(side_effect=ValueError("Gemini OAuth needs reauthentication."))

        await self.bot._handle_message(update, context)

        self.bot._get_agent.assert_called_once_with(self.chat_id)
        self.assertEqual(update.message.reply_text.await_count, 2)
        self.assertEqual(update.message.reply_text.await_args_list[0].args[0], "⌛ Working on that...")
        self.assertIn("Gemini OAuth needs reauthentication", update.message.reply_text.await_args_list[1].args[0])

    @patch("core.telegram_bot.Agent")
    @patch("core.telegram_bot.os.path.exists")
    @patch("core.telegram_bot.get_provider")
    def test_gemini_reauth_falls_back_to_codex_when_available(self, mock_get_provider, mock_exists, mock_agent):
        mock_get_provider.return_value = ModelProvider.GEMINI
        mock_exists.return_value = True
        mock_agent.side_effect = [
            ValueError("Gemini OAuth needs reauthentication."),
            MagicMock(provider=ModelProvider.OPENAI_CODEX),
        ]

        bot = TelegramBot(provider=None)
        agent = bot._get_agent(self.chat_id)

        self.assertEqual(agent.provider, ModelProvider.OPENAI_CODEX)
        self.assertEqual(bot.provider, ModelProvider.OPENAI_CODEX)

    @patch("tools.vision_analysis.generate_price_chart_image")
    async def test_handle_chart_request_sends_photo(self, mock_chart):
        mock_chart.return_value = SimpleNamespace(symbol="BTC", image_bytes=b"png-bytes", error=None)
        update = MagicMock(spec=Update)
        update.effective_chat.id = self.chat_id
        update.message = AsyncMock(spec=Message)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot.send_chat_action = AsyncMock()

        await self.bot._handle_chart_request(update, context, "pull a BTC chart and show me")

        update.message.reply_photo.assert_awaited_once()
        update.message.reply_text.assert_not_called()

    async def test_handle_message_chart_request_stops_after_fast_path(self):
        update = MagicMock(spec=Update)
        update.effective_chat.id = self.chat_id
        update.message = AsyncMock(spec=Message)
        update.message.message_id = 42
        update.message.text = "pull a BTC chart and show me"
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot.send_chat_action = AsyncMock()

        self.bot._handle_chart_request = AsyncMock()
        self.bot._get_agent = MagicMock(side_effect=AssertionError("generic agent path should not run"))

        with self.assertRaises(ApplicationHandlerStop):
            await self.bot._handle_message(update, context)

        self.bot._handle_chart_request.assert_awaited_once_with(update, context, update.message.text)
        self.bot._get_agent.assert_not_called()
        update.message.reply_text.assert_not_called()

    async def test_duplicate_chart_message_is_ignored(self):
        update = MagicMock(spec=Update)
        update.effective_chat.id = self.chat_id
        update.message = AsyncMock(spec=Message)
        update.message.message_id = 99
        update.message.text = "pull a BTC chart and show me"
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        self.bot._mark_chart_message_handled((self.chat_id, 99))
        self.bot._handle_chart_request = AsyncMock()

        with self.assertRaises(ApplicationHandlerStop):
            await self.bot._handle_message(update, context)

        self.bot._handle_chart_request.assert_not_called()
        update.message.reply_text.assert_not_called()

    @patch("tools.vision_analysis.generate_price_chart_image")
    async def test_handle_chart_request_failure_fails_closed(self, mock_chart):
        mock_chart.return_value = SimpleNamespace(symbol="BTC", image_bytes=None, error="Chart rendering requires `mplfinance`.")
        update = MagicMock(spec=Update)
        update.effective_chat.id = self.chat_id
        update.message = AsyncMock(spec=Message)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot.send_chat_action = AsyncMock()

        await self.bot._handle_chart_request(update, context, "pull a BTC chart and show me")

        update.message.reply_text.assert_awaited_once_with("Chart rendering requires `mplfinance`.")
        update.message.reply_photo.assert_not_called()

    @patch("requests.get")
    async def test_call_api_get_success(self, mock_get):
        """Test successful GET API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": "test"}
        mock_get.return_value = mock_response

        result = await self.bot._call_api("/test", method="GET")
        self.assertEqual(result, {"success": True, "data": "test"})

    @patch("requests.post")
    async def test_call_api_post_failure(self, mock_post):
        """Test failed POST API call."""
        import requests
        mock_post.side_effect = requests.exceptions.RequestException("Connection error")

        result = await self.bot._call_api("/test", method="POST", json_data={"key": "val"})
        self.assertIn("error", result)
        self.assertFalse(result.get("success", True))

    async def test_handle_start(self):
        """Test /start command handler."""
        update = MagicMock(spec=Update)
        update.message = AsyncMock(spec=Message)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        await self.bot._handle_start(update, context)
        
        # Verify reply_text was called
        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("AI Crypto Trading Bot", args[0])
        self.assertIsNotNone(kwargs.get("reply_markup"))

    @patch("core.telegram_bot.TelegramBot._call_api", new_callable=AsyncMock)
    async def test_process_quick_trade_buy(self, mock_call_api):
        """Test quick trade buy logic."""
        update = MagicMock(spec=Update)
        update.effective_chat.id = self.chat_id
        update.message = AsyncMock(spec=Message)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        
        mock_call_api.return_value = {
            "success": True,
            "order": {"entry_price": 50000, "total": 1000}
        }

        # Simulate user entering "BTC 1000"
        await self.bot._process_quick_trade(update, context, "buy", "BTC 1000")

        # Verify API was called with correct parameters
        mock_call_api.assert_called_with(
            "/api/paper-trading/place-order",
            "POST",
            json_data={
                "telegram_id": self.chat_id,
                "action": "buy",
                "symbol": "BTC",
                "quantity": None,
                "amount_usd": 1000.0
            }
        )
        # Verify success message
        update.message.reply_text.assert_called()
        self.assertIn("Trade Successful", update.message.reply_text.call_args_list[-1][0][0])

if __name__ == "__main__":
    unittest.main()
