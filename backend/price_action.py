"""
Price Action Analyzer Module

Analyzes price movements and generates actionable trading insights
without relying on indicators.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime, timedelta
from collections import deque
import logging

logger = logging.getLogger(__name__)


class PriceActionAnalyzer:
    """Analyze price action patterns and movements"""

    def __init__(self, lookback_period: int = 50, volatility_window: int = 20):
        """
        Initialize price action analyzer

        Args:
            lookback_period: Default lookback period for calculations
            volatility_window: Window for volatility calculation
        """
        self.lookback_period = lookback_period
        self.volatility_window = volatility_window

    def get_trend_direction(self, df: pd.DataFrame, period: int = None) -> str:
        """
        Determine current trend direction

        Args:
            df: DataFrame with OHLCV data
            period: Period to analyze (default to lookback_period)

        Returns:
            'UP', 'DOWN', or 'NEUTRAL'
        """
        if df.empty:
            return 'NEUTRAL'

        period = period or self.lookback_period
        if len(df) < period + 1:
            period = len(df) - 1

        # Get price series
        closes = df['close'].iloc[-period:]

        # Simple moving average crossover
        sma_short = closes.rolling(window=min(5, period)).mean().iloc[-1]
        sma_long = closes.rolling(window=min(period // 2, period)).mean().iloc[-1]

        if sma_short > sma_long:
            return 'UP'
        elif sma_short < sma_long:
            return 'DOWN'
        else:
            return 'NEUTRAL'

    def get_momentum(self, df: pd.DataFrame, period: int = None) -> float:
        """
        Calculate momentum (rate of change)

        Args:
            df: DataFrame with OHLCV data
            period: Period for calculation

        Returns:
            Momentum value
        """
        if df.empty:
            return 0.0

        period = period or self.lookback_period
        if len(df) < period:
            period = len(df) - 1

        current_price = df['close'].iloc[-1]
        past_price = df['close'].iloc[-period]

        if past_price == 0:
            return 0.0

        return (current_price - past_price) / past_price * 100

    def get_volatility(self, df: pd.DataFrame, period: int = None) -> float:
        """
        Calculate volatility (standard deviation of returns)

        Args:
            df: DataFrame with OHLCV data
            period: Period for calculation

        Returns:
            Volatility as percentage
        """
        if df.empty:
            return 0.0

        period = period or self.volatility_window
        if len(df) < period:
            period = len(df)

        # Calculate returns
        returns = df['close'].pct_change().dropna()

        if len(returns) < period:
            period = len(returns)

        recent_returns = returns.tail(period)

        if len(recent_returns) == 0:
            return 0.0

        return recent_returns.std() * np.sqrt(252) * 100

    def get_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate Relative Strength Index

        Args:
            df: DataFrame with OHLCV data
            period: RSI period

        Returns:
            RSI value between 0 and 100
        """
        if df.empty:
            return 50.0

        if len(df) < period + 1:
            period = len(df) - 1

        # Calculate price changes
        delta = df['close'].diff()

        # Separate gains and losses
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)

        # Calculate average gains and losses
        avg_gain = gains.rolling(window=period, min_periods=1).mean()
        avg_loss = losses.rolling(window=period, min_periods=1).mean()

        # Calculate RS
        rs = avg_gain / avg_loss

        # Calculate RSI
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1] if len(rsi) > 0 else 50.0

    def get_support_resistance(self, df: pd.DataFrame,
                               num_points: int = 3) -> Dict[str, List[float]]:
        """
        Identify support and resistance levels

        Args:
            df: DataFrame with OHLCV data
            num_points: Number of support/resistance points to return

        Returns:
            Dictionary with support and resistance levels
        """
        if df.empty:
            return {'support': [], 'resistance': []}

        lookback = min(len(df), self.lookback_period)

        # Use local minima for support, local maxima for resistance
        lows = df['low'].tail(lookback).values
        highs = df['high'].tail(lookback).values

        # Find local minima (support)
        support = []
        for i in range(1, len(lows) - 1):
            if lows[i] <= lows[i - 1] and lows[i] <= lows[i + 1]:
                support.append(lows[i])

        # Find local maxima (resistance)
        resistance = []
        for i in range(1, len(highs) - 1):
            if highs[i] >= highs[i - 1] and highs[i] >= highs[i + 1]:
                resistance.append(highs[i])

        # Return top levels
        return {
            'support': sorted(support)[-num_points:],
            'resistance': sorted(resistance, reverse=True)[:num_points]
        }

    def is_support_rejection(self, df: pd.DataFrame) -> Tuple[bool, Optional[float]]:
        """
        Check if price is rejecting a support level

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Tuple of (is_rejection, rejection_price)
        """
        if df.empty:
            return False, None

        support_levels = self.get_support_resistance(df, num_points=1)

        if not support_levels['support']:
            return False, None

        support_level = support_levels['support'][-1]
        current_price = df['close'].iloc[-1]

        # Check if price is near support
        distance_from_support = abs(current_price - support_level) / support_level

        if distance_from_support > 0.05:
            return False, None

        # Check if current candle is rejecting
        current_candle = df.iloc[-1]
        rejection = (
            current_candle['close'] > current_candle['low'] and
            current_candle['open'] > current_candle['low']
        )

        return rejection, support_level

    def is_resistance_rejection(self, df: pd.DataFrame) -> Tuple[bool, Optional[float]]:
        """
        Check if price is rejecting a resistance level

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Tuple of (is_rejection, rejection_price)
        """
        if df.empty:
            return False, None

        resistance_levels = self.get_support_resistance(df, num_points=1)

        if not resistance_levels['resistance']:
            return False, None

        resistance_level = resistance_levels['resistance'][-1]
        current_price = df['close'].iloc[-1]

        # Check if price is near resistance
        distance_from_resistance = abs(current_price - resistance_level) / resistance_level

        if distance_from_resistance > 0.05:
            return False, None

        # Check if current candle is rejecting
        current_candle = df.iloc[-1]
        rejection = (
            current_candle['close'] < current_candle['high'] and
            current_candle['open'] < current_candle['high']
        )

        return rejection, resistance_level

    def detect_breakout(self, df: pd.DataFrame,
                       period: int = 20, tolerance: float = 0.02) -> Dict[str, bool]:
        """
        Detect price breakouts (trend continuation or reversal)

        Args:
            df: DataFrame with OHLCV data
            period: Breakout period
            tolerance: Tolerance for breakout

        Returns:
            Dictionary with breakout information
        """
        if df.empty or len(df) < period + 1:
            return {'breakout': False, 'type': None, 'strength': 0.0}

        # Calculate average range over period
        ranges = df['high'].iloc[-period:] - df['low'].iloc[-period:]
        avg_range = ranges.mean()
        breakout_threshold = avg_range * (1 + tolerance)

        # Current range
        current_range = df['high'].iloc[-1] - df['low'].iloc[-1]

        # Check for breakout
        if current_range > breakout_threshold * 1.5:
            # Determine breakout direction
            prev_close = df['close'].iloc[-2]
            current_close = df['close'].iloc[-1]

            if current_close > prev_close:
                breakout_type = 'BULLISH'
                strength = (current_close - prev_close) / prev_close * 100
            elif current_close < prev_close:
                breakout_type = 'BEARISH'
                strength = (prev_close - current_close) / prev_close * 100
            else:
                breakout_type = 'NEUTRAL'
                strength = 0.0

            return {
                'breakout': True,
                'type': breakout_type,
                'strength': strength
            }

        return {'breakout': False, 'type': None, 'strength': 0.0}

    def detect_reversal(self, df: pd.DataFrame,
                       period: int = 20, tolerance: float = 0.02) -> Dict[str, bool]:
        """
        Detect potential price reversals

        Args:
            df: DataFrame with OHLCV data
            period: Reversal detection period
            tolerance: Tolerance for reversal

        Returns:
            Dictionary with reversal information
        """
        if df.empty or len(df) < period + 1:
            return {'reversal': False, 'type': None, 'strength': 0.0}

        prev_close = df['close'].iloc[-period]
        current_close = df['close'].iloc[-1]

        # Calculate recent swing points
        swing_high = df['high'].iloc[-period:].max()
        swing_low = df['low'].iloc[-period:].min()

        # Check for bullish reversal
        bullish_reversal = (
            current_close > prev_close and
            current_close > swing_low * (1 + tolerance) and
            current_close > swing_low
        )

        # Check for bearish reversal
        bearish_reversal = (
            current_close < prev_close and
            current_close < swing_high * (1 - tolerance) and
            current_close < swing_high
        )

        if bullish_reversal:
            strength = (current_close - swing_low) / swing_low * 100
            return {
                'reversal': True,
                'type': 'BULLISH',
                'strength': strength
            }
        elif bearish_reversal:
            strength = (swing_high - current_close) / swing_high * 100
            return {
                'reversal': True,
                'type': 'BEARISH',
                'strength': strength
            }

        return {'reversal': False, 'type': None, 'strength': 0.0}

    def analyze_price_action(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Comprehensive price action analysis

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with comprehensive analysis
        """
        if df.empty:
            return {}

        analysis = {
            'trend': self.get_trend_direction(df),
            'momentum': self.get_momentum(df),
            'volatility': self.get_volatility(df),
            'rsi': self.get_rsi(df),
            'support_levels': self.get_support_resistance(df),
            'resistance_levels': self.get_support_resistance(df, num_points=3),
            'breakout': self.detect_breakout(df),
            'reversal': self.detect_reversal(df),
            'support_rejection': self.is_support_rejection(df),
            'resistance_rejection': self.is_resistance_rejection(df)
        }

        return analysis

    def get_trading_signals(self, df: pd.DataFrame) -> List[Dict]:
        """
        Generate trading signals based on price action

        Args:
            df: DataFrame with OHLCV data

        Returns:
            List of trading signals
        """
        signals = []

        if df.empty:
            return signals

        analysis = self.analyze_price_action(df)

        # Trend-based signals
        if analysis['trend'] == 'UP':
            signals.append({
                'signal': 'BUY',
                'reason': 'Strong uptrend detected',
                'confidence': self._calculate_trend_confidence(df),
                'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
            })
        elif analysis['trend'] == 'DOWN':
            signals.append({
                'signal': 'SELL',
                'reason': 'Strong downtrend detected',
                'confidence': self._calculate_trend_confidence(df),
                'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
            })

        # Breakout signals
        if analysis['breakout']['breakout']:
            if analysis['breakout']['type'] == 'BULLISH':
                signals.append({
                    'signal': 'BUY',
                    'reason': f'Bullish breakout detected ({analysis["breakout"]["strength"]:.2f}%)',
                    'confidence': min(0.95, 0.5 + analysis['breakout']['strength'] / 100),
                    'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
                })
            elif analysis['breakout']['type'] == 'BEARISH':
                signals.append({
                    'signal': 'SELL',
                    'reason': f'Bearish breakout detected ({analysis["breakout"]["strength"]:.2f}%)',
                    'confidence': min(0.95, 0.5 + analysis['breakout']['strength'] / 100),
                    'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
                })

        # Reversal signals
        if analysis['reversal']['reversal']:
            if analysis['reversal']['type'] == 'BULLISH':
                signals.append({
                    'signal': 'BUY',
                    'reason': f'Bullish reversal detected ({analysis["reversal"]["strength"]:.2f}%)',
                    'confidence': min(0.9, 0.6 + analysis['reversal']['strength'] / 100),
                    'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
                })
            elif analysis['reversal']['type'] == 'BEARISH':
                signals.append({
                    'signal': 'SELL',
                    'reason': f'Bearish reversal detected ({analysis["reversal"]["strength"]:.2f}%)',
                    'confidence': min(0.9, 0.6 + analysis['reversal']['strength'] / 100),
                    'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
                })

        # Support/Resistance signals
        if analysis['support_rejection'][0]:
            signals.append({
                'signal': 'BUY',
                'reason': f'Price rejecting support level at {analysis["support_rejection"][1]:.2f}',
                'confidence': 0.75,
                'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
            })

        if analysis['resistance_rejection'][0]:
            signals.append({
                'signal': 'SELL',
                'reason': f'Price rejecting resistance level at {analysis["resistance_rejection"][1]:.2f}',
                'confidence': 0.75,
                'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
            })

        # RSI-based signals
        rsi = analysis['rsi']
        if rsi < 30:
            signals.append({
                'signal': 'BUY',
                'reason': f'RSI oversold ({rsi:.2f})',
                'confidence': 0.65,
                'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
            })
        elif rsi > 70:
            signals.append({
                'signal': 'SELL',
                'reason': f'RSI overbought ({rsi:.2f})',
                'confidence': 0.65,
                'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
            })

        return signals

    def _calculate_trend_confidence(self, df: pd.DataFrame) -> float:
        """
        Calculate trend confidence score

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Confidence score between 0 and 1
        """
        if df.empty:
            return 0.0

        # Use momentum and RSI to calculate confidence
        momentum = self.get_momentum(df)
        rsi = self.get_rsi(df)

        momentum_score = min(abs(momentum) / 100, 1.0)
        rsi_score = min(abs(rsi - 50) / 50, 1.0)

        return (momentum_score + rsi_score) / 2 * 0.7 + 0.3


class PriceActionStrategy:
    """Price action-based trading strategy"""

    def __init__(self, analyzer: PriceActionAnalyzer):
        """
        Initialize price action strategy

        Args:
            analyzer: Price action analyzer instance
        """
        self.analyzer = analyzer

    def generate_entry_signals(self, df: pd.DataFrame) -> List[Dict]:
        """
        Generate entry signals based on strategy rules

        Args:
            df: DataFrame with OHLCV data

        Returns:
            List of entry signals
        """
        signals = []

        if df.empty:
            return signals

        # Get support and resistance
        levels = self.analyzer.get_support_resistance(df)
        support_levels = levels['support']
        resistance_levels = levels['resistance']

        current_price = df['close'].iloc[-1]

        # Entry signal: Pullback to support
        if support_levels:
            support_price = support_levels[-1]
            if abs(current_price - support_price) / support_price < 0.03:
                signals.append({
                    'type': 'PULLBACK_TO_SUPPORT',
                    'price': current_price,
                    'target': resistance_levels[0] if resistance_levels else None,
                    'stop_loss': support_price * 0.98 if support_price else None,
                    'reason': f'Pullback to support at {support_price:.2f}',
                    'confidence': 0.7
                })

        # Entry signal: Breakout above resistance
        if resistance_levels:
            resistance_price = resistance_levels[0]
            if current_price > resistance_price * 1.02:
                signals.append({
                    'type': 'BREAKOUT',
                    'price': current_price,
                    'target': current_price * 1.05,
                    'stop_loss': resistance_price,
                    'reason': f'Breakout above resistance at {resistance_price:.2f}',
                    'confidence': 0.65
                })

        # Entry signal: Trend following
        trend = self.analyzer.get_trend_direction(df)
        if trend == 'UP':
            # Buy on pullback
            momentum = self.analyzer.get_momentum(df)
            if momentum > 0 and momentum < 2:
                signals.append({
                    'type': 'TREND_PULLBACK',
                    'price': current_price,
                    'target': current_price * 1.02,
                    'stop_loss': current_price * 0.99,
                    'reason': 'Trend pullback - buy',
                    'confidence': 0.6
                })

        # Entry signal: RSI oversold
        rsi = self.analyzer.get_rsi(df)
        if rsi < 30:
            signals.append({
                'type': 'RSI_OVERSOLD',
                'price': current_price,
                'target': current_price * 1.03,
                'stop_loss': current_price * 0.97,
                'reason': f'RSI oversold ({rsi:.2f})',
                'confidence': 0.55
            })

        return signals

    def generate_exit_signals(self, df: pd.DataFrame) -> List[Dict]:
        """
        Generate exit signals based on strategy rules

        Args:
            df: DataFrame with OHLCV data

        Returns:
            List of exit signals
        """
        signals = []

        if df.empty:
            return signals

        # Exit signal: Hit resistance
        levels = self.analyzer.get_support_resistance(df, num_points=3)
        resistance_levels = levels['resistance']
        current_price = df['close'].iloc[-1]

        for resistance in resistance_levels:
            if current_price >= resistance * 1.01:
                signals.append({
                    'type': 'HIT_RESISTANCE',
                    'reason': f'Price hit resistance at {resistance:.2f}',
                    'confidence': 0.75
                })
                break

        # Exit signal: Trend reversal
        trend = self.analyzer.get_trend_direction(df)
        if trend == 'DOWN':
            signals.append({
                'type': 'TREND_REVERSAL',
                'reason': 'Downtrend detected - exit',
                'confidence': 0.7
            })

        # Exit signal: RSI overbought
        rsi = self.analyzer.get_rsi(df)
        if rsi > 70:
            signals.append({
                'type': 'RSI_OVERBOUGHT',
                'reason': f'RSI overbought ({rsi:.2f})',
                'confidence': 0.6
            })

        # Exit signal: Breakdown
        analysis = self.analyzer.detect_breakout(df)
        if analysis['breakout'] and analysis['breakout']['type'] == 'BEARISH':
            signals.append({
                'type': 'BREAKDOWN',
                'reason': f'Bearish breakout ({analysis["breakout"]["strength"]:.2f}%)',
                'confidence': 0.75
            })

        return signals