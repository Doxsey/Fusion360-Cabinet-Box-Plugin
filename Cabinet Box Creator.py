"""Entry point for Cabinet Box Creator.

Shows a single Fusion command dialog with a Part Type dropdown; each
builder registers its own input group, and only the selected group is
visible. On OK, the chosen builder's build() runs.

Add new part types in builders/ and register them in builders/__init__.py.
"""

import os
import sys
import traceback

import adsk.core
import adsk.fusion

# Fusion adds the script's folder to sys.path when running, but be explicit
# so `from lib.x import ...` / `from builders import ...` are unambiguous.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from builders import BUILDERS, DEFAULT_KEY  # noqa: E402

CMD_ID = "CabinetBoxCreatorCmd"
CMD_NAME = "Cabinet Box Creator"
CMD_DESCRIPTION = "Create cabinet parts (base cabinet, upper, drawer box, door)."
PART_TYPE_INPUT_ID = "part_type"

# Fusion holds only weak refs to event handlers; keep strong refs here.
_handlers: list = []


def _key_for_display(display_name: str) -> str:
    for key, builder in BUILDERS.items():
        if builder.DISPLAY_NAME == display_name:
            return key
    raise ValueError(f"Unknown part type: {display_name}")


def _set_group_visibility(inputs: adsk.core.CommandInputs, selected_key: str) -> None:
    for key, builder in BUILDERS.items():
        group = inputs.itemById(builder.GROUP_ID)
        if group:
            group.isVisible = (key == selected_key)


class CommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            event_args = adsk.core.CommandEventArgs.cast(args)
            inputs = event_args.command.commandInputs

            dropdown = adsk.core.DropDownCommandInput.cast(inputs.itemById(PART_TYPE_INPUT_ID))
            builder_key = _key_for_display(dropdown.selectedItem.name)

            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                ui.messageBox("No active Fusion design found.", CMD_NAME)
                return

            BUILDERS[builder_key].build(design, inputs, ui)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            ui.messageBox("Build failed:\n\n" + traceback.format_exc(), CMD_NAME)


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            event_args = adsk.core.InputChangedEventArgs.cast(args)
            changed = event_args.input
            if changed.id != PART_TYPE_INPUT_ID:
                return
            dropdown = adsk.core.DropDownCommandInput.cast(changed)
            selected_key = _key_for_display(dropdown.selectedItem.name)
            _set_group_visibility(event_args.inputs, selected_key)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            ui.messageBox("InputChanged failed:\n\n" + traceback.format_exc(), CMD_NAME)


class CommandDestroyHandler(adsk.core.CommandEventHandler):
    def notify(self, _args):
        # End the script once the dialog is dismissed.
        adsk.terminate()


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = adsk.core.CommandCreatedEventArgs.cast(args).command
            inputs = cmd.commandInputs

            dd = inputs.addDropDownCommandInput(
                PART_TYPE_INPUT_ID,
                "Part Type",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for key, builder in BUILDERS.items():
                dd.listItems.add(builder.DISPLAY_NAME, key == DEFAULT_KEY, "")

            # Each builder creates its own group; only the default one starts visible.
            for key, builder in BUILDERS.items():
                group = builder.define_inputs(inputs)
                group.isVisible = (key == DEFAULT_KEY)

            on_execute = CommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_input_changed = InputChangedHandler()
            cmd.inputChanged.add(on_input_changed)
            _handlers.append(on_input_changed)

            on_destroy = CommandDestroyHandler()
            cmd.destroy.add(on_destroy)
            _handlers.append(on_destroy)
        except Exception:
            ui = adsk.core.Application.get().userInterface
            ui.messageBox("CommandCreated failed:\n\n" + traceback.format_exc(), CMD_NAME)


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        if not adsk.fusion.Design.cast(app.activeProduct):
            ui.messageBox(
                "No active Fusion 360 design found.\n"
                "Please open or create a design first.",
                CMD_NAME,
            )
            return

        cmd_defs = ui.commandDefinitions
        existing = cmd_defs.itemById(CMD_ID)
        if existing:
            existing.deleteMe()
        cmd_def = cmd_defs.addButtonDefinition(CMD_ID, CMD_NAME, CMD_DESCRIPTION)

        on_created = CommandCreatedHandler()
        cmd_def.commandCreated.add(on_created)
        _handlers.append(on_created)

        cmd_def.execute()

        # Keep the script alive until the command's destroy handler calls terminate().
        adsk.autoTerminate(False)
    except Exception:
        if ui:
            ui.messageBox("Script failed:\n\n" + traceback.format_exc(), CMD_NAME)
