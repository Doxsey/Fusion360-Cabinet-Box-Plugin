"""Upper cabinet builder: face frame + dado-housed top/bottom panels + back nailer.

Inputs are the outer face frame dimensions (Width, Height) plus total Depth.
The face frame overhangs the carcass by FaceFrameOverlap on the left, right,
and bottom; the top is flush. Side panels carry two through dados (one near
the top, one near the bottom) at material thickness T from each end, each
dado T wide and T/2 deep. The top and bottom panels sit in the dados; a
back nailer spans between the sides at the top-rear for wall mounting.
"""

import adsk.core
import adsk.fusion

from lib.units import IN_TO_CM, MM_TO_IN, inches
from lib.sketch_utils import get_face_sketch_bounds, find_face_by_normal, sketch_rect_xy
from lib.appearance import apply_appearance, get_appearance

KEY = "upper_cabinet"
DISPLAY_NAME = "Upper Cabinet"
GROUP_ID = "upper_cabinet_group"

DEFAULTS = {
    "Width": 24.0,
    "Height": 30.0,
    "Depth": 12.0,
    "Thickness": 18.0 * MM_TO_IN,
    "FaceFrameOverlap": 0.25,
    "FaceFrameThickness": 0.75,
    "FaceFrameWidth": 1.5,
}

NAILER_WIDTH_IN = 4.0
BACK_PANEL_CLEARANCE_IN = 0.25


def _in_value(val_in: float) -> adsk.core.ValueInput:
    return adsk.core.ValueInput.createByReal(inches(val_in))


def define_inputs(inputs: adsk.core.CommandInputs) -> adsk.core.GroupCommandInput:
    group = inputs.addGroupCommandInput(GROUP_ID, DISPLAY_NAME)
    group.isExpanded = True
    ci = group.children

    ci.addValueInput("uc_width",         "Width",                "in", _in_value(DEFAULTS["Width"]))
    ci.addValueInput("uc_height",        "Height",               "in", _in_value(DEFAULTS["Height"]))
    ci.addValueInput("uc_depth",         "Depth",                "in", _in_value(DEFAULTS["Depth"]))
    ci.addValueInput("uc_thickness",     "Material Thickness",   "in", _in_value(DEFAULTS["Thickness"]))
    ci.addValueInput("uc_ff_overlap",    "Face Frame Overlap",   "in", _in_value(DEFAULTS["FaceFrameOverlap"]))
    ci.addValueInput("uc_ff_thickness",  "Face Frame Thickness", "in", _in_value(DEFAULTS["FaceFrameThickness"]))
    ci.addValueInput("uc_ff_width",      "Face Frame Width",     "in", _in_value(DEFAULTS["FaceFrameWidth"]))

    return group


def _collect_values(cmd_inputs: adsk.core.CommandInputs) -> dict:
    def _val_in(id_: str) -> float:
        return cmd_inputs.itemById(id_).value / IN_TO_CM

    return {
        "Width":              _val_in("uc_width"),
        "Height":             _val_in("uc_height"),
        "Depth":              _val_in("uc_depth"),
        "Thickness":          _val_in("uc_thickness"),
        "FaceFrameOverlap":   _val_in("uc_ff_overlap"),
        "FaceFrameThickness": _val_in("uc_ff_thickness"),
        "FaceFrameWidth":     _val_in("uc_ff_width"),
    }


def build(design: adsk.fusion.Design, cmd_inputs: adsk.core.CommandInputs, ui: adsk.core.UserInterface) -> None:
    vals = _collect_values(cmd_inputs)

    T   = vals["Thickness"]
    FFO = vals["FaceFrameOverlap"]
    FFT = vals["FaceFrameThickness"]
    FFW = vals["FaceFrameWidth"]

    min_w_dado = 2 * FFO + T
    if vals["Width"] <= min_w_dado:
        ui.messageBox(
            f'Width must be greater than 2× face frame overlap + material thickness ({min_w_dado:.3g}").',
            DISPLAY_NAME,
        )
        return
    if vals["Width"] <= 2 * FFW:
        ui.messageBox(
            f'Width must be greater than 2× face frame width ({2 * FFW:.3g}").',
            DISPLAY_NAME,
        )
        return

    # Need vertical room for both dado pockets plus a nailer at top and bottom.
    min_h = 4 * T + FFO + 2 * NAILER_WIDTH_IN
    if vals["Height"] <= min_h:
        ui.messageBox(
            f'Height must be greater than {min_h:.3g}" — room for two dadoes and both nailers.',
            DISPLAY_NAME,
        )
        return
    if vals["Depth"] <= FFT:
        ui.messageBox("Depth must be greater than face frame thickness.", DISPLAY_NAME)
        return

    _build_cabinet(design.rootComponent, vals)


