from decimal import Decimal
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import sys

from backend.paper_trading import PaperTradingAccount, create_paper_trading_account
from backend.models import calculate_win_rate, calculate_strategy_performance, get_closed_trades
from backend.portfolio_dashboard import Portfolio
from risk_management import RiskManager
from tools import strategy_tools
from tools import trading_control
from backend.portfolio_dashboard import calculate_monthly_volume_stats_from_history


class DummyWallet:
    def get_wallet_balance(self) -> float:
        return 10_000.0


class DummyAnalyzer:
    pass


def test_strategy_tools_use_sanitized_memory_path(tmp_path, monkeypatch):
    monkeypatch.setattr(strategy_tools, "MEMORY_DIR", tmp_path)

    result = strategy_tools.write_strategy("../eth??", "strategy body")
    assert "Successfully saved strategy" in result

    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0].parent == tmp_path
    assert "strategy body" in strategy_tools.read_strategy("../eth??")


def test_mission_briefing_strategy_is_anchored():
    briefing = strategy_tools.read_strategy("mission_briefing_strategy")

    assert "workspace/tobyworld_master_archive.md" in briefing
    assert "Tobyworld Trinity assets are TOBY, PATIENCE, and TABOSHI" in briefing


def test_fifo_close_updates_correct_trade_lots():
    account = PaperTradingAccount(user_id=7, initial_balance=1_000.0)
    assert account.open_position("ETH", 1.0, 100.0, strategy="first")
    assert account.open_position("ETH", 1.0, 120.0, strategy="second")

    assert account.close_position("ETH", 1.5, 150.0)

    assert account.positions["ETH"] == Decimal("0.5")
    assert account.paper_trades[0]["status"] == "closed"
    assert account.paper_trades[0]["remaining_quantity"] == 0.0
    assert account.paper_trades[1]["status"] == "partial"
    assert account.paper_trades[1]["remaining_quantity"] == 0.5
    assert round(account.last_close_summary["pnl"], 2) == 65.00


def test_sell_order_reports_partial_status():
    account = PaperTradingAccount(user_id=8, initial_balance=1_000.0)
    assert account.open_position("ETH", 1.0, 100.0, strategy="first")

    result = account.sell_order("ETH", 0.4, 150.0)

    assert result["success"] is True
    assert result["status"] == "partial"
    assert account.paper_trades[0]["status"] == "partial"
    assert round(result["pnl"], 2) == 20.00


def test_paper_trading_statistics_has_win_rate():
    account = PaperTradingAccount(user_id=9, initial_balance=1_000.0)
    assert account.open_position("ETH", 1.0, 100.0, strategy="first")
    assert account.close_position("ETH", 1.0, 120.0)

    stats = account.get_statistics({"ETH": 120.0})

    assert round(stats["win_rate"], 2) == 100.0
    assert stats["closed_trades"] == 1


def test_execute_paper_trade_uses_entry_price_when_live_price_unresolved(monkeypatch):
    create_paper_trading_account(91, 1_000.0)
    monkeypatch.setattr(trading_control, "_get_live_price", lambda symbol: 0.0)

    result = trading_control.execute_paper_trade(
        user_id=91,
        symbol="TOBY",
        side="buy",
        amount=100.0,
        entry_price=0.01,
    )

    assert "Paper BUY Executed" in result
    assert "Symbol: TOBY" in result
    assert "Price: $0.01" in result


def test_execute_paper_trade_prefers_live_price_for_normal_symbols(monkeypatch):
    account = create_paper_trading_account(92, 1_000.0)
    monkeypatch.setattr(trading_control, "_get_live_price", lambda symbol: 200.0)

    result = trading_control.execute_paper_trade(
        user_id=92,
        symbol="ETH",
        side="buy",
        amount=200.0,
        entry_price=100.0,
    )

    assert "Paper BUY Executed" in result
    assert account.positions["ETH"] == Decimal("1.0")
    assert account.paper_trades[-1]["entry_price"] == 200.0


def test_validate_entry_includes_risk_reward_ratio():
    manager = RiskManager(DummyWallet(), DummyAnalyzer())

    valid, message, params = manager.validate_entry(
        token_address="ETH",
        symbol="ETH",
        entry_price=100.0,
        target_position_size=1.0,
        stop_loss_pct=5.0,
        take_profit_pct=10.0,
        risk_reward_ratio=2.0,
    )

    assert valid is True
    assert message == "Entry validated successfully"
    assert params["risk_reward_ratio"] == 2.0


def test_calculate_win_rate_uses_closed_trades_when_available():
    trades = [
        SimpleNamespace(status="open", pnl=100.0),
        SimpleNamespace(status="closed", pnl=10.0),
        SimpleNamespace(status="COMPLETED", pnl=-5.0),
    ]

    assert round(calculate_win_rate(trades), 2) == 50.0


def test_get_closed_trades_prefers_closed_subset():
    trades = [
        SimpleNamespace(status="open", pnl=100.0),
        SimpleNamespace(status="closed", pnl=10.0),
        SimpleNamespace(status="partial", pnl=-5.0),
    ]

    closed_trades = get_closed_trades(trades)

    assert len(closed_trades) == 1
    assert closed_trades[0].status == "closed"


