"""
Celery task queue configuration and worker tasks.

This module provides task definitions for asynchronous operations like
data fetching, analysis, notifications, and background jobs.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from decimal import Decimal

from celery import Celery
from celery.schedules import crontab
from celery.result import AsyncResult
from celery.utils.log import get_task_logger

from app.config import settings

# Configure Celery
celery_app = Celery(
    "crypto_agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_backend_url,
    include=[
        "backend.tasks.celery_tasks",
        "backend.tasks.data_tasks",
        "backend.tasks.notification_tasks",
        "backend.tasks.analysis_tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3000,  # 50 minutes
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,

    # Result backend
    result_expires=3600,  # Results expire after 1 hour

    # Task retry settings
    task_autoretry_for=(Exception,),
    task_retry_kwargs={"max_retries": 3, "interval_start": 1, "interval_step": 1, "interval_max": 10},

    # Scheduled tasks
    beat_schedule={
        # Fetch market data every minute
        "fetch-market-data": {
            "task": "backend.tasks.data_tasks.fetch_market_data",
            "schedule": crontab(minute="*"),
        },
        # Update price trends every 5 minutes
        "update-price-trends": {
            "task": "backend.tasks.data_tasks.update_price_trends",
            "schedule": crontab(minute="*/5"),
        },
        # Check for alerts every minute
        "check-alerts": {
            "task": "backend.tasks.data_tasks.check_alerts",
            "schedule": crontab(minute="*"),
        },
        # Send pending notifications every 5 minutes
        "send-notifications": {
            "task": "backend.tasks.notification_tasks.send_notifications",
            "schedule": crontab(minute="*/5"),
        },
        # Calculate metrics daily at midnight
        "calculate-metrics": {
            "task": "backend.tasks.analysis_tasks.calculate_metrics",
            "schedule": crontab(hour=0, minute=0),
        },
        # Clean up old data daily at 2 AM
        "cleanup-old-data": {
            "task": "backend.tasks.data_tasks.cleanup_old_data",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)

logger = get_task_logger(__name__)


class TaskResults:
    """Helper class for task result tracking."""

    def __init__(self):
        self._tasks = {}

    def track(self, task_id: str, metadata: Dict[str, Any]):
        """Track a task with metadata."""
        self._tasks[task_id] = {
            "metadata": metadata,
            "started_at": datetime.now(timezone.utc),
        }

    def update(self, task_id: str, status: str, result: Any = None):
        """Update task status."""
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = status
            if result is not None:
                self._tasks[task_id]["result"] = result
                self._tasks[task_id]["completed_at"] = datetime.now(timezone.utc)

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task metadata."""
        return self._tasks.get(task_id)


# Global task results tracker
task_results = TaskResults()


# ============ Data Fetching Tasks ============

@celery_app.task(bind=True, max_retries=3, name="backend.tasks.data_tasks.fetch_market_data")
def fetch_market_data(self, agent_id: int, symbols: List[str] = None, sources: List[str] = None):
    """
    Fetch market data for specified symbols.

    Args:
        agent_id: Agent ID to fetch data for
        symbols: List of symbols to fetch (default: all)
        sources: List of data sources (default: all)

    Returns:
        Dict with fetch results
    """
    from backend.database import get_db_manager
    from backend.redis import get_redis_manager

    try:
        db = get_db_manager()
        redis_mgr = get_redis_manager()

        # Get agent
        from sqlalchemy.orm import Session
        session = db.get_session()
        agent = session.query(Agent).filter(Agent.id == agent_id).first()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Track task
        task_results.track(self.request.id, {
            "agent_id": agent_id,
            "action": "fetch_market_data",
        })

        # Determine symbols to fetch
        if not symbols:
            # Fetch popular symbols
            symbols = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT"]

        # Fetch data from market data module
        from market_data import MarketAggregator
        aggregator = MarketAggregator()
        aggregator.add_source(BinanceAPI())
        aggregator.add_source(CoinbaseAPI())

        results = {}
        for symbol in symbols:
            try:
                # Get price
                price = aggregator.get_price(symbol, symbol)
                if price:
                    results[symbol] = {
                        "price": price.price,
                        "source": price.data_source,
                        "volume": price.volume,
                    }

                    # Cache in Redis
                    cache_key = f"market:{symbol}:price:{price.data_source}"
                    redis_mgr.cache_set(cache_key, price, ttl=60)

            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")

        session.close()
        task_results.update(self.request.id, "completed", results)

        return {
            "success": True,
            "fetched": len(results),
            "symbols": list(results.keys()),
            "data": results,
        }

    except Exception as exc:
        logger.error(f"Market data fetch failed: {exc}")
        self.retry(exc=exc)
        return {"success": False, "error": str(exc)}


