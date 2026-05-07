"""Shared builder for rail-and-stile frames with a recessed centre panel
and tongue-and-groove joinery.

Used by drawer_front and (eventually) doors — their construction is the
same: two full-height stiles with two rails running between them, plus
a thin centre panel offset from the front face.

Joinery:
  - A groove runs along the inner (panel-facing) edge of each rail and
    stile, 3/8" deep × 1/4" wide by default, centred on the frame
    thickness so front and back walls are equal. Stile grooves go full
    height (through).
  - Each rail has a tongue on each end that slides into the stile
    groove. The tongues are haunched — shortened at the corner-facing
    end — so they don't collide with the panel's corner tongue.
  - The panel has a continuous picture-frame tongue around all 4 edges
    (no notches at the corners), flush with the panel's front face so
    the panel's back sits flush with the back of the frame.

Orientation (matches the base cabinet's front):
  X = width   (left to right)
  Y = thickness (front at Y=0, back at Y=+frame_thickness)
  Z = height  (bottom to top)
"""

import adsk.core
import adsk.fusion

from lib.units import inches


def build_frame_panel(
    root: adsk.fusion.Component,
    width_in: float,
    height_in: float,
    component_name: str,
    frame_width_in: float = 2.5,
    frame_thickness_in: float = 0.75,
    panel_thickness_in: float = 0.5,
    panel_offset_in: float = 0.25,
    groove_depth_in: float = 0.375,
    groove_width_in: float = 0.25,
    placement_transform: adsk.core.Matrix3D = None,
) -> adsk.fusion.Component:
    """Build a frame-and-panel assembly inside a new child component of `root`.
    Returns the new component. See module docstring for joinery details.

    `placement_transform` positions the new occurrence inside `root`; defaults
    to identity (placed at `root`'s origin).
    """
    W  = inches(width_in)
    H  = inches(height_in)
    FW = inches(frame_width_in)
    FT = inches(frame_thickness_in)
    PT = inches(panel_thickness_in)
    PO = inches(panel_offset_in)
    GD = inches(groove_depth_in)
    GW = inches(groove_width_in)

    # Groove Y range — centred on the frame thickness.
    GY_MIN = (FT - GW) / 2
    GY_MAX = GY_MIN + GW

    if placement_transform is None:
        placement_transform = adsk.core.Matrix3D.create()
    occ = root.occurrences.addNewComponent(placement_transform)
    comp = occ.component
    comp.name = component_name

    sketches = comp.sketches
    extrudes = comp.features.extrudeFeatures
    xy_plane = comp.xYConstructionPlane
    xz_plane = comp.xZConstructionPlane

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

    def _pick_profile_xy(sketch, target_x, target_y):
        best, best_d2 = None, float('inf')
        for i in range(sketch.profiles.count):
            prof = sketch.profiles.item(i)
            c = sketch.sketchToModelSpace(prof.areaProperties().centroid)
            d2 = (c.x - target_x) ** 2 + (c.y - target_y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = prof
        return best

    # ------------------------------------------------------------------
    # FRAME: one sketch with 4 rectangles, one extrude per profile.
    # Adjacent rectangles share corner edges; extruding them together
    # would merge them into a single body. We want 4 named bodies.
    # ------------------------------------------------------------------
    frame_sketch = sketches.add(xz_plane)
    frame_lines = frame_sketch.sketchCurves.sketchLines

    frame_specs = [
        ("Left Stile",   0,       0,       FW,      H),
        ("Right Stile",  W - FW,  0,       W,       H),
        ("Bottom Rail",  FW,      0,       W - FW,  FW),
        ("Top Rail",     FW,      H - FW,  W - FW,  H),
    ]

    for _, x0, z0, x1, z1 in frame_specs:
        p0 = frame_sketch.modelToSketchSpace(adsk.core.Point3D.create(x0, 0, z0))
        p1 = frame_sketch.modelToSketchSpace(adsk.core.Point3D.create(x1, 0, z1))
        frame_lines.addTwoPointRectangle(
            adsk.core.Point3D.create(p0.x, p0.y, 0),
            adsk.core.Point3D.create(p1.x, p1.y, 0),
        )

    frame_bodies = {}
    for name, x0, z0, x1, z1 in frame_specs:
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        ext_in = extrudes.createInput(
            _pick_profile_xz(frame_sketch, cx, cz),
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(FT))
        feat = extrudes.add(ext_in)
        body = feat.bodies.item(0)
        body.name = name
        frame_bodies[name] = body

    # ------------------------------------------------------------------
    # GROOVES: cut a slot into each frame piece's inner edge. Each cut
    # is sketched on XY and extruded down through the appropriate Z range
    # of the target frame piece.
    #   - Stile grooves run the full height Z=0..H (through groove).
    #   - Rail grooves sit just inside the rail's inner face.
    # Cut volumes only overlap their intended frame body, so we don't
    # need to specify participantBodies.
    # ------------------------------------------------------------------
    stile_groove_sketch = sketches.add(xy_plane)
    stile_groove_lines = stile_groove_sketch.sketchCurves.sketchLines
    stile_groove_specs = [
        (FW - GD,   GY_MIN, FW,          GY_MAX),  # Left stile
        (W - FW,    GY_MIN, W - FW + GD, GY_MAX),  # Right stile
    ]
    for x0, y0, x1, y1 in stile_groove_specs:
        stile_groove_lines.addTwoPointRectangle(
            adsk.core.Point3D.create(x0, y0, 0),
            adsk.core.Point3D.create(x1, y1, 0),
        )
    for x0, y0, x1, y1 in stile_groove_specs:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        cut_in = extrudes.createInput(
            _pick_profile_xy(stile_groove_sketch, cx, cy),
            adsk.fusion.FeatureOperations.CutFeatureOperation,
        )
        cut_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(H))
        extrudes.add(cut_in)

    # Rail grooves share one XY footprint; extrude twice at different Z.
    rail_groove_sketch = sketches.add(xy_plane)
    rail_groove_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(FW,     GY_MIN, 0),
        adsk.core.Point3D.create(W - FW, GY_MAX, 0),
    )
    rail_groove_profile = rail_groove_sketch.profiles.item(0)

    for z_start in (FW - GD, H - FW):
        cut_in = extrudes.createInput(
            rail_groove_profile,
            adsk.fusion.FeatureOperations.CutFeatureOperation,
        )
        cut_in.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(z_start),
        )
        cut_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(GD))
        extrudes.add(cut_in)

    # ------------------------------------------------------------------
    # RAIL TONGUES: each rail gets a tongue on both ends that fits into
    # the stile groove. Haunched — the tongue's Z range excludes the
    # groove-width region at the panel-facing end so the panel's corner
    # tongue can tuck in without overlapping the rail tongue.
    # ------------------------------------------------------------------
    rail_tongue_sketch = sketches.add(xz_plane)
    rail_tongue_lines = rail_tongue_sketch.sketchCurves.sketchLines

    # (rail_body_name, x0, z0, x1, z1) — haunched so the panel corner fits
    rail_tongue_specs = [
        ("Bottom Rail", FW - GD,  0,             FW,           FW - GD),
        ("Bottom Rail", W - FW,   0,             W - FW + GD,  FW - GD),
        ("Top Rail",    FW - GD,  H - FW + GD,   FW,           H),
        ("Top Rail",    W - FW,   H - FW + GD,   W - FW + GD,  H),
    ]

    for _, x0, z0, x1, z1 in rail_tongue_specs:
        p0 = rail_tongue_sketch.modelToSketchSpace(adsk.core.Point3D.create(x0, 0, z0))
        p1 = rail_tongue_sketch.modelToSketchSpace(adsk.core.Point3D.create(x1, 0, z1))
        rail_tongue_lines.addTwoPointRectangle(
            adsk.core.Point3D.create(p0.x, p0.y, 0),
            adsk.core.Point3D.create(p1.x, p1.y, 0),
        )

    for rail_name, x0, z0, x1, z1 in rail_tongue_specs:
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        ext_in = extrudes.createInput(
            _pick_profile_xz(rail_tongue_sketch, cx, cz),
            adsk.fusion.FeatureOperations.JoinFeatureOperation,
        )
        ext_in.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByReal(GY_MIN),
        )
        ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(GW))
        ext_in.participantBodies = [frame_bodies[rail_name]]
        extrudes.add(ext_in)

    # ------------------------------------------------------------------
    # PANEL BODY: fills the opening, full panel thickness.
    # ------------------------------------------------------------------
    panel_body_sketch = sketches.add(xz_plane)
    pp0 = panel_body_sketch.modelToSketchSpace(
        adsk.core.Point3D.create(FW, 0, FW),
    )
    pp1 = panel_body_sketch.modelToSketchSpace(
        adsk.core.Point3D.create(W - FW, 0, H - FW),
    )
    panel_body_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(pp0.x, pp0.y, 0),
        adsk.core.Point3D.create(pp1.x, pp1.y, 0),
    )

    panel_ext_in = extrudes.createInput(
        panel_body_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    panel_ext_in.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(PO),
    )
    panel_ext_in.setDistanceExtent(
        False,
        adsk.core.ValueInput.createByReal(PT),
    )
    panel_feat = extrudes.add(panel_ext_in)
    panel_body = panel_feat.bodies.item(0)
    panel_body.name = "Panel"

    # ------------------------------------------------------------------
    # PANEL TONGUE: continuous picture-frame around the panel body. Drawn
    # as outer rectangle + inner rectangle; the picture-frame profile is
    # the one with 2 loops (outer + inner hole).
    # ------------------------------------------------------------------
    tongue_sketch = sketches.add(xz_plane)
    tongue_lines = tongue_sketch.sketchCurves.sketchLines

    op0 = tongue_sketch.modelToSketchSpace(
        adsk.core.Point3D.create(FW - GD, 0, FW - GD),
    )
    op1 = tongue_sketch.modelToSketchSpace(
        adsk.core.Point3D.create(W - FW + GD, 0, H - FW + GD),
    )
    tongue_lines.addTwoPointRectangle(
        adsk.core.Point3D.create(op0.x, op0.y, 0),
        adsk.core.Point3D.create(op1.x, op1.y, 0),
    )

    ip0 = tongue_sketch.modelToSketchSpace(
        adsk.core.Point3D.create(FW, 0, FW),
    )
    ip1 = tongue_sketch.modelToSketchSpace(
        adsk.core.Point3D.create(W - FW, 0, H - FW),
    )
    tongue_lines.addTwoPointRectangle(
        adsk.core.Point3D.create(ip0.x, ip0.y, 0),
        adsk.core.Point3D.create(ip1.x, ip1.y, 0),
    )

    tongue_frame_profile = None
    for i in range(tongue_sketch.profiles.count):
        prof = tongue_sketch.profiles.item(i)
        if prof.profileLoops.count > 1:
            tongue_frame_profile = prof
            break

    tongue_ext_in = extrudes.createInput(
        tongue_frame_profile,
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
    )
    tongue_ext_in.startExtent = adsk.fusion.OffsetStartDefinition.create(
        adsk.core.ValueInput.createByReal(GY_MIN),
    )
    tongue_ext_in.setDistanceExtent(
        False,
        adsk.core.ValueInput.createByReal(GW),
    )
    tongue_ext_in.participantBodies = [panel_body]
    extrudes.add(tongue_ext_in)

    return comp
