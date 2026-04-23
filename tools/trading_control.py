"""
Trading control tools for Claude Code agent.

Provides tools for the AI agent to:
- Check cryptocurrency prices
- Get portfolio status
- Execute paper trades
- Analyze market data
- Check risk metrics
"""

import json
from typing import Dict, Any, Optional
from decimal import Decimal
from core.tools import register_tool
from tools.trading_data import fetch_ticker, get_supported_symbols
from tools.trust import TrustWalletAPI
from backend.paper_trading import PaperTradingEngine, create_paper_trading_account, get_paper_trading_account
from backend.portfolio_dashboard import PortfolioDashboard
from risk_management import RiskManager, RiskConfig
from execution_layer import ExecutionLayer, ExecutionStrategy, Network


def _get_live_price(symbol: str) -> float:
    """Get a live price using the same ticker path as the public price tool."""
    result = fetch_ticker(symbol)
    if result.startswith("[error]"):
        return 0.0

    try:
        data = json.loads(result)
        return float(data.get("price", 0.0))
    except Exception:
        return 0.0


@register_tool(
    name="check_price",
    description="Check the current price of a cryptocurrency. Supports BTC, ETH, SOL, and any Binance-listed symbol. Returns price, 24h change, volume, and market data.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Trading symbol (e.g., BTC, ETH, SOL, PEPE). Can include USDT suffix or will be auto-added.",
            }
        },
        "required": ["symbol"],
    },
)
def check_price(symbol: str) -> str:
    """Get current price and market data for a cryptocurrency."""
    result = fetch_ticker(symbol)
    if result.startswith("[error]"):
        return f"Error fetching price: {result}"
    return f"Price data for {symbol.upper()}:\n{result}"


@register_tool(
    name="list_trading_symbols",
    description="List available cryptocurrency symbols for trading. Returns top 100 symbols by trading volume on Binance.",
    input_schema={
        "type": "object",
        "properties": {},
    },
)
def list_trading_symbols() -> str:
    """Get list of available trading symbols."""
    result = get_supported_symbols()
    if result.startswith("[error]"):
        return f"Error fetching symbols: {result}"
    try:
        data = json.loads(result)
        symbols = data.get("top_100_by_volume", [])
        total = data.get("total_available", 0)
        return f"Top {len(symbols)} trading symbols (out of {total} available):\n" + ", ".join(symbols[:20])
    except:
        return result


@register_tool(
    name="create_paper_trading_account",
    description="Create a paper trading account for testing strategies without real money. Returns account details.",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "integer",
                "description": "User ID for the account",
            },
            "initial_balance": {
                "type": "number",
                "description": "Initial balance in USD (default: 10000)",
            }
        },
        "required": ["user_id"],
    },
)
def create_paper_trading_account_tool(user_id: int, initial_balance: float = 10000.0) -> str:
    """Create a paper trading account."""
    try:
        account = create_paper_trading_account(user_id, initial_balance)
        return (
            f"✅ Paper trading account created for user {user_id}\n"
            f"   Initial balance: ${float(account.balance):,.2f}\n"
            f"   Cash available: ${float(account.cash):,.2f}\n"
            f"   Account ready for simulated trading"
        )
    except Exception as e:
        return f"Error creating paper trading account: {type(e).__name__}: {e}"


