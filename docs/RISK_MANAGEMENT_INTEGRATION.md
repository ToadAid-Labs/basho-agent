# Risk Management Module - Integration Guide

This document explains how the Risk Management module integrates with the overall Trust Wallet Trading Bot system.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Trust Wallet Trading Bot                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐       │
│  │ Trust       │    │ Market Data  │    │   Risk          │       │
│  │ Wallet      │───>│ Analyzer     │───>│ Management      │       │
│  │ API Client  │    │              │    │ Module          │       │
│  └─────────────┘    └──────────────┘    └──────────────────┘       │
│        │                  │                  │                      │
│        ▼                  ▼                  ▼                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                    Telegram Bot Interface                  │       │
│  │  - Position alerts                                        │       │
│  │  - Risk status updates                                    │       │
│  │  - Trading controls                                      │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Module Dependencies

### Required Modules

1. **Trust Wallet API Client** (`tools/trust.py`)
   - Handles wallet balance
   - Current prices
   - Execute trades
   - Transaction history

2. **Market Data Analyzer** (`tools/market_data.py`)
   - Technical analysis
   - Market trends
   - Volatility assessment

### Module Relationships

```
RiskManager ───> TrustWalletAgent
                │
                ├──> get_wallet_balance()
                ├──> get_current_price(token)
                ├──> execute_trade(token, amount)
                └──> get_transaction_history()

RiskManager ───> MarketDataAnalyzer
                │
                ├──> get_technical_signals()
                ├──> get_market_trend()
                └──> get_volatility_score()
```

## Integration with Main Bot

### 1. Initialization

```python
# In main.py or bot setup
from tools.trust import TrustWalletAgent
from tools.market_data import MarketDataAnalyzer
from risk_management import RiskManager, RiskLevel
from telegram_bot import TelegramBot

# Initialize components
trust_wallet = TrustWalletAgent(access_id, hmac_secret)
market_analyzer = MarketDataAnalyzer()
risk_manager = RiskManager(trust_wallet, market_analyzer)
telegram_bot = TelegramBot(risk_manager)

# Set initial risk level
risk_manager.set_risk_level(RiskLevel.MEDIUM)
```

### 2. In the Trading Loop

```python
import asyncio
from datetime import datetime

async def trading_loop(risk_manager, market_analyzer):
    """Main trading loop with risk controls"""

    while True:
        try:
            # 1. Get market signals
            signals = market_analyzer.analyze_market()

            # 2. For each signal
            for signal in signals:
                # 3. Validate with risk manager
                is_valid, message, params = risk_manager.validate_entry(
                    token_address=signal['token'],
                    entry_price=signal['price'],
                    target_position_size=signal['target_size'],
                    stop_loss_pct=signal['stop_loss'],
                    take_profit_pct=signal['take_profit']
                )

                if is_valid:
                    # 4. Open position
                    result = risk_manager.open_position(
                        token_address=signal['token'],
                        entry_price=signal['price'],
                        position_size=params['position_size'],
                        stop_loss_pct=params['stop_loss'],
                        take_profit_pct=params['take_profit']
                    )

                    if result['success']:
                        # 5. Notify via Telegram
                        telegram_bot.notify_position_opened(
                            position=result['position'],
                            metrics=risk_manager.get_current_metrics()
                        )

            # 6. Check and manage positions
            management = risk_manager.check_and_manage_positions()

            if management['closed_positions']:
                telegram_bot.notify_position_closed(
                    positions=management['closed_positions']
                )

            # 7. Send periodic status update
            if datetime.now().minute == 0:
                telegram_bot.send_status_update(
                    metrics=risk_manager.get_current_metrics(),
                    diversification=risk_manager.get_diversification_score()
                )

            # 8. Sleep for next check
            await asyncio.sleep(60)  # 1 minute

        except Exception as e:
            print(f"Error in trading loop: {e}")
            await asyncio.sleep(60)
```

### 3. Telegram Integration

