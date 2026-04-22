import re
from pathlib import Path
from core.tools import register_tool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = PROJECT_ROOT / "workspace" / "agent_memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _safe_symbol(symbol: str) -> str:
    """Normalize a symbol so it cannot escape the memory directory."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", symbol.strip().upper())
    return cleaned or "UNKNOWN"


def _strategy_path(symbol: str) -> Path:
    safe_symbol = _safe_symbol(symbol).lower()
    suffix = "" if safe_symbol.endswith("_strategy") else "_strategy"
    return MEMORY_DIR / f"{safe_symbol}{suffix}.md"

@register_tool(
    name="read_strategy",
    description="Read the persistent strategy and trading log for a specific symbol.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Trading symbol (e.g., BTC, ETH)",
            }
        },
        "required": ["symbol"],
    },
)
def read_strategy(symbol: str) -> str:
    """Read the strategy log for a given symbol."""
    file_path = _strategy_path(symbol)
    if not file_path.exists():
        return f"No strategy file found for {symbol}. You can create one using write_strategy."
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading strategy: {e}"

@register_tool(
    name="write_strategy",
    description="Write or update the persistent strategy and trading log for a specific symbol. This file should be used as the source of truth for your paper-trade updates.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Trading symbol (e.g., BTC, ETH)",
            },
            "content": {
                "type": "string",
                "description": "The full markdown content to save.",
            }
        },
        "required": ["symbol", "content"],
    },
)
def write_strategy(symbol: str, content: str) -> str:
    """Write the strategy log for a given symbol."""
    file_path = _strategy_path(symbol)
    try:
        file_path.write_text(content, encoding="utf-8")
        return f"Successfully saved strategy for {symbol} to {file_path}"
    except Exception as e:
        return f"Error writing strategy: {e}"

@register_tool(
    name="calculate_position_size",
    description="Calculate conservative position size based on account balance, risk percentage, and stop loss distance.",
    input_schema={
        "type": "object",
        "properties": {
            "account_balance": {
                "type": "number",
                "description": "Total account balance (e.g., 10000.0)",
            },
            "risk_percentage": {
                "type": "number",
                "description": "Percentage of account to risk (e.g., 1.5 for 1.5%)",
            },
            "stop_loss_percentage": {
                "type": "number",
                "description": "Distance to stop loss in percentage (e.g., 5.0 for 5%)",
            },
            "current_price": {
                "type": "number",
                "description": "Current asset price (e.g., 2500.0)",
            }
        },
        "required": ["account_balance", "risk_percentage", "stop_loss_percentage", "current_price"],
    },
)
def calculate_position_size(account_balance: float, risk_percentage: float, stop_loss_percentage: float, current_price: float) -> str:
    """Calculate the exact position size based on stop loss distance."""
    try:
        if stop_loss_percentage <= 0:
            return "Error: Stop loss percentage must be greater than 0."
        if current_price <= 0:
            return "Error: Current price must be greater than 0."
            
        dollar_risk = account_balance * (risk_percentage / 100.0)
        notional_position = dollar_risk / (stop_loss_percentage / 100.0)
        units = notional_position / current_price
        
        result = (
            f"Position Sizing Calculation:\n"
            f"- Account Balance: ${account_balance:.2f}\n"
            f"- Risk Percentage: {risk_percentage}%\n"
            f"- Dollar Risk: ${dollar_risk:.2f}\n"
            f"- Stop Loss Distance: {stop_loss_percentage}%\n"
            f"- Total Notional Position Value: ${notional_position:.2f}\n"
            f"- Target Asset Quantity: {units:.6f} units at ${current_price:.2f}\n"
        )
        return result
    except Exception as e:
        return f"Error calculating position size: {e}"

@register_tool(
    name="write_wisdom_commandment",
    description="Write a new overarching commandment to the permanent Wisdom Ledger based on an event or anomaly.",
    input_schema={
        "type": "object",
        "properties": {
            "commandment": {
                "type": "string",
                "description": "The exact rule text to add to the wisdom ledger.",
            }
        },
        "required": ["commandment"],
    },
)
def write_wisdom_commandment(commandment: str) -> str:
    """Add a commandment to the wisdom store."""
    try:
        from memory.wisdom import WisdomStore
        store = WisdomStore()
        store.add_commandment(commandment)
        return f"Successfully added commandment: {commandment}"
    except Exception as e:
        return f"Error adding commandment: {e}"
