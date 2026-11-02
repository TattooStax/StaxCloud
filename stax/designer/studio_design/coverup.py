"""Slice S8 — cover-up workspace (REVIEW-GBT-CANVAS §2 F; GBT §5).

A cover-up is designed AGAINST the tattoo being covered, not from a
separate picture the artist glances at. A session is an ordinary
DesignDoc plus a CoverUpRecord: the photograph of the existing
tattoo rides in the document as a layer with the new role
'reference' (document.py), and everything else is built on top.

THE REFERENCE IS AN UNDERLAY, NEVER ARTWORK. It is LOCKED on
creation (S5 — transform/reorder/remove/opacity all refuse), and
document.render skips reference layers unconditionally, so it can
appear in no share, preview, PSD or stencil. The artist sees it
only through this module's `render_overlay` — the deliberate
working view (reference at its overlay opacity under the design).

OVERLAY OPACITY is the one sanctioned exception to the lock:
`set_reference_opacity` performs the change through the document's
own lock/unlock/set_opacity ops (so the audit trail shows exactly
what happened) and then appends a `coverup.reference_opacity` op
naming the sanctioned path. There is no other back door in here.

CALIBRATION: the record stores the reference's physical size
(width/height in mm, orientation, curvature and skin notes).
`calibration` derives px-per-mm from the document's own DPI and
reports the reference's expected pixel size at that scale plus the
scale factor that would fit the photo to it via the existing
transform ops — scaling the DESIGN against the reference stays an
ordinary layer.transform, nothing special is invented here.

DARKNESS MAP — method and limits, stated plainly. A pixel's ink
darkness estimate is 255 minus its luminance: pure black ink reads
255, blank paper-white reads 0. A pixel counts as "dark" when its
darkness is >= the record's threshold (default 128). This is an
ESTIMATE for the artist: photograph lighting, white balance, skin
tone and glare all move luminance without moving real pigment, and
a dark reading cannot distinguish old ink from shadow. Nothing in
this module calls the map a measurement of the tattoo itself.

COVERAGE ANALYSIS compares like with like. The old tattoo's dark
pixels come from the reference as PLACED in the document (rendered
at full opacity; canvas outside the photo is not skin and never
counts). The new design's darkness comes from share_canvas — the
design WITHOUT the reference — with each pixel's darkness weighted
by its alpha (a half-transparent black pixel covers half as much).
An old-dark pixel is INSUFFICIENTLY covered when the design's
darkness there is less than the old darkness minus a margin
(COVERAGE_MARGIN, 10/255: near-equal darkness counts as covered,
because the comparison itself is an estimate). The highlight image
marks exactly those pixels in a warning colour; it is a working
aid, exported separately, and is never part of the design.

NO GUARANTEE. Every record carries GUARANTEE_NOTE verbatim, it
round-trips through the record's JSON, and it is written into the
exported design bundle (a `coverup.json` sidecar entry next to
manifest.json — the document format has no notes field, and the
format was NOT changed for this; the note also rides in the export
result record). Coverage cannot be promised from a photograph —
see the note.

Records are plain JSON dicts via CoverUpRecord (`to_dict` /
`from_dict`), so a host can store them beside the document, the
same pattern as every other slice's records.
"""

from __future__ import annotations

import io
import json
import zipfile

from PIL import Image, ImageChops

from .document import DesignDoc, LockedError  # noqa: F401  (re-exported for hosts)

# A design pixel covers an old-dark pixel when its darkness is at
# least the old darkness minus this margin. Small, because the
# darkness figures on both sides are estimates from pixels.
COVERAGE_MARGIN = 10

# Default darkness threshold (0..255 scale): at or above = "dark".
DEFAULT_DARKNESS_THRESHOLD = 128

# Highlight colour for insufficiently covered old ink.
WARNING_COLOR = (255, 64, 32, 255)

GUARANTEE_NOTE = (
    "Coverage cannot be guaranteed from a photograph alone. "
    "Existing pigment density, skin condition, healing, and "
    "achievable saturation must be judged by the artist."
)


def px_per_mm(doc: DesignDoc) -> float:
    """Pixels per millimetre at the document's own DPI — the scale
    every calibration figure in this module derives from."""
    return doc.dpi / 25.4


# ---------------------------------------------------------------------
# The session record
# ---------------------------------------------------------------------

