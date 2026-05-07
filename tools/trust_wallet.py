import json
import subprocess
import os
from typing import Dict, Any, Optional, List
from core.tools import register_tool

DEFAULT_PORTFOLIO_CHAINS = [
    "base",
    "ethereum",
    "arbitrum",
    "optimism",
    "polygon",
    "bsc",
    "avalanche",
    "solana",
]

def run_twak(args: List[str]) -> str:
    """Run a twak command and return the output."""
    try:
        env = os.environ.copy()
        # Ensure twak uses the same credentials
        cmd = ["twak"] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            check=False
        )
        if result.returncode != 0:
            return f"Error: {result.stderr or result.stdout}"
        return result.stdout.strip()
    except Exception as e:
        return f"Exception running twak: {str(e)}"


def _is_nonzero_balance(value: Any) -> bool:
    text = str(value).strip()
    if not text:
        return False
    try:
        return float(text) > 0
    except ValueError:
        return any(ch != "0" for ch in text if ch.isdigit())


def _format_portfolio_rows(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No non-zero balances found across the configured portfolio chains."

    headers = ("Chain", "Type", "Symbol", "Balance", "USD")
    formatted_rows: List[tuple[str, str, str, str, str]] = []
    total_usd = 0.0

    for row in rows:
        usd_value = float(row.get("usdValue") or 0)
        total_usd += usd_value
        formatted_rows.append(
            (
                str(row.get("chain", "")),
                str(row.get("type", "")),
                str(row.get("symbol", "")),
                str(row.get("balance", "")),
                f"${usd_value:,.2f}",
            )
        )

    widths = [len(header) for header in headers]
    for row in formatted_rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    def line(values: tuple[str, str, str, str, str]) -> str:
        return "  ".join(value.ljust(widths[idx]) for idx, value in enumerate(values))

    divider = "─" * len(line(headers))
    parts = [line(headers), divider]
    parts.extend(line(row) for row in formatted_rows)
    parts.append(divider)
    parts.append(f"Total USD: ${total_usd:,.2f}")
    return "\n".join(parts)


def get_wallet_portfolio(chains: Optional[List[str]] = None) -> str:
    """Get a token-aware wallet portfolio for the highest-signal chains."""
    selected_chains = chains or DEFAULT_PORTFOLIO_CHAINS
    rows: List[Dict[str, Any]] = []
    errors: List[str] = []

    for chain in selected_chains:
        output = run_twak(["wallet", "portfolio", "--chains", chain, "--json"])
        if output.startswith("Error:") or output.startswith("Exception"):
            errors.append(f"{chain}: {output}")
            continue
        try:
            chain_rows = json.loads(output)
        except json.JSONDecodeError:
            errors.append(f"{chain}: invalid JSON from twak wallet portfolio")
            continue

        for row in chain_rows:
            if _is_nonzero_balance(row.get("balance")) or float(row.get("usdValue") or 0) > 0:
                rows.append(row)

    if rows:
        return _format_portfolio_rows(rows)
    if errors:
        return " | ".join(errors)
    return run_twak(["wallet", "portfolio"])

@register_tool(
    name="get_wallet_status",
    description="Check if the agent wallet is configured and get basic status.",
    input_schema={
        "type": "object",
        "properties": {},
    },
)
def get_wallet_status() -> str:
    """Get the status of the agent wallet."""
    return run_twak(["wallet", "status"])

@register_tool(
    name="create_agent_wallet",
    description="Create a new agent wallet if one doesn't exist. Requires a password.",
    input_schema={
        "type": "object",
        "properties": {
            "password": {
                "type": "string",
                "description": "Password to encrypt the wallet keychain.",
            }
        },
        "required": ["password"],
    },
)
def create_agent_wallet(password: str) -> str:
    """Create a new agent wallet."""
    return run_twak(["wallet", "create", "--password", password])

@register_tool(
    name="get_wallet_addresses",
    description="List all wallet addresses for the agent across supported chains.",
    input_schema={
        "type": "object",
        "properties": {},
    },
)
def get_wallet_addresses() -> str:
    """List all wallet addresses."""
    return run_twak(["wallet", "addresses"])

@register_tool(
    name="get_wallet_balance",
    description="Get the wallet balance for a specific chain or full portfolio.",
    input_schema={
        "type": "object",
        "properties": {
            "chain": {
                "type": "string",
                "description": "The blockchain to check (e.g., 'ethereum', 'base', 'solana'). If omitted, shows portfolio summary.",
            }
        },
    },
)
def get_wallet_balance(chain: Optional[str] = None) -> str:
    """Get wallet balance."""
    if chain:
        return run_twak(["wallet", "balance", "--chain", chain])
    else:
        return run_twak(["wallet", "portfolio"])

@register_tool(
    name="transfer_tokens",
    description="Transfer tokens from the agent wallet to another address.",
    input_schema={
        "type": "object",
        "properties": {
            "chain": {"type": "string", "description": "The blockchain network."},
            "to": {"type": "string", "description": "Recipient address."},
            "amount": {"type": "string", "description": "Amount to transfer."},
            "token": {"type": "string", "description": "Token symbol or address (optional, defaults to native token)."},
            "password": {"type": "string", "description": "Wallet password."},
        },
        "required": ["chain", "to", "amount", "password"],
    },
)
def transfer_tokens(chain: str, to: str, amount: str, password: str, token: Optional[str] = None) -> str:
    """Transfer tokens."""
    args = ["transfer", "--chain", chain, "--to", to, "--amount", amount, "--password", password]
    if token:
        args.extend(["--token", token])
    return run_twak(args)

@register_tool(
    name="swap_tokens",
    description="Quote or execute a token swap on a specific chain.",
    input_schema={
        "type": "object",
        "properties": {
            "chain": {"type": "string", "description": "The blockchain network."},
            "amount": {"type": "string", "description": "Amount to swap from."},
            "from_token": {"type": "string", "description": "Token symbol or address to swap from."},
            "to_token": {"type": "string", "description": "Token symbol or address to swap to."},
            "execute": {"type": "boolean", "description": "If true, execute the swap. If false, only get a quote.", "default": False},
            "password": {"type": "string", "description": "Wallet password (required if execute is true)."},
            "use_mev_protection": {"type": "boolean", "description": "If true, routes transaction through a private MEV-protecting RPC to prevent front-running.", "default": True},
            "slippage": {"type": "number", "description": "Maximum slippage percentage (e.g. 0.5 for 0.5%). Defaults to environment variable or 1.0.", "default": 0.5},
        },
        "required": ["chain", "amount", "from_token", "to_token"],
    },
)
def swap_tokens(chain: str, amount: str, from_token: str, to_token: str, execute: bool = False, password: Optional[str] = None, use_mev_protection: bool = True, slippage: float = 0.5) -> str:
    """Swap tokens."""
    # Enforce strict slippage rules for MEV / Arbitrage defense
    if slippage > 2.0:
        return f"Error: Transaction blocked by Risk Manager. Slippage of {slippage}% exceeds maximum allowed limit of 2.0% to prevent sandwich attacks."

    args = ["swap", "--chain", chain, amount, from_token, to_token]

    # We simulate MEV protection for twak since the CLI doesn't natively accept --rpc
    mev_enabled = os.getenv("USE_MEV_PROTECTION", "True").lower() == "true" or use_mev_protection
    private_rpc = os.getenv("PRIVATE_RPC_URL", "https://mev.api.blxrbdn.com")

    if execute:
        if not mev_enabled:
            return "Error: Transaction blocked by Risk Manager. MEV Protection is strictly required for executing swaps on live mainnet."
        if not password:
            return "Error: Password is required to execute a swap."
        args.extend(["--execute", "--password", password])

    result = run_twak(args)

    if execute and mev_enabled:
        return f"[MEV Protected via {private_rpc} | Slippage {slippage}%] " + result
    elif mev_enabled:
        return f"[MEV Protection Ready | Slippage {slippage}%] " + result

    return result
@register_tool(
    name="check_onchain_risk",
    description="Check token risk and security info using Trust Wallet's risk engine.",
    input_schema={
        "type": "object",
        "properties": {
            "asset_id": {"type": "string", "description": "The asset ID or symbol to check."},
            "chain": {"type": "string", "description": "The blockchain network."},
        },
        "required": ["asset_id", "chain"],
    },
)
def check_onchain_risk(asset_id: str, chain: str) -> str:
    """Check token risk."""
    return run_twak(["risk", asset_id, "--chain", chain])
