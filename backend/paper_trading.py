"""
Paper Trading Simulation Module

This module provides paper trading functionality for testing trading strategies
without real money or risk.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, getcontext
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from backend.database import SessionLocal, Trade, User

getcontext().prec = 8  # High precision for financial calculations


class TradeType(Enum):
    """Trade type enum for paper trading."""
    BUY = "buy"
    SELL = "sell"


class PaperTradingAccount:
    """Paper trading account for testing strategies."""

    def __init__(self, user_id: int, initial_balance: float = 10000.00):
        """
        Initialize a paper trading account.

        Args:
            user_id: User ID associated with the account
            initial_balance: Initial paper trading balance (default: $10,000)
        """
        self.user_id = user_id
        self.balance = Decimal(str(initial_balance))
        self.cash = self.balance
        self.positions: Dict[str, Decimal] = {}  # symbol -> quantity
        self.trades: List[Dict] = []
        self.paper_trades: List[Dict] = []  # Stores paper trades for history
        self.last_close_summary: Optional[Dict[str, Any]] = None
        self.is_halted = False
        self.halt_reason = ""

    def halt_trading(self, reason: str):
        """Halt all trading activities."""
        self.is_halted = True
        self.halt_reason = reason
        print(f"TRADING HALTED: {reason}")
        self.close_all_positions(notes=f"Emergency liquidation: {reason}")

    def resume_trading(self):
        """Resume trading activities."""
        self.is_halted = False
        self.halt_reason = ""
        print("TRADING RESUMED")

    def close_all_positions(self, notes: str = "Closing all positions"):
        """Liquidate all open positions."""
        symbols = list(self.positions.keys())
        # We'd need live prices to do this properly, 
        # but for paper trading we can use the last known price or a mock.
        # This method is primarily used during halts.
        for symbol in symbols:
            qty = float(self.positions[symbol])
            # For simplicity in this logic, we assume we can close at the last entry price 
            # if we don't have a lookup, but in practice the caller should provide prices.
            entry_price = float(self._get_entry_price(symbol) or Decimal("0"))
            self.close_position(symbol, qty, entry_price, notes=notes)

    def get_total_value(self, current_prices: Dict[str, float]) -> float:
        """
        Get total portfolio value including cash and positions.

        Args:
            current_prices: Dictionary of current prices for symbols

        Returns:
            Total portfolio value
        """
        positions_value = Decimal("0.00")
        for symbol, quantity in self.positions.items():
            price = current_prices.get(symbol, 0.0)
            positions_value += quantity * Decimal(str(price))

        return float(self.cash + positions_value)

    def get_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate unrealized profit/loss for all open positions.

        Args:
            current_prices: Dictionary of current prices for symbols

        Returns:
            Unrealized PnL
        """
        unrealized_pnl = Decimal("0.00")
        for symbol, quantity in self.positions.items():
            price = current_prices.get(symbol, 0.0)
            entry_price = self._get_entry_price(symbol)
            if entry_price and price:
                pnl = (Decimal(str(price)) - entry_price) * quantity
                unrealized_pnl += pnl

        return float(unrealized_pnl)

    def get_realized_pnl(self) -> float:
        """
        Calculate total realized profit/loss from closed trades.

        Returns:
            Realized PnL
        """
        total_pnl = sum(trade.get('pnl', 0.0) for trade in self.paper_trades)
        return total_pnl

    def get_portfolio_allocation(self, current_prices: Dict[str, float]) -> Dict[str, float]:
        """
        Get portfolio allocation by asset.

        Args:
            current_prices: Dictionary of current prices for symbols

        Returns:
            Dictionary of symbol -> allocation percentage
        """
        total_value = self.get_total_value(current_prices)

        if total_value == 0:
            return {}

        allocation = {}
        for symbol, quantity in self.positions.items():
            price = current_prices.get(symbol, 0.0)
            position_value = quantity * price
            allocation[symbol] = (position_value / total_value) * 100

        return allocation

    def open_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        strategy: str = None
    ) -> bool:
        """
        Open a new position in paper trading.

        Args:
            symbol: Trading symbol (e.g., "BTC")
            quantity: Quantity to buy/sell
            price: Entry price
            strategy: Strategy name used for this trade

        Returns:
            True if successful, False otherwise
        """
        if self.is_halted:
            print(f"Cannot open position for {symbol}: Trading is halted ({self.halt_reason})")
            return False
            
        try:
            total_cost = Decimal(str(quantity * price))

            if total_cost > self.cash:
                print(f"Error: Insufficient cash. Required: ${total_cost:.2f}, Available: ${self.cash:.2f}")
                return False

            # Record trade
            trade = {
                'id': len(self.paper_trades) + 1,
                'agent_id': self.user_id,
                'user_id': self.user_id,
                'symbol': symbol,
                'action': TradeType.BUY.value,
                'strategy': strategy,
                'entry_price': price,
                'exit_price': None,
                'quantity': quantity,
                'remaining_quantity': quantity,
                'entry_date': datetime.now(timezone.utc).isoformat(),
                'exit_date': None,
                'pnl': 0.0,
                'status': 'open',
                'realized_pnl': 0.0,
                'entry_fee': 0.0,
                'exit_fee': 0.0,
                'notes': 'Paper trading',
                'type': 'paper'
            }

            self.paper_trades.append(trade)

            # Update balance and positions
            self.cash -= total_cost
            self.positions[symbol] = self.positions.get(symbol, Decimal("0")) + Decimal(str(quantity))

            print(f"Opened {symbol} position: {quantity} @ ${price:.2f}")
            return True

        except Exception as e:
            print(f"Error opening position: {e}")
            return False

    def close_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        notes: str = None
    ) -> bool:
        """
        Close a position in paper trading.

        Args:
            symbol: Trading symbol
            quantity: Quantity to sell
            price: Exit price
            notes: Notes about the trade

        Returns:
            True if successful, False otherwise
        """
        try:
            if symbol not in self.positions:
                print(f"Error: No position in {symbol}")
                return False

            quantity_dec = Decimal(str(quantity))
            current_quantity = self.positions[symbol]
            
            # Use a small epsilon for float comparison safety
            if quantity_dec > current_quantity + Decimal("0.00000001"):
                print(f"Error: Quantity to close exceeds position. Available: {current_quantity}, Requested: {quantity_dec}")
                return False

            open_lots = self._get_open_trade_lots(symbol)
            if not open_lots:
                print(f"Error: No open trade lots for {symbol}")
                return False

            remaining_to_close = quantity_dec
            total_pnl = Decimal("0.00")
            total_entry_notional = Decimal("0.00")
            closed_lots: List[Dict[str, Any]] = []
            now_iso = datetime.now(timezone.utc).isoformat()

            # FIFO close across lots so partial exits update the correct trade records.
            for trade in open_lots:
                if remaining_to_close <= Decimal("0"):
                    break

                trade_remaining = Decimal(str(trade.get("remaining_quantity", trade["quantity"])))
                if trade_remaining <= Decimal("0"):
                    continue

                close_qty = min(trade_remaining, remaining_to_close)
                entry_price = Decimal(str(trade["entry_price"]))
                lot_pnl = (Decimal(str(price)) - entry_price) * close_qty
                total_pnl += lot_pnl
                total_entry_notional += entry_price * close_qty

                trade["remaining_quantity"] = float(trade_remaining - close_qty)
                trade["realized_pnl"] = float(Decimal(str(trade.get("realized_pnl", 0.0))) + lot_pnl)
                trade["pnl"] = trade["realized_pnl"]
                trade["exit_price"] = price
                trade["exit_date"] = now_iso
                trade["notes"] = notes or f"PnL: ${Decimal(str(trade['realized_pnl'])):.2f}"

                if Decimal(str(trade["remaining_quantity"])) <= Decimal("0.00000001"):
                    trade["remaining_quantity"] = 0.0
                    trade["status"] = "closed"
                else:
                    trade["status"] = "partial"

                closed_lots.append(
                    {
                        "trade_id": trade["id"],
                        "symbol": symbol,
                        "closed_quantity": float(close_qty),
                        "entry_price": float(entry_price),
                        "exit_price": float(price),
                        "pnl": float(lot_pnl),
                        "status": trade["status"],
                        "strategy": trade.get("strategy"),
                    }
                )

                remaining_to_close -= close_qty

            # Update balance
            total_sale = Decimal(str(quantity * price))
            self.cash += total_sale
            self.cash -= Decimal("0.001")  # Simulate trading fee

            # Update position
            self.positions[symbol] -= quantity_dec
            if self.positions[symbol] <= Decimal("0.00000001"):
                del self.positions[symbol]

            avg_entry_price = float(total_entry_notional / quantity_dec) if quantity_dec > 0 else 0.0
            summary_trade = {
                'id': closed_lots[-1]['trade_id'] if closed_lots else None,
                'agent_id': self.user_id,
                'user_id': self.user_id,
                'symbol': symbol,
                'action': TradeType.SELL.value,
                'strategy': closed_lots[0].get('strategy') if closed_lots else None,
                'entry_price': avg_entry_price,
                'exit_price': price,
                'quantity': float(quantity_dec),
                'entry_date': open_lots[0]['entry_date'] if open_lots else now_iso,
                'exit_date': now_iso,
                'pnl': float(total_pnl),
                'status': 'closed' if not any(float(t.get('remaining_quantity', 0.0)) > 0 for t in open_lots) else 'partial',
                'entry_fee': 0.0,
                'exit_fee': 0.0,
                'notes': notes or f"PnL: ${total_pnl:.2f}",
                'type': 'paper',
                'closed_lots': closed_lots,
            }
            self.last_close_summary = summary_trade

            print(f"Closed {symbol} position: {quantity} @ ${price:.2f}, PnL: ${total_pnl:.2f}")
            
            # Trigger Post-Mortem AI reflection
            from tools.reflection import trigger_post_mortem
            trigger_post_mortem(summary_trade)
            
            return True

        except Exception as e:
            print(f"Error closing position: {e}")
            return False

    def _get_open_trade_lots(self, symbol: str) -> List[Dict[str, Any]]:
        """Return open/partial buy trades for a symbol in FIFO order."""
        lots: List[Dict[str, Any]] = []
        for trade in self.paper_trades:
            if trade['symbol'] != symbol or trade['action'] != TradeType.BUY.value:
                continue
            if trade.get('status') not in {'open', 'partial'}:
                continue
            remaining_quantity = Decimal(str(trade.get('remaining_quantity', trade.get('quantity', 0.0))))
            if remaining_quantity > Decimal("0"):
                lots.append(trade)
        return lots

    def _get_entry_price(self, symbol: str) -> Optional[Decimal]:
        """
        Get entry price for a symbol from open trades.

        Args:
            symbol: Trading symbol

        Returns:
            Entry price or None
        """
        lots = self._get_open_trade_lots(symbol)
        if not lots:
            return None

        total_qty = Decimal("0.00")
        total_cost = Decimal("0.00")
        for trade in lots:
            qty = Decimal(str(trade.get('remaining_quantity', trade.get('quantity', 0.0))))
            entry_price = Decimal(str(trade['entry_price']))
            total_qty += qty
            total_cost += qty * entry_price

        if total_qty <= Decimal("0"):
            return None

        return total_cost / total_qty

    def get_open_positions(self) -> List[Dict]:
        """
        Get list of open positions.

        Returns:
            List of open position dictionaries
        """
        positions = []
        for symbol, quantity in self.positions.items():
            entry_price = self._get_entry_price(symbol)
            if entry_price:
                positions.append({
                    'symbol': symbol,
                    'quantity': float(quantity),
                    'entry_price': float(entry_price),
                    'current_price': None,  # Would need current prices
                    'unrealized_pnl': 0.0
                })
        return positions

    def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """
        Get trade history.

        Args:
            limit: Maximum number of trades to return

        Returns:
            List of trade dictionaries
        """
        return self.paper_trades[-limit:] if limit else self.paper_trades

    def get_statistics(self, current_prices: Dict[str, float]) -> Dict[str, float]:
        """
        Get paper trading statistics.

        Args:
            current_prices: Dictionary of current prices for symbols

        Returns:
            Dictionary of statistics
        """
        total_value = self.get_total_value(current_prices)
        unrealized_pnl = self.get_unrealized_pnl(current_prices)
        realized_pnl = self.get_realized_pnl()
        total_pnl = unrealized_pnl + realized_pnl
        return {
            'total_value': total_value,
            'cash': float(self.cash),
            'positions_value': total_value - float(self.cash),
            'unrealized_pnl': unrealized_pnl,
            'realized_pnl': realized_pnl,
            'total_pnl': total_pnl,
            'win_rate': self._calculate_win_rate(),
            'total_trades': len(self.paper_trades),
            'closed_trades': sum(1 for t in self.paper_trades if t['status'] == 'closed'),
            'partial_trades': sum(1 for t in self.paper_trades if t['status'] == 'partial')
        }

    def _calculate_win_rate(self) -> float:
        """Calculate win rate from completed paper trades."""
        closed_trades = [t for t in self.paper_trades if t.get("status") == "closed"]
        if not closed_trades:
            closed_trades = list(self.paper_trades)

        if not closed_trades:
            return 0.0

        winning_trades = sum(1 for trade in closed_trades if float(trade.get("pnl", 0.0)) > 0)
        return (winning_trades / len(closed_trades)) * 100

    def buy_order(self, symbol: str, quantity: Optional[float] = None, price: float = 0.0, amount_usd: Optional[float] = None, strategy: str = "MANUAL") -> dict:
        """Helper to place a buy order."""
        if amount_usd and price > 0:
            quantity = amount_usd / price
        
        if not quantity or quantity <= 0:
            return {"success": False, "error": "Invalid quantity"}
            
        success = self.open_position(symbol, quantity, price, strategy)
        if success:
            return {
                "success": True, 
                "order_id": len(self.paper_trades),
                "symbol": symbol,
                "action": "buy",
                "quantity": float(quantity),
                "entry_price": float(price),
                "total": float(quantity * price),
                "status": "open"
            }
        return {"success": False, "error": "Insufficient funds or other error"}

    def sell_order(self, symbol: str, quantity: float, price: float) -> dict:
        """Helper to place a sell order."""
        if not quantity or quantity <= 0:
            return {"success": False, "error": "Invalid quantity"}
            
        success = self.close_position(symbol, quantity, price)
        if success:
            trade = self.last_close_summary or {}
            return {
                "success": True,
                "order_id": trade.get("id"),
                "symbol": symbol,
                "action": "sell",
                "quantity": float(quantity),
                "entry_price": float(trade.get("entry_price", 0)),
                "exit_price": float(price),
                "total": float(quantity * price),
                "pnl": float(trade.get("pnl", 0)),
                "status": trade.get("status", "closed"),
                "closed_lots": trade.get("closed_lots", [])
            }
        return {"success": False, "error": "No position or insufficient quantity"}

    def reset(self):
        """Reset paper trading account to initial state."""
        self.cash = self.balance
        self.positions = {}
        self.trades = []
        self.paper_trades = []
        print("Paper trading account reset")

    def save_to_database(self):
        """Save paper trades to the database."""
        session = SessionLocal()

        try:
            # Get existing trade IDs for this user to avoid duplicates
            existing_trade_ids = {t.id for t in session.query(Trade.id).filter(Trade.user_id == self.user_id).all()}

            for trade_data in self.paper_trades:
                # Use the 'id' from paper_trades as a reference if possible, 
                # but since it's just an index, we might need a better way.
                # For now, let's assume we want to sync all.
                
                # Check if this trade (by its index-based ID) already exists
                # This is a bit weak but works for this simulation
                
                # Actually, let's just clear and re-insert or update
                # Simpler: find by user_id, symbol, quantity, entry_date
                
                entry_date = datetime.fromisoformat(trade_data['entry_date'])
                
                existing_trade = session.query(Trade).filter(
                    Trade.user_id == self.user_id,
                    Trade.symbol == trade_data['symbol'],
                    Trade.quantity == Decimal(str(trade_data['quantity'])),
                    Trade.entry_date == entry_date
                ).first()

                if existing_trade:
                    # Update status and exit info
                    existing_trade.status = trade_data['status']
                    if trade_data['exit_date']:
                        existing_trade.exit_date = datetime.fromisoformat(trade_data['exit_date'])
                    if trade_data['exit_price']:
                        existing_trade.exit_price = Decimal(str(trade_data['exit_price']))
                    existing_trade.pnl = Decimal(str(trade_data['pnl']))
                    existing_trade.notes = trade_data.get('notes')
                else:
                    # Create new
                    new_trade = Trade(
                        user_id=trade_data['user_id'],
                        portfolio_id=1,  # Default portfolio
                        agent_id=trade_data.get('agent_id', self.user_id),
                        symbol=trade_data['symbol'],
                        action=trade_data['action'],
                        trade_type=trade_data['action'],
                        strategy=trade_data.get('strategy'),
                        entry_price=Decimal(str(trade_data['entry_price'])),
                        exit_price=Decimal(str(trade_data['exit_price'])) if trade_data['exit_price'] else None,
                        quantity=Decimal(str(trade_data['quantity'])),
                        entry_date=entry_date,
                        exit_date=datetime.fromisoformat(trade_data['exit_date']) if trade_data['exit_date'] else None,
                        pnl=Decimal(str(trade_data['pnl'])),
                        status=trade_data['status'],
                        entry_fee=Decimal(str(trade_data.get('entry_fee', 0.0))),
                        exit_fee=Decimal(str(trade_data.get('exit_fee', 0.0))),
                        notes=trade_data.get('notes')
                    )
                    session.add(new_trade)

            session.commit()
            print(f"Paper trades for user {self.user_id} saved/updated in database")

        except Exception as e:
            session.rollback()
            print(f"Error saving trades to database: {e}")
            import traceback
            traceback.print_exc()
        finally:
            session.close()


