import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import os
import json
from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes

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
