# 🚀 Quick Start Guide - Enhanced Trading Bot

## Installation

```bash
# Install dependencies
pip install python-telegram-bot python-dotenv rich

# Create .env file
cat > .env << EOF
TELEGRAM_BOT_TOKEN=your_token_here
EOF

# Run the bot
python agent_bot_enhanced.py
```

## Basic Usage

### 1. Start the Bot
Send `/start` to your bot in Telegram

### 2. Explore the Menu
Use `/menu` to see all available options:
- 📊 Dashboard - Overview
- 💰 Portfolio - Your holdings
- 📈 Trades - Active positions
- 🔔 Alerts - Notifications
- ⚙️ Settings - Configuration
- 🔍 Price - Check prices
- 🛡️ Security - Token security
- 🔄 Search - Find tokens
- ❓ Help - Support

### 3. Check Token Prices
```
/price PEPE
/price ETH
/price SOL
```

### 4. Search for Tokens
```
/search doge
/search solana
```

### 5. Check Token Security
```
/security SHIB
/security PEPE
```

### 6. Get Swap Quotes
```
/quote USDC ETH 100
/quote PEPE ETH 1000
```

## Dashboard Features

When you view `/dashboard`, you'll see:
- 💰 Portfolio value and PnL
- 📈 Active trades with PnL
- 🔔 Recent alerts
- 🌐 Market status
- 📊 Performance metrics

## Settings Configuration

Use `/settings` to customize:
- **Risk Level** - Low, Medium, High
- **Max Position Size** - Percentage of portfolio
- **Stop Loss** - Percentage
- **Take Profit** - Percentage
- **Alerts** - On/Off for different types

## Quick Commands Reference

| Command | Example | What it Does |
|---------|---------|--------------|
| `/menu` | - | Show main menu |
| `/dashboard` | - | View dashboard |
| `/portfolio` | - | View portfolio |
| `/trades` | - | View trades |
| `/alerts` | - | View alerts |
| `/settings` | - | Configure settings |
| `/price <token>` | `/price PEPE` | Check price |
| `/search <query>` | `/search solana` | Find tokens |
| `/security <token>` | `/security SHIB` | Check security |
| `/quote <from> <to> <amount>` | `/quote USDC ETH 100` | Get swap quote |
| `/help` | - | Show help |

## Tips

1. **Start with Paper Trading** - Set `trading_mode` to Paper Trading in settings
2. **Check Security First** - Always run `/security` before trading
3. **Monitor Alerts** - Stay updated with `/alerts`
4. **Review Dashboard** - Check `/dashboard` regularly
5. **Customize Settings** - Adjust risk levels to your comfort

## Common Issues

**Bot not responding?**
- Check `.env` file has valid token
- Restart the bot

**API errors?**
- Verify internet connection
- Check API key if using advanced features

**Settings not saving?**
- Ensure write permissions for `user_settings.json`

---

**Ready to trade? Just run the bot and start exploring!** 🎉