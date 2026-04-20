# Risk Management Module

Comprehensive risk management system for cryptocurrency trading bots with position sizing, stop-loss automation, and portfolio diversification.

## Features

### 🛡️ Core Risk Controls

1. **Position Sizing**
   - Never risk more than X% per trade
   - Automatic calculation based on stop-loss distance
   - Limits based on portfolio value

2. **Stop-Loss / Take-Profit Automation**
   - Automatic stop-loss triggers
   - Automatic take-profit execution
   - Configurable percentage-based triggers

3. **Portfolio Diversification**
   - Max single position allocation
   - Diversification score (0-100)
   - Concentration risk checks

4. **Daily Loss Limits**
   - Prevents catastrophic daily losses
   - Automatic stop on threshold breach
   - Reset on new trading day

5. **Maximum Drawdown Protection**
   - Tracks peak portfolio value
   - Automatic halt on drawdown limit
   - Long-term portfolio preservation

6. **Risk-Reward Ratio Tracking**
   - Validates trade entries
   - Minimum required ratios
   - Performance analytics

## Installation

The module is included in the main project. No additional installation needed.

## Configuration

### Risk Levels

```python
from risk_management import RiskManager, RiskLevel

# Initialize with Trust Wallet and Market Data
trust_wallet = TrustWalletAgent(access_id, hmac_secret)
market_analyzer = MarketDataAnalyzer()
risk_manager = RiskManager(trust_wallet, market_analyzer)

# Set risk level (automatically configures parameters)
risk_manager.set_risk_level(RiskLevel.LOW)   # Conservative
risk_manager.set_risk_level(RiskLevel.MEDIUM) # Balanced
risk_manager.set_risk_level(RiskLevel.HIGH)   # Aggressive
```

### Custom Configuration

```python
from risk_management import RiskManager, RiskConfig

config = RiskConfig(
    max_daily_loss_pct=2.0,           # Maximum daily loss allowed
    max_drawdown_pct=10.0,            # Maximum drawdown allowed
    risk_per_trade_pct=1.0,           # Max risk per trade (2% of portfolio)
    max_position_size_pct=10.0,       # Max single position size
    min_risk_reward_ratio=1.5,        # Minimum risk-reward ratio
    stop_loss_pct=3.0,                # Default stop-loss percentage
    take_profit_pct=6.0,              # Default take-profit percentage
    risk_level=RiskLevel.MEDIUM       # Default risk level
)

risk_manager = RiskManager(trust_wallet, market_analyzer)
risk_manager.config = config
```

## Usage Examples

### Opening a Position

```python
# Validate entry
is_valid, message, params = risk_manager.validate_entry(
    token_address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    entry_price=1.0,
    target_position_size=100.0,
    stop_loss_pct=3.0,
    take_profit_pct=6.0,
    risk_reward_ratio=2.0
)

if is_valid:
    # Open position
    result = risk_manager.open_position(
        token_address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        entry_price=1.0,
        position_size=100.0,
        stop_loss_pct=3.0,
        take_profit_pct=6.0
    )
    print(f"Position opened: {result['success']}")
```

### Managing Positions

```python
# Check and manage all positions
management = risk_manager.check_and_manage_positions()

print(f"Closed: {len(management['closed_positions'])}")
print(f"Updated: {len(management['updated_positions'])}")
print(f"Warnings: {len(management['warnings'])}")

for warning in management['warnings']:
    print(f"⚠️ {warning}")
```

### Getting Portfolio Status

```python
# Get current risk metrics
metrics = risk_manager.get_current_metrics()

print(f"Portfolio Value: ${metrics.total_portfolio_value:.2f}")
print(f"Daily PnL: ${metrics.daily_pnl:.2f} ({metrics.daily_pnl_pct:.2f}%)")
print(f"Max Drawdown: {metrics.max_drawdown:.2f}%")
print(f"Win Rate: {metrics.win_rate:.2f}%")
print(f"Avg Risk-Reward: {metrics.average_risk_reward:.2f}")
```

### Checking Diversification

```python
# Get diversification score
diversification = risk_manager.get_diversification_score()

print(f"Score: {diversification['diversification_score']:.2f}/100")
print(f"Active Positions: {diversification['active_positions']}")
print(f"Is Diversified: {diversification['is_diversified']}")
print(f"Max Allocation: {diversification['max_allocation']:.2f}%")

# Check if can open new position
can_open, message = risk_manager.can_open_new_position()
print(f"Can open: {can_open} - {message}")
```