def _build_cabinet(root: adsk.fusion.Component, vals: dict) -> adsk.fusion.Component:
    """Build an upper cabinet (face frame + carcass) under a wrapper component."""

    W   = inches(vals["Width"])
    H   = inches(vals["Height"])
    D   = inches(vals["Depth"])
    T   = inches(vals["Thickness"])
    FFO = inches(vals["FaceFrameOverlap"])
    FFT = inches(vals["FaceFrameThickness"])
    FFW = inches(vals["FaceFrameWidth"])
    NW  = inches(NAILER_WIDTH_IN)
    BPC = inches(BACK_PANEL_CLEARANCE_IN)

    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = (
        f"UpperCabinet_{vals['Width']:.4g}x{vals['Height']:.4g}x{vals['Depth']:.4g}"
    )

    # Wrapper holding Face Frame + Carcass sub-assemblies; each owns its
    # own sketches/features/centerline.

    # ------------------------------------------------------------------
    # FACE FRAME — styles span Z=[0, H] (full FF height, no top overlap).
    # ------------------------------------------------------------------
    ff_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    ff_comp = ff_occ.component
    ff_comp.name = "Face Frame"

    ff_sketches = ff_comp.sketches
    ff_extrudes = ff_comp.features.extrudeFeatures
    ff_xy_plane = ff_comp.xYConstructionPlane

    ff_planes = ff_comp.constructionPlanes
    ff_centerline_input = ff_planes.createInput()
    ff_centerline_input.setByOffset(
        ff_comp.yZConstructionPlane,
        adsk.core.ValueInput.createByReal(W / 2),
    )
    ff_centerline_plane = ff_planes.add(ff_centerline_input)
    ff_centerline_plane.name = "Face Frame Centerline"

    # LEFT STYLE
    sk_ff_left_style = sketch_rect_xy(ff_sketches, ff_xy_plane, 0, 0, FFW, FFT)
    ff_left_ext_input = ff_extrudes.createInput(
        sk_ff_left_style.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    ff_left_ext_input.setDistanceExtent(
        False,
        adsk.core.ValueInput.createByReal(H),
    )
    feat_ff_left_style = ff_extrudes.add(ff_left_ext_input)
    feat_ff_left_style.bodies.item(0).name = "Left Style"

    # RIGHT STYLE (mirror across face frame centerline)
    style_mirror_bodies = adsk.core.ObjectCollection.create()
    style_mirror_bodies.add(feat_ff_left_style.bodies.item(0))
    style_mirror_input = ff_comp.features.mirrorFeatures.createInput(style_mirror_bodies, ff_centerline_plane)
    feat_ff_right_style = ff_comp.features.mirrorFeatures.add(style_mirror_input)
    feat_ff_right_style.bodies.item(0).name = "Right Style"

    # TOP & BOTTOM RAILS — sketched on the left style's inner face and
    # extruded across to the right style's inner face.
    left_style = feat_ff_left_style.bodies.item(0)
    left_style_inner_face = find_face_by_normal(left_style, 1, 0, 0)
    right_style = feat_ff_right_style.bodies.item(0)
    right_style_inner_face = find_face_by_normal(right_style, -1, 0, 0)

    rails_sketch = ff_sketches.add(left_style_inner_face)
    min_pt, max_pt = get_face_sketch_bounds(rails_sketch, left_style_inner_face)

    rails_lines = rails_sketch.sketchCurves.sketchLines
    # Bottom rail is FFW + T tall (vs FFW for the top rail) so its top edge
    # projects above the dado-housed bottom panel by FFW - FFO - T — the
    # same internal overhang the styles have past the side panels' inner face.
    rails_lines.addTwoPointRectangle(
        adsk.core.Point3D.create(min_pt.x, min_pt.y, 0),
        adsk.core.Point3D.create(max_pt.x, min_pt.y + FFW + T, 0),
    )
    rails_lines.addTwoPointRectangle(
        adsk.core.Point3D.create(min_pt.x, max_pt.y - FFW, 0),
        adsk.core.Point3D.create(max_pt.x, max_pt.y, 0),
    )

    bot_rail_prof = None
    top_rail_prof = None
    lowest_y = float('inf')
    highest_y = -float('inf')
    for i in range(rails_sketch.profiles.count):
        prof = rails_sketch.profiles.item(i)
        cy = prof.areaProperties().centroid.y
        if cy < lowest_y:
            lowest_y = cy
            bot_rail_prof = prof
        if cy > highest_y:
            highest_y = cy
            top_rail_prof = prof

    rail_profs = adsk.core.ObjectCollection.create()
    rail_profs.add(bot_rail_prof)
    rail_profs.add(top_rail_prof)

    rails_ext_input = ff_extrudes.createInput(
        rail_profs,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    rails_ext_input.setOneSideToExtent(right_style_inner_face, False)
    feat_rails = ff_extrudes.add(rails_ext_input)

    rail_bodies = sorted(
        (feat_rails.bodies.item(i) for i in range(feat_rails.bodies.count)),
        key=lambda b: b.physicalProperties.centerOfMass.z,
    )
    rail_bodies[0].name = "Bottom Rail"
    rail_bodies[1].name = "Top Rail"

    design = adsk.fusion.Design.cast(root.parentDesign)
    abs_white = get_appearance(design, ["ABS", "White"])
    apply_appearance(
        [
            feat_ff_left_style.bodies.item(0),
            feat_ff_right_style.bodies.item(0),
            rail_bodies[0],
            rail_bodies[1],
        ],
        abs_white,
    )

    # ------------------------------------------------------------------
    # CARCASS — own sub-component. Side panels carry the dado profile
    # directly (no separate cut feature); top/bottom panels and the back
    # nailer extrude in Y from the carcass XZ plane.
    # ------------------------------------------------------------------
    c_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    c_comp = c_occ.component
    c_comp.name = "Carcass"

    c_sketches = c_comp.sketches
    c_extrudes = c_comp.features.extrudeFeatures
    c_xz_plane = c_comp.xZConstructionPlane

    c_planes = c_comp.constructionPlanes
    c_centerline_input = c_planes.createInput()
    c_centerline_input.setByOffset(
        c_comp.yZConstructionPlane,
        adsk.core.ValueInput.createByReal(W / 2),
    )
    centerline_plane = c_planes.add(c_centerline_input)
    centerline_plane.name = "Carcass Centerline"

    # LEFT SIDE PANEL — 12-vertex profile on the carcass XZ plane (Y=0),
    # extruded in +Y from Y=FFT to Y=DEPTH. Two dado notches on the inner
    # (right) edge are baked into the profile so a single extrude produces
    # the finished side; the right side is then a mirror of this body.
    left_side_sketch = c_sketches.add(c_xz_plane)
    ls_lines = left_side_sketch.sketchCurves.sketchLines

    # CCW from bottom-left; inner edge (+X) steps inward at each dado.
    profile_pts_model = [
        (FFO,         FFO),
        (FFO + T,     FFO),
        (FFO + T,     FFO + T),
        (FFO + T/2,   FFO + T),
        (FFO + T/2,   FFO + 2*T),
        (FFO + T,     FFO + 2*T),
        (FFO + T,     H - 2*T),
        (FFO + T/2,   H - 2*T),
        (FFO + T/2,   H - T),
        (FFO + T,     H - T),
        (FFO + T,     H),
        (FFO,         H),
    ]

    def _sketch_pt(x_model, z_model):
        sk = left_side_sketch.modelToSketchSpace(
            adsk.core.Point3D.create(x_model, 0, z_model)
        )
        return adsk.core.Point3D.create(sk.x, sk.y, 0)

    # Thread the loop through the previous line's endSketchPoint so each
    # vertex is a single shared point — guarantees the loop is closed.
    drawn = []
    for i in range(len(profile_pts_model) - 1):
        end_pt = _sketch_pt(*profile_pts_model[i + 1])
        if i == 0:
            start = _sketch_pt(*profile_pts_model[0])
            line = ls_lines.addByTwoPoints(start, end_pt)
        else:
            line = ls_lines.addByTwoPoints(drawn[-1].endSketchPoint, end_pt)
        drawn.append(line)
    ls_lines.addByTwoPoints(drawn[-1].endSketchPoint, drawn[0].startSketchPoint)

    left_side_ext_in = c_extrudes.createInput(
        left_side_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    left_side_ext_in.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(FFT)
    )
    left_side_ext_in.setDistanceExtent(
        False,
        adsk.core.ValueInput.createByReal(D - FFT),
    )
    feat_left_side = c_extrudes.add(left_side_ext_in)
    feat_left_side.bodies.item(0).name = "Left Panel"

    # RIGHT SIDE PANEL — mirror; dado notches come along automatically.
    side_mirror_bodies = adsk.core.ObjectCollection.create()
    side_mirror_bodies.add(feat_left_side.bodies.item(0))
    side_mirror_input = c_comp.features.mirrorFeatures.createInput(side_mirror_bodies, centerline_plane)
    feat_right_side = c_comp.features.mirrorFeatures.add(side_mirror_input)
    feat_right_side.bodies.item(0).name = "Right Panel"

    # ------------------------------------------------------------------
    # TOP PANEL + BOTTOM PANEL + BACK NAILER — one XZ sketch (3 rects),
    # one extrude per profile because each piece has its own Y range.
    # Top/bottom panels reach T/2 into the dado on each side; the nailer
    # spans between the side panels' inner faces (no dado intrusion).
    # ------------------------------------------------------------------
    panels_sketch = c_sketches.add(c_xz_plane)
    pl = panels_sketch.sketchCurves.sketchLines

    # (name, x0, z0, x1, z1, y_start, y_end)
    rect_specs = [
        # Top panel stops T + BPC short of the back to leave a slot for a
        # back panel to slide in (the back panel itself isn't modelled).
        ("Top Panel",
            FFO + T/2,        H - 2*T,
            W - FFO - T/2,    H - T,
            FFT,              D - T - BPC),
        ("Bottom Panel",
            FFO + T/2,        FFO + T,
            W - FFO - T/2,    FFO + 2*T,
            FFT,              D),
        ("Top Nailer",
            FFO + T,          H - 2*T - NW,
            W - FFO - T,      H - 2*T,
            D - T,            D),
        ("Bottom Nailer",
            FFO + T,          FFO + 2*T,
            W - FFO - T,      FFO + 2*T + NW,
            D - T,            D),
    ]

    for _, x0, z0, x1, z1, _y0, _y1 in rect_specs:
        p0 = panels_sketch.modelToSketchSpace(adsk.core.Point3D.create(x0, 0, z0))
        p1 = panels_sketch.modelToSketchSpace(adsk.core.Point3D.create(x1, 0, z1))
        pl.addTwoPointRectangle(
            adsk.core.Point3D.create(p0.x, p0.y, 0),
            adsk.core.Point3D.create(p1.x, p1.y, 0),
        )

    def _pick_profile_xz(sketch, target_x, target_z):
        best, best_d2 = None, float('inf')
        for i in range(sketch.profiles.count):
            prof = sketch.profiles.item(i)
            c = sketch.sketchToModelSpace(prof.areaProperties().centroid)
            d2 = (c.x - target_x) ** 2 + (c.z - target_z) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = prof
        return best

    carcass_panel_bodies = []
    for name, x0, z0, x1, z1, y0, y1 in rect_specs:
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        ext_in = c_extrudes.createInput(
            _pick_profile_xz(panels_sketch, cx, cz),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        ext_in.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(y0)
        )
        ext_in.setDistanceExtent(
            False,
            adsk.core.ValueInput.createByReal(y1 - y0),
        )
        feat = c_extrudes.add(ext_in)
        body = feat.bodies.item(0)
        body.name = name
        carcass_panel_bodies.append(body)

    oak_semigloss = get_appearance(design, ["Oak", "Semigloss"])
    apply_appearance(
        [
            feat_left_side.bodies.item(0),
            feat_right_side.bodies.item(0),
            *carcass_panel_bodies,
        ],
        oak_semigloss,
    )

    return comp
