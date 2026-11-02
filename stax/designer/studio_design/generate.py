"""Slice 2 — generative support: routing, prompts, matting, provenance,
linework measurement (PLAN-v2 §8 Slice 2).

This module is the deterministic scaffolding AROUND the generative
tool, plus the deterministic half of the pipeline itself:

- ROUTING and the PROMPT BUILDER are pure text functions. The model
  call itself (`generate_element`) happens in the agent's chat image
  path, exactly as designs are generated in chat today; what this
  module guarantees is that the request is routed to the best-fit
  artist, the prompt carries that artist's style anchor and the
  standing simplified value style, and every planned generation has a
  complete provenance record BEFORE any pixels exist.
- MATTING + SPLIT + STAMP are deterministic pixel functions: a
  generated element arrives on plain white (the prompt demands white
  precisely so extraction is deterministic), and leaves as transparent
  RGBA, a pure-black line layer, a separate grey shading layer, and a
  luminance stamp mask — the PLAN §3 format contract.
- MEASURE_LINEWORK is the Director condition-6 harness: it measures
  real generated output and reports metrics + a pass/warn verdict. It
  is a measurement, not a quality guarantee — the rejection rate it
  feeds is what decides whether client-facing stencil claims are made.

Skill/tool boundary (PLAN §6) holds: this module decides nothing
about composition taste; it routes by declared profile descriptors,
builds prompts from them, and processes pixels deterministically.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field

from PIL import Image

# ---------------------------------------------------------------------
# Routing (PLAN §4)
# ---------------------------------------------------------------------


def _norm(text: str) -> str:
    text = text.lower().replace("&", " and ").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


# Descriptor groups: (profile keys that activate the group, aliases in
# a request that match it). A group scores at most once per artist, so
# "bold color" never double-counts as "bold" + "color".
_DESCRIPTOR_GROUPS: list[tuple[list[str], list[str]]] = [
    (["black and grey"], ["black and grey", "black and gray", "b&g", "blackwork grey"]),
    (["fine line"], ["fine line", "fineline", "fine linework"]),
    (["realism", "semi realism"], ["realism", "realistic", "semi realism", "semi realistic"]),
    (["minimalist"], ["minimalist", "minimal", "minimalism"]),
    (["street style"], ["street style", "street"]),
    (["neo traditional"], ["neo traditional", "neotraditional", "neo trad", "traditional"]),
    (["bold color"], ["bold color", "bold colour", "color", "colour", "colorful"]),
    (["illustrative"], ["illustrative", "illustration"]),
    (["graphic"], ["graphic"]),
    (["floral"], ["floral", "florals", "botanical", "flowers"]),
    (["red ink"], ["red ink"]),
]


def _artist_groups(profile: dict) -> list[list[str]]:
    """The descriptor groups an artist's own profile activates."""
    declared = _norm(" | ".join(profile.get("styles", []) + profile.get("specialties", [])))
    groups = []
    for keys, aliases in _DESCRIPTOR_GROUPS:
        if any(_norm(k) in declared for k in keys):
            groups.append(aliases)
    return groups


def _alias_matches(alias: str, request_norm: str) -> bool:
    return re.search(rf"\b{re.escape(_norm(alias))}\b", request_norm) is not None


def route_request(text: str, store) -> dict | None:
    """Pick the best-fit artist for a design request.

    Matches request descriptors against each profile's declared
    styles/specialties (PLAN §4). Returns:
      {artist_id, reason, matched_terms, scores}  — one clear winner
      {ambiguous: [artist_id, ...], ...}          — equal fit; the
        caller must ASK, never silently default (PLAN §4)
      None                                        — nothing fits
    """
    request_norm = _norm(text)
    scored: list[tuple[str, list[str]]] = []
    for profile in store.agent_view():
        matched: list[str] = []
        for aliases in _artist_groups(profile):
            hit = next((a for a in aliases if _alias_matches(a, request_norm)), None)
            if hit:
                matched.append(hit)
        scored.append((profile["artist_id"], matched))
    best = max((len(m) for _, m in scored), default=0)
    if best == 0:
        return None
    winners = [artist_id for artist_id, m in scored if len(m) == best]
    scores = {artist_id: len(m) for artist_id, m in scored}
    matched_by = {artist_id: m for artist_id, m in scored if m}
    if len(winners) > 1:
        return {"ambiguous": winners, "scores": scores, "matched_terms": matched_by,
                "reason": "equal descriptor fit — ask the customer/owner to choose"}
    artist_id = winners[0]
    terms = matched_by[artist_id]
    return {"artist_id": artist_id, "matched_terms": terms, "scores": scores,
            "reason": f"best fit for {artist_id}: matched profile descriptors "
                      f"{', '.join(terms)} ({best} group(s); next best "
                      f"{max((s for a, s in scores.items() if a != artist_id), default=0)})"}