def test_calculate_strategy_performance_uses_closed_trades(monkeypatch):
    trades = [
        SimpleNamespace(strategy="A", status="open", pnl=100.0),
        SimpleNamespace(strategy="A", status="closed", pnl=25.0),
        SimpleNamespace(strategy="B", status="closed", pnl=-10.0),
    ]

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return self.rows

    class FakeSession:
        def query(self, *args, **kwargs):
            return FakeQuery(trades)

        def close(self):
            pass

    fake_app = SimpleNamespace(get_session=lambda: FakeSession())
    monkeypatch.setitem(sys.modules, "app", fake_app)

    result = calculate_strategy_performance(user_id=1, portfolio_id=1)

    assert result["A"]["trades"] == 1
    assert result["A"]["total_pnl"] == Decimal("25.00")
    assert result["A"]["win_rate"] == 100.0
    assert result["B"]["trades"] == 1
    assert result["B"]["total_pnl"] == Decimal("-10.00")


def test_risk_manager_closes_matching_trade_not_last_trade():
    manager = RiskManager(DummyWallet(), DummyAnalyzer())

    assert manager.open_position("ETH", "ETH", 100.0, 1.0, stop_loss_pct=5.0, take_profit_pct=10.0, risk_reward_ratio=2.0)["success"]
    assert manager.open_position("SOL", "SOL", 50.0, 1.0, stop_loss_pct=5.0, take_profit_pct=10.0, risk_reward_ratio=2.0)["success"]

    result = manager._close_position("ETH", "take_profit", 120.0)

    assert result["success"] is True
    assert manager.trade_history[0]["status"] == "closed"
    assert manager.trade_history[0]["exit_reason"] == "take_profit"
    assert manager.trade_history[1]["status"] == "open"


def test_db_dashboard_fifo_rebuild_handles_partial_closes():
    now = datetime.now(timezone.utc)
    trades = [
        SimpleNamespace(
            id=1,
            user_id=1,
            symbol="ETH",
            action="buy",
            trade_type="buy",
            strategy="first",
            entry_price=100.0,
            exit_price=None,
            price=100.0,
            quantity=1.0,
            pnl=0.0,
            status="closed",
            entry_date=now - timedelta(days=2),
            exit_date=now - timedelta(days=1),
            timestamp=now - timedelta(days=2),
            notes="first lot",
        ),
        SimpleNamespace(
            id=2,
            user_id=1,
            symbol="ETH",
            action="buy",
            trade_type="buy",
            strategy="second",
            entry_price=120.0,
            exit_price=None,
            price=120.0,
            quantity=1.0,
            pnl=0.0,
            status="partial",
            entry_date=now - timedelta(days=1, hours=12),
            exit_date=now - timedelta(days=1),
            timestamp=now - timedelta(days=1, hours=12),
            notes="second lot",
        ),
        SimpleNamespace(
            id=3,
            user_id=1,
            symbol="ETH",
            action="sell",
            trade_type="sell",
            strategy="first",
            entry_price=113.33,
            exit_price=150.0,
            price=150.0,
            quantity=1.5,
            pnl=65.0,
            status="closed",
            entry_date=now - timedelta(days=1),
            exit_date=now - timedelta(days=1),
            timestamp=now - timedelta(days=1),
            notes="partial exit",
        ),
    ]

    portfolio = Portfolio.__new__(Portfolio)
    portfolio.user_id = 1
    portfolio.account = None
    portfolio.trades = trades

    current_prices = {"ETH": 200.0}
    assert portfolio.get_portfolio_value(current_prices) == 100.0
    assert round(portfolio.get_total_profit_loss(current_prices), 2) == 105.0

    history = portfolio.get_trade_history()
    sell_rows = [trade for trade in history if trade["action"] == "sell"]
    buy_rows = [trade for trade in history if trade["action"] == "buy"]

    assert sell_rows[0]["pnl"] == 65.0
    buy_by_id = {trade["id"]: trade for trade in buy_rows}
    assert buy_by_id[1]["remaining_quantity"] == 0.0
    assert buy_by_id[2]["remaining_quantity"] == 0.5

    metrics = portfolio.get_performance_metrics(current_prices)
    assert metrics["closed_trades"] == 1
    assert round(metrics["win_rate"], 2) == 100.0


def test_normalized_monthly_volume_stats_from_history():
    month = 4
    year = 2026
    trades = [
        {
            "id": 1,
            "action": "buy",
            "quantity": 2.0,
            "entry_price": 100.0,
            "entry_date": "2026-04-10T12:00:00",
        },
        {
            "id": 2,
            "action": "sell",
            "quantity": 1.5,
            "entry_price": 0.0,
            "exit_price": 120.0,
            "exit_date": "2026-04-12T12:00:00",
        },
        {
            "id": 3,
            "action": "buy",
            "quantity": 1.0,
            "entry_price": 90.0,
            "entry_date": "2026-03-15T12:00:00",
        },
    ]

    stats = calculate_monthly_volume_stats_from_history(trades, month, year)

    assert stats["total_trades"] == 2
    assert stats["buy_trades"] == 1
    assert stats["sell_trades"] == 1
    assert stats["buy_to_sell_ratio"] == 1.0
    assert round(stats["avg_buy_amount"], 2) == 200.0
    assert round(stats["avg_sell_amount"], 2) == 180.0
