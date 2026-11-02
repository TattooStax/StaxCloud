"""Slice S7 — AI edit masks + protected regions (REVIEW-GBT-CANVAS
§2 E; GBT §9 agent workflow).

An AI edit is a request, not a free hand. The artist (or the agent
on their behalf) names ONE target — a layer, a canvas region, or a
mask reference — and the content that must NOT change: the protected
set. Protected artwork is an invariant, not a suggestion:

- `build_mask` computes the editable area deterministically. Any
  protected area is subtracted LAST, so protection wins every
  overlap with the target.
- The document's structural outline (S6), when one is set, is
  protected BY DEFAULT in every request. The only way it becomes
  editable is naming it as the target with geometry_authorized=True
  — and even then S5 locking still applies: a locked outline refuses
  until the artist explicitly unlocks it.
- A locked target layer (S5) refuses the request outright, at
  validation, before any pixel is considered.

`apply_edit` simulates what a host returns from a model edit: a
full-canvas RGBA proposal for the target layer's new rendering. It
runs TWO gates, in order:

1. PROPOSAL AUDIT. The raw proposal is diffed against the current
   target rendering everywhere the mask says "not editable". Pixels
   the model changed inside a protected area (a protected layer's
   footprint, a protected rect, the outline's footprint) mean the
   model did not respect the mask — the edit is REFUSED and the
   result carries a preview record (the hypothetical composite's
   hash + the per-region diff stats) instead of applying anything.
   Out-of-bounds changes that touch only unprotected, non-target
   canvas are discarded by the mask and merely reported
   (`discarded_px`): the mask, not the model, decides what lands.
2. APPLY + VERIFY. The proposal is composited over the current
   target rendering through the mask and baked into the layer
   (see below), recorded as a `layer.replace_content` op carrying
   the EditRequest id, so it is undoable like every other op.
   Then `verify_protected` diffs the real before/after documents —
   every protected layer's own full-canvas rendering, and the
   composite inside every protected rect — and any changed
   protected pixel rolls the document back to its exact prior
   state (bundle restore + history/ops truncation) and refuses.

verify_protected's per-region stats count differing pixels per
entry; a pixel covered by two entries is counted in both, so the
entries — not the summed total — are the authoritative record.

BAKING: a model returns pixels in canvas space, so a landed edit
bakes the target layer's placement into its pixels: the layer's
image becomes the composited full-canvas rendering cropped to its
alpha bounding box, x/y become that box's origin, and scale /
rotation / opacity reset to 1 / 0 / 1.0 (the pre-edit values are
recorded in the op). For the common case (a layer placed by x/y
alone) this is exact. Stamp layers are refused: a stamp is a
luminance mask, not canvas pixels — edit its raster source instead.

DETERMINISTIC GUARD (GBT §9): moving, resizing, hiding, reordering
or exporting an element is a typed op, never an inference spend.
`classify_intent` is a small keyword/kind heuristic and is honest
about its limits: it only REJECTS from the AI path when a request
is clearly a transform (an explicit deterministic kind, or
transform keywords with no generative keywords). Anything with
generative keywords — or nothing recognizable at all — stays on
the AI path; the classifier never invents a transform the artist
did not ask for.

Requests are RUNTIME records: an EditRequest (and any mask built
from it) lives in the session, not in the document manifest. It
round-trips through JSON (`to_dict` / `from_dict`) so a host can
store or transmit it; `mask_ref` names a mask a host holds, and is
resolved only when a masks mapping is handed to build_mask /
apply_edit.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass, field

from PIL import Image, ImageChops, ImageDraw

from .document import DesignDoc, LockedError

# Kinds that are always typed ops, never inference (GBT §9).
DETERMINISTIC_KINDS = (
    "transform", "move", "resize", "scale", "rotate", "flip",
    "hide", "show", "reorder", "export", "opacity", "remove",
    "rename", "undo", "redo",
)

_DETERMINISTIC_WORDS = (
    "move", "shift", "nudge", "slide", "resize", "rescale", "scale",
    "rotate", "flip", "hide", "show", "reveal", "reorder", "restack",
    "export", "rename", "undo", "redo",
)
_GENERATIVE_WORDS = (
    "fix", "redraw", "repaint", "regenerate", "deepen", "darken",
    "recolor", "stipple", "hatch", "soften", "sharpen", "correct",
    "extend", "texture", "shading", "shade", "blend",
)


class DeterministicIntentError(ValueError):
    """The request is a deterministic transform, not an AI edit.
    Raised before anything changes, with a pointer to the ops
    surface that does the job for free."""


def classify_intent(instruction: str = "", kind: str | None = None) -> dict:
    """Classify a request as "deterministic" (typed op) or "ai_edit".

    Small and keyword-based by design — see the module docstring
    for exactly where its authority starts and stops. Returns
    {kind, via, deterministic_hits, generative_hits}."""
    if kind is not None:
        if kind in DETERMINISTIC_KINDS:
            return {"kind": "deterministic", "via": "kind",
                    "deterministic_hits": [kind], "generative_hits": []}
        if kind in ("ai_edit", "generate", "edit"):
            return {"kind": "ai_edit", "via": "kind",
                    "deterministic_hits": [], "generative_hits": [kind]}
        raise ValueError(f"unknown request kind: {kind!r}")
    text = (instruction or "").lower()
    det = [w for w in _DETERMINISTIC_WORDS
           if re.search(rf"\b{re.escape(w)}\b", text)]
    gen = [w for w in _GENERATIVE_WORDS
           if re.search(rf"\b{re.escape(w)}\b", text)]
    if det and not gen:
        return {"kind": "deterministic", "via": "keywords",
                "deterministic_hits": det, "generative_hits": gen}
    return {"kind": "ai_edit", "via": "keywords" if gen else "default",
            "deterministic_hits": det, "generative_hits": gen}


# ---------------------------------------------------------------------
# EditRequest — a runtime record (JSON-round-trippable, not manifest)
# ---------------------------------------------------------------------

@dataclass
class EditRequest:
    request_id: str
    doc_id: str
    instruction: str
    target: dict
    protected: list = field(default_factory=list)
    created_by: str = ""
    geometry_authorized: bool = False
    kind: str | None = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "doc_id": self.doc_id,
            "instruction": self.instruction,
            "target": self.target,
            "protected": list(self.protected),
            "created_by": self.created_by,
            "geometry_authorized": bool(self.geometry_authorized),
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EditRequest":
        return cls(
            request_id=data["request_id"],
            doc_id=data["doc_id"],
            instruction=data["instruction"],
            target=data["target"],
            protected=list(data.get("protected", [])),
            created_by=data.get("created_by", ""),
            geometry_authorized=bool(data.get("geometry_authorized", False)),
            kind=data.get("kind"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "EditRequest":
        return cls.from_dict(json.loads(text))


# ---------------------------------------------------------------------
# Spec normalization + validation
# ---------------------------------------------------------------------

def _norm_area(entry, what: str) -> dict:
    """Normalize one target/protected area spec to
    {type: "layer", layer_id} or {type: "region", rect} — a
    mask_ref rides along on either as an added constraint."""
    if not isinstance(entry, dict):
        raise ValueError(f"{what} must be a dict, got {type(entry).__name__}")
    out = {}
    if entry.get("mask_ref") is not None:
        if not isinstance(entry["mask_ref"], str) or not entry["mask_ref"]:
            raise ValueError(f"{what}: mask_ref must be a non-empty string")
        out["mask_ref"] = entry["mask_ref"]
    if entry.get("layer_id") is not None:
        out["type"] = "layer"
        out["layer_id"] = entry["layer_id"]
    elif entry.get("rect") is not None:
        rect = entry["rect"]
        if (not isinstance(rect, (list, tuple)) or len(rect) != 4
                or not all(isinstance(v, int) and not isinstance(v, bool)
                           for v in rect)):
            raise ValueError(f"{what}: rect must be [x, y, w, h] of ints")
        out["type"] = "region"
        out["rect"] = [int(v) for v in rect]
    elif "mask_ref" not in out:
        raise ValueError(f"{what}: needs a layer_id, a rect, or a mask_ref")
    else:
        out["type"] = "region"
    if entry.get("type") is not None and entry["type"] != out["type"]:
        raise ValueError(
            f"{what}: type {entry['type']!r} does not match its fields "
            f"({out['type']})")
    return out


def _check_rect(doc: DesignDoc, rect, what: str) -> None:
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        raise ValueError(f"{what}: rect w/h must be positive, got {rect}")
    if x < 0 or y < 0 or x + w > doc.width_px or y + h > doc.height_px:
        raise ValueError(
            f"{what}: rect {rect} is not inside the canvas "
            f"{doc.width_px}x{doc.height_px}")


def effective_protected(doc: DesignDoc, request: EditRequest) -> list[dict]:
    """The protected set that actually governs a request: the
    artist's entries, PLUS the structural outline (auto-added,
    flagged) whenever one is set — unless the outline itself is
    the target under an explicit geometry authorization."""
    entries = [_norm_area(e, "protected") for e in request.protected]
    outline_id = doc.outline_layer
    if outline_id is not None:
        target = _norm_area(request.target, "target")
        authorized_outline = (
            target.get("type") == "layer"
            and target.get("layer_id") == outline_id
            and request.geometry_authorized)
        already = any(e.get("layer_id") == outline_id for e in entries)
        if not authorized_outline and not already:
            entries.append({"type": "layer", "layer_id": outline_id,
                            "auto": True})
    return entries


def validate_edit_request(doc: DesignDoc, request: EditRequest) -> dict:
    """Validate a request against a document. Raises before any
    state is touched: ValueError for a malformed/unresolvable
    request, DeterministicIntentError for a transform that belongs
    on the ops surface, LockedError for a locked target.

    Returns the normalized governing record: the target, the
    EFFECTIVE protected set (outline auto-protection applied), and
    the intent classification."""
    if not request.request_id:
        raise ValueError("request_id must be non-empty")
    if request.doc_id != doc.id:
        raise ValueError(
            f"request is for doc {request.doc_id!r}, not {doc.id!r}")
    if not request.instruction:
        raise ValueError("instruction must be non-empty")

    intent = classify_intent(request.instruction, request.kind)
    if intent["kind"] == "deterministic":
        raise DeterministicIntentError(
            "this request is a deterministic transform "
            f"({', '.join(intent['deterministic_hits'])}); use the typed "
            "ops surface (layer.transform / layer.reorder / "
            "layer.set_visible / doc.export_*) instead of an AI edit — "
            "never spend inference on a transform (GBT §9)")

    target = _norm_area(request.target, "target")
    if target["type"] == "layer":
        layer = doc.get(target["layer_id"])  # KeyError: no such layer
        if layer.locked:
            raise LockedError(
                f"edit target layer {layer.id!r} ({layer.name!r}) is "
                "locked; an AI edit request against it is refused "
                "outright — unlock it explicitly first")
    elif "rect" in target:
        _check_rect(doc, target["rect"], "target")

    outline_id = doc.outline_layer
    if (outline_id is not None and target["type"] == "layer"
            and target.get("layer_id") == outline_id
            and not request.geometry_authorized):
        raise ValueError(
            f"layer {outline_id!r} is the structural outline and is "
            "protected by default; editing its geometry requires "
            "geometry_authorized=True on the request")

    protected = effective_protected(doc, request)
    for entry in protected:
        if entry["type"] == "layer":
            doc.get(entry["layer_id"])  # KeyError: no such layer
        else:
            _check_rect(doc, entry["rect"], "protected")
    if target["type"] == "layer" and any(
            e["type"] == "layer" and e["layer_id"] == target["layer_id"]
            for e in protected):
        raise ValueError(
            f"target layer {target['layer_id']!r} is also in the "
            "protected set; protection wins — remove it from one side")

    return {"request_id": request.request_id, "target": target,
            "protected": protected, "intent": intent}


# ---------------------------------------------------------------------
# Masks
# ---------------------------------------------------------------------

def _footprint(doc: DesignDoc, layer) -> Image.Image:
    """A layer's placed footprint as an L mask (255 = covered)."""
    alpha = doc._render_layer_full(layer).getchannel("A")
    return alpha.point(lambda a: 255 if a > 0 else 0)


