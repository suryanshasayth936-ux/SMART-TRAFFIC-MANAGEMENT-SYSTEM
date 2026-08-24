"""
System-wide configuration, baseline timings, and algorithm parameters.
"""

from typing import List, Tuple

# Timing constants (in seconds)
MIN_GREEN_TIME: int = 10
MAX_GREEN_TIME: int = 90
DEFAULT_BASE_GREEN: int = 20

# Occupancy calculation parameters
# Linear curve calibrated to: 30% occupancy = 20s, 80% occupancy = 60s
# Slope = (60 - 20) / (80 - 30) = 0.8
# Intercept = 20 - (0.8 * 30) = -4.0
TIMER_SLOPE: float = 0.8
TIMER_INTERCEPT: float = -4.0

# Network balancing parameters
HIGH_CONGESTION_THRESHOLD: float = 75.0  # Percentage (> 75%)
DOWNSTREAM_BOOST_MULTIPLIER: float = 1.20  # +20% boost

# Emergency Override parameters
EMERGENCY_GREEN_TIME: int = 90  # Force maximum green wave

# Default Road ROI Polygon (normalized coordinates [0.0 - 1.0])
DEFAULT_ROI_NORMALIZED: List[Tuple[float, float]] = [
    (0.15, 0.95),  # Bottom-left
    (0.85, 0.95),  # Bottom-right
    (0.65, 0.10),  # Top-right
    (0.35, 0.10),  # Top-left
]
