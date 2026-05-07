"""Sketch and face helpers shared by all builders."""

import adsk.core
import adsk.fusion


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
    """Return (min_pt, max_pt) of a BRepFace in *sketch*'s local space."""
    bbox = face.boundingBox
    min_local = sketch.modelToSketchSpace(bbox.minPoint)
    max_local = sketch.modelToSketchSpace(bbox.maxPoint)
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