@register_tool(
    name="get_portfolio_status",
    description="Get current portfolio status for a user. Returns total value, cash, positions, and P&L.",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "integer",
                "description": "User ID to check portfolio for",
            }
        },
        "required": ["user_id"],
    },
)
def get_portfolio_status(user_id: int) -> str:
    """Get portfolio status for a user."""
    try:
        account = get_paper_trading_account(user_id)
        if not account:
            return f"No paper trading account found for user {user_id}. Create one first with create_paper_trading_account."

        prices = {}
        for symbol in account.positions.keys():
            prices[symbol] = _get_live_price(symbol)

        total_value = account.get_total_value(prices)
        unrealized_pnl = account.get_unrealized_pnl(prices)
        realized_pnl = account.get_realized_pnl()

        positions_str = "\n".join(
            f"   • {symbol}: {float(qty):.4f} (${float(qty) * prices.get(symbol, 0):,.2f})"
            for symbol, qty in account.positions.items()
        ) if account.positions else "   No open positions"

        return (
            f"📊 Portfolio Status for User {user_id}\n"
            f"────────────────────────────────\n"
            f"Total Value: ${total_value:,.2f}\n"
            f"Cash: ${float(account.cash):,.2f}\n"
            f"Unrealized P&L: ${unrealized_pnl:,.2f}\n"
            f"Realized P&L: ${realized_pnl:,.2f}\n"
            f"\nOpen Positions:\n{positions_str}"
        )
    except Exception as e:
        return f"Error getting portfolio status: {type(e).__name__}: {e}"


@register_tool(
    name="execute_paper_trade",
    description="Execute a paper trade (simulated, no real money). Supports either action+amount or side+quantity.",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "integer",
                "description": "User ID for the paper trading account",
            },
            "symbol": {
                "type": "string",
                "description": "Trading symbol (e.g., BTC, ETH, SOL)",
            },
            "action": {
                "type": "string",
                "description": "Legacy alias for side: buy or sell",
                "enum": ["buy", "sell"],
            },
            "side": {
                "type": "string",
                "description": "Trade side: buy or sell",
                "enum": ["buy", "sell"],
            },
            "amount": {
                "type": "number",
                "description": "Amount in USD to trade",
            },
            "quantity": {
                "type": "number",
                "description": "Coin quantity to trade (e.g. 0.346 ETH)",
            },
            "strategy": {
                "type": "string",
                "description": "Trading strategy used (e.g., DCA, MOMENTUM, MANUAL)",
            },
            "entry_price": {
                "type": "number",
                "description": (
                    "Optional externally resolved USD entry price. Normal listed symbols "
                    "use live market price; this is used as a fallback when the internal "
                    "price source cannot resolve the symbol."
                ),
            },
            "stop_loss": {
                "type": "number",
                "description": "Optional stop-loss price for logging/reference",
            },
            "take_profit": {
                "type": "number",
                "description": "Optional take-profit price for logging/reference",
            },
        },
        "required": ["user_id", "symbol"],
    },
)
def execute_paper_trade(
    user_id: int,
    symbol: str,
    action: Optional[str] = None,
    side: Optional[str] = None,
    amount: Optional[float] = None,
    quantity: Optional[float] = None,
    strategy: str = "MANUAL",
    entry_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
) -> str:
    """Execute a paper trade in the simulated account."""
    try:
        account = get_paper_trading_account(user_id)
        if not account:
            return f"No paper trading account found for user {user_id}. Create one first with create_paper_trading_account."

        symbol = symbol.upper().strip()
        normalized_side = (side or action or "").lower().strip()
        if normalized_side not in {"buy", "sell"}:
            return "Invalid trade side. Use side='buy'/'sell' or action='buy'/'sell'."

        live_price = _get_live_price(symbol)
        entry_price_override = float(entry_price) if entry_price is not None else 0.0
        price = live_price or entry_price_override

        if price <= 0:
            return f"Cannot get current price for {symbol}. Trade aborted."

        if quantity is not None and quantity > 0:
            trade_quantity = round(float(quantity), 8)
            trade_amount = float(trade_quantity * price)
        elif amount is not None and amount > 0:
            trade_amount = float(amount)
            trade_quantity = round(float(trade_amount / price), 8)
        else:
            return "Provide either quantity or amount for the paper trade."

        if normalized_side == "buy":
            if account.cash < Decimal(str(trade_amount)):
                return f"Insufficient cash. Have ${float(account.cash):,.2f}, need ${trade_amount:,.2f}"

            # Execute buy
            success = account.open_position(symbol, trade_quantity, price, strategy=strategy)
            if success:
                trade = account.paper_trades[-1]
                trade["planned_entry_price"] = entry_price
                trade["stop_loss"] = stop_loss
                trade["take_profit"] = take_profit
                return (
                    f"✅ Paper BUY Executed\n"
                    f"   Symbol: {symbol}\n"
                    f"   Quantity: {trade_quantity:.6f}\n"
                    f"   Price: ${price:,.2f}\n"
                    f"   Total: ${trade_amount:,.2f}\n"
                    f"   Strategy: {strategy}\n"
                    f"   Remaining cash: ${float(account.cash):,.2f}"
                )
            else:
                return "Buy order failed (check risk limits or account status)"

        current_qty = account.positions.get(symbol, Decimal("0"))
        trade_quantity = round(trade_quantity, 8)
        if current_qty < Decimal(str(trade_quantity)):
            return f"Insufficient {symbol} position. Have {float(current_qty):.6f}, want to sell {trade_quantity:.6f}"

        # Execute sell
        success = account.close_position(symbol, trade_quantity, price)
        if success:
            trade = account.last_close_summary or {}
            trade["planned_entry_price"] = entry_price
            trade["stop_loss"] = stop_loss
            trade["take_profit"] = take_profit
            return (
                f"✅ Paper SELL Executed\n"
                f"   Symbol: {symbol}\n"
                f"   Quantity: {trade_quantity:.6f}\n"
                f"   Price: ${price:,.2f}\n"
                f"   P&L: ${float(trade.get('pnl', 0.0)):,.2f}\n"
                f"   Cash after: ${float(account.cash):,.2f}"
            )
        return "Sell order failed"

    except Exception as e:
        return f"Error executing paper trade: {type(e).__name__}: {e}"


