"""
Portfolio Tracking API Routes
"""

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from decimal import Decimal

from backend.app import get_session
from backend.market_data import get_current_prices
from backend.models import User, Portfolio, Holding, Performance, Alert, StrategyPerformance, VolumeStatistics, calculate_strategy_performance
from backend.portfolio_dashboard import PortfolioDashboard, calculate_monthly_volume_stats_from_history

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/")
async def get_portfolio(
    telegram_id: str,
    db: Session = Depends(get_session)
) -> Dict:
    """Get portfolio summary and holdings"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    portfolio = user.portfolios[0] if user.portfolios else None

    if not portfolio:
        return {
            "portfolio": None,
            "holdings": [],
            "performance": None
        }

    dashboard = PortfolioDashboard(user.id)
    current_prices = get_current_prices()
    summary = dashboard.portfolio.get_summary(current_prices)
    fifo_state = dashboard.portfolio._build_fifo_state(current_prices)

    holdings = []
    for symbol, position in fifo_state["open_positions"].items():
        current_value = Decimal(str(position["market_value"]))
        entry_value = Decimal(str(position["quantity"])) * Decimal(str(position["average_entry_price"]))
        allocation = float((current_value / Decimal(str(summary["total_value"]))) * 100) if summary["total_value"] > 0 else 0

        holdings.append({
            "symbol": symbol,
            "quantity": float(position["quantity"]),
            "avg_cost": float(position["average_entry_price"]),
            "current_price": float(current_prices.get(symbol, position["average_entry_price"])),
            "current_value": float(current_value),
            "pnl": float(position["unrealized_pnl"] + position["realized_pnl"]),
            "pnl_pct": ((float(current_value - entry_value) / float(entry_value)) * 100) if entry_value > 0 else 0,
            "allocation": allocation
        })

    performance = summary["performance"]
    top_assets = dashboard.analytics.get_top_assets(current_prices)

    return {
        "portfolio": {
            "id": portfolio.id,
            "created_at": portfolio.created_at.isoformat() if portfolio.created_at else None
        },
        "holdings": holdings,
        "performance": performance,
        "top_assets": top_assets
    }


@router.get("/trades/")
async def get_trades(
    telegram_id: str,
    limit: int = 50,
    db: Session = Depends(get_session)
) -> List[Dict]:
    """Get trade history"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    dashboard = PortfolioDashboard(user.id)
    trades = dashboard.portfolio.get_trade_history(limit=limit)

    return [
        {
            "id": trade.get("id"),
            "symbol": trade.get("symbol"),
            "trade_type": trade.get("action"),
            "quantity": float(trade.get("quantity", 0.0)),
            "price": float(trade.get("exit_price") or trade.get("entry_price") or 0.0),
            "amount": float(trade.get("quantity", 0.0)) * float(trade.get("exit_price") or trade.get("entry_price") or 0.0),
            "pnl": float(trade.get("pnl", 0.0)),
            "strategy": trade.get("strategy"),
            "status": trade.get("status"),
            "timestamp": trade.get("exit_date") or trade.get("entry_date"),
            "remaining_quantity": float(trade.get("remaining_quantity", 0.0)),
            "notes": trade.get("notes"),
        }
        for trade in trades
    ]


@router.get("/performance/")
async def get_performance(
    telegram_id: str,
    db: Session = Depends(get_session)
) -> Dict:
    """Get detailed performance metrics"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    dashboard = PortfolioDashboard(user.id)
    current_prices = get_current_prices()
    stats = dashboard.portfolio.get_performance_metrics(current_prices)
    trades = dashboard.portfolio.get_trade_history(limit=10000)

    if not trades:
        return {
            "total_value": 0.0,
            "total_pnl": 0.0,
            "return_pct": 0.0,
            "total_trades": 0,
            "buy_trades": 0,
            "sell_trades": 0,
            "avg_pnl": 0.0,
            "win_rate": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "monthly_performance": []
        }

    monthly_performance: List[Dict] = []
    monthly_index: Dict[tuple, Dict[str, float]] = {}
    for trade in trades:
        stamp = trade.get("exit_date") or trade.get("entry_date")
        if not stamp:
            continue
        dt = datetime.fromisoformat(stamp)
        key = (dt.year, dt.month)
        bucket = monthly_index.setdefault(key, {"trades": 0, "total_pnl": 0.0})
        bucket["trades"] += 1
        bucket["total_pnl"] += float(trade.get("pnl", 0.0))

    for (year, month), bucket in sorted(monthly_index.items()):
        monthly_performance.append({
            "year": year,
            "month": month,
            "trades": bucket["trades"],
            "total_pnl": bucket["total_pnl"]
        })

    return {
        "total_value": float(stats["total_value"]),
        "total_pnl": float(stats["total_pnl"]),
        "return_pct": float(stats["return_pct"]),
        "total_trades": stats["total_trades"],
        "buy_trades": sum(1 for trade in trades if trade.get("action") == "buy"),
        "sell_trades": sum(1 for trade in trades if trade.get("action") == "sell"),
        "avg_pnl": float(stats["avg_pnl"]),
        "win_rate": float(stats["win_rate"]),
        "max_drawdown": 0.0,
        "sharpe_ratio": 0.0,
        "monthly_performance": monthly_performance
    }


@router.get("/strategies/")
async def get_strategy_performance(
    telegram_id: str,
    db: Session = Depends(get_session)
) -> Dict:
    """Get performance metrics per strategy"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    portfolio = user.portfolios[0] if user.portfolios else None

    if not portfolio:
        return {}

    dashboard = PortfolioDashboard(user.id)
    strategies = dashboard.analytics.get_strategy_performance()

    return strategies


