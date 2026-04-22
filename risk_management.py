"""
Risk Management Module
======================

Implements comprehensive risk management for trading strategies:
- Position sizing limits
- Stop-loss and take-profit automation
- Portfolio diversification checks
- Daily loss limits
- Maximum drawdown protection
- Risk-reward ratio tracking
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from dataclasses import dataclass, field
from enum import Enum
import math

# Import our tools
from tools.trust import TrustWalletAgent
from tools.market_data import MarketDataAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level categories"""
    LOW = "low"           # Conservative
    MEDIUM = "medium"     # Balanced
    HIGH = "high"         # Aggressive


class RiskEvent(Enum):
    """Risk event types"""
    POSITION_SIZE = "position_size"
    DAILY_LOSS = "daily_loss"
    MAX_DRAWDOWN = "max_drawdown"
    RISK_REWARD = "risk_reward"
    DIVERSIFICATION = "diversification"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


@dataclass
class RiskConfig:
    """Overall risk configuration"""
    max_daily_loss_pct: float = 2.0          # Maximum daily loss allowed
    max_drawdown_pct: float = 10.0           # Maximum drawdown allowed
    risk_per_trade_pct: float = 1.0          # Max risk per trade (2% of portfolio)
    max_position_size_pct: float = 10.0      # Max single position size
    min_risk_reward_ratio: float = 1.5       # Minimum risk-reward ratio
    max_portfolio_concentration: float = 30.0 # Max single asset allocation
    stop_loss_pct: float = 3.0               # Default stop-loss percentage
    take_profit_pct: float = 6.0             # Default take-profit percentage
    risk_level: RiskLevel = RiskLevel.MEDIUM
    
    # Narrative & Correlation Guard
    max_narrative_exposure_pct: float = 25.0  # Max 25% in one ecosystem (e.g. SOL, AI)
    max_correlated_positions: int = 3         # Max 3 tokens in the same category
    narrative_map: Dict[str, str] = field(default_factory=lambda: {
        "BTC": "L1", "ETH": "L1", "SOL": "L1",
        "PEPE": "MEME", "WIF": "MEME", "DOGE": "MEME", "SHIB": "MEME", "WOJAK": "MEME",
        "RNDR": "AI", "FET": "AI", "TAO": "AI", "NEAR": "AI",
        "LINK": "ORACLE", "PYTH": "ORACLE",
        "AAVE": "DEFI", "UNI": "DEFI", "SNX": "DEFI"
    })


