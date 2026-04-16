"""Registry of part-type builders.

Each builder module must expose:
  - KEY (str):          unique id used by the dispatch layer
  - DISPLAY_NAME (str): label shown in the part-type dropdown
  - GROUP_ID (str):     CommandInputs id of its top-level GroupCommandInput
  - define_inputs(inputs) -> GroupCommandInput:
        build the dialog inputs for this part type, return the group so
        the main dialog can toggle its visibility
  - build(design, cmd_inputs, ui) -> None:
        run on OK, reads values from cmd_inputs and creates geometry

Add a new part type by creating a module that implements the above and
registering it in BUILDERS below.
"""

from builders import base_cabinet, upper_cabinet, drawer_box, drawer_front, doors

BUILDERS = {
    base_cabinet.KEY: base_cabinet,
    upper_cabinet.KEY: upper_cabinet,
    drawer_box.KEY: drawer_box,
    drawer_front.KEY: drawer_front,
    doors.KEY: doors,
}

DEFAULT_KEY = base_cabinet.KEY