@router.get("/alerts/")
async def get_alerts(
    telegram_id: str,
    db: Session = Depends(get_session)
) -> List[Dict]:
    """Get user alerts"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    alerts = (
        db.query(Alert)
        .filter(Alert.user_id == user.id)
        .order_by(Alert.created_at.desc())
        .all()
    )

    return [
        {
            "id": alert.id,
            "type": alert.type,
            "symbol": alert.symbol,
            "message": alert.message,
            "is_read": alert.is_read,
            "created_at": alert.created_at.isoformat() if alert.created_at else None
        }
        for alert in alerts
    ]


@router.get("/holdings/{symbol}/history/")
async def get_holding_history(
    telegram_id: str,
    symbol: str,
    db: Session = Depends(get_session)
) -> List[Dict]:
    """Get trading history for a specific asset"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    dashboard = PortfolioDashboard(user.id)
    trades = [
        trade for trade in dashboard.portfolio.get_trade_history(limit=10000)
        if trade.get("symbol") == symbol.upper()
    ]

    return [
        {
            "id": trade.get("id"),
            "trade_type": trade.get("action"),
            "quantity": float(trade.get("quantity", 0.0)),
            "remaining_quantity": float(trade.get("remaining_quantity", 0.0)),
            "price": float(trade.get("exit_price") or trade.get("entry_price") or 0.0),
            "amount": float(trade.get("quantity", 0.0)) * float(trade.get("exit_price") or trade.get("entry_price") or 0.0),
            "pnl": float(trade.get("pnl", 0.0)),
            "status": trade.get("status"),
            "timestamp": trade.get("exit_date") or trade.get("entry_date"),
            "notes": trade.get("notes")
        }
        for trade in trades
    ]


@router.get("/volume/{month}/{year}/")
async def get_volume_stats(
    telegram_id: str,
    month: int,
    year: int,
    db: Session = Depends(get_session)
) -> Dict:
    """Get trading volume statistics for a specific month"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    portfolio = user.portfolios[0] if user.portfolios else None

    if not portfolio:
        return {
            "total_trades": 0,
            "buy_trades": 0,
            "sell_trades": 0,
            "buy_to_sell_ratio": 0.0,
            "avg_buy_amount": 0.0,
            "avg_sell_amount": 0.0
        }

    stats = (
        db.query(VolumeStatistics)
        .filter(
            VolumeStatistics.user_id == user.id,
            VolumeStatistics.portfolio_id == portfolio.id,
            VolumeStatistics.month == month,
            VolumeStatistics.year == year
        )
        .first()
    )

    if not stats:
        dashboard = PortfolioDashboard(user.id)
        history = dashboard.portfolio.get_trade_history(limit=10000)
        return calculate_monthly_volume_stats_from_history(history, month, year)

    if stats:
        return {
            "total_trades": stats.total_trades,
            "buy_trades": stats.buy_trades,
            "sell_trades": stats.sell_trades,
            "buy_to_sell_ratio": stats.buy_to_sell_ratio,
            "avg_buy_amount": float(stats.avg_buy_amount),
            "avg_sell_amount": float(stats.avg_sell_amount)
        }

    return {
        "total_trades": 0,
        "buy_trades": 0,
        "sell_trades": 0,
        "buy_to_sell_ratio": 0.0,
        "avg_buy_amount": 0.0,
        "avg_sell_amount": 0.0
    }
