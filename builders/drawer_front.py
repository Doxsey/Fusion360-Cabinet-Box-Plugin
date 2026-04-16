"""Drawer front builder — stub. Fill in define_inputs() and build()."""

import adsk.core
import adsk.fusion

KEY = "drawer_front"
DISPLAY_NAME = "Drawer Front"
GROUP_ID = "drawer_front_group"


def define_inputs(inputs: adsk.core.CommandInputs) -> adsk.core.GroupCommandInput:
    group = inputs.addGroupCommandInput(GROUP_ID, DISPLAY_NAME)
    group.isExpanded = True
    group.children.addTextBoxCommandInput(
        "df_placeholder", "", "Drawer front builder not yet implemented.", 2, True,
    )
    return group


def build(design: adsk.fusion.Design, cmd_inputs: adsk.core.CommandInputs, ui: adsk.core.UserInterface) -> None:
    ui.messageBox("Drawer front builder is not implemented yet.", DISPLAY_NAME)
