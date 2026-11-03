"""Layered design document — deterministic core of the Studio Design Generator.

Native format (Director verdict 2026-10-30, Q4; PLAN-v2 §3):

    <doc>/
      manifest.json   {id, version, width_mm, height_mm, dpi, layers: [...]}
      layers/
        <layer_id>.png      RGBA raster elements
        <layer_id>.l8.png   luminance stamp masks (tinted at render time)

Physical size is carried in mm at 300 DPI from creation; per-element
provenance is stored from day one even though Slice 1 has nothing
generative to record. The ops surface is a whitelist: elements, not
pixels — add / transform / reorder / opacity / remove, render, export.
No painting, no brushes.

Slice S5 (Foundation) adds three things on top of the whitelist:

- LOCKING: a layer's `locked` flag lives in the manifest. A locked
  layer refuses every mutating op (LockedError, nothing changes) —
  protected artwork is an invariant, not a suggestion.
- UNDO/REDO + SNAPSHOTS: document history and named snapshots are
  RUNTIME state, held in memory alongside the document. They are
  deliberately NOT part of the manifest or the saved bundle: a saved
  document carries the artwork and its audit log, not the session's
  undo stack. History is captured at op granularity through the same
  entries serialization save/load uses, so a restored state is the
  exact state, pixels included.

Slice S6 adds document content fields that DO persist: `lighting`
(the structured lighting spec from lighting.py) and `outline_layer`
(the structural outline's layer id), plus `set_structural_outline`,
which locks a line layer as the geometry shading must respect.

Slice S8 adds ONE layer role, `reference` (cover-up workspace,
coverup.py): a photograph of the existing tattoo, used as a locked
working underlay. A reference layer is NEVER artwork: `render()`
(and therefore share_canvas, previews and the PSD composite) skips
it, the PSD layer list omits it, and the stencil — built from
'line' layers only — cannot contain it. The sanctioned way to SEE
the reference under a design is coverup.render_overlay.

Slice R1 (durable recovery, REVIEW-GBT2 §A.5/§B.1/§B.2) adds:

- REVISION: every document carries `revision`, a monotonically
  increasing integer bumped by EVERY successful mutation through
  the op system — layer ops, locking, lighting, undo/redo and
  snapshot restores included (a state swap is a mutation: a result
  computed before it is stale after it). The counter is NOT part
  of the manifest (content hashes keep measuring artwork alone);
  it persists as a `revision.json` entry beside the manifest in
  every serialization, so it round-trips save/load. Async results
  (edit requests, host jobs) carry the revision they were computed
  against as `base_revision`; applying one whose base no longer
  matches is refused (editmask.apply_edit, StaleRevisionError).
- DURABLE SNAPSHOTS: the S5 runtime snapshot store gains a
  persistence layer (SnapshotStore.save_to / load_from): named
  snapshots — approved flag and the never-auto-evict rule
  included — written to a directory beside the document, so an
  approved version survives a process restart and restores
  byte-identical (manifest + layer bytes).
- ATOMIC WRITES: save() lands every file through
  storage.atomic_write_bytes (temp + rename); a crash mid-save
  leaves the old file or the new one, never a torn one.

The document serializes to an ordered set of (arcname, bytes) entries.
A directory on disk and a .zip bundle are two sinks for the exact same
entries, so save/load behaviour is identical across hosts (directory for
StaxCloud/InkStax package stores, bundle for Fang kv storage).
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import zipfile

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .storage import atomic_write_bytes

FORMAT_VERSION = 1
DEFAULT_DPI = 300
BLEND_MODES = ("normal", "multiply", "screen", "overlay")
# "reference" (S8) is the cover-up photo underlay: locked on
# creation by coverup.py and excluded from every artwork render /
# export (see the module header). It exists so an old tattoo can be
# designed against without ever becoming part of the design.
ROLES = ("line", "shading", "color", "art", "reference")

# Runtime history / snapshot caps (S5). States are full document
# bundles held in memory, so both stores are capped: history keeps
# the newest HISTORY_MAX prior states, and the snapshot store keeps
# at most SNAPSHOT_MAX named snapshots per document.
HISTORY_MAX = 50
SNAPSHOT_MAX = 20


class LockedError(Exception):
    """A mutating op was attempted on a locked layer.

    Raised BEFORE anything changes: the document, the layer, and the
    ops log are exactly as they were before the refused op."""


class StaleRevisionError(Exception):
    """An async result was offered against a revision the document
    has since moved past (R1). Carries both revisions so a host can
    record the refusal verbatim: the result was computed against
    `base_revision`, the document is now at `current_revision`, and
    NOTHING was applied — a delayed AI/job result can never silently
    overwrite newer edits."""

    def __init__(self, doc_id: str, base_revision: int, current_revision: int):
        self.doc_id = doc_id
        self.base_revision = int(base_revision)
        self.current_revision = int(current_revision)
        super().__init__(
            f"stale result for doc {doc_id!r}: computed against "
            f"revision {self.base_revision}, document is now at "
            f"revision {self.current_revision} — refused, nothing applied")


def mm_to_px(mm: float, dpi: int = DEFAULT_DPI) -> int:
    """Physical millimetres to pixels at the given DPI (round-half-up)."""
    return int(math.floor(mm * dpi / 25.4 + 0.5))


class Layer:
    """One element in the stack. `image` is the element's own pixels:
    RGBA for rasters, mode 'L' luminance mask for stamps."""

    def __init__(
        self,
        layer_id: str,
        name: str,
        kind: str,
        image: Image.Image,
        x: int = 0,
        y: int = 0,
        scale: float = 1.0,
        rotation: float = 0.0,
        opacity: float = 1.0,
        blend: str = "normal",
        visible: bool = True,
        tint: tuple | None = None,
        role: str = "art",
        provenance: dict | None = None,
        locked: bool = False,
    ):
        if kind not in ("raster", "stamp"):
            raise ValueError(f"unknown layer kind: {kind!r}")
        if blend not in BLEND_MODES:
            raise ValueError(f"blend mode {blend!r} outside the PSD-safe subset")
        if role not in ROLES:
            raise ValueError(f"unknown layer role: {role!r}")
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be within 0..1")
        self.id = layer_id
        self.name = name
        self.kind = kind
        self.image = image
        self.x = int(x)
        self.y = int(y)
        self.scale = float(scale)
        self.rotation = float(rotation)
        self.opacity = float(opacity)
        self.blend = blend
        self.visible = bool(visible)
        self.tint = tuple(tint) if tint is not None else None
        self.role = role
        self.provenance = provenance or {"source": "artist-supplied"}
        self.locked = bool(locked)

    # -- serialization -------------------------------------------------
    @property
    def filename(self) -> str:
        return f"{self.id}.l8.png" if self.kind == "stamp" else f"{self.id}.png"

    def to_manifest(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "role": self.role,
            "file": self.filename,
            "x": self.x,
            "y": self.y,
            "scale": self.scale,
            "rotation": self.rotation,
            "opacity": self.opacity,
            "blend": self.blend,
            "visible": self.visible,
            "locked": self.locked,
            "tint": list(self.tint) if self.tint is not None else None,
            "provenance": self.provenance,
        }

    # -- rendering ------------------------------------------------------
    def content_image(self) -> Image.Image:
        """The element's own pixels, scale/rotation applied, before placement."""
        if self.kind == "stamp":
            mask = self.image.convert("L")
            if self.scale != 1.0:
                mask = mask.resize(
                    (max(1, round(mask.width * self.scale)),
                     max(1, round(mask.height * self.scale))),
                    Image.NEAREST,
                )
            if self.rotation:
                mask = mask.rotate(self.rotation, expand=True, resample=Image.NEAREST)
            tint = self.tint if self.tint is not None else (0, 0, 0)
            out = Image.new("RGBA", mask.size, tint + (0,))
            out.putalpha(mask)
            return out
        img = self.image.convert("RGBA")
        if self.scale != 1.0:
            img = img.resize(
                (max(1, round(img.width * self.scale)),
                 max(1, round(img.height * self.scale))),
                Image.BICUBIC,
            )
        if self.rotation:
            img = img.rotate(self.rotation, expand=True, resample=Image.BICUBIC)
        return img

    def placed_bbox(self) -> tuple[int, int, int, int]:
        content = self.content_image()
        return (self.x, self.y, self.x + content.width, self.y + content.height)


