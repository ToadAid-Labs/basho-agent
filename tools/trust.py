"""
Trust Wallet API Client
Supports Base chain DEX trading via Trust Wallet Agent Skills

API Base: https://tws.trustwallet.com
Auth: HMAC-SHA256 with Access ID and HMAC Secret

Documentation: https://docs.trustwallet.org
"""

import os
import hmac
import hashlib
import requests
import subprocess
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv
import json
import logging

from core.tools import register_tool

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def _run_twak_market(args: List[str]) -> Optional[str]:
    """Run a Trust Wallet Agent Kit market-data command if the CLI is available."""
    try:
        result = subprocess.run(
            ["twak"] + args,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
            timeout=30,
        )
    except FileNotFoundError:
        return None
    except Exception as e:  # noqa: BLE001
        return f"[error] twak {type(e).__name__}: {e}"

    if result.returncode != 0:
        return f"[error] twak: {(result.stderr or result.stdout).strip()}"
    return result.stdout.strip()


def _rank_token_search_results(query: str, raw_result: Any) -> Any:
    """Rank exact symbol/name matches first for agent-friendly token search."""
    if not isinstance(raw_result, list):
        return raw_result

    needle = query.strip().lower()

    def rank(item: Any) -> tuple[int, str]:
        if not isinstance(item, dict):
            return (99, "")

        symbol = str(item.get("symbol", "")).lower()
        name = str(item.get("name", "")).lower()
        address = str(item.get("address", "")).lower()

        if symbol == needle:
            score = 0
        elif name == needle:
            score = 1
        elif address == needle:
            score = 2
        elif symbol.startswith(needle):
            score = 3
        elif needle in symbol:
            score = 4
        elif needle in name:
            score = 5
        else:
            score = 6

        return (score, symbol or name or address)

    return sorted(raw_result, key=rank)


def _native_price_search_result(query: str, chain: str) -> Optional[Dict[str, Any]]:
    """Return native token price data in search shape when twak price supports it."""
    twak_result = _run_twak_market(["price", query, "--chain", chain, "--json"])
    if not twak_result or twak_result.startswith("[error]"):
        return None

    try:
        price_data = json.loads(twak_result)
    except json.JSONDecodeError:
        return None

    token = str(price_data.get("token", "")).lower()
    if token != query.strip().lower():
        return None

    return {
        "name": price_data.get("name") or query.upper(),
        "symbol": price_data.get("token") or query.upper(),
        "chain": price_data.get("chain") or chain,
        "assetType": "native",
        "priceUsd": price_data.get("priceUsd"),
        "source": "twak price",
    }


def _prepend_native_result(query: str, chain: str, results: Any) -> Any:
    if not isinstance(results, list):
        return results

    native_result = _native_price_search_result(query, chain)
    if not native_result:
        return results

    native_symbol = str(native_result.get("symbol", "")).lower()
    has_exact_symbol = any(
        isinstance(item, dict) and str(item.get("symbol", "")).lower() == native_symbol
        for item in results
    )
    if has_exact_symbol:
        return results

    return [native_result] + results