class PaperTradingEngine:
    """Main paper trading engine for managing multiple accounts."""

    def __init__(self):
        """Initialize the paper trading engine."""
        self.accounts: Dict[int, PaperTradingAccount] = {}
        self.initial_balances: Dict[int, float] = {}

    def create_account(self, user_id: int, initial_balance: float = 10000.00) -> PaperTradingAccount:
        """
        Create a new paper trading account.

        Args:
            user_id: User ID
            initial_balance: Initial balance

        Returns:
            PaperTradingAccount instance
        """
        if user_id not in self.accounts:
            account = PaperTradingAccount(user_id, initial_balance)
            self.accounts[user_id] = account
            self.initial_balances[user_id] = initial_balance
            print(f"Created paper trading account for user {user_id} with ${initial_balance}")
        return self.accounts[user_id]

    def get_account(self, user_id: int) -> Optional[PaperTradingAccount]:
        """
        Get a paper trading account.

        Args:
            user_id: User ID

        Returns:
            PaperTradingAccount or None
        """
        return self.accounts.get(user_id)

    def get_all_accounts(self) -> Dict[int, PaperTradingAccount]:
        """Get all paper trading accounts."""
        return self.accounts

    def get_statistics(self, user_id: int, current_prices: Dict[str, float]) -> Optional[Dict]:
        """
        Get statistics for a user's paper trading account.

        Args:
            user_id: User ID
            current_prices: Current prices

        Returns:
            Statistics dictionary or None
        """
        account = self.get_account(user_id)
        if account:
            return account.get_statistics(current_prices)
        return None

    def reset_all_accounts(self):
        """Reset all paper trading accounts."""
        for account in self.accounts.values():
            account.reset()
        print("All paper trading accounts reset")


# Global paper trading engine instance
paper_trading_engine = PaperTradingEngine()


def create_paper_trading_account(user_id: int, initial_balance: float = 10000.00) -> PaperTradingAccount:
    """
    Factory function to create a paper trading account.

    Args:
        user_id: User ID
        initial_balance: Initial balance

    Returns:
        PaperTradingAccount instance
    """
    return paper_trading_engine.create_account(user_id, initial_balance)


def get_paper_trading_account(user_id: int) -> Optional[PaperTradingAccount]:
    """
    Factory function to get a paper trading account.

    Args:
        user_id: User ID

    Returns:
        PaperTradingAccount or None
    """
    return paper_trading_engine.get_account(user_id)
