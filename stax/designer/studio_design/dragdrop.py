"""Drag-and-drop gestures + viewer state for the Studio Design Generator.

Direct manipulation and chat are two front ends over ONE command
system. A drag therefore never invents its own mutation path: each
gesture translates pointer movement into a call on the document's
existing typed ops (`layer.reorder`, `layer.transform`,
`layer.set_visible`), so the op appended to `doc.ops_log` is exactly
the op the equivalent chat instruction would append — same shape,
same values. A design built by dragging and one built by talking are
the same design, audit trail included.

Canvas drags are expressed in millimetres because the document is a
physical object (mm at the doc's DPI): the artist drags "two inches
lower", not "236 pixels lower". Distances snap to an mm grid
(default 1 mm) so a drag lands on the same coordinates the annotated
preview shows, instead of on arbitrary sub-millimetre positions no
one can name or reproduce in chat.
"""

from __future__ import annotations

import math

from .document import DesignDoc, mm_to_px

DEFAULT_SNAP_MM = 1.0


def snap_to_grid(value_mm: float, snap_mm: float | None) -> float:
    """Snap a millimetre value to the nearest multiple of `snap_mm`
    (halves round away from zero, so a drag behaves the same in both
    directions). `snap_mm` of None or 0 disables snapping."""
    if not snap_mm:
        return float(value_mm)
    if snap_mm < 0:
        raise ValueError("snap_mm must be >= 0")
    units = abs(value_mm) / snap_mm
    snapped = math.floor(units + 0.5) * snap_mm
    return math.copysign(snapped, value_mm) if value_mm else 0.0


def _px(mm_value: float, doc: DesignDoc) -> int:
    return mm_to_px(mm_value, doc.dpi)


def drag_layer(doc: DesignDoc, layer_id: str, to_index: int) -> dict:
    """Drag a layer to `to_index` in the stack (0 = bottom).

    Delegates to `doc.reorder`, which clamps out-of-range targets —
    a drag past the top or bottom of the stack lands on the end,
    it does not fail. Returns the appended ops-log entry."""
    doc.reorder(layer_id, int(to_index))
    return doc.ops_log[-1]


def drag_element(doc: DesignDoc, layer_id: str, dx_mm: float, dy_mm: float,
                 snap_mm: float | None = DEFAULT_SNAP_MM) -> dict:
    """Drag an element by (dx_mm, dy_mm), snapped to the mm grid.

    Emits exactly the `layer.transform` op a chat instruction with
    the same pixel delta would emit. Returns the appended entry,
    which carries the element's resulting x/y in pixels."""
    dx = _px(snap_to_grid(dx_mm, snap_mm), doc)
    dy = _px(snap_to_grid(dy_mm, snap_mm), doc)
    doc.transform(layer_id, dx=dx, dy=dy)
    return doc.ops_log[-1]


def drag_element_to(doc: DesignDoc, layer_id: str, x_mm: float, y_mm: float,
                    snap_mm: float | None = DEFAULT_SNAP_MM) -> dict:
    """Drag an element so its origin lands at (x_mm, y_mm), snapped.
    Emits the same `layer.transform` op shape as a relative drag."""
    x = _px(snap_to_grid(x_mm, snap_mm), doc)
    y = _px(snap_to_grid(y_mm, snap_mm), doc)
    doc.transform(layer_id, x=x, y=y)
    return doc.ops_log[-1]


def drag_rotate(doc: DesignDoc, layer_id: str, delta_degrees: float) -> dict:
    """Rotate an element by `delta_degrees` from its current angle.

    The transform op stores absolute rotation, so the delta is
    resolved against the layer's current value before delegating —
    the recorded op is the one a chat "rotate to N degrees" emits."""
    layer = doc.get(layer_id)
    doc.transform(layer_id, rotation=layer.rotation + float(delta_degrees))
    return doc.ops_log[-1]


def drag_scale(doc: DesignDoc, layer_id: str, factor: float) -> dict:
    """Scale an element by `factor` relative to its current scale
    (a pinch gesture is multiplicative; the recorded op carries the
    resulting absolute scale, as a chat "scale to N" would)."""
    if factor <= 0:
        raise ValueError("scale factor must be > 0")
    layer = doc.get(layer_id)
    doc.transform(layer_id, scale=layer.scale * float(factor))
    return doc.ops_log[-1]


