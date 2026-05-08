"""Base cabinet builder: face frame + two sides + bottom + 3 supports."""

import adsk.core
import adsk.fusion

from lib.units import IN_TO_CM, MM_TO_IN, inches
from lib.sketch_utils import get_face_sketch_bounds, find_face_by_normal, sketch_rect_xy
from lib.params import add_or_update_param
from lib.appearance import apply_appearance, get_appearance

KEY = "base_cabinet"
DISPLAY_NAME = "Base Cabinet"
GROUP_ID = "base_cabinet_group"

DEFAULTS = {
    "Width": 24.0,
    "Height": 30.5,
    "Depth": 24.0,
    "Thickness": 18.0 * MM_TO_IN,
    "FaceFrameOverlap": 0.25,
    "FaceFrameThickness": 0.75,
    "FaceFrameWidth": 1.5,
}


def _in_value(val_in: float) -> adsk.core.ValueInput:
    return adsk.core.ValueInput.createByReal(inches(val_in))


def define_inputs(inputs: adsk.core.CommandInputs) -> adsk.core.GroupCommandInput:
    group = inputs.addGroupCommandInput(GROUP_ID, DISPLAY_NAME)
    group.isExpanded = True
    ci = group.children

    ci.addValueInput("bc_width",         "Width",                "in", _in_value(DEFAULTS["Width"]))
    ci.addValueInput("bc_height",        "Height",               "in", _in_value(DEFAULTS["Height"]))
    ci.addValueInput("bc_depth",         "Depth",                "in", _in_value(DEFAULTS["Depth"]))
    ci.addValueInput("bc_thickness",     "Material Thickness",   "in", _in_value(DEFAULTS["Thickness"]))
    ci.addValueInput("bc_ff_overlap",    "Face Frame Overlap",   "in", _in_value(DEFAULTS["FaceFrameOverlap"]))
    ci.addValueInput("bc_ff_thickness",  "Face Frame Thickness", "in", _in_value(DEFAULTS["FaceFrameThickness"]))
    ci.addValueInput("bc_ff_width",      "Face Frame Width",     "in", _in_value(DEFAULTS["FaceFrameWidth"]))

    return group


def _collect_values(cmd_inputs: adsk.core.CommandInputs) -> dict:
    def _val_in(id_: str) -> float:
        return cmd_inputs.itemById(id_).value / IN_TO_CM

    return {
        "Width":              _val_in("bc_width"),
        "Height":             _val_in("bc_height"),
        "Depth":              _val_in("bc_depth"),
        "Thickness":          _val_in("bc_thickness"),
        "FaceFrameOverlap":   _val_in("bc_ff_overlap"),
        "FaceFrameThickness": _val_in("bc_ff_thickness"),
        "FaceFrameWidth":     _val_in("bc_ff_width"),
    }


def build(design: adsk.fusion.Design, cmd_inputs: adsk.core.CommandInputs, ui: adsk.core.UserInterface) -> None:
    vals = _collect_values(cmd_inputs)

    T = vals["Thickness"]
    if vals["Width"] <= T * 2:
        ui.messageBox("Width must be greater than 2× material thickness.", DISPLAY_NAME)
        return
    if vals["Height"] <= T * 2:
        ui.messageBox("Height must be greater than 2× material thickness.", DISPLAY_NAME)
        return

    params = design.userParameters
    param_map = {
        "CabWidth":     ("Width",      "Width (in)"),
        "CabHeight":    ("Height",     "Height (in)"),
        "CabDepth":     ("Depth",      "Depth (in)"),
        "MatThickness": ("Thickness",  "Material thickness (in)"),
    }
    for pname, (vkey, comment) in param_map.items():
        add_or_update_param(params, pname, vals[vkey], "cm", comment)

    _build_cabinet(design.rootComponent, vals)


