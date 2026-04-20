# Execution Layer

A comprehensive Python execution layer for decentralized exchange (DEX) trading with slippage protection, transaction queuing, and arbitrage capabilities.

## Features

- **Multi-DEX Support**: Uniswap V2/V3, PancakeSwap, SushiSwap, and more
- **Multi-Network**: Ethereum, BSC, Arbitrum, Optimism, Polygon, Avalanche
- **Execution Strategies**: Best price, lowest slippage, fastest gas, risk-averse
- **Slippage Protection**: Configurable max slippage and price impact tolerance
- **Transaction Queue**: Batch processing for optimized gas costs
- **Flash Loan Arbitrage**: Built-in arbitrage detection and execution
- **Performance Monitoring**: Real-time metrics and tracking

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your API keys and configuration
```

## Quick Start

```python
from execution_layer import ExecutionLayer, ExecutionStrategy, Network, SlippageConfig

# Initialize execution layer
slippage_config = SlippageConfig(
    max_slippage_pct=0.02,
    min_price_impact_pct=0.01
)

execution_layer = ExecutionLayer(
    trust_wallet=None,
    market_analyzer=None,
    slippage_config=slippage_config
)

# Execute a trade
result = execution_layer.execute_trade(
    token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    amount=1.0,
    strategy=ExecutionStrategy.BEST_PRICE,
    network=Network.ETHEREUM,
    slippage_tolerance=0.02
)

if result.success:
    print(f"Trade executed: {result.actual_amount}")
    print(f"Slippage: {result.actual_slippage:.2%}")
```

## API Reference

### ExecutionLayer

Main class for trade execution and transaction management.

#### Methods

- `execute_trade(token_address, amount, strategy, network, slippage_tolerance)` - Execute a single trade
- `queue_transaction(token_address, amount, strategy, network, slippage_tolerance)` - Queue a transaction
- `execute_queued_transactions()` - Process all queued transactions
- `get_transaction_status(tx_id)` - Get status of a specific transaction
- `get_queue_status()` - Get queue statistics
- `execute_flash_loan_arbitrage(token, amount, dex, path, gas_limit, max_slippage)` - Execute flash loan arbitrage
- `optimize_gas(network, dex)` - Get gas optimization recommendations
- `get_execution_metrics()` - Get performance metrics

### Configuration

#### SlippageConfig

```python
SlippageConfig(
    max_slippage_pct: float = 0.02,    # Maximum slippage (0-1)
    min_price_impact_pct: float = 0.01 # Minimum price impact (0-1)
)
```

#### Execution Strategies

- `BEST_PRICE`: Optimize for best execution price
- `LOWEST_SLIPPAGE`: Minimize slippage
- `FASTEST_GAS`: Prioritize transaction speed
- `RISK_AVERSE`: Conservative approach with lowest risk

#### Networks

- `ETHEREUM`: Main Ethereum network
- `BSC`: Binance Smart Chain
- `ARBITRUM`: Arbitrum
- `OPTIMISM`: Optimism
- `POLYGON`: Polygon
- `AVALANCHE`: Avalanche

#### DEXs

- `UNISWAP_V2`, `UNISWAP_V3`
- `PANCAKESWAP`
- `SUSHISWAP`
- `SHIBASWAP`
- `QUICKSWAP`

## Usage Examples

### Basic Trade Execution

```python
from execution_layer import ExecutionLayer, ExecutionStrategy, Network

# Initialize
layer = ExecutionLayer(
    trust_wallet=wallet_instance,
    market_analyzer=mapper_instance,
    slippage_config=SlippageConfig(0.02, 0.01)
)

# Execute trade
result = layer.execute_trade(
    token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    amount=1.0,
    strategy=ExecutionStrategy.BEST_PRICE,
    network=Network.ETHEREUM,
    slippage_tolerance=0.02
)

if result.success:
    print(f"Executed: {result.actual_amount} WETH")
    print(f"Gas Cost: ${result.gas_cost:.2f}")
```

### Transaction Queuing

```python
# Queue multiple transactions
for token in tokens_to_trade:
    layer.queue_transaction(
        token_address=token,
        amount=1.0,
        strategy=ExecutionStrategy.BEST_PRICE,
        network=Network.ETHEREUM,
        slippage_tolerance=0.02
    )

# Process all queued transactions
result = layer.execute_queued_transactions()

print(f"Processed: {result.total_transactions}")
print(f"Successful: {result.successful_transactions}")
print(f"Failed: {result.failed_transactions}")
```

### Flash Loan Arbitrage

```python
from execution_layer import DEX

# Execute arbitrage
arbitrage_result = layer.execute_flash_loan_arbitrage(
    token="0xWETH",
    amount=1000,
    dex=DEX.UNISWAP_V2,
    path=["0xWETH", "0xUNI", "0WETH"],
    gas_limit=300000,
    max_slippage=0.02
)

print(f"Profit: ${arbitrage_result['profit_percentage']:.2f}%")
print(f"Gas Cost: ${arbitrage_result['gas_cost_usd']:.2f}")
```

### Gas Optimization

```python
# Get gas optimization recommendations
recommendations = layer.optimize_gas(
    network=Network.ETHEREUM,
    dex=DEX.UNISWAP_V3
)

print(f"Recommended Gas Price: {recommendations['recommended_gas_price']} gwei")
print(f"Estimated Gas: {recommendations['estimated_gas']} units")
print(f"Network Fee: ${recommendations['network_fee_usd']:.4f}")
```

### Performance Monitoring

```python
# Get execution metrics
metrics = layer.get_execution_metrics()

print(f"Total Executions: {metrics['total_executions']}")
print(f"Success Rate: {metrics['success_rate']:.2f}%")
print(f"Avg Execution Time: {metrics['avg_execution_time']:.2f}s")
print(f"Avg Slippage: {metrics['avg_slippage']:.2%}")
```

## Transaction Lifecycle

1. **Create**: `execute_trade()` creates a new trade execution
2. **Queue**: `queue_transaction()` adds to batch processing queue
3. **Execute**: `execute_queued_transactions()` processes queued trades
4. **Monitor**: `get_transaction_status()` checks status
5. **Cleanup**: `cleanup_old_transactions()` removes old records

## Security Considerations

- Always validate slippage tolerance
- Use risk-averse strategies for large trades
- Monitor gas prices before execution
- Test thoroughly with paper trading mode
- Keep API keys and private keys secure

## Testing

```bash
# Run unit tests
pytest tests/

# Run demo
python demo_simple.py
```

## Contributing

When contributing:

1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Follow security best practices

## License

MIT License

## Support

For issues and questions:
- Check the documentation
- Review test cases
- Open an issue on GitHub