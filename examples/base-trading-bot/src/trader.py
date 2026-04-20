"""
Base Trading Bot - Main trading logic
"""
import logging
import time
from typing import Optional, List
from .client import DexScreenerClient, TokenInfo, PairData
from .oneinch import OneInchClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseTrader:
    """Base trading bot for executing trades on Base"""

    def __init__(self, config: dict):
        self.config = config
        self.dexscreener = DexScreenerClient(config.get('dexscreener', {}).get('api_key'))
        self.oneinch = OneInchClient(config.get('uniswap', {}).get('api_key'))

        # Token addresses
        self.usdc_address = config['trading']['usdc_address']
        self.weth_address = config['trading']['weth_address']

        # Trading parameters
        self.capital_usd = config['trading']['capital_usd']
        self.max_trade_size_usd = config['trading']['max_trade_size_usd']
        self.slippage_bps = config['trading']['slippage_bps']
        self.take_profit = config['strategy']['take_profit_percent']
        self.stop_loss = config['strategy']['stop_loss_percent']

        # Monitoring parameters
        self.price_refresh_interval = config['monitoring']['price_refresh_interval']
        self.min_liquidity = config['monitoring']['min_liquidity_usd']
        self.min_volume = config['monitoring']['min_volume_usd']

    def get_current_prices(self) -> Dict[str, float]:
        """Get current prices for main tokens"""
        try:
            # Get USDC price
            usdc_pair = self.dexscreener.get_pair_data(self.usdc_address)
            weth_price = None

            if usdc_pair and usdc_pair.quote_token.symbol.lower() == 'usdc':
                # USDC is the quote token
                weth_price = usdc_pair.price_usd
            elif usdc_pair and usdc_pair.base_token.symbol.lower() == 'usdc':
                # USDC is the base token
                weth_price = usdc_pair.price_usd

            return {
                'usdc': 1.0,  # USDC is pegged to USD
                'weth': weth_price or 0
            }
        except Exception as e:
            logger.error(f"Error getting prices: {e}")
            return {'usdc': 1.0, 'weth': 0}

    def should_trade(self, pair_data: PairData) -> bool:
        """Check if a pair meets trading criteria"""
        try:
            # Check liquidity
            if pair_data.liquidity_usd < self.min_liquidity:
                logger.debug(f"Low liquidity: {pair_data.liquidity_usd:.2f} < {self.min_liquidity}")
                return False

            # Check volume
            if pair_data.volume_24h < self.min_volume:
                logger.debug(f"Low volume: {pair_data.volume_24h:.2f} < {self.min_volume}")
                return False

            # Check price change (prefer stable pairs)
            if abs(pair_data.price_change_h24) > 5:
                logger.debug(f"High volatility: {pair_data.price_change_h24:.2f}%")
                return False

            return True
        except Exception as e:
            logger.error(f"Error checking trade criteria: {e}")
            return False

    def execute_swap(self, from_token: str, to_token: str, amount: float) -> Optional[dict]:
        """Execute a token swap"""
        try:
            logger.info(f"Executing swap: {amount} {from_token} -> {to_token}")

            # Get quote
            quote = self.oneinch.get_quote(from_token, to_token, amount)
            if not quote:
                logger.error("Failed to get quote")
                return None

            # Check slippage
            if quote.estimated_price_impact * 100 > self.slippage_bps:
                logger.warning(f"High slippage: {quote.estimated_price_impact * 100:.2f}%")

            # Get swap data
            swap_data = self.oneinch.get_swap_data(from_token, to_token, amount)
            if not swap_data:
                logger.error("Failed to get swap data")
                return None

            logger.info(f"Swap quote: {quote.to_amount_ether:.4f} {to_token}")
            logger.info(f"Gas estimate: {swap_data.estimated_gas}")

            return {
                'success': True,
                'quote': quote,
                'transaction': swap_data.transaction
            }

        except Exception as e:
            logger.error(f"Error executing swap: {e}")
            return None

    def monitor_market(self) -> List[PairData]:
        """Monitor market for trading opportunities"""
        try:
            logger.info("Monitoring market...")

            # Get WETH pairs
            weth_pairs = self.dexscreener.get_all_pairs_for_token(self.weth_address)

            # Filter by criteria
            valid_pairs = [p for p in weth_pairs if self.should_trade(p)]

            if not valid_pairs:
                logger.info("No valid pairs found")
                return []

            # Log top 3 pairs
            logger.info("\n=== Top Pairs ===")
            for i, pair in enumerate(valid_pairs[:3], 1):
                logger.info(f"{i}. {pair.base_token.symbol}/{pair.quote_token.symbol}")
                logger.info(f"   Price: ${pair.price_usd:.4f}")
                logger.info(f"   Liquidity: ${pair.liquidity_usd:,.2f}")
                logger.info(f"   Volume (24h): ${pair.volume_24h:,.2f}")
                logger.info(f"   Dex: {pair.dex_id}")

            return valid_pairs

        except Exception as e:
            logger.error(f"Error monitoring market: {e}")
            return []

    def run(self, wallet_address: str = None):
        """Main trading loop"""
        try:
            logger.info("=" * 60)
            logger.info("Base Trading Bot Started")
            logger.info("=" * 60)

            # Get prices
            prices = self.get_current_prices()
            logger.info(f"Current prices: USDC=${prices['usdc']:.2f}, WETH=${prices['weth']:.4f}")

            # Monitor market
            pairs = self.monitor_market()

            if pairs:
                logger.info(f"\nFound {len(pairs)} valid trading pairs")

                # Example trade: sell USDC for WETH
                trade_amount = min(self.max_trade_size_usd, self.capital_usd * 0.5)
                logger.info(f"\nExample trade: ${trade_amount:.2f} USDC -> WETH")

                result = self.execute_swap(self.usdc_address, self.weth_address, trade_amount)
                if result:
                    logger.info(f"✓ Swap prepared: {result['quote'].to_amount_ether:.4f} WETH")
                    logger.info(f"  To: {result['transaction']['to']}")
                    logger.info(f"  Gas: {result['transaction']['gas']}")
                else:
                    logger.error("✗ Swap failed")
            else:
                logger.info("No trading opportunities found")

            logger.info("\nBot session complete")

        except Exception as e:
            logger.error(f"Error running bot: {e}")


def main():
    """Main entry point"""
    import yaml

    try:
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)

        trader = BaseTrader(config)

        # For demo, run once and exit
        trader.run()

    except FileNotFoundError:
        logger.error("Config file not found")
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    main()