class SnapshotStore:
    """Named document snapshots for one document session (runtime only).

    Each record is {name, bundle, approved, seq}: the bundle is the
    document's own zip serialization, so a restore is byte-exact.
    The store is capped at SNAPSHOT_MAX records; when a new name
    would exceed the cap, the OLDEST NON-APPROVED snapshot is
    evicted first. Approved snapshots (an artist's signed-off
    versions) are never evicted automatically — if the store is full
    of approved snapshots, adding another raises ValueError rather
    than silently dropping one."""

    def __init__(self, max_snapshots: int = SNAPSHOT_MAX):
        self.max_snapshots = int(max_snapshots)
        self._records: dict[str, dict] = {}
        self._seq = 0

    def put(self, name: str, bundle: bytes, approved: bool = False) -> dict:
        if name not in self._records and len(self._records) >= self.max_snapshots:
            evictable = [r for r in self._records.values() if not r["approved"]]
            if not evictable:
                raise ValueError(
                    "snapshot store is full of approved snapshots; "
                    "delete one explicitly before adding another")
            oldest = min(evictable, key=lambda r: r["seq"])
            del self._records[oldest["name"]]
        self._seq += 1
        record = {"name": name, "bundle": bytes(bundle),
                  "approved": bool(approved), "seq": self._seq}
        self._records[name] = record
        return {"name": name, "approved": record["approved"]}

    def get(self, name: str) -> dict:
        if name not in self._records:
            raise KeyError(f"no snapshot named {name!r}")
        return self._records[name]

    def delete(self, name: str) -> None:
        if name not in self._records:
            raise KeyError(f"no snapshot named {name!r}")
        del self._records[name]

    def list(self) -> list[dict]:
        """Snapshot metadata (no bundle bytes), oldest first."""
        return [{"name": r["name"], "approved": r["approved"]}
                for r in sorted(self._records.values(), key=lambda r: r["seq"])]

    def __contains__(self, name: str) -> bool:
        return name in self._records

    def __len__(self) -> int:
        return len(self._records)

    # -- durable persistence (R1): the store on disk -------------------
    # Layout of the directory save_to writes:
    #   index.json       {"max_snapshots": n, "records":
    #                     [{name, approved, seq, file}, ...]}
    #   snap-<seq>.zip   one snapshot's bundle bytes, verbatim
    # Every file lands atomically (storage.atomic_write_bytes), and
    # bundle files orphaned by a re-put under the same name are
    # removed, so the directory always mirrors the store exactly.
    # The invariants are the runtime ones, enforced identically on
    # load: the cap evicts oldest NON-APPROVED first; approved
    # snapshots are never evicted automatically — a directory whose
    # records are all approved keeps all of them rather than
    # dropping one to fit the cap.

    def _enforce_cap(self) -> None:
        while len(self._records) > self.max_snapshots:
            evictable = [r for r in self._records.values()
                         if not r["approved"]]
            if not evictable:
                break  # approved overflow is kept, never dropped
            oldest = min(evictable, key=lambda r: r["seq"])
            del self._records[oldest["name"]]

    def to_records(self) -> list[dict]:
        """The whole store as JSON-able records (bundles base64'd) —
        the transport form a host kv store can carry verbatim."""
        return [{"name": r["name"], "approved": r["approved"],
                 "seq": r["seq"],
                 "bundle_b64": base64.b64encode(r["bundle"]).decode("ascii")}
                for r in sorted(self._records.values(), key=lambda r: r["seq"])]

    @classmethod
    def from_records(cls, records: list[dict],
                     max_snapshots: int = SNAPSHOT_MAX) -> "SnapshotStore":
        store = cls(max_snapshots=max_snapshots)
        for rec in records:
            store._records[rec["name"]] = {
                "name": rec["name"], "bundle": base64.b64decode(rec["bundle_b64"]),
                "approved": bool(rec["approved"]), "seq": int(rec["seq"])}
            store._seq = max(store._seq, int(rec["seq"]))
        store._enforce_cap()
        return store

    def save_to(self, dirpath: str) -> str:
        """Persist every snapshot in this store under `dirpath`
        (created if needed), atomically. Returns the dirpath."""
        os.makedirs(dirpath, exist_ok=True)
        index = {"max_snapshots": self.max_snapshots, "records": []}
        live_files = set()
        for r in sorted(self._records.values(), key=lambda r: r["seq"]):
            fname = f"snap-{r['seq']}.zip"
            atomic_write_bytes(os.path.join(dirpath, fname), r["bundle"])
            live_files.add(fname)
            index["records"].append({"name": r["name"],
                                     "approved": r["approved"],
                                     "seq": r["seq"], "file": fname})
        for existing in os.listdir(dirpath):
            if (existing.startswith("snap-") and existing.endswith(".zip")
                    and existing not in live_files):
                os.unlink(os.path.join(dirpath, existing))
        atomic_write_bytes(os.path.join(dirpath, "index.json"),
                           json.dumps(index, indent=2).encode("utf-8"))
        return dirpath

    @classmethod
    def load_from(cls, dirpath: str,
                  max_snapshots: int | None = None) -> "SnapshotStore":
        """Rebuild a store from a save_to directory. A missing
        directory or index yields an EMPTY store (a document that
        never persisted snapshots has none — not an error)."""
        index_path = os.path.join(dirpath, "index.json")
        if not os.path.exists(index_path):
            return cls(max_snapshots=max_snapshots or SNAPSHOT_MAX)
        with open(index_path, "rb") as f:
            index = json.loads(f.read().decode("utf-8"))
        store = cls(max_snapshots=max_snapshots
                    or int(index.get("max_snapshots", SNAPSHOT_MAX)))
        for rec in index.get("records", []):
            with open(os.path.join(dirpath, rec["file"]), "rb") as f:
                bundle = f.read()
            store._records[rec["name"]] = {
                "name": rec["name"], "bundle": bundle,
                "approved": bool(rec["approved"]), "seq": int(rec["seq"])}
            store._seq = max(store._seq, int(rec["seq"]))
        store._enforce_cap()
        return store


