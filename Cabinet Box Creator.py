"""This file acts as the main module for this script."""

import traceback
import adsk.core
import adsk.fusion
# import adsk.cam

# Initialize the global variables for the Application and UserInterface objects.
# app = adsk.core.Application.get()
# ui  = app.userInterface

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IN_TO_CM = 2.54          # Fusion 360 internal unit is cm
MM_TO_IN = 1.0 / 25.4   # millimetres → inches

# Hard-coded values that are never prompted for.
# Each entry maps a values-dict key to its fixed value in inches.
# Add new entries here as needed.
FIXED_VALUES: dict[str, float] = {
    "Thickness": 18 * MM_TO_IN,       # 18 mm material thickness
    "Depth":     24,                  # 24 inches
    "Height":    30.5,                # 30.5 inches
    "FaceFrameOverlap": 0.25,         # 0.25 inch face frame overlap on front of box
    "FaceFrameThickness": 0.75,       # 0.75 inch face frame thickness (extends forward of box)
    "FaceFrameWidth": 1.5,            # 1.5 inch wide face frame members
}


def inches(val: float) -> float:
    """Convert inches to centimeters for Fusion API calls."""
    return val * IN_TO_CM
 
 
# ---------------------------------------------------------------------------
# Dialog helpers
# ---------------------------------------------------------------------------
 
def get_inputs(ui: adsk.core.UserInterface) -> dict | None:
    """Show a series of InputBox dialogs to collect cabinet dimensions."""
 
    fields = [
        ("Cabinet Width (inches)",    "Width",         "24"),
    ]

    # Seed with hard-coded values so they're available before prompts run.
    values: dict[str, float] = dict(FIXED_VALUES)

    for prompt, key, default in fields:
        result, cancelled = ui.inputBox(prompt, "Cabinet Box Generator", default)
        if cancelled:
            return None
        try:
            values[key] = float(result)
        except ValueError:
            ui.messageBox(f'Invalid value for {key}: "{result}". Script cancelled.')
            return None
 
    # Basic validation
    T = values["Thickness"]
    if values["Width"] <= T * 2:
        ui.messageBox("Width must be greater than 2× material thickness.")
        return None
    if values["Height"] <= T * 2:
        ui.messageBox("Height must be greater than 2× material thickness.")
        return None
    return values
 
 
# ---------------------------------------------------------------------------
# Parameter helpers
# ---------------------------------------------------------------------------
 
def add_or_update_param(
    params: adsk.fusion.UserParameters,
    name: str,
    value_in: float,
    unit: str,
    comment: str,
) -> adsk.fusion.UserParameter:
    """Create or overwrite a user parameter (value in inches, stored as cm)."""
    existing = params.itemByName(name)
    val_input = adsk.core.ValueInput.createByReal(inches(value_in))
    if existing:
        existing.value = inches(value_in)
        return existing
    return params.add(name, val_input, unit, comment)
 
 
# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
 
def extrude_profile(
    extrudes: adsk.fusion.ExtrudeFeatures,
    profile: adsk.fusion.Profile,
    depth_cm: float,
    operation: adsk.fusion.FeatureOperations = adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    target_bodies=None,
) -> adsk.fusion.ExtrudeFeature:
    """Extrude a profile by depth_cm along +Z. Returns the feature."""
    ext_input = extrudes.createInput(profile, operation)
    ext_input.setDistanceExtent(
        False,
        adsk.core.ValueInput.createByReal(depth_cm),
    )
    if target_bodies:
        ext_input.participantBodies = target_bodies
    return extrudes.add(ext_input)
 
 
def sketch_rect_xy(
    sketches: adsk.fusion.Sketches,
    plane,
    x0: float, y0: float,
    x1: float, y1: float,
) -> adsk.fusion.Sketch:
    """Add a sketch on *plane* with a single rectangle (all values in cm)."""
    sk = sketches.add(plane)
    lines = sk.sketchCurves.sketchLines
    lines.addTwoPointRectangle(
        adsk.core.Point3D.create(x0, y0, 0),
        adsk.core.Point3D.create(x1, y1, 0),
    )
    return sk

def get_face_sketch_bounds(
    sketch: adsk.fusion.Sketch,
    face: adsk.fusion.BRepFace,
) -> tuple[adsk.core.Point3D, adsk.core.Point3D]:
    """
    Return (min_pt, max_pt) of a BRepFace in the local coordinate space
    of a sketch that was created on that face.

    Both points are 2D-safe Point3D objects (Z=0) ready for use in
    sketchCurves calls.

    Usage:
        face_sketch = sketches.add(some_face)
        min_pt, max_pt = get_face_sketch_bounds(face_sketch, some_face)
        lines.addTwoPointRectangle(min_pt, max_pt)
    """
    bbox = face.boundingBox
    min_local = sketch.modelToSketchSpace(bbox.minPoint)
    max_local = sketch.modelToSketchSpace(bbox.maxPoint)

    # Force Z=0 — modelToSketchSpace should already do this but be explicit
    return (
        adsk.core.Point3D.create(min_local.x, min_local.y, 0),
        adsk.core.Point3D.create(max_local.x, max_local.y, 0),
    )

