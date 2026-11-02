"""Slice S6 — outline-first workflow + closed-contour measurement
(REVIEW-GBT-CANVAS §2 D; Director-review §7).

Outline-first: an artist generates or uploads a composition, takes a
clean outline from it, and develops the piece progressively. The
outline becomes the LOCKED structural reference (document.py's
`set_structural_outline`, S5 locking underneath) and shading work
must reference it: `shading_plan` refuses to plan shading for a
document whose outline is set unless the plan names that outline.
The outline stays exportable at any stage — `export_stencil` reads
visible line layers only, so a developed, shaded document still
yields exactly its outline (proven byte-identical, shading on/off).

`measure_contours` is a REPORT, never a verdict on stencil-worthiness
(verdict is always "report"; the artist decides — REVIEW §7 warns
the metric can misread stipple/whip textures, and edge detection
alone is never called a finished stencil here).

METHOD (flood-fill enclosure, deterministic): ink = covered pixels
(alpha > 10) of the line image. Background (~ink) is labelled with
4-connectivity; components that touch the image border are exterior.
Remaining background components are ENCLOSED regions — areas fully
surrounded by ink — and each is one closed contour.
  contour_count  = number of enclosed background components
  enclosed_px    = their total area
  closed_ratio   = enclosed area / background area inside the ink's
                   bounding box (0.0 when there is no ink): how much
                   of the region the linework spans is sealed off
                   from the outside.
LIMITS, stated plainly: a filled black disc encloses nothing (its
interior is ink, not background) and reports 0; a ring with a 1-px
gap leaks and also reports 0 — both are the method working as
defined, and both are why the artist, not this number, judges a
stencil. Gap size/count are NOT estimated: flood-fill enclosure
cannot locate or size a gap defensibly (a leak says "not closed",
never where), so gap_count and largest_gap_px are reported as None
rather than invented.
"""

from __future__ import annotations


def set_structural_outline(doc, layer_id: str) -> str:
    """Mark a line layer as the document's structural outline —
    delegates to the document op (which locks the layer, records
    the op, and persists the id in the manifest)."""
    return doc.set_structural_outline(layer_id)


def shading_plan(doc, targets=None, outline_ref: str | None = None) -> dict:
    """Plan shading work for a document, respecting outline-first.

    If the document has a structural outline, the plan MUST
    reference it: `outline_ref` must equal the outline's layer id,
    and passing nothing (or a different id) raises ValueError —
    shading that ignores the locked geometry is refused at plan
    time, not discovered after the fact. With no outline set, a
    plan is produced with outline_ref None.

    The plan records what a generation would be built against:
    the outline reference and a copy of the document's lighting
    spec (or None), plus the requested shading targets (element
    subjects or layer ids to shade). Planning generates nothing.
    """
    if doc.outline_layer is not None and outline_ref != doc.outline_layer:
        raise ValueError(
            f"document {doc.id!r} has structural outline "
            f"{doc.outline_layer!r}; a shading plan must reference it "
            f"(outline_ref={doc.outline_layer!r}), got {outline_ref!r}")
    import copy

    return {
        "doc_id": doc.id,
        "outline_ref": outline_ref if doc.outline_layer is not None else outline_ref,
        "lighting": copy.deepcopy(doc.lighting),
        "targets": list(targets or []),
    }


def measure_contours(line_rgba, max_measure_px: int = 1000) -> dict:
    """Closed-contour report for a line layer — see the module
    docstring for the flood-fill method and its stated limits.

    Large inputs are measured on a NEAREST reduction to
    <= max_measure_px on the long side; areas and ratios come from
    the measured image and `measured_size` says what that was.
    Verdict is ALWAYS "report"."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    img = line_rgba.convert("RGBA")
    if max(img.size) > max_measure_px:
        scale = max_measure_px / max(img.size)
        img = img.resize((max(1, round(img.width * scale)),
                          max(1, round(img.height * scale))),
                         Image.NEAREST)
    arr = np.asarray(img)
    ink = arr[..., 3] > 10
    result = {
        "method": "flood-fill enclosure (4-connected background "
                  "components not touching the border)",
        "measured_size": [img.width, img.height],
        "ink_pixels": int(ink.sum()),
        "contour_count": 0,
        "enclosed_px": 0,
        "closed_ratio": 0.0,
        "gap_count": None,
        "largest_gap_px": None,
        "verdict": "report",
    }
    if not ink.any():
        return result
    background = ~ink
    labels, count = ndimage.label(background)
    if count == 0:
        return result
    border = (set(labels[0, :]) | set(labels[-1, :])
              | set(labels[:, 0]) | set(labels[:, -1]))
    border.discard(0)
    enclosed_labels = [lab for lab in range(1, count + 1) if lab not in border]
    if not enclosed_labels:
        return result
    enclosed_mask = np.isin(labels, enclosed_labels)
    enclosed_px = int(enclosed_mask.sum())
    ys, xs = np.where(ink)
    bbox_bg = int(background[ys.min():ys.max() + 1, xs.min():xs.max() + 1].sum())
    result["contour_count"] = len(enclosed_labels)
    result["enclosed_px"] = enclosed_px
    result["closed_ratio"] = round(enclosed_px / bbox_bg, 4) if bbox_bg else 0.0
    return result
