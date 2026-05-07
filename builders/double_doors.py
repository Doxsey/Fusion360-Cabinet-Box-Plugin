"""Double-door builder: two frame-and-panel doors sized from a cabinet opening.

Inputs are the cabinet opening width and height. Each door overlays the
face frame by 1/2" on its top, bottom, and outer side; a 1/8" gap sits
between the two doors, centred on the opening. Each door is built with
lib.frame_panel.build_frame_panel and placed inside a wrapper component.
"""

import adsk.core
import adsk.fusion

from lib.frame_panel import build_frame_panel
from lib.units import IN_TO_CM, inches

KEY = "double_doors"
DISPLAY_NAME = "Double Doors"
GROUP_ID = "double_doors_group"

FRAME_WIDTH_IN     = 2.5
FRAME_THICKNESS_IN = 0.75
PANEL_THICKNESS_IN = 0.5
PANEL_OFFSET_IN    = 0.25
GROOVE_DEPTH_IN    = 0.375
GROOVE_WIDTH_IN    = 0.25

OVERLAY_IN = 0.5
GAP_IN     = 0.125

DEFAULTS = {
    "OpeningWidth":  30.0,
    "OpeningHeight": 24.0,
}


def _in_value(val_in: float) -> adsk.core.ValueInput:
    return adsk.core.ValueInput.createByReal(inches(val_in))


def define_inputs(inputs: adsk.core.CommandInputs) -> adsk.core.GroupCommandInput:
    group = inputs.addGroupCommandInput(GROUP_ID, DISPLAY_NAME)
    group.isExpanded = True
    ci = group.children

    ci.addValueInput("dd_opening_width",  "Opening Width",  "in", _in_value(DEFAULTS["OpeningWidth"]))
    ci.addValueInput("dd_opening_height", "Opening Height", "in", _in_value(DEFAULTS["OpeningHeight"]))

    return group


def _collect_values(cmd_inputs: adsk.core.CommandInputs) -> dict:
    def _val_in(id_: str) -> float:
        return cmd_inputs.itemById(id_).value / IN_TO_CM

    return {
        "OpeningWidth":  _val_in("dd_opening_width"),
        "OpeningHeight": _val_in("dd_opening_height"),
    }


def build(design: adsk.fusion.Design, cmd_inputs: adsk.core.CommandInputs, ui: adsk.core.UserInterface) -> None:
    vals = _collect_values(cmd_inputs)
    opening_w = vals["OpeningWidth"]
    opening_h = vals["OpeningHeight"]

    # Each door: half the opening + outer overlay - half the gap.
    door_w = (opening_w + 2 * OVERLAY_IN - GAP_IN) / 2
    door_h = opening_h + 2 * OVERLAY_IN

    min_dim = 2 * FRAME_WIDTH_IN
    if door_w <= min_dim:
        ui.messageBox(
            f'Each door width ({door_w:.3g}") must be greater than 2× frame width ({min_dim}").\n'
            f'Increase the opening width.',
            DISPLAY_NAME,
        )
        return
    if door_h <= min_dim:
        ui.messageBox(
            f'Each door height ({door_h:.3g}") must be greater than 2× frame width ({min_dim}").\n'
            f'Increase the opening height.',
            DISPLAY_NAME,
        )
        return

    root = design.rootComponent
    wrapper_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    wrapper = wrapper_occ.component
    wrapper.name = f"DoubleDoors_{opening_w:.4g}x{opening_h:.4g}"

    common = dict(
        width_in=door_w,
        height_in=door_h,
        frame_width_in=FRAME_WIDTH_IN,
        frame_thickness_in=FRAME_THICKNESS_IN,
        panel_thickness_in=PANEL_THICKNESS_IN,
        panel_offset_in=PANEL_OFFSET_IN,
        groove_depth_in=GROOVE_DEPTH_IN,
        groove_width_in=GROOVE_WIDTH_IN,
    )

    build_frame_panel(wrapper, component_name="Left Door", **common)

    right_xform = adsk.core.Matrix3D.create()
    right_xform.translation = adsk.core.Vector3D.create(inches(door_w + GAP_IN), 0, 0)
    build_frame_panel(
        wrapper,
        component_name="Right Door",
        placement_transform=right_xform,
        **common,
    )