@register_tool(
    name="check_risk_limits",
    description="Check risk management limits for a paper trading account. Returns position limits, daily loss, drawdown status.",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "integer",
                "description": "User ID to check risk for",
            }
        },
        "required": ["user_id"],
    },
)
def check_risk_limits(user_id: int) -> str:
    """Check risk management status for an account."""
    try:
        account = get_paper_trading_account(user_id)
        if not account:
            return f"No paper trading account found for user {user_id}"

        # Initialize risk manager with default config
        risk_config = RiskConfig()

        # Calculate metrics
        prices = {}
        for symbol in account.positions.keys():
            prices[symbol] = _get_live_price(symbol)

        total_value = account.get_total_value(prices)

        # Check position concentration
        concentration_warnings = []
        for symbol, qty in account.positions.items():
            position_value = float(qty) * prices.get(symbol, 0)
            pct = (position_value / total_value * 100) if total_value > 0 else 0
            if pct > risk_config.max_position_size_pct:
                concentration_warnings.append(f"{symbol}: {pct:.1f}% (limit: {risk_config.max_position_size_pct}%)")

        return (
            f"🛡️ Risk Management Status for User {user_id}\n"
            f"────────────────────────────────\n"
            f"Portfolio Value: ${total_value:,.2f}\n"
            f"Max Position Size: {risk_config.max_position_size_pct}% per asset\n"
            f"Max Daily Loss: {risk_config.max_daily_loss_pct}%\n"
            f"Max Drawdown: {risk_config.max_drawdown_pct}%\n"
            f"Min Risk/Reward: {risk_config.min_risk_reward_ratio}:1\n"
            f"\nConcentration Warnings:\n" +
            ("\n".join(f"   ⚠️ {w}" for w in concentration_warnings) if concentration_warnings else "   ✅ All positions within limits")
        )
    except Exception as e:
        return f"Error checking risk limits: {type(e).__name__}: {e}"


