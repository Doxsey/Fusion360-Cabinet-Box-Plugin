"""Appearance lookup and assignment helpers."""

import adsk.core
import adsk.fusion


_appearance_cache: dict[str, adsk.core.Appearance] = {}


def get_appearance(design: adsk.fusion.Design, search_terms: list[str]) -> adsk.core.Appearance | None:
    """Return an appearance whose name contains all *search_terms* (case-insensitive).

    Searches appearances already in the design first, then copies from the
    Fusion appearance library on a miss. Results are cached per process.
    """
    key = "|".join(t.lower() for t in search_terms)
    if key in _appearance_cache:
        return _appearance_cache[key]

    def _matches(name: str) -> bool:
        n = name.lower()
        return all(t.lower() in n for t in search_terms)

    for i in range(design.appearances.count):
        app_item = design.appearances.item(i)
        if _matches(app_item.name):
            _appearance_cache[key] = app_item
            return app_item

    app = adsk.core.Application.get()
    for lib_name in ("Fusion Appearance Library", "Fusion 360 Appearance Library"):
        lib = app.materialLibraries.itemByName(lib_name)
        if not lib:
            continue
        for i in range(lib.appearances.count):
            lib_app = lib.appearances.item(i)
            if _matches(lib_app.name):
                copied = design.appearances.addByCopy(lib_app, lib_app.name)
                _appearance_cache[key] = copied
                return copied
    return None


def apply_appearance(bodies, appearance: adsk.core.Appearance) -> None:
    """Assign *appearance* to each body in the iterable."""
    if not appearance:
        return
    for body in bodies:
        body.appearance = appearance