def layer_position_mm(doc: DesignDoc, layer_id: str) -> tuple[float, float]:
    """An element's origin in millimetres — the coordinates the
    annotated preview speaks, for hosts that label a drag result."""
    layer = doc.get(layer_id)
    return (round(layer.x * 25.4 / doc.dpi, 2),
            round(layer.y * 25.4 / doc.dpi, 2))


class ViewerState:
    """Read-mostly viewer over one document: what the artist sees.

    The viewer owns no rendering or mutation logic of its own. Its
    canvas is the document's share composite (visible layers only —
    what is shared is what is live on the canvas), and its one
    mutation, the visibility toggle, delegates to `layer.set_visible`
    so the change and its audit entry are the chat op's. Selection is
    viewer-local state: it emits NO op, because selecting an element
    is not a change to the artwork and must never enter the history
    that undo and approval read from."""

    def __init__(self, doc: DesignDoc):
        self.doc = doc
        self._selected_id: str | None = doc.layers[-1].id if doc.layers else None

    # -- selection ------------------------------------------------------
    @property
    def selected_id(self) -> str | None:
        return self._selected_id

    def select(self, layer_id: str) -> str:
        self.doc.get(layer_id)  # unknown ids fail here, as everywhere
        self._selected_id = layer_id
        return layer_id

    def _require_selected(self) -> str:
        if self._selected_id is None:
            raise ValueError("no layer selected")
        return self._selected_id

    # -- views -----------------------------------------------------------
    def canvas(self):
        """The on-screen canvas image: visible layers only, exactly
        the image `share_canvas` would send."""
        return self.doc.share_canvas()

    def preview(self):
        """Flattened on-white preview (customer-style viewing)."""
        return self.doc.render_preview()

    def annotated(self):
        """Grid + numbered-outline render matching `layer_list`."""
        return self.doc.render_annotated()

    def layer_list(self) -> list[dict]:
        """Layer rows, top first, numbered as the annotated render
        and `layer_list_text` number them (1 = top)."""
        rows = []
        for i, layer in enumerate(reversed(self.doc.layers), start=1):
            rows.append({
                "number": i,
                "id": layer.id,
                "name": layer.name,
                "kind": layer.kind,
                "role": layer.role,
                "visible": layer.visible,
                "opacity": layer.opacity,
                "x": layer.x,
                "y": layer.y,
                "pos_mm": (round(layer.x * 25.4 / self.doc.dpi, 2),
                           round(layer.y * 25.4 / self.doc.dpi, 2)),
                "scale": layer.scale,
                "rotation": layer.rotation,
                "selected": layer.id == self._selected_id,
            })
        return rows

    # -- the viewer's one document mutation ------------------------------
    def toggle_visibility(self, layer_id: str) -> bool:
        """Flip a layer's visibility via the typed op; returns the
        new state. The canvas share changes accordingly because the
        share is the visible-only composite."""
        layer = self.doc.get(layer_id)
        self.doc.set_visible(layer_id, not layer.visible)
        return self.doc.get(layer_id).visible

    # -- gestures on the selection ---------------------------------------
    def drag_selected_layer(self, to_index: int) -> dict:
        return drag_layer(self.doc, self._require_selected(), to_index)

    def drag_selected(self, dx_mm: float, dy_mm: float,
                      snap_mm: float | None = DEFAULT_SNAP_MM) -> dict:
        return drag_element(self.doc, self._require_selected(),
                            dx_mm, dy_mm, snap_mm=snap_mm)

    def drag_selected_to(self, x_mm: float, y_mm: float,
                         snap_mm: float | None = DEFAULT_SNAP_MM) -> dict:
        return drag_element_to(self.doc, self._require_selected(),
                               x_mm, y_mm, snap_mm=snap_mm)

    def rotate_selected(self, delta_degrees: float) -> dict:
        return drag_rotate(self.doc, self._require_selected(), delta_degrees)

    def scale_selected(self, factor: float) -> dict:
        return drag_scale(self.doc, self._require_selected(), factor)
