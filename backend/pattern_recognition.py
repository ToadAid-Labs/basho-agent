"""
Pattern Recognition Module

Identifies common trading patterns and market formations
to help with decision making and strategy development.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
import logging

logger = logging.getLogger(__name__)


class CandlestickPatterns:
    """Detect candlestick patterns"""

    @staticmethod
    def detect_bullish_engulfing(open_price: float, high: float, low: float, close: float,
                            prev_open: float, prev_high: float, prev_low: float, prev_close: float) -> bool:
        """
        Bullish Engulfing Pattern - reversal pattern indicating upward trend

        Args:
            Current and previous candle OHLC data

        Returns:
            True if bullish engulfing pattern detected
        """
        # Current candle should be green
        is_bullish = close > open_price

        # Previous candle should be red
        is_prev_bearish = prev_close < prev_open

        # Current candle should fully engulf previous candle
        engulfing = (
            close > prev_open and
            open_price < prev_close and
            high > max(prev_high, close) and
            low < min(prev_low, open_price)
        )

        return is_bullish and is_prev_bearish and engulfing

    @staticmethod
    def detect_bearish_engulfing(open_price: float, high: float, low: float, close: float,
                            prev_open: float, prev_high: float, prev_low: float, prev_close: float) -> bool:
        """
        Bearish Engulfing Pattern - reversal pattern indicating downward trend

        Args:
            Current and previous candle OHLC data

        Returns:
            True if bearish engulfing pattern detected
        """
        # Current candle should be red
        is_bearish = close < open_price

        # Previous candle should be green
        is_prev_bullish = prev_close > prev_open

        # Current candle should fully engulf previous candle
        engulfing = (
            close < prev_open and
            open_price > prev_close and
            high > max(prev_high, close) and
            low < min(prev_low, open_price)
        )

        return is_bearish and is_prev_bullish and engulfing

    @staticmethod
    def detect_doji(open_price: float, high: float, low: float, close: float,
               tolerance: float = 0.1) -> bool:
        """
        Doji Pattern - indecision pattern

        Args:
            Current candle OHLC data
            tolerance: Tolerance for doji classification

        Returns:
            True if doji pattern detected
        """
        body_size = abs(close - open_price)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        total_range = high - low

        if total_range == 0:
            return False

        # Doji if body is very small relative to total range
        return body_size / total_range < tolerance

    @staticmethod
    def detect_hammer(open_price: float, high: float, low: float, close: float,
                 body_ratio: float = 0.1) -> bool:
        """
        Hammer Pattern - potential reversal up

        Args:
            Current candle OHLC data
            body_ratio: Maximum ratio of body to wick

        Returns:
            True if hammer pattern detected
        """
        # Body should be small
        body_size = abs(close - open_price)
        upper_wick = high - max(open_price, close)

        # Lower wick should be at least twice the body
        lower_wick = min(open_price, close) - low

        # No large upper wick
        is_hammer = (
            lower_wick > body_ratio * (high - low) and
            upper_wick < lower_wick and
            body_size < lower_wick
        )

        return is_hammer

    @staticmethod
    def detect_shooting_star(open_price: float, high: float, low: float, close: float,
                         body_ratio: float = 0.1) -> bool:
        """
        Shooting Star Pattern - potential reversal down

        Args:
            Current candle OHLC data
            body_ratio: Maximum ratio of body to wick

        Returns:
            True if shooting star pattern detected
        """
        # Body should be small
        body_size = abs(close - open_price)
        lower_wick = min(open_price, close) - low

        # Upper wick should be at least twice the body
        upper_wick = high - max(open_price, close)

        # No large lower wick
        is_shooting_star = (
            upper_wick > body_ratio * (high - low) and
            lower_wick < upper_wick and
            body_size < upper_wick
        )

        return is_shooting_star

    @staticmethod
    def detect_bullish_harami(open_price: float, high: float, low: float, close: float,
                          prev_open: float, prev_high: float, prev_low: float, prev_close: float) -> bool:
        """
        Bullish Harami Pattern - potential reversal up

        Args:
            Current and previous candle OHLC data

        Returns:
            True if bullish harami pattern detected
        """
        # Current candle should be green
        is_bullish = close > open_price

        # Previous candle should be red and smaller
        is_prev_bearish = prev_close < prev_open
        is_smaller = (high - low) < (prev_high - prev_low)

        return is_bullish and is_prev_bearish and is_smaller

    @staticmethod
    def detect_bearish_harami(open_price: float, high: float, low: float, close: float,
                          prev_open: float, prev_high: float, prev_low: float, prev_close: float) -> bool:
        """
        Bearish Harami Pattern - potential reversal down

        Args:
            Current and previous candle OHLC data

        Returns:
            True if bearish harami pattern detected
        """
        # Current candle should be red
        is_bearish = close < open_price

        # Previous candle should be green and smaller
        is_prev_bullish = prev_close > prev_open
        is_smaller = (high - low) < (prev_high - prev_low)

        return is_bearish and is_prev_bullish and is_smaller

    @staticmethod
    def detect_three_white_soldiers(open_candles: List[Tuple[float, float, float, float]],
                                   tolerance: float = 0.1) -> bool:
        """
        Three White Soldiers Pattern - strong bullish continuation

        Args:
            List of three candle OHLC data
            tolerance: Tolerance for consecutive green candles

        Returns:
            True if three white soldiers pattern detected
        """
        if len(open_candles) < 3:
            return False

        # Check if all three are green
        for i in range(3):
            open_price, high, low, close = open_candles[i]
            if close <= open_price:
                return False

        # Check for continuous upward movement
        open_prices = [c[0] for c in open_candles]
        close_prices = [c[3] for c in open_candles]

        # Each close should be higher than previous open
        continuous = all(
            close_prices[i] > open_prices[i - 1]
            for i in range(1, 3)
        )

        # Each candle should be at least as long as previous
        bodies = [abs(close_prices[i] - open_prices[i]) for i in range(3)]
        growing_bodies = all(bodies[i] >= bodies[i - 1] * (1 - tolerance)
                            for i in range(1, 3))

        return continuous and growing_bodies

    @staticmethod
    def detect_three_black_crows(open_candles: List[Tuple[float, float, float, float]],
                            tolerance: float = 0.1) -> bool:
        """
        Three Black Crows Pattern - strong bearish reversal

        Args:
            List of three candle OHLC data
            tolerance: Tolerance for consecutive red candles

        Returns:
            True if three black crows pattern detected
        """
        if len(open_candles) < 3:
            return False

        # Check if all three are red
        for i in range(3):
            open_price, high, low, close = open_candles[i]
            if close >= open_price:
                return False

        # Check for continuous downward movement
        open_prices = [c[0] for c in open_candles]
        close_prices = [c[3] for c in open_candles]

        # Each close should be lower than previous open
        continuous = all(
            close_prices[i] < open_prices[i - 1]
            for i in range(1, 3)
        )

        # Each candle should be at least as long as previous
        bodies = [abs(close_prices[i] - open_prices[i]) for i in range(3)]
        growing_bodies = all(bodies[i] >= bodies[i - 1] * (1 - tolerance)
                            for i in range(1, 3))

        return continuous and growing_bodies

    @staticmethod
    def detect_morning_star(open_candles: List[Tuple[float, float, float, float]],
                       tolerance: float = 0.1) -> bool:
        """
        Morning Star Pattern - bullish reversal

        Args:
            List of three candle OHLC data
            tolerance: Tolerance for pattern shape

        Returns:
            True if morning star pattern detected
        """
        if len(open_candles) < 3:
            return False

        # First candle should be bearish
        is_first_bearish = open_candles[0][3] < open_candles[0][0]

        # Second candle should be doji or small
        is_doji = CandlestickPatterns.detect_doji(*open_candles[1])

        # Third candle should be green and engulfing
        open_price, high, low, close = open_candles[2]
        is_bullish = close > open_price

        # Third candle should be large enough to cover first candle
        is_enough = close > open_candles[0][0]

        return is_first_bearish and (is_doji or abs(open_candles[1][3] - open_candles[1][0]) < 0.1 * (high - low)) and is_bullish and is_enough

    @staticmethod
    def detect_evening_star(open_candles: List[Tuple[float, float, float, float]],
                       tolerance: float = 0.1) -> bool:
        """
        Evening Star Pattern - bearish reversal

        Args:
            List of three candle OHLC data
            tolerance: Tolerance for pattern shape

        Returns:
            True if evening star pattern detected
        """
        if len(open_candles) < 3:
            return False

        # First candle should be bullish
        is_first_bullish = open_candles[0][3] > open_candles[0][0]

        # Second candle should be doji or small
        is_doji = CandlestickPatterns.detect_doji(*open_candles[1])

        # Third candle should be red and large
        open_price, high, low, close = open_candles[2]
        is_bearish = close < open_price

        # Third candle should be large enough to cover first candle
        is_enough = close < open_candles[0][0]

        return is_first_bullish and (is_doji or abs(open_candles[1][3] - open_candles[1][0]) < 0.1 * (high - low)) and is_bearish and is_enough


class TrendPatterns:
    """Detect trend patterns and formations"""

    @staticmethod
    def detect_upper_channel_open(open_price: float, high: float, low: float,
                              prev_open: float, prev_high: float, prev_low: float,
                              prev_close: float) -> bool:
        """
        Upper Channel Open - candle opening above previous close

        Args:
            Current and previous candle OHLC data

        Returns:
            True if upper channel open detected
        """
        return open_price > prev_close

    @staticmethod
    def detect_lower_channel_open(open_price: float, high: float, low: float,
                              prev_open: float, prev_high: float, prev_low: float,
                              prev_close: float) -> bool:
        """
        Lower Channel Open - candle opening below previous close

        Args:
            Current and previous candle OHLC data

        Returns:
            True if lower channel open detected
        """
        return open_price < prev_close

    @staticmethod
    def detect_upper_trend_channel(candles: List[Tuple[float, float, float, float]],
                              lower_bound: float, upper_bound: float,
                              tolerance: float = 0.02) -> bool:
        """
        Upper Trend Channel - price maintains within channel

        Args:
            List of candle OHLC data
            lower_bound, upper_bound: Channel bounds
            tolerance: Tolerance for boundary crossing

        Returns:
            True if upper trend channel detected
        """
        if len(candles) < 5:
            return False

        # Check if most candles are within channel
        within_channel = 0
        for open_price, high, low, close in candles[-5:]:
            is_within = low >= lower_bound and high <= upper_bound
            if is_within:
                within_channel += 1

        return within_channel / 5 >= (1 - tolerance)

    @staticmethod
    def detect_support_level(candles: List[Tuple[float, float, float, float]],
                         lookback: int = 20, tolerance: float = 0.02) -> bool:
        """
        Support Level - price bounces from support

        Args:
            List of candle OHLC data
            lookback: Lookback period
            tolerance: Tolerance for bounce

        Returns:
            True if support level detected
        """
        if len(candles) < lookback + 1:
            return False

        # Calculate support using low prices
        lows = [c[2] for c in candles[-lookback:]]
        support = min(lows)

        # Check for bounce
        current_low = candles[-1][2]
        previous_low = candles[-2][2]

        # Price should be near support
        is_near_support = abs(current_low - support) / support < tolerance

        # Should have bounced
        bounced = current_low < previous_low

        return is_near_support and bounced

    @staticmethod
    def detect_resistance_level(candles: List[Tuple[float, float, float, float]],
                            lookback: int = 20, tolerance: float = 0.02) -> bool:
        """
        Resistance Level - price hits resistance and bounces down

        Args:
            List of candle OHLC data
            lookback: Lookback period
            tolerance: Tolerance for bounce

        Returns:
            True if resistance level detected
        """
        if len(candles) < lookback + 1:
            return False

        # Calculate resistance using high prices
        highs = [c[1] for c in candles[-lookback:]]
        resistance = max(highs)

        # Check for rejection
        current_high = candles[-1][1]
        previous_high = candles[-2][1]

        # Price should be near resistance
        is_near_resistance = abs(current_high - resistance) / resistance < tolerance

        # Should have rejected
        rejected = current_high > previous_high

        return is_near_resistance and rejected

    @staticmethod
    def detect_triangle_pattern(candles: List[Tuple[float, float, float, float]],
                           pattern_type: str = 'symmetric') -> bool:
        """
        Triangle Pattern - converging price movement

        Args:
            List of candle OHLC data
            pattern_type: 'ascending', 'descending', or 'symmetric'

        Returns:
            True if triangle pattern detected
        """
        if len(candles) < 10:
            return False

        # Get highs and lows
        highs = [c[1] for c in candles[-10:]]
        lows = [c[2] for c in candles[-10:]]

        # Calculate trend of highs and lows
        high_trend = highs[-1] - highs[0]
        low_trend = lows[-1] - lows[0]

        if pattern_type == 'symmetric':
            # Both converge towards each other
            return abs(high_trend) > 0 and abs(low_trend) > 0

        elif pattern_type == 'ascending':
            # Highs increase, lows decrease or stay flat
            return high_trend > 0 and low_trend <= 0

        elif pattern_type == 'descending':
            # Highs decrease, lows increase or stay flat
            return high_trend <= 0 and low_trend > 0

        return False

    @staticmethod
    def detect_chart_pattern(candles: List[Tuple[float, float, float, float]],
                         pattern_name: str) -> bool:
        """
        Detect various chart patterns

        Args:
            List of candle OHLC data
            pattern_name: Name of the pattern to detect

        Returns:
            True if pattern detected
        """
        pattern_methods = {
            'bullish_engulfing': lambda: CandlestickPatterns.detect_bullish_engulfing(
                candles[-1][0], candles[-1][1], candles[-1][2], candles[-1][3],
                candles[-2][0], candles[-2][1], candles[-2][2], candles[-2][3]
            ),
            'bearish_engulfing': lambda: CandlestickPatterns.detect_bearish_engulfing(
                candles[-1][0], candles[-1][1], candles[-1][2], candles[-1][3],
                candles[-2][0], candles[-2][1], candles[-2][2], candles[-2][3]
            ),
            'doji': lambda: CandlestickPatterns.detect_doji(
                candles[-1][0], candles[-1][1], candles[-1][2], candles[-1][3]
            ),
            'hammer': lambda: CandlestickPatterns.detect_hammer(
                candles[-1][0], candles[-1][1], candles[-1][2], candles[-1][3]
            ),
            'shooting_star': lambda: CandlestickPatterns.detect_shooting_star(
                candles[-1][0], candles[-1][1], candles[-1][2], candles[-1][3]
            ),
            'bullish_harami': lambda: CandlestickPatterns.detect_bullish_harami(
                candles[-1][0], candles[-1][1], candles[-1][2], candles[-1][3],
                candles[-2][0], candles[-2][1], candles[-2][2], candles[-2][3]
            ),
            'bearish_harami': lambda: CandlestickPatterns.detect_bearish_harami(
                candles[-1][0], candles[-1][1], candles[-1][2], candles[-1][3],
                candles[-2][0], candles[-2][1], candles[-2][2], candles[-2][3]
            ),
            'three_white_soldiers': lambda: CandlestickPatterns.detect_three_white_soldiers(candles[-3:]),
            'three_black_crows': lambda: CandlestickPatterns.detect_three_black_crows(candles[-3:]),
            'morning_star': lambda: CandlestickPatterns.detect_morning_star(candles[-3:]),
            'evening_star': lambda: CandlestickPatterns.detect_evening_star(candles[-3:])
        }

        method = pattern_methods.get(pattern_name)
        if method:
            return method()

        return False


class VolumePatterns:
    """Detect volume patterns"""

    @staticmethod
    def detect_volume_spike(candles: List[Tuple[float, float, float, float]],
                       threshold: float = 1.5) -> bool:
        """
        Volume Spike - unusually high trading volume

        Args:
            List of candle OHLC data
            threshold: Multiple of average volume

        Returns:
            True if volume spike detected
        """
        if len(candles) < 20:
            return False

        # Calculate average volume
        avg_volume = sum(c[4] for c in candles[-20:]) / 20 if len(candles) >= 20 else 0
        current_volume = candles[-1][4]

        if avg_volume == 0:
            return False

        return current_volume > threshold * avg_volume

    @staticmethod
    def detect_volume_decline(candles: List[Tuple[float, float, float, float]],
                         threshold: float = 0.5) -> bool:
        """
        Volume Decline - unusually low trading volume

        Args:
            List of candle OHLC data
            threshold: Fraction of average volume

        Returns:
            True if volume decline detected
        """
        if len(candles) < 20:
            return False

        # Calculate average volume
        avg_volume = sum(c[4] for c in candles[-20:]) / 20 if len(candles) >= 20 else 0
        current_volume = candles[-1][4]

        if avg_volume == 0:
            return False

        return current_volume < threshold * avg_volume

    @staticmethod
    def detect_volume_surge_and_decline(candles: List[Tuple[float, float, float, float]],
                                    window: int = 3) -> bool:
        """
        Volume Surge and Decline - typical breakout pattern

        Args:
            List of candle OHLC data
            window: Number of candles to check

        Returns:
            True if surge then decline pattern detected
        """
        if len(candles) < window * 2:
            return False

        # Check for surge
        surge = VolumePatterns.detect_volume_spike(candles, threshold=1.5)

        # Check for decline
        decline = VolumePatterns.detect_volume_decline(candles[-window:], threshold=0.7)

        return surge and decline


class MarketPatternDetector:
    """Comprehensive pattern detection"""

    def __init__(self):
        self.candle_patterns = CandlestickPatterns()
        self.trend_patterns = TrendPatterns()
        self.volume_patterns = VolumePatterns()

    def detect_all_patterns(self, df: pd.DataFrame,
                           min_candles: int = 5) -> Dict[str, List[Dict]]:
        """
        Detect all patterns in market data

        Args:
            df: DataFrame with OHLCV data
            min_candles: Minimum number of candles needed

        Returns:
            Dictionary with pattern lists
        """
        patterns = {
            'candlestick': [],
            'trend': [],
            'volume': [],
            'all': []
        }

        if df.empty or len(df) < min_candles:
            return patterns

        # Extract candle data
        candles = []
        for i in range(len(df)):
            candles.append((
                float(df['open'].iloc[i]),
                float(df['high'].iloc[i]),
                float(df['low'].iloc[i]),
                float(df['close'].iloc[i]),
                float(df['volume'].iloc[i])
            ))

        # Detect candlestick patterns
        pattern_configs = [
            ('bullish_engulfing', 'BULLISH_ENGULFING', 'strong_buy'),
            ('bearish_engulfing', 'BEARISH_ENGULFING', 'strong_sell'),
            ('doji', 'DOJI', 'neutral'),
            ('hammer', 'HAMMER', 'buy'),
            ('shooting_star', 'SHOOTING_STAR', 'sell'),
            ('bullish_harami', 'BULLISH_HARAMI', 'buy'),
            ('bearish_harami', 'BEARISH_HARAMI', 'sell'),
            ('three_white_soldiers', 'THREE_WHITE_SOLDIERS', 'strong_buy'),
            ('three_black_crows', 'THREE_BLACK_CROWS', 'strong_sell'),
            ('morning_star', 'MORNING_STAR', 'buy'),
            ('evening_star', 'EVENING_STAR', 'sell')
        ]

        for pattern_name, pattern_label, sentiment in pattern_configs:
            if self.candle_patterns.detect_chart_pattern(candles, pattern_name):
                patterns['candlestick'].append({
                    'type': pattern_label,
                    'sentiment': sentiment,
                    'symbol': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None,
                    'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
                })

        # Detect trend patterns
        if self.trend_patterns.detect_support_level(candles):
            patterns['trend'].append({
                'type': 'SUPPORT_LEVEL',
                'sentiment': 'buy',
                'symbol': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None,
                'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
            })

        if self.trend_patterns.detect_resistance_level(candles):
            patterns['trend'].append({
                'type': 'RESISTANCE_LEVEL',
                'sentiment': 'sell',
                'symbol': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None,
                'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
            })

        # Detect volume patterns
        if self.volume_patterns.detect_volume_spike(candles):
            patterns['volume'].append({
                'type': 'VOLUME_SPIKE',
                'sentiment': 'neutral',
                'symbol': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None,
                'timestamp': df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else None
            })

        # Add all patterns
        patterns['all'] = (
            patterns['candlestick'] +
            patterns['trend'] +
            patterns['volume']
        )

        # Sort by sentiment (strong_buy > buy > neutral > sell > strong_sell)
        sentiment_order = {'strong_buy': 0, 'buy': 1, 'neutral': 2, 'sell': 3, 'strong_sell': 4}
        patterns['all'].sort(
            key=lambda x: sentiment_order.get(x.get('sentiment', 'neutral'), 2)
        )

        return patterns

    def get_pattern_sentiment_score(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate sentiment score from patterns

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with sentiment components
        """
        patterns = self.detect_all_patterns(df)

        if not patterns['all']:
            return {'score': 0.0, 'components': {}}

        sentiment_values = {
            'strong_buy': 1.0,
            'buy': 0.5,
            'neutral': 0.0,
            'sell': -0.5,
            'strong_sell': -1.0
        }

        total_score = 0.0
        count = 0

        for pattern in patterns['all']:
            sentiment = pattern.get('sentiment', 'neutral')
            total_score += sentiment_values.get(sentiment, 0)
            count += 1

        return {
            'score': float(total_score / count) if count > 0 else 0.0,
            'components': {
                'buy_count': sum(1 for p in patterns['all'] if p.get('sentiment') in ['buy', 'strong_buy']),
                'sell_count': sum(1 for p in patterns['all'] if p.get('sentiment') in ['sell', 'strong_sell'])
            }
        }

    def generate_trading_signals(self, df: pd.DataFrame) -> List[Dict]:
        """
        Generate trading signals based on detected patterns

        Args:
            df: DataFrame with OHLCV data

        Returns:
            List of trading signals
        """
        signals = []

        patterns = self.detect_all_patterns(df)

        for pattern in patterns['all']:
            signal = {
                'pattern_type': pattern['type'],
                'sentiment': pattern.get('sentiment', 'neutral'),
                'signal': 'BUY' if pattern.get('sentiment') in ['buy', 'strong_buy'] else
                         'SELL' if pattern.get('sentiment') in ['sell', 'strong_sell'] else 'HOLD',
                'timestamp': pattern.get('timestamp')
            }
            signals.append(signal)

        return signals