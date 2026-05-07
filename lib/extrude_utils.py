"""Extrude helpers shared by all builders."""

import adsk.core
import adsk.fusion


def extrude_profile(
    extrudes: adsk.fusion.ExtrudeFeatures,
    profile: adsk.fusion.Profile,
    depth_cm: float,
    operation: adsk.fusion.FeatureOperations = adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    target_bodies=None,
) -> adsk.fusion.ExtrudeFeature:
    """Extrude a profile by depth_cm along +Z. Returns the feature."""
    ext_input = extrudes.createInput(profile, operation)
    ext_input.setDistanceExtent(
        False,
        adsk.core.ValueInput.createByReal(depth_cm),
    )
    if target_bodies:
        ext_input.participantBodies = target_bodies
    return extrudes.add(ext_input)
