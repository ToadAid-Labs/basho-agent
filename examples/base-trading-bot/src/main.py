#!/usr/bin/env python3
"""
Base Trading Bot - Main Entry Point
"""
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trader import BaseTrader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the trading bot"""
    try:
        import yaml

        # Load configuration
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)

        # Create trader instance
        trader = BaseTrader(config)

        # Run bot
        trader.run()

        return 0

    except FileNotFoundError:
        logger.error("Config file not found: config/config.yaml")
        return 1
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())