@register_tool(
    name="analyze_market_trend",
    description="Analyze market trend for a cryptocurrency using technical indicators. Returns trend analysis and signals.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Trading symbol (e.g., BTC, ETH, SOL)",
            },
            "period": {
                "type": "integer",
                "description": "Analysis period in hours (default: 24)",
            }
        },
        "required": ["symbol"],
    },
)
def analyze_market_trend(symbol: str, period: int = 24) -> str:
    """Analyze market trend with technical indicators."""
    try:
        from tools.trading_data import calculate_bollinger_bands_from_data, fetch_historical

        # Fetch historical data ONCE (use max required limit)
        fetch_limit = max(period, 70) # Bollinger needs ~70 for period 20
        candles_result = fetch_historical(symbol, interval="1h", limit=fetch_limit)
        
        if candles_result.startswith("[error]"):
            return f"Error analyzing {symbol}: {candles_result}"

        candles = json.loads(candles_result)
        
        # 1. Get Bollinger Bands using shared data
        try:
            bb_data = calculate_bollinger_bands_from_data(symbol, candles)
        except Exception as e:
            return f"Error calculating Bollinger Bands for {symbol}: {e}"

        # 2. Calculate trend from same data
        if len(candles) >= 2:
            # Use requested period for trend calculation (slice from end)
            trend_candles = candles[-period:]
            first_close = trend_candles[0]["close"]
            last_close = trend_candles[-1]["close"]
            change_pct = ((last_close - first_close) / first_close) * 100

            trend = "📈 UP" if change_pct > 5 else "📉 DOWN" if change_pct < -5 else "➡️ SIDEWAYS"

            # Get volume analysis
            avg_volume = sum(c["volume"] for c in trend_candles) / len(trend_candles)
            latest_volume = trend_candles[-1]["volume"]
            volume_signal = "High" if latest_volume > avg_volume * 1.5 else "Low" if latest_volume < avg_volume * 0.5 else "Normal"

            return (
                f"📊 Market Analysis for {symbol.upper()}\n"
                f"────────────────────────────────\n"
                f"Trend: {trend} ({change_pct:+.2f}% over {len(trend_candles)}h)\n"
                f"Current Price: ${bb_data['current_price']:,.2f}\n"
                f"Bollinger Status: {bb_data['status'].upper()}\n"
                f"Upper Band: ${bb_data['upper_band']:,.2f}\n"
                f"Lower Band: ${bb_data['lower_band']:,.2f}\n"
                f"Volume Signal: {volume_signal} (avg: {avg_volume:,.0f})\n"
                f"\nSignals:\n" +
                ("   🟢 Potential BUY - Price below lower band\n" if bb_data['status'] == 'below' else "") +
                ("   🔴 Potential SELL - Price above upper band\n" if bb_data['status'] == 'above' else "") +
                ("   ⚠️ High volatility expected\n" if bb_data['status'] != 'within' else "   ✅ Price within normal range")
            )
        else:
            return f"Insufficient data for {symbol} trend analysis"

    except Exception as e:
        return f"Error analyzing market: {type(e).__name__}: {e}"


@register_tool(
    name="get_trade_history",
    description="Get paper trade history for a user. Returns list of executed trades with P&L.",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "integer",
                "description": "User ID to get history for",
            },
            "limit": {
                "type": "integer",
                "description": "Number of trades to return (default: 10)",
            }
        },
        "required": ["user_id"],
    },
)
def get_trade_history(user_id: int, limit: int = 10) -> str:
    """Get trade history for a paper trading account."""
    try:
        account = get_paper_trading_account(user_id)
        if not account:
            return f"No paper trading account found for user {user_id}"

        if not account.paper_trades:
            return f"No trade history for user {user_id}"

        # Get recent trades
        recent_trades = account.paper_trades[-limit:]

        trade_list = []
        for i, trade in enumerate(reversed(recent_trades), 1):
            action = trade.get("action", "unknown")
            symbol = trade.get("symbol", "unknown")
            qty = trade.get("quantity", 0)
            price = trade.get("entry_price", trade.get("exit_price", 0))
            pnl = trade.get("pnl", 0)
            status = trade.get("status", "unknown")

            pnl_str = f" (${pnl:+.2f})" if pnl != 0 else ""
            trade_list.append(
                f"{i}. [{status}] {action.upper()} {symbol}: {qty:.6f} @ ${price:,.2f}{pnl_str}"
            )

        total_trades = len(account.paper_trades)
        completed_trades = [t for t in account.paper_trades if t.get("status") == "closed"]
        winning_trades = sum(1 for t in completed_trades if t.get("pnl", 0) > 0)

        return (
            f"📜 Trade History for User {user_id}\n"
            f"────────────────────────────────\n"
            f"Total trades: {total_trades}\n"
            f"Completed trades: {len(completed_trades)}\n"
            f"Winning trades: {winning_trades} ({(winning_trades/len(completed_trades)*100 if completed_trades else 0):.1f}%)\n"
            f"\nRecent {min(limit, total_trades)} trades:\n" +
            "\n".join(trade_list)
        )
    except Exception as e:
        return f"Error getting trade history: {type(e).__name__}: {e}"

