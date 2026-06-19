"""Drawer box builder — Blum TANDEM undermount drawer box.

Sized from the cabinet opening per the Blum TANDEM front-view spec:
the inside drawer width MUST equal the opening width minus 49 mm for the
slides to align. Construction:

  - Two sides run the full 21" depth (fixed). The front and back fit
    BETWEEN the sides, so each is `inside_width` (= opening - 49) long.
    Outside box width = inside_width + 2·T = opening - 13 mm.
  - The drawer bottom sits in a dado cut on the inner face of all four
    pieces. The dado is half the side-material thickness deep (9 mm for
    18 mm stock) and as wide as the bottom panel. Its lower shoulder is
    the 13 mm "bottom recess" above the bottom edge of the sides.

Only 3/4" (treated as 18 mm) stock is wired up for now; 1/2" (13 mm) will
be added later by parameterising MATERIAL_THICKNESS_MM. User inputs are
just opening width and box (side) height — depth is fixed.

Orientation (matches the rest of the project):
  X = width   (left to right)
  Y = depth   (front at Y=0, back at Y=+depth)
  Z = height  (bottom to top)
"""

import adsk.core
import adsk.fusion

from lib.units import IN_TO_CM, MM_TO_IN, inches, mm
from lib.appearance import apply_appearance, get_appearance

KEY = "drawer_box"
DISPLAY_NAME = "Drawer Box"
GROUP_ID = "drawer_box_group"

# Material — 3/4" nominal stock treated as 18 mm internally. The drawer
# bottom uses the same stock, which sets the dado width.
MATERIAL_THICKNESS_MM = 18.0
DRAWER_BOTTOM_THICKNESS_MM = 18.0

# Blum TANDEM fixed dimensions.
DRAWER_DEPTH_IN = 21.0           # fixed for now
BOTTOM_RECESS_MM = 13.0          # underside of bottom panel above side bottom
TANDEM_WIDTH_DEDUCTION_MM = 49.0  # inside width = opening - 49

# Rear notches in the back panel that clear the slide locking mechanism.
# Blum's spec is 35 mm (1-3/8") minimum wide; we use 1.5". The 13 mm height
# matches the bottom recess, so each notch tops out at the dado's lower edge.
BACK_NOTCH_WIDTH_IN = 1.5
BACK_NOTCH_HEIGHT_MM = 13.0

DEFAULTS = {
    "OpeningWidth": 18.0,
    "BoxHeight": 6.0,
}


def _in_value(val_in: float) -> adsk.core.ValueInput:
    return adsk.core.ValueInput.createByReal(inches(val_in))


def define_inputs(inputs: adsk.core.CommandInputs) -> adsk.core.GroupCommandInput:
    group = inputs.addGroupCommandInput(GROUP_ID, DISPLAY_NAME)
    group.isExpanded = True
    ci = group.children

    ci.addValueInput("db_opening_width", "Opening Width", "in", _in_value(DEFAULTS["OpeningWidth"]))
    ci.addValueInput("db_box_height",    "Box Height",    "in", _in_value(DEFAULTS["BoxHeight"]))

    return group


def _collect_values(cmd_inputs: adsk.core.CommandInputs) -> dict:
    def _val_in(id_: str) -> float:
        return cmd_inputs.itemById(id_).value / IN_TO_CM  # cm -> inches

    return {
        "OpeningWidth": _val_in("db_opening_width"),
        "BoxHeight":    _val_in("db_box_height"),
    }


def build(design: adsk.fusion.Design, cmd_inputs: adsk.core.CommandInputs, ui: adsk.core.UserInterface) -> None:
    vals = _collect_values(cmd_inputs)

    opening_mm = vals["OpeningWidth"] / MM_TO_IN     # inches -> mm
    height_mm = vals["BoxHeight"] / MM_TO_IN

    inside_w_mm = opening_mm - TANDEM_WIDTH_DEDUCTION_MM
    if inside_w_mm <= 0:
        ui.messageBox(
            f'Opening Width must be greater than {TANDEM_WIDTH_DEDUCTION_MM:.0f} mm '
            f'({TANDEM_WIDTH_DEDUCTION_MM * MM_TO_IN:.3g}") so the inside width is positive.',
            DISPLAY_NAME,
        )
        return

    if inside_w_mm <= 2 * BACK_NOTCH_WIDTH_IN / MM_TO_IN:
        ui.messageBox(
            f'Opening Width is too small — the two {BACK_NOTCH_WIDTH_IN:g}" rear '
            f'notches would meet. Increase the opening width.',
            DISPLAY_NAME,
        )
        return

    min_h_mm = BOTTOM_RECESS_MM + DRAWER_BOTTOM_THICKNESS_MM
    if height_mm <= min_h_mm:
        ui.messageBox(
            f'Box Height must be greater than {min_h_mm:.0f} mm '
            f'({min_h_mm * MM_TO_IN:.3g}") to fit the bottom dado.',
            DISPLAY_NAME,
        )
        return

    _build_box(design, vals)


