"""
Anomaly Detection Module

Detects unusual market activity, price movements, and trading patterns
that may indicate opportunities or risks.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger(__name__)


class VolumeAnomalyDetector:
    """Detect anomalies in trading volume"""

    def __init__(self, window: int = 20, std_threshold: float = 2.5):
        self.window = window
        self.std_threshold = std_threshold
        self.scaler = StandardScaler()

    def detect_surge(self, df: pd.DataFrame, threshold: float = 2.0) -> pd.Series:
        """
        Detect volume surges above average

        Args:
            df: DataFrame with 'volume' column
            threshold: Number of standard deviations above mean

        Returns:
            Boolean series indicating surges
        """
        if df.empty:
            return pd.Series([], dtype=bool)

        volume = df['volume'].values.reshape(-1, 1)
        volume_scaled = self.scaler.fit_transform(volume)

        vol_mean = np.mean(volume_scaled, axis=0)[0]
        vol_std = np.std(volume_scaled, axis=0)[0]

        is_surge = volume_scaled > (vol_mean + threshold * vol_std)
        return pd.Series(is_surge.flatten(), index=df.index)

    def detect_contract(self, df: pd.DataFrame, threshold: float = 0.5) -> pd.Series:
        """
        Detect unusually low volume (contract)

        Args:
            df: DataFrame with 'volume' column
            threshold: Standard deviations below mean

        Returns:
            Boolean series indicating contracts
        """
        if df.empty:
            return pd.Series([], dtype=bool)

        volume = df['volume'].values.reshape(-1, 1)
        volume_scaled = self.scaler.fit_transform(volume)

        vol_mean = np.mean(volume_scaled, axis=0)[0]
        vol_std = np.std(volume_scaled, axis=0)[0]

        is_contract = volume_scaled < (vol_mean - threshold * vol_std)
        return pd.Series(is_contract.flatten(), index=df.index)

    def get_volume_stats(self, df: pd.DataFrame) -> Dict[str, float]:
        """Get current volume statistics"""
        if df.empty:
            return {}

        stats = {
            'current_volume': float(df['volume'].iloc[-1]),
            'avg_volume_20': float(df['volume'].rolling(20).mean().iloc[-1]),
            'volume_ratio': float(df['volume'].iloc[-1] / df['volume'].rolling(20).mean().iloc[-1])
        }

        return stats


class PriceMovementAnomalyDetector:
    """Detect anomalies in price movements"""

    def __init__(self, window: int = 20, std_threshold: float = 2.5):
        self.window = window
        self.std_threshold = std_threshold
        self.scaler = StandardScaler()

    def detect_extreme_move(self, df: pd.DataFrame, direction: str = 'both',
                           threshold: float = 3.0) -> pd.Series:
        """
        Detect extreme price movements

        Args:
            df: DataFrame with 'close' column
            direction: 'up', 'down', or 'both'
            threshold: Number of standard deviations

        Returns:
            Boolean series indicating extreme moves
        """
        if df.empty:
            return pd.Series([], dtype=bool)

        returns = df['close'].pct_change().dropna()

        if direction == 'up':
            threshold *= -1  # Use negative threshold for upward moves

        returns_scaled = self.scaler.fit_transform(returns.values.reshape(-1, 1))
        is_extreme = returns_scaled > (self.std_threshold * np.std(returns_scaled))

        return pd.Series(is_extreme.flatten(), index=returns.index)

    def detect_volatility_surge(self, df: pd.DataFrame, threshold: float = 2.0) -> pd.Series:
        """
        Detect sudden increases in volatility

        Args:
            df: DataFrame with 'close' column
            threshold: Number of standard deviations above average

        Returns:
            Boolean series indicating volatility surges
        """
        if df.empty:
            return pd.Series([], dtype=bool)

        returns = df['close'].pct_change().dropna()
        volatility = returns.rolling(self.window).std()

        vol_mean = volatility.mean()
        vol_std = volatility.std()

        is_surge = volatility > (vol_mean + threshold * vol_std)
        return pd.Series(is_surge, index=volatility.index)

    def detect_mean_reversion(self, df: pd.DataFrame, lookback: int = 20) -> pd.Series:
        """
        Detect potential mean reversion opportunities

        Args:
            df: DataFrame with 'close' column
            lookback: Lookback period for moving averages

        Returns:
            Boolean series indicating mean reversion opportunities
        """
        if df.empty:
            return pd.Series([], dtype=bool)

        sma = df['close'].rolling(lookback).mean()
        std = df['close'].rolling(lookback).std()

        # Price far below SMA
        below_lower = df['close'] < (sma - 2 * std)
        # Price far above SMA
        above_upper = df['close'] > (sma + 2 * std)

        return below_lower | above_upper

    def get_price_change_stats(self, df: pd.DataFrame,
                              period: str = '24h') -> Dict[str, float]:
        """Get price change statistics"""
        if df.empty:
            return {}

        stats = {}

        if period == '1h':
            change = df['close'].pct_change(1)
        elif period == '4h':
            change = df['close'].pct_change(4)
        elif period == '24h':
            change = df['close'].pct_change(24)
        else:
            change = df['close'].pct_change()

        stats['current_change'] = float(change.iloc[-1] * 100)
        stats['max_change'] = float(change.max() * 100)
        stats['min_change'] = float(change.min() * 100)

        return stats


class TradingPatternAnomalyDetector:
    """Detect unusual trading patterns"""

    def __init__(self):
        self.volume_anomaly = VolumeAnomalyDetector()
        self.price_anomaly = PriceMovementAnomalyDetector()

    def detect_liquidity_spike(self, df: pd.DataFrame,
                               volume_threshold: float = 2.0,
                               price_move_threshold: float = 1.0) -> List[Dict]:
        """
        Detect liquidity spikes - both volume and price movement

        Args:
            df: DataFrame with OHLCV data
            volume_threshold: Volume threshold
            price_move_threshold: Price move threshold in %

        Returns:
            List of anomaly dictionaries
        """
        anomalies = []

        if df.empty:
            return anomalies

        # Detect volume surges
        volume_surge = self.volume_anomaly.detect_surge(df, volume_threshold)

        # Detect price moves
        price_change = df['close'].pct_change().dropna()
        extreme_moves = np.abs(price_change) > (price_move_threshold / 100)

        # Find correlations
        for i in range(len(df)):
            if i >= len(volume_surge) or i >= len(extreme_moves):
                break

            if volume_surge.iloc[i] and extreme_moves.iloc[i]:
                anomaly = {
                    'symbol': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                    'volume': float(df['volume'].iloc[i]),
                    'price': float(df['close'].iloc[i]),
                    'price_change_pct': float(price_change.iloc[i] * 100),
                    'type': 'LIQUIDITY_SPIKE',
                    'severity': 'HIGH'
                }
                anomalies.append(anomaly)

        return anomalies

    def detect_rug_pull(self, df: pd.DataFrame, lookback: int = 30) -> List[Dict]:
        """
        Detect potential rug pull patterns (rapid price drop after pump)

        Args:
            df: DataFrame with OHLCV data
            lookback: Lookback period

        Returns:
            List of potential rug pull anomalies
        """
        anomalies = []

        if df.empty or len(df) < lookback:
            return anomalies

        # Detect pumps (rapid price increases)
        price_change_24h = df['close'].pct_change(24)
        pumps = price_change_24h > 0.20  # More than 20% increase

        # Check if followed by rapid drops
        for i in range(len(pumps)):
            if not pumps.iloc[i]:
                continue

            # Look for drops in subsequent days
            for j in range(i + 1, min(i + 7, len(df))):
                if j >= len(df):
                    break

                days_later = (df.index[j] - df.index[i]).days if isinstance(df.index, pd.DatetimeIndex) else 1
                if days_later < 1:
                    continue

                price_change = df['close'].iloc[i] / df['close'].iloc[j] - 1

                if price_change < -0.30:  # More than 30% drop
                    anomaly = {
                        'symbol': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                        'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                        'pump_date': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                        'drop_date': df.index[j] if isinstance(df.index, pd.DatetimeIndex) else None,
                        'initial_price': float(df['close'].iloc[i]),
                        'final_price': float(df['close'].iloc[j]),
                        'price_change': float(price_change * 100),
                        'days_between': days_later,
                        'type': 'RUG_PULL',
                        'severity': 'CRITICAL'
                    }
                    anomalies.append(anomaly)
                    break

        return anomalies

    def detect_wick_spike(self, df: pd.DataFrame, threshold: float = 2.5) -> List[Dict]:
        """
        Detect large wicks (large difference between high and close or low and close)

        Args:
            df: DataFrame with OHLCV data
            threshold: Threshold in standard deviations

        Returns:
            List of wick spike anomalies
        """
        anomalies = []

        if df.empty:
            return anomalies

        # Calculate average body size
        body_size = np.abs(df['close'] - df['open'])
        avg_body = body_size.mean()

        # Calculate wick size (max of high-close and low-open)
        wick_size = np.maximum(df['high'] - df['close'], df['low'] - df['open'])

        # Find large wicks
        for i in range(len(df)):
            wick_ratio = wick_size.iloc[i] / (avg_body + 1e-10)

            if wick_ratio > threshold:
                anomaly = {
                    'symbol': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                    'open': float(df['open'].iloc[i]),
                    'high': float(df['high'].iloc[i]),
                    'low': float(df['low'].iloc[i]),
                    'close': float(df['close'].iloc[i]),
                    'wick_size': float(wick_size.iloc[i]),
                    'body_size': float(body_size.iloc[i]),
                    'wick_ratio': float(wick_ratio),
                    'type': 'WICK_SPIKE',
                    'severity': 'MEDIUM'
                }
                anomalies.append(anomaly)

        return anomalies

    def detect_unusual_spread(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect unusual bid-ask spread patterns

        Args:
            df: DataFrame with OHLCV data (simulated spread data)

        Returns:
            List of spread anomalies
        """
        anomalies = []

        if df.empty:
            return anomalies

        # Calculate average spread
        spread = df['high'] - df['low']
        avg_spread = spread.mean()

        # Find wide spreads
        for i in range(len(df)):
            if spread.iloc[i] > 3 * avg_spread:
                anomaly = {
                    'symbol': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                    'high': float(df['high'].iloc[i]),
                    'low': float(df['low'].iloc[i]),
                    'spread': float(spread.iloc[i]),
                    'avg_spread': float(avg_spread),
                    'spread_ratio': float(spread.iloc[i] / avg_spread),
                    'type': 'UNUSUAL_SPREAD',
                    'severity': 'MEDIUM'
                }
                anomalies.append(anomaly)

        return anomalies

    def detect_market_manipulation(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect potential market manipulation patterns

        Args:
            df: DataFrame with OHLCV data

        Returns:
            List of manipulation anomaly indicators
        """
        anomalies = []

        if df.empty:
            return anomalies

        # Check for consecutive large green candles
        green_candles = df['close'] > df['open']

        for i in range(len(green_candles) - 1):
            if green_candles.iloc[i] and green_candles.iloc[i + 1]:
                # Check for spike in volume
                volume_surge = df['volume'].iloc[i] > df['volume'].rolling(20).mean().iloc[i]

                if volume_surge:
                    anomaly = {
                        'symbol': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                        'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                        'type': 'CONSECUTIVE_LARGE_GREEN',
                        'severity': 'MEDIUM',
                        'details': {
                            'consecutive_count': 2,
                            'volume_surge': True
                        }
                    }
                    anomalies.append(anomaly)

        return anomalies

    def detect_frontrun_opportunity(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect front-running opportunities based on order book patterns

        Args:
            df: DataFrame with OHLCV data (simulated order book data)

        Returns:
            List of front-run opportunities
        """
        opportunities = []

        if df.empty:
            return opportunities

        # Check for large buy walls that don't result in price increase
        volume = df['volume'].rolling(20).mean()
        volume_surge = df['volume'] > volume * 1.5

        for i in range(len(volume_surge)):
            if volume_surge.iloc[i]:
                # Check if price moved up significantly
                price_change = df['close'].pct_change(3).iloc[i] if i + 3 < len(df) else 0

                if price_change < 0.01:  # Less than 1% increase despite volume surge
                    opportunity = {
                        'symbol': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                        'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                        'volume': float(df['volume'].iloc[i]),
                        'price': float(df['close'].iloc[i]),
                        'volume_surge': True,
                        'price_change_3h': float(price_change * 100),
                        'type': 'FRONTRUN_OPPORTUNITY',
                        'severity': 'MEDIUM'
                    }
                    opportunities.append(opportunity)

        return opportunities


class MarketAnomalyDetector:
    """Comprehensive market anomaly detection"""

    def __init__(self):
        self.volume_detector = VolumeAnomalyDetector()
        self.price_detector = PriceMovementAnomalyDetector()
        self.pattern_detector = TradingPatternAnomalyDetector()

    def detect_all_anomalies(self, df: pd.DataFrame) -> Dict[str, List[Dict]]:
        """
        Run all anomaly detection on market data

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with anomaly lists by type
        """
        anomalies = {
            'volume': [],
            'price': [],
            'patterns': [],
            'all': []
        }

        if df.empty:
            return anomalies

        # Detect volume anomalies
        volume_surge = self.volume_detector.detect_surge(df)
        anomalies['volume'].extend(self._create_volume_anomalies(df, volume_surge, 'SURGE'))

        volume_contract = self.volume_detector.detect_contract(df)
        anomalies['volume'].extend(self._create_volume_anomalies(df, volume_contract, 'CONTRACT'))

        # Detect price anomalies
        extreme_moves = self.price_detector.detect_extreme_move(df)
        anomalies['price'].extend(self._create_price_anomalies(df, extreme_moves, 'EXTREME_MOVE'))

        volatility_surge = self.price_detector.detect_volatility_surge(df)
        anomalies['price'].extend(self._create_price_anomalies(df, volatility_surge, 'VOLATILITY_SURGE'))

        # Detect patterns
        anomalies['patterns'].extend(
            self.pattern_detector.detect_liquidity_spike(df)
        )
        anomalies['patterns'].extend(
            self.pattern_detector.detect_wick_spike(df)
        )
        anomalies['patterns'].extend(
            self.pattern_detector.detect_rug_pull(df)
        )
        anomalies['patterns'].extend(
            self.pattern_detector.detect_market_manipulation(df)
        )
        anomalies['patterns'].extend(
            self.pattern_detector.detect_frontrun_opportunity(df)
        )

        # Add all anomalies to single list
        anomalies['all'] = (
            anomalies['volume'] +
            anomalies['price'] +
            anomalies['patterns']
        )

        # Sort by severity
        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        anomalies['all'].sort(
            key=lambda x: severity_order.get(x.get('severity', 'LOW'), 3)
        )

        return anomalies

    def _create_volume_anomalies(self, df: pd.DataFrame,
                                 anomaly_series: pd.Series,
                                 anomaly_type: str) -> List[Dict]:
        """Create volume anomaly dictionaries"""
        anomalies = []

        for i in range(len(anomaly_series)):
            if anomaly_series.iloc[i]:
                anomalies.append({
                    'symbol': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                    'volume': float(df['volume'].iloc[i]),
                    'avg_volume': float(df['volume'].rolling(20).mean().iloc[i]),
                    'type': anomaly_type,
                    'severity': 'HIGH' if anomaly_type == 'SURGE' else 'MEDIUM'
                })

        return anomalies

    def _create_price_anomalies(self, df: pd.DataFrame,
                               anomaly_series: pd.Series,
                               anomaly_type: str) -> List[Dict]:
        """Create price anomaly dictionaries"""
        anomalies = []

        for i in range(len(anomaly_series)):
            if anomaly_series.iloc[i]:
                anomalies.append({
                    'symbol': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else None,
                    'price': float(df['close'].iloc[i]),
                    'type': anomaly_type,
                    'severity': 'HIGH'
                })

        return anomalies

    def get_market_risk_score(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate overall market risk score

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with risk components
        """
        if df.empty:
            return {'risk_score': 0.0, 'components': {}}

        anomalies = self.detect_all_anomalies(df)
        total_anomalies = len(anomalies['all'])

        # Calculate components
        volume_anomalies = len(anomalies['volume'])
        price_anomalies = len(anomalies['price'])
        pattern_anomalies = len(anomalies['patterns'])

        # Normalize (assuming up to 10 anomalies each)
        score = (
            (volume_anomalies / 10) * 0.33 +
            (price_anomalies / 10) * 0.33 +
            (pattern_anomalies / 10) * 0.34
        )

        return {
            'risk_score': float(score),
            'components': {
                'volume_anomalies': float(volume_anomalies / 10),
                'price_anomalies': float(price_anomalies / 10),
                'pattern_anomalies': float(pattern_anomalies / 10)
            }
        }