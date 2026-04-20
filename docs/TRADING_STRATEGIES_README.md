# Trading Strategies Module

A comprehensive trading strategies system for standalone trading bots. This module implements multiple trading strategies that integrate with Trust Wallet API for execution.

## Features

- **6 Built-in Trading Strategies**
  - DCA (Dollar Cost Averaging)
  - Momentum (Trend Following)
  - Mean Reversion
  - Arbitrage
  - Swing Trading
  - Portfolio Rebalancing

- **Market Analysis Integration**
  - Real-time price data fetching
  - Historical price analysis
  - Technical indicators (RSI, Moving Averages)

- **Risk Management**
  - Stop-loss and take-profit levels
  - Position sizing limits
  - Risk level configuration

- **Flexible Configuration**
  - Per-strategy parameter tuning
  - Enable/disable strategies
  - Custom thresholds

## Installation

No additional installation required. The module uses existing dependencies:
- `tools.trust` - Trust Wallet API client
- `tools.market_data` - Market data analyzer

## Quick Start

```python
from tools.trust import TrustWalletAgent
from tools.market_data import MarketDataAnalyzer
from trading_strategies import StrategyManager, StrategyType

# Initialize agents
trust_wallet = TrustWalletAgent(
    access_id=os.getenv('TWAK_ACCESS_ID'),
    hmac_secret=os.getenv('TWAK_HMAC_SECRET')
)

market_analyzer = MarketDataAnalyzer()
strategy_manager = StrategyManager(trust_wallet, market_analyzer)

# Execute DCA strategy
result = strategy_manager.execute_strategy(
    StrategyType.DCA,
    token_address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",  # USDC-BSC
    amount=100.0,
    interval_days=7
)

print(result)
```

## Strategies Overview

### 1. DCA Strategy (Dollar Cost Averaging)
Regular investments at fixed intervals, regardless of price.

**Parameters:**
- `token_address`: Token contract address
- `amount`: Investment amount per period
- `interval_days`: Days between purchases

**Best for:** Long-term investors, reducing market timing risk

### 2. Momentum Strategy (Trend Following)
Buy when prices are rising, sell when falling.

**Parameters:**
- `token_address`: Token contract address
- `portfolio_value`: Total portfolio value
- `lookback_days`: Days to analyze trend

**Best for:** Capturing upward trends in bullish markets

### 3. Mean Reversion Strategy
Buy when prices drop below average, sell when above.

**Parameters:**
- `token_address`: Token contract address
- `lookback_days`: Days to calculate average
- `deviation_threshold`: Standard deviations from mean

**Best for:** Finding undervalued assets after corrections

### 4. Arbitrage Strategy
Capitalizes on price differences across exchanges.

**Parameters:**
- `token_address`: Token contract address
- `min_profit_pct`: Minimum profit percentage required

**Best for:** Low-risk profit opportunities

### 5. Swing Trading Strategy
Captures medium-term price movements (days to weeks).

**Parameters:**
- `token_address`: Token contract address
- `lookback_days`: Days for analysis
- `hold_period_days`: Days to hold position

**Best for:** Trading between daily volatility swings

### 6. Portfolio Rebalancing Strategy
Maintains target asset allocation.

**Parameters:**
- `target_allocation`: Dict mapping token addresses to percentages
- `threshold_pct`: Drift percentage to trigger rebalance

**Best for:** Risk management and maintaining diversification

## Usage Examples

### Example 1: Execute DCA Strategy

```python
result = strategy_manager.execute_strategy(
    StrategyType.DCA,
    token_address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    amount=100.0,
    interval_days=7
)

# Access result
if result.get('success'):
    print(f"Buy {result['tokens_bought']:.6f} tokens")
    print(f"Next purchase: {result['next_purchase_date']}")
```

### Example 2: Execute Momentum Strategy

```python
result = strategy_manager.execute_strategy(
    StrategyType.MOMENTUM,
    token_address="0x55d398326f99059fF775485246999027B3197955",  # USDT-BSC
    portfolio_value=1000.0,
    lookback_days=7
)

# Access result
print(f"Signal: {result['signal']}")  # 'BUY' or 'SELL'
print(f"Confidence: {result['confidence']:.2%}")
```

