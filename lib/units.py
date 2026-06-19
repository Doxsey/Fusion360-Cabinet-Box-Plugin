"""Unit conversion constants and helpers.

Fusion 360's internal unit is centimetres, so every length we pass to the
API must be in cm. The rest of this project prefers to reason in inches.
"""

IN_TO_CM = 2.54
MM_TO_IN = 1.0 / 25.4


def inches(val: float) -> float:
    """Convert inches to centimetres for Fusion API calls."""
    return val * IN_TO_CM


def mm(val: float) -> float:
    """Convert millimetres to centimetres for Fusion API calls."""
    return val * 0.1