# ---------------------------------------------------------------------
# Prompt builder (PLAN §3/§4; simplified value style 2026-11-01)
# ---------------------------------------------------------------------

VALUE_STYLE = (
    "simplified value style: less detail, clean linework, smooth shading "
    "off the lines, strong white/dark separation, no muddy mid-tones"
)
TATTOOABILITY = (
    "tattooable: bold outer contours, fine inner detail only where it "
    "will hold, clean negative space, designed to heal and age legibly"
)
ISOLATION = "single isolated element, plain white background, centered, no skin, no text"

NEGATIVE_PROMPT = (
    "background scenery, skin, body part, photograph of a person, text, "
    "lettering, watermark, muddy mid-tones, excessive detail, clutter, "
    "blurry edges, broken lines, grey background, coloured background"
)


@dataclass
class PromptSpec:
    prompt: str
    negative_prompt: str = NEGATIVE_PROMPT

    def __iter__(self):
        yield self.prompt
        yield self.negative_prompt


def _style_anchor(profile: dict) -> str:
    styles = ", ".join(profile.get("styles", []))
    specialties = ", ".join(profile.get("specialties", []))
    anchor = f"in the style of {profile.get('display_name', profile['artist_id'])}: {styles}"
    if specialties:
        anchor += f"; known for {specialties}"
    style_note = (profile.get("style_note") or "").strip()
    if style_note:
        # Owner delta 2026-11-02: a profile's style note refines the
        # anchor (e.g. Shawn's leans slightly more realistic) and must
        # reach every generation prompt built for that artist.
        anchor += f"; style note: {style_note}"
    return anchor


def _size_text(size) -> str:
    if size is None:
        return ""
    if isinstance(size, (tuple, list)):
        return f"{size[0]}x{size[1]} mm"
    return str(size)


def _lighting_part(lighting, preset) -> str | None:
    """The lighting clause for a prompt, rendered FROM structured
    data (S6): `lighting` is a spec dict / LightingSpec (typically
    the document's stored spec); `preset` is a preset key whose
    defaults fill any field the spec leaves unset (an explicitly
    set technique wins over the preset's). Returns None when
    neither is given, so an unlit prompt is byte-identical to the
    pre-S6 builders."""
    if lighting is None and preset is None:
        return None
    from .lighting import get_preset, lighting_clause, validate_lighting_spec

    data: dict = {}
    if preset is not None:
        data.update(get_preset(preset)["defaults"])
    if lighting is not None:
        explicit = lighting.to_dict() if hasattr(lighting, "to_dict") else dict(lighting)
        data.update({k: v for k, v in explicit.items() if v is not None})
        if preset is not None and "technique" not in explicit:
            data["technique"] = get_preset(preset)["defaults"]["technique"]
    return lighting_clause(validate_lighting_spec(data))


def build_element_prompt(artist_profile: dict, subject: str,
                         placement: str | None = None, size=None,
                         lighting=None, preset: str | None = None) -> PromptSpec:
    """Prompt for ONE element, generated on white so matting is
    deterministic. Encodes the artist's style anchor, the standing
    simplified value style, and tattooability constraints. When a
    lighting spec (or preset) is given, its clause is rendered from
    the structured fields and appended (S6)."""
    parts = [f"Tattoo design element: {subject}", _style_anchor(artist_profile),
             VALUE_STYLE, TATTOOABILITY, ISOLATION]
    if placement:
        parts.append(f"composed to sit on the {placement}")
    size_text = _size_text(size)
    if size_text:
        parts.append(f"designed at {size_text}")
    clause = _lighting_part(lighting, preset)
    if clause:
        parts.append(clause)
    return PromptSpec(prompt=". ".join(parts) + ".")


def build_layout_prompt(artist_profile: dict, subject: str,
                        placement: str | None = None, size=None,
                        lighting=None, preset: str | None = None) -> PromptSpec:
    """Prompt for the FLAT layout-reference pass (Director Q1 hybrid):
    one coherent full composition first, so per-element generation
    that follows stays coherent in lighting, line weight and palette.
    Accepts the same lighting spec/preset injection as
    build_element_prompt (S6) — the layout pass is where a scene's
    light is established, so it takes the spec first."""
    parts = [f"Flat layout reference for a tattoo design: {subject}",
             _style_anchor(artist_profile), VALUE_STYLE, TATTOOABILITY,
             "full composition, all elements arranged together in their "
             "final relative positions, plain white background, no skin, no text"]
    if placement:
        parts.append(f"composed to sit on the {placement}")
    size_text = _size_text(size)
    if size_text:
        parts.append(f"designed at {size_text}")
    clause = _lighting_part(lighting, preset)
    if clause:
        parts.append(clause)
    return PromptSpec(prompt=". ".join(parts) + ".")


