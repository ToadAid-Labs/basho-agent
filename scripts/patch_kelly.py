import re

with open('risk_management.py', 'r') as f:
    content = f.read()

kelly_method = """    def calculate_kelly_position_size(
        self,
        confidence: float,
        risk_reward_ratio: Optional[float] = None,
        max_kelly_fraction: float = 0.5
    ) -> float:
        \"\"\"
        Calculate the optimal portfolio fraction to risk using the Kelly Criterion.
        
        f* = p - (q / b)
        
        Args:
            confidence: Win probability (0.0 to 1.0)
            risk_reward_ratio: Win size / Loss size (b in the formula). If None, uses config.min_risk_reward_ratio.
            max_kelly_fraction: Safety multiplier (often 0.5 for 'Half-Kelly')
            
        Returns:
            The percentage of the total portfolio to risk on this trade.
        \"\"\"
        p = confidence
        q = 1.0 - p
        b = risk_reward_ratio if risk_reward_ratio else self.config.min_risk_reward_ratio
        
        if b <= 0:
            return 0.0
            
        kelly_fraction = p - (q / b)
        
        if kelly_fraction <= 0:
            return 0.0
            
        # Apply fractional Kelly for safety
        adjusted_kelly = kelly_fraction * max_kelly_fraction
        
        # Cap at the max risk per trade defined in the risk config (can be overridden by aggressive settings)
        # But we still enforce absolute max limits. Let's use max_position_size_pct as hard cap.
        max_risk = self.config.max_position_size_pct / 100.0
        final_risk_fraction = min(adjusted_kelly, max_risk)
        
        # If confidence is high, maybe allow up to max_position_size, but normally cap to risk_per_trade
        # Let's use max_risk as the risk_per_trade_pct normally, but since Kelly is dynamic, 
        # we can allow it to go higher up to max_position_size_pct.
        
        return final_risk_fraction * 100.0  # Return as percentage

"""

if "def calculate_kelly_position_size" not in content:
    new_content = content.replace(
        "    def calculate_position_size(",
        kelly_method + "    def calculate_position_size("
    )
    with open('risk_management.py', 'w') as f:
        f.write(new_content)
    print("Kelly criterion method added to risk_management.py")
else:
    print("Kelly criterion method already exists.")
