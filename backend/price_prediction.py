"""
Price Prediction Module

Provides ML-based price prediction for cryptocurrency assets.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import logging
import joblib
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Calculate technical indicators for price prediction"""

    @staticmethod
    def calculate_sma(data: pd.Series, window: int = 20) -> pd.Series:
        """Simple Moving Average"""
        return data.rolling(window=window).mean()

    @staticmethod
    def calculate_ema(data: pd.Series, window: int = 20) -> pd.Series:
        """Exponential Moving Average"""
        return data.ewm(span=window, adjust=False).mean()

    @staticmethod
    def calculate_rsi(data: pd.Series, window: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_macd(data: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Moving Average Convergence Divergence"""
        ema12 = data.ewm(span=12, adjust=False).mean()
        ema26 = data.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal
        return macd, signal, histogram

    @staticmethod
    def calculate_bollinger_bands(data: pd.Series, window: int = 20) -> Dict[str, pd.Series]:
        """Bollinger Bands"""
        sma = data.rolling(window=window).mean()
        std = data.rolling(window=window).std()
        upper_band = sma + (std * 2)
        lower_band = sma - (std * 2)
        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band
        }

    @staticmethod
    def calculate_volatility(data: pd.Series, window: int = 20) -> pd.Series:
        """Historical volatility"""
        return data.rolling(window=window).std()

    @staticmethod
    def calculate_volatility_ratio(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """Average True Range (ATR) - measures volatility"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=window).mean()
        return atr

    @staticmethod
    def calculate_momentum(data: pd.Series, window: int = 10) -> pd.Series:
        """Price momentum indicator"""
        return data.diff(periods=window)

    @staticmethod
    def calculate_crossover_signals(sma_short: pd.Series, sma_long: pd.Series) -> pd.Series:
        """Generate crossover signals"""
        signals = pd.Series(0, index=sma_short.index)
        signals[sma_short > sma_long] = 1  # Buy signal
        signals[sma_short < sma_long] = -1  # Sell signal
        return signals

    @staticmethod
    def create_features(df: pd.DataFrame) -> pd.DataFrame:
        """Create comprehensive feature set from OHLC data"""
        df = df.copy()

        # Price-based features
        df['sma_20'] = TechnicalIndicators.calculate_sma(df['close'], 20)
        df['sma_50'] = TechnicalIndicators.calculate_sma(df['close'], 50)
        df['sma_200'] = TechnicalIndicators.calculate_sma(df['close'], 200)

        # Momentum features
        df['rsi'] = TechnicalIndicators.calculate_rsi(df['close'], 14)
        df['momentum_10'] = TechnicalIndicators.calculate_momentum(df['close'], 10)
        df['momentum_20'] = TechnicalIndicators.calculate_momentum(df['close'], 20)

        # Volatility features
        df['volatility_20'] = TechnicalIndicators.calculate_volatility(df['close'], 20)
        df['atr'] = TechnicalIndicators.calculate_volatility_ratio(df['high'], df['low'], df['close'], 14)

        # MACD features
        df['macd'], df['macd_signal'], df['macd_hist'] = TechnicalIndicators.calculate_macd(df['close'])

        # Bollinger Bands
        bb = TechnicalIndicators.calculate_bollinger_bands(df['close'], 20)
        df['bb_upper'] = bb['upper']
        df['bb_middle'] = bb['middle']
        df['bb_lower'] = bb['lower']
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

        # Price changes
        df['price_change'] = df['close'].pct_change()
        df['price_change_1h'] = df['close'].pct_change(1)
        df['price_change_4h'] = df['close'].pct_change(4)
        df['price_change_24h'] = df['close'].pct_change(24)

        # Volume features
        df['volume_ma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma_20']

        # Normalize data
        df = df.ffill().bfill()

        return df.dropna()

    @staticmethod
    def get_current_signals(df: pd.DataFrame) -> Dict[str, float]:
        """Get current technical signals"""
        if df.empty:
            return {}

        signals = {}

        # SMA Crossovers
        signals['sma_cross_short_long'] = float(df['sma_20'].iloc[-1] > df['sma_50'].iloc[-1])
        signals['sma_cross_long_long'] = float(df['sma_50'].iloc[-1] > df['sma_200'].iloc[-1])

        # RSI
        rsi = df['rsi'].iloc[-1]
        signals['rsi'] = float(rsi)
        signals['rsi_overbought'] = float(rsi > 70)
        signals['rsi_oversold'] = float(rsi < 30)
        signals['rsi_neutral'] = float(30 <= rsi <= 70)

        # MACD
        signals['macd_bullish'] = float(df['macd'].iloc[-1] > df['macd_signal'].iloc[-1])
        signals['macd_hist_bullish'] = float(df['macd_hist'].iloc[-1] > 0)

        # Bollinger Bands
        close = df['close'].iloc[-1]
        signals['bb_upper'] = float(df['bb_upper'].iloc[-1])
        signals['bb_lower'] = float(df['bb_lower'].iloc[-1])
        signals['price_at_bb_upper'] = float(close >= df['bb_upper'].iloc[-1])
        signals['price_at_bb_lower'] = float(close <= df['bb_lower'].iloc[-1])

        # Volatility and trend context
        signals['volatility_20'] = float(df['volatility_20'].iloc[-1])
        signals['atr'] = float(df['atr'].iloc[-1])
        signals['close'] = float(close)
        signals['volatility_pct'] = float(df['volatility_20'].iloc[-1] / close) if close else 0.0
        signals['atr_pct'] = float(df['atr'].iloc[-1] / close) if close else 0.0

        # Volume
        signals['volume_surge'] = float(df['volume_ratio'].iloc[-1] > 2)

        return signals


class PricePredictionModel:
    """Machine learning model for price prediction"""

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = None
        self.is_trained = False
        self.predict_window = 1  # hours

    def get_model_path(self, symbol: str) -> Path:
        """Get the path to the saved model for a symbol"""
        models_dir = Path.home() / ".agent" / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir / f"{symbol.upper()}.pkl"

    def save(self, symbol: str) -> bool:
        """Save the trained model and scaler to disk"""
        if not self.is_trained or self.model is None:
            logger.warning("Attempted to save an untrained model")
            return False
            
        try:
            path = self.get_model_path(symbol)
            state = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_columns': self.feature_columns,
                'predict_window': self.predict_window
            }
            joblib.dump(state, path)
            logger.info(f"Model saved to {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save model for {symbol}: {e}")
            return False

    def load(self, symbol: str) -> bool:
        """Load a trained model and scaler from disk"""
        path = self.get_model_path(symbol)
        if not path.exists():
            return False
            
        try:
            state = joblib.load(path)
            self.model = state['model']
            self.scaler = state['scaler']
            self.feature_columns = state['feature_columns']
            self.predict_window = state.get('predict_window', 1)
            self.is_trained = True
            logger.info(f"Model loaded from {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model for {symbol}: {e}")
            return False

    def train(self, df: pd.DataFrame, target_column: str = 'close',
              features: Optional[List[str]] = None) -> float:
        """
        Train the prediction model

        Args:
            df: DataFrame with OHLCV data and features
            target_column: Target column to predict
            features: List of feature columns to use

        Returns:
            Mean Absolute Error of training set
        """
        if features is None:
            features = [col for col in df.columns
                       if col != target_column and 'close' not in col]

        self.feature_columns = features

        # Prepare data
        df_train = df.copy()
        df_train['future_target'] = df_train[target_column].shift(-self.predict_window)
        df_train = df_train.dropna()
        
        X = df_train[features].values
        y = df_train['future_target'].values

        # Split data
        train_size = int(len(X) * 0.8)
        X_train, X_test = X[:train_size], X[train_size:]
        y_train, y_test = y[:train_size], y[train_size:]

        # Scale data
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Create and train model
        self.model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )

        self.model.fit(X_train_scaled, y_train)

        # Evaluate
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)

        logger.info(f"Model trained - Train R²: {train_score:.4f}, Test R²: {test_score:.4f}")

        self.is_trained = True
        return test_score

    def predict(self, df: pd.DataFrame, hours_ahead: int = 1) -> pd.Series:
        """
        Predict future prices

        Args:
            df: DataFrame with OHLCV data
            hours_ahead: Number of hours ahead to predict

        Returns:
            Series of predicted prices
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model must be trained before prediction")

        # Ensure df has same features
        features_to_use = [col for col in self.feature_columns
                          if col in df.columns]

        if len(features_to_use) != len(self.feature_columns):
            logger.warning("Some features missing, using available features")

        # Forecast from the latest known feature row. Using the full history here
        # creates one prediction per historical candle, which does not match the
        # requested future horizon.
        X = df[features_to_use].tail(1).values
        X_scaled = self.scaler.transform(X)

        # Predict
        next_prediction = float(self.model.predict(X_scaled)[0])
        predictions = np.repeat(next_prediction, hours_ahead)

        # Create result series with dates
        prediction_dates = pd.date_range(
            start=df.index[-1] + timedelta(hours=1),
            periods=hours_ahead,
            freq='h'
        )

        return pd.Series(predictions, index=prediction_dates)

    def predict_multiple_stocks(self, stock_dfs: Dict[str, pd.DataFrame],
                               hours_ahead: int = 1) -> Dict[str, pd.Series]:
        """
        Predict prices for multiple stocks

        Args:
            stock_dfs: Dictionary mapping symbol to OHLCV DataFrame
            hours_ahead: Number of hours ahead to predict

        Returns:
            Dictionary mapping symbol to predicted prices
        """
        predictions = {}

        for symbol, df in stock_dfs.items():
            try:
                if self.is_trained:
                    predictions[symbol] = self.predict(df, hours_ahead)
                else:
                    logger.warning(f"Model not trained, using naive prediction for {symbol}")
                    predictions[symbol] = self.naive_prediction(df, hours_ahead)
            except Exception as e:
                logger.error(f"Error predicting {symbol}: {e}")
                predictions[symbol] = pd.Series([])

        return predictions

    def naive_prediction(self, df: pd.DataFrame, hours_ahead: int = 1) -> pd.Series:
        """Simple prediction using last known price"""
        last_price = df['close'].iloc[-1]
        prediction_dates = pd.date_range(
            start=df.index[-1] + timedelta(hours=1),
            periods=hours_ahead,
            freq='H'
        )
        return pd.Series([last_price] * hours_ahead, index=prediction_dates)

    def get_confidence_interval(self, df: pd.DataFrame, hours_ahead: int = 1,
                                confidence: float = 0.95) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Get prediction with confidence interval using random forest ensemble

        Args:
            df: DataFrame with features
            hours_ahead: Number of hours ahead
            confidence: Confidence level

        Returns:
            Tuple of (predictions, lower_bound, upper_bound)
        """
        features = [col for col in self.feature_columns if col in df.columns]

        X = df[features].values
        X_scaled = self.scaler.transform(X)

        # Run multiple predictions with different random seeds
        n_predictions = 20
        all_predictions = []

        for _ in range(n_predictions):
            model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=np.random.randint(1000, 10000)
            )
            model.fit(X_scaled, df['close'].values)
            all_predictions.append(model.predict(X_scaled))

        all_predictions = np.array(all_predictions)

        # Get predictions for next period
        base_predictions = all_predictions[-1]

        # Calculate confidence intervals
        lower_percentile = (1 - confidence) / 2 * 100
        upper_percentile = (1 + confidence) / 2 * 100

        lower_bound = np.percentile(all_predictions, lower_percentile, axis=0)
        upper_bound = np.percentile(all_predictions, upper_percentile, axis=0)

        return pd.Series(base_predictions, index=df.index), pd.Series(lower_bound, index=df.index), pd.Series(upper_bound, index=df.index)

    def calculate_expected_return(self, df: pd.DataFrame, hours_ahead: int = 1) -> float:
        """
        Calculate expected return for given time horizon

        Args:
            df: Current DataFrame with features
            hours_ahead: Time horizon in hours

        Returns:
            Expected percentage return
        """
        current_price = df['close'].iloc[-1]

        # Predict future prices
        predictions = self.predict(df, hours_ahead)
        future_price = predictions.iloc[-1] if len(predictions) > 0 else current_price

        # Calculate expected return
        expected_return = (future_price - current_price) / current_price
        expected_return_pct = expected_return * 100

        return expected_return_pct

    def get_trading_signals(self, df: pd.DataFrame, hours_ahead: int = 1,
                          threshold: float = 0.02, confidence_modifier: float = 1.0,
                          rsi_overbought_threshold: float = 70.0,
                          rsi_oversold_threshold: float = 30.0,
                          max_volatility_pct: float = 0.08,
                          conservative_mode: bool = True) -> Dict[str, float]:
        """
        Generate trading signals based on prediction.

        Adds a conservative guardrail layer so the model does not issue BUY
        purely from expected return when the market is already overbought or
        unusually volatile.
        """
        expected_return = self.calculate_expected_return(df, hours_ahead)
        technicals = TechnicalIndicators.get_current_signals(df)

        rsi = float(technicals.get('rsi', 50.0))
        volatility_pct = float(technicals.get('volatility_pct', 0.0))
        atr_pct = float(technicals.get('atr_pct', 0.0))
        macd_bullish = bool(technicals.get('macd_bullish', 0.0))
        price_at_bb_upper = bool(technicals.get('price_at_bb_upper', 0.0))
        price_at_bb_lower = bool(technicals.get('price_at_bb_lower', 0.0))

        action = 'HOLD'
        reason = 'threshold_not_met'
        threshold_pct = threshold * 100.0
        high_volatility = max(volatility_pct, atr_pct) > max_volatility_pct

        if expected_return > threshold_pct:
            action = 'BUY'
            reason = 'predicted_return_above_threshold'
        elif expected_return < -threshold_pct:
            action = 'SELL'
            reason = 'predicted_return_below_threshold'

        if conservative_mode:
            if action == 'BUY':
                if rsi >= rsi_overbought_threshold:
                    action = 'HOLD'
                    reason = 'buy_veto_overbought_rsi'
                elif price_at_bb_upper:
                    action = 'HOLD'
                    reason = 'buy_veto_upper_bollinger'
                elif high_volatility and not macd_bullish:
                    action = 'HOLD'
                    reason = 'buy_veto_high_volatility'

            elif action == 'SELL':
                if rsi <= rsi_oversold_threshold:
                    action = 'HOLD'
                    reason = 'sell_veto_oversold_rsi'
                elif price_at_bb_lower:
                    action = 'HOLD'
                    reason = 'sell_veto_lower_bollinger'

        base_confidence = min(abs(expected_return) / threshold_pct, 1.0) if threshold_pct > 0 else 0.0

        if action == 'HOLD' and reason.startswith(('buy_veto_', 'sell_veto_')):
            base_confidence *= 0.5
        if high_volatility:
            base_confidence *= 0.8

        confidence = round(max(0.0, min(base_confidence * confidence_modifier, 1.0)), 3)

        return {
            'expected_return': round(expected_return, 4),
            'action': action,
            'confidence': confidence,
            'reason': reason,
            'rsi': round(rsi, 2),
            'volatility_pct': round(volatility_pct * 100, 4),
            'atr_pct': round(atr_pct * 100, 4),
            'conservative_mode': float(conservative_mode),
        }