### Running the Demo

```bash
python demo_risk_management.py
```

## Risk Level Profiles

### LOW (Conservative)
- Max Daily Loss: 1%
- Max Drawdown: 5%
- Risk per Trade: 0.5%
- Max Position Size: 5%
- Min Risk-Reward: 2.0

### MEDIUM (Balanced)
- Max Daily Loss: 2%
- Max Drawdown: 10%
- Risk per Trade: 1.0%
- Max Position Size: 10%
- Min Risk-Reward: 1.5

### HIGH (Aggressive)
- Max Daily Loss: 5%
- Max Drawdown: 20%
- Risk per Trade: 3.0%
- Max Position Size: 20%
- Min Risk-Reward: 1.2

## API Reference

### RiskManager Class

#### Methods

##### `set_risk_level(level: RiskLevel)`
Set overall risk level with pre-configured parameters.

##### `calculate_position_size(entry_price, risk_amount, stop_loss_distance)`
Calculate optimal position size based on risk parameters.

##### `validate_entry(token_address, entry_price, target_position_size, stop_loss_pct, take_profit_pct, risk_reward_ratio)`
Validate a trade entry against all risk rules.

##### `open_position(token_address, entry_price, position_size, stop_loss_pct, take_profit_pct, risk_reward_ratio)`
Open a new trading position with risk controls.

##### `check_and_manage_positions()`
Check all active positions and manage stop-loss/take-profit triggers.

##### `can_open_new_position() -> Tuple[bool, str]`
Check if can open a new position based on risk limits.

##### `get_current_metrics() -> RiskMetrics`
Get current portfolio risk metrics and statistics.

##### `get_diversification_score() -> Dict`
Get portfolio diversification score and allocation details.

##### `get_all_positions() -> List[Dict]`
Get all active positions with details.

##### `get_trade_history(days=30) -> List[Dict]`
Get trade history for the specified number of days.

##### `print_status()`
Print comprehensive risk management status report.

## Data Classes

### RiskConfig
```python
@dataclass
class RiskConfig:
    max_daily_loss_pct: float = 2.0
    max_drawdown_pct: float = 10.0
    risk_per_trade_pct: float = 1.0
    max_position_size_pct: float = 10.0
    min_risk_reward_ratio: float = 1.5
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 6.0
    risk_level: RiskLevel = RiskLevel.MEDIUM
```

### RiskMetrics
```python
@dataclass
class RiskMetrics:
    total_portfolio_value: float
    daily_pnl: float
    daily_pnl_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    average_risk_reward: float
```

## Integration with Other Modules

### Trust Wallet
```python
from tools.trust import TrustWalletAgent

trust_wallet = TrustWalletAgent(access_id, hmac_secret)
risk_manager = RiskManager(trust_wallet, market_analyzer)
```

### Market Data
```python
from tools.market_data import MarketDataAnalyzer

market_analyzer = MarketDataAnalyzer()
risk_manager = RiskManager(trust_wallet, market_analyzer)
```

## Error Handling

The module includes comprehensive error handling for:
- Invalid token addresses
- Insufficient balance
- Missing price data
- Risk limit violations
- Invalid risk parameters

All errors are logged with descriptive messages and returned in results.

## Security Considerations

1. **Never expose private keys or secrets**
2. **Use environment variables for sensitive data**
3. **Test thoroughly before live trading**
4. **Start with conservative risk levels**
5. **Monitor position management closely**

## Performance

- Position sizing: O(1)
- Validation: O(1)
- Portfolio checks: O(n) where n = number of active positions
- Trade history: O(n) with pagination support

## Best Practices

1. **Always validate entries** before opening positions
2. **Start conservative** with risk level LOW
3. **Monitor daily PnL** and stop if approaching limits
4. **Maintain diversification** with multiple positions
5. **Review drawdown** regularly and adjust strategy
6. **Track risk-reward ratios** and optimize

## Troubleshooting

### Common Issues

**"Daily loss limit reached"**
- Reduce risk per trade
- Close some positions
- Wait for next trading day

**"Maximum drawdown limit reached"**
- Reduce position sizes
- Increase stop-loss distances
- Review and adjust strategy

**"Risk-reward ratio too low"**
- Increase stop-loss distance
- Set higher target profit
- Adjust risk level parameters

## License

Part of the Trust Wallet Trading Bot project. See main LICENSE file.