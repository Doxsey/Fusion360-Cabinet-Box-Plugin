"""User parameter helpers."""

import adsk.core
import adsk.fusion

from lib.units import inches


def add_or_update_param(
    params: adsk.fusion.UserParameters,
    name: str,
    value_in: float,
    unit: str,
    comment: str,
) -> adsk.fusion.UserParameter:
    """Create or overwrite a user parameter (value in inches, stored as cm)."""
    existing = params.itemByName(name)
    val_input = adsk.core.ValueInput.createByReal(inches(value_in))
    if existing:
        existing.value = inches(value_in)
        return existing
    return params.add(name, val_input, unit, comment)