@celery_app.task(bind=True, max_retries=3, name="backend.tasks.data_tasks.update_price_trends")
def update_price_trends(self, symbol: str, lookback_hours: int = 24):
    """
    Update price trends for a symbol.

    Args:
        symbol: Token symbol
        lookback_hours: Number of hours to look back

    Returns:
        Dict with trend data
    """
    from backend.database import get_db_manager
    from market_data import MarketAggregator

    try:
        db = get_db_manager()
        session = db.get_session()

        # Track task
        task_results.track(self.request.id, {
            "symbol": symbol,
            "lookback_hours": lookback_hours,
            "action": "update_price_trends",
        })

        # Fetch historical data
        aggregator = MarketAggregator()
        aggregator.add_source(BinanceAPI())

        trend = aggregator.get_price_trend(symbol, lookback_hours)

        session.close()
        task_results.update(self.request.id, "completed", trend)

        return {
            "success": True,
            "symbol": symbol,
            "trend": trend,
        }

    except Exception as exc:
        logger.error(f"Price trend update failed: {exc}")
        self.retry(exc=exc)
        return {"success": False, "error": str(exc)}


@celery_app.task(bind=True, max_retries=3, name="backend.tasks.data_tasks.check_alerts")
def check_alerts(self, agent_id: int):
    """
    Check for triggered alerts.

    Args:
        agent_id: Agent ID to check alerts for

    Returns:
        Dict with triggered alerts
    """
    from backend.database import get_db_manager
    from sqlalchemy.orm import Session

    try:
        db = get_db_manager()
        session = db.get_session()

        # Track task
        task_results.track(self.request.id, {
            "agent_id": agent_id,
            "action": "check_alerts",
        })

        # Get active alerts
        from backend.database import Alert, Agent
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        alerts = session.query(Alert).filter(
            Alert.agent_id == agent_id,
            Alert.is_triggered == False
        ).all()

        triggered = []
        for alert in alerts:
            try:
                # Check if price threshold was met
                from market_data import MarketAggregator
                aggregator = MarketAggregator()
                aggregator.add_source(BinanceAPI())

                current_price = aggregator.get_price(alert.symbol, alert.symbol)

                # Check buy/sell signals
                if alert.alert_type == "buy" and current_price.price <= alert.price:
                    alert.is_triggered = True
                    alert.triggered_at = datetime.now(timezone.utc)
                    triggered.append({
                        "alert_id": alert.id,
                        "symbol": alert.symbol,
                        "type": alert.alert_type,
                        "price": alert.price,
                        "message": alert.message,
                    })

                # Similar logic for other alert types...

            except Exception as e:
                logger.warning(f"Failed to check alert {alert.id}: {e}")

        session.commit()
        session.close()
        task_results.update(self.request.id, "completed", {"triggered": triggered})

        return {
            "success": True,
            "triggered_count": len(triggered),
            "alerts": triggered,
        }

    except Exception as exc:
        logger.error(f"Alert checking failed: {exc}")
        self.retry(exc=exc)
        return {"success": False, "error": str(exc)}


# ============ Notification Tasks ============

@celery_app.task(bind=True, max_retries=3, name="backend.tasks.notification_tasks.send_notifications")
def send_notifications(self):
    """
    Send pending notifications.

    Returns:
        Dict with notification results
    """
    from backend.database import get_db_manager
    from sqlalchemy.orm import Session

    try:
        db = get_db_manager()
        session = db.get_session()

        # Get pending notifications
        from backend.database import Notification
        notifications = session.query(Notification).filter(
            Notification.is_sent == False,
            Notification.is_read == False
        ).all()

        results = {"sent": 0, "failed": 0}
        for notification in notifications:
            try:
                # Send notification
                success = _send_telegram_notification(notification)

                if success:
                    notification.is_sent = True
                    notification.sent_at = datetime.now(timezone.utc)
                    results["sent"] += 1
                else:
                    results["failed"] += 1

            except Exception as e:
                logger.error(f"Failed to send notification {notification.id}: {e}")
                results["failed"] += 1

        session.commit()
        session.close()
        task_results.update(self.request.id, "completed", results)

        return results

    except Exception as exc:
        logger.error(f"Notification sending failed: {exc}")
        self.retry(exc=exc)
        return {"success": False, "error": str(exc)}


def _send_telegram_notification(notification: Notification) -> bool:
    """Send notification via Telegram."""
    from backend.database import get_db_manager
    from sqlalchemy.orm import Session

    db = get_db_manager()
    session = db.get_session()

    try:
        from telegram import Bot
        bot = Bot(token=notification.agent.bot_token)

        message = f"🔔 *{notification.title}*\n\n{notification.message}\n\n*Data:* {json.dumps(notification.data, indent=2, ensure_ascii=False)}"

        bot.send_message(
            chat_id=notification.user_id,
            text=message,
            parse_mode="Markdown"
        )

        session.close()
        return True

    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")
        session.close()
        return False


# ============ Analysis Tasks ============

