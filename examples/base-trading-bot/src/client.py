"""
DexScreener Client for fetching token prices and pair data
"""
import requests
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    symbol: str
    name: str
    address: str
    decimals: int = 18


@dataclass
class PairData:
    chain_id: str
    dex_id: str
    pair_address: str
    base_token: TokenInfo
    quote_token: TokenInfo
    price_usd: float
    liquidity_usd: float
    volume_24h: float
    price_change_h24: float
    txns_24h: Dict[str, int]
    pair_created_at: int


class DexScreenerClient:
    """Client for interacting with DexScreener API"""

    BASE_URL = "https://api.dexscreener.com/latest"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()

    def get_token_info(self, address: str) -> Optional[TokenInfo]:
        """Get basic token information from a token address"""
        try:
            # Get pairs for the token
            url = f"{self.BASE_URL}/dex/tokens/{address}"
            params = {} if not self.api_key else {"apiKey": self.api_key}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Extract token info from first pair
            pairs = data.get("pairs", [])
            if not pairs:
                return None

            first_pair = pairs[0]
            base = first_pair.get("baseToken", {})
            quote = first_pair.get("quoteToken", {})

            return TokenInfo(
                symbol=base.get("symbol", ""),
                name=base.get("name", ""),
                address=base.get("address", address),
                decimals=base.get("decimals", 18)
            )
        except Exception as e:
            logger.error(f"Error getting token info: {e}")
            return None

    def get_pair_data(self, address: str) -> Optional[PairData]:
        """Get pair data for a specific token"""
        try:
            url = f"{self.BASE_URL}/dex/tokens/{address}"
            params = {} if not self.api_key else {"apiKey": self.api_key}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            pairs = data.get("pairs", [])
            if not pairs:
                return None

            # Find the best liquidity pair
            best_pair = None
            min_price = float('inf')

            for pair in pairs:
                # Prefer stablecoin pairs (low volatility)
                base_symbol = pair.get("baseToken", {}).get("symbol", "").lower()
                quote_symbol = pair.get("quoteToken", {}).get("symbol", "").lower()

                # Prefer pairs with high liquidity
                liquidity = pair.get("liquidity", {}).get("usd", 0)
                volume_24h = pair.get("volume", {}).get("h24", 0)

                if liquidity < 1000:  # Skip low liquidity pairs
                    continue

                price = float(pair.get("priceUsd", 0))

                if price < min_price:
                    min_price = price
                    best_pair = pair

            if not best_pair:
                return None

            base = best_pair.get("baseToken", {})
            quote = best_pair.get("quoteToken", {})

            return PairData(
                chain_id=best_pair.get("chainId", ""),
                dex_id=best_pair.get("dexId", ""),
                pair_address=best_pair.get("pairAddress", ""),
                base_token=TokenInfo(
                    symbol=base.get("symbol", ""),
                    name=base.get("name", ""),
                    address=base.get("address", address)
                ),
                quote_token=TokenInfo(
                    symbol=quote.get("symbol", ""),
                    name=quote.get("name", ""),
                    address=quote.get("address", "")
                ),
                price_usd=float(best_pair.get("priceUsd", 0)),
                liquidity_usd=float(best_pair.get("liquidity", {}).get("usd", 0)),
                volume_24h=float(best_pair.get("volume", {}).get("h24", 0)),
                price_change_h24=float(best_pair.get("priceChange", {}).get("h24", 0)),
                txns_24h=best_pair.get("txns", {}).get("h24", {}),
                pair_created_at=best_pair.get("pairCreatedAt", 0)
            )
        except Exception as e:
            logger.error(f"Error getting pair data: {e}")
            return None

    def get_all_pairs_for_token(self, address: str) -> List[PairData]:
        """Get all pairs for a specific token"""
        pairs = []
        try:
            url = f"{self.BASE_URL}/dex/tokens/{address}"
            params = {} if not self.api_key else {"apiKey": self.api_key}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            for pair in data.get("pairs", []):
                base = pair.get("baseToken", {})
                quote = pair.get("quoteToken", {})

                pairs.append(PairData(
                    chain_id=pair.get("chainId", ""),
                    dex_id=pair.get("dexId", ""),
                    pair_address=pair.get("pairAddress", ""),
                    base_token=TokenInfo(
                        symbol=base.get("symbol", ""),
                        name=base.get("name", ""),
                        address=base.get("address", address)
                    ),
                    quote_token=TokenInfo(
                        symbol=quote.get("symbol", ""),
                        name=quote.get("name", ""),
                        address=quote.get("address", "")
                    ),
                    price_usd=float(pair.get("priceUsd", 0)),
                    liquidity_usd=float(pair.get("liquidity", {}).get("usd", 0)),
                    volume_24h=float(pair.get("volume", {}).get("h24", 0)),
                    price_change_h24=float(pair.get("priceChange", {}).get("h24", 0)),
                    txns_24h=pair.get("txns", {}).get("h24", {}),
                    pair_created_at=pair.get("pairCreatedAt", 0)
                ))

            # Sort by liquidity (highest first)
            pairs.sort(key=lambda x: x.liquidity_usd, reverse=True)

        except Exception as e:
            logger.error(f"Error getting all pairs: {e}")

        return pairs