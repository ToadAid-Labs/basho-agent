import re

with open('tools/trading_control.py', 'r') as f:
    content = f.read()

kelly_tool = """
@register_tool(
    name="calculate_kelly_risk",
    description="Calculate the optimal portfolio fraction to risk on a trade using the Kelly Criterion based on your confidence score.",
    input_schema={
        "type": "object",
        "properties": {
            "confidence": {
                "type": "number",
                "description": "Win probability of the trade (from 0.0 to 1.0, e.g. 0.8 for 80% confident)."
            },
            "risk_reward_ratio": {
                "type": "number",
                "description": "The ratio of expected profit to expected loss (e.g., 2.0). If omitted, defaults to 1.5."
            }
        },
        "required": ["confidence"],
    },
)
def calculate_kelly_risk(confidence: float, risk_reward_ratio: float = 1.5) -> str:
    \"\"\"Calculate position size using the Kelly Criterion.\"\"\"
    from risk_management import RiskManager, RiskConfig
    try:
        # We can just create a temporary risk manager to do the math
        risk_manager = RiskManager(trust_wallet=None, market_analyzer=None)
        
        # Override default to show math
        kelly_pct = risk_manager.calculate_kelly_position_size(
            confidence=confidence,
            risk_reward_ratio=risk_reward_ratio,
            max_kelly_fraction=0.5 # Half Kelly
        )
        
        full_kelly_pct = risk_manager.calculate_kelly_position_size(
            confidence=confidence,
            risk_reward_ratio=risk_reward_ratio,
            max_kelly_fraction=1.0 # Full Kelly
        )
        
        return (
            f"Kelly Criterion Position Sizer:\\n"
            f"- Confidence: {confidence*100:.1f}%\\n"
            f"- Risk/Reward Ratio: {risk_reward_ratio}\\n"
            f"- Full Kelly Suggestion: Risk {full_kelly_pct:.2f}% of portfolio\\n"
            f"- Half Kelly Suggestion (Recommended): Risk {kelly_pct:.2f}% of portfolio\\n\\n"
            f"Result: You should risk {kelly_pct:.2f}% of your current balance on this trade to mathematically maximize long-term growth."
        )
    except Exception as e:
        return f"Error calculating Kelly criterion: {e}"
"""

if "def calculate_kelly_risk" not in content:
    content += kelly_tool
    with open('tools/trading_control.py', 'w') as f:
        f.write(content)
    print("Kelly criterion tool added to trading_control.py")
else:
    print("Kelly criterion tool already exists.")
