import json
import logging
from typing import List, Dict, Any, Optional
from core.tools import register_tool
from monitoring.backtesting import Backtester
from tools.backtest_tool import PricePredictionStrategy, generate_mock_ohlcv

logger = logging.getLogger(__name__)

@register_tool(
    name="optimize_strategy_parameters",
    description="Run a grid search optimization to find the best BUY/SELL threshold and risk parameters for the current model. Tests multiple configurations and identifies the one with the highest total return.",
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Symbol to optimize for."},
            "threshold_range": {
                "type": "array", 
                "items": {"type": "number"},
                "description": "List of thresholds to test, e.g., [0.01, 0.02, 0.03].",
                "default": [0.01, 0.02, 0.03, 0.05]
            },
            "days": {"type": "integer", "description": "Number of days for backtesting.", "default": 60}
        },
        "required": ["symbol"],
    },
)
def optimize_strategy_parameters(symbol: str, threshold_range: List[float] = [0.01, 0.02, 0.03, 0.05], days: int = 60) -> str:
    """Run optimization grid search."""
    try:
        logger.info(f"Optimizing parameters for {symbol} over {days} days...")
        data = generate_mock_ohlcv(days=days)
        backtester = Backtester()
        
        results = []
        for threshold in threshold_range:
            strategy = PricePredictionStrategy(threshold=threshold)
            res = backtester.backtest_strategy(strategy, data)
            results.append({
                "threshold": threshold,
                "return_pct": res.total_return,
                "win_rate": res.win_rate,
                "max_drawdown": res.max_drawdown,
                "trades": res.total_trades
            })
            
        # Find best by return
        best = max(results, key=lambda x: x["return_pct"])
        
        output = [
            f"📈 Parameter Optimization Results for {symbol.upper()}",
            f"Tested {len(results)} configurations over {days} days of data.",
            f"--------------------------------------------------",
            f"WINNING CONFIGURATION:",
            f"Threshold: {best['threshold']*100}%",
            f"Total Return: {best['return_pct']:.2f}%",
            f"Win Rate: {best['win_rate']:.2f}%",
            f"Max Drawdown: {best['max_drawdown']:.2f}%",
            f"Total Trades: {best['trades']}",
            f"--------------------------------------------------",
            f"Full Grid Summary:"
        ]
        
        for r in results:
            output.append(f"T: {r['threshold']*100}% -> Ret: {r['return_pct']:.2f}%, WR: {r['win_rate']:.2f}%")
            
        output.append(f"\nRecommendation: Update your {symbol.lower()}_strategy.md with a {best['threshold']*100}% threshold for optimal performance.")
        
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        return f"Error optimizing strategy: {e}"