class TrustWalletAPI:
    """Trust Wallet REST API client"""

    BASE_URL = "https://tws.trustwallet.com"

    def __init__(self):
        self.access_id = os.getenv("TWAK_ACCESS_ID")
        self.hmac_secret = os.getenv("TWAK_HMAC_SECRET")
        self.mock_mode = os.getenv("MOCK_API", "False").lower() == "true"

        if not self.mock_mode and (not self.access_id or not self.hmac_secret):
            logger.warning("TWAK_ACCESS_ID and TWAK_HMAC_SECRET not set. Falling back to mock mode.")
            self.mock_mode = True

        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def _generate_auth_headers(self, method: str, path: str, body: Optional[str] = None) -> Dict[str, str]:
        """Generate HMAC-SHA256 authentication headers"""
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if body:
            message = f"{method}|{path}|{timestamp}|{body}"
        else:
            message = f"{method}|{path}|{timestamp}|"

        signature = hmac.new(
            self.hmac_secret.encode('utf-8') if self.hmac_secret else b'',
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return {
            "X-TWAK-ACCESS-ID": self.access_id or "mock_id",
            "X-TWAK-TIMESTAMP": timestamp,
            "X-TWAK-SIGNATURE": signature
        }

    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, body: Optional[Dict] = None):
        """Make authenticated API request"""
        if self.mock_mode:
            return self._mock_request(method, endpoint, params, body)

        url = f"{self.BASE_URL}{endpoint}"
        path = endpoint
        full_url = url

        # Add query parameters if present
        if params:
            from urllib.parse import urlencode
            full_url = f"{url}?{urlencode(params)}"

        body_str = json.dumps(body) if body else None
        headers = self._generate_auth_headers(method, path, body_str)

        try:
            response = self.session.request(
                method=method,
                url=full_url,
                headers=headers,
                json=body,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"API endpoint not found: {full_url}. Using mock response.")
                return self._mock_request(method, endpoint, params, body)
            raise e

    def _mock_request(self, method: str, endpoint: str, params: Optional[Dict] = None, body: Optional[Dict] = None):
        """Provide mock data for development"""
        if "search" in endpoint:
            q = params.get("q", "").upper()
            return [{
                "symbol": q or "BTC",
                "name": f"{q or 'Bitcoin'} (Mock)",
                "address": "0x" + "0" * 40,
                "chain": params.get("chain", "base")
            }]
        elif "price" in endpoint:
            import random
            return {"price": random.uniform(10, 60000), "vs_currency": "usd"}
        elif "validate" in endpoint:
            return {"valid": True}
        elif "balances" in endpoint:
            return [{"symbol": "USDC", "balance": "1000.0"}, {"symbol": "ETH", "balance": "1.5"}]
        
        return {}

    def get_token_info(self, token_address: str, chain: str = "base") -> Dict[str, Any]:
        """Get token information by address"""
        return self._request("GET", f"/tokens/{token_address}", params={"chain": chain})

    def search_token(self, query: str, chain: str = "base") -> List[Dict[str, Any]]:
        """Search for tokens by name or symbol"""
        return self._request("GET", "/tokens/search", params={"q": query, "chain": chain})

    def get_price(self, token_address: str, vs_currency: str = "usd", chain: str = "base") -> Dict[str, Any]:
        """Get token price in USD"""
        return self._request(
            "GET",
            f"/tokens/{token_address}/price",
            params={"vs_currency": vs_currency, "chain": chain}
        )

    def get_prices_batch(self, token_addresses: List[str], vs_currency: str = "usd", chain: str = "base") -> Dict[str, Any]:
        """Get prices for multiple tokens at once"""
        return self._request(
            "POST",
            "/prices/batch",
            body={"addresses": token_addresses, "vs_currency": vs_currency, "chain": chain}
        )

    def get_swap_quote(
        self,
        from_token: str,
        to_token: str,
        amount: str,
        chain: str = "base"
    ) -> Dict[str, Any]:
        """Get swap quote for DEX routing"""
        return self._request(
            "POST",
            "/swap/quote",
            body={
                "from": from_token,
                "to": to_token,
                "amount": amount,
                "chain": chain
            }
        )

    def get_market_data(
        self,
        chain: str = "base",
        limit: int = 10,
        sort_by: str = "market_cap"
    ) -> List[Dict[str, Any]]:
        """Get trending or top tokens by market data"""
        return self._request(
            "GET",
            "/market/trending",
            params={"chain": chain, "limit": limit, "sort_by": sort_by}
        )

    def check_token_security(
        self,
        token_address: str,
        chain: str = "base"
    ) -> Dict[str, Any]:
        """Check token security (honeypot, rug check, etc.)"""
        return self._request(
            "GET",
            f"/tokens/{token_address}/security",
            params={"chain": chain}
        )

    def validate_address(
        self,
        address: str,
        chain: str = "base"
    ) -> Dict[str, Any]:
        """Validate blockchain address format"""
        return self._request(
            "GET",
            "/address/validate",
            params={"address": address, "chain": chain}
        )

    def get_token_balances(
        self,
        address: str,
        chain: str = "base"
    ) -> List[Dict[str, Any]]:
        """Get token balances for a wallet address"""
        return self._request(
            "GET",
            "/wallet/balances",
            params={"address": address, "chain": chain}
        )

    def get_token_holders(
        self,
        token_address: str,
        chain: str = "base",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get top token holders"""
        return self._request(
            "GET",
            f"/tokens/{token_address}/holders",
            params={"chain": chain, "limit": limit}
        )


# Convenience functions for trading agent use

def get_token_price(token_symbol: str, chain: str = "base") -> float:
    """Quick helper to get token price"""
    try:
        api = TrustWalletAPI()
        # First try to search for the token
        results = api.search_token(token_symbol, chain)
        if results:
            token_address = results[0].get('address')
            if token_address:
                price_data = api.get_price(token_address, vs_currency="usd", chain=chain)
                return float(price_data.get('price', 0))
    except Exception as e:
        print(f"Error getting price for {token_symbol}: {e}")
    return 0.0


@register_tool(
    name="trust_search_token",
    description="Search Trust Wallet market data for a token by symbol, name, or address.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Token symbol, name, or address to search for, e.g. ETH, USDC, PEPE.",
            },
            "chain": {
                "type": "string",
                "description": "Blockchain network, e.g. ethereum, base, solana. Defaults to ethereum.",
                "default": "ethereum",
            },
        },
        "required": ["query"],
    },
)
def trust_search_token(query: str, chain: str = "ethereum") -> str:
    """Search for tokens through the Trust Wallet API."""
    twak_result = _run_twak_market(["search", query, "--networks", chain, "--limit", "10", "--json"])
    if twak_result:
        try:
            ranked = _rank_token_search_results(query, json.loads(twak_result))
            ranked = _prepend_native_result(query, chain, ranked)
            return json.dumps(ranked, indent=2)
        except json.JSONDecodeError:
            return twak_result

    try:
        api = TrustWalletAPI()
        ranked = _rank_token_search_results(query, api.search_token(query, chain))
        ranked = _prepend_native_result(query, chain, ranked)
        return json.dumps(ranked, indent=2)
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"


@register_tool(
    name="trust_get_token_price",
    description="Get a token price from the Trust Wallet API. Use token_address when available, or token_symbol to search first.",
    input_schema={
        "type": "object",
        "properties": {
            "token_symbol": {
                "type": "string",
                "description": "Token symbol to search first, e.g. ETH or USDC.",
            },
            "token_address": {
                "type": "string",
                "description": "Token contract address or Trust Wallet asset identifier.",
            },
            "chain": {
                "type": "string",
                "description": "Blockchain network, e.g. ethereum, base, solana. Defaults to ethereum.",
                "default": "ethereum",
            },
            "vs_currency": {
                "type": "string",
                "description": "Quote currency. Defaults to usd.",
                "default": "usd",
            },
        },
    },
)
def trust_get_token_price(
    token_symbol: Optional[str] = None,
    token_address: Optional[str] = None,
    chain: str = "ethereum",
    vs_currency: str = "usd",
) -> str:
    """Get current token price through the Trust Wallet API."""
    token = token_address or token_symbol
    if token:
        twak_args = ["price", token, "--chain", chain, "--json"]
        twak_result = _run_twak_market(twak_args)
        if twak_result:
            return twak_result

    try:
        api = TrustWalletAPI()
        address = token_address
        search_result = None
        if not address and token_symbol:
            results = api.search_token(token_symbol, chain)
            search_result = results[0] if results else None
            address = search_result.get("address") if search_result else None

        if not address:
            return "[error] Provide token_address or a token_symbol that Trust Wallet can find."

        price_data = api.get_price(address, vs_currency=vs_currency, chain=chain)
        result = {
            "symbol": token_symbol,
            "chain": chain,
            "token_address": address,
            "price": price_data.get("price") if isinstance(price_data, dict) else None,
            "vs_currency": vs_currency,
            "raw": price_data,
        }
        if search_result:
            result["matched_token"] = search_result
        return json.dumps(result, indent=2)
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"


@register_tool(
    name="trust_get_swap_quote",
    description="Get a swap quote from the Trust Wallet API without executing a trade.",
    input_schema={
        "type": "object",
        "properties": {
            "from_token": {"type": "string", "description": "Source token symbol, address, or asset identifier."},
            "to_token": {"type": "string", "description": "Destination token symbol, address, or asset identifier."},
            "amount": {"type": "string", "description": "Amount of source token to quote."},
            "chain": {
                "type": "string",
                "description": "Blockchain network, e.g. ethereum, base, solana. Defaults to ethereum.",
                "default": "ethereum",
            },
        },
        "required": ["from_token", "to_token", "amount"],
    },
)
def trust_get_swap_quote(from_token: str, to_token: str, amount: str, chain: str = "ethereum") -> str:
    """Get a Trust Wallet swap quote."""
    twak_result = _run_twak_market(
        ["swap", amount, from_token, to_token, "--chain", chain, "--quote-only", "--json"]
    )
    if twak_result:
        return twak_result

    try:
        api = TrustWalletAPI()
        return json.dumps(api.get_swap_quote(from_token, to_token, amount, chain), indent=2)
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"


def get_swap_quote_safe(from_token: str, to_token: str, amount: str, chain: str = "base") -> Optional[Dict]:
    """Get swap quote with error handling"""
    try:
        api = TrustWalletAPI()
        return api.get_swap_quote(from_token, to_token, amount, chain)
    except Exception as e:
        print(f"Error getting swap quote: {e}")
        return None


def check_token_security_safe(token_address: str, chain: str = "base") -> Optional[Dict]:
    """Check token security with error handling"""
    try:
        api = TrustWalletAPI()
        return api.check_token_security(token_address, chain)
    except Exception as e:
        print(f"Error checking token security: {e}")
        return None
# Add this at the end of the file
TrustWalletAgent = TrustWalletAPI