def _area_mask(doc: DesignDoc, area: dict, masks) -> Image.Image:
    """The canvas mask one area spec covers: a layer's footprint, a
    filled rect, and/or a named mask (intersected when combined)."""
    result = None
    if area["type"] == "layer":
        result = _footprint(doc, doc.get(area["layer_id"]))
    elif "rect" in area:
        result = Image.new("L", doc.size_px, 0)
        x, y, w, h = area["rect"]
        ImageDraw.Draw(result).rectangle([x, y, x + w - 1, y + h - 1],
                                         fill=255)
    if "mask_ref" in area:
        if not masks or area["mask_ref"] not in masks:
            raise ValueError(
                f"mask_ref {area['mask_ref']!r} cannot be resolved: "
                "no mask under that name was supplied")
        named = masks[area["mask_ref"]]
        named = (named.getchannel("A") if named.mode in ("RGBA", "LA")
                 else named.convert("L"))
        if named.size != doc.size_px:
            raise ValueError(
                f"mask {area['mask_ref']!r} is {named.size}, not the "
                f"canvas size {doc.size_px}")
        named = named.point(lambda a: 255 if a > 0 else 0)
        result = named if result is None else ImageChops.darker(result, named)
    return result


def build_mask(doc: DesignDoc, request: EditRequest,
               masks: dict | None = None) -> Image.Image:
    """The editable-area mask for a request (L mode, canvas size;
    255 = editable, 0 = protected).

    Construction is ordered so protection is an invariant: start
    all-protected when the effective protected set is non-empty
    (all-editable when it is empty), paint the target area editable,
    then subtract EVERY protected area last — a protected pixel is
    never editable, even where it overlaps the target."""
    validate_edit_request(doc, request)
    protected = effective_protected(doc, request)
    target = _norm_area(request.target, "target")
    mask = Image.new("L", doc.size_px, 0 if protected else 255)
    target_mask = _area_mask(doc, target, masks)
    mask = ImageChops.lighter(mask, target_mask)
    for entry in protected:
        mask = ImageChops.darker(
            mask, ImageChops.invert(_area_mask(doc, entry, masks)))
    return mask