class MarketStateAnalyzer:
    """Analyze current market state for context"""

    def __init__(self):
        self.model = PricePredictionModel()

    def analyze_market_trend(self, df: pd.DataFrame) -> str:
        """
        Analyze overall market trend

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Trend label: 'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        sma_short = df['sma_20'].iloc[-1]
        sma_long = df['sma_200'].iloc[-1]
        current_price = df['close'].iloc[-1]

        if current_price > sma_short > sma_long:
            return 'BULLISH'
        elif current_price < sma_short < sma_long:
            return 'BEARISH'
        else:
            return 'NEUTRAL'

    def get_market_momentum(self, df: pd.DataFrame) -> float:
        """
        Calculate market momentum score (-1 to 1)

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Momentum score (-1 to 1)
        """
        rsi = df['rsi'].iloc[-1]

        if rsi > 70:
            return min((rsi - 70) / 30, 1.0)
        elif rsi < 30:
            return max(-(rsi - 30) / 30, -1.0)
        else:
            return 0.0

    def get_volatility_level(self, df: pd.DataFrame) -> str:
        """
        Determine volatility level

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Volatility level: 'LOW', 'MEDIUM', 'HIGH'
        """
        volatility = df['volatility_20'].iloc[-1]
        avg_volatility = df['volatility_20'].mean()

        if volatility < avg_volatility * 0.5:
            return 'LOW'
        elif volatility < avg_volatility * 1.5:
            return 'MEDIUM'
        else:
            return 'HIGH'

