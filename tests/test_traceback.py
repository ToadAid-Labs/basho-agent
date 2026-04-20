import traceback
from tools.trading_control import calculate_kelly_risk

try:
    print(calculate_kelly_risk(0.6, 2.0))
except Exception as e:
    traceback.print_exc()