@celery_app.task(bind=True, max_retries=3, name="backend.tasks.analysis_tasks.calculate_metrics")
def calculate_metrics(self, agent_id: int, period: str = "daily"):
    """
    Calculate performance metrics for an agent.

    Args:
        agent_id: Agent ID to calculate metrics for
        period: Time period ('daily', 'weekly', 'monthly')

    Returns:
        Dict with calculated metrics
    """
    from backend.database import get_db_manager
    from sqlalchemy.orm import Session

    try:
        db = get_db_manager()
        session = db.get_session()

        # Track task
        task_results.track(self.request.id, {
            "agent_id": agent_id,
            "period": period,
            "action": "calculate_metrics",
        })

        # Get agent
        from backend.database import Agent, Trade
        from backend.models import get_closed_trades
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        trades = session.query(Trade).filter(Trade.agent_id == agent_id).all()
        trades_to_use = get_closed_trades(trades)

        # Calculate metrics
        total_trades = len(trades_to_use)
        winning_trades = [t for t in trades_to_use if t.pnl > 0]
        losing_trades = [t for t in trades_to_use if t.pnl < 0]

        total_pnl = sum(Decimal(str(getattr(t, "pnl", 0.0) or 0.0)) for t in trades_to_use)
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

        # Calculate other metrics
        metrics = {
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(avg_pnl, 2),
        }

        # Store metrics in database
        for metric_type, value in metrics.items():
            metric = AgentMetric(
                agent_id=agent_id,
                metric_type=metric_type,
                value=value,
                period=period,
            )
            session.add(metric)

        session.commit()
        session.close()
        task_results.update(self.request.id, "completed", metrics)

        return metrics

    except Exception as exc:
        logger.error(f"Metrics calculation failed: {exc}")
        self.retry(exc=exc)
        return {"success": False, "error": str(exc)}


@celery_app.task(bind=True, max_retries=3, name="backend.tasks.analysis_tasks.analyze_strategy")
def analyze_strategy(self, agent_id: int, strategy_name: str):
    """
    Analyze strategy performance.

    Args:
        agent_id: Agent ID
        strategy_name: Strategy to analyze

    Returns:
        Dict with strategy analysis
    """
    from backend.database import get_db_manager
    from sqlalchemy.orm import Session

    try:
        db = get_db_manager()
        session = db.get_session()

        # Track task
        task_results.track(self.request.id, {
            "agent_id": agent_id,
            "strategy": strategy_name,
            "action": "analyze_strategy",
        })

        # Get strategy trades
        from backend.database import Trade, Agent
        from backend.models import get_closed_trades
        agent = session.query(Agent).filter(Agent.id == agent_id).first()
        trades = session.query(Trade).filter(
            Trade.agent_id == agent_id,
            Trade.strategy == strategy_name
        ).all()
        trades_to_use = get_closed_trades(trades)

        # Calculate analysis
        analysis = {
            "strategy": strategy_name,
            "total_trades": len(trades_to_use),
            "avg_profit": 0,
            "avg_loss": 0,
            "profit_factor": 0,
        }

        if trades_to_use:
            pnls = [Decimal(str(getattr(t, "pnl", 0.0) or 0.0)) for t in trades_to_use]
            profits = [pnl for pnl in pnls if pnl > 0]
            losses = [abs(pnl) for pnl in pnls if pnl < 0]

            analysis["avg_profit"] = round(sum(profits) / len(profits), 2) if profits else 0
            analysis["avg_loss"] = round(sum(losses) / len(losses), 2) if losses else 0
            analysis["profit_factor"] = round(sum(profits) / sum(losses), 2) if losses else float('inf')

        session.close()
        task_results.update(self.request.id, "completed", analysis)

        return analysis

    except Exception as exc:
        logger.error(f"Strategy analysis failed: {exc}")
        self.retry(exc=exc)
        return {"success": False, "error": str(exc)}


# ============ Utility Tasks ============

@celery_app.task(name="backend.tasks.data_tasks.cleanup_old_data")
def cleanup_old_data(days: int = 30):
    """
    Clean up old data from the database.

    Args:
        days: Number of days to keep data

    Returns:
        Dict with cleanup results
    """
    from backend.database import get_db_manager
    from sqlalchemy.orm import Session

    try:
        db = get_db_manager()
        session = db.get_session()

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Clean up old market data
        from backend.database import MarketDataRecord
        deleted = session.query(MarketDataRecord).filter(
            MarketDataRecord.timestamp < cutoff_date
        ).delete()

        # Clean up old alerts
        from backend.database import Alert
        alert_deleted = session.query(Alert).filter(
            Alert.created_at < cutoff_date
        ).delete()

        session.commit()
        session.close()

        return {
            "success": True,
            "market_data_deleted": deleted,
            "alerts_deleted": alert_deleted,
        }

    except Exception as e:
        logger.error(f"Data cleanup failed: {e}")
        return {"success": False, "error": str(e)}