def _build_cabinet(root: adsk.fusion.Component, vals: dict) -> adsk.fusion.Component:
    """Build all cabinet panels inside a new child component. Returns the new component."""

    WIDTH     = inches(vals["Width"])
    H         = inches(vals["Height"])
    DEPTH     = inches(vals["Depth"])
    THICKNESS = inches(vals["Thickness"])
    FF_OVERLAP = inches(vals["FaceFrameOverlap"])
    FF_THICK   = inches(vals["FaceFrameThickness"])
    FF_WIDTH   = inches(vals["FaceFrameWidth"])

    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = (
        f"Cabinet_{vals['Width']:.4g}x{vals['Height']:.4g}x{vals['Depth']:.4g}"
    )

    # The cabinet component is a wrapper holding two sub-assemblies (Face
    # Frame, Carcass); each owns its own sketches/features/centerline.

    # ------------------------------------------------------------------
    # FACE FRAME — own sub-component with its own mirror centerline so the
    # 4 frame pieces are self-contained and can be hidden/replaced as a unit.
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
        adsk.core.ValueInput.createByReal(WIDTH / 2),
    )
    ff_centerline_plane = ff_planes.add(ff_centerline_input)
    ff_centerline_plane.name = "Face Frame Centerline"

    # LEFT STYLE
    sk_ff_left_style = sketch_rect_xy(ff_sketches, ff_xy_plane, 0, 0, FF_WIDTH, FF_THICK)
    ff_left_ext_input = ff_extrudes.createInput(
        sk_ff_left_style.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    ff_left_ext_input.setDistanceExtent(
        False,
        adsk.core.ValueInput.createByReal(H + FF_OVERLAP),
    )
    feat_ff_left_style = ff_extrudes.add(ff_left_ext_input)
    feat_ff_left_style.bodies.item(0).name = "Left Style"

    # RIGHT STYLE (mirror across face frame centerline)
    style_mirror_bodies = adsk.core.ObjectCollection.create()
    style_mirror_bodies.add(feat_ff_left_style.bodies.item(0))
    style_mirror_input = ff_comp.features.mirrorFeatures.createInput(style_mirror_bodies, ff_centerline_plane)
    feat_ff_right_style = ff_comp.features.mirrorFeatures.add(style_mirror_input)
    feat_ff_right_style.bodies.item(0).name = "Right Style"

    # TOP & BOTTOM RAILS (one sketch, one extrude, two bodies)
    left_style = feat_ff_left_style.bodies.item(0)
    left_style_inner_face = find_face_by_normal(left_style, 1, 0, 0)
    right_style = feat_ff_right_style.bodies.item(0)
    right_style_inner_face = find_face_by_normal(right_style, -1, 0, 0)

    rails_sketch = ff_sketches.add(left_style_inner_face)
    min_pt, max_pt = get_face_sketch_bounds(rails_sketch, left_style_inner_face)

    rails_lines = rails_sketch.sketchCurves.sketchLines
    rails_lines.addTwoPointRectangle(
        adsk.core.Point3D.create(min_pt.x, min_pt.y, 0),
        adsk.core.Point3D.create(max_pt.x, min_pt.y + FF_WIDTH, 0),
    )
    rails_lines.addTwoPointRectangle(
        adsk.core.Point3D.create(min_pt.x, max_pt.y - FF_WIDTH, 0),
        adsk.core.Point3D.create(max_pt.x, max_pt.y, 0),
    )

    # The sketch also contains the face's projected edges. Pick the two rail
    # profiles by centroid Y: lowest = bottom rail, highest = top rail.
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
    # CARCASS — own sub-component containing both side panels, the bottom
    # panel, and the three supports. Owns its own mirror centerline.
    # ------------------------------------------------------------------
    c_occ = comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    c_comp = c_occ.component
    c_comp.name = "Carcass"

    sketches = c_comp.sketches
    extrudes = c_comp.features.extrudeFeatures
    xy_plane = c_comp.xYConstructionPlane

    c_planes = c_comp.constructionPlanes
    c_centerline_input = c_planes.createInput()
    c_centerline_input.setByOffset(
        c_comp.yZConstructionPlane,
        adsk.core.ValueInput.createByReal(WIDTH / 2),
    )
    centerline_plane = c_planes.add(c_centerline_input)
    centerline_plane.name = "Carcass Centerline"

    # ------------------------------------------------------------------
    # LEFT SIDE  (x=0, full height, full depth)
    # ------------------------------------------------------------------
    left_panel_sketch = sketch_rect_xy(
        sketches, xy_plane,
        FF_OVERLAP,             FF_THICK,
        FF_OVERLAP + THICKNESS, DEPTH,
    )

    left_panel_ext_input = extrudes.createInput(
        left_panel_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    left_panel_ext_input.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(FF_OVERLAP)
    )
    left_panel_ext_input.setDistanceExtent(
        False,
        adsk.core.ValueInput.createByReal(H),
    )

    feat_left_panel = extrudes.add(left_panel_ext_input)
    feat_left_panel.bodies.item(0).name = "Left Panel"

    # ------------------------------------------------------------------
    # RIGHT SIDE  (mirror of left across cabinet centerline)
    # ------------------------------------------------------------------
    panel_mirror_bodies = adsk.core.ObjectCollection.create()
    panel_mirror_bodies.add(feat_left_panel.bodies.item(0))
    panel_mirror_input = c_comp.features.mirrorFeatures.createInput(panel_mirror_bodies, centerline_plane)
    feat_right_panel = c_comp.features.mirrorFeatures.add(panel_mirror_input)
    feat_right_panel.bodies.item(0).name = "Right Panel"

    # ------------------------------------------------------------------
    # BOTTOM PANEL + 3 SUPPORTS (top-front, top-back, back nailer)
    # All drawn on the left panel's inner face in one sketch, then extruded
    # together to the right panel's inner face so every piece tucks cleanly
    # between the two sides.
    # ------------------------------------------------------------------
    SUPPORT_WIDTH = inches(4)
    TOP_Z = FF_OVERLAP + H

    left_panel_body = feat_left_panel.bodies.item(0)
    right_panel_body = feat_right_panel.bodies.item(0)
    left_panel_inner_face = find_face_by_normal(left_panel_body, 1, 0, 0)
    right_panel_inner_face = find_face_by_normal(right_panel_body, -1, 0, 0)

    panels_sketch = sketches.add(left_panel_inner_face)
    face_x = FF_OVERLAP + THICKNESS

    rect_specs = [
        ("Bottom Panel",
            FF_THICK,              FF_OVERLAP,
            DEPTH,                 FF_OVERLAP + THICKNESS),
        ("Top Front Stretcher",
            FF_THICK,              TOP_Z - THICKNESS,
            FF_THICK + SUPPORT_WIDTH, TOP_Z),
        ("Top Back Stretcher",
            DEPTH - SUPPORT_WIDTH, TOP_Z - THICKNESS,
            DEPTH,                 TOP_Z),
        ("Back Nailer",
            DEPTH - THICKNESS,     TOP_Z - THICKNESS - SUPPORT_WIDTH,
            DEPTH,                 TOP_Z - THICKNESS),
    ]

    rect_lines = panels_sketch.sketchCurves.sketchLines
    for _, y0, z0, y1, z1 in rect_specs:
        p0 = panels_sketch.modelToSketchSpace(adsk.core.Point3D.create(face_x, y0, z0))
        p1 = panels_sketch.modelToSketchSpace(adsk.core.Point3D.create(face_x, y1, z1))
        rect_lines.addTwoPointRectangle(
            adsk.core.Point3D.create(p0.x, p0.y, 0),
            adsk.core.Point3D.create(p1.x, p1.y, 0),
        )

    def _pick_profile(target_y, target_z):
        best, best_d2 = None, float('inf')
        for i in range(panels_sketch.profiles.count):
            prof = panels_sketch.profiles.item(i)
            c = panels_sketch.sketchToModelSpace(prof.areaProperties().centroid)
            d2 = (c.y - target_y) ** 2 + (c.z - target_z) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = prof
        return best

    # One extrude per profile — adjacent profiles (e.g., Top Back Stretcher and
    # Back Nailer share an edge) would otherwise merge into a single body when
    # extruded together.
    support_bodies = []
    for name, y0, z0, y1, z1 in rect_specs:
        cy, cz = (y0 + y1) / 2, (z0 + z1) / 2
        ext_in = extrudes.createInput(
            _pick_profile(cy, cz),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        ext_in.setOneSideToExtent(right_panel_inner_face, False)
        feat = extrudes.add(ext_in)
        body = feat.bodies.item(0)
        body.name = name
        support_bodies.append(body)

    oak_semigloss = get_appearance(design, ["Oak", "Semigloss"])
    apply_appearance(
        [feat_left_panel.bodies.item(0), feat_right_panel.bodies.item(0), *support_bodies],
        oak_semigloss,
    )

    return comp