def find_face_by_normal(body, nx, ny, nz, tol=0.001):
    for face in body.faces:
        plane = adsk.core.Plane.cast(face.geometry)
        if plane:
            n = plane.normal
            if abs(n.x - nx) < tol and abs(n.y - ny) < tol and abs(n.z - nz) < tol:
                return face
    return None


# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------

def build_cabinet(
    root: adsk.fusion.Component,
    vals: dict,
    ui: adsk.core.UserInterface,
) -> adsk.fusion.Component:
    """
    Build all cabinet panels inside a new child component.
    Returns the new component.
    """
 
    WIDTH   = inches(vals["Width"])
    H   = inches(vals["Height"])
    DEPTH   = inches(vals["Depth"])
    THICKNESS   = inches(vals["Thickness"])
    FF_OVERLAP  = inches(vals["FaceFrameOverlap"])
    FF_THICK = inches(vals["FaceFrameThickness"])
    FF_WIDTH = inches(vals["FaceFrameWidth"])

    # Create a dedicated component for this cabinet
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    comp = occ.component
    comp.name = (
        f"Cabinet_{vals['Width']:.4g}x{vals['Height']:.4g}x{vals['Depth']:.4g}"
    )
 
    sketches = comp.sketches
    extrudes = comp.features.extrudeFeatures
    xy_plane = comp.xYConstructionPlane  # XY → bottom of cabinet
    xz_plane = comp.xZConstructionPlane  # XZ → top-down view (plan)

    # Centerline mirror plane at X = WIDTH/2, reused for all left↔right mirrors.
    planes = comp.constructionPlanes
    centerline_input = planes.createInput()
    centerline_input.setByOffset(
        comp.yZConstructionPlane,
        adsk.core.ValueInput.createByReal(WIDTH / 2),
    )
    centerline_plane = planes.add(centerline_input)
    centerline_plane.name = "Cabinet Centerline"

    # ------------------------------------------------------------------
    # FACEFRAME - LEFT SIDE STYLE
    # ------------------------------------------------------------------
    sk_ff_left_style = sketch_rect_xy(sketches, xy_plane, 0, 0, FF_WIDTH, FF_THICK)
    feat_ff_left_style = extrude_profile(extrudes, sk_ff_left_style.profiles.item(0), H+FF_OVERLAP)
    feat_ff_left_style.bodies.item(0).name = "Left Style"

    # ------------------------------------------------------------------
    # FACEFRAME - RIGHT SIDE STYLE (mirror of left across centerline)
    # ------------------------------------------------------------------
    style_mirror_bodies = adsk.core.ObjectCollection.create()
    style_mirror_bodies.add(feat_ff_left_style.bodies.item(0))
    style_mirror_input = comp.features.mirrorFeatures.createInput(style_mirror_bodies, centerline_plane)
    feat_ff_right_style = comp.features.mirrorFeatures.add(style_mirror_input)
    feat_ff_right_style.bodies.item(0).name = "Right Style"

    # ------------------------------------------------------------------
    # FACEFRAME - TOP & BOTTOM RAILS (one sketch, one extrude, two bodies)
    # ------------------------------------------------------------------
    left_style = feat_ff_left_style.bodies.item(0)
    left_style_inner_face = find_face_by_normal(left_style, 1, 0, 0)
    right_style = feat_ff_right_style.bodies.item(0)
    right_style_inner_face = find_face_by_normal(right_style, -1, 0, 0)

    rails_sketch = sketches.add(left_style_inner_face)
    min_pt, max_pt = get_face_sketch_bounds(rails_sketch, left_style_inner_face)

    rails_lines = rails_sketch.sketchCurves.sketchLines
    # Bottom rail
    rails_lines.addTwoPointRectangle(
        adsk.core.Point3D.create(min_pt.x, min_pt.y, 0),
        adsk.core.Point3D.create(max_pt.x, min_pt.y + FF_WIDTH, 0),
    )
    # Top rail
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

    rails_ext_input = extrudes.createInput(
        rail_profs,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    rails_ext_input.setOneSideToExtent(right_style_inner_face, False)
    feat_rails = extrudes.add(rails_ext_input)

    # Name the two resulting bodies by centroid Z (model space): lower = bottom rail
    rail_bodies = sorted(
        (feat_rails.bodies.item(i) for i in range(feat_rails.bodies.count)),
        key=lambda b: b.physicalProperties.centerOfMass.z,
    )
    rail_bodies[0].name = "Bottom Rail"
    rail_bodies[1].name = "Top Rail"


    # ------------------------------------------------------------------
    # LEFT SIDE  (x=0, full height, full depth)
    # ------------------------------------------------------------------

    # Sketch the left-side panel footprint on the XY plane (top-down view):
    #   X: FF_OVERLAP .. FF_OVERLAP + THICKNESS
    #   Y: FF_THICK   .. DEPTH
    # Then extrude upward in +Z for height H, starting at Z = FF_OVERLAP.
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
    panel_mirror_input = comp.features.mirrorFeatures.createInput(panel_mirror_bodies, centerline_plane)
    feat_right_panel = comp.features.mirrorFeatures.add(panel_mirror_input)
    feat_right_panel.bodies.item(0).name = "Right Panel"
 
    # ------------------------------------------------------------------
    # BOTTOM PANEL  (sits between sides, flush with bottom)
    # Top face at y = T (thickness), so it tucks between the side panels.
    # ------------------------------------------------------------------
    # left_side_body = feat_l.bodies.item(0)

    # inner_face = find_face_by_normal(left_side_body, 1, 0, 0)

    # face_sketch = sketches.add(inner_face)
    # min_pt, max_pt = get_face_sketch_bounds(face_sketch, inner_face)

    # lines = face_sketch.sketchCurves.sketchLines
    # lines.addTwoPointRectangle(
    #     adsk.core.Point3D.create(min_pt.x, min_pt.y, 0),
    #     adsk.core.Point3D.create(max_pt.x, min_pt.y + 1.8, 0),
    # )

    # # Get the inner face of the right side (the -X facing face)
    # right_side_body = feat_r.bodies.item(0)
    # right_inner_face = find_face_by_normal(right_side_body, -1, 0, 0)

    # prof = face_sketch.profiles.item(0)
    # ext_input = extrudes.createInput(
    #     prof,
    #     adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    # )

    # # Extrude "to object" — terminates exactly at the right side's inner face
    # ext_input.setOneSideToExtent(right_inner_face, False)

    # feat_b = extrudes.add(ext_input)
    # feat_b.bodies.item(0).name = "Bottom Panel"

    ################################## 

    # ------------------------------------------------------------------
    # TOP PANEL  (between sides, at top)
    # ------------------------------------------------------------------
    # sk_t = sketch_rect_xy(sketches, xy_plane, THICKNESS, 0, WIDTH - THICKNESS, DEPTH)
    # feat_t = extrude_profile(extrudes, sk_t.profiles.item(0), THICKNESS)
    # # Move to top: we'll offset it using a move body feature
    # bodies = comp.bRepBodies
    # top_body = feat_t.bodies.item(0)
    # top_body.name = "Top Panel"
 
    # Translate top panel up to H - THICKNESS
    # transform = adsk.core.Matrix3D.create()
    # transform.translation = adsk.core.Vector3D.create(0, 0, H - THICKNESS)
    # move_feats = comp.features.moveFeatures
    # body_coll = adsk.core.ObjectCollection.create()
    # body_coll.add(top_body)
    # move_input = move_feats.createInput(body_coll, transform)
    # move_feats.add(move_input)
 
    return comp
 

def test_function(app, ui, design):
    root = design.rootComponent

    sketches = root.sketches
    extrudes = root.features.extrudeFeatures
    xy = root.xYConstructionPlane

    sk = sketches.add(xy)
    lines = sk.sketchCurves.sketchLines

    x = 0
    y = 0
    w = 45.72
    h = 60.96
    depth = 60.96
    t = 1.8

    lines.addTwoPointRectangle(
            adsk.core.Point3D.create(x, y, 0),
            adsk.core.Point3D.create(x + w, y + h, 0)
        )
    prof = sk.profiles.item(0)
    ext_in = extrudes.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    ext_in.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(t)
    )
    extrudes.add(ext_in)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
 