@dataclass
class Position:
    """Active trading position with advanced management features"""
    token_address: str
    symbol: str
    entry_price: float
    amount: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    entry_time: datetime
    status: str = "open"  # open, closed, partial
    
    # Advanced features
    peak_price: float = 0.0
    is_trailing: bool = False
    trailing_activation_price: Optional[float] = None
    trailing_distance_atr: float = 2.0
    atr_value: float = 0.0
    
    breakeven_activation_price: Optional[float] = None
    has_moved_to_breakeven: bool = False
    
    partial_tp_targets: List[Dict[str, float]] = field(default_factory=list) # List of {'price': x, 'fraction': 0.5, 'hit': False}

    def __post_init__(self):
        if self.peak_price == 0.0:
            self.peak_price = self.entry_price

    @property
    def current_value(self) -> float:
        """Current position value"""
        return self.amount * self.entry_price # Note: In a real system, we'd use current price

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized profit/loss"""
        return 0.0 # Updated in manager


@dataclass
class RiskMetrics:
    """Current risk metrics"""
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


class RiskManager:
    """Comprehensive risk management system"""

    def __init__(self, trust_wallet: TrustWalletAgent, market_analyzer: MarketDataAnalyzer):
        """
        Initialize risk manager

        Args:
            trust_wallet: TrustWalletAgent for wallet operations
            market_analyzer: MarketDataAnalyzer for market data
        """
        self.trust_wallet = trust_wallet
        self.market_analyzer = market_analyzer

        # Risk configuration
        self.config = RiskConfig()

        # Active positions
        self.active_positions: Dict[str, Position] = {}

        # Trade history
        self.trade_history: List[Dict] = []

        # Portfolio tracking
        self.initial_portfolio_value: float = 0
        self.max_portfolio_value: float = 0
        self.current_max_drawdown: float = 0

        # Daily tracking
        self.daily_start_value: float = 0
        self.daily_trades: List[Dict] = []

        # Initialize tracking
        self._initialize_tracking()

    def _initialize_tracking(self):
        """Initialize or reset daily tracking"""
        now = datetime.now()

        # Check if we need to reset daily tracking
        if not hasattr(self, 'last_daily_reset') or \
           (now - self.last_daily_reset).days >= 1:

            self.daily_start_value = self._get_total_portfolio_value()
            self.daily_trades = []
            self.last_daily_reset = now
            logger.info(f"Daily tracking reset. Starting value: ${self.daily_start_value:.2f}")

    def _get_total_portfolio_value(self) -> float:
        """Get total portfolio value"""
        balance = self.trust_wallet.get_wallet_balance() if self.trust_wallet else 10000.0

        # Add unrealized position values
        total_positions = sum(pos.current_value for pos in self.active_positions.values())
        total_value = balance + total_positions

        return total_value

    def set_risk_level(self, level: RiskLevel):
        """Set overall risk level"""
        self.config.risk_level = level

        # Configure based on risk level
        if level == RiskLevel.LOW:
            self.config = RiskConfig(
                max_daily_loss_pct=1.0,
                max_drawdown_pct=5.0,
                risk_per_trade_pct=0.5,
                max_position_size_pct=5.0,
                min_risk_reward_ratio=2.0,
                stop_loss_pct=2.0,
                take_profit_pct=4.0
            )
        elif level == RiskLevel.HIGH:
            self.config = RiskConfig(
                max_daily_loss_pct=5.0,
                max_drawdown_pct=20.0,
                risk_per_trade_pct=3.0,
                max_position_size_pct=20.0,
                min_risk_reward_ratio=1.2,
                stop_loss_pct=5.0,
                take_profit_pct=12.0
            )

        logger.info(f"Risk level set to: {level.value}")

    def calculate_kelly_position_size(
        self,
        confidence: float,
        risk_reward_ratio: Optional[float] = None,
        max_kelly_fraction: float = 0.5
    ) -> float:
        """
        Calculate the optimal portfolio fraction to risk using the Kelly Criterion.
        
        f* = p - (q / b)
        
        Args:
            confidence: Win probability (0.0 to 1.0)
            risk_reward_ratio: Win size / Loss size (b in the formula). If None, uses config.min_risk_reward_ratio.
            max_kelly_fraction: Safety multiplier (often 0.5 for 'Half-Kelly')
            
        Returns:
            The percentage of the total portfolio to risk on this trade.
        """
        p = confidence
        q = 1.0 - p
        b = risk_reward_ratio if risk_reward_ratio else self.config.min_risk_reward_ratio
        
        if b <= 0:
            return 0.0
            
        kelly_fraction = p - (q / b)
        
        if kelly_fraction <= 0:
            return 0.0
            
        # Apply fractional Kelly for safety
        adjusted_kelly = kelly_fraction * max_kelly_fraction
        
        # Cap at the max risk per trade defined in the risk config (can be overridden by aggressive settings)
        # But we still enforce absolute max limits. Let's use max_position_size_pct as hard cap.
        max_risk = self.config.max_position_size_pct / 100.0
        final_risk_fraction = min(adjusted_kelly, max_risk)
        
        # If confidence is high, maybe allow up to max_position_size, but normally cap to risk_per_trade
        # Let's use max_risk as the risk_per_trade_pct normally, but since Kelly is dynamic, 
        # we can allow it to go higher up to max_position_size_pct.
        
        return final_risk_fraction * 100.0  # Return as percentage

    def calculate_position_size(
        self,
        entry_price: float,
        risk_amount: float,
        stop_loss_distance: float
    ) -> float:
        """
        Calculate optimal position size based on risk parameters

        Args:
            entry_price: Entry price of the trade
            risk_amount: Maximum risk amount (e.g., 1% of portfolio)
            stop_loss_distance: Distance to stop-loss price

        Returns:
            Number of tokens to buy
        """
        if stop_loss_distance == 0:
            return 0

        # Calculate position size based on risk
        position_size = risk_amount / stop_loss_distance

        # Check against max position size
        total_value = self._get_total_portfolio_value()
        max_position_value = total_value * (self.config.max_position_size_pct / 100)

        if position_size * entry_price > max_position_value:
            position_size = max_position_value / entry_price

        return round(position_size, 6)

    def validate_entry(
        self,
        token_address: str,
        symbol: str,
        entry_price: float,
        target_position_size: float,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        risk_reward_ratio: Optional[float] = None
    ) -> Tuple[bool, str, Dict]:
        """
        Validate a trade entry with Narrative and Correlation guards.
        """
        total_value = self._get_total_portfolio_value()
        symbol = symbol.upper()

        # 1. Basic Checks (Daily Loss, Drawdown)
        daily_pnl_pct = self._calculate_daily_pnl_pct()
        if daily_pnl_pct >= self.config.max_daily_loss_pct:
            return False, f"Daily loss limit reached ({daily_pnl_pct:.2f}% >= {self.config.max_daily_loss_pct}%)", {}

        if self.current_max_drawdown >= self.config.max_drawdown_pct:
            return False, f"Maximum drawdown limit reached ({self.current_max_drawdown:.2f}% >= {self.config.max_drawdown_pct}%)", {}

        # 2. Position Size Check
        position_value = target_position_size * entry_price
        max_position_value = total_value * (self.config.max_position_size_pct / 100)
        if position_value > max_position_value:
            return False, f"Position size too large (${position_value:,.2f} > limit ${max_position_value:,.2f})", {}

        # 3. Narrative & Correlation Guard
        narrative = self.config.narrative_map.get(symbol, "UNKNOWN")
        
        # Count positions in the same narrative
        narrative_count = 0
        narrative_value = 0.0
        for pos in self.active_positions.values():
            pos_narrative = self.config.narrative_map.get(pos.symbol, "UNKNOWN")
            if pos_narrative == narrative:
                narrative_count += 1
                narrative_value += pos.current_value

        # Check Correlation Limit (count)
        if narrative != "UNKNOWN" and narrative_count >= self.config.max_correlated_positions:
            return False, f"Correlation limit hit: Already have {narrative_count} positions in {narrative} narrative.", {}

        # Check Narrative Exposure (value)
        total_narrative_exposure = (narrative_value + position_value) / total_value * 100
        if narrative != "UNKNOWN" and total_narrative_exposure > self.config.max_narrative_exposure_pct:
            return False, f"Narrative exposure too high: {narrative} would be {total_narrative_exposure:.1f}% (Limit: {self.config.max_narrative_exposure_pct}%)", {}

        # 4. Risk-Reward Check
        sl_pct = stop_loss_pct or self.config.stop_loss_pct
        tp_pct = take_profit_pct or self.config.take_profit_pct
        stop_loss_price = entry_price * (1 - sl_pct / 100)
        stop_loss_distance = entry_price - stop_loss_price
        calculated_risk_reward = risk_reward_ratio or (tp_pct / sl_pct if sl_pct else 0.0)
        if calculated_risk_reward < self.config.min_risk_reward_ratio:
            return False, (
                f"Risk-reward ratio too low ({calculated_risk_reward:.2f} < "
                f"{self.config.min_risk_reward_ratio:.2f})"
            ), {}
        
        # Final validation
        return True, "Entry validated successfully", {
            'token_address': token_address,
            'symbol': symbol,
            'entry_price': entry_price,
            'position_size': target_position_size,
            'stop_loss_price': stop_loss_price,
            'risk_amount': stop_loss_distance * target_position_size,
            'risk_reward_ratio': calculated_risk_reward
        }

    def open_position(
        self,
        token_address: str,
        symbol: str,
        entry_price: float,
        position_size: float,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        risk_reward_ratio: Optional[float] = None,
        trailing_stop: bool = False,
        partial_tp: bool = False
    ) -> Dict:
        """
        Open a new trading position with advanced management options

        Args:
            token_address: Token to buy
            symbol: Token symbol
            entry_price: Entry price
            position_size: Number of tokens to buy
            stop_loss_pct: Stop-loss percentage
            take_profit_pct: Take-profit percentage
            risk_reward_ratio: Required risk-reward ratio
            trailing_stop: Whether to enable trailing stop-loss
            partial_tp: Whether to enable multi-stage take-profit
        """
        # Validate entry
        is_valid, message, params = self.validate_entry(
            token_address=token_address,
            symbol=symbol,
            entry_price=entry_price,
            target_position_size=position_size,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            risk_reward_ratio=risk_reward_ratio
        )

        if not is_valid:
            return {
                'success': False,
                'message': message,
                'token_address': token_address,
                'entry_price': entry_price,
                'position_size': position_size
            }

        # Calculate stop-loss and take-profit prices
        sl_pct = stop_loss_pct if stop_loss_pct is not None else self.config.stop_loss_pct
        tp_pct = take_profit_pct if take_profit_pct is not None else self.config.take_profit_pct

        stop_loss_price = entry_price * (1 - sl_pct / 100)
        take_profit_price = entry_price * (1 + tp_pct / 100)

        # Calculate risk amount
        risk_amount = position_size * (entry_price - stop_loss_price)

        # Create position
        position = Position(
            token_address=token_address,
            symbol=symbol,
            entry_price=entry_price,
            amount=position_size,
            stop_loss=stop_loss_price,
            take_profit=take_profit_price,
            risk_amount=risk_amount,
            entry_time=datetime.now()
        )
        
        # Setup trailing stop if requested
        if trailing_stop:
            # Activate trailing after 3% profit
            position.trailing_activation_price = entry_price * 1.03
            position.trailing_distance_atr = 2.0 # 2x ATR
            
        # Setup partial TPs if requested
        if partial_tp:
            # Stage 1: Sell 50% at 5% profit
            position.partial_tp_targets.append({
                'price': entry_price * 1.05,
                'fraction': 0.5,
                'hit': False
            })
            # Also move to breakeven after TP1
            position.breakeven_activation_price = entry_price * 1.05

        # Store position
        self.active_positions[token_address] = position

        # Record trade
        trade_record = {
            'token_address': token_address,
            'symbol': symbol,
            'entry_price': entry_price,
            'position_size': position_size,
            'stop_loss': stop_loss_price,
            'take_profit': take_profit_price,
            'risk_amount': risk_amount,
            'entry_time': datetime.now(),
            'status': 'open',
            'management': 'advanced' if (trailing_stop or partial_tp) else 'standard'
        }
        self.trade_history.append(trade_record)

        logger.info(f"Position opened: {symbol} ({token_address}), Size: {position_size:.6f}, "
                   f"Stop: ${stop_loss_price:.4f}, TP: ${take_profit_price:.4f}")

        return {
            'success': True,
            'message': message,
            'position': {
                'symbol': symbol,
                'token_address': token_address,
                'entry_price': entry_price,
                'position_size': position_size,
                'stop_loss': stop_loss_price,
                'take_profit': take_profit_price
            }
        }

    def check_and_manage_positions(self) -> Dict:
        """
        Enhanced management: Trailing stops, partial TPs, and breakeven logic.
        """
        results = {
            'closed_positions': [],
            'partial_sells': [],
            'updated_positions': [],
            'warnings': []
        }

        for token_address, position in list(self.active_positions.items()):
            current_price = self.market_analyzer.get_price(token_address)

            if current_price is None or current_price == 0:
                results['warnings'].append(f"Could not get price for {position.symbol}")
                continue

            # 1. Update peak price
            if current_price > position.peak_price:
                position.peak_price = current_price

            # 2. Check Breakeven Logic
            if not position.has_moved_to_breakeven and position.breakeven_activation_price:
                if current_price >= position.breakeven_activation_price:
                    old_sl = position.stop_loss
                    position.stop_loss = position.entry_price
                    position.has_moved_to_breakeven = True
                    logger.info(f"🛡️ {position.symbol} moved to BREAKEVEN (Stop-loss adjusted from ${old_sl:.4f} to ${position.entry_price:.4f})")

            # 3. Check Trailing Stop Activation
            if not position.is_trailing and position.trailing_activation_price:
                if current_price >= position.trailing_activation_price:
                    position.is_trailing = True
                    logger.info(f"📈 {position.symbol} Trailing Stop ACTIVATED at ${current_price:.4f}")

            # 4. Handle Trailing Stop Adjustment
            if position.is_trailing:
                # Calculate distance using fixed 2% if ATR not available, or implement ATR fetch
                # For this roadmap version, we'll use a dynamic 2.5% trail from peak
                trail_sl = position.peak_price * 0.975
                if trail_sl > position.stop_loss:
                    position.stop_loss = trail_sl
                    logger.debug(f"Adjusted trailing stop for {position.symbol} to ${trail_sl:.4f}")

            # 5. Check Partial Take Profits
            for target in position.partial_tp_targets:
                if not target['hit'] and current_price >= target['price']:
                    sell_amount = position.amount * target['fraction']
                    target['hit'] = True
                    # In a real system, we'd execute the sell here
                    logger.info(f"🎯 {position.symbol} Partial TP HIT! Sold {target['fraction']*100}% ({sell_amount:.6f}) at ${current_price:.4f}")
                    position.amount -= sell_amount
                    position.status = "partial"
                    results['partial_sells'].append({
                        'symbol': position.symbol,
                        'price': current_price,
                        'fraction': target['fraction']
                    })

            # 6. Check Hard Stop or TP
            if current_price <= position.stop_loss:
                reason = "trailing_stop" if position.is_trailing else "stop_loss"
                result = self._close_position(token_address, reason, current_price)
                results['closed_positions'].append(result)
            elif current_price >= position.take_profit:
                result = self._close_position(token_address, 'take_profit', current_price)
                results['closed_positions'].append(result)
            else:
                results['updated_positions'].append({
                    'symbol': position.symbol,
                    'current_price': current_price,
                    'pnl': (current_price - position.entry_price) * position.amount
                })

        return results

    def _close_position(
        self,
        token_address: str,
        reason: str,
        current_price: float
    ) -> Dict:
        """
        Close a position

        Args:
            token_address: Token address
            reason: Reason for closing (stop_loss, take_profit, etc.)
            current_price: Current price

        Returns:
            Closing result
        """
        if token_address not in self.active_positions:
            return {'success': False, 'message': 'Position not found'}

        position = self.active_positions[token_address]

        # Calculate PnL
        pnl = position.amount * (current_price - position.entry_price)
        pnl_pct = (pnl / position.amount) * 100

        # Update the matching open trade, not just the most recent trade.
        matching_trades = [
            trade for trade in reversed(self.trade_history)
            if trade.get('token_address') == token_address and trade.get('status') == 'open'
        ]
        if not matching_trades:
            return {'success': False, 'message': 'Matching open trade not found'}

        trade = matching_trades[0]
        # Close position only after we know the trade record is available.
        self.active_positions.pop(token_address)
        trade.update({
            'exit_price': current_price,
            'exit_time': datetime.now(),
            'exit_reason': reason,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'status': 'closed'
        })

        # Update tracking
        self._update_portfolio_tracking(pnl)

        logger.info(f"Position closed: {token_address}, Reason: {reason}, "
                   f"PnL: ${pnl:.2f} ({pnl_pct:.2f}%)")

        return {
            'success': True,
            'message': f"Position closed: {reason}",
            'token_address': token_address,
            'entry_price': position.entry_price,
            'exit_price': current_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': reason
        }

    def _update_portfolio_tracking(self, pnl: float):
        """Update portfolio value tracking"""
        current_value = self._get_total_portfolio_value()

        # Update max portfolio value
        if current_value > self.max_portfolio_value:
            self.max_portfolio_value = current_value

        # Calculate drawdown
        if self.initial_portfolio_value > 0:
            drawdown = (self.initial_portfolio_value - current_value) / self.initial_portfolio_value * 100
            self.current_max_drawdown = max(self.current_max_drawdown, drawdown)

        # Reset daily tracking if needed
        if (datetime.now() - self.last_daily_reset).days >= 1:
            self.daily_start_value = current_value
            self.last_daily_reset = datetime.now()

    def _calculate_daily_pnl_pct(self) -> float:
        """Calculate daily PnL percentage"""
        current_value = self._get_total_portfolio_value()
        daily_pnl = current_value - self.daily_start_value
        daily_pnl_pct = (daily_pnl / self.daily_start_value) * 100
        return daily_pnl_pct

    def get_current_metrics(self) -> RiskMetrics:
        """Get current risk metrics"""
        total_value = self._get_total_portfolio_value()

        # Calculate daily PnL
        daily_pnl = total_value - self.daily_start_value
        daily_pnl_pct = (daily_pnl / self.daily_start_value) * 100

        # Calculate max drawdown
        if self.initial_portfolio_value > 0:
            drawdown = (self.initial_portfolio_value - total_value) / self.initial_portfolio_value * 100
        else:
            drawdown = 0

        # Calculate trade statistics
        closed_trades = [t for t in self.trade_history if t['status'] == 'closed']
        total_trades = len(closed_trades)
        winning_trades = sum(1 for t in closed_trades if t['pnl'] > 0)
        losing_trades = sum(1 for t in closed_trades if t['pnl'] < 0)

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Average risk-reward
        valid_rr_trades = [t for t in closed_trades if t['risk_amount'] > 0]
        if valid_rr_trades:
            avg_risk_reward = sum(
                t['potential_profit'] / t['risk_amount']
                for t in valid_rr_trades
            ) / len(valid_rr_trades)
        else:
            avg_risk_reward = 0

        return RiskMetrics(
            total_portfolio_value=total_value,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            max_drawdown=drawdown,
            max_drawdown_pct=max(self.current_max_drawdown, drawdown),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            average_risk_reward=avg_risk_reward
        )

    def get_diversification_score(self) -> Dict:
        """Get portfolio diversification score"""
        total_value = self._get_total_portfolio_value()
        active_positions = len(self.active_positions)

        # Calculate allocation percentages
        allocations = {}
        for token_address, position in self.active_positions.items():
            position_value = position.amount * position.entry_price
            allocation_pct = (position_value / total_value * 100) if total_value > 0 else 0
            allocations[token_address] = allocation_pct

        # Check concentration
        max_allocation = max(allocations.values()) if allocations else 0

        # Diversification score (0-100)
        # Fewer positions and more balanced = higher score
        diversity_score = min(100, (active_positions / 10 * 50) + (1 - max_allocation / self.config.max_portfolio_concentration * 100 / 10))

        return {
            'active_positions': active_positions,
            'total_value': total_value,
            'allocations': allocations,
            'max_allocation': max_allocation,
            'diversification_score': round(diversity_score, 2),
            'is_diversified': max_allocation < self.config.max_portfolio_concentration
        }

    def can_open_new_position(self) -> Tuple[bool, str]:
        """Check if can open a new position"""
        # Check daily loss limit
        daily_pnl_pct = self._calculate_daily_pnl_pct()
        if daily_pnl_pct >= self.config.max_daily_loss_pct:
            return False, f"Daily loss limit reached ({daily_pnl_pct:.2f}% >= {self.config.max_daily_loss_pct}%)"

        # Check max drawdown
        if self.current_max_drawdown >= self.config.max_drawdown_pct:
            return False, f"Maximum drawdown limit reached ({self.current_max_drawdown:.2f}% >= {self.config.max_drawdown_pct}%)"

        # Check active positions limit (optional)
        max_positions = 5
        if len(self.active_positions) >= max_positions:
            return False, f"Maximum number of active positions reached ({len(self.active_positions)}/{max_positions})"

        return True, "Ready to open new position"

    def get_all_positions(self) -> List[Dict]:
        """Get all active positions"""
        return [
            {
                'token_address': pos.token_address,
                'entry_price': pos.entry_price,
                'amount': pos.amount,
                'stop_loss': pos.stop_loss,
                'take_profit': pos.take_profit,
                'entry_time': pos.entry_time,
                'position_value': pos.amount * pos.entry_price
            }
            for pos in self.active_positions.values()
        ]

    def get_trade_history(self, days: int = 30) -> List[Dict]:
        """Get trade history for last N days"""
        cutoff = datetime.now() - timedelta(days=days)
        return [
            trade for trade in self.trade_history
            if trade['entry_time'] >= cutoff
        ]

    def print_status(self):
        """Print current risk status"""
        metrics = self.get_current_metrics()
        diversification = self.get_diversification_score()

        print("\n" + "=" * 60)
        print("📊 RISK MANAGEMENT STATUS")
        print("=" * 60)
        print(f"\nPortfolio Value: ${metrics.total_portfolio_value:.2f}")
        print(f"Daily PnL: ${metrics.daily_pnl:.2f} ({metrics.daily_pnl_pct:.2f}%)")
        print(f"Max Drawdown: {metrics.max_drawdown:.2f}%")
        print(f"Max Drawdown: {metrics.max_drawdown_pct:.2f}%")
        print(f"\nTrade Statistics:")
        print(f"  Total Trades: {metrics.total_trades}")
        print(f"  Winning: {metrics.winning_trades}")
        print(f"  Losing: {metrics.losing_trades}")
        print(f"  Win Rate: {metrics.win_rate:.2f}%")
        print(f"  Avg Risk-Reward: {metrics.average_risk_reward:.2f}")
        print(f"\nActive Positions: {diversification['active_positions']}")
        print(f"Diversification Score: {diversification['diversification_score']:.2f}/100")
        print(f"Max Allocation: {diversification['max_allocation']:.2f}%")
        print(f"Is Diversified: {'✅ Yes' if diversification['is_diversified'] else '❌ No'}")
        print(f"\nRisk Config:")
        print(f"  Max Daily Loss: {self.config.max_daily_loss_pct}%")
        print(f"  Max Drawdown: {self.config.max_drawdown_pct}%")
        print(f"  Risk per Trade: {self.config.risk_per_trade_pct}%")
        print(f"  Max Position Size: {self.config.max_position_size_pct}%")
        print(f"  Min Risk-Reward: {self.config.min_risk_reward_ratio}")
        print("=" * 60 + "\n")
