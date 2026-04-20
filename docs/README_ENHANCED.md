# Enhanced Trading Agent Bot 🤖

A powerful, menu-driven Telegram trading bot built with the TrustWallet API and Telegram Bot API.

## 🌟 Features

### Core Trading Capabilities
- **Real-time Token Prices** - Check prices for any token instantly
- **Token Search** - Search and discover tokens
- **Swap Quotes** - Get swap quotes between tokens
- **Security Checks** - Verify token security (honeypot detection, liquidity, rug pull risk)

### Dashboard & Monitoring
- **Live Dashboard** - Overview of portfolio, trades, and market status
- **Portfolio Tracking** - Monitor all your holdings and performance
- **Active Trades** - View and manage open positions
- **Trade History** - Track all past trades with PnL
- **System Alerts** - Real-time notifications for price changes, trade alerts, and risks

### Menu System
Full navigation with inline buttons for easy access:
- 📊 Dashboard - Overview of everything
- 💰 Portfolio - Your holdings and performance
- 📈 Trades - Active and closed positions
- 🔔 Alerts - System notifications
- ⚙️ Settings - Configure preferences
- 🔍 Price - Check token prices
- 🛡️ Security - Token security checks
- 🔄 Search - Find tokens
- ❓ Help - Full help documentation

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Telegram Bot Token (from @BotFather)
- TrustWallet API Key (optional, for real trading data)

### Installation

1. Clone or download this repository:
```bash
cd trading-bot
```

2. Install dependencies:
```bash
pip install python-telegram-bot python-dotenv rich
```

3. Create a `.env` file with your configuration:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
# ADMIN_IDS=123456789,987654321  # Optional: comma-separated admin IDs
```

4. Get a Telegram Bot Token:
   - Message @BotFather on Telegram
   - Send `/newbot` command
   - Follow the instructions to create your bot
   - Copy the token to your `.env` file

5. Run the bot:
```bash
python agent_bot_enhanced.py
```

## 📖 Usage

### Basic Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and bot introduction |
| `/menu` | Show main menu with all options |
| `/dashboard` | View dashboard overview |
| `/portfolio` | View your portfolio status |
| `/trades` | View active and closed trades |
| `/alerts` | View system alerts |
| `/settings` | Configure bot settings |

### Trading Commands

| Command | Description |
|---------|-------------|
| `/price <token>` | Check token price (e.g., `/price PEPE`) |
| `/search <query>` | Search for tokens (e.g., `/search doge`) |
| `/security <token>` | Check token security (e.g., `/security SHIB`) |
| `/quote <from> <to> <amount>` | Get swap quote (e.g., `/quote USDC ETH 100`) |

### Example Usage

```bash
# Check menu
/menu

# View dashboard
/dashboard

# Check PEPE price
/price PEPE

# Search for tokens
/search solana

# Check SHIB security
/security SHIB

# Get swap quote
/quote USDC ETH 100
```

## ⚙️ Configuration

### Environment Variables

- `TELEGRAM_BOT_TOKEN` (required) - Your bot token from @BotFather
- `ADMIN_IDS` (optional) - Comma-separated list of admin user IDs
- `TRUSTWALLET_API_KEY` (optional) - For enhanced API access

### User Settings

The bot saves user preferences in `user_settings.json`:
- Trading preferences (risk level, position sizes)
- Alert settings
- User account preferences

## 🎨 Dashboard Features

### Portfolio Overview
- Total balance and PnL
- Active trades count
- Win rate statistics
- Token diversification

### Active Trades
- Real-time trade positions
- Entry and current prices
- PnL (profit/loss) with percentage
- Trade status (open/closed)

### Alerts System
- Price change alerts
- Trade completion alerts
- Risk and security alerts
- System performance alerts

## 📊 Statistics

The bot tracks and displays:
- Total trades executed
- Win rate percentage
- Total profit and losses
- Best and worst trades
- Performance metrics (Sharpe ratio, max drawdown)

## 🔒 Security

### Token Security Checks
- Honeypot detection
- Liquidity lock verification
- Rug pull risk assessment
- Sellability analysis
- Contract audit status

### Trading Safety
- Paper trading mode
- Risk level configuration
- Stop-loss and take-profit settings
- Max position size limits

## 🛠️ Development

### Project Structure
```
agent/
├── agent_bot_enhanced.py    # Main bot file
├── tools/
│   └── trust.py            # TrustWallet API wrapper
├── user_settings.json      # User preferences (auto-generated)
├── .env                    # Configuration file
└── README_ENHANCED.md      # This file
```

### Adding New Features

1. Add a new command handler in `agent_bot_enhanced.py`
2. Update the menu keyboard with new buttons
3. Create corresponding callback handler
4. Add help documentation

### Example: Adding a New Command

```python
async def my_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom command"""
    message = "Your custom message here"
    await update.message.reply_text(message)

# Add to main():
# application.add_handler(CommandHandler("mycommand", bot.my_command))

# Add to menu keyboard
keyboard.append([InlineKeyboardButton("My Feature", callback_data="myfeature")])
```

## 🐛 Troubleshooting

### Bot Not Responding
- Check that `TELEGRAM_BOT_TOKEN` is set correctly
- Verify the bot token is active and not expired
- Check for Python errors in the console output

### API Errors
- Ensure `TRUSTWALLET_API_KEY` is configured if using advanced features
- Check internet connection for API calls
- Verify API key permissions

### User Settings Not Saving
- Check file permissions for `user_settings.json`
- Ensure the bot has write access to the directory

## 📈 Customization

### Theme and Colors
- Modify color codes in `_generate_*_view()` methods
- Use rich console colors (red, green, yellow, cyan, etc.)

### Alert Messages
- Customize alert messages in `_generate_alerts_view()`
- Add new alert types as needed

### Trading Parameters
- Adjust risk levels and position sizes
- Set custom stop-loss and take-profit thresholds

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests
- Improve documentation

## 📝 License

This project is open source and available under the MIT License.

## 📧 Support

For support and questions:
- Check the `/help` command in the bot
- Review the documentation
- Contact the development team

## 🌟 Highlights

- **Menu-Driven Interface** - Intuitive navigation with inline buttons
- **Rich UI** - Beautiful terminal-style dashboard with colored output
- **Real-Time Data** - Live token prices and market data
- **Security Focused** - Comprehensive token security checks
- **Portfolio Tracking** - Full portfolio and trade management
- **Alert System** - Customizable notifications
- **Easy Configuration** - Simple setup and customization

---

**Built with ❤️ using Python, Telegram Bot API, and Rich for beautiful console output**

**Ready to start trading? Run the bot and explore all the features!** 🚀
