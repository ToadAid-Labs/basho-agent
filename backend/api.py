"""
Flask API Module

This module provides REST API endpoints for paper trading and portfolio tracking.
"""

from flask import Blueprint, jsonify, request
from typing import Dict, Optional
from decimal import Decimal
import os
import json
import asyncio
import logging
import traceback

# Add the backend directory to the path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.paper_trading import PaperTradingEngine, PaperTradingAccount, create_paper_trading_account, get_paper_trading_account
from backend.portfolio_dashboard import PortfolioDashboard
from backend.market_data import init_market_data, market_aggregator, get_current_prices, TRADING_SYMBOLS, ensure_market_data_initialized

logger = logging.getLogger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


# Configuration
PAPER_TRADING_INITIAL_BALANCE = Decimal(os.getenv('PAPER_TRADING_INITIAL_BALANCE', '10000'))


@api_bp.route('/paper-trading/create', methods=['POST'])
def create_paper_trading_account_api():
    """
    Create a new paper trading account.

    Request body:
    {
        "user_id": 123,
        "initial_balance": 10000.00
    }

    Response:
    {
        "success": true,
        "account": {...}
    }
    """
    try:
        data = request.get_json()

        if not data or 'user_id' not in data:
            return jsonify({'error': 'Missing user_id'}), 400

        user_id = data['user_id']
        initial_balance = data.get('initial_balance', float(PAPER_TRADING_INITIAL_BALANCE))

        account = create_paper_trading_account(user_id, initial_balance)

        return jsonify({
            'success': True,
            'account': {
                'user_id': account.user_id,
                'balance': float(account.balance),
                'cash': float(account.cash),
                'positions': {k: float(v) for k, v in account.positions.items()}
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/paper-trading/account/<int:user_id>', methods=['GET'])
def get_paper_trading_account_api(user_id: int):
    """
    Get paper trading account details.

    Response:
    {
        "success": true,
        "account": {...}
    }
    """
    try:
        account = get_paper_trading_account(user_id)

        if not account:
            return jsonify({'error': 'Account not found'}), 404

        # Get current prices from market data
        current_prices = get_current_prices()

        return jsonify({
            'success': True,
            'account': {
                'user_id': account.user_id,
                'balance': float(account.balance),
                'cash': float(account.cash),
                'positions': {k: float(v) for k, v in account.positions.items()},
                'total_value': account.get_total_value(current_prices),
                'unrealized_pnl': account.get_unrealized_pnl(current_prices),
                'realized_pnl': account.get_realized_pnl()
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/paper-trading/open-position', methods=['POST'])
def open_position_api():
    """
    Open a new paper trading position.

    Request body:
    {
        "user_id": 123,
        "symbol": "BTC",
        "quantity": 0.1,
        "price": 45000.00,
        "strategy": "momentum"
    }

    Response:
    {
        "success": true,
        "trade": {...}
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Missing request data'}), 400

        required_fields = ['user_id', 'symbol', 'quantity', 'price']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing {field}'}), 400

        user_id = data['user_id']
        symbol = data['symbol'].upper()
        quantity = Decimal(str(data['quantity']))
        price = Decimal(str(data['price']))
        strategy = data.get('strategy')

        account = get_paper_trading_account(user_id)

        if not account:
            account = create_paper_trading_account(user_id)

        success = account.open_position(symbol, float(quantity), float(price), strategy)

        if success:
            # Save to database
            account.save_to_database()
            
            # Get current prices for response
            try:
                current_prices = get_current_prices()
                return jsonify({
                    'success': True,
                    'account': {
                        'user_id': account.user_id,
                        'balance': float(account.balance),
                        'cash': float(account.cash),
                        'positions': {k: float(v) for k, v in account.positions.items()},
                        'total_value': account.get_total_value(current_prices),
                        'unrealized_pnl': account.get_unrealized_pnl(current_prices)
                    }
                }), 200
            except Exception as inner_e:
                print(f"Error getting prices in open_position_api: {inner_e}")
                traceback.print_exc()
                return jsonify({
                    'success': True,
                    'message': 'Position opened but failed to fetch current prices',
                    'account': {
                        'user_id': account.user_id,
                        'balance': float(account.balance),
                        'cash': float(account.cash),
                        'positions': {k: float(v) for k, v in account.positions.items()},
                    }
                }), 200
        else:
            return jsonify({'error': 'Failed to open position'}), 400

    except Exception as e:
        print(f"Error in open_position_api: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/paper-trading/close-position', methods=['POST'])
def close_position_api():
    """
    Close a paper trading position.

    Request body:
    {
        "user_id": 123,
        "symbol": "BTC",
        "quantity": 0.1,
        "price": 46000.00,
        "notes": "Sold at profit"
    }

    Response:
    {
        "success": true,
        "trade": {...}
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Missing request data'}), 400

        required_fields = ['user_id', 'symbol', 'quantity', 'price']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing {field}'}), 400

        user_id = data['user_id']
        symbol = data['symbol'].upper()
        quantity = Decimal(str(data['quantity']))
        price = Decimal(str(data['price']))
        notes = data.get('notes')

        account = get_paper_trading_account(user_id)

        if not account:
            return jsonify({'error': 'Account not found'}), 404

        success = account.close_position(symbol, float(quantity), float(price), notes)

        if success:
            # Save to database
            account.save_to_database()
            
            # Get current prices for response
            current_prices = get_current_prices()
            return jsonify({
                'success': True,
                'account': {
                    'user_id': account.user_id,
                    'balance': float(account.balance),
                    'cash': float(account.cash),
                    'positions': {k: float(v) for k, v in account.positions.items()},
                    'total_value': account.get_total_value(current_prices),
                    'unrealized_pnl': account.get_unrealized_pnl(current_prices),
                    'realized_pnl': account.get_realized_pnl()
                }
            }), 200
        else:
            return jsonify({'error': 'Failed to close position'}), 400

    except Exception as e:
        print(f"Error in close_position_api: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/paper-trading/statistics/<int:user_id>', methods=['GET'])
def get_statistics_api(user_id: int):
    """
    Get paper trading statistics.

    Response:
    {
        "success": true,
        "statistics": {...}
    }
    """
    try:
        account = get_paper_trading_account(user_id)

        if not account:
            return jsonify({'error': 'Account not found'}), 404

        current_prices = get_current_prices()
        stats = account.get_statistics(current_prices)

        return jsonify({
            'success': True,
            'statistics': stats
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/portfolio/dashboard/<int:user_id>', methods=['GET'])
def get_portfolio_dashboard_api(user_id: int):
    """
    Get full portfolio dashboard.

    Query parameters:
        - market_data: JSON string with current prices

    Response:
    {
        "success": true,
        "dashboard": {...}
    }
    """
    try:
        current_prices = {}

        # Parse market data from query parameter if provided
        market_data_param = request.args.get('market_data')
        if market_data_param:
            try:
                current_prices = json.loads(market_data_param)
            except json.JSONDecodeError:
                pass

        dashboard = PortfolioDashboard(user_id).get_full_dashboard(current_prices)

        return jsonify({
            'success': True,
            'dashboard': dashboard
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/portfolio/summary/<int:user_id>', methods=['GET'])
def get_portfolio_summary_api(user_id: int):
    """
    Get portfolio summary.

    Query parameters:
        - market_data: JSON string with current prices

    Response:
    {
        "success": true,
        "summary": {...}
    }
    """
    try:
        current_prices = {}

        market_data_param = request.args.get('market_data')
        if market_data_param:
            try:
                current_prices = json.loads(market_data_param)
            except json.JSONDecodeError:
                pass

        dashboard = PortfolioDashboard(user_id)
        summary = dashboard.portfolio.get_summary(current_prices)

        return jsonify({
            'success': True,
            'summary': summary
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/portfolio/performance/<int:user_id>', methods=['GET'])
def get_portfolio_performance_api(user_id: int):
    """
    Get portfolio performance metrics.

    Query parameters:
        - market_data: JSON string with current prices

    Response:
    {
        "success": true,
        "performance": {...}
    }
    """
    try:
        current_prices = {}

        market_data_param = request.args.get('market_data')
        if market_data_param:
            try:
                current_prices = json.loads(market_data_param)
            except json.JSONDecodeError:
                pass

        dashboard = PortfolioDashboard(user_id)
        performance = dashboard.portfolio.get_performance_metrics(current_prices)

        return jsonify({
            'success': True,
            'performance': performance
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/portfolio/allocation/<int:user_id>', methods=['GET'])
def get_portfolio_allocation_api(user_id: int):
    """
    Get portfolio asset allocation.

    Query parameters:
        - market_data: JSON string with current prices

    Response:
    {
        "success": true,
        "allocation": {...}
    }
    """
    try:
        current_prices = {}

        market_data_param = request.args.get('market_data')
        if market_data_param:
            try:
                current_prices = json.loads(market_data_param)
            except json.JSONDecodeError:
                pass

        dashboard = PortfolioDashboard(user_id)
        allocation = dashboard.portfolio.get_asset_allocation(current_prices)

        return jsonify({
            'success': True,
            'allocation': allocation
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/charts/<int:user_id>/<chart_type>', methods=['GET'])
def get_chart_api(user_id: int, chart_type: str):
    """
    Get chart data for a specific chart type.

    Query parameters:
        - market_data: JSON string with current prices

    Response:
    {
        "success": true,
        "chart": {...}
    }
    """
    try:
        current_prices = {}

        market_data_param = request.args.get('market_data')
        if market_data_param:
            try:
                current_prices = json.loads(market_data_param)
            except json.JSONDecodeError:
                pass

        valid_charts = ['portfolio_value', 'allocation', 'pnl', 'returns']
        if chart_type not in valid_charts:
            return jsonify({'error': f'Invalid chart type. Must be one of: {valid_charts}'}), 400

        dashboard = PortfolioDashboard(user_id)
        chart_data = getattr(dashboard, f'get_{chart_type}_chart')(current_prices)

        return jsonify({
            'success': True,
            'chart': chart_data
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/paper-trading/place-order', methods=['POST'])
def place_order_api():
    """
    Place a paper trading order.

    Request body:
    {
        "telegram_id": 123,
        "action": "buy" | "sell",
        "symbol": "BTC",
        "quantity": 0.5,
        "amount_usd": 1000
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing request body', 'success': False}), 400

        telegram_id = data.get('telegram_id')
        action = data.get('action', '').lower()
        symbol = data.get('symbol', '').upper()
        quantity = data.get('quantity')
        amount_usd = data.get('amount_usd')

        if not telegram_id or not action or not symbol:
            return jsonify({'error': 'Missing telegram_id, action, or symbol', 'success': False}), 400

        # Get account
        account = get_paper_trading_account(telegram_id)
        if not account:
            return jsonify({'error': 'Account not found. Use /api/paper-trading/initialize first.', 'success': False}), 404

        # Get price
        current_prices = get_current_prices()
        price = current_prices.get(symbol)
        if not price:
            return jsonify({'error': f'Symbol {symbol} not found or price unavailable', 'success': False}), 404

        if action == 'buy':
            result = account.buy_order(symbol, quantity=quantity, price=price, amount_usd=amount_usd)
        elif action == 'sell':
            result = account.sell_order(symbol, quantity=quantity, price=price)
        else:
            return jsonify({'error': 'Invalid action', 'success': False}), 400

        if result.get("success"):
            # Save to database
            account.save_to_database()
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error in place_order_api: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


@api_bp.route('/paper-trading/open-orders', methods=['GET'])
def get_open_orders_api():
    """
    Get all open orders for a user.

    Query params:
        telegram_id: int
    """
    try:
        telegram_id = request.args.get('telegram_id', type=int)

        if not telegram_id:
            return jsonify({'error': 'Missing telegram_id parameter'}), 400

        # Get account
        account = get_paper_trading_account(telegram_id)
        if not account:
            return jsonify({'error': 'Account not found'}), 404

        # Get open positions/orders
        open_orders = []
        for symbol, position in account.positions.items():
            if position.quantity > 0:  # Open position
                current_prices = get_current_prices()
                current_price = current_prices.get(symbol, position.entry_price)
                unrealized_pnl = (current_price - position.entry_price) * position.quantity

                open_orders.append({
                    'symbol': symbol,
                    'action': 'buy' if position.quantity > 0 else 'sell',
                    'quantity': abs(position.quantity),
                    'entry_price': float(position.entry_price),
                    'current_price': float(current_price),
                    'unrealized_pnl': float(unrealized_pnl),
                    'total': float(position.total)
                })

        return jsonify({
            'success': True,
            'orders': open_orders
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/paper-trading/account', methods=['GET'])
def get_account_api():
    """
    Get account details (with query param).

    Query params:
        telegram_id: int
    """
    try:
        telegram_id = request.args.get('telegram_id', type=int)

        if not telegram_id:
            return jsonify({'error': 'Missing telegram_id parameter'}), 400

        account = get_paper_trading_account(telegram_id)
        if not account:
            return jsonify({'error': 'Account not found'}), 404

        current_prices = get_current_prices()

        return jsonify({
            'success': True,
            'account': {
                'user_id': account.user_id,
                'balance': float(account.balance),
                'available': float(account.cash),
                'equity': float(account.get_total_value(current_prices)),
                'margin_used': float(account.balance - account.cash)
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/portfolio', methods=['GET'])
def get_portfolio_api():
    """
    Get portfolio summary (with query param).

    Query params:
        telegram_id: int
    """
    try:
        telegram_id = request.args.get('telegram_id', type=int)

        if not telegram_id:
            return jsonify({'error': 'Missing telegram_id parameter', 'success': False}), 400

        account = get_paper_trading_account(telegram_id)
        if not account:
            return jsonify({'error': 'Account not found', 'success': False}), 404

        current_prices = get_current_prices()

        positions = []
        for symbol, quantity in account.positions.items():
            current_price = current_prices.get(symbol, 0.0)
            entry_price = float(account._get_entry_price(symbol) or current_price)
            unrealized_pnl = (current_price - entry_price) * float(quantity)
            positions.append({
                'symbol': symbol,
                'quantity': float(quantity),
                'entry_price': entry_price,
                'current_price': float(current_price),
                'unrealized_pnl': float(unrealized_pnl)
            })

        return jsonify({
            'success': True,
            'balance': float(account.balance),
            'available': float(account.cash),
            'position_count': len(positions),
            'positions': positions
        }), 200

    except Exception as e:
        logger.error(f"Error in get_portfolio_api: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


@api_bp.route('/paper-trading/performance', methods=['GET'])
def get_performance_api():
    """
    Get trading performance statistics (with query param).

    Query params:
        telegram_id: int
    """
    try:
        telegram_id = request.args.get('telegram_id', type=int)

        if not telegram_id:
            return jsonify({'error': 'Missing telegram_id parameter', 'success': False}), 400

        account = get_paper_trading_account(telegram_id)
        if not account:
            return jsonify({'error': 'Account not found', 'success': False}), 404

        # Calculate performance
        current_prices = get_current_prices()
        total_value = account.get_total_value(current_prices)
        unrealized_pnl = account.get_unrealized_pnl(current_prices)
        realized_pnl = account.get_realized_pnl()

        total_trades = len(account.paper_trades)
        win_rate = account._calculate_win_rate()

        return jsonify({
            'success': True,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'total_pnl': float(realized_pnl + unrealized_pnl),
            'equity': float(total_value),
            'unrealized_pnl': float(unrealized_pnl),
            'realized_pnl': float(realized_pnl)
        }), 200

    except Exception as e:
        logger.error(f"Error in get_performance_api: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


@api_bp.route('/paper-trading/trades', methods=['GET'])
def get_trades_api():
    """
    Get recent trades (with query param).

    Query params:
        telegram_id: int
        limit: int (default: 10)
    """
    try:
        telegram_id = request.args.get('telegram_id', type=int)
        limit = request.args.get('limit', default=10, type=int)

        if not telegram_id:
            return jsonify({'error': 'Missing telegram_id parameter'}), 400

        account = get_paper_trading_account(telegram_id)
        if not account:
            return jsonify({'error': 'Account not found'}), 404

        all_trades = account.get_trade_history(limit=limit)

        return jsonify({
            'success': True,
            'trades': all_trades
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/charts/portfolio', methods=['GET'])
def get_portfolio_chart_api():
    """
    Get portfolio chart data (with query param).

    Query params:
        telegram_id: int
    """
    try:
        telegram_id = request.args.get('telegram_id', type=int)

        if not telegram_id:
            return jsonify({'error': 'Missing telegram_id parameter'}), 400

        account = get_paper_trading_account(telegram_id)
        if not account:
            return jsonify({'error': 'Account not found'}), 404

        current_prices = get_current_prices()
        dashboard = PortfolioDashboard(telegram_id, account)
        chart_data = dashboard.analytics.generate_chart_data('portfolio_value', current_prices)

        return jsonify({
            'success': True,
            'chart_type': 'portfolio',
            'data': chart_data
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/charts/pnl', methods=['GET'])
def get_pnl_chart_api():
    """
    Get P&L chart data (with query param).

    Query params:
        telegram_id: int
    """
    try:
        telegram_id = request.args.get('telegram_id', type=int)

        if not telegram_id:
            return jsonify({'error': 'Missing telegram_id parameter'}), 400

        account = get_paper_trading_account(telegram_id)
        if not account:
            return jsonify({'error': 'Account not found'}), 404

        current_prices = get_current_prices()
        dashboard = PortfolioDashboard(telegram_id, account)
        chart_data = dashboard.analytics.generate_chart_data('pnl', current_prices)

        return jsonify({
            'success': True,
            'chart_type': 'pnl',
            'data': chart_data
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/paper-trading/initialize', methods=['POST'])
def initialize_paper_trading_api():
    """
    Initialize paper trading for a Telegram user.

    Request body:
    {
        "telegram_id": 123
    }

    Response:
    {
        "success": true
    }
    """
    try:
        data = request.get_json()

        if not data or 'telegram_id' not in data:
            return jsonify({'error': 'Missing telegram_id'}), 400

        telegram_id = data['telegram_id']
        initial_balance = float(PAPER_TRADING_INITIAL_BALANCE)

        # Check if account exists
        account = get_paper_trading_account(telegram_id)
        if account:
            return jsonify({'success': True, 'message': 'Account already exists'}), 200

        # Create new account
        account = create_paper_trading_account(telegram_id, initial_balance)

        return jsonify({
            'success': True,
            'message': 'Paper trading account initialized successfully'
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def initialize_paper_trading_for_user(user_id: int, initial_balance: float = None) -> Optional[PaperTradingAccount]:
    """
    Initialize paper trading account for a user.

    Args:
        user_id: User ID
        initial_balance: Initial balance (optional, uses config default if not provided)

    Returns:
        PaperTradingAccount or None
    """
    return create_paper_trading_account(user_id, initial_balance)
