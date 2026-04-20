"""
Trading Strategies Module
========================

Implements various trading strategies for the standalone trading bot.
All strategies integrate with Trust Wallet API for execution.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

# Import our tools
from tools.trust import TrustWalletAgent
from tools.market_data import MarketDataAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Supported trading strategy types"""
    DCA = "dca"                    # Dollar Cost Averaging
    MOMENTUM = "momentum"          # Trend following
    MEAN_REVERSION = "mean_reversion"  # Buy low, sell high
    ARBITRAGE = "arbitrage"        # Price arbitrage
    SWING = "swing"                # Swing trading
    REBALANCE = "rebalance"        # Portfolio rebalancing


@dataclass
class StrategyConfig:
    """Configuration for a trading strategy"""
    strategy_type: StrategyType
    enabled: bool = True
    parameters: Dict = None
    risk_level: str = "medium"  # low, medium, high
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    max_position_size: float = 0.1  # Max 10% of portfolio


class TradingStrategy:
    """Base class for all trading strategies"""

    def __init__(self, trust_wallet: TrustWalletAgent, market_analyzer: MarketDataAnalyzer):
        """
        Initialize trading strategy

        Args:
            trust_wallet: TrustWalletAgent instance for execution
            market_analyzer: MarketDataAnalyzer instance for market data
        """
        self.trust_wallet = trust_wallet
        self.market_analyzer = market_analyzer

    def execute(self, **kwargs) -> Dict:
        """
        Execute strategy

        Args:
            **kwargs: Strategy-specific parameters

        Returns:
            Execution result dictionary
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def validate_parameters(self, config: StrategyConfig) -> bool:
        """
        Validate strategy parameters

        Args:
            config: Strategy configuration

        Returns:
            True if valid, False otherwise
        """
        return True


class DCAStrategy(TradingStrategy):
    """
    Dollar Cost Averaging Strategy
    Buy at regular intervals regardless of price
    """

    def __init__(self, trust_wallet: TrustWalletAgent, market_analyzer: MarketDataAnalyzer):
        super().__init__(trust_wallet, market_analyzer)

    def execute(
        self,
        token_address: str,
        amount: float,
        interval_days: int = 7,
        start_date: datetime = None
    ) -> Dict:
        """
        Execute DCA strategy

        Args:
            token_address: Token to invest in
            amount: Investment amount per period
            interval_days: Days between purchases
            start_date: Start date (default: now)

        Returns:
            Execution result
        """
        if start_date is None:
            start_date = datetime.now()

        logger.info(f"Executing DCA: {token_address}, amount: ${amount}, interval: {interval_days} days")

        # Check if we can afford the trade
        balance = self.trust_wallet.get_wallet_balance()
        if balance < amount:
            return {
                'success': False,
                'message': f'Insufficient balance. Required: ${amount}, Available: ${balance}',
                'balance': balance
            }

        # Get current token price
        price_data = self.trust_wallet.get_price(token_address)
        if not price_data.get('success'):
            return {
                'success': False,
                'message': f'Failed to get token price: {price_data.get("error")}'
            }

        current_price = price_data.get('price', 0)
        if current_price == 0:
            return {
                'success': False,
                'message': 'Invalid token price'
            }

        # Calculate amount of tokens to buy
        tokens_to_buy = amount / current_price

        # Execute trade
        result = self.trust_wallet.trade_tokens(
            token_address=token_address,
            amount=tokens_to_buy,
            trade_type='buy'
        )

        if result.get('success'):
            logger.info(f"DCA purchase successful: {tokens_to_buy:.6f} tokens @ ${current_price}")

        return {
            'success': result.get('success', False),
            'tokens_bought': tokens_to_buy if result.get('success') else 0,
            'price': current_price,
            'investment': amount,
            'next_purchase_date': start_date + timedelta(days=interval_days),
            'message': result.get('message', 'Trade executed')
        }


class MomentumStrategy(TradingStrategy):
    """
    Momentum Trading Strategy
    Ride trends - buy when price is trending up, sell when trending down
    """

    def __init__(self, trust_wallet: TrustWalletAgent, market_analyzer: MarketDataAnalyzer):
        super().__init__(trust_wallet, market_analyzer)

    def execute(
        self,
        token_address: str,
        portfolio_value: float = 1000.0,
        lookback_days: int = 7
    ) -> Dict:
        """
        Execute momentum strategy

        Args:
            token_address: Token to trade
            portfolio_value: Portfolio value for position sizing
            lookback_days: Lookback period for trend analysis

        Returns:
            Execution result
        """
        logger.info(f"Executing Momentum: {token_address}, lookback: {lookback_days} days")

        # Get current price
        price_data = self.trust_wallet.get_price(token_address)
        if not price_data.get('success'):
            return {
                'success': False,
                'message': f'Failed to get token price: {price_data.get("error")}'
            }

        current_price = price_data.get('price', 0)
        if current_price == 0:
            return {
                'success': False,
                'message': 'Invalid token price'
            }

        # Analyze price trend
        price_data_full = self.market_analyzer.get_token_price_history(
            token_address,
            lookback_days
        )

        if not price_data_full.get('success'):
            return {
                'success': False,
                'message': f'Failed to get price history: {price_data_full.get("error")}'
            }

        history = price_data_full.get('history', [])

        if len(history) < 3:
            return {
                'success': False,
                'message': 'Insufficient price history for trend analysis'
            }

        # Calculate momentum indicators
        price_changes = []
        for i in range(1, len(history)):
            change = (history[i]['close'] - history[i-1]['close']) / history[i-1]['close'] * 100
            price_changes.append(change)

        avg_change = sum(price_changes) / len(price_changes)
        max_change = max(price_changes)
        min_change = min(price_changes)

        # Determine signal
        if avg_change > 2:  # Strong uptrend
            signal = 'BUY'
            confidence = min(abs(avg_change) / 10, 1.0)
            reason = f"Strong uptrend ({avg_change:.2f}% avg change)"
        elif avg_change > 0:  # Mild uptrend
            signal = 'HOLD'
            confidence = 0.3
            reason = f"Mild uptrend ({avg_change:.2f}% avg change)"
        elif avg_change > -2:  # Mild downtrend
            signal = 'SELL'
            confidence = min(abs(avg_change) / 10, 1.0)
            reason = f"Mild downtrend ({avg_change:.2f}% avg change)"
        else:  # Strong downtrend
            signal = 'SELL'
            confidence = min(abs(avg_change) / 10, 1.0)
            reason = f"Strong downtrend ({avg_change:.2f}% avg change)"

        # Calculate position size
        position_size = portfolio_value * 0.1  # 10% of portfolio
        tokens_to_trade = position_size / current_price

        result = {}

        if signal == 'BUY' and confidence > 0.5:
            result = self.trust_wallet.trade_tokens(
                token_address=token_address,
                amount=tokens_to_trade,
                trade_type='buy'
            )
            result['signal'] = 'BUY'
        elif signal == 'SELL':
            # Get current holdings
            holdings = self.trust_wallet.get_token_balances()
            token_holding = next((h for h in holdings if h['address'].lower() == token_address.lower()), None)

            if token_holding and token_holding['balance'] > 0:
                sell_amount = min(token_holding['balance'], tokens_to_trade)
                result = self.trust_wallet.trade_tokens(
                    token_address=token_address,
                    amount=sell_amount,
                    trade_type='sell'
                )
            result['signal'] = 'SELL'
        else:
            result['signal'] = 'HOLD'
            result['confidence'] = confidence

        result.update({
            'price': current_price,
            'avg_change': avg_change,
            'max_change': max_change,
            'min_change': min_change,
            'confidence': confidence,
            'reason': reason
        })

        logger.info(f"Momentum {signal}: {token_address} - {reason}")

        return result


class MeanReversionStrategy(TradingStrategy):
    """
    Mean Reversion Strategy
    Buy low, sell high - exploit price deviations from average
    """

    def __init__(self, trust_wallet: TrustWalletAgent, market_analyzer: MarketDataAnalyzer):
        super().__init__(trust_wallet, market_analyzer)

    def execute(
        self,
        token_address: str,
        lookback_days: int = 14,
        deviation_threshold: float = 3.0  # % deviation from mean
    ) -> Dict:
        """
        Execute mean reversion strategy

        Args:
            token_address: Token to trade
            lookback_days: Lookback period for average calculation
            deviation_threshold: % deviation to trigger trade

        Returns:
            Execution result
        """
        logger.info(f"Executing Mean Reversion: {token_address}, lookback: {lookback_days} days")

        # Get current price
        price_data = self.trust_wallet.get_price(token_address)
        if not price_data.get('success'):
            return {
                'success': False,
                'message': f'Failed to get token price: {price_data.get("error")}'
            }

        current_price = price_data.get('price', 0)
        if current_price == 0:
            return {
                'success': False,
                'message': 'Invalid token price'
            }

        # Get price history
        price_data_full = self.market_analyzer.get_token_price_history(
            token_address,
            lookback_days
        )

        if not price_data_full.get('success'):
            return {
                'success': False,
                'message': f'Failed to get price history: {price_data_full.get("error")}'
            }

        history = price_data_full.get('history', [])

        if len(history) < lookback_days:
            return {
                'success': False,
                'message': f'Insufficient price history. Need {lookback_days} days, have {len(history)}'
            }

        # Calculate average price
        avg_price = sum(h['close'] for h in history) / len(history)
        std_dev = (sum((h['close'] - avg_price) ** 2 for h in history) / len(history)) ** 0.5

        # Calculate current deviation
        deviation = (current_price - avg_price) / avg_price * 100

        # Determine signal
        if deviation < -deviation_threshold:  # Below average by threshold
            signal = 'BUY'
            reason = f"Price {deviation:.2f}% below average (${avg_price:.2f})"
            confidence = min(abs(deviation) / deviation_threshold, 1.0)
        elif deviation > deviation_threshold:  # Above average by threshold
            signal = 'SELL'
            reason = f"Price {deviation:.2f}% above average (${avg_price:.2f})"
            confidence = min(abs(deviation) / deviation_threshold, 1.0)
        else:
            signal = 'HOLD'
            reason = f"Price within normal range (avg: ${avg_price:.2f})"
            confidence = 0.0

        # Calculate position size
        balance = self.trust_wallet.get_wallet_balance()
        position_size = balance * 0.1  # 10% of balance
        tokens_to_trade = position_size / current_price

        result = {
            'signal': signal,
            'confidence': confidence,
            'current_price': current_price,
            'avg_price': avg_price,
            'std_dev': std_dev,
            'deviation': deviation,
            'reason': reason
        }

        if signal == 'BUY':
            result['tokens_to_buy'] = tokens_to_trade
            result = self.trust_wallet.trade_tokens(
                token_address=token_address,
                amount=tokens_to_trade,
                trade_type='buy'
            )
            result['tokens_to_buy'] = tokens_to_trade
            result['avg_price'] = avg_price

        elif signal == 'SELL':
            # Get current holdings
            holdings = self.trust_wallet.get_token_balances()
            token_holding = next((h for h in holdings if h['address'].lower() == token_address.lower()), None)

            if token_holding and token_holding['balance'] > 0:
                sell_amount = min(token_holding['balance'], tokens_to_trade)
                result['tokens_to_sell'] = sell_amount
                result = self.trust_wallet.trade_tokens(
                    token_address=token_address,
                    amount=sell_amount,
                    trade_type='sell'
                )
                result['tokens_to_sell'] = sell_amount

        logger.info(f"Mean Reversion {signal}: {token_address} - {reason}")

        return result


class ArbitrageStrategy(TradingStrategy):
    """
    Arbitrage Strategy
    Exploit price differences across multiple sources
    """

    def __init__(self, trust_wallet: TrustWalletAgent, market_analyzer: MarketDataAnalyzer):
        super().__init__(trust_wallet, market_analyzer)

    def execute(
        self,
        token_address: str,
        min_profit_pct: float = 1.0
    ) -> Dict:
        """
        Execute arbitrage strategy

        Args:
            token_address: Token to arbitrage
            min_profit_pct: Minimum profit percentage to trigger trade

        Returns:
            Execution result
        """
        logger.info(f"Executing Arbitrage: {token_address}, min profit: {min_profit_pct}%")

        # Get token price from multiple sources
        sources = {
            'trust_wallet': self.trust_wallet.get_price(token_address),
            'market_data': self.market_analyzer.get_token_price(token_address)
        }

        prices = {}
        for source, data in sources.items():
            if data.get('success'):
                prices[source] = data.get('price', 0)

        if len(prices) < 2:
            return {
                'success': False,
                'message': 'Insufficient price sources for arbitrage'
            }

        # Find best buy and sell prices
        buy_price = min(prices.values())
        sell_price = max(prices.values())

        # Calculate potential profit
        potential_profit = (sell_price - buy_price) / buy_price * 100

        # Check if profit meets threshold
        if potential_profit >= min_profit_pct:
            # Calculate position size
            balance = self.trust_wallet.get_wallet_balance()
            position_size = balance * 0.05  # 5% of balance

            # Determine which side to trade
            # Note: In a real implementation, you'd need specific DEX pairs
            # This is a simplified version for demonstration

            result = {
                'success': True,
                'signal': 'ARBITRAGE OPPORTUNITY',
                'buy_price': buy_price,
                'sell_price': sell_price,
                'potential_profit': potential_profit,
                'sources': prices,
                'reason': f"Price difference of {potential_profit:.2f}% found",
                'action': 'monitor'  # In real arbitrage, you'd execute on DEX
            }

            logger.info(f"Arbitrage opportunity: {potential_profit:.2f}% profit potential")

        else:
            result = {
                'success': True,
                'signal': 'NO OPPORTUNITY',
                'buy_price': buy_price,
                'sell_price': sell_price,
                'potential_profit': potential_profit,
                'reason': f"Price difference too low ({potential_profit:.2f}%)",
                'action': 'monitor'
            }

        return result


class SwingStrategy(TradingStrategy):
    """
    Swing Trading Strategy
    Capture medium-term price movements (days to weeks)
    """

    def __init__(self, trust_wallet: TrustWalletAgent, market_analyzer: MarketDataAnalyzer):
        super().__init__(trust_wallet, market_analyzer)

    def execute(
        self,
        token_address: str,
        lookback_days: int = 14,
        hold_period_days: int = 5
    ) -> Dict:
        """
        Execute swing trading strategy

        Args:
            token_address: Token to trade
            lookback_days: Lookback period for analysis
            hold_period_days: Expected hold period

        Returns:
            Execution result
        """
        logger.info(f"Executing Swing: {token_address}, hold: {hold_period_days} days")

        # Get price history
        price_data_full = self.market_analyzer.get_token_price_history(
            token_address,
            lookback_days
        )

        if not price_data_full.get('success'):
            return {
                'success': False,
                'message': f'Failed to get price history: {price_data_full.get("error")}'
            }

        history = price_data_full.get('history', [])

        if len(history) < lookback_days:
            return {
                'success': False,
                'message': f'Insufficient price history'
            }

        # Get current data
        current = history[-1]
        prev_5 = history[-6:-1] if len(history) >= 6 else history[:-1]

        # Calculate swing indicators
        high_14 = max(h['high'] for h in history)
        low_14 = min(h['low'] for h in history)

        # Calculate RSI (simplified)
        gains = sum(h['close'] > h['close'] for h in prev_5)
        losses = sum(h['close'] < h['close'] for h in prev_5)
        rsi = (gains / (gains + losses) * 100) if (gains + losses) > 0 else 50

        # Determine signal
        current_price = current['close']

        if current_price < low_14 * 1.02 and rsi < 30:
            signal = 'BUY'
            reason = f"Price near 14-day low (${low_14:.2f}), RSI oversold ({rsi:.1f})"
            confidence = 0.8
        elif current_price > high_14 * 0.98 and rsi > 70:
            signal = 'SELL'
            reason = f"Price near 14-day high (${high_14:.2f}), RSI overbought ({rsi:.1f})"
            confidence = 0.8
        elif rsi < 40:
            signal = 'BUY'
            reason = f"RSI low ({rsi:.1f}) - potential buy opportunity"
            confidence = 0.6
        elif rsi > 60:
            signal = 'SELL'
            reason = f"RSI high ({rsi:.1f}) - potential sell opportunity"
            confidence = 0.6
        else:
            signal = 'HOLD'
            reason = f"RSI neutral ({rsi:.1f})"
            confidence = 0.4

        # Calculate position size
        balance = self.trust_wallet.get_wallet_balance()
        position_size = balance * 0.1
        tokens_to_trade = position_size / current_price

        result = {
            'signal': signal,
            'confidence': confidence,
            'current_price': current_price,
            'high_14': high_14,
            'low_14': low_14,
            'rsi': rsi,
            'reason': reason,
            'hold_period_days': hold_period_days
        }

        if signal == 'BUY':
            result['tokens_to_buy'] = tokens_to_trade
            result = self.trust_wallet.trade_tokens(
                token_address=token_address,
                amount=tokens_to_trade,
                trade_type='buy'
            )
            result['tokens_to_buy'] = tokens_to_trade

        elif signal == 'SELL':
            holdings = self.trust_wallet.get_token_balances()
            token_holding = next((h for h in holdings if h['address'].lower() == token_address.lower()), None)

            if token_holding and token_holding['balance'] > 0:
                sell_amount = min(token_holding['balance'], tokens_to_trade)
                result['tokens_to_sell'] = sell_amount
                result = self.trust_wallet.trade_tokens(
                    token_address=token_address,
                    amount=sell_amount,
                    trade_type='sell'
                )
                result['tokens_to_sell'] = sell_amount

        logger.info(f"Swing {signal}: {token_address} - {reason}")

        return result


class PortfolioRebalanceStrategy(TradingStrategy):
    """
    Portfolio Rebalancing Strategy
    Maintain target asset allocation
    """

    def __init__(self, trust_wallet: TrustWalletAgent, market_analyzer: MarketDataAnalyzer):
        super().__init__(trust_wallet, market_analyzer)

    def execute(
        self,
        target_allocation: Dict[str, float],
        threshold_pct: float = 5.0
    ) -> Dict:
        """
        Execute portfolio rebalancing

        Args:
            target_allocation: Target allocation for each token (percentage)
            threshold_pct: Allocation drift threshold to trigger rebalance

        Returns:
            Execution result
        """
        logger.info(f"Executing Portfolio Rebalance, threshold: {threshold_pct}%")

        # Get current portfolio
        holdings = self.trust_wallet.get_token_balances()
        balance = self.trust_wallet.get_wallet_balance()

        if balance == 0:
            return {
                'success': False,
                'message': 'No balance to rebalance'
            }

        # Get current prices
        tokens_to_trade = []
        for token in holdings:
            token_address = token['address']
            price_data = self.trust_wallet.get_price(token_address)

            if price_data.get('success'):
                price = price_data.get('price', 0)
                token_value = token['balance'] * price

                tokens_to_trade.append({
                    'address': token_address,
                    'balance': token['balance'],
                    'price': price,
                    'value': token_value,
                    'current_allocation': token_value / balance * 100
                })

        # Calculate current allocations
        current_allocations = {
            t['address']: t['current_allocation'] for t in tokens_to_trade
        }

        # Identify trades needed
        trades = []
        total_allocation = sum(current_allocations.values())

        for token_address, target_pct in target_allocation.items():
            if token_address not in current_allocations:
                continue

            current_pct = current_allocations[token_address]
            drift = abs(current_pct - target_pct)

            if drift > threshold_pct:
                # Calculate trade amount
                target_value = balance * (target_pct / 100)
                current_value = current_allocations[token_address] * balance / 100

                if target_value > current_value:
                    # Need to buy
                    trade_amount = (target_value - current_value) / target_allocation.get(token_address, 1)
                    trades.append({
                        'action': 'buy',
                        'token_address': token_address,
                        'amount': trade_amount,
                        'target_value': target_value,
                        'current_value': current_value,
                        'drift': drift
                    })
                else:
                    # Need to sell
                    trade_amount = (current_value - target_value) / target_allocation.get(token_address, 1)
                    trades.append({
                        'action': 'sell',
                        'token_address': token_address,
                        'amount': trade_amount,
                        'target_value': target_value,
                        'current_value': current_value,
                        'drift': drift
                    })

        # Execute trades
        results = []
        total_trades = len(trades)

        for trade in trades:
            if trade['action'] == 'buy':
                result = self.trust_wallet.trade_tokens(
                    token_address=trade['token_address'],
                    amount=trade['amount'],
                    trade_type='buy'
                )
            else:
                result = self.trust_wallet.trade_tokens(
                    token_address=trade['token_address'],
                    amount=trade['amount'],
                    trade_type='sell'
                )

            results.append({
                'success': result.get('success', False),
                'action': trade['action'],
                'token_address': trade['token_address'],
                'amount': trade['amount'],
                'drift': trade['drift'],
                'message': result.get('message', '')
            })

        logger.info(f"Portfolio Rebalance: {total_trades} trades executed")

        return {
            'success': len(trades) > 0,
            'total_trades': total_trades,
            'trades': results,
            'message': f"Rebalanced {total_trades} positions" if total_trades > 0 else "No rebalancing needed"
        }


class StrategyManager:
    """Manages all trading strategies"""

    def __init__(self, trust_wallet: TrustWalletAgent, market_analyzer: MarketDataAnalyzer):
        """
        Initialize strategy manager

        Args:
            trust_wallet: TrustWalletAgent instance
            market_analyzer: MarketDataAnalyzer instance
        """
        self.trust_wallet = trust_wallet
        self.market_analyzer = market_analyzer

        # Initialize all strategies
        self.strategies = {
            StrategyType.DCA: DCAStrategy(trust_wallet, market_analyzer),
            StrategyType.MOMENTUM: MomentumStrategy(trust_wallet, market_analyzer),
            StrategyType.MEAN_REVERSION: MeanReversionStrategy(trust_wallet, market_analyzer),
            StrategyType.ARBITRAGE: ArbitrageStrategy(trust_wallet, market_analyzer),
            StrategyType.SWING: SwingStrategy(trust_wallet, market_analyzer),
            StrategyType.REBALANCE: PortfolioRebalanceStrategy(trust_wallet, market_analyzer),
        }

    def execute_strategy(
        self,
        strategy_type: StrategyType,
        **kwargs
    ) -> Dict:
        """
        Execute a specific strategy

        Args:
            strategy_type: Type of strategy to execute
            **kwargs: Strategy-specific parameters

        Returns:
            Execution result
        """
        strategy = self.strategies.get(strategy_type)

        if not strategy:
            return {
                'success': False,
                'message': f'Strategy {strategy_type} not found'
            }

        if not strategy.validate_parameters(kwargs):
            return {
                'success': False,
                'message': 'Invalid strategy parameters'
            }

        try:
            result = strategy.execute(**kwargs)
            result['strategy_type'] = strategy_type.value
            return result
        except Exception as e:
            logger.error(f"Error executing {strategy_type}: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'strategy_type': strategy_type.value
            }

    def get_available_strategies(self) -> List[Dict]:
        """Get list of available strategies"""
        return [
            {
                'type': s_type.value,
                'name': s_type.name,
                'description': self._get_strategy_description(s_type)
            }
            for s_type, strategy in self.strategies.items()
        ]

    def _get_strategy_description(self, strategy_type: StrategyType) -> str:
        """Get description for a strategy"""
        descriptions = {
            StrategyType.DCA: 'Buy at regular intervals regardless of price',
            StrategyType.MOMENTUM: 'Ride trends - buy when trending up, sell when trending down',
            StrategyType.MEAN_REVERSION: 'Buy low, sell high - exploit price deviations from average',
            StrategyType.ARBITRAGE: 'Exploit price differences across multiple sources',
            StrategyType.SWING: 'Capture medium-term price movements (days to weeks)',
            StrategyType.REBALANCE: 'Maintain target asset allocation'
        }
        return descriptions.get(strategy_type, 'Trading strategy')

    def run_multi_strategy(self, strategies_config: List[Dict]) -> List[Dict]:
        """
        Run multiple strategies

        Args:
            strategies_config: List of strategy configurations

        Returns:
            List of execution results
        """
        results = []

        for config in strategies_config:
            strategy_type = StrategyType(config['type'])
            result = self.execute_strategy(strategy_type, **config.get('params', {}))
            results.append(result)

        return results