class DesignDoc:
    """A layered document. `layers` is ordered bottom-first (index 0 is
    the bottom of the stack), matching paint order."""

    def __init__(self, doc_id: str, width_mm: float, height_mm: float, dpi: int = DEFAULT_DPI):
        self.id = doc_id
        self.width_mm = float(width_mm)
        self.height_mm = float(height_mm)
        self.dpi = int(dpi)
        self.layers: list[Layer] = []
        self._counter = 0
        self.ops_log: list[dict] = []
        # R1: the mutation counter async results are checked
        # against (see the module header). Starts at 0; bumped by
        # _note_mutation at the end of every successful mutating
        # op, state swaps (undo/redo/restore) included. Persisted
        # as the bundle's revision.json entry, never in the
        # manifest, so content hashes measure artwork alone.
        self.revision: int = 0
        # S6: structured lighting spec (a plain JSON dict as produced
        # by lighting.validate_lighting_spec, or None) and the
        # structural outline layer id (or None). Both are document
        # content — they live in the manifest and round-trip saves,
        # unlike S5 history/snapshots, which are session state.
        self.lighting: dict | None = None
        self.outline_layer: str | None = None
        # Runtime-only session state (S5): undo/redo history and the
        # snapshot store. Neither is persisted in the manifest/bundle.
        self._history: list[bytes] = []
        self._redo: list[bytes] = []
        self.snapshots = SnapshotStore()

    # -- geometry --------------------------------------------------------
    @property
    def width_px(self) -> int:
        return mm_to_px(self.width_mm, self.dpi)

    @property
    def height_px(self) -> int:
        return mm_to_px(self.height_mm, self.dpi)

    @property
    def size_px(self) -> tuple[int, int]:
        return (self.width_px, self.height_px)

    # -- construction ------------------------------------------------------
    @classmethod
    def create(cls, doc_id: str, width_mm: float, height_mm: float, dpi: int = DEFAULT_DPI) -> "DesignDoc":
        doc = cls(doc_id, width_mm, height_mm, dpi)
        doc.ops_log.append({"op": "doc.create", "width_mm": width_mm, "height_mm": height_mm, "dpi": dpi})
        return doc

    def _next_id(self) -> str:
        self._counter += 1
        return f"L{self._counter}"

    def _note_mutation(self) -> int:
        """Advance the revision counter after a successful mutation
        (R1). Called exactly once at the END of each mutating op —
        after validation, history capture, the mutation itself and
        the ops-log entry — so a refused op never advances it and a
        landed one always does. Returns the new revision."""
        self.revision += 1
        return self.revision

    def get(self, layer_id: str) -> Layer:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        raise KeyError(f"no layer with id {layer_id!r}")

    # -- history internals (S5: runtime state, never persisted) ------------
    def _capture_state(self) -> bytes:
        """The document's full content state as bundle bytes — the
        same serialization save/load uses, so a capture restored
        later is the exact state, pixels included. The ops log is
        NOT part of the captured state: it is an append-only audit
        trail, and undo/redo/restore add their own entries to it
        instead of rewinding it."""
        return self.save_bundle()

    def _restore_state(self, bundle: bytes) -> None:
        """Swap this document's content to a captured state, in place
        (callers and viewers holding this doc see the restored state).
        History stacks, the snapshot store, and the ops log are
        session state and are left untouched. The REVISION is also
        left untouched: it counts this live document's mutations and
        never rewinds — the public op performing the swap (undo /
        redo / restore_snapshot) bumps it via _note_mutation, so a
        result computed against the pre-swap state is stale after
        the swap even though the artwork went back."""
        other = DesignDoc.load_bundle(bundle)
        self.id = other.id
        self.width_mm = other.width_mm
        self.height_mm = other.height_mm
        self.dpi = other.dpi
        self.layers = other.layers
        self._counter = other._counter
        self.lighting = other.lighting
        self.outline_layer = other.outline_layer

    def _push_history(self) -> None:
        """Record the pre-op state for undo. Called by every mutating
        op AFTER its validation has passed and BEFORE it mutates, so
        a refused op (locked layer, bad value) never pollutes the
        history. A new op clears the redo branch."""
        self._history.append(self._capture_state())
        if len(self._history) > HISTORY_MAX:
            del self._history[: len(self._history) - HISTORY_MAX]
        self._redo.clear()

    def undo(self) -> bool:
        """Restore the state before the most recent mutating op.
        Returns False (a clean no-op) when there is nothing to undo."""
        if not self._history:
            return False
        self._redo.append(self._capture_state())
        if len(self._redo) > HISTORY_MAX:
            del self._redo[: len(self._redo) - HISTORY_MAX]
        self._restore_state(self._history.pop())
        self.ops_log.append({"op": "doc.undo"})
        self._note_mutation()
        return True

    def redo(self) -> bool:
        """Re-apply the most recently undone state. Returns False
        (a clean no-op) when the redo branch is empty — including
        after any new op, which clears it."""
        if not self._redo:
            return False
        self._history.append(self._capture_state())
        if len(self._history) > HISTORY_MAX:
            del self._history[: len(self._history) - HISTORY_MAX]
        self._restore_state(self._redo.pop())
        self.ops_log.append({"op": "doc.redo"})
        self._note_mutation()
        return True

    # -- snapshots (S5: runtime store, named restore points) ----------------
    def snapshot(self, name: str, approved: bool = False) -> dict:
        """Capture the current state under `name` in this session's
        snapshot store. `approved=True` marks an artist's signed-off
        version; approved snapshots are never evicted automatically.
        Taking a snapshot does not mutate the document."""
        record = self.snapshots.put(name, self._capture_state(), approved=approved)
        self.ops_log.append({"op": "doc.snapshot", "name": name,
                             "approved": bool(approved)})
        return record

    def restore_snapshot(self, name: str) -> bool:
        """Return the document to the exact state captured under
        `name` (manifest + pixels identical). The restore is itself
        a mutating op for history purposes: the pre-restore state is
        pushed, so an accidental restore can be undone."""
        record = self.snapshots.get(name)  # KeyError for unknown names
        self._push_history()
        self._restore_state(record["bundle"])
        self.ops_log.append({"op": "doc.restore_snapshot", "name": name})
        self._note_mutation()
        return True

    def list_snapshots(self) -> list[dict]:
        return self.snapshots.list()

    # -- durable snapshots (R1: the S5 store, persisted) ----------------
    def save_snapshot_store(self, dirpath: str) -> str:
        """Persist this document's snapshot store to `dirpath`
        (SnapshotStore.save_to's layout), so named snapshots —
        approved versions included — survive a process restart.
        Beside the document directory is the convention:
        save_snapshots_beside / load_snapshots_beside use
        `<doc dir>/snapshots`."""
        return self.snapshots.save_to(dirpath)

    def load_snapshot_store(self, dirpath: str) -> SnapshotStore:
        """Replace this document's snapshot store with the one
        persisted at `dirpath` (an empty store when nothing was
        ever saved there). The snapshots then restore through the
        ordinary restore_snapshot op."""
        self.snapshots = SnapshotStore.load_from(dirpath)
        return self.snapshots

    def save_snapshots_beside(self, doc_dir: str) -> str:
        return self.save_snapshot_store(os.path.join(doc_dir, "snapshots"))

    def load_snapshots_beside(self, doc_dir: str) -> SnapshotStore:
        return self.load_snapshot_store(os.path.join(doc_dir, "snapshots"))

    # -- locking (S5) ---------------------------------------------------------
    @staticmethod
    def _require_unlocked(layer: Layer) -> None:
        if layer.locked:
            raise LockedError(
                f"layer {layer.id!r} ({layer.name!r}) is locked; "
                "unlock it before mutating it")

    def lock_layer(self, layer_id: str) -> None:
        layer = self.get(layer_id)
        self._push_history()
        layer.locked = True
        self.ops_log.append({"op": "layer.lock", "id": layer_id})
        self._note_mutation()

    def unlock_layer(self, layer_id: str) -> None:
        layer = self.get(layer_id)
        self._push_history()
        layer.locked = False
        self.ops_log.append({"op": "layer.unlock", "id": layer_id})
        self._note_mutation()

    # -- layer ops (the whitelist) -----------------------------------------
    def add_raster(self, name: str, image: Image.Image, x: int = 0, y: int = 0,
                   scale: float = 1.0, rotation: float = 0.0, opacity: float = 1.0,
                   blend: str = "normal", role: str = "art",
                   provenance: dict | None = None, locked: bool = False) -> str:
        layer = Layer(self._next_id(), name, "raster", image.convert("RGBA"),
                      x=x, y=y, scale=scale, rotation=rotation, opacity=opacity,
                      blend=blend, role=role, provenance=provenance, locked=locked)
        self._push_history()
        self.layers.append(layer)
        self.ops_log.append({"op": "layer.add_raster", "id": layer.id, "name": name})
        self._note_mutation()
        return layer.id

    def add_stamp(self, name: str, luminance: Image.Image, x: int = 0, y: int = 0,
                  scale: float = 1.0, rotation: float = 0.0, opacity: float = 1.0,
                  tint: tuple | None = (0, 0, 0), role: str = "line",
                  provenance: dict | None = None, locked: bool = False) -> str:
        layer = Layer(self._next_id(), name, "stamp", luminance.convert("L"),
                      x=x, y=y, scale=scale, rotation=rotation, opacity=opacity,
                      tint=tint, role=role, provenance=provenance, locked=locked)
        self._push_history()
        self.layers.append(layer)
        self.ops_log.append({"op": "layer.add_stamp", "id": layer.id, "name": name})
        self._note_mutation()
        return layer.id

    def transform(self, layer_id: str, x: int | None = None, y: int | None = None,
                  dx: int = 0, dy: int = 0, scale: float | None = None,
                  rotation: float | None = None) -> None:
        layer = self.get(layer_id)
        self._require_unlocked(layer)
        self._push_history()
        if x is not None:
            layer.x = int(x)
        if y is not None:
            layer.y = int(y)
        layer.x += int(dx)
        layer.y += int(dy)
        if scale is not None:
            layer.scale = float(scale)
        if rotation is not None:
            layer.rotation = float(rotation)
        self.ops_log.append({"op": "layer.transform", "id": layer_id,
                             "x": layer.x, "y": layer.y, "scale": layer.scale,
                             "rotation": layer.rotation})
        self._note_mutation()

    def reorder(self, layer_id: str, new_index: int) -> None:
        """Move a layer to `new_index` in the stack (0 = bottom)."""
        layer = self.get(layer_id)
        self._require_unlocked(layer)
        self._push_history()
        self.layers.remove(layer)
        new_index = max(0, min(new_index, len(self.layers)))
        self.layers.insert(new_index, layer)
        self.ops_log.append({"op": "layer.reorder", "id": layer_id, "index": new_index})
        self._note_mutation()

    def move_below(self, layer_id: str, other_id: str) -> None:
        other = self.get(other_id)
        layer = self.get(layer_id)
        self._require_unlocked(layer)
        self._push_history()
        self.layers.remove(layer)
        self.layers.insert(self.layers.index(other), layer)
        self.ops_log.append({"op": "layer.reorder", "id": layer_id, "below": other_id})
        self._note_mutation()

    def move_above(self, layer_id: str, other_id: str) -> None:
        other = self.get(other_id)
        layer = self.get(layer_id)
        self._require_unlocked(layer)
        self._push_history()
        self.layers.remove(layer)
        self.layers.insert(self.layers.index(other) + 1, layer)
        self.ops_log.append({"op": "layer.reorder", "id": layer_id, "above": other_id})
        self._note_mutation()

    def set_opacity(self, layer_id: str, opacity: float) -> None:
        layer = self.get(layer_id)
        self._require_unlocked(layer)
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be within 0..1")
        self._push_history()
        layer.opacity = float(opacity)
        self.ops_log.append({"op": "layer.set_opacity", "id": layer_id, "opacity": opacity})
        self._note_mutation()

    def set_visible(self, layer_id: str, visible: bool) -> None:
        layer = self.get(layer_id)
        self._require_unlocked(layer)
        self._push_history()
        layer.visible = bool(visible)
        self.ops_log.append({"op": "layer.set_visible", "id": layer_id, "visible": visible})
        self._note_mutation()

    def remove(self, layer_id: str) -> None:
        layer = self.get(layer_id)
        self._require_unlocked(layer)
        self._push_history()
        self.layers.remove(layer)
        self.ops_log.append({"op": "layer.remove", "id": layer_id})
        self._note_mutation()

    # -- outline-first (S6) ------------------------------------------------
    def set_structural_outline(self, layer_id: str) -> str:
        """Mark a line layer as the document's structural outline
        (outline-first workflow, REVIEW §2 D): the layer is LOCKED
        (S5) so later shading work cannot move or alter the geometry
        it defines, and its id is recorded on the document as
        `outline_layer` (manifest-persisted) so shading plans must
        reference it (see outline.shading_plan). Marking is a
        recorded, undoable op. Only a layer with role 'line' can be
        the structural outline — marking anything else raises
        ValueError before anything changes."""
        layer = self.get(layer_id)
        if layer.role != "line":
            raise ValueError(
                f"structural outline must be a 'line' layer; "
                f"layer {layer_id!r} has role {layer.role!r}")
        self._push_history()
        layer.locked = True
        self.outline_layer = layer_id
        self.ops_log.append({"op": "doc.set_structural_outline", "id": layer_id})
        self._note_mutation()
        return layer_id

    # -- rendering ---------------------------------------------------------
    def _render_layer_full(self, layer: Layer, apply_opacity: bool = True) -> Image.Image:
        """One layer rendered onto a transparent full-canvas image."""
        canvas = Image.new("RGBA", self.size_px, (0, 0, 0, 0))
        content = layer.content_image()
        if apply_opacity and layer.opacity < 1.0:
            alpha = content.getchannel("A").point(lambda a: round(a * layer.opacity))
            content = content.copy()
            content.putalpha(alpha)
        canvas.alpha_composite(content, (layer.x, layer.y))
        return canvas

    def render(self) -> Image.Image:
        """Clean composite: visible layers in stack order on transparency.

        Layers with role 'reference' (S8 cover-up photos) are skipped
        unconditionally: a reference is a working underlay, never part
        of the artwork, so it appears in NO composite — not in shares,
        previews, or exports — however it is set. coverup.py's
        render_overlay is the one place it is drawn, deliberately."""
        canvas = Image.new("RGBA", self.size_px, (0, 0, 0, 0))
        for layer in self.layers:
            if not layer.visible or layer.role == "reference":
                continue
            canvas = _blend(canvas, self._render_layer_full(layer), layer.blend)
        return canvas

    def render_preview(self) -> Image.Image:
        """Flattened on-white preview (chat / customer viewing)."""
        white = Image.new("RGBA", self.size_px, (255, 255, 255, 255))
        white.alpha_composite(self.render())
        return white.convert("RGB")

    # -- sharing (owner rule 2026-11-02: what's shared is what's live
    #    on the canvas) ---------------------------------------------------
    def share_canvas(self) -> Image.Image:
        """The shareable canvas image: the composite of VISIBLE layers
        only, exactly as the artist sees it on screen.

        THE RULE: what gets shared is what's live on the canvas —
        a hidden layer is NEVER in a canvas share. Turn the shading
        layer off and the share is the linework alone (which is also,
        by construction, the stencil); turn it back on and the share
        carries line + shading together. This is the same visible-only
        composite `render()` produces; sharing adds no second path
        that could leak a hidden layer."""
        return self.render()

    def share_layer(self, layer_id: str) -> bytes:
        """Share ONE layer on its own, as RGBA PNG bytes.

        The layer is rendered alone at full canvas size — its own
        placement, scale/rotation, tint (for stamps) and opacity
        applied, the same rendering the compositor uses — and no other
        layer contributes a pixel, regardless of the other layers'
        state. An explicit per-layer share is a deliberate artist
        action, so it works even while the layer is hidden from the
        canvas (hiding gates canvas shares, not this export). PNG
        encoding uses the same BytesIO save the document serializer
        (`to_entries`) uses for layer payloads."""
        layer = self.get(layer_id)
        buf = io.BytesIO()
        self._render_layer_full(layer).save(buf, "PNG")
        return buf.getvalue()

    _ANNOTATION_COLORS = [
        (220, 40, 40), (30, 120, 220), (20, 160, 60), (200, 130, 10),
        (150, 50, 200), (10, 160, 170), (230, 90, 160),
    ]

    def render_annotated(self) -> Image.Image:
        """On-white preview with a light mm grid and a numbered outline
        per visible layer, so an artist can direct chat ops by number
        ('move 3 down-left'). Numbers match `layer_list_text`: 1 = top."""
        img = Image.new("RGBA", self.size_px, (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)
        step = mm_to_px(10, self.dpi)
        for gx in range(step, self.width_px, step):
            draw.line([(gx, 0), (gx, self.height_px)], fill=(225, 225, 225, 255))
        for gy in range(step, self.height_px, step):
            draw.line([(0, gy), (self.width_px, gy)], fill=(225, 225, 225, 255))
        img.alpha_composite(self.render())
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        numbered = list(reversed([l for l in self.layers if l.visible]))  # top first
        for i, layer in enumerate(numbered, start=1):
            color = self._ANNOTATION_COLORS[(i - 1) % len(self._ANNOTATION_COLORS)] + (255,)
            bbox = layer.placed_bbox()
            draw.rectangle(bbox, outline=color, width=3)
            label = str(i)
            draw.rectangle([bbox[0], bbox[1], bbox[0] + 26, bbox[1] + 26], fill=color)
            draw.text((bbox[0] + 8, bbox[1] + 6), label, fill=(255, 255, 255, 255), font=font)
        return img.convert("RGB")

    def layer_list_text(self) -> str:
        """Text layer list printed under every chat render: '1 = top'."""
        numbered = list(reversed(self.layers))
        parts = [f"{i} {layer.name}" + ("" if layer.visible else " (hidden)")
                 for i, layer in enumerate(numbered, start=1)]
        return " · ".join(parts)

    # -- stencil -------------------------------------------------------------
    def export_stencil(self) -> Image.Image:
        """Pure-black linework at exact print size, NOT mirrored.

        Built from the alpha of visible layers whose role is 'line':
        any covered pixel becomes opaque pure black, everything else
        fully transparent. Output pixels are only (0,0,0,255) or
        (0,0,0,0)."""
        mask = Image.new("L", self.size_px, 0)
        for layer in self.layers:
            if not layer.visible or layer.role != "line":
                continue
            alpha = self._render_layer_full(layer).getchannel("A")
            mask = ImageChops.lighter(mask, alpha)
        mask = mask.point(lambda a: 255 if a > 0 else 0)
        out = Image.new("RGBA", self.size_px, (0, 0, 0, 0))
        out.putalpha(mask)
        return out

    # -- PSD export ------------------------------------------------------------
    def export_psd(self) -> bytes:
        from .psd import write_psd

        # PSD carries opacity in the layer record, so channel data is
        # rendered without opacity baked in (no double application).
        # Reference layers (S8) are omitted entirely: a PSD design
        # export carries the artwork, never the cover-up photo.
        rendered = [(layer.name, self._render_layer_full(layer, apply_opacity=False),
                     layer.opacity, layer.visible)
                    for layer in reversed(self.layers)
                    if layer.role != "reference"]  # PSD records are top-first
        return write_psd(self.render(), rendered)

    # -- persistence -------------------------------------------------------------
    def manifest(self) -> dict:
        return {
            "id": self.id,
            "version": FORMAT_VERSION,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "dpi": self.dpi,
            "lighting": self.lighting,
            "outline_layer": self.outline_layer,
            "layers": [layer.to_manifest() for layer in self.layers],
        }

    def to_entries(self) -> list[tuple[str, bytes]]:
        """The document as ordered (arcname, bytes) entries — the single
        serialization every sink (directory, zip bundle) shares. The
        R1 revision rides as its own `revision.json` entry, NOT in
        the manifest: content hashes (manifest + pixels) keep
        measuring the artwork alone, while the counter still
        round-trips every save/load."""
        entries: list[tuple[str, bytes]] = [
            ("manifest.json", json.dumps(self.manifest(), indent=2).encode("utf-8"))
        ]
        for layer in self.layers:
            buf = io.BytesIO()
            layer.image.save(buf, "PNG")
            entries.append((f"layers/{layer.filename}", buf.getvalue()))
        entries.append(("revision.json",
                        json.dumps({"revision": self.revision}).encode("utf-8")))
        return entries

    def save_bundle(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for arcname, data in self.to_entries():
                zf.writestr(arcname, data)
        return buf.getvalue()

    def save(self, path: str) -> None:
        """Save as a document directory: manifest.json + layers/ +
        revision.json. Every file lands atomically (R1: temp +
        rename via storage.atomic_write_bytes), so an interrupted
        save never leaves a torn file at a final path."""
        for arcname, data in self.to_entries():
            atomic_write_bytes(os.path.join(path, arcname), data)

    @classmethod
    def from_entries(cls, entries: dict[str, bytes]) -> "DesignDoc":
        manifest = json.loads(entries["manifest.json"].decode("utf-8"))
        if manifest.get("version") != FORMAT_VERSION:
            raise ValueError(f"unsupported document version: {manifest.get('version')!r}")
        doc = cls(manifest["id"], manifest["width_mm"], manifest["height_mm"], manifest["dpi"])
        # .get for back-compat: bundles written before S6 carry no
        # lighting / outline_layer keys and load with both None.
        doc.lighting = manifest.get("lighting")
        doc.outline_layer = manifest.get("outline_layer")
        for entry in manifest["layers"]:
            data = entries[f"layers/{entry['file']}"]
            image = Image.open(io.BytesIO(data))
            image.load()
            layer = Layer(
                entry["id"], entry["name"], entry["kind"], image,
                x=entry["x"], y=entry["y"], scale=entry["scale"],
                rotation=entry["rotation"], opacity=entry["opacity"],
                blend=entry["blend"], visible=entry["visible"],
                tint=tuple(entry["tint"]) if entry["tint"] is not None else None,
                role=entry["role"], provenance=entry.get("provenance"),
                # .get for back-compat: bundles written before S5
                # carry no "locked" key and load as unlocked.
                locked=bool(entry.get("locked", False)),
            )
            doc.layers.append(layer)
            doc._counter = max(doc._counter, int(entry["id"][1:]) if entry["id"][1:].isdigit() else doc._counter)
        # R1: the revision entry, when present (bundles written
        # before R1 carry none and load at revision 0).
        raw_revision = entries.get("revision.json")
        if raw_revision is not None:
            doc.revision = int(json.loads(raw_revision.decode("utf-8"))["revision"])
        return doc

    @classmethod
    def load_bundle(cls, bundle: bytes) -> "DesignDoc":
        with zipfile.ZipFile(io.BytesIO(bundle), "r") as zf:
            entries = {name: zf.read(name) for name in zf.namelist()}
        return cls.from_entries(entries)

    @classmethod
    def load(cls, path: str) -> "DesignDoc":
        entries: dict[str, bytes] = {}
        with open(os.path.join(path, "manifest.json"), "rb") as f:
            entries["manifest.json"] = f.read()
        manifest = json.loads(entries["manifest.json"].decode("utf-8"))
        for entry in manifest["layers"]:
            with open(os.path.join(path, "layers", entry["file"]), "rb") as f:
                entries[f"layers/{entry['file']}"] = f.read()
        revision_path = os.path.join(path, "revision.json")
        if os.path.exists(revision_path):
            with open(revision_path, "rb") as f:
                entries["revision.json"] = f.read()
        return cls.from_entries(entries)


def _blend(base: Image.Image, over: Image.Image, mode: str) -> Image.Image:
    """Composite `over` onto `base` honouring the PSD-safe blend subset.

    'normal' is plain alpha compositing. The other modes blend the RGB
    of fully/partially covered pixels with the standard formulas, then
    alpha-composite by the over-layer's alpha."""
    if mode == "normal":
        base.alpha_composite(over)
        return base
    br, bg, bb, ba = base.split()
    orr, og, ob, oa = over.split()
    if mode == "multiply":
        blended = [Image.frombytes("L", base.size, bytes(
            (x * y) // 255 for x, y in zip(a.tobytes(), b.tobytes())))
            for a, b in ((br, orr), (bg, og), (bb, ob))]
    elif mode == "screen":
        blended = [Image.frombytes("L", base.size, bytes(
            255 - ((255 - x) * (255 - y)) // 255 for x, y in zip(a.tobytes(), b.tobytes())))
            for a, b in ((br, orr), (bg, og), (bb, ob))]
    elif mode == "overlay":
        blended = [Image.frombytes("L", base.size, bytes(
            (2 * x * y) // 255 if x < 128 else 255 - (2 * (255 - x) * (255 - y)) // 255
            for x, y in zip(a.tobytes(), b.tobytes())))
            for a, b in ((br, orr), (bg, og), (bb, ob))]
    else:  # pragma: no cover - guarded by Layer validation
        raise ValueError(mode)
    merged = Image.merge("RGBA", (*blended, oa))
    base.alpha_composite(merged)
    return base