```python
from telegram_bot import TelegramBot

class TelegramBot:
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
        self.setup_handlers()

    def setup_handlers(self):
        """Setup Telegram message handlers"""

        # Position opened
        @self.bot.message_handler(commands=['position'])
        def handle_position_status(message):
            positions = self.risk_manager.get_all_positions()
            self.send_positions_list(positions, message.chat.id)

        # Risk metrics
        @self.bot.message_handler(commands=['risk'])
        def handle_risk_status(message):
            metrics = self.risk_manager.get_current_metrics()
            self.send_risk_report(metrics, message.chat.id)

        # Diversification
        @self.bot.message_handler(commands=['diversify'])
        def handle_diversification(message):
            score = self.risk_manager.get_diversification_score()
            self.send_diversification_report(score, message.chat.id)

        # Set risk level
        @self.bot.message_handler(commands=['risk_level'])
        def handle_risk_level(message):
            # Parse level from command
            parts = message.text.split()
            if len(parts) > 1:
                level = parts[1].upper()
                if level in ['LOW', 'MEDIUM', 'HIGH']:
                    self.risk_manager.set_risk_level(level)
                    self.send_message(
                        f"✓ Risk level set to {level}",
                        message.chat.id
                    )
                else:
                    self.send_message(
                        "Invalid risk level. Use LOW, MEDIUM, or HIGH.",
                        message.chat.id
                    )

    def notify_position_opened(self, position, metrics):
        """Send notification when position is opened"""
        message = (
            f"📈 Position Opened:\n"
            f"Token: {position['token_address']}\n"
            f"Entry: ${position['entry_price']:.6f}\n"
            f"Size: {position['amount']:.6f}\n"
            f"Stop Loss: ${position['stop_loss']:.6f}\n"
            f"Take Profit: ${position['take_profit']:.6f}\n"
            f"Position Value: ${position['position_value']:.2f}"
        )
        self.send_message(message, self.chat_id)

    def notify_position_closed(self, positions):
        """Send notification when position is closed"""
        message = f"Position(s) closed:\n"
        for pos in positions:
            message += f"  {pos['token_address']}: PnL = ${pos['pnl']:.2f}\n"
        self.send_message(message, self.chat_id)

    def send_status_update(self, metrics, diversification):
        """Send periodic status update"""
        message = (
            f"📊 Portfolio Status Update:\n"
            f"Total Value: ${metrics.total_portfolio_value:.2f}\n"
            f"Daily PnL: ${metrics.daily_pnl:.2f} ({metrics.daily_pnl_pct:.2f}%)\n"
            f"Active Positions: {diversification['active_positions']}\n"
            f"Diversification Score: {diversification['diversification_score']:.2f}"
        )
        self.send_message(message, self.chat_id)
```

## Event Flow

### Trade Execution Flow

```
1. Market Signal Generated
   └─> Market Data Analyzer
       └─> Technical Analysis
           └─> Trading Opportunity Found

2. Risk Validation
   └─> Risk Manager
       ├─> Position Sizing Check
       ├─> Diversification Check
       ├─> Daily Loss Limit Check
       ├─> Drawdown Limit Check
       ├─> Risk-Reward Validation
       └─> Calculate Parameters

3. Position Opening
   └─> Risk Manager
       └─> Create Position Record
       └─> Calculate Stop Loss/Take Profit
       └─> Save to Database

4. Execution
   └─> Trust Wallet Agent
       ├─> Get Current Price
       ├─> Execute Buy Trade
       └─> Record Transaction

5. Monitoring
   └─> Risk Manager
       ├─> Track Position
       ├─> Monitor Price
       ├─> Check Stop Loss/Take Profit
       └─> Trigger Exits if Needed

6. Notification
   └─> Telegram Bot
       ├─> Position Opened
       ├─> Price Alert
       ├─> Position Closed
       └─> Status Update
```

## Data Flow

### Data Sources

1. **Trust Wallet**
   - Wallet balance
   - Current prices
   - Transaction results

2. **Market Data**
   - Price history
   - Technical indicators
   - Market signals

### Data Storage

```python
# Position storage (in-memory)
active_positions = {
    position_id: {
        'token_address': str,
        'entry_price': float,
        'amount': float,
        'stop_loss': float,
        'take_profit': float,
        'position_value': float,
        'open_time': datetime,
        'pnl': float
    }
}

# Trade history (in-memory, could be extended to database)
trade_history = {
    trade_id: {
        'token_address': str,
        'entry_price': float,
        'exit_price': float,
        'position_size': float,
        'pnl': float,
        'timestamp': datetime,
        'strategy': str
    }
}
```

## Error Handling

### Error Propagation

```
Market Signal
    │
    ├─> Invalid Token
    │   └─> Log Error, Skip Signal
    │
    ├─> Missing Price Data
    │   └─> Log Error, Skip Signal
    │
    └─> Risk Validation Failed
        └─> Log Error, Skip Signal

Position Open
    │
    ├─> Insufficient Balance
    │   └─> Log Error, Notify
    │
    ├─> Price Deviation
    │   └─> Log Warning, Adjust
    │
    └─> Execution Failed
        └─> Log Error, Notify

Position Monitor
    │
    ├─> Price Data Error
    │   └─> Log Warning, Continue
    │
    ├─> Stop Loss Triggered
    │   └─> Execute Exit, Notify
    │
    └─> Take Profit Triggered
        └─> Execute Exit, Notify
```

