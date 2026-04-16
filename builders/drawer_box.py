"""Drawer box builder — stub. Fill in define_inputs() and build()."""

import adsk.core
import adsk.fusion

KEY = "drawer_box"
DISPLAY_NAME = "Drawer Box"
GROUP_ID = "drawer_box_group"


def define_inputs(inputs: adsk.core.CommandInputs) -> adsk.core.GroupCommandInput:
    group = inputs.addGroupCommandInput(GROUP_ID, DISPLAY_NAME)
    group.isExpanded = True
    group.children.addTextBoxCommandInput(
        "db_placeholder", "", "Drawer box builder not yet implemented.", 2, True,
    )
    return group


def build(design: adsk.fusion.Design, cmd_inputs: adsk.core.CommandInputs, ui: adsk.core.UserInterface) -> None:
    ui.messageBox("Drawer box builder is not implemented yet.", DISPLAY_NAME)