class CoverUpRecord:
    """One cover-up session: which document, which reference layer,
    and the photo's calibration. `guarantee_note` is not a setting —
    it is part of the record's substance and is always written."""

    def __init__(
        self,
        coverup_id: str,
        doc_id: str,
        reference_layer_id: str,
        source_ref: str = "",
        physical_width_mm: float = 0.0,
        physical_height_mm: float = 0.0,
        orientation_deg: float = 0.0,
        curvature_note: str = "",
        skin_note: str = "",
        threshold: int = DEFAULT_DARKNESS_THRESHOLD,
    ):
        if not coverup_id:
            raise ValueError("coverup_id must be non-empty")
        if not doc_id:
            raise ValueError("doc_id must be non-empty")
        if not reference_layer_id:
            raise ValueError("reference_layer_id must be non-empty")
        if physical_width_mm <= 0 or physical_height_mm <= 0:
            raise ValueError("reference physical size must be positive (mm)")
        if not 0 <= int(threshold) <= 255:
            raise ValueError("threshold must be within 0..255")
        self.coverup_id = str(coverup_id)
        self.doc_id = str(doc_id)
        self.reference = {
            "source_ref": str(source_ref),
            "reference_layer_id": str(reference_layer_id),
            "physical_width_mm": float(physical_width_mm),
            "physical_height_mm": float(physical_height_mm),
            "orientation_deg": float(orientation_deg),
            "curvature_note": str(curvature_note),
            "skin_note": str(skin_note),
        }
        self.threshold = int(threshold)
        self.guarantee_note = GUARANTEE_NOTE

    @property
    def reference_layer_id(self) -> str:
        return self.reference["reference_layer_id"]

    # -- JSON ---------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "coverup_id": self.coverup_id,
            "doc_id": self.doc_id,
            "reference": dict(self.reference),
            "threshold": self.threshold,
            "guarantee_note": self.guarantee_note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CoverUpRecord":
        ref = data["reference"]
        record = cls(
            coverup_id=data["coverup_id"],
            doc_id=data["doc_id"],
            reference_layer_id=ref["reference_layer_id"],
            source_ref=ref.get("source_ref", ""),
            physical_width_mm=ref["physical_width_mm"],
            physical_height_mm=ref["physical_height_mm"],
            orientation_deg=ref.get("orientation_deg", 0.0),
            curvature_note=ref.get("curvature_note", ""),
            skin_note=ref.get("skin_note", ""),
            threshold=data.get("threshold", DEFAULT_DARKNESS_THRESHOLD),
        )
        # The note is substance, not data: whatever a stored record
        # says, the live record carries the note verbatim.
        record.guarantee_note = GUARANTEE_NOTE
        return record

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "CoverUpRecord":
        return cls.from_dict(json.loads(text))


# ---------------------------------------------------------------------
# Session setup
# ---------------------------------------------------------------------

def create_coverup(
    doc: DesignDoc,
    coverup_id: str,
    reference_image: Image.Image,
    source_ref: str = "",
    physical_width_mm: float = 0.0,
    physical_height_mm: float = 0.0,
    orientation_deg: float = 0.0,
    curvature_note: str = "",
    skin_note: str = "",
    threshold: int = DEFAULT_DARKNESS_THRESHOLD,
) -> CoverUpRecord:
    """Open a cover-up session on `doc`: the reference photo becomes
    the BOTTOM layer of the stack (an underlay is underneath by
    definition), with role 'reference', and is LOCKED before this
    returns — add / reorder / lock are the recorded ops, in that
    order. Scaling or moving the photo afterwards is refused like
    any locked layer; alignment happens by transforming the DESIGN
    layers against it, which is the workflow the workspace exists
    for."""
    # Validate the record fields BEFORE the document is touched, so
    # a bad calibration can never leave a stray reference layer
    # behind: a probe record with a placeholder layer id runs the
    # same constructor validation the real record will.
    CoverUpRecord(
        coverup_id=coverup_id, doc_id=doc.id, reference_layer_id="probe",
        source_ref=source_ref, physical_width_mm=physical_width_mm,
        physical_height_mm=physical_height_mm,
        orientation_deg=orientation_deg, curvature_note=curvature_note,
        skin_note=skin_note, threshold=threshold)
    layer_id = doc.add_raster(
        "cover-up reference", reference_image, role="reference",
        provenance={"source": "cover-up-reference", "source_ref": source_ref})
    if len(doc.layers) > 1:
        doc.reorder(layer_id, 0)
    doc.lock_layer(layer_id)
    return CoverUpRecord(
        coverup_id=coverup_id, doc_id=doc.id,
        reference_layer_id=layer_id, source_ref=source_ref,
        physical_width_mm=physical_width_mm,
        physical_height_mm=physical_height_mm,
        orientation_deg=orientation_deg, curvature_note=curvature_note,
        skin_note=skin_note, threshold=threshold)


