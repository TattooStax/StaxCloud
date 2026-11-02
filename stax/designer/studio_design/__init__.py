"""Studio Design Generator — deterministic core (Slice 1) plus
generative support (Slice 2): routing, prompt building, matting /
line-shading split / stamp extraction, provenance records, and the
condition-6 linework measurement harness. The generative model call
itself lives in the agent's chat image path, not in this package.
Owner deltas 2026-11-02 add: per-artist versions-per-request,
canvas/layer sharing, the per-artist element library + stamp kits,
and profile style notes. Slice S3 adds the customer-facing flow:
one intake contract for sms/email/widget, the opt-in offer gate,
the full approval lifecycle, and the estimate guard. Slice S4 adds
drag-and-drop: gestures and a viewer state model that emit the
same typed ops as chat, so both front ends share one history.
Slice S5 (Foundation) adds layer locking (LockedError), undo/redo
history and named snapshots (runtime state, never persisted), and
the metered-cost field on generation records. Slice S6 adds the
structured lighting spec + six shading presets (lighting.py,
manifest-persisted on the document, injected into prompts from the
structure) and the outline-first workflow (outline.py): a locked
structural outline that shading plans must reference, and the
flood-fill closed-contour measurement — a report, never a verdict.
Slice S7 adds AI edit masks + protected regions (editmask.py):
an edit names one target and a protected set (the structural
outline is protected by default); the mask subtracts protection
last so it always wins; a model proposal is audited against the
protected areas and verified against the real before/after
documents, and any protected change refuses the edit with a
preview record instead of applying it. Deterministic transforms
are rejected from the AI path — they belong on the ops surface.
Slice S8 adds the cover-up workspace (coverup.py): the existing
tattoo's photo as a LOCKED 'reference' layer that no share, stencil
or PSD can contain, calibration from the doc's DPI, a darkness map
of the old ink, and a coverage analysis that highlights where the
new design is too light over it — an estimate for the artist,
carrying the no-guarantee-from-a-photo note in every record.
Slice S10 adds the bonus Procreate interchange (brush.py): stamp
elements and whole stamp kits exported as .brush / .brushset
files built to the 2026-10-30 format research (luminance Shape +
Grain sources, stamp parameters, NSKeyedArchiver Brush.archive,
brushset.plist manifest). Savage publishes no spec, so the export
is research-conformant and its importability is UNPROVEN — every
record carries that status; the iPad test-import against a real
Procreate export remains the integration gate.
Slice R1 adds durable recovery (REVIEW-GBT2 §A.5): a monotonic
revision counter on every document, bumped by each mutation and
checked against the base_revision async results carry (stale
results are refused, never landed); the snapshot store persisted
to disk so named approved versions survive restarts and restore
byte-identical; and atomic writes (temp + rename) as the
package's only file sink (storage.py).
"""

from .brush import (
    MAX_SOURCE_PX,
    SPEC_STATUS,
    brush_sources_from_stamp,
    build_brush_archive,
    export_stamp_brush,
    export_stamp_kit_as_brushset,
    parse_brush_archive,
    stamp_parameters,
)

from .coverup import (
    COVERAGE_MARGIN,
    DEFAULT_DARKNESS_THRESHOLD,
    GUARANTEE_NOTE,
    WARNING_COLOR,
    CoverUpRecord,
    calibration,
    coverage_analysis,
    create_coverup,
    darkness_map,
    export_coverup_design,
    export_highlight,
    px_per_mm,
    render_overlay,
    set_reference_opacity,
)
from .customer import (
    CHANNELS,
    STATES,
    CustomerFlow,
    DesignRequest,
    InvalidTransition,
    check_outbound,
    evaluate_offer,
    make_intake,
)
from .document import (
    HISTORY_MAX,
    SNAPSHOT_MAX,
    DesignDoc,
    Layer,
    LockedError,
    SnapshotStore,
    StaleRevisionError,
    mm_to_px,
)
from .storage import atomic_write_bytes, atomic_write_text
from .dragdrop import (
    ViewerState,
    drag_element,
    drag_element_to,
    drag_layer,
    drag_rotate,
    drag_scale,
    layer_position_mm,
    snap_to_grid,
)
from .generate import (
    GenerationRecord,
    PromptSpec,
    attach_record_to_layer,
    build_element_prompt,
    build_layout_prompt,
    make_stamp,
    matte_to_transparent,
    measure_linework,
    plan_three_versions,
    plan_versions,
    record_cost,
    route_request,
    split_line_shading,
)
from .editmask import (
    DeterministicIntentError,
    EditRequest,
    apply_edit,
    build_mask,
    classify_intent,
    effective_protected,
    validate_edit_request,
    verify_protected,
)
from .library import ElementLibrary
from .lighting import (
    PRESETS,
    LightingSpec,
    get_preset,
    lighting_clause,
    list_presets,
    set_element_lighting,
    set_lighting,
    spec_from_preset,
    validate_lighting_spec,
)
from .outline import measure_contours, set_structural_outline, shading_plan
from .profiles import ProfileStore, seed_fargo_tattoo
from .validate import validate_document, validate_element

__version__ = "0.10.0"
__all__ = [
    "DesignDoc",
    "Layer",
    "LockedError",
    "SnapshotStore",
    "StaleRevisionError",
    "atomic_write_bytes",
    "atomic_write_text",
    "HISTORY_MAX",
    "SNAPSHOT_MAX",
    "mm_to_px",
    "CHANNELS",
    "STATES",
    "CustomerFlow",
    "DesignRequest",
    "InvalidTransition",
    "check_outbound",
    "evaluate_offer",
    "make_intake",
    "ProfileStore",
    "seed_fargo_tattoo",
    "validate_document",
    "validate_element",
    "GenerationRecord",
    "PromptSpec",
    "attach_record_to_layer",
    "build_element_prompt",
    "build_layout_prompt",
    "make_stamp",
    "matte_to_transparent",
    "measure_linework",
    "plan_three_versions",
    "plan_versions",
    "record_cost",
    "route_request",
    "split_line_shading",
    "ElementLibrary",
    "EditRequest",
    "DeterministicIntentError",
    "classify_intent",
    "validate_edit_request",
    "effective_protected",
    "build_mask",
    "verify_protected",
    "apply_edit",
    "LightingSpec",
    "PRESETS",
    "get_preset",
    "list_presets",
    "spec_from_preset",
    "validate_lighting_spec",
    "lighting_clause",
    "set_lighting",
    "set_element_lighting",
    "set_structural_outline",
    "shading_plan",
    "measure_contours",
    "CoverUpRecord",
    "GUARANTEE_NOTE",
    "COVERAGE_MARGIN",
    "DEFAULT_DARKNESS_THRESHOLD",
    "WARNING_COLOR",
    "create_coverup",
    "calibration",
    "px_per_mm",
    "set_reference_opacity",
    "render_overlay",
    "darkness_map",
    "coverage_analysis",
    "export_highlight",
    "export_coverup_design",
    "ViewerState",
    "drag_element",
    "drag_element_to",
    "drag_layer",
    "drag_rotate",
    "drag_scale",
    "layer_position_mm",
    "snap_to_grid",
    "MAX_SOURCE_PX",
    "SPEC_STATUS",
    "brush_sources_from_stamp",
    "stamp_parameters",
    "build_brush_archive",
    "parse_brush_archive",
    "export_stamp_brush",
    "export_stamp_kit_as_brushset",
]