def _protected_area_mask(doc: DesignDoc, protected: list[dict],
                         masks) -> Image.Image:
    """Union of every protected area (255 = protected)."""
    union = Image.new("L", doc.size_px, 0)
    for entry in protected:
        union = ImageChops.lighter(union, _area_mask(doc, entry, masks))
    return union


# ---------------------------------------------------------------------
# Pixel diffing (Pillow only)
# ---------------------------------------------------------------------

def _diff_count(a: Image.Image, b: Image.Image) -> int:
    """Pixels differing in ANY channel between two same-size images."""
    if a.size != b.size:
        raise ValueError(f"diff of mismatched sizes {a.size} vs {b.size}")
    diff = ImageChops.difference(a.convert("RGBA"), b.convert("RGBA"))
    m = diff.split()[0]
    for chan in diff.split()[1:]:
        m = ImageChops.lighter(m, chan)
    return m.point(lambda v: 255 if v > 0 else 0).histogram()[255]


def _overlap_count(a_mask: Image.Image, b_mask: Image.Image) -> int:
    return ImageChops.darker(a_mask, b_mask).histogram()[255]


# ---------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------

def verify_protected(before_doc: DesignDoc, after_doc: DesignDoc,
                     request: EditRequest,
                     masks: dict | None = None) -> dict:
    """Diff every protected entry between two document states.

    Layer entries are diffed on that layer's OWN full-canvas
    rendering (so a change anywhere in the layer counts, not just
    inside the target); rect entries are diffed on the composite
    render cropped to the rect. A protected layer missing from the
    after-state counts every covered pixel as changed.

    Returns {ok, changed_protected_pixels, regions: [{key, type,
    ref, changed_pixels, total_pixels}]} — per-region entries are
    authoritative; the total sums them (overlaps double-count)."""
    protected = effective_protected(before_doc, request)
    regions = []
    total_changed = 0
    for entry in protected:
        if entry["type"] == "layer":
            layer_id = entry["layer_id"]
            before_layer = before_doc.get(layer_id)
            before_full = before_doc._render_layer_full(before_layer)
            try:
                after_full = after_doc._render_layer_full(
                    after_doc.get(layer_id))
            except KeyError:
                after_full = Image.new("RGBA", before_doc.size_px,
                                       (0, 0, 0, 0))
            changed = _diff_count(before_full, after_full)
            total_px = _footprint(before_doc, before_layer).histogram()[255]
            key = f"layer:{layer_id}"
            ref = layer_id
        else:
            x, y, w, h = entry["rect"]
            box = (x, y, x + w, y + h)
            changed = _diff_count(before_doc.render().crop(box),
                                  after_doc.render().crop(box))
            total_px = w * h
            key = f"rect:{x},{y},{w},{h}"
            ref = list(entry["rect"])
        regions.append({"key": key, "type": entry["type"], "ref": ref,
                        "changed_pixels": changed,
                        "total_pixels": total_px})
        total_changed += changed
    return {"ok": total_changed == 0,
            "changed_protected_pixels": total_changed,
            "regions": regions}


