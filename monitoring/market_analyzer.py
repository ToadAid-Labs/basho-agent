"""
Market analysis and condition monitoring.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict
from enum import Enum
import random
import statistics


class MarketCondition(Enum):
    """Market condition types."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDELINES = "sidelines"
    VOLATILE = "volatile"
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"


@dataclass
class MarketConditionData:
    """Represents current market condition."""
    condition: MarketCondition
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    volatility: float = 0.0  # 0.0 to 1.0
    volume: float = 0.0  # Normalized volume
    sentiment_score: float = 0.0  # -1.0 to 1.0


@dataclass
class VolatilityReport:
    """Volatility analysis report."""
    timestamp: datetime = field(default_factory=datetime.now)
    avg_volatility: float = 0.0
    max_volatility: float = 0.0
    min_volatility: float = 0.0
    trend: str = ""
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert report to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'avg_volatility': self.avg_volatility,
            'max_volatility': self.max_volatility,
            'min_volatility': self.min_volatility,
            'trend': self.trend,
            'recommendations': self.recommendations
        }


class MarketAnalyzer:
    """Analyzes market conditions and volatility."""

    def __init__(self):
        self.conditions: List[MarketConditionData] = []
        self.volatility_history: List[float] = []
        self.recent_signals: List[Dict] = []
        self.max_history = 100

    def analyze_market(self, price_data: List[Dict], current_time: Optional[datetime] = None) -> MarketConditionData:
        """
        Analyze current market conditions.

        Args:
            price_data: Recent price history
            current_time: Current timestamp (defaults to now)

        Returns:
            MarketConditionData with analysis
        """
        if not price_data:
            return self._default_condition(current_time)

        current_time = current_time or datetime.now()

        # Calculate metrics
        volatility = self._calculate_volatility(price_data)
        volume = self._calculate_volume(price_data)
        sentiment = self._calculate_sentiment(price_data)

        # Determine condition
        condition = self._determine_condition(volatility, sentiment, volume)

        # Create condition data
        condition_data = MarketConditionData(
            condition=condition,
            confidence=self._calculate_confidence(volatility, sentiment),
            timestamp=current_time,
            volatility=volatility,
            volume=volume,
            sentiment_score=sentiment
        )

        # Store and cleanup
        self.conditions.insert(0, condition_data)
        if len(self.conditions) > self.max_history:
            self.conditions = self.conditions[:self.max_history]

        return condition_data

    def _calculate_volatility(self, price_data: List[Dict]) -> float:
        """Calculate volatility from price data."""
        if len(price_data) < 2:
            return 0.0

        prices = [data['close'] for data in price_data]
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]

        if not returns:
            return 0.0

        volatility = statistics.mean(abs(r) for r in returns)
        return min(volatility, 1.0)  # Normalize to 0-1

    def _calculate_volume(self, price_data: List[Dict]) -> float:
        """Calculate normalized volume."""
        if not price_data:
            return 0.5

        volumes = [data.get('volume', 0) for data in price_data]
        avg_volume = statistics.mean(volumes)

        if avg_volume == 0:
            return 0.5

        # Normalize to 0-1 range (assuming typical range)
        return min((avg_volume / 1000000), 1.0)

    def _calculate_sentiment(self, price_data: List[Dict]) -> float:
        """Calculate sentiment score from price movement."""
        if len(price_data) < 2:
            return 0.0

        prices = [data['close'] for data in price_data]
        start_price = prices[0]
        end_price = prices[-1]

        change = (end_price - start_price) / start_price

        # Normalize to -1 to 1
        return min(max(change * 0.5, -1.0), 1.0)

    def _determine_condition(self, volatility: float, sentiment: float, volume: float) -> MarketCondition:
        """Determine overall market condition."""
        if volatility > 0.3:
            return MarketCondition.VOLATILE

        if sentiment > 0.3:
            return MarketCondition.BULLISH if volume > 0.4 else MarketCondition.RISK_ON
        elif sentiment < -0.3:
            return MarketCondition.BEARISH if volume > 0.4 else MarketCondition.RISK_OFF
        else:
            return MarketCondition.SIDELINES

    def _calculate_confidence(self, volatility: float, sentiment: float) -> float:
        """Calculate confidence in the analysis."""
        confidence = (1.0 - volatility) * 0.7 + abs(sentiment) * 0.3
        return min(max(confidence, 0.0), 1.0)

    def _default_condition(self, current_time: Optional[datetime] = None) -> MarketConditionData:
        """Return default condition."""
        current_time = current_time or datetime.now()
        return MarketConditionData(
            condition=MarketCondition.SIDELINES,
            confidence=0.5,
            timestamp=current_time,
            volatility=0.0,
            volume=0.5,
            sentiment_score=0.0
        )

    def generate_volatility_report(self, price_data: List[Dict]) -> VolatilityReport:
        """Generate a volatility analysis report."""
        if len(price_data) < 2:
            return VolatilityReport(
                recommendations=["Insufficient data for analysis"]
            )

        prices = [data['close'] for data in price_data]
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]

        volatilities = [abs(r) for r in returns]
        avg_vol = statistics.mean(volatilities) if volatilities else 0.0
        max_vol = max(volatilities) if volatilities else 0.0
        min_vol = min(volatilities) if volatilities else 0.0

        # Determine trend
        recent_vol = volatilities[-5:] if len(volatilities) >= 5 else volatilities
        if len(recent_vol) >= 2:
            trend = "increasing" if recent_vol[-1] > recent_vol[0] else "decreasing"
        else:
            trend = "stable"

        # Generate recommendations
        recommendations = self._generate_recommendations(avg_vol, trend)

        return VolatilityReport(
            avg_volatility=avg_vol * 100,  # Convert to percentage
            max_volatility=max_vol * 100,
            min_volatility=min_vol * 100,
            trend=trend,
            recommendations=recommendations
        )

    def _generate_recommendations(self, volatility: float, trend: str) -> List[str]:
        """Generate trading recommendations based on volatility."""
        recommendations = []

        if volatility > 0.15:  # High volatility
            recommendations.append("Consider reducing position sizes")
            recommendations.append("Use wider stop-losses")
            recommendations.append("Be cautious with large trades")
        elif volatility < 0.05:  # Low volatility
            recommendations.append("Look for momentum opportunities")
            recommendations.append("Consider scaling into positions")
            recommendations.append("Market may be consolidating")

        if trend == "increasing":
            recommendations.append("Volatility is increasing - consider tightening risk")
        elif trend == "decreasing":
            recommendations.append("Volatility is decreasing - look for breakout opportunities")

        return recommendations

    def get_current_condition(self) -> Optional[MarketConditionData]:
        """Get the most recent market condition."""
        return self.conditions[0] if self.conditions else None

    def get_historical_conditions(self, hours: int = 24) -> List[MarketConditionData]:
        """Get conditions from the past X hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [c for c in self.conditions if c.timestamp >= cutoff]

    def analyze_token(self, token_address: str, price_data: List[Dict]) -> Dict:
        """Analyze a specific token's market data."""
        condition = self.analyze_market(price_data)

        return {
            'token_address': token_address,
            'condition': condition.condition.value,
            'confidence': condition.confidence,
            'volatility': condition.volatility,
            'volume': condition.volume,
            'sentiment': condition.sentiment_score,
            'recommendation': self._get_token_recommendation(condition)
        }

    def _get_token_recommendation(self, condition: MarketConditionData) -> str:
        """Get trading recommendation based on condition."""
        if condition.confidence < 0.6:
            return "Wait for more clarity in market conditions"

        if condition.condition == MarketCondition.BULLISH:
            return "Consider taking long positions"
        elif condition.condition == MarketCondition.BEARISH:
            return "Consider taking defensive positions"
        elif condition.condition == MarketCondition.VOLATILE:
            return "Be cautious and use tight risk management"
        elif condition.condition == MarketCondition.RISK_ON:
            return "Moderate risk - consider selective trading"
        elif condition.condition == MarketCondition.RISK_OFF:
            return "Reduce exposure and wait for safer conditions"
        else:
            return "Market is neutral - look for setup opportunities"

    def generate_report(self) -> Dict:
        """Generate comprehensive market report."""
        current = self.get_current_condition()
        conditions_24h = self.get_historical_conditions(24)

        if not current:
            return {}

        # Count conditions in last 24 hours
        condition_counts = {c.value: 0 for c in MarketCondition}
        for c in conditions_24h:
            condition_counts[c.condition.value] += 1

        return {
            'current_condition': current.condition.value,
            'current_confidence': current.confidence,
            'volatility': current.volatility,
            'sentiment': current.sentiment_score,
            'volume': current.volume,
            'last_update': current.timestamp.isoformat(),
            'hourly_distribution': {
                k: v for k, v in condition_counts.items()
                if k != current.condition.value
            }
        }