## Performance Monitoring

### Key Metrics to Track

1. **Position Management**
   - Number of active positions
   - Average position size
   - Position concentration

2. **Risk Metrics**
   - Daily PnL percentage
   - Drawdown level
   - Risk-reward ratio

3. **Performance**
   - Win rate
   - Average R:R
   - Trade frequency

4. **System Health**
   - API response times
   - Error rate
   - Position monitoring uptime

### Monitoring Code

```python
def monitor_system_performance(risk_manager):
    """Monitor system performance and health"""

    metrics = risk_manager.get_current_metrics()

    # Check if running within limits
    if metrics.daily_pnl_pct < -0.5:
        print("⚠️ Warning: Daily PnL approaching loss limit")

    if metrics.max_drawdown > 8.0:
        print("⚠️ Warning: Drawdown approaching limit")

    # Check diversification
    diversification = risk_manager.get_diversification_score()
    if not diversification['is_diversified']:
        print("⚠️ Warning: Portfolio concentration high")

    # Log system health
    print(f"📊 System Health:")
    print(f"   - Positions: {len(risk_manager.active_positions)}")
    print(f"   - Active: {metrics.total_portfolio_value:.2f}")
    print(f"   - Errors: {0}")  # Track error count
    print(f"   - Uptime: {0}")  # Track uptime
```

## Testing Integration

### Unit Tests

```python
import pytest
from risk_management import RiskManager
from tools.trust import TrustWalletAgent
from tools.market_data import MarketDataAnalyzer

def test_risk_integration():
    """Test risk manager integration"""

    # Initialize components
    trust_wallet = TrustWalletAgent(access_id, hmac_secret)
    market_analyzer = MarketDataAnalyzer()
    risk_manager = RiskManager(trust_wallet, market_analyzer)

    # Test position validation
    is_valid, message, params = risk_manager.validate_entry(
        token_address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        entry_price=1.0,
        target_position_size=100.0,
        stop_loss_pct=3.0,
        take_profit_pct=6.0
    )

    assert is_valid, "Position should be valid"
    assert params['stop_loss'] < params['entry_price']

    # Test position opening
    result = risk_manager.open_position(
        token_address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        entry_price=1.0,
        position_size=100.0,
        stop_loss_pct=3.0,
        take_profit_pct=6.0
    )

    assert result['success'], "Position should open successfully"
    assert len(risk_manager.active_positions) == 1
```

### Integration Tests

```python
def test_full_trading_cycle():
    """Test complete trading cycle"""

    trust_wallet = TrustWalletAgent(access_id, hmac_secret)
    market_analyzer = MarketDataAnalyzer()
    risk_manager = RiskManager(trust_wallet, market_analyzer)

    # Simulate market signal
    signal = {
        'token': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d',
        'price': 1.0,
        'target_size': 100.0,
        'stop_loss': 3.0,
        'take_profit': 6.0
    }

    # Validate and open
    is_valid, _, params = risk_manager.validate_entry(**signal)
    assert is_valid

    result = risk_manager.open_position(**params)
    assert result['success']

    # Monitor position
    management = risk_manager.check_and_manage_positions()
    assert len(management['closed_positions']) == 0  # Should still be open

    # Check status
    metrics = risk_manager.get_current_metrics()
    assert metrics.total_trades == 1
```

## Best Practices

1. **Always validate entries** before opening positions
2. **Start with conservative settings** and gradually increase
3. **Monitor positions closely** in early stages
4. **Test thoroughly** before live deployment
5. **Maintain logs** for debugging and analysis
6. **Regularly review** risk metrics and limits
7. **Keep risk levels appropriate** for your experience and risk tolerance

## Future Enhancements

1. **Database Integration**
   - Persistent position storage
   - Trade history analytics
   - Performance reports

2. **Advanced Analytics**
   - Backtesting
   - Strategy optimization
   - Risk-adjusted returns

3. **Multi-Strategy Support**
   - Different strategies per token
   - Adaptive position sizing
   - Strategy switching

4. **Advanced Risk Controls**
   - Correlation monitoring
   - Beta-based sizing
   - Macro risk indicators

5. **Alerting**
   - Custom alert thresholds
   - Multiple notification channels
   - Trend alerts

## Support and Documentation

- Main README: See `README.md`
- Trust Wallet API: See `TRUST_WALLET_README.md`
- Market Data Module: See `MARKET_DATA_README.md`
- Risk Management Module: See `RISK_MANAGEMENT_README.md`

## License

Part of the Trust Wallet Trading Bot project. See main LICENSE file.