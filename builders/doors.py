"""Doors builder — stub. Fill in define_inputs() and build()."""

import adsk.core
import adsk.fusion

KEY = "doors"
DISPLAY_NAME = "Doors"
GROUP_ID = "doors_group"


def define_inputs(inputs: adsk.core.CommandInputs) -> adsk.core.GroupCommandInput:
    group = inputs.addGroupCommandInput(GROUP_ID, DISPLAY_NAME)
    group.isExpanded = True
    group.children.addTextBoxCommandInput(
        "doors_placeholder", "", "Doors builder not yet implemented.", 2, True,
    )
    return group


def build(design: adsk.fusion.Design, cmd_inputs: adsk.core.CommandInputs, ui: adsk.core.UserInterface) -> None:
    ui.messageBox("Doors builder is not implemented yet.", DISPLAY_NAME)