@register_tool(
    name="calculate_kelly_risk",
    description="Calculate the optimal portfolio fraction to risk on a trade using the Kelly Criterion based on your confidence score.",
    input_schema={
        "type": "object",
        "properties": {
            "confidence": {
                "type": "number",
                "description": "Win probability of the trade (from 0.0 to 1.0, e.g. 0.8 for 80% confident)."
            },
            "risk_reward_ratio": {
                "type": "number",
                "description": "The ratio of expected profit to expected loss (e.g., 2.0). If omitted, defaults to 1.5."
            }
        },
        "required": ["confidence"],
    },
)
def calculate_kelly_risk(confidence: float, risk_reward_ratio: float = 1.5) -> str:
    """Calculate position size using the Kelly Criterion."""
    from risk_management import RiskManager, RiskConfig
    try:
        # We can just create a temporary risk manager to do the math
        risk_manager = RiskManager(trust_wallet=None, market_analyzer=None)
        
        # Override default to show math
        kelly_pct = risk_manager.calculate_kelly_position_size(
            confidence=confidence,
            risk_reward_ratio=risk_reward_ratio,
            max_kelly_fraction=0.5 # Half Kelly
        )
        
        full_kelly_pct = risk_manager.calculate_kelly_position_size(
            confidence=confidence,
            risk_reward_ratio=risk_reward_ratio,
            max_kelly_fraction=1.0 # Full Kelly
        )
        
        return (
            f"Kelly Criterion Position Sizer:\n"
            f"- Confidence: {confidence*100:.1f}%\n"
            f"- Risk/Reward Ratio: {risk_reward_ratio}\n"
            f"- Full Kelly Suggestion: Risk {full_kelly_pct:.2f}% of portfolio\n"
            f"- Half Kelly Suggestion (Recommended): Risk {kelly_pct:.2f}% of portfolio\n\n"
            f"Result: You should risk {kelly_pct:.2f}% of your current balance on this trade to mathematically maximize long-term growth."
        )
    except Exception as e:
        return f"Error calculating Kelly criterion: {e}"


@register_tool(
    name="resume_trading",
    description="Resume trading activity after a manual or automatic halt (e.g. after a circuit breaker was triggered).",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "integer",
                "description": "The user ID of the paper account.",
            }
        },
        "required": ["user_id"],
    },
)
def resume_trading_tool(user_id: int) -> str:
    """Resume trading for a user."""
    account = get_paper_trading_account(user_id)
    if not account:
        return f"No paper trading account found for user {user_id}."
    account.resume_trading()
    return f"Trading has been resumed for user {user_id}."


@register_tool(
    name="halt_trading",
    description="Manually halt all trading activity and liquidate open positions for safety.",
    input_schema={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "integer",
                "description": "The user ID of the paper account.",
            },
            "reason": {
                "type": "string",
                "description": "The reason for the manual halt.",
            }
        },
        "required": ["user_id", "reason"],
    },
)
def halt_trading_tool(user_id: int, reason: str) -> str:
    """Halt trading for a user."""
    account = get_paper_trading_account(user_id)
    if not account:
        return f"No paper trading account found for user {user_id}."
    account.halt_trading(reason)
    return f"Trading has been halted for user {user_id}. Reason: {reason}. All positions liquidated."