# ---------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------

def _bake_into_layer(layer, full_rgba: Image.Image) -> dict:
    """Bake a full-canvas rendering into a layer's own pixels
    (canvas-space edit semantics — see the module docstring).
    Returns the pre-bake transform record for the op log."""
    baked_from = {"x": layer.x, "y": layer.y, "scale": layer.scale,
                  "rotation": layer.rotation, "opacity": layer.opacity}
    bbox = full_rgba.getchannel("A").getbbox()
    if bbox is None:
        layer.image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        layer.x, layer.y = 0, 0
    else:
        layer.image = full_rgba.crop(bbox)
        layer.x, layer.y = bbox[0], bbox[1]
    layer.scale, layer.rotation, layer.opacity = 1.0, 0.0, 1.0
    return baked_from


def _preview_record(doc_like: DesignDoc, verification: dict,
                    note: str) -> dict:
    """The record a refusal leaves behind instead of an edit: the
    hypothetical composite's hash + the diff stats that refused it."""
    buf = io.BytesIO()
    doc_like.render().save(buf, "PNG")
    return {"composite_sha256": hashlib.sha256(buf.getvalue()).hexdigest(),
            "changed_protected_pixels":
                verification["changed_protected_pixels"],
            "regions": verification["regions"],
            "note": note}


