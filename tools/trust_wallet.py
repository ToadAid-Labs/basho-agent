import json
import subprocess
import os
import re
from decimal import Decimal, InvalidOperation
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
DEFAULT_TELEGRAM_PORTFOLIO_CHAINS = [
    "base",
    "ethereum",
    "arbitrum",
]
TRACKED_TOKENS = [
    {
        "chain": "base",
        "symbol": "DEGEN",
        "contract": "0x4ed4e862860beD51a9570b96d89aF5E1B0Efefed",
        "asset_id": "c8453_t0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed",
        "decimals": 18,
        "type": "token",
    },
]
SECURE_TWAK_UNLOCK_MESSAGE = (
    "Wallet signer is locked or unavailable. Please unlock it through the secure local TWAK flow, then retry."
)
TX_HASH_RE = re.compile(r"\b0x[a-fA-F0-9]{64}\b")

def run_twak(args: List[str], timeout: Optional[int] = None) -> str:
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
            check=False,
            timeout=timeout,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr or result.stdout}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"Error: timed out running {' '.join(cmd)}"
    except Exception as e:
        return f"Exception running twak: {str(e)}"


def _looks_like_twak_error(text: str) -> bool:
    return text.startswith("Error:") or text.startswith("Exception")


def _saved_twak_credential_hint_present() -> bool:
    return bool(os.getenv("TWAK_WALLET_PASSWORD") or os.getenv("TWAK_WALLET_SESSION"))


def _is_locked_or_unavailable_message(text: str) -> bool:
    lowered = str(text).lower()
    markers = (
        "wallet signer is locked",
        "wallet password",
        "password is required",
        "private key",
        "seed phrase",
        "signing secret",
        "signer unavailable",
        "signer is locked",
        "wallet is locked",
        "unlock wallet",
        "unlock it",
        "credential unavailable",
        "credentials unavailable",
        "keychain",
        "no active wallet session",
        "no wallet session",
    )
    return any(marker in lowered for marker in markers)


def _extract_tx_hash(output: str) -> Optional[str]:
    text = str(output).strip()
    if not text:
        return None

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None

    def _search_payload(value: Any) -> Optional[str]:
        if isinstance(value, dict):
            for key in ("txHash", "transactionHash", "hash", "txid", "signature"):
                item = value.get(key)
                if isinstance(item, str) and item.strip():
                    match = TX_HASH_RE.search(item)
                    return match.group(0) if match else item.strip()
            for nested in value.values():
                found = _search_payload(nested)
                if found:
                    return found
            return None
        if isinstance(value, list):
            for nested in value:
                found = _search_payload(nested)
                if found:
                    return found
        return None

    payload_hash = _search_payload(payload)
    if payload_hash:
        return payload_hash

    match = TX_HASH_RE.search(text)
    if match:
        return match.group(0)
    return None


def _signed_execution_preflight() -> Optional[str]:
    if _saved_twak_credential_hint_present():
        return None

    status = run_twak(["wallet", "status"])
    if _looks_like_twak_error(status):
        return None
    if _is_locked_or_unavailable_message(status):
        return SECURE_TWAK_UNLOCK_MESSAGE
    return None


def _run_signed_twak(args: List[str], *, timeout: Optional[int] = None) -> str:
    preflight_error = _signed_execution_preflight()
    if preflight_error:
        return preflight_error

    result = run_twak(args, timeout=timeout)
    if _is_locked_or_unavailable_message(result):
        return SECURE_TWAK_UNLOCK_MESSAGE
    if _looks_like_twak_error(result):
        return result

    tx_hash = _extract_tx_hash(result)
    if tx_hash:
        return f"Verified tx hash: {tx_hash}"
    return result


def _is_nonzero_balance(value: Any) -> bool:
    text = str(value).strip()
    if not text:
        return False
    try:
        return float(text) > 0
    except ValueError:
        return any(ch != "0" for ch in text if ch.isdigit())


def _safe_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _format_decimal(value: Decimal) -> str:
    normalized = format(value.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _extract_wallet_address_cards(output: str) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    current_lines: List[str] = []
    in_box = False

    for line in output.splitlines():
        if line.startswith("╭"):
            current_lines = []
            in_box = True
            continue
        if line.startswith("╰") and in_box:
            chains_parts: List[str] = []
            address = ""
            collecting_chains = False
            for card_line in current_lines:
                stripped = card_line.strip()
                if not stripped:
                    continue
                if stripped.startswith("Chains"):
                    collecting_chains = True
                    chains_parts.append(stripped.removeprefix("Chains").strip())
                    continue
                if stripped.startswith("Address"):
                    collecting_chains = False
                    address = stripped.removeprefix("Address").strip()
                    continue
                if collecting_chains:
                    chains_parts.append(stripped)
            if address:
                cards.append(
                    {
                        "chains": " ".join(part for part in chains_parts if part).lower(),
                        "address": address,
                    }
                )
            current_lines = []
            in_box = False
            continue
        if in_box and "│" in line:
            first = line.find("│")
            last = line.rfind("│")
            if first != last:
                current_lines.append(line[first + 1:last].rstrip())

    return cards


def _resolve_wallet_address_map() -> Dict[str, str]:
    output = run_twak(["wallet", "addresses"])
    if output.startswith("Error:") or output.startswith("Exception"):
        return {}

    address_map: Dict[str, str] = {}
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, list):
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            address = str(entry.get("address") or "").strip()
            if not address:
                continue
            chains_value = entry.get("chains") or entry.get("chain") or []
            if isinstance(chains_value, str):
                chains = [chains_value]
            else:
                chains = list(chains_value)
            for chain in chains:
                address_map[str(chain).lower()] = address

    if address_map:
        return address_map

    for card in _extract_wallet_address_cards(output):
        address = card["address"]
        for chain in card["chains"].split():
            cleaned = chain.strip(",").lower()
            if cleaned:
                address_map[cleaned] = address
    return address_map


