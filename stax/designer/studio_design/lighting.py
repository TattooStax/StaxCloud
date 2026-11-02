"""Slice S6 — structured lighting spec + shading presets
(REVIEW-GBT-CANVAS §2 C; Director-review §4/§7).

Lighting is SCENE DATA, not prompt text. A LightingSpec lives on the
document (manifest-persisted, so it round-trips save/load and is
captured by S5 history/snapshots like any other content), is
revisable independently of any generation, and is rendered into
generation prompts FROM its structured fields by `lighting_clause`
— never pasted in as a free-text blob, so changing a value changes
the prompt in exactly the derived words.

No physical relighting is promised anywhere here: the spec is
structured intent. Shading changes ride constrained generation
against the spec, and the artist judges the result (REVIEW §3).

Per-element flags: `element_flags` maps a layer id to
{receive_light, cast_shadow} — which elements the light logic
should treat as lit receivers vs shadow casters when the spec is
injected or a shading plan is built.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

CONTRASTS = ("low", "medium", "high")

_SPEC_FIELDS = (
    "direction", "angle_deg", "intensity", "softness",
    "shadow_direction", "horizon", "technique", "contrast",
    "element_flags",
)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass
class LightingSpec:
    """One document's lighting intent. Defaults are a plain upper-
    left key light at medium contrast; every field is validated by
    `validate_lighting_spec` before a spec may land on a document."""
    direction: str = "upper-left"
    angle_deg: float = 315.0
    intensity: float = 0.8
    softness: float = 0.5
    shadow_direction: str | None = "lower-right"
    horizon: str | None = None
    technique: str = "smooth-black-and-grey-realism"
    contrast: str = "medium"
    element_flags: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "angle_deg": self.angle_deg,
            "intensity": self.intensity,
            "softness": self.softness,
            "shadow_direction": self.shadow_direction,
            "horizon": self.horizon,
            "technique": self.technique,
            "contrast": self.contrast,
            "element_flags": copy.deepcopy(self.element_flags),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LightingSpec":
        if not isinstance(data, dict):
            raise ValueError("lighting spec must be a dict")
        return cls(**validate_lighting_spec(data))


def validate_lighting_spec(spec) -> dict:
    """Validate a spec (LightingSpec or dict) and return its
    normalized plain-dict form — the form stored on a document.

    Rules: direction a non-empty string; angle_deg a number in
    0..360; intensity and softness numbers in 0..1; shadow_direction
    and horizon strings or None; technique a non-empty string (a
    preset key or free text); contrast one of low|medium|high;
    element_flags a dict of layer id -> {receive_light: bool,
    cast_shadow: bool} (missing flags default to True). Unknown
    fields are refused, not silently dropped. Any violation raises
    ValueError with nothing changed anywhere."""
    if isinstance(spec, LightingSpec):
        data = spec.to_dict()
    elif isinstance(spec, dict):
        data = spec
    else:
        raise ValueError("lighting spec must be a LightingSpec or a dict")
    unknown = set(data) - set(_SPEC_FIELDS)
    if unknown:
        raise ValueError(f"unknown lighting spec field(s): {sorted(unknown)}")
    out = LightingSpec().to_dict()
    out.update({k: data[k] for k in _SPEC_FIELDS if k in data})

    if not isinstance(out["direction"], str) or not out["direction"].strip():
        raise ValueError("lighting direction must be a non-empty string")
    if not _is_number(out["angle_deg"]) or not 0.0 <= float(out["angle_deg"]) <= 360.0:
        raise ValueError("lighting angle_deg must be a number in 0..360")
    for name in ("intensity", "softness"):
        if not _is_number(out[name]) or not 0.0 <= float(out[name]) <= 1.0:
            raise ValueError(f"lighting {name} must be a number in 0..1")
    for name in ("shadow_direction", "horizon"):
        if out[name] is not None and (not isinstance(out[name], str)
                                      or not out[name].strip()):
            raise ValueError(f"lighting {name} must be a non-empty string or None")
    if not isinstance(out["technique"], str) or not out["technique"].strip():
        raise ValueError("lighting technique must be a non-empty string")
    if out["contrast"] not in CONTRASTS:
        raise ValueError(f"lighting contrast must be one of {CONTRASTS}")
    flags = out["element_flags"]
    if not isinstance(flags, dict):
        raise ValueError("lighting element_flags must be a dict keyed by layer id")
    normalized_flags = {}
    for layer_id, entry in flags.items():
        if not isinstance(entry, dict):
            raise ValueError(f"element_flags[{layer_id!r}] must be a dict")
        extra = set(entry) - {"receive_light", "cast_shadow"}
        if extra:
            raise ValueError(
                f"element_flags[{layer_id!r}] has unknown flag(s): {sorted(extra)}")
        normalized_flags[str(layer_id)] = {
            "receive_light": bool(entry.get("receive_light", True)),
            "cast_shadow": bool(entry.get("cast_shadow", True)),
        }
    return {
        "direction": out["direction"].strip(),
        "angle_deg": float(out["angle_deg"]),
        "intensity": float(out["intensity"]),
        "softness": float(out["softness"]),
        "shadow_direction": (out["shadow_direction"].strip()
                             if out["shadow_direction"] else None),
        "horizon": out["horizon"].strip() if out["horizon"] else None,
        "technique": out["technique"].strip(),
        "contrast": out["contrast"],
        "element_flags": normalized_flags,
    }


# ---------------------------------------------------------------------
# Presets (GBT §3: six named shading techniques)
# ---------------------------------------------------------------------

PRESETS: dict[str, dict] = {
    "smooth-black-and-grey-realism": {
        "name": "Smooth black-and-grey realism",
        "defaults": {"technique": "smooth-black-and-grey-realism",
                     "intensity": 0.8, "softness": 0.75, "contrast": "medium"},
        "prompt_phrase": ("smooth black-and-grey realism shading, soft grey "
                          "transitions, no micro-detail texture"),
    },
    "soft-whip-shading": {
        "name": "Soft whip-shading",
        "defaults": {"technique": "soft-whip-shading",
                     "intensity": 0.7, "softness": 0.6, "contrast": "medium"},
        "prompt_phrase": ("soft whip-shading appearance, feathered grey "
                          "falloff at the edges of each shadow shape"),
    },
    "stipple": {
        "name": "Stipple shading",
        "defaults": {"technique": "stipple",
                     "intensity": 0.65, "softness": 0.35, "contrast": "medium"},
        "prompt_phrase": ("stipple shading, value built from clean dot "
                          "density, no smudged gradients"),
    },
    "traditional-solid": {
        "name": "Traditional solid-black and grey",
        "defaults": {"technique": "traditional-solid",
                     "intensity": 0.9, "softness": 0.25, "contrast": "high"},
        "prompt_phrase": ("traditional solid-black packing with flat grey "
                          "steps, bold separated value shapes"),
    },
    "high-contrast-illustrative": {
        "name": "High-contrast illustrative",
        "defaults": {"technique": "high-contrast-illustrative",
                     "intensity": 1.0, "softness": 0.3, "contrast": "high"},
        "prompt_phrase": ("high-contrast illustrative shading, strong black "
                          "separation, whites kept clean and open"),
    },
    "fine-line-minimal": {
        "name": "Fine-line minimal shading",
        "defaults": {"technique": "fine-line-minimal",
                     "intensity": 0.45, "softness": 0.5, "contrast": "low"},
        "prompt_phrase": ("fine-line minimal shading, the lightest grey "
                          "wash only where a form must turn, most of the "
                          "piece carried by line alone"),
    },
}


def list_presets() -> list[str]:
    """The preset keys, in directive order."""
    return list(PRESETS)


def get_preset(key: str) -> dict:
    """A preset as {key, name, defaults, prompt_phrase} — a copy, so
    callers may bend the defaults into their own spec safely."""
    if key not in PRESETS:
        raise KeyError(f"no lighting preset {key!r}; known: {sorted(PRESETS)}")
    preset = PRESETS[key]
    return {"key": key, "name": preset["name"],
            "defaults": dict(preset["defaults"]),
            "prompt_phrase": preset["prompt_phrase"]}


def spec_from_preset(key: str, **overrides) -> dict:
    """A validated spec dict built from a preset's defaults plus
    caller overrides — the convenient way to light a document."""
    data = dict(get_preset(key)["defaults"])
    data.update(overrides)
    return validate_lighting_spec(data)


# ---------------------------------------------------------------------
# Prompt rendering FROM the structure (never a free-text blob)
# ---------------------------------------------------------------------


def _softness_words(softness: float) -> str:
    if softness >= 0.66:
        return "soft, diffuse light with gradual shadow edges"
    if softness >= 0.33:
        return "moderately soft light with defined but eased shadow edges"
    return "hard light with crisp, sharp shadow edges"


def _intensity_words(intensity: float) -> str:
    if intensity >= 0.66:
        return "strong key light"
    if intensity >= 0.33:
        return "moderate key light"
    return "low, gentle key light"


def lighting_clause(spec) -> str:
    """Render a lighting spec as one prompt clause, derived field by
    field: direction + angle, intensity/softness words bucketed from
    the numeric values, the technique (a preset key renders as that
    preset's prompt phrase; free text renders verbatim), shadow
    direction, contrast, and horizon when set. Two specs that differ
    in any rendered field produce different clauses — the structure
    is what reaches the model."""
    data = validate_lighting_spec(spec)
    technique = data["technique"]
    if technique in PRESETS:
        technique_text = PRESETS[technique]["prompt_phrase"]
    else:
        technique_text = f"shading technique: {technique}"
    parts = [
        f"light source from the {data['direction']} "
        f"({data['angle_deg']:g} degrees)",
        _intensity_words(data["intensity"]),
        _softness_words(data["softness"]),
        technique_text,
        f"{data['contrast']} contrast value distribution",
    ]
    if data["shadow_direction"]:
        parts.append(f"shadows fall to the {data['shadow_direction']}")
    if data["horizon"]:
        parts.append(f"scene horizon: {data['horizon']}")
    lit = [lid for lid, f in data["element_flags"].items() if f["receive_light"]]
    shadowed = [lid for lid, f in data["element_flags"].items() if f["cast_shadow"]]
    if data["element_flags"]:
        parts.append(f"element light flags — receives light: "
                     f"{', '.join(lit) or 'none'}; casts shadow: "
                     f"{', '.join(shadowed) or 'none'}")
    return "lighting: " + ", ".join(parts)


# ---------------------------------------------------------------------
# Document attachment (recorded, undoable ops — the S5 pattern:
# validate first, push history, mutate, append to the ops log)
# ---------------------------------------------------------------------


def set_lighting(doc, spec) -> dict:
    """Validate `spec` and store it as the document's lighting
    (doc.lighting). Records a `doc.set_lighting` op and is undoable
    through the S5 history, exactly like the document's own ops.
    Passing None clears the lighting (also recorded). Validation
    failure raises ValueError before anything changes."""
    normalized = None if spec is None else validate_lighting_spec(spec)
    doc._push_history()
    doc.lighting = normalized
    doc.ops_log.append({"op": "doc.set_lighting", "lighting": normalized})
    return doc.lighting


def set_element_lighting(doc, layer_id: str, receive_light: bool | None = None,
                         cast_shadow: bool | None = None) -> dict:
    """Set one layer's receive_light / cast_shadow flags inside the
    document's lighting spec. Requires a spec to already be set
    (ValueError otherwise) and an existing layer (KeyError). Only
    the flags named change; the op is recorded and undoable, the
    same history path as set_lighting."""
    if doc.lighting is None:
        raise ValueError("set a lighting spec on the document before "
                         "setting per-element light flags")
    layer = doc.get(layer_id)  # KeyError for a missing layer
    flags = dict(doc.lighting.get("element_flags", {}))
    entry = dict(flags.get(layer.id, {"receive_light": True, "cast_shadow": True}))
    if receive_light is not None:
        entry["receive_light"] = bool(receive_light)
    if cast_shadow is not None:
        entry["cast_shadow"] = bool(cast_shadow)
    flags[layer.id] = entry
    updated = dict(doc.lighting)
    updated["element_flags"] = flags
    normalized = validate_lighting_spec(updated)
    doc._push_history()
    doc.lighting = normalized
    doc.ops_log.append({"op": "doc.set_element_lighting", "id": layer.id,
                        "flags": normalized["element_flags"][layer.id]})
    return normalized["element_flags"][layer.id]
