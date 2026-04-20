"""
1inch Client for swap execution on Base
"""
import requests
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Quote:
    dex_id: str
    price_impact: float
    gas_price: int
    estimated_price_impact: float
    estimated_gas_price: int
    estimated_price: float
    estimated_protocol_fee: float
    from_token_address: str
    to_token_address: str
    amount: float
    amount_in_ether: float
    to_amount: float
    to_amount_ether: float
    to_amount_min: float
    to_amount_min_ether: float
    route: List[Any]
    approve: Dict[str, Any]
    spender: str
    target: str
    chain_id: int
    function_data: str
    from_token_decimals: int
    to_token_decimals: int


@dataclass
class SwapData:
    quote: Quote
    transaction: Dict[str, Any]
    estimated_gas: int


class OneInchClient:
    """Client for interacting with 1inch API for swap execution"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()
        self.base_url = "https://api.1inch.dev/base"

    def get_quote(self, from_token: str, to_token: str, amount: float) -> Optional[Quote]:
        """Get a swap quote from 1inch"""
        try:
            url = f"{self.base_url}/quote"
            headers = {}
            if self.api_key:
                headers["Authorization"] = self.api_key

            params = {
                "src": from_token,
                "dst": to_token,
                "amount": str(int(amount * 10**18))
            }

            response = self.session.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return Quote(
                dex_id=data.get("dexId", ""),
                price_impact=float(data.get("priceImpact", 0)),
                gas_price=int(data.get("gasPrice", 0)),
                estimated_price_impact=float(data.get("estimatedPriceImpact", 0)),
                estimated_gas_price=int(data.get("estimatedGasPrice", 0)),
                estimated_price=float(data.get("estimatedPrice", 0)),
                estimated_protocol_fee=float(data.get("estimatedProtocolFee", 0)),
                from_token_address=data.get("fromTokenAddress", ""),
                to_token_address=data.get("toTokenAddress", ""),
                amount=float(data.get("amount", 0)),
                amount_in_ether=float(data.get("amountInEther", 0)),
                to_amount=float(data.get("toAmount", 0)),
                to_amount_ether=float(data.get("toAmountEther", 0)),
                to_amount_min=float(data.get("toAmountMin", 0)),
                to_amount_min_ether=float(data.get("toAmountMinEther", 0)),
                route=data.get("route", []),
                approve=data.get("approve", {}),
                spender=data.get("spender", ""),
                target=data.get("target", ""),
                chain_id=int(data.get("chainId", 0)),
                function_data=data.get("functionData", ""),
                from_token_decimals=int(data.get("fromTokenDecimals", 0)),
                to_token_decimals=int(data.get("toTokenDecimals", 0))
            )
        except Exception as e:
            logger.error(f"Error getting quote: {e}")
            return None

    def get_swap_data(self, from_token: str, to_token: str, amount: float) -> Optional[SwapData]:
        """Get complete swap data including transaction"""
        try:
            url = f"{self.base_url}/swap"
            headers = {}
            if self.api_key:
                headers["Authorization"] = self.api_key

            params = {
                "src": from_token,
                "dst": to_token,
                "amount": str(int(amount * 10**18))
            }

            response = self.session.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return SwapData(
                quote=self.get_quote(from_token, to_token, amount),
                transaction={
                    "to": data.get("to", ""),
                    "data": data.get("data", ""),
                    "value": str(data.get("value", 0)),
                    "gas": str(data.get("gas", 0))
                },
                estimated_gas=int(data.get("gas", 0))
            )
        except Exception as e:
            logger.error(f"Error getting swap data: {e}")
            return None

    def approve_token(self, token_address: str, spender: str, amount: float) -> Optional[Dict]:
        """Get approve transaction data"""
        try:
            url = f"{self.base_url}/approve"
            headers = {}
            if self.api_key:
                headers["Authorization"] = self.api_key

            params = {
                "token": token_address,
                "amount": str(int(amount * 10**18))
            }

            response = self.session.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error approving token: {e}")
            return None

    def get_user_balance(self, address: str, token_address: str) -> Optional[float]:
        """Get token balance for user"""
        try:
            url = f"{self.base_url}/balances/{address}"
            headers = {}
            if self.api_key:
                headers["Authorization"] = self.api_key

            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            balances = data.get("balances", {})
            for addr, balance in balances.items():
                if addr.lower() == token_address.lower():
                    return float(balance)

            return 0.0
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return None