def calibration(doc: DesignDoc, record: CoverUpRecord) -> dict:
    """The session's scale figures, all derived from the doc's DPI:
    px-per-mm, the pixel size the reference SHOULD occupy at its
    recorded physical size, its actual placed size, and the scale
    factor a layer.transform would need to fit photo to record."""
    layer = doc.get(record.reference_layer_id)
    ppm = px_per_mm(doc)
    expected = (round(record.reference["physical_width_mm"] * ppm),
                round(record.reference["physical_height_mm"] * ppm))
    placed = layer.placed_bbox()
    placed_size = (placed[2] - placed[0], placed[3] - placed[1])
    fit_scale = (expected[0] / placed_size[0]) if placed_size[0] else 1.0
    return {
        "px_per_mm": ppm,
        "dpi": doc.dpi,
        "expected_reference_px": expected,
        "placed_reference_px": placed_size,
        "fit_scale": fit_scale,
    }


def set_reference_opacity(doc: DesignDoc, record: CoverUpRecord, value: float) -> None:
    """THE sanctioned lock exception: set the reference's overlay
    opacity. A direct doc.set_opacity on the locked reference raises
    LockedError (S5); this path unlocks through the document's own op, sets the
    opacity, relocks, and appends a `coverup.reference_opacity` op
    so the audit trail names the exception for what it is. An
    out-of-range value raises ValueError from set_opacity with the
    layer relocked and its opacity unchanged."""
    layer = doc.get(record.reference_layer_id)
    was_locked = layer.locked
    if was_locked:
        doc.unlock_layer(layer.id)
    try:
        doc.set_opacity(layer.id, value)
    finally:
        if was_locked:
            doc.lock_layer(layer.id)
    doc.ops_log.append({"op": "coverup.reference_opacity",
                        "id": layer.id, "opacity": float(value)})


def render_overlay(doc: DesignDoc, record: CoverUpRecord) -> Image.Image:
    """The working view — the ONLY sanctioned drawing of the
    reference: the photo rendered at its overlay opacity (bottom of
    the stack, where create_coverup put it) with the design — the
    share_canvas, reference-free by construction — composited over
    it. A viewing aid; never an export of the design."""
    layer = doc.get(record.reference_layer_id)
    canvas = Image.new("RGBA", doc.size_px, (0, 0, 0, 0))
    canvas.alpha_composite(doc._render_layer_full(layer))
    canvas.alpha_composite(doc.share_canvas())
    return canvas


# ---------------------------------------------------------------------
# Darkness map
# ---------------------------------------------------------------------

def darkness_map(image: Image.Image,
                 threshold: int = DEFAULT_DARKNESS_THRESHOLD) -> tuple[Image.Image, dict]:
    """Ink-darkness estimate for a photograph (method + limits in
    the module docstring).

    Returns (map, summary): the map is an L-mode image the size of
    the input whose value at each pixel is 255 - luminance (255 =
    darkest). The summary counts pixels at or above `threshold`:
    {threshold, total_px, dark_px, coverage_fraction — the dark
    share of the image, mean_darkness_in_covered — the mean darkness
    of those dark pixels (0.0 when there are none)}."""
    if not 0 <= int(threshold) <= 255:
        raise ValueError("threshold must be within 0..255")
    lum = image.convert("L")
    dark = ImageChops.invert(lum)
    data = dark.tobytes()
    total = len(data)
    dark_values = [v for v in data if v >= threshold]
    dark_px = len(dark_values)
    summary = {
        "threshold": int(threshold),
        "total_px": total,
        "dark_px": dark_px,
        "coverage_fraction": (dark_px / total) if total else 0.0,
        "mean_darkness_in_covered": (sum(dark_values) / dark_px) if dark_px else 0.0,
    }
    return dark, summary