# ---------------------------------------------------------------------
# Matting + split + stamp (deterministic; PLAN §3)
# ---------------------------------------------------------------------


def _luminance_array(img_rgba):
    import numpy as np

    arr = np.asarray(img_rgba).astype(np.float32)
    lum = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    return arr, lum


def _background_mask(rgb_img) -> "object":
    """Near-white pixels connected to the image border = background.

    Connectivity matters: interior whites (paper highlights inside the
    motif) are NOT background and survive as covered pixels.
    """
    import numpy as np
    from scipy import ndimage

    arr = np.asarray(rgb_img.convert("RGB")).astype(np.int32)
    near_white = arr.min(axis=2) >= 243
    labels, _ = ndimage.label(near_white)  # 4-connectivity by default
    border_labels = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    border_labels.discard(0)
    return np.isin(labels, list(border_labels)) if border_labels else np.zeros_like(near_white)


def matte_to_transparent(img: Image.Image) -> Image.Image:
    """Extract an element generated on plain white onto transparency.

    Background (border-connected near-white) becomes alpha 0. A 1-px
    boundary band is decontaminated: anti-aliased edge pixels are
    un-multiplied from the white ground, so the light fringe that
    would read as a halo becomes the artwork's own dark edge at
    partial alpha — or is removed outright below 4% coverage.
    """
    import numpy as np
    from scipy import ndimage

    rgb = img.convert("RGB")
    arr = np.asarray(rgb).astype(np.float32)
    bg = _background_mask(rgb)
    alpha = np.where(bg, 0.0, 255.0)

    foreground_near_bg = (~bg) & ndimage.binary_dilation(bg)
    if foreground_near_bg.any():
        min_channel = arr.min(axis=2)
        light = foreground_near_bg & (min_channel >= 180)
        coverage = (255.0 - min_channel) / 255.0
        ys, xs = np.where(light)
        for y, x in zip(ys, xs):
            cov = float(coverage[y, x])
            if cov < 0.04:
                alpha[y, x] = 0.0
                continue
            unmult = (arr[y, x] - (1.0 - cov) * 255.0) / cov
            arr[y, x] = np.clip(unmult, 0, 255)
            alpha[y, x] = cov * 255.0

    out = np.dstack([arr, alpha]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def split_line_shading(element_rgba: Image.Image,
                       line_max_luminance: float = 85.0,
                       paper_min_luminance: float = 248.0):
    """Split a transparent element into (line_rgba, shading_rgba).

    Line = the darkest covered pixels, re-issued as pure black on
    transparent (passes the §3 line rule by construction). Shading =
    the mid-luminance covered pixels as a smooth grey wash on
    transparent, with every line pixel removed, so shading sits OFF
    the lines and the two layers recombine without overlap. Covered
    near-white pixels are paper highlights and leave both layers.

    V1 limit, stated plainly: the split is a luminance threshold, so
    the darkest core of a soft shade can land in the line layer. The
    threshold is one named constant the artist's rejection data
    (Slice 2 measurement) can tune.
    """
    import numpy as np

    arr, lum = _luminance_array(element_rgba.convert("RGBA"))
    alpha = arr[..., 3]
    covered = alpha > 0

    line_mask = covered & (lum <= line_max_luminance)
    line = np.zeros_like(arr)
    line[..., 3] = np.where(line_mask, alpha, 0)

    shading_mask = covered & (lum > line_max_luminance) & (lum < paper_min_luminance)
    shading = np.zeros_like(arr)
    grey = np.where(shading_mask, lum, 0)
    shading[..., 0] = grey
    shading[..., 1] = grey
    shading[..., 2] = grey
    shading[..., 3] = np.where(shading_mask, alpha, 0)

    return (Image.fromarray(line.clip(0, 255).astype(np.uint8), "RGBA"),
            Image.fromarray(shading.clip(0, 255).astype(np.uint8), "RGBA"))


def make_stamp(element_rgba: Image.Image) -> Image.Image:
    """Luminance stamp mask (.l8): white motif on black, tintable.

    Mask value = coverage x darkness, so a pure-black line element's
    stamp IS its alpha, and transparent pixels are always 0.
    """
    import numpy as np

    arr, lum = _luminance_array(element_rgba.convert("RGBA"))
    mask = (arr[..., 3] / 255.0) * (255.0 - lum)
    return Image.fromarray(mask.clip(0, 255).astype(np.uint8), "L")


# ---------------------------------------------------------------------
# Provenance + version orchestration (PLAN §5 flow; Director Q2/Q5;
# per-artist version count = owner delta 2026-11-02)
# ---------------------------------------------------------------------

DEFAULT_MODEL = "stax-chat-image-generation"

_COMPOSITION_VARIANTS = [
    "straight-on front view, balanced composition, element centred with breathing room",
    "three-quarter view, diagonal flow that follows the placement, depth layered front-to-back",
    "alternate angle, vertical flow, negative space opened up for later collage additions",
]


@dataclass
class GenerationRecord:
    """Provenance for one planned/generated element. Recorded BEFORE
    generation (Director: approval is of a reproducible design, not
    just a picture) and attached to the document layer it becomes.

    `cost` is the METERED cost of the generation call as
    {amount, currency, source}. It stays None — at planning time and
    forever after — until a host meters a REAL call and records it
    via `record_cost`. It is never estimated, interpolated, or filled
    from a price list: an unmetered generation has no cost of record,
    which is a different statement from "it was free"."""
    seed: int
    model: str
    prompt: str
    negative_prompt: str
    reference_ids: list = field(default_factory=list)
    artist_id: str = ""
    subject: str = ""
    placement: str = ""
    size_mm: object = None
    cost: dict | None = None

    def to_dict(self) -> dict:
        return {
            "seed": self.seed, "model": self.model, "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "reference_ids": list(self.reference_ids),
            "artist_id": self.artist_id, "subject": self.subject,
            "placement": self.placement, "size_mm": self.size_mm,
            "cost": dict(self.cost) if self.cost is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GenerationRecord":
        return cls(**{k: data[k] for k in
                      ("seed", "model", "prompt", "negative_prompt", "reference_ids",
                       "artist_id", "subject", "placement", "size_mm",
                       "cost") if k in data})

    def is_complete(self) -> bool:
        d = self.to_dict()
        return all(d[k] not in (None, "") for k in
                   ("model", "prompt", "negative_prompt", "artist_id", "subject")) \
            and isinstance(d["seed"], int)

    def as_layer_provenance(self) -> dict:
        return {"source": "generated", **self.to_dict()}


def record_cost(record: GenerationRecord, amount, currency: str, source: str) -> dict:
    """Record the metered cost of the REAL generation call behind a
    record (GBT §7, adopted as REVIEW §2 G). This is the only way a
    record gains a cost: the caller is a host metering an actual
    call, and `source` names that meter (e.g. the provider's usage
    record). Validation: amount must be a non-negative number,
    currency and source non-empty strings."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError("cost amount must be a number")
    if amount < 0:
        raise ValueError("cost amount must be >= 0")
    if not isinstance(currency, str) or not currency.strip():
        raise ValueError("cost currency must be a non-empty string")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("cost source must be a non-empty string")
    record.cost = {"amount": float(amount), "currency": currency, "source": source}
    return record.cost


def attach_record_to_layer(doc, layer_id: str, record: GenerationRecord) -> dict:
    """Attach a generation record to a Slice 1 document layer's
    provenance (the layer then carries it through manifest/save/load)."""
    layer = doc.get(layer_id)
    layer.provenance = record.as_layer_provenance()
    doc.ops_log.append({"op": "layer.set_provenance", "id": layer_id,
                        "seed": record.seed, "artist_id": record.artist_id})
    return layer.provenance


def _reference_ids(profile: dict) -> list:
    ids = []
    for item in profile.get("approved_library", []):
        ids.append(item["id"] if isinstance(item, dict) else str(item))
    return ids


def plan_versions(request, store, count: int | None = None) -> dict:
    """Plan a request's versions without generating.

    `request`: a string, or a dict {text|subject, placement, size_mm}.
    Version count (owner delta 2026-11-02) resolves as: the explicit
    `count` override if given, else the routed artist's
    `versions_per_request` profile setting, else the product default
    1. Returns {routing, versions: [GenerationRecord-as-dict, ...]}
    on a routed fit; {routing, versions: []} when routing is
    ambiguous or finds no fit — planning never silently defaults
    the artist either.
    """
    if count is not None:
        count = int(count)
        if count < 1:
            raise ValueError("version count must be at least 1")
    if isinstance(request, str):
        request = {"text": request}
    subject = request.get("subject") or request.get("text", "")
    placement = request.get("placement", "")
    size_mm = request.get("size_mm", request.get("size"))
    if isinstance(size_mm, tuple):
        size_mm = list(size_mm)

    if request.get("artist_id"):
        routing = {"artist_id": request["artist_id"],
                   "reason": "artist named in the request", "matched_terms": []}
    else:
        routing = route_request(f"{subject} {request.get('text', '')}", store)
    if not routing or "ambiguous" in routing:
        return {"routing": routing, "versions": []}

    artist_id = routing["artist_id"]
    profile = store.get(artist_id)
    if count is None:
        count = int(profile.get("versions_per_request", 1))
    base_seed = 1000 + zlib.crc32(f"{artist_id}|{subject}|{placement}".encode()) % 90000
    versions = []
    for i in range(count):
        composition = _COMPOSITION_VARIANTS[i % len(_COMPOSITION_VARIANTS)]
        if i >= len(_COMPOSITION_VARIANTS):
            composition = f"{composition}; variation {i + 1}"
        spec = build_element_prompt(profile, subject, placement, size_mm)
        record = GenerationRecord(
            seed=base_seed + i * 137,
            model=request.get("model", DEFAULT_MODEL),
            prompt=f"{spec.prompt} Composition: {composition}.",
            negative_prompt=spec.negative_prompt,
            reference_ids=_reference_ids(profile),
            artist_id=artist_id, subject=subject,
            placement=placement, size_mm=size_mm,
        )
        versions.append(record.to_dict())
    return {"routing": routing, "versions": versions}


def plan_three_versions(request, store) -> dict:
    """Back-compat wrapper: force exactly 3 versions (PLAN §5's
    original flow). New code should call `plan_versions`, whose count
    comes from the routed artist's setting."""
    return plan_versions(request, store, count=3)


# ---------------------------------------------------------------------
# Linework quality measurement (Director condition 6)
# ---------------------------------------------------------------------


def measure_linework(rgba: Image.Image) -> dict:
    """Measure a line element's stencil-readiness. Harness, not a
    guarantee: the verdict feeds the rejection-rate record that
    decides whether client-facing stencil claims are ever made.

    Metrics:
      edge_density        dark line pixels / total pixels
      broken_line_ratio   estimate: components per 100 dark pixels
                          (capped at 1.0) — fragmented linework has
                          many small components for its area
      anti_alias_fraction covered artwork pixels that are neither
                          solid dark nor paper: semi-transparent or
                          mid-luminance (grey / mushy edges)
      min_feature_px      estimate of the thinnest stroke: twice the
                          5th-percentile distance-to-background over
                          dark pixels
    Verdict: "warn" if there is no linework, the anti-alias fraction
    exceeds 0.4, or the broken estimate exceeds 0.25; else "pass".
    Large inputs are measured on a <=800px reduction (min_feature_px
    is scaled back to full-size pixels).
    """
    import numpy as np
    from scipy import ndimage

    img = rgba.convert("RGBA")
    scale = 1.0
    if max(img.size) > 800:
        scale = 800 / max(img.size)
        img = img.resize((max(1, round(img.width * scale)),
                          max(1, round(img.height * scale))), Image.NEAREST)
    arr, lum = _luminance_array(img)
    alpha = arr[..., 3]
    total = alpha.size
    covered = alpha > 10
    dark = covered & (lum <= 110)

    dark_px = int(dark.sum())
    covered_px = int(covered.sum())
    edge_density = dark_px / total if total else 0.0

    artwork = covered & (lum < 248)
    mushy = artwork & ((alpha < 250) | ((lum > 40) & (lum < 210)))
    anti_alias_fraction = float(mushy.sum() / artwork.sum()) if artwork.any() else 0.0

    if dark_px:
        _, n_components = ndimage.label(dark)
        broken = min(1.0, n_components * 100.0 / dark_px)
        distances = ndimage.distance_transform_edt(dark)
        on_line = distances[dark]
        min_feature = float(2 * np.percentile(on_line, 5) / scale) if on_line.size else 0.0
    else:
        n_components, broken, min_feature = 0, 1.0, 0.0

    verdict = "pass"
    if dark_px == 0 or anti_alias_fraction > 0.4 or broken > 0.25:
        verdict = "warn"
    return {
        "edge_density": round(float(edge_density), 4),
        "broken_line_ratio": round(float(broken), 4),
        "anti_alias_fraction": round(anti_alias_fraction, 4),
        "min_feature_px": round(min_feature, 2),
        "dark_pixels": dark_px,
        "component_count": int(n_components),
        "verdict": verdict,
    }