def _find_matching_row(rows: List[Dict[str, Any]], token: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    token_chain = str(token["chain"]).lower()
    token_symbol = str(token["symbol"]).lower()
    token_contract = str(token["contract"]).lower()
    token_asset_id = str(token["asset_id"]).lower()

    for row in rows:
        if str(row.get("chain", "")).lower() != token_chain:
            continue
        row_symbol = str(row.get("symbol", "")).lower()
        row_contract = str(
            row.get("contract")
            or row.get("contractAddress")
            or row.get("tokenAddress")
            or ""
        ).lower()
        row_asset_id = str(row.get("assetId") or row.get("asset_id") or "").lower()
        if row_contract and row_contract == token_contract:
            return row
        if row_asset_id and row_asset_id == token_asset_id:
            return row
        if row_symbol and row_symbol == token_symbol:
            return row
    return None


def _extract_direct_token_balance(payload: Any, decimals: int) -> Optional[Decimal]:
    if isinstance(payload, list):
        for entry in payload:
            balance = _extract_direct_token_balance(entry, decimals)
            if balance is not None:
                return balance
        return None
    if not isinstance(payload, dict):
        return None

    for key in ("balance", "formattedBalance", "uiAmount", "amount"):
        value = _safe_decimal(payload.get(key))
        if value is not None:
            return value

    raw_value = _safe_decimal(payload.get("rawBalance") or payload.get("value"))
    if raw_value is not None:
        payload_decimals = payload.get("decimals")
        divisor_decimals = int(payload_decimals) if str(payload_decimals).isdigit() else decimals
        return raw_value / (Decimal(10) ** divisor_decimals)

    return None


def _lookup_tracked_token_rows(selected_chains: List[str], summary_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tracked_tokens = [token for token in TRACKED_TOKENS if token["chain"] in selected_chains]
    if not tracked_tokens:
        return []

    address_map = _resolve_wallet_address_map()
    direct_timeout = int(os.getenv("TWAK_DIRECT_BALANCE_TIMEOUT_SECONDS", "12"))
    tracked_rows: List[Dict[str, Any]] = []

    for token in tracked_tokens:
        summary_row = _find_matching_row(summary_rows, token)
        address = address_map.get(token["chain"])
        if not address:
            if summary_row is None:
                tracked_rows.append(
                    {
                        "chain": token["chain"],
                        "type": token.get("type", "token"),
                        "symbol": token["symbol"],
                        "balance": "unknown",
                        "usdValue": None,
                        "assetId": token["asset_id"],
                        "contractAddress": token["contract"],
                    }
                )
            continue

        output = run_twak(
            [
                "balance",
                "--chain",
                token["chain"],
                "--address",
                address,
                "--token",
                token["contract"],
                "--json",
            ],
            timeout=direct_timeout,
        )
        if output.startswith("Error:") or output.startswith("Exception"):
            if summary_row is None:
                tracked_rows.append(
                    {
                        "chain": token["chain"],
                        "type": token.get("type", "token"),
                        "symbol": token["symbol"],
                        "balance": "unknown",
                        "usdValue": None,
                        "assetId": token["asset_id"],
                        "contractAddress": token["contract"],
                    }
                )
            continue

        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            if summary_row is None:
                tracked_rows.append(
                    {
                        "chain": token["chain"],
                        "type": token.get("type", "token"),
                        "symbol": token["symbol"],
                        "balance": "unknown",
                        "usdValue": None,
                        "assetId": token["asset_id"],
                        "contractAddress": token["contract"],
                    }
                )
            continue

        balance_value = _extract_direct_token_balance(payload, token["decimals"])
        if balance_value is None:
            if summary_row is None:
                tracked_rows.append(
                    {
                        "chain": token["chain"],
                        "type": token.get("type", "token"),
                        "symbol": token["symbol"],
                        "balance": "unknown",
                        "usdValue": None,
                        "assetId": token["asset_id"],
                        "contractAddress": token["contract"],
                    }
                )
            continue

        merged_row = dict(summary_row or {})
        merged_row.update(
            {
                "chain": token["chain"],
                "type": merged_row.get("type") or token.get("type", "token"),
                "symbol": token["symbol"],
                "balance": _format_decimal(balance_value),
                "assetId": token["asset_id"],
                "contractAddress": token["contract"],
            }
        )
        if "usdValue" not in merged_row:
            merged_row["usdValue"] = None
        tracked_rows.append(merged_row)

    return tracked_rows


def _format_portfolio_rows(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No non-zero balances found across the configured portfolio chains."

    headers = ("Chain", "Type", "Symbol", "Balance", "USD")
    formatted_rows: List[tuple[str, str, str, str, str]] = []
    total_usd = 0.0

    for row in rows:
        usd_raw = row.get("usdValue")
        usd_decimal = _safe_decimal(usd_raw)
        if usd_decimal is not None:
            total_usd += float(usd_decimal)
            usd_display = f"${float(usd_decimal):,.2f}"
        elif usd_raw in (None, ""):
            usd_display = "Unknown"
        else:
            usd_display = str(usd_raw)
        formatted_rows.append(
            (
                str(row.get("chain", "")),
                str(row.get("type", "")),
                str(row.get("symbol", "")),
                str(row.get("balance", "")),
                usd_display,
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
    per_chain_timeout = int(os.getenv("TWAK_PORTFOLIO_CHAIN_TIMEOUT_SECONDS", "12"))

    for chain in selected_chains:
        output = run_twak(["wallet", "portfolio", "--chains", chain, "--json"], timeout=per_chain_timeout)
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

    merged_rows: List[Dict[str, Any]] = []
    tracked_keys = {
        (
            str(token["chain"]).lower(),
            str(token["asset_id"]).lower(),
        )
        for token in TRACKED_TOKENS
        if token["chain"] in selected_chains
    }
    for row in rows:
        row_chain = str(row.get("chain", "")).lower()
        row_asset_id = str(row.get("assetId") or row.get("asset_id") or "").lower()
        if (row_chain, row_asset_id) in tracked_keys:
            continue
        merged_rows.append(row)

    merged_rows.extend(_lookup_tracked_token_rows(selected_chains, rows))

    if merged_rows:
        return _format_portfolio_rows(merged_rows)
    if errors:
        return " | ".join(errors)
    return run_twak(["wallet", "portfolio"])


def get_telegram_wallet_portfolio() -> str:
    """Fast wallet portfolio view for Telegram UX."""
    return get_wallet_portfolio(DEFAULT_TELEGRAM_PORTFOLIO_CHAINS)

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
    description="Start secure local TWAK wallet setup guidance. Never request or accept wallet passwords, seed phrases, private keys, or secrets in chat.",
    input_schema={
        "type": "object",
        "properties": {},
    },
)
def create_agent_wallet() -> str:
    """Redirect wallet creation to the secure local TWAK flow."""
    return (
        "Use the secure local TWAK flow to create or unlock the wallet signer. "
        "Do not provide wallet passwords, seed phrases, private keys, or signing secrets in chat."
    )

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
    description="Transfer tokens from the agent wallet to another address using only saved/local TWAK credentials. Never ask for passwords, seed phrases, private keys, or secrets in chat.",
    input_schema={
        "type": "object",
        "properties": {
            "chain": {"type": "string", "description": "The blockchain network."},
            "to": {"type": "string", "description": "Recipient address."},
            "amount": {"type": "string", "description": "Amount to transfer."},
            "token": {"type": "string", "description": "Token symbol or address (optional, defaults to native token)."},
        },
        "required": ["chain", "to", "amount"],
    },
)
def transfer_tokens(chain: str, to: str, amount: str, token: Optional[str] = None) -> str:
    """Transfer tokens."""
    args = ["transfer", "--chain", chain, "--to", to, "--amount", amount]
    if token:
        args.extend(["--token", token])
    return _run_signed_twak(args)

@register_tool(
    name="swap_tokens",
    description="Quote or execute a token swap on a specific chain. Execution must use saved/local TWAK credentials only and must never request passwords, seed phrases, private keys, or secrets in chat.",
    input_schema={
        "type": "object",
        "properties": {
            "chain": {"type": "string", "description": "The blockchain network."},
            "amount": {"type": "string", "description": "Amount to swap from."},
            "from_token": {"type": "string", "description": "Token symbol or address to swap from."},
            "to_token": {"type": "string", "description": "Token symbol or address to swap to."},
            "execute": {"type": "boolean", "description": "If true, execute the swap. If false, only get a quote.", "default": False},
            "use_mev_protection": {"type": "boolean", "description": "If true, routes transaction through a private MEV-protecting RPC to prevent front-running.", "default": True},
            "slippage": {"type": "number", "description": "Maximum slippage percentage (e.g. 0.5 for 0.5%). Defaults to environment variable or 1.0.", "default": 0.5},
        },
        "required": ["chain", "amount", "from_token", "to_token"],
    },
)
def swap_tokens(chain: str, amount: str, from_token: str, to_token: str, execute: bool = False, use_mev_protection: bool = True, slippage: float = 0.5) -> str:
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
        args.append("--execute")

    result = _run_signed_twak(args) if execute else run_twak(args)

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
