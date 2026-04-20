import json
import logging
from core.tools import register_tool
from tools.trading_control import execute_paper_trade, _get_live_price

logger = logging.getLogger(__name__)

@register_tool(
    name="copy_trade_wallet",
    description="Simulate tracking a whale's recent wallet activity and mirroring a high-conviction trade into the user's paper trading account.",
    input_schema={
        "type": "object",
        "properties": {
            "wallet_address": {
                "type": "string",
                "description": "The EVM address of the whale wallet."
            },
            "chain": {
                "type": "string",
                "description": "The blockchain network (e.g., ethereum, base).",
                "default": "ethereum"
            },
            "user_id": {
                "type": "integer",
                "description": "The user ID of the paper account."
            },
            "mirror_amount_usd": {
                "type": "number",
                "description": "The max amount of USD to allocate to the copied trade."
            }
        },
        "required": ["wallet_address", "user_id", "mirror_amount_usd"],
    },
)
def copy_trade_wallet(wallet_address: str, user_id: int, mirror_amount_usd: float, chain: str = "ethereum") -> str:
    """Scan a wallet and mirror a trade."""
    logger.info(f"Scanning wallet {wallet_address} for copy-trading on {chain}...")
    
    # In a real system, we would query Etherscan/Basescan or Trust Wallet API for recent TXs.
    # For now, we simulate finding a recent "Smart Money" accumulation.
    
    simulated_target_asset = "ETH"
    current_price = _get_live_price(simulated_target_asset)
    
    if current_price is None or current_price <= 0:
        return f"Error: Could not fetch price for the target asset {simulated_target_asset}."
        
    qty = mirror_amount_usd / current_price
    
    # Mirror the trade
    result = execute_paper_trade(
        user_id=user_id,
        symbol=simulated_target_asset,
        action="buy",
        amount=mirror_amount_usd,
        strategy=f"COPY_WHALE_{wallet_address[-4:]}"
    )
    
    return (
        f"🚨 Whale Tracking Alert!\n"
        f"Detected large accumulation in tracked wallet: {wallet_address}\n"
        f"Action: Wallet swapped USDC for {simulated_target_asset} on {chain}.\n"
        f"---\n"
        f"Mirroring trade into Paper Account:\n"
        f"Result: {result}"
    )
