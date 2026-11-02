"""Deterministic format validation (PLAN-v2 §3 validation gate).

Every generated/extracted element must pass this gate before it can be
shipped; an output that fails is regenerated or fixed, never eyeballed
through. Checks are pure functions of the pixels — no model judgment:

- corners fully transparent (alpha == 0): catches baked backgrounds.
- no near-white halo fringe: semi-transparent near-white pixels sitting
  on the boundary of the opaque region (classic matting artefact from
  cutting an element off a white ground).
- line layers are linework only: every covered pixel is pure black.
"""

from __future__ import annotations

from PIL import Image


def _boundary_mask(alpha: Image.Image) -> set[tuple[int, int]]:
    """Coordinates of covered pixels that touch a fully transparent one."""
    w, h = alpha.size
    px = alpha.load()
    boundary = set()
    for y in range(h):
        for x in range(w):
            if px[x, y] == 0:
                continue
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < w and 0 <= ny < h and px[nx, ny] == 0:
                    boundary.add((x, y))
                    break
    return boundary


def check_corners(image: Image.Image) -> list[str]:
    rgba = image.convert("RGBA")
    w, h = rgba.size
    alpha = rgba.getchannel("A")
    bad = [(x, y) for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))
           if alpha.getpixel((x, y)) != 0]
    if bad:
        return [f"corners not transparent at {bad}: alpha must be 0 "
                f"(baked background?)"]
    return []


def check_halo(image: Image.Image, white_threshold: int = 240,
               alpha_ceiling: int = 200) -> list[str]:
    rgba = image.convert("RGBA")
    px = rgba.load()
    count = 0
    for x, y in _boundary_mask(rgba.getchannel("A")):
        r, g, b, a = px[x, y]
        if 0 < a < alpha_ceiling and min(r, g, b) > white_threshold:
            count += 1
    if count:
        return [f"near-white halo fringe: {count} semi-transparent "
                f"near-white boundary pixels"]
    return []


def check_line_layer(image: Image.Image) -> list[str]:
    """Line layers: every covered pixel must be pure black (0,0,0)."""
    rgba = image.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    bad = 0
    first = None
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 0 and (r, g, b) != (0, 0, 0):
                bad += 1
                if first is None:
                    first = (x, y, (r, g, b, a))
    if bad:
        return [f"line layer not pure black: {bad} covered pixels with "
                f"non-black colour, first at {first}"]
    return []


def validate_element(image: Image.Image, role: str = "art") -> list[str]:
    """Validate one element image. Returns a list of violations;
    an empty list means the element passes the §3 gate."""
    violations = check_corners(image) + check_halo(image)
    if role == "line":
        violations += check_line_layer(image)
    return violations


def validate_document(doc) -> list[str]:
    """Validate every layer's element plus the document composite."""
    violations: list[str] = []
    for layer in doc.layers:
        # A stamp's stored pixels are a luminance mask, not a picture;
        # validate what the stamp renders as (tint x mask), not the mask.
        # The pure-black rule binds line RASTERS: a stamp's colour is a
        # render-time tint choice, and its stencil blackness comes from
        # the mask's alpha — which export_stencil's output check proves.
        element = layer.content_image() if layer.kind == "stamp" else layer.image
        effective_role = layer.role if layer.kind == "raster" else "art"
        for v in validate_element(element, role=effective_role):
            violations.append(f"layer {layer.id} ({layer.name}): {v}")
    for v in check_corners(doc.render()):
        violations.append(f"composite: {v}")
    return violations