def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)

        if not design:
            ui.messageBox(
                "No active Fusion 360 design found.\n"
                "Please open or create a design first.",
                "Cabinet Box Generator",
            )
            return
        

        #######################################
        
        # test_function(app, ui, design)

        # return



        #########################################################

        # Collect inputs
        vals = get_inputs(ui)
        if vals is None:
            return  # user cancelled

        # Store named user parameters in the design
        params = design.userParameters
        param_map = {
            "CabWidth":      ("Width",         "Width (in)"),
            "CabHeight":     ("Height",        "Height (in)"),
            "CabDepth":      ("Depth",         "Depth (in)"),
            "MatThickness":  ("Thickness",     "Material thickness (in)"),
        }
        for param_name, (val_key, comment) in param_map.items():
            add_or_update_param(params, param_name, vals[val_key], "cm", comment)

        # Build the cabinet geometry
        root = design.rootComponent
        cab_comp = build_cabinet(root, vals, ui)

        # ui.messageBox(
        #     f'Cabinet created successfully!\n\n'
        #     f'Component: {cab_comp.name}\n'
        #     f'  Width:  {vals["Width"]}" | Height: {vals["Height"]}" | Depth: {vals["Depth"]}"\n'
        #     f'  Material: {vals["Thickness"]}"\n\n'
        #     f'Named parameters have been added to your design.\n'
        #     f'Edit them under Modify → Change Parameters.',
        #     "Cabinet Box Generator",
        # )

    except Exception:  # pylint: disable=broad-except
        if ui:
            ui.messageBox(
                "Script failed with error:\n\n" + traceback.format_exc(),
                "Cabinet Box Generator – Error",
            )
    finally:
        pass