def apply_edit(doc: DesignDoc, request: EditRequest,
               edited_layer_image: Image.Image,
               masks: dict | None = None) -> dict:
    """Apply a host model edit to a document, through the mask,
    under protected-region verification (the module docstring
    describes the two gates, and the baking semantics).

    `edited_layer_image` is the model's proposed new rendering OF
    THE TARGET LAYER, full-canvas RGBA. Layer targets only: a
    region/mask target has no single layer to land pixels on, so
    it raises ValueError (region edits are host-applied, then
    checked with verify_protected). Stamp targets raise too.

    Returns an applied record {refused: False, ok: True, op,
    verification, discarded_px, mask_editable_px} or a refusal
    {refused: True, ok: False, verification, preview} — and on
    refusal the document is exactly as it was before the call."""
    governing = validate_edit_request(doc, request)
    target = governing["target"]
    if target["type"] != "layer":
        raise ValueError(
            "apply_edit lands pixels on ONE target layer; a region / "
            "mask_ref target has no single layer — host-side region "
            "edits are checked with verify_protected instead")
    layer = doc.get(target["layer_id"])
    if layer.kind == "stamp":
        raise ValueError(
            f"target layer {layer.id!r} is a stamp (a luminance mask), "
            "not canvas pixels; edit its raster source instead")
    proposal = edited_layer_image.convert("RGBA")
    if proposal.size != doc.size_px:
        raise ValueError(
            f"edited image is {proposal.size}, not the canvas size "
            f"{doc.size_px} — a host edit must return canvas-space pixels")

    protected = governing["protected"]
    mask = build_mask(doc, request, masks)
    current_full = doc._render_layer_full(layer)

    # Gate 1 — audit the RAW proposal: anything it changed outside
    # the editable mask, inside a protected area, refuses the edit.
    outside = ImageChops.difference(proposal, current_full)
    m = outside.split()[0]
    for chan in outside.split()[1:]:
        m = ImageChops.lighter(m, chan)
    changed_anywhere = m.point(lambda v: 255 if v > 0 else 0)
    not_editable = ImageChops.invert(mask)
    out_of_bounds = ImageChops.darker(changed_anywhere, not_editable)
    discarded_px = out_of_bounds.histogram()[255]
    if protected:
        area = _protected_area_mask(doc, protected, masks)
        poison = ImageChops.darker(out_of_bounds, area)
        poison_px = poison.histogram()[255]
        if poison_px:
            regions = []
            for entry in protected:
                n = _overlap_count(poison, _area_mask(doc, entry, masks))
                if n:
                    ref = (entry["layer_id"] if entry["type"] == "layer"
                           else list(entry["rect"]))
                    regions.append({
                        "key": (f"layer:{ref}" if entry["type"] == "layer"
                                else f"rect:{','.join(map(str, ref))}"),
                        "type": entry["type"], "ref": ref,
                        "changed_pixels": n, "total_pixels": None})
            verification = {"ok": False,
                            "changed_protected_pixels": poison_px,
                            "regions": regions,
                            "stage": "proposal-audit"}
            hypo = DesignDoc.load_bundle(doc.save_bundle())
            _bake_into_layer(hypo.get(layer.id), proposal)
            return {"refused": True, "ok": False,
                    "request_id": request.request_id,
                    "verification": verification,
                    "discarded_px": discarded_px,
                    "preview": _preview_record(
                        hypo, verification,
                        "the model proposal changed protected content; "
                        "nothing was applied — the artist reviews this "
                        "preview instead")}

    # Gate 2 — composite through the mask, bake, record, verify.
    pre_bundle = doc.save_bundle()
    pre_history = list(doc._history)
    pre_redo = list(doc._redo)
    pre_ops_len = len(doc.ops_log)
    before_doc = DesignDoc.load_bundle(pre_bundle)

    composited = Image.composite(proposal, current_full, mask)
    doc._push_history()
    baked_from = _bake_into_layer(layer, composited)
    layer.provenance = {
        **layer.provenance,
        "edit_request": request.request_id,
        "edit_instruction": request.instruction,
        "edited_by": request.created_by,
        "last_edit_source": "ai-edit",
    }
    op = {"op": "layer.replace_content", "id": layer.id,
          "edit_request": request.request_id, "baked_from": baked_from}
    doc.ops_log.append(op)

    verification = verify_protected(before_doc, doc, request, masks)
    verification["stage"] = "post-apply"
    if not verification["ok"]:
        hypo_render = doc.render()
        doc._restore_state(pre_bundle)
        doc._history = pre_history
        doc._redo = pre_redo
        del doc.ops_log[pre_ops_len:]
        buf = io.BytesIO()
        hypo_render.save(buf, "PNG")
        preview = {"composite_sha256":
                   hashlib.sha256(buf.getvalue()).hexdigest(),
                   "changed_protected_pixels":
                       verification["changed_protected_pixels"],
                   "regions": verification["regions"],
                   "note": "the masked edit still changed protected "
                           "content on verification; it was rolled "
                           "back byte-identical — the artist reviews "
                           "this preview instead"}
        return {"refused": True, "ok": False,
                "request_id": request.request_id,
                "verification": verification,
                "discarded_px": discarded_px,
                "preview": preview}

    return {"refused": False, "ok": True,
            "request_id": request.request_id,
            "op": op,
            "verification": verification,
            "discarded_px": discarded_px,
            "mask_editable_px": mask.histogram()[255]}
