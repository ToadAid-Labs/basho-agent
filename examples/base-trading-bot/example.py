#!/usr/bin/env python3
"""
Example usage of the Base Trading Bot
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import yaml
from trader import BaseTrader

# Load configuration
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Create trader instance
trader = BaseTrader(config)

# Run the bot
trader.run()