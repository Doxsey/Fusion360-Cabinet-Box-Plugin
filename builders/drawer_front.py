"""Drawer front builder: 2 stiles + 2 rails + recessed centre panel.

Shares its construction with doors via lib.frame_panel.build_frame_panel.
"""

import adsk.core
import adsk.fusion

from lib.frame_panel import build_frame_panel
from lib.units import IN_TO_CM, inches

KEY = "drawer_front"
DISPLAY_NAME = "Drawer Front"
GROUP_ID = "drawer_front_group"

FRAME_WIDTH_IN     = 2.5
FRAME_THICKNESS_IN = 0.75
PANEL_THICKNESS_IN = 0.5
PANEL_OFFSET_IN    = 0.25

DEFAULTS = {
    "Width":  24.0,
    "Height": 6.0,
}


def _in_value(val_in: float) -> adsk.core.ValueInput:
    return adsk.core.ValueInput.createByReal(inches(val_in))


def define_inputs(inputs: adsk.core.CommandInputs) -> adsk.core.GroupCommandInput:
    group = inputs.addGroupCommandInput(GROUP_ID, DISPLAY_NAME)
    group.isExpanded = True
    ci = group.children

    ci.addValueInput("df_width",  "Width",  "in", _in_value(DEFAULTS["Width"]))
    ci.addValueInput("df_height", "Height", "in", _in_value(DEFAULTS["Height"]))

    return group


def _collect_values(cmd_inputs: adsk.core.CommandInputs) -> dict:
    def _val_in(id_: str) -> float:
        return cmd_inputs.itemById(id_).value / IN_TO_CM

    return {
        "Width":  _val_in("df_width"),
        "Height": _val_in("df_height"),
    }


def build(design: adsk.fusion.Design, cmd_inputs: adsk.core.CommandInputs, ui: adsk.core.UserInterface) -> None:
    vals = _collect_values(cmd_inputs)

    min_dim = 2 * FRAME_WIDTH_IN
    if vals["Width"] <= min_dim:
        ui.messageBox(
            f'Width must be greater than 2× frame width ({min_dim}").',
            DISPLAY_NAME,
        )
        return
    if vals["Height"] <= min_dim:
        ui.messageBox(
            f'Height must be greater than 2× frame width ({min_dim}").',
            DISPLAY_NAME,
        )
        return

    comp_name = f"DrawerFront_{vals['Width']:.4g}x{vals['Height']:.4g}"

    build_frame_panel(
        design.rootComponent,
        width_in=vals["Width"],
        height_in=vals["Height"],
        component_name=comp_name,
        frame_width_in=FRAME_WIDTH_IN,
        frame_thickness_in=FRAME_THICKNESS_IN,
        panel_thickness_in=PANEL_THICKNESS_IN,
        panel_offset_in=PANEL_OFFSET_IN,
    )