def _build_box(design: adsk.fusion.Design, vals: dict) -> adsk.fusion.Component:
    """Build the five drawer-box bodies inside a new child component."""
    root = design.rootComponent

    # All lengths in cm (Fusion internal units).
    T     = mm(MATERIAL_THICKNESS_MM)          # side / front / back thickness
    BT    = mm(DRAWER_BOTTOM_THICKNESS_MM)     # bottom thickness == dado width
    DD    = mm(MATERIAL_THICKNESS_MM / 2.0)    # dado depth (half material)
    REC   = mm(BOTTOM_RECESS_MM)               # dado lower shoulder height
    DEPTH = inches(DRAWER_DEPTH_IN)
    IW    = inches(vals["OpeningWidth"]) - mm(TANDEM_WIDTH_DEDUCTION_MM)  # inside width
    OW    = IW + 2 * T                          # outside width
    H     = inches(vals["BoxHeight"])

    DADO_Z0 = REC          # bottom of dado
    DADO_Z1 = REC + BT     # top of dado

    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = f"DrawerBox_{vals['OpeningWidth']:.4g}x{vals['BoxHeight']:.4g}"

    sketches = comp.sketches
    extrudes = comp.features.extrudeFeatures
    mirrors = comp.features.mirrorFeatures
    xz_plane = comp.xZConstructionPlane
    yz_plane = comp.yZConstructionPlane
    xy_plane = comp.xYConstructionPlane

    # Mirror centerlines.
    planes = comp.constructionPlanes
    w_center_in = planes.createInput()
    w_center_in.setByOffset(yz_plane, adsk.core.ValueInput.createByReal(OW / 2))
    w_center_plane = planes.add(w_center_in)
    w_center_plane.name = "Width Centerline"

    d_center_in = planes.createInput()
    d_center_in.setByOffset(xz_plane, adsk.core.ValueInput.createByReal(DEPTH / 2))
    d_center_plane = planes.add(d_center_in)
    d_center_plane.name = "Depth Centerline"

    def _draw_closed_loop(lines, pts):
        """Thread a closed polyline through shared endpoints so it closes cleanly."""
        drawn = []
        for i in range(len(pts) - 1):
            start = pts[0] if i == 0 else drawn[-1].endSketchPoint
            drawn.append(lines.addByTwoPoints(start, pts[i + 1]))
        lines.addByTwoPoints(drawn[-1].endSketchPoint, drawn[0].startSketchPoint)

    def _mirror(body, mirror_plane, new_name):
        coll = adsk.core.ObjectCollection.create()
        coll.add(body)
        feat = mirrors.add(mirrors.createInput(coll, mirror_plane))
        mirrored = feat.bodies.item(0)
        mirrored.name = new_name
        return mirrored

    # ------------------------------------------------------------------
    # LEFT SIDE — cross-section in the XZ plane (thickness X, height Z),
    # dado notch baked into the inner (X=T) edge. Extruded full depth +Y.
    # Mirrored across the width centerline for the right side.
    # ------------------------------------------------------------------
    side_sketch = sketches.add(xz_plane)
    side_lines = side_sketch.sketchCurves.sketchLines

    def _xz_pt(x, z):
        p = side_sketch.modelToSketchSpace(adsk.core.Point3D.create(x, 0, z))
        return adsk.core.Point3D.create(p.x, p.y, 0)

    # CCW: outer edge at X=0, inner edge at X=T with the dado stepping to X=T-DD.
    side_pts = [
        _xz_pt(0,      0),
        _xz_pt(T,      0),
        _xz_pt(T,      DADO_Z0),
        _xz_pt(T - DD, DADO_Z0),
        _xz_pt(T - DD, DADO_Z1),
        _xz_pt(T,      DADO_Z1),
        _xz_pt(T,      H),
        _xz_pt(0,      H),
    ]
    _draw_closed_loop(side_lines, side_pts)

    left_side_in = extrudes.createInput(
        side_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    left_side_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(DEPTH))
    feat_left_side = extrudes.add(left_side_in)
    feat_left_side.bodies.item(0).name = "Left Side"

    _mirror(feat_left_side.bodies.item(0), w_center_plane, "Right Side")

    # ------------------------------------------------------------------
    # FRONT — cross-section in the YZ plane (thickness Y, height Z), dado
    # notch on the inner (Y=T) edge. Extruded +X between the sides
    # (X=T .. OW-T). Mirrored across the depth centerline for the back.
    # ------------------------------------------------------------------
    front_sketch = sketches.add(yz_plane)
    front_lines = front_sketch.sketchCurves.sketchLines

    def _yz_pt(y, z):
        p = front_sketch.modelToSketchSpace(adsk.core.Point3D.create(0, y, z))
        return adsk.core.Point3D.create(p.x, p.y, 0)

    front_pts = [
        _yz_pt(0,      0),
        _yz_pt(T,      0),
        _yz_pt(T,      DADO_Z0),
        _yz_pt(T - DD, DADO_Z0),
        _yz_pt(T - DD, DADO_Z1),
        _yz_pt(T,      DADO_Z1),
        _yz_pt(T,      H),
        _yz_pt(0,      H),
    ]
    _draw_closed_loop(front_lines, front_pts)

    front_in = extrudes.createInput(
        front_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    front_in.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(T)
    )
    front_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(IW))
    feat_front = extrudes.add(front_in)
    feat_front.bodies.item(0).name = "Front"

    back_body = _mirror(feat_front.bodies.item(0), d_center_plane, "Back")

    # ------------------------------------------------------------------
    # REAR NOTCHES — cut from both bottom corners of the back panel only,
    # to clear the slide locking mechanism (Blum TANDEM). Each is
    # BACK_NOTCH_WIDTH_IN wide from the panel end and BACK_NOTCH_HEIGHT_MM
    # tall, cut through the full panel thickness (Y).
    # ------------------------------------------------------------------
    NW = inches(BACK_NOTCH_WIDTH_IN)
    NH = mm(BACK_NOTCH_HEIGHT_MM)

    notch_sketch = sketches.add(xz_plane)
    notch_lines = notch_sketch.sketchCurves.sketchLines
    notch_specs = [
        (T,           0, T + NW,        NH),  # left corner
        (OW - T - NW, 0, OW - T,        NH),  # right corner
    ]
    for x0, z0, x1, z1 in notch_specs:
        p0 = notch_sketch.modelToSketchSpace(adsk.core.Point3D.create(x0, 0, z0))
        p1 = notch_sketch.modelToSketchSpace(adsk.core.Point3D.create(x1, 0, z1))
        notch_lines.addTwoPointRectangle(
            adsk.core.Point3D.create(p0.x, p0.y, 0),
            adsk.core.Point3D.create(p1.x, p1.y, 0),
        )

    notch_profs = adsk.core.ObjectCollection.create()
    for i in range(notch_sketch.profiles.count):
        notch_profs.add(notch_sketch.profiles.item(i))

    notch_cut_in = extrudes.createInput(
        notch_profs,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    notch_cut_in.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(DEPTH - T)
    )
    notch_cut_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(T))
    notch_cut_in.participantBodies = [back_body]
    extrudes.add(notch_cut_in)

    # ------------------------------------------------------------------
    # BOTTOM — flat panel seated in all four dados. Reaches DD into each
    # dado floor and spans the Z band of the dado.
    # ------------------------------------------------------------------
    bottom_sketch = sketches.add(xy_plane)
    bp0 = adsk.core.Point3D.create(T - DD, T - DD, 0)
    bp1 = adsk.core.Point3D.create(OW - T + DD, DEPTH - T + DD, 0)
    bottom_sketch.sketchCurves.sketchLines.addTwoPointRectangle(bp0, bp1)

    bottom_in = extrudes.createInput(
        bottom_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    bottom_in.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(DADO_Z0)
    )
    bottom_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(BT))
    feat_bottom = extrudes.add(bottom_in)
    feat_bottom.bodies.item(0).name = "Bottom"

    # ------------------------------------------------------------------
    # Appearance.
    # ------------------------------------------------------------------
    oak_semigloss = get_appearance(design, ["Oak", "Semigloss"])
    apply_appearance(
        [comp.bRepBodies.item(i) for i in range(comp.bRepBodies.count)],
        oak_semigloss,
    )

    return comp
