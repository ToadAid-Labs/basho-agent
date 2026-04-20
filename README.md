# 🤖 AI Trading Bot & Educational Hub

An autonomous, multi-agent AI trading system built for open-source education and treasury management research. Powered by the **ToadAid Mission** for stillness, wisdom, and clarity in the Web3 world.

## 🛡️ ToadAid Vision
This system is designed to guard capital and empower community lore-keepers through institutional-grade AI analysis. Read our mission statement in [TOADAID.md](./TOADAID.md).

## 🚀 Advanced Features

- 🧠 **Autonomous Worker System** - Specialized roles for Research, Execution, and Risk Management.
- 🦉 **Agent Wisdom Ledger** - Long-term memory that extracts and follows trading "Commandments."
- 📐 **Swing Trading Architect** - Automated Fibonacci, RSI Divergence, and ATR-based trade planning.
- 🎓 **Agent Tutor Mode** - A dedicated role to explain technical indicators and bot logic to users.
- 🛡️ **Rug-Pull Auditor** - Deep smart contract security scanning via GoPlus API.
- 🔔 **Intelligent Alerts** - Proactive background watchers for price, sentiment, and whale moves.
- 📱 **Telegram Integration** - Full-featured bot menu for portfolio management and trade execution.
- 📊 **Advanced WebUI** - Real-time wisdom feed and forecast accuracy charts.

## Prerequisites

- Python 3.9 or higher
- npm/node.js (for Trust Wallet Agent Skills)
- Telegram account
- Trust Wallet Agent Skills account (free at https://portal.trustwallet.com)

## Installation

### 1. Install Python Dependencies

```bash
cd trading-bot
pip install -r requirements.txt
```

### 2. Install Trust Wallet Agent Skills

```bash
npm install -g @trustwallet/cli @coinbase/cdp-sdk
```

### 3. Set Up Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```bash
# Trust Wallet API Credentials (free at https://portal.trustwallet.com)
TWAK_ACCESS_ID=your_access_id_here
TWAK_HMAC_SECRET=your_hmac_secret_here

# Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Admin IDs (optional, comma-separated list of user IDs)
ADMIN_IDS=123456789
```

**How to get credentials:**

1. **Trust Wallet API Keys:**
   - Visit https://portal.trustwallet.com
   - Create a free account
   - Generate API keys in your dashboard

2. **Telegram Bot Token:**
   - Message @BotFather on Telegram
   - Send `/newbot` command
   - Follow the instructions to create your bot
   - Copy the bot token

3. **Your Telegram User ID (for admin):**
   - Message @userinfobot on Telegram
   - The bot will reply with your user ID

## Usage

### Run the Bot

```bash
python agent_bot.py
```

### Bot Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Start the bot and show welcome message | `/start` |
| `/help` | Show all available commands | `/help` |
| `/price <token>` | Get current token price | `/price USDC` |
| `/search <query>` | Search for tokens | `/search pepe` |
| `/quote <from> <to> <amount>` | Get swap quote | `/quote ETH USDC 1` |
| `/security <token>` | Check token security | `/security PEPE` |
| `/convert <from> <to> <amount>` | Get conversion quote | `/convert USDC ETH 100` |

### Usage Examples

```bash
# Check USDC price
/price USDC

# Search for PEPE token
/search pepe

# Get swap quote for 1 ETH to USDC
/quote ETH USDC 1

# Check if PEPE is safe to trade
/security PEPE

# Convert 100 USDC to ETH
/convert USDC ETH 100
```

## Supported Networks

The bot currently supports trading on:
- **Base** (default)
- Ethereum
- Polygon
- Binance Smart Chain

To change the network, modify the `chain` parameter in the code or add network selection functionality.

## Project Structure

```
trading-bot/
├── agent_bot.py          # Main Telegram bot application
├── tools/
│   └── trust.py         # Trust Wallet API client
├── .env.example         # Environment variables template
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Development

### Adding New Features

1. Add new command handler in `agent_bot.py` using `async def handler(self, update, context):`
2. Register the handler with `application.add_handler(CommandHandler("command", handler))`
3. Update the help message with the new command

### Extending the API Client

Add new methods to the `TrustWalletAPI` class in `tools/trust.py`:

```python
def new_method(self, param1: str, param2: str) -> Dict[str, Any]:
    """Your new API method"""
    return self._request("GET", "/endpoint", params={"param1": param1, "param2": param2})
```

## Error Handling

The bot includes comprehensive error handling:

- Invalid token symbols
- API connection issues
- Network timeouts
- Missing parameters
- Token not found

All errors are logged to the console and sent to the user via Telegram.

## Security Best Practices

⚠️ **Important:**

1. **Never commit your `.env` file** - It contains sensitive credentials
2. **Keep your API keys secure** - Don't share them publicly
3. **Use VPN** when accessing the API if you're in a restricted region
4. **Always do your own research** - The bot provides data, not financial advice
5. **Start with small amounts** when testing new tokens
6. **Check token security** before trading

## Troubleshooting

### Bot not starting

- Check that all required environment variables are set in `.env`
- Verify your Telegram bot token is correct
- Ensure Python dependencies are installed

### API not working

- Verify your Trust Wallet API keys are valid
- Check that your account has API access enabled
- Try accessing https://portal.trustwallet.com to verify your account

### Token not found

- Try searching with the full name or symbol
- Ensure the token is available on the selected network (Base, Ethereum, etc.)
- Check that you're using the correct token format

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is provided as-is for educational and research purposes.

## Disclaimer

⚠️ **This bot is for educational purposes only.**

- Not financial advice
- Always DYOR (Do Your Own Research)
- Cryptocurrency trading carries significant risk
- The authors are not responsible for any financial losses

Use at your own risk. Never trade more than you can afford to lose.
