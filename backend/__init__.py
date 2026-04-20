"""
Price Action Analysis Module

This module provides tools for analyzing cryptocurrency price movements
without relying on technical indicators.
"""

from backend.pattern_recognition import (
    CandlestickPatterns,
    TrendPatterns,
    VolumePatterns,
    MarketPatternDetector
)

from backend.price_action import (
    PriceActionAnalyzer,
    PriceActionStrategy
)

__version__ = "1.0.0"
__all__ = [
    'CandlestickPatterns',
    'TrendPatterns',
    'VolumePatterns',
    'MarketPatternDetector',
    'PriceActionAnalyzer',
    'PriceActionStrategy'
]