# ---------------------------------------------------------------------
# Coverage analysis
# ---------------------------------------------------------------------

def coverage_analysis(doc: DesignDoc, record: CoverUpRecord,
                      margin: int = COVERAGE_MARGIN) -> dict:
    """Compare the old tattoo's dark pixels against the new design's
    darkness, pixel by pixel (method in the module docstring).

    Returns {threshold, margin, old_dark_px, covered_px,
    uncovered_px, coverage_ratio (1.0 when there is nothing to
    cover), highlight} where highlight is an RGBA canvas-size image
    marking exactly the insufficiently covered old-dark pixels in
    WARNING_COLOR and nothing else."""
    if not 0 <= int(margin) <= 255:
        raise ValueError("margin must be within 0..255")
    ref_layer = doc.get(record.reference_layer_id)
    threshold = record.threshold

    # Old ink: the reference as placed, at full opacity. Canvas the
    # photo does not cover is not skin and never counts as ink.
    placed = doc._render_layer_full(ref_layer, apply_opacity=False)
    photo_alpha = placed.getchannel("A").tobytes()
    on_white = Image.new("RGBA", doc.size_px, (255, 255, 255, 255))
    on_white.alpha_composite(placed)
    old_dark = ImageChops.invert(on_white.convert("L")).tobytes()

    # New design: share_canvas (reference-free by construction),
    # darkness weighted by alpha — translucent ink covers partially.
    design = doc.share_canvas()
    design_dark = ImageChops.invert(design.convert("L")).tobytes()
    design_alpha = design.getchannel("A").tobytes()
    effective = bytes((d * a) // 255 for d, a in zip(design_dark, design_alpha))

    highlight = Image.new("RGBA", doc.size_px, (0, 0, 0, 0))
    hp = highlight.load()
    width, height = doc.size_px
    old_dark_px = covered_px = 0
    for i, old in enumerate(old_dark):
        if photo_alpha[i] == 0 or old < threshold:
            continue
        old_dark_px += 1
        if effective[i] >= old - margin:
            covered_px += 1
        else:
            hp[i % width, i // width] = WARNING_COLOR
    uncovered_px = old_dark_px - covered_px
    return {
        "threshold": threshold,
        "margin": int(margin),
        "old_dark_px": old_dark_px,
        "covered_px": covered_px,
        "uncovered_px": uncovered_px,
        "coverage_ratio": (covered_px / old_dark_px) if old_dark_px else 1.0,
        "highlight": highlight,
    }


def export_highlight(analysis: dict) -> bytes:
    """PNG bytes of an analysis' highlight image — a separate
    working-aid export, never part of any design bundle."""
    buf = io.BytesIO()
    analysis["highlight"].save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------
# Design export (new art only)
# ---------------------------------------------------------------------

def export_coverup_design(doc: DesignDoc, record: CoverUpRecord) -> dict:
    """Export the NEW ART ONLY: a copy of the document with the
    reference layer removed, serialized as a bundle.

    The working document is never touched — the removal happens on
    a bundle round-tripped copy (its lock is lifted there, on the
    copy, through the copy's own ops). The bundle additionally
    carries a `coverup.json` sidecar entry holding the export
    record incl. the guarantee note: the manifest format has no
    notes field and was not changed for this, so the note travels
    beside manifest.json inside the bundle AND in this function's
    returned record — either read shows it.

    Returns {bundle: bytes, record: {...}, guarantee_note}."""
    exported = DesignDoc.load_bundle(doc.save_bundle())
    ref_id = record.reference_layer_id
    ref = exported.get(ref_id)
    if ref.role != "reference":
        raise ValueError(f"layer {ref_id!r} is not the cover-up reference")
    exported.unlock_layer(ref_id)
    exported.remove(ref_id)

    export_record = {
        "kind": "coverup-design-export",
        "coverup_id": record.coverup_id,
        "doc_id": record.doc_id,
        "reference_layer_id": ref_id,
        "reference": dict(record.reference),
        "threshold": record.threshold,
        "guarantee_note": GUARANTEE_NOTE,
    }
    entries = exported.to_entries()
    entries.append(("coverup.json",
                    json.dumps(export_record, indent=2).encode("utf-8")))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, data in entries:
            zf.writestr(arcname, data)
    return {"bundle": buf.getvalue(), "record": export_record,
            "guarantee_note": GUARANTEE_NOTE}