### Example 3: Rebalance Portfolio

```python
target_allocation = {
    "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d": 40.0,  # USDC
    "0x55d398326f99059fF775485246999027B3197955": 30.0,  # USDT
    "0xE592427A0AEce92De3Edee1F18E0157C05861564": 20.0,  # BUSD
    "0x2170Ed0880ac9A7588bD10F801F6288Bd85f019E": 10.0,  # WBNB
}

result = strategy_manager.execute_strategy(
    StrategyType.REBALANCE,
    target_allocation=target_allocation,
    threshold_pct=5.0
)

print(f"Trades executed: {result['total_trades']}")
```

## Running the Demo

A comprehensive demo script is provided:

```bash
python demo_strategies.py
```

This demonstrates all strategies with realistic token addresses and parameters.

## Running Tests

```bash
python test_trading_strategies.py
```

## Strategy Management

### Check Available Strategies

```python
strategies = strategy_manager.get_available_strategies()
for strategy in strategies:
    print(f"{strategy['name']}: {strategy['description']}")
```

### Enable/Disable Strategies

```python
config = strategy_manager.get_strategy_config(StrategyType.DCA)
config.enabled = True
strategy_manager.update_strategy_config(StrategyType.DCA, config)
```

### Get Strategy History

```python
history = strategy_manager.get_strategy_history(StrategyType.DCA)
for entry in history[-10:]:  # Last 10 entries
    print(f"{entry['date']}: {entry['action']} - {entry['amount']}")
```

## Best Practices

1. **Always test with paper trading first** - Never start live trading without testing
2. **Start small** - Begin with small amounts while monitoring performance
3. **Use appropriate strategies** - Different strategies work better in different market conditions
4. **Monitor regularly** - Review strategy performance and adjust parameters as needed
5. **Diversify** - Use multiple strategies to reduce overall risk
6. **Set stop-losses** - Never trade without risk management
7. **Keep parameters reasonable** - Avoid extreme values that may indicate strategy failure

## Error Handling

Strategies return consistent result dictionaries:

```python
if result.get('success'):
    # Success handling
    tokens_bought = result.get('tokens_bought', 0)
    next_purchase = result.get('next_purchase_date')
else:
    # Error handling
    error_message = result.get('message')
    print(f"Strategy failed: {error_message}")
```

Common error reasons:
- Insufficient wallet balance
- Invalid token address
- Market data unavailable
- Network errors

## Advanced Usage

### Custom Strategy Configuration

```python
from trading_strategies import StrategyConfig, StrategyType

config = StrategyConfig(
    strategy_type=StrategyType.DCA,
    enabled=True,
    parameters={
        'interval_days': 14,
        'start_date': datetime(2024, 1, 1)
    },
    risk_level="low",
    stop_loss_pct=3.0,
    take_profit_pct=6.0,
    max_position_size=0.05
)

strategy_manager.update_strategy_config(StrategyType.DCA, config)
```

### Combining Strategies

```python
# Run multiple strategies in sequence
for strategy_type in [StrategyType.DCA, StrategyType.MOMENTUM]:
    result = strategy_manager.execute_strategy(
        strategy_type,
        token_address="YOUR_TOKEN_ADDRESS",
        # strategy-specific params
    )
    if result['success']:
        # Handle successful execution
        pass
```

## API Reference

### StrategyManager Methods

- `execute_strategy(strategy_type, **kwargs)` - Execute a strategy
- `get_available_strategies()` - Get list of available strategies
- `get_strategy_config(strategy_type)` - Get strategy configuration
- `update_strategy_config(strategy_type, config)` - Update strategy configuration
- `get_strategy_history(strategy_type)` - Get execution history

### Strategy Types

All strategy types are defined in `StrategyType` enum:
- `StrategyType.DCA`
- `StrategyType.MOMENTUM`
- `StrategyType.MEAN_REVERSION`
- `StrategyType.ARBITRAGE`
- `StrategyType.SWING`
- `StrategyType.REBALANCE`

## Support

For issues or questions:
1. Check the error messages in strategy results
2. Verify Trust Wallet API credentials are correct
3. Ensure market data provider is accessible
4. Check token addresses are correct and valid

## License

Part of the trading bot project. See main project LICENSE file.