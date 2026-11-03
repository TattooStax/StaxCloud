#!/usr/bin/env python3
"""Designer sidecar — the deterministic half of the OpenFang adapter.

WHY THIS FILE EXISTS (host truth, proven on the live instance and
recorded in the fork's LOOP.md R7/R12 entries):

- OpenFang agents CANNOT enumerate the kv store. `memory_recall`
  fetches ONE exact key; `memory_list`, `memory_delete` and
  `memory_update` DO NOT EXIST in the runtime tool catalog (they
  are display labels only). So an agent can never "find" records
  or run package code itself.
- Agent-side shell is not a transport: `shell_exec` forbids ALL
  metacharacters and defaults to requiring approval, so no
  curl/HTTP recipe an agent could run is viable. The Forms hand
  says it plainly: "you have no shell and need none."
- Fang approvals are a LIVE-ACTION GATE, not a queue: they expire
  (policy timeout, hard max 300s). The durable hold is a kv
  `draft/<uuid>` record; the module sync (pull-sync.sh) carries
  held drafts into Needs-you, re-carries them when an approval
  expires unactioned, and treats the kv record's `decided` status
  as TERMINAL — the ledger of record.

So the pattern — the same one pull-sync and the modem bridge
implement — is: a deterministic sidecar beside the daemon does
all enumeration, HTTP, and code execution; agents work only with
exact keys the sidecar (or a deterministic key rule) names.

THIS SIDECAR, per cycle (run it on the same 5-minute flock cron
as pull-sync, beside the daemon):

1. JOBS — the Designer agent queues work by storing a job record
   at `designjob/<job_id>` and appending the id to the fixed
   index key `designjob/index` (the `attention/sms` pattern: one
   fixed key names everything pending). This sidecar reads ONLY
   that index to discover jobs — a job record that is not in the
   index is never executed, and an index entry with no record
   behind it is reported, never invented around. Each job is
   executed against the package core (`studio_design`) if its op
   is on the allowlist below; the outcome (status + result or
   error) is written back onto the same `designjob/<job_id>`
   record, the exact key the agent recalls.
2. APPROVALS — mirrors pull-sync's drafts phase for designer
   drafts at `draft/design-<request_id>`: a held draft with no
   live approval is carried into Needs-you via the daemon's
   approvals API; an expired approval is re-carried; when the
   linked approval reads approved/rejected, the decision is
   written back onto the request (the package lifecycle
   transition runs here, in deterministic code) and the draft is
   closed `decided` — terminal, never re-carried, never
   re-applied, even if the approvals API later forgets it.

KV LAYOUT (values are JSON objects, stored whole, read back
whole — there is no partial update):

- `artist/<id>`        one artist profile (package record)
- `artist/index`       {"artists": [<id>, ...]}   (fixed key)
- `design/<id>`        one design document record: metadata +
                       `bundle_b64` (small docs) or `bundle_ref`
                       (file sidecar, see below)
- `design/index`       {"designs": [<id>, ...]}   (fixed key)
- `designreq/<id>`     one customer design request (package
                       lifecycle record, superset of
                       DesignRequest.to_dict())
- `designreq/index`    {"requests": [<id>, ...]}  (fixed key)
- `designrec/<id>`     one CUSTOMER-VISIBLE design record —
                       exists only after artist approval (Gate 2)
- `designrec/index`    {"designs": [<id>, ...]}   (fixed key)
- `designjob/<id>`     one job record {job_id, op, args, status,
                       result?, error?, refusal?, ts, finished?}
- `designjob/index`    {"jobs": [<id>, ...]}      (fixed key)
- `designver/<design_id>/<name>`  one DURABLE named snapshot of a
                       design (R1): {design_id, name, approved,
                       revision, ts} + the bundle (inline
                       `snapshot_b64` or a file sidecar
                       `snapshot_ref`, same size rule as designs)
- `designver/index`    {"versions": ["<design_id>/<name>", ...]}
- `designhist/<design_id>`  the design's undo/redo stacks
                       (OPS18): {design_id, undo: [...], redo:
                       [...], updated} — each entry one captured
                       document bundle (inline `bundle_b64` or a
                       file sidecar under designs/<id>/history/,
                       same size rule). Addressed by the design's
                       own id — auxiliary state of a known record,
                       not a discovery surface, so no index.
- `designmask/<design_id>/<name>`  one named edit mask (OPS18):
                       {design_id, name, size, size_bytes, ts} +
                       the mask PNG (inline `mask_b64` or a file
                       sidecar `mask_ref` under designs/<id>/
                       masks/, same size rule). The core resolves
                       a request's `mask_ref` only when a host
                       supplies the named masks; this store is how
                       this host holds them, durably.
- `designmask/index`   {"entries": ["<design_id>/<name>", ...]}
- `designedit/<request_id>`  one S7 edit request + its state:
                       {request: EditRequest record, status
                       (awaiting_result / applied / refused_stale /
                       refused_protected), outcome?}
- `designedit/index`   {"edits": [<request_id>, ...]}  (fixed key)
- `designcover/<coverup_id>`  one S8 cover-up session record
                       (CoverUpRecord verbatim — guarantee note
                       included) + session state
- `designcover/index`  {"coverups": [<coverup_id>, ...]} (fixed key)
- `designlib/<artist_id>/<element_id>`  one library element: the
                       core ElementLibrary record (owner stamped)
                       + its PNG bytes (inline `element_b64` or a
                       file sidecar `element_ref`, same size rule)
- `designlib/index`    {"entries": ["<artist_id>/<element_id>", ...]}
- `designlib/meta`     {"kit_counter": n} — the core kit counter,
                       persisted so kit ids never collide across
                       sidecar processes
- `designkit/<artist_id>/<kit_id>`  one stamp kit (core record)
- `designkit/index`    {"kits": ["<artist_id>/<kit_id>", ...]}
- `draft/design-<request_id>`  the durable approval hold

REVISIONS (R1): every `design/<id>` record carries `revision`,
the core document's mutation counter, rewritten from the loaded
doc after every mutating job. A mutating job (doc.op,
doc.set_structural_outline, doc.set_lighting, doc.snapshot_restore,
doc.undo, doc.redo, edit.apply, coverup.create, coverup.set_opacity,
library.reuse) MAY carry `base_revision` in its args — the
revision the caller computed against. When it is present and no
longer equals the record's revision, the job is REFUSED before
anything runs: the job record closes status "error" with a
structured `refusal` {reason: "stale_revision", base_revision,
current_revision} and the cycle report lists it under "refused".
A delayed result can never overwrite newer edits. Jobs without
base_revision are legacy/unguarded (the pre-R1 protocol) and run
as before.

UNDO/REDO (OPS18): sidecar cycles are fresh processes, so the
core's runtime history stacks would die with each cycle. They
are therefore persisted verbatim (the core's export_history /
import_history) at `designhist/<design_id>` on every design
re-store and re-imported on every load — undo/redo across
cycles restore the exact captured bundles, with the core's own
semantics (an undo is itself a mutation: it bumps the revision
and pushes the pre-undo state onto the redo stack).

FILE SIDECARS: a design bundle over BUNDLE_INLINE_MAX_BYTES is
NOT base64'd into kv (layered RGBA at print size is tens of MB;
kv is the wrong home). The bytes go to `<data dir>/designs/
<doc_id>.zip` and the record carries
`bundle_ref: "file:designs/<doc_id>.zip"`. Rendered exports
(preview / share / stencil PNGs) always live as files under
`designs/<doc_id>/` and are referenced from the design record.
The data dir is a box path (env DESIGNER_DATA_DIR, default
~/.openfang/designer-data) — it belongs to the install, not to
the agent.

PREFLIGHT (box-side, the installer's job — the agent cannot and
must not assume it): python3 with Pillow importable, the package
(`studio_design/`) placed beside this file's install home, and
the daemon reachable. `preflight()` below is that check; a cycle
that fails it does nothing and says why.

Transport note: pull-sync addresses kv through the agent's own
namespace (`/api/memory/agents/<agent_id>/kv/...`) — the same
store the agent's memory_store/memory_recall tools resolve to
(the drafts phase reads Forms-agent drafts through the forms
agent's namespace). This sidecar does the same with the designer
agent's id, found by name through GET /api/agents, exactly as
pull-sync finds the forms agent. The one exception is the
daemon-wide shared namespace id pull-sync uses for crew/health;
designer records are the designer's own, so no exception here.

No generative call lives here either: `doc.build` runs the
package pipeline on a synthetic stand-in element or on an
element image file a host leg produced. The model call stays in
the chat/host image path, as in every package slice. The S7
edit jobs follow the same rule: `edit.apply` takes a result
image a host leg produced (a file sidecar) and runs the core's
gates on it — the sidecar enforces, it never generates.
"""

from __future__ import annotations

import base64
import copy
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# The package core sits at the plug-in root (two levels up from
# adapters/openfang/). At install time the package is placed
# beside this file's home; the path insert covers the in-repo
# layout and is harmless when studio_design is already importable.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", ".."))

try:
    from PIL import Image, ImageDraw
    _PIL_ERROR = None
except Exception as exc:  # pragma: no cover - exercised by preflight test only on broken boxes
    Image = None
    ImageDraw = None
    _PIL_ERROR = exc

BUNDLE_INLINE_MAX_BYTES = 256 * 1024  # over this, bundles are file sidecars

ARTIST_INDEX = "artist/index"
DESIGN_INDEX = "design/index"
REQUEST_INDEX = "designreq/index"
DESIGNREC_INDEX = "designrec/index"
JOB_INDEX = "designjob/index"
VERSION_INDEX = "designver/index"
EDIT_INDEX = "designedit/index"
COVERUP_INDEX = "designcover/index"
MASK_INDEX = "designmask/index"
LIBRARY_INDEX = "designlib/index"
LIBRARY_META = "designlib/meta"
KIT_INDEX = "designkit/index"
DRAFT_PREFIX = "draft/design-"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def preflight() -> tuple[bool, str]:
    """Box preflight: Pillow importable + package importable.
    Returns (ok, message). The installer runs this on the box;
    a cycle refuses to start when it fails."""
    if _PIL_ERROR is not None:
        return False, (f"Pillow is not importable by this python3 "
                       f"({_PIL_ERROR}); install it on the box first "
                       f"(pip install 'Pillow>=9.0') — the Designer "
                       f"hand cannot run without it")
    try:
        import numpy  # noqa: F401 — the pipeline (matte/split,
        # contours) imports numpy + scipy lazily; a box without
        # them passes an import-only preflight and then fails
        # doc.build mid-job (found at live landing, 2026-11-02)
        from scipy import ndimage  # noqa: F401
    except Exception as exc:
        return False, (f"numpy/scipy is not importable by this "
                       f"python3 ({exc}); install them on the box "
                       f"first (pip install 'numpy>=1.26' "
                       f"'scipy>=1.11') — the design pipeline "
                       f"cannot run without them")
    try:
        import studio_design  # noqa: F401
    except Exception as exc:
        return False, f"studio_design package is not importable: {exc}"
    return True, "Pillow + numpy + scipy + studio_design importable"


# ---------------------------------------------------------------------
# Transports — the sidecar's only doors to the world.
# HttpKvTransport mirrors pull-sync.sh's drafts phase (urllib,
# Bearer token grepped from ~/.openfang/config.toml, kv addressed
# through the agent's own namespace). Tests substitute an
# in-memory transport with the same surface.
# ---------------------------------------------------------------------

class HttpKvTransport:
    def __init__(self, api_base: str | None = None,
                 config_path: str | None = None,
                 agent_name: str = "designer"):
        self.api = (api_base or os.environ.get("FANG_API")
                    or "http://127.0.0.1:4200").rstrip("/")
        self.config_path = (config_path
                            or os.path.expanduser("~/.openfang/config.toml"))
        self.agent_name = agent_name
        self._token: str | None = None
        self._agent_id: str | None = None

    # -- plumbing (pull-sync's shape) --------------------------------
    def _tok(self) -> str:
        if self._token is None:
            with open(self.config_path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("api_key "):
                        self._token = line.split('"')[1]
                        break
            if self._token is None:
                raise RuntimeError(f"no api_key in {self.config_path}")
        return self._token

    def _req(self, method: str, path: str, body=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.api + path, data=data, method=method)
        r.add_header("Authorization", "Bearer " + self._tok())
        if data:
            r.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(r, timeout=20) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}

    def agent_id(self) -> str:
        if self._agent_id is None:
            agents = self._req("GET", "/api/agents")
            found = next((a["id"] for a in agents
                          if a.get("name") == self.agent_name), None)
            if not found:
                raise RuntimeError(f"no agent named {self.agent_name!r} "
                                   f"on this daemon — is the hand installed?")
            self._agent_id = found
        return self._agent_id

    # -- kv surface ----------------------------------------------------
    def get(self, key: str):
        enc = urllib.parse.quote(key, safe="")
        try:
            d = self._req("GET",
                          f"/api/memory/agents/{self.agent_id()}/kv/{enc}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # live daemon: a missing key is a 404,
                # not {"value": null} (found at live landing,
                # 2026-11-02 — the in-memory simulation returns
                # None, so this branch is live-only by nature)
            raise
        return d.get("value") if isinstance(d, dict) else None

    def put(self, key: str, value) -> None:
        enc = urllib.parse.quote(key, safe="")
        self._req("PUT", f"/api/memory/agents/{self.agent_id()}/kv/{enc}",
                  {"value": value})

    def delete(self, key: str) -> None:
        # The daemon's kv DELETE route — the same one the landing
        # cleanups used (it answers {"status": "deleted"}). Only
        # the library delete op uses it: an artist deleting their
        # own element is the one true record removal in the
        # package. Agents have no delete tool; this door is the
        # deterministic sidecar's, like the approvals door.
        enc = urllib.parse.quote(key, safe="")
        self._req("DELETE",
                  f"/api/memory/agents/{self.agent_id()}/kv/{enc}")

    def list_pairs(self) -> list[tuple[str, object]]:
        d = self._req("GET", f"/api/memory/agents/{self.agent_id()}/kv")
        pairs = d.get("kv_pairs", []) if isinstance(d, dict) else []
        return [(p.get("key", ""), p.get("value")) for p in pairs]

    # -- approvals + wake (sidecar-only doors; agents have neither) ---
    def get_approvals(self) -> list[dict]:
        d = self._req("GET", "/api/approvals")
        return d if isinstance(d, list) else d.get("approvals", [])

    def post_approval(self, body: dict) -> dict:
        return self._req("POST", "/api/approvals", body)

    def wake(self, message: str) -> None:
        """Name exact keys to the agent — pull-sync's wake-poke."""
        self._req("POST", f"/api/agents/{self.agent_id()}/message",
                  {"message": message})


def _atomic_write(path: str, data: bytes) -> None:
    """Temp-file + fsync + rename in the same directory (R1): a
    crash leaves the old file or the new one, never a torn one.
    A local helper (mirroring studio_design.storage) — this
    sidecar deploys as a single file and its file store must not
    depend on package internals."""
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                               prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class FileSidecarStore:
    """Bytes that do not belong in kv: design bundles over the
    inline threshold and every rendered export."""

    def __init__(self, root: str | None = None):
        self.root = (root or os.environ.get("DESIGNER_DATA_DIR")
                     or os.path.expanduser("~/.openfang/designer-data"))

    def _path(self, ref: str) -> str:
        if not ref.startswith("file:"):
            raise ValueError(f"not a file ref: {ref!r}")
        rel = ref[len("file:"):]
        if rel.startswith("/") or ".." in rel.split("/"):
            raise ValueError(f"unsafe file ref: {ref!r}")
        return os.path.join(self.root, rel)

    def put_bytes(self, ref: str, data: bytes) -> str:
        path = self._path(ref)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _atomic_write(path, data)
        return ref

    def get_bytes(self, ref: str) -> bytes:
        with open(self._path(ref), "rb") as f:
            return f.read()

    def exists(self, ref: str) -> bool:
        return os.path.exists(self._path(ref))

    def remove(self, ref: str) -> None:
        try:
            os.unlink(self._path(ref))
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------
# Record helpers — indexes are fixed keys; a missing index means
# "no records", never a reason to guess keys.
# ---------------------------------------------------------------------

def _index_ids(transport, index_key: str, field: str) -> list[str]:
    rec = transport.get(index_key)
    if not isinstance(rec, dict):
        return []
    return [x for x in rec.get(field, []) if isinstance(x, str)]


def _index_add(transport, index_key: str, field: str, item: str) -> None:
    ids = _index_ids(transport, index_key, field)
    if item not in ids:
        ids.append(item)
        transport.put(index_key, {field: ids})


def _index_set(transport, index_key: str, field: str, ids: list[str]) -> None:
    transport.put(index_key, {field: list(ids)})


# ---------------------------------------------------------------------
# Package state, rebuilt from kv each time it is needed (the
# sidecar is stateless between cycles, like pull-sync).
# ---------------------------------------------------------------------

def _load_profiles(transport):
    from studio_design.profiles import ProfileStore
    store = ProfileStore()
    for artist_id in _index_ids(transport, ARTIST_INDEX, "artists"):
        rec = transport.get(f"artist/{artist_id}")
        if isinstance(rec, dict):
            store.add(rec)
    return store


def _save_profile(transport, profile: dict) -> None:
    transport.put(f"artist/{profile['artist_id']}", profile)
    _index_add(transport, ARTIST_INDEX, "artists", profile["artist_id"])


def _request_record(req) -> dict:
    """The stored designreq/<id> shape: DesignRequest.to_dict()
    plus the fields to_dict omits, so a rebuilt flow loses
    nothing (plans, the offer decision, a pending choice, the
    style anchor)."""
    rec = req.to_dict()
    rec.update({
        "offer": copy.deepcopy(req.offer),
        "pending_choice": copy.deepcopy(req.pending_choice),
        "plans": copy.deepcopy(req.plans),
        "style_anchor_prompt": req.style_anchor_prompt,
    })
    return rec


def _rebuild_request(rec: dict):
    from studio_design.customer import DesignRequest
    req = DesignRequest(rec["intake"])
    req.status = rec["status"]
    req.history = list(rec["history"])
    req.artist_id = rec.get("artist_id")
    req.routing = copy.deepcopy(rec.get("routing"))
    req.offer = copy.deepcopy(rec.get("offer"))
    req.pending_choice = copy.deepcopy(rec.get("pending_choice"))
    req.round = rec.get("round", 0)
    req.versions = copy.deepcopy(rec.get("versions", []))
    req.plans = copy.deepcopy(rec.get("plans", []))
    req.style_anchor_prompt = rec.get("style_anchor_prompt")
    req.feedback = list(rec.get("feedback", []))
    req.artist_alerted = bool(rec.get("artist_alerted", False))
    req.design_id = rec.get("design_id")
    req.stencil_ref = rec.get("stencil_ref")
    return req


def _load_flow(transport, store=None):
    from studio_design.customer import CustomerFlow
    if store is None:
        store = _load_profiles(transport)
    flow = CustomerFlow(store)
    for rid in _index_ids(transport, REQUEST_INDEX, "requests"):
        rec = transport.get(f"designreq/{rid}")
        if isinstance(rec, dict):
            req = _rebuild_request(rec)
            flow.requests[req.request_id] = req
    for did in _index_ids(transport, DESIGNREC_INDEX, "designs"):
        rec = transport.get(f"designrec/{did}")
        if isinstance(rec, dict):
            flow.designs.append(rec)
    return flow


def _save_request(transport, req) -> None:
    transport.put(f"designreq/{req.request_id}", _request_record(req))
    _index_add(transport, REQUEST_INDEX, "requests", req.request_id)


def _save_designs(transport, flow) -> None:
    """Persist the customer-visible design records (Gate 2: an
    entry is created by the core only at artist approval)."""
    for d in flow.designs:
        transport.put(f"designrec/{d['id']}", d)
    _index_set(transport, DESIGNREC_INDEX, "designs",
               [d["id"] for d in flow.designs])


# ---------------------------------------------------------------------
# Design documents — bundle storage with the size rule.
# ---------------------------------------------------------------------

def store_bundle(transport, files: FileSidecarStore, doc_id: str,
                 bundle: bytes) -> dict:
    """The storage half of a design record: inline base64 at or
    under BUNDLE_INLINE_MAX_BYTES, a file sidecar above it."""
    if len(bundle) <= BUNDLE_INLINE_MAX_BYTES:
        return {"bundle_b64": base64.b64encode(bundle).decode("ascii"),
                "size_bytes": len(bundle)}
    ref = f"file:designs/{doc_id}.zip"
    files.put_bytes(ref, bundle)
    return {"bundle_ref": ref, "size_bytes": len(bundle)}


def load_bundle(transport, files: FileSidecarStore, record: dict) -> bytes:
    if record.get("bundle_b64"):
        return base64.b64decode(record["bundle_b64"])
    if record.get("bundle_ref"):
        return files.get_bytes(record["bundle_ref"])
    raise ValueError(f"design record {record.get('id')!r} carries "
                     f"neither bundle_b64 nor bundle_ref")


def _save_design_record(transport, record: dict) -> None:
    transport.put(f"design/{record['id']}", record)
    _index_add(transport, DESIGN_INDEX, "designs", record["id"])


# Snapshot bundles follow the design-bundle size rule, under their
# own record fields so a snapshot record never reads as a design.
def store_snapshot_bundle(files: FileSidecarStore, design_id: str,
                          name: str, bundle: bytes) -> dict:
    if len(bundle) <= BUNDLE_INLINE_MAX_BYTES:
        return {"snapshot_b64": base64.b64encode(bundle).decode("ascii"),
                "size_bytes": len(bundle)}
    ref = f"file:designs/{design_id}/snapshots/{name}.zip"
    files.put_bytes(ref, bundle)
    return {"snapshot_ref": ref, "size_bytes": len(bundle)}


def load_snapshot_bundle(files: FileSidecarStore, record: dict) -> bytes:
    if record.get("snapshot_b64"):
        return base64.b64decode(record["snapshot_b64"])
    if record.get("snapshot_ref"):
        return files.get_bytes(record["snapshot_ref"])
    raise ValueError(f"snapshot record {record.get('name')!r} carries "
                     f"neither snapshot_b64 nor snapshot_ref")


# Library element PNGs follow the same size rule, under their own
# record fields (an element record never reads as a design).
def store_element_bytes(files: FileSidecarStore, artist_id: str,
                        element_id: str, data: bytes) -> dict:
    if len(data) <= BUNDLE_INLINE_MAX_BYTES:
        return {"element_b64": base64.b64encode(data).decode("ascii"),
                "size_bytes": len(data)}
    ref = f"file:library/{artist_id}/{element_id}.png"
    files.put_bytes(ref, data)
    return {"element_ref": ref, "size_bytes": len(data)}


def load_element_bytes(files: FileSidecarStore, record: dict) -> bytes:
    if record.get("element_b64"):
        return base64.b64decode(record["element_b64"])
    if record.get("element_ref"):
        return files.get_bytes(record["element_ref"])
    raise ValueError(f"library element {record.get('element_id')!r} "
                     f"carries neither element_b64 nor element_ref")


# Design history stacks (OPS18) follow the same size rule, one
# record per design at designhist/<design_id>. Entries are
# positional file refs (history/<stack>-<i>.zip); a re-store
# removes refs the new stacks no longer occupy, the same orphan
# sweep SnapshotStore.save_to performs on disk.
def _persist_history(ctx, design_id: str, doc) -> None:
    """Write the doc's undo/redo stacks (the core's export_history,
    verbatim bundles) to the design's durable history record."""
    transport = ctx["transport"]
    hist = doc.export_history()
    old = transport.get(f"designhist/{design_id}")
    old_refs = set()
    if isinstance(old, dict):
        for stack in ("undo", "redo"):
            for entry in old.get(stack, []):
                if isinstance(entry, dict) and entry.get("bundle_ref"):
                    old_refs.add(entry["bundle_ref"])
    new_refs = set()
    rec = {"design_id": design_id, "updated": _now()}
    for stack in ("undo", "redo"):
        entries = []
        for i, data in enumerate(hist[stack]):
            if len(data) <= BUNDLE_INLINE_MAX_BYTES:
                entries.append({
                    "bundle_b64": base64.b64encode(data).decode("ascii"),
                    "size_bytes": len(data)})
            else:
                ref = f"file:designs/{design_id}/history/{stack}-{i}.zip"
                ctx["files"].put_bytes(ref, data)
                new_refs.add(ref)
                entries.append({"bundle_ref": ref,
                                "size_bytes": len(data)})
        rec[stack] = entries
    transport.put(f"designhist/{design_id}", rec)
    for ref in old_refs - new_refs:
        ctx["files"].remove(ref)


def _load_history(ctx, doc) -> None:
    """Re-import a design's persisted undo/redo stacks into the
    loaded doc (a design with no history record has empty stacks —
    not an error)."""
    rec = ctx["transport"].get(f"designhist/{doc.id}")
    if not isinstance(rec, dict):
        return
    stacks = {}
    for stack in ("undo", "redo"):
        bundles = []
        for entry in rec.get(stack, []):
            if entry.get("bundle_b64"):
                bundles.append(base64.b64decode(entry["bundle_b64"]))
            elif entry.get("bundle_ref"):
                bundles.append(ctx["files"].get_bytes(entry["bundle_ref"]))
        stacks[stack] = bundles
    doc.import_history(stacks["undo"], stacks["redo"])


# Named-mask PNGs follow the same size rule, under their own
# record fields (a mask record never reads as a design).
def store_mask_bytes(files: FileSidecarStore, design_id: str,
                     name: str, data: bytes) -> dict:
    if len(data) <= BUNDLE_INLINE_MAX_BYTES:
        return {"mask_b64": base64.b64encode(data).decode("ascii"),
                "size_bytes": len(data)}
    ref = f"file:designs/{design_id}/masks/{name}.png"
    files.put_bytes(ref, data)
    return {"mask_ref": ref, "size_bytes": len(data)}


def load_mask_bytes(files: FileSidecarStore, record: dict) -> bytes:
    if record.get("mask_b64"):
        return base64.b64decode(record["mask_b64"])
    if record.get("mask_ref"):
        return files.get_bytes(record["mask_ref"])
    raise ValueError(f"mask record {record.get('name')!r} carries "
                     f"neither mask_b64 nor mask_ref")


def _require_fresh(args: dict, record: dict) -> None:
    """The R1 revision guard for mutating jobs: when the job's
    args carry base_revision and it no longer equals the design
    record's revision, raise StaleRevisionError BEFORE anything
    runs — the caller has been working from an older state."""
    from studio_design.document import StaleRevisionError
    base = (args or {}).get("base_revision")
    if base is None:
        return
    current = int(record.get("revision", 0))
    if int(base) != current:
        raise StaleRevisionError(record.get("id", "?"), int(base), current)


def _restash_design(ctx, record: dict, doc) -> None:
    """Re-store a mutated doc under its record: bundle (size rule),
    the R1 revision read back off the doc, the timestamp — and the
    OPS18 history stacks, so the undo/redo state a mutating op
    produced survives this process."""
    record.pop("bundle_b64", None)
    record.pop("bundle_ref", None)
    record.update(store_bundle(ctx["transport"], ctx["files"],
                               record["id"], doc.save_bundle()))
    record["revision"] = doc.revision
    record["updated"] = _now()
    _save_design_record(ctx["transport"], record)
    _persist_history(ctx, record["id"], doc)


def _synthetic_element(width: int, height: int, variant: int = 0) -> Image.Image:
    """A deterministic stand-in for a generation, in the shape the
    chat image path hands over: motif on plain white — black
    linework over a grey wash (the acceptance suite's synthetic).
    Labelled synthetic in provenance wherever it is used; it is
    pipeline fodder, never presented as model output."""
    img = Image.new("RGB", (width, height), (255, 255, 255))
    d = ImageDraw.Draw(img)
    cx, cy = width // 2, height // 2
    r = max(10, min(width, height) // 4)
    wash = (170, 170, 170)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=wash)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(0, 0, 0), width=6)
    petals = 3 + (variant % 3)
    for i in range(petals):
        px = cx - r + (2 * r * i) // max(petals - 1, 1) if petals > 1 else cx
        d.ellipse((px - r // 3, cy - r // 3, px + r // 3, cy + r // 3),
                  outline=(0, 0, 0), width=4)
    d.line([(cx, cy + r), (cx, height - 5)], fill=(0, 0, 0), width=6)
    d.line([(cx - r // 2, 5), (cx + r // 2, 5)], fill=(0, 0, 0), width=6)
    return img


# ---------------------------------------------------------------------
# Job operations — THE ALLOWLIST. A job whose op is not here is
# refused with the allowlist named; the sidecar runs nothing else.
# ---------------------------------------------------------------------

def _ctx(transport, files):
    return {"transport": transport, "files": files,
            "store": None, "flow": None, "library": None}


def _store(ctx):
    if ctx["store"] is None:
        ctx["store"] = _load_profiles(ctx["transport"])
    return ctx["store"]


def _flow(ctx):
    if ctx["flow"] is None:
        ctx["flow"] = _load_flow(ctx["transport"], _store(ctx))
    return ctx["flow"]


def _op_profile_seed(ctx, args):
    from studio_design.profiles import seed_fargo_tattoo
    seeded, kept = [], []
    existing = set(_index_ids(ctx["transport"], ARTIST_INDEX, "artists"))
    for profile in seed_fargo_tattoo().agent_view():
        if profile["artist_id"] in existing:
            kept.append(profile["artist_id"])  # never clobber owner edits
        else:
            _save_profile(ctx["transport"], profile)
            seeded.append(profile["artist_id"])
    ctx["store"] = None
    return {"seeded": seeded, "already_present": kept}


def _op_profile_get(ctx, args):
    return {"profile": _store(ctx).get(args["artist_id"])}


def _op_profile_update(ctx, args):
    store = _store(ctx)
    profile = store.get(args["artist_id"])  # KeyError if unknown — honest
    patch = args.get("patch", {})
    allowed = {"display_name", "styles", "specialties", "style_note",
               "approved_library", "allow_customer_designs",
               "versions_per_request"}
    unknown = set(patch) - allowed
    if unknown:
        raise ValueError(f"profile patch fields not allowed: {sorted(unknown)}")
    merged = dict(profile)
    merged.update(patch)
    saved = store.add(merged)  # core re-validates (versions >= 1 etc.)
    _save_profile(ctx["transport"], saved)
    return {"profile": saved}


def _op_route_request(ctx, args):
    from studio_design.generate import route_request
    return {"routing": route_request(args["text"], _store(ctx))}


def _op_plan_versions(ctx, args):
    from studio_design.generate import plan_versions
    request = args.get("request") or {"text": args["text"]}
    return plan_versions(request, _store(ctx),
                         count=args.get("count"))


def _op_request_intake(ctx, args):
    flow = _flow(ctx)
    req = flow.intake(args["channel"], args["customer_id"],
                      args["prompt_text"], placement=args.get("placement"),
                      size_mm=args.get("size_mm"),
                      reference_ref=args.get("reference_ref"),
                      ts=args.get("ts"), request_id=args.get("request_id"))
    _save_request(ctx["transport"], req)
    return {"request": _request_record(req)}


def _op_request_evaluate(ctx, args):
    return {"offer": _flow(ctx).evaluate(args["request_id"])}


def _op_request_route(ctx, args):
    flow = _flow(ctx)
    result = flow.route(args["request_id"],
                        chosen_artist_id=args.get("chosen_artist_id"))
    _save_request(ctx["transport"], flow.get(args["request_id"]))
    return result


def _op_request_plan(ctx, args):
    flow = _flow(ctx)
    versions = flow.plan(args["request_id"])
    _save_request(ctx["transport"], flow.get(args["request_id"]))
    return {"versions": versions}


def _op_request_submit(ctx, args):
    """planned -> awaiting_artist AND the durable approval hold:
    draft/design-<request_id>, the record the approvals phase
    carries into Needs-you (pull-sync's draft pattern)."""
    flow = _flow(ctx)
    req = flow.get(args["request_id"])
    flow.submit_to_artist(req.request_id)
    _save_request(ctx["transport"], req)
    draft_key = f"{DRAFT_PREFIX}{req.request_id}"
    if not isinstance(ctx["transport"].get(draft_key), dict):
        ctx["transport"].put(draft_key, {
            "kind": "design_approval",
            "request_id": req.request_id,
            "artist_id": req.artist_id,
            "customer_id": req.customer_id,
            "text": (f"Design for {req.artist_id}: "
                     f"{req.prompt_text} — round {req.round}, "
                     f"{len(req.versions)} version(s) planned. "
                     f"Approve to make it customer-visible."),
            "status": "held",
        })
    return {"request_id": req.request_id, "status": req.status,
            "draft_key": draft_key}


def _op_request_artist_approve(ctx, args):
    flow = _flow(ctx)
    record = flow.artist_approve(args["request_id"])
    _save_request(ctx["transport"], flow.get(args["request_id"]))
    _save_designs(ctx["transport"], flow)
    return {"design": record}


def _op_request_artist_reject(ctx, args):
    flow = _flow(ctx)
    flow.artist_reject(args["request_id"])
    _save_request(ctx["transport"], flow.get(args["request_id"]))
    return {"request_id": args["request_id"], "status": "artist_rejected"}


def _op_request_alert_artist(ctx, args):
    flow = _flow(ctx)
    flow.alert_artist(args["request_id"])
    _save_request(ctx["transport"], flow.get(args["request_id"]))
    return {"request_id": args["request_id"], "artist_alerted": True}


def _op_request_send(ctx, args):
    """The core refuses an unframed price promise (PermissionError)
    or an unalerted estimate before anything advances — the job
    surfaces that refusal as the job's error, verbatim."""
    flow = _flow(ctx)
    flow.send_to_customer(args["request_id"], text=args.get("text"))
    _save_request(ctx["transport"], flow.get(args["request_id"]))
    return {"request_id": args["request_id"], "status": "sent_to_customer"}


def _op_request_revision(ctx, args):
    flow = _flow(ctx)
    versions = flow.request_revision(args["request_id"], args["feedback"])
    _save_request(ctx["transport"], flow.get(args["request_id"]))
    return {"versions": versions}


def _op_request_customer_approve(ctx, args):
    flow = _flow(ctx)
    flow.customer_approve(args["request_id"])
    _save_request(ctx["transport"], flow.get(args["request_id"]))
    return {"request_id": args["request_id"], "status": "customer_approved"}


def _op_request_stencil_ready(ctx, args):
    flow = _flow(ctx)
    req = flow.get(args["request_id"])
    record = flow.mark_stencil_ready(req.request_id)
    _save_request(ctx["transport"], req)
    _save_designs(ctx["transport"], flow)
    _save_profile(ctx["transport"], flow.store.get(req.artist_id))
    return {"design": record}


def _op_doc_build(ctx, args):
    """Create a design doc through the package pipeline and store
    it. Element sources: {"kind": "synthetic", "variant": n}
    (deterministic stand-in) or {"kind": "file", "ref":
    "file:elements/<name>.png"} (an image a host leg produced).
    Pipeline: matte -> line/shading split -> doc with line +
    shading layers, provenance naming the source honestly."""
    from studio_design.document import DesignDoc
    from studio_design.generate import (matte_to_transparent,
                                        split_line_shading)
    doc_id = args["doc_id"]
    if isinstance(ctx["transport"].get(f"design/{doc_id}"), dict):
        raise ValueError(f"design {doc_id!r} already exists — "
                         f"build is create-once; use doc.op to change it")
    element = args["element"]
    if element.get("kind") == "synthetic":
        raw = _synthetic_element(args.get("element_px", 480),
                                 args.get("element_px", 480),
                                 int(element.get("variant", 0)))
        source = "synthetic stand-in (no model call)"
    elif element.get("kind") == "file":
        from io import BytesIO
        raw = Image.open(BytesIO(ctx["files"].get_bytes(element["ref"])))
        raw = raw.convert("RGB")
        source = element["ref"]
    else:
        raise ValueError(f"element.kind must be 'synthetic' or 'file', "
                         f"got {element.get('kind')!r}")
    matted = matte_to_transparent(raw)
    line, shading = split_line_shading(matted)
    doc = DesignDoc.create(doc_id, float(args["width_mm"]),
                           float(args["height_mm"]))
    prov = {"source": source, "via": "designer_sidecar doc.build"}
    line_id = doc.add_raster("line", line, role="line", provenance=prov)
    shading_id = doc.add_raster("shading", shading, role="shading",
                                provenance=prov)
    record = {"id": doc_id, "artist_id": args.get("artist_id"),
              "title": args.get("title", doc_id),
              "layers": [{"id": line_id, "name": "line", "role": "line"},
                         {"id": shading_id, "name": "shading",
                          "role": "shading"}],
              "revision": doc.revision,
              "updated": _now()}
    record.update(store_bundle(ctx["transport"], ctx["files"],
                               doc_id, doc.save_bundle()))
    _save_design_record(ctx["transport"], record)
    return {"design": {k: record[k] for k in
                       ("id", "artist_id", "title", "size_bytes",
                        "revision")},
            "storage": "bundle_ref" if "bundle_ref" in record
                       else "bundle_b64"}


def _load_doc(ctx, design_id: str):
    from studio_design.document import DesignDoc
    record = ctx["transport"].get(f"design/{design_id}")
    if not isinstance(record, dict):
        raise KeyError(f"no design record at design/{design_id}")
    doc = DesignDoc.load_bundle(
        load_bundle(ctx["transport"], ctx["files"], record))
    # The record is the host-side ledger: when it carries a
    # revision it wins over the bundle's own entry (they are
    # written together by _restash_design; the record is what
    # _require_fresh checks against, so the doc must agree).
    if isinstance(record.get("revision"), int):
        doc.revision = record["revision"]
    # OPS18: the persisted undo/redo stacks ride along with every
    # load, so a doc.undo job in THIS fresh process sees the
    # history earlier cycles produced.
    _load_history(ctx, doc)
    return record, doc


def _op_doc_validate(ctx, args):
    from studio_design.validate import validate_document
    record, doc = _load_doc(ctx, args["design_id"])
    errors = validate_document(doc)
    return {"design_id": args["design_id"], "valid": not errors,
            "errors": errors}


def _op_doc_export(ctx, args):
    """Render exports to the file sidecar and reference them from
    the design record: preview (on white), share (exactly the
    visible canvas), stencil (line layer only)."""
    record, doc = _load_doc(ctx, args["design_id"])
    kinds = args.get("kinds", ["preview", "share", "stencil"])
    renderers = {"preview": doc.render_preview,
                 "share": doc.share_canvas,
                 "stencil": doc.export_stencil}
    exports = dict(record.get("exports", {}))
    written = {}
    from io import BytesIO
    for kind in kinds:
        if kind not in renderers:
            raise ValueError(f"export kind {kind!r} not in "
                             f"{sorted(renderers)}")
        buf = BytesIO()
        renderers[kind]().save(buf, format="PNG")
        ref = f"file:designs/{args['design_id']}/{kind}.png"
        ctx["files"].put_bytes(ref, buf.getvalue())
        exports[kind] = ref
        written[kind] = ref
    record["exports"] = exports
    record["updated"] = _now()
    _save_design_record(ctx["transport"], record)
    result = {"design_id": args["design_id"], "exports": written}
    if "stencil" in written:
        # The stencil's record carries the outline's provenance +
        # review state (RESULTS19): a stencil built on an
        # unreviewed threshold split says so in its record.
        from studio_design.outline import stencil_export_record
        result["stencil_record"] = stencil_export_record(doc)
    return result


_DOC_OPS = ("transform", "reorder", "set_opacity", "set_visible",
            "remove", "lock", "unlock")


def _op_doc_op(ctx, args):
    """One deterministic layer op against a stored doc (the chat
    ops of the playbook, executed here — never by regenerating).
    The changed doc is re-stored under the same size rule, its
    record revision advanced. A stale base_revision in the job
    args refuses the op before anything runs (R1)."""
    record, doc = _load_doc(ctx, args["design_id"])
    _require_fresh(args, record)
    op = args["op"]
    if op not in _DOC_OPS:
        raise ValueError(f"doc.op {op!r} not in {list(_DOC_OPS)}")
    a = args.get("args", {})
    if op == "transform":
        doc.transform(args["layer_id"], x=a.get("x"), y=a.get("y"),
                      dx=int(a.get("dx", 0)), dy=int(a.get("dy", 0)),
                      scale=a.get("scale"), rotation=a.get("rotation"))
    elif op == "reorder":
        doc.reorder(args["layer_id"], int(a["new_index"]))
    elif op == "set_opacity":
        doc.set_opacity(args["layer_id"], float(a["opacity"]))
    elif op == "set_visible":
        doc.set_visible(args["layer_id"], bool(a["visible"]))
    elif op == "remove":
        doc.remove(args["layer_id"])
    elif op == "lock":
        doc.lock_layer(args["layer_id"])
    elif op == "unlock":
        doc.unlock_layer(args["layer_id"])
    _restash_design(ctx, record, doc)
    return {"design_id": args["design_id"], "op": op,
            "revision": doc.revision,
            "layers": [l.id for l in doc.layers]}


def _op_doc_get(ctx, args):
    record = ctx["transport"].get(f"design/{args['design_id']}")
    if not isinstance(record, dict):
        raise KeyError(f"no design record at design/{args['design_id']}")
    return {"design": {k: v for k, v in record.items()
                       if k != "bundle_b64"}}


# ---------------------------------------------------------------------
# R1 ops — outline-first + lighting wired as jobs, and durable
# named snapshots as kv records (designver/<design_id>/<name>).
# ---------------------------------------------------------------------

def _op_doc_set_structural_outline(ctx, args):
    """Mark a line layer as the document's structural outline
    (the core op locks it). Mutating: revision-guarded, the
    record's revision advances with the doc's. Outline
    provenance (RESULTS19): the job may name how the outline was
    produced — source (threshold_split / candidate_step /
    artist_supplied) plus the candidate step's production
    report; the default stays the bare op's artist_supplied."""
    from studio_design.outline import set_structural_outline
    record, doc = _load_doc(ctx, args["design_id"])
    _require_fresh(args, record)
    set_structural_outline(doc, args["layer_id"],
                           source=args.get("source", "artist_supplied"),
                           production=args.get("production"))
    _restash_design(ctx, record, doc)
    return {"design_id": args["design_id"],
            "outline_layer": doc.outline_layer,
            "outline_provenance": doc.outline_provenance,
            "revision": doc.revision}


def _op_doc_outline_accept(ctx, args):
    """The artist's review transition for the structural outline
    (RESULTS19): unreviewed -> artist_reviewed, recorded with
    who/when on the design's outline provenance. Mutating:
    revision-guarded like every design-mutating job — a stale
    base_revision refuses before the core op runs. The acceptor
    defaults to the design's owning artist when the job does not
    name one."""
    record, doc = _load_doc(ctx, args["design_id"])
    _require_fresh(args, record)
    accepted_by = args.get("accepted_by") or record.get("artist_id")
    if not accepted_by:
        raise ValueError("doc.outline_accept needs accepted_by "
                         "(or a design record carrying artist_id)")
    provenance = doc.accept_outline(str(accepted_by), at=args.get("at"))
    _restash_design(ctx, record, doc)
    return {"design_id": args["design_id"],
            "outline_layer": doc.outline_layer,
            "outline_provenance": provenance,
            "revision": doc.revision}


def _op_doc_shading_plan(ctx, args):
    """Plan shading against the doc. Read-only, but GATED by the
    core: with a structural outline set, a plan that does not
    reference it is refused (the error lands on the job record)."""
    from studio_design.outline import shading_plan
    record, doc = _load_doc(ctx, args["design_id"])
    return shading_plan(doc, targets=args.get("targets"),
                        outline_ref=args.get("outline_ref"))


def _op_doc_measure_contours(ctx, args):
    """The closed-contour REPORT for one layer (the outline layer
    by default). A report, never a stencil verdict (S6)."""
    from io import BytesIO
    from studio_design.outline import measure_contours
    record, doc = _load_doc(ctx, args["design_id"])
    layer_id = args.get("layer_id") or doc.outline_layer
    if not layer_id:
        raise ValueError("measure_contours needs a layer_id — the "
                         "document has no structural outline to "
                         "default to")
    img = Image.open(BytesIO(doc.share_layer(layer_id)))
    img.load()
    return {"design_id": args["design_id"], "layer_id": layer_id,
            "report": measure_contours(img)}


def _op_doc_set_lighting(ctx, args):
    """Set the document's lighting from a preset key (plus
    overrides), a full spec dict, or clear=true. Mutating:
    revision-guarded; the spec lives in the manifest and the
    prompt path reads it from there."""
    from studio_design.lighting import set_lighting, spec_from_preset
    record, doc = _load_doc(ctx, args["design_id"])
    _require_fresh(args, record)
    if args.get("clear"):
        spec = None
    elif args.get("preset"):
        spec = spec_from_preset(args["preset"],
                                **(args.get("overrides") or {}))
    elif "spec" in args:
        spec = args["spec"]
    else:
        raise ValueError("doc.set_lighting needs a preset, a spec, "
                         "or clear=true")
    set_lighting(doc, spec)
    _restash_design(ctx, record, doc)
    return {"design_id": args["design_id"], "lighting": doc.lighting,
            "revision": doc.revision}


_SNAPSHOT_NAME_OK = None  # compiled on first use


def _check_snapshot_name(name) -> str:
    global _SNAPSHOT_NAME_OK
    import re
    if _SNAPSHOT_NAME_OK is None:
        _SNAPSHOT_NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    if not isinstance(name, str) or not _SNAPSHOT_NAME_OK.match(name):
        raise ValueError(
            f"snapshot name {name!r} must be a simple name "
            f"(letters, digits, '.', '_' or '-', no path separators) — "
            f"it becomes a kv key segment and a file name")
    return name


def _op_doc_snapshot_put(ctx, args):
    """Persist a NAMED snapshot of the current doc as a durable
    designver record (R1): the bundle bytes, the approved flag,
    and the revision they were taken at. Capturing state does not
    mutate the doc, so no revision guard applies."""
    record, doc = _load_doc(ctx, args["design_id"])
    name = _check_snapshot_name(args["name"])
    snap = {"design_id": args["design_id"], "name": name,
            "approved": bool(args.get("approved", False)),
            "revision": doc.revision, "ts": _now()}
    snap.update(store_snapshot_bundle(ctx["files"], args["design_id"],
                                      name, doc.save_bundle()))
    ctx["transport"].put(f"designver/{args['design_id']}/{name}", snap)
    _index_add(ctx["transport"], VERSION_INDEX, "versions",
               f"{args['design_id']}/{name}")
    return {"design_id": args["design_id"], "name": name,
            "approved": snap["approved"], "revision": doc.revision,
            "size_bytes": snap["size_bytes"],
            "storage": "snapshot_ref" if "snapshot_ref" in snap
                       else "snapshot_b64"}


def _op_doc_snapshot_restore(ctx, args):
    """Restore a design to a persisted named snapshot, through
    the core's own restore op (history push + ops log + revision
    bump). MUTATING: a stale base_revision refuses it — restoring
    over newer edits is exactly what the guard exists for."""
    record, doc = _load_doc(ctx, args["design_id"])
    _require_fresh(args, record)
    name = _check_snapshot_name(args["name"])
    snap = ctx["transport"].get(f"designver/{args['design_id']}/{name}")
    if not isinstance(snap, dict):
        raise KeyError(f"no snapshot at designver/"
                       f"{args['design_id']}/{name}")
    bundle = load_snapshot_bundle(ctx["files"], snap)
    doc.snapshots.put(name, bundle, approved=bool(snap.get("approved")))
    doc.restore_snapshot(name)
    _restash_design(ctx, record, doc)
    return {"design_id": args["design_id"], "restored_from": name,
            "snapshot_revision": snap.get("revision"),
            "revision": doc.revision}


def _op_doc_snapshot_list(ctx, args):
    """Snapshot metadata for one design, read from the fixed
    version index (never by guessing keys)."""
    out = []
    for entry in _index_ids(ctx["transport"], VERSION_INDEX, "versions"):
        design_id, _, name = entry.partition("/")
        if design_id != args["design_id"]:
            continue
        rec = ctx["transport"].get(f"designver/{entry}")
        if isinstance(rec, dict):
            out.append({"name": name,
                        "approved": bool(rec.get("approved")),
                        "revision": rec.get("revision"),
                        "size_bytes": rec.get("size_bytes"),
                        "ts": rec.get("ts")})
    return {"design_id": args["design_id"], "snapshots": out}


def _op_doc_undo(ctx, args):
    """Undo the design's most recent mutation — across sidecar
    cycles: the stacks were persisted at designhist/<design_id>
    by every re-store and re-imported by _load_doc, so this fresh
    process undoes work an earlier cycle did. The core's own
    undo runs (state swap + redo push + revision bump): undoing
    is a mutation, so the job is revision-guarded like the rest.
    Nothing to undo is a clean no-op (undone=false), not an
    error."""
    record, doc = _load_doc(ctx, args["design_id"])
    _require_fresh(args, record)
    done = doc.undo()
    if done:
        _restash_design(ctx, record, doc)
    hist = doc.export_history()
    return {"design_id": args["design_id"], "undone": done,
            "revision": doc.revision,
            "undo_depth": len(hist["undo"]),
            "redo_depth": len(hist["redo"])}


def _op_doc_redo(ctx, args):
    """Redo the most recently undone mutation (same durable
    stacks as doc.undo). An empty redo branch — including after
    any new mutation, which clears it — is a clean no-op."""
    record, doc = _load_doc(ctx, args["design_id"])
    _require_fresh(args, record)
    done = doc.redo()
    if done:
        _restash_design(ctx, record, doc)
    hist = doc.export_history()
    return {"design_id": args["design_id"], "redone": done,
            "revision": doc.revision,
            "undo_depth": len(hist["undo"]),
            "redo_depth": len(hist["redo"])}


def _op_doc_snapshot_delete(ctx, args):
    """Delete one durable named snapshot (the R1 leftover): the
    designver record and any file-sidecar bundle, via the kv
    DELETE route the library delete proved. Deleting an APPROVED
    snapshot — an artist's signed-off version — is a deliberate
    act in the spirit of the core's never-auto-evict rule: the
    job must carry confirm_approved=true, and the result names
    that the deleted version was approved. The design itself is
    not touched (no revision change)."""
    transport = ctx["transport"]
    design_id = args["design_id"]
    name = _check_snapshot_name(args["name"])
    key = f"designver/{design_id}/{name}"
    snap = transport.get(key)
    if not isinstance(snap, dict):
        raise KeyError(f"no snapshot at {key}")
    was_approved = bool(snap.get("approved"))
    if was_approved and not args.get("confirm_approved"):
        raise ValueError(
            f"snapshot {name!r} of design {design_id!r} is an "
            f"APPROVED version — deleting it is a deliberate act; "
            f"pass confirm_approved=true to proceed (nothing was "
            f"deleted)")
    if snap.get("snapshot_ref"):
        ctx["files"].remove(snap["snapshot_ref"])
    transport.delete(key)
    remaining = [e for e in _index_ids(transport, VERSION_INDEX,
                                       "versions")
                 if e != f"{design_id}/{name}"]
    _index_set(transport, VERSION_INDEX, "versions", remaining)
    return {"design_id": design_id, "name": name, "deleted": True,
            "was_approved": was_approved,
            "confirm_approved": bool(args.get("confirm_approved"))}


# ---------------------------------------------------------------------
# Named masks (OPS18) — the core resolves a request's mask_ref
# only when a host supplies masks under those names; the doc
# itself stores none. This host holds them durably, one record
# per (design, name) at designmask/<design_id>/<name>, so an
# edit's target/protected entries may name them across cycles.
# A mask only ever CONSTRAINS an area (the core intersects);
# storing one never widens what an edit may touch.
# ---------------------------------------------------------------------

_MASK_NAME_OK = None  # compiled on first use


def _check_mask_name(name) -> str:
    global _MASK_NAME_OK
    import re
    if _MASK_NAME_OK is None:
        _MASK_NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    if not isinstance(name, str) or not _MASK_NAME_OK.match(name):
        raise ValueError(
            f"mask name {name!r} must be a simple name "
            f"(letters, digits, '.', '_' or '-', no path separators) — "
            f"it becomes a kv key segment and a file name")
    return name


def _op_mask_put(ctx, args):
    """Store a named mask for a design from a supplied mask image
    (a file sidecar a host leg placed — the sidecar draws no
    masks of its own). The image must be exactly canvas size:
    the core refuses a mismatched mask at mask-build time, and
    failing here, at store time, names the problem earlier."""
    from io import BytesIO
    record, doc = _load_doc(ctx, args["design_id"])
    name = _check_mask_name(args["name"])
    img = Image.open(BytesIO(ctx["files"].get_bytes(args["mask_ref"])))
    img.load()
    if img.size != doc.size_px:
        raise ValueError(
            f"mask {name!r} is {img.size}, not the canvas size "
            f"{doc.size_px} of design {args['design_id']!r} — a "
            f"named mask must be a full-canvas image")
    buf = BytesIO()
    img.save(buf, format="PNG")
    rec = {"design_id": args["design_id"], "name": name,
           "size": list(img.size), "ts": _now()}
    rec.update(store_mask_bytes(ctx["files"], args["design_id"],
                                name, buf.getvalue()))
    ctx["transport"].put(f"designmask/{args['design_id']}/{name}", rec)
    _index_add(ctx["transport"], MASK_INDEX, "entries",
               f"{args['design_id']}/{name}")
    return {"design_id": args["design_id"], "name": name,
            "size": list(img.size), "size_bytes": rec["size_bytes"],
            "storage": "mask_ref" if "mask_ref" in rec else "mask_b64"}


def _op_mask_list(ctx, args):
    """Named-mask metadata for one design, from the fixed mask
    index (never by guessing keys)."""
    out = []
    for entry in _index_ids(ctx["transport"], MASK_INDEX, "entries"):
        design_id, _, name = entry.partition("/")
        if design_id != args["design_id"]:
            continue
        rec = ctx["transport"].get(f"designmask/{entry}")
        if isinstance(rec, dict):
            out.append({"name": name, "size": rec.get("size"),
                        "size_bytes": rec.get("size_bytes"),
                        "ts": rec.get("ts")})
    return {"design_id": args["design_id"], "masks": out}


def _op_mask_delete(ctx, args):
    """Remove one named mask (record + any file sidecar + index
    entry) via the kv DELETE route. An edit record that still
    names the mask will fail honestly at apply time — the mask
    is gone, and the sidecar does not invent one."""
    transport = ctx["transport"]
    design_id = args["design_id"]
    name = _check_mask_name(args["name"])
    key = f"designmask/{design_id}/{name}"
    rec = transport.get(key)
    if not isinstance(rec, dict):
        raise KeyError(f"no named mask at {key}")
    if rec.get("mask_ref"):
        ctx["files"].remove(rec["mask_ref"])
    transport.delete(key)
    remaining = [e for e in _index_ids(transport, MASK_INDEX, "entries")
                 if e != f"{design_id}/{name}"]
    _index_set(transport, MASK_INDEX, "entries", remaining)
    return {"design_id": design_id, "name": name, "deleted": True}


def _mask_refs_of(request) -> list[str]:
    """The mask_ref names a request's target + protected entries
    carry, in first-use order."""
    names = []
    for area in [request.target, *request.protected]:
        if isinstance(area, dict) and area.get("mask_ref"):
            if area["mask_ref"] not in names:
                names.append(area["mask_ref"])
    return names


def _resolve_masks(ctx, design_id: str, names: list[str]) -> dict:
    """Load the named masks stored for a design as PIL images —
    the mapping the core's build_mask / apply_edit resolve
    mask_refs against. A missing name is a KeyError naming the
    exact record that is not there."""
    from io import BytesIO
    out = {}
    for name in names:
        rec = ctx["transport"].get(f"designmask/{design_id}/{name}")
        if not isinstance(rec, dict):
            raise KeyError(
                f"no named mask at designmask/{design_id}/{name} — "
                f"store it with a mask.put job first")
        img = Image.open(BytesIO(load_mask_bytes(ctx["files"], rec)))
        img.load()
        out[name] = img
    return out


# ---------------------------------------------------------------------
# S7 edit ops — request + apply. The sidecar generates NOTHING:
# edit.request validates and stores the EditRequest (the core's
# deterministic-intent guard bounces transforms to doc.op before
# anything is stored); edit.apply takes a result image a host
# leg produced (a file sidecar) and runs the core's apply_edit —
# stale revision refused first, then protected-region
# verification. The outline is protected by default because the
# core's effective_protected adds it; there is no switch here.
# Named masks (OPS18): a target/protected entry may carry a
# mask_ref naming a mask in the durable designmask store;
# edit.request verifies the names exist, edit.apply resolves
# them into the mapping the core requires. A region-only target
# (a rect, or a mask_ref with no layer) still has no apply path
# — apply_edit lands pixels on ONE layer, by core design.
# ---------------------------------------------------------------------

def _save_edit_record(transport, rec: dict) -> None:
    transport.put(f"designedit/{rec['request']['request_id']}", rec)
    _index_add(transport, EDIT_INDEX, "edits",
               rec["request"]["request_id"])


def _load_edit_record(transport, request_id: str) -> dict:
    rec = transport.get(f"designedit/{request_id}")
    if not isinstance(rec, dict):
        raise KeyError(f"no edit record at designedit/{request_id}")
    return rec


def _op_edit_request(ctx, args):
    """Validate an AI edit request against the stored doc and
    hold it as a durable designedit record, awaiting a supplied
    result. A deterministic intent (move/resize/hide/...) is
    refused by the core's guard with the ops pointer — that
    refusal IS the bounce to doc.op, and nothing is stored."""
    from studio_design.editmask import EditRequest, validate_edit_request
    record, doc = _load_doc(ctx, args["design_id"])
    request = EditRequest(
        request_id=args["request_id"],
        doc_id=args["design_id"],
        instruction=args["instruction"],
        target=args["target"],
        protected=list(args.get("protected") or []),
        created_by=args.get("created_by", ""),
        geometry_authorized=bool(args.get("geometry_authorized", False)),
        kind=args.get("kind"),
        # The revision the eventual result will be computed
        # against: the caller's, or the doc's current revision
        # when the request is made against what is stored now.
        base_revision=(int(args["base_revision"])
                       if args.get("base_revision") is not None
                       else doc.revision),
    )
    governing = validate_edit_request(doc, request)
    # OPS18: a request may name masks (mask_ref in its target /
    # protected entries). The core resolves them only against a
    # host-supplied mapping, so the names must exist in THIS
    # host's durable mask store for the design — checked now, at
    # request time, so an apply never discovers a missing mask.
    mask_refs = _mask_refs_of(request)
    for name in mask_refs:
        if not isinstance(ctx["transport"].get(
                f"designmask/{args['design_id']}/{name}"), dict):
            raise KeyError(
                f"no named mask at designmask/{args['design_id']}/"
                f"{name} — store it with a mask.put job first")
    rec = {"request": request.to_dict(), "status": "awaiting_result",
           "design_revision": record.get("revision"),
           "mask_refs": mask_refs,
           "created": _now(), "updated": _now()}
    _save_edit_record(ctx["transport"], rec)
    return {"request_id": request.request_id,
            "design_id": args["design_id"],
            "status": "awaiting_result",
            "base_revision": request.base_revision,
            "target": governing["target"],
            "protected": governing["protected"],
            "mask_refs": mask_refs,
            "intent": governing["intent"]}


def _op_edit_apply(ctx, args):
    """Apply a supplied edit result through the core's gates, in
    the core's order: stale revision FIRST (job-level refusal,
    R1 pattern — the edit record is closed refused_stale),
    then protected-region verification inside apply_edit (a
    refusal there is the gate's verdict: the edit record closes
    refused_protected with the verification + preview, the job
    result carries refused=true, and the stored bundle is not
    re-stashed — the design is byte-identical)."""
    from io import BytesIO
    from studio_design.document import StaleRevisionError
    from studio_design.editmask import EditRequest, apply_edit
    transport = ctx["transport"]
    rec = _load_edit_record(transport, args["request_id"])
    if rec["status"] != "awaiting_result":
        raise ValueError(f"edit {args['request_id']!r} is "
                         f"{rec['status']}, not awaiting_result — "
                         f"a decided edit is final; queue a new "
                         f"edit.request to edit again")
    request = EditRequest.from_dict(rec["request"])
    record, doc = _load_doc(ctx, args["design_id"])
    if request.doc_id != args["design_id"]:
        raise ValueError(f"edit {args['request_id']!r} is for doc "
                         f"{request.doc_id!r}, not {args['design_id']!r}")
    if (request.base_revision is not None
            and int(request.base_revision) != int(record.get("revision", 0))):
        rec["status"] = "refused_stale"
        rec["updated"] = _now()
        rec["outcome"] = {"refused": True, "reason": "stale_revision",
                          "base_revision": int(request.base_revision),
                          "current_revision": int(record.get("revision", 0))}
        _save_edit_record(transport, rec)
        raise StaleRevisionError(args["design_id"],
                                 int(request.base_revision),
                                 int(record.get("revision", 0)))
    result_ref = args["result_ref"]
    img = Image.open(BytesIO(ctx["files"].get_bytes(result_ref)))
    img.load()
    # OPS18: resolve the request's named masks from the durable
    # mask store and hand them to the core — the mapping its
    # build_mask / verification resolve mask_refs against. A
    # mask deleted since the request fails here, honestly.
    mask_refs = rec.get("mask_refs") or _mask_refs_of(request)
    masks = (_resolve_masks(ctx, args["design_id"], mask_refs)
             if mask_refs else None)
    outcome = apply_edit(doc, request, img, masks=masks)
    rec["updated"] = _now()
    if outcome.get("refused"):
        rec["status"] = "refused_protected"
        rec["outcome"] = {"refused": True, "reason": "protected_region",
                          "verification": outcome.get("verification"),
                          "preview": outcome.get("preview"),
                          "discarded_px": outcome.get("discarded_px")}
        _save_edit_record(transport, rec)
        return {"request_id": args["request_id"],
                "design_id": args["design_id"],
                "refused": True, "reason": "protected_region",
                "verification": outcome.get("verification"),
                "preview": outcome.get("preview"),
                "revision": record.get("revision")}
    rec["status"] = "applied"
    rec["outcome"] = {"refused": False,
                      "verification": outcome.get("verification"),
                      "discarded_px": outcome.get("discarded_px"),
                      "mask_editable_px": outcome.get("mask_editable_px")}
    _save_edit_record(transport, rec)
    _restash_design(ctx, record, doc)
    return {"request_id": args["request_id"],
            "design_id": args["design_id"],
            "refused": False, "revision": doc.revision,
            "verification": outcome.get("verification"),
            "discarded_px": outcome.get("discarded_px"),
            "mask_editable_px": outcome.get("mask_editable_px")}


def _op_edit_get(ctx, args):
    rec = _load_edit_record(ctx["transport"], args["request_id"])
    return {"edit": rec}


# ---------------------------------------------------------------------
# S8 cover-up ops — the session record is a durable kv record at
# designcover/<coverup_id>; the workspace lives ON the design doc
# (the locked reference layer), so create / set_opacity are
# design-mutating and revision-guarded, while analyze / overlay /
# export read the doc as stored. Exports are the core's own
# new-art-only bundle: the reference is removed on a copy, and
# the export record carries the guarantee note.
# ---------------------------------------------------------------------

def _save_coverup_record(transport, rec: dict) -> None:
    transport.put(f"designcover/{rec['coverup_id']}", rec)
    _index_add(transport, COVERUP_INDEX, "coverups", rec["coverup_id"])


def _load_coverup(ctx, coverup_id: str):
    from studio_design.coverup import CoverUpRecord
    rec = ctx["transport"].get(f"designcover/{coverup_id}")
    if not isinstance(rec, dict):
        raise KeyError(f"no cover-up record at designcover/{coverup_id}")
    return rec, CoverUpRecord.from_dict(rec["record"])


def _op_coverup_create(ctx, args):
    """Open a cover-up session on a stored design: the reference
    photo (a file sidecar a host leg placed) becomes the doc's
    locked bottom reference layer, and the session record —
    calibration fields + the guarantee note, verbatim — is
    stored as a durable kv record."""
    from io import BytesIO
    from studio_design.coverup import calibration, create_coverup
    record, doc = _load_doc(ctx, args["design_id"])
    _require_fresh(args, record)
    if isinstance(ctx["transport"].get(
            f"designcover/{args['coverup_id']}"), dict):
        raise ValueError(f"cover-up {args['coverup_id']!r} already "
                         f"exists — create is create-once")
    photo = Image.open(BytesIO(ctx["files"].get_bytes(args["photo_ref"])))
    photo.load()
    cu = create_coverup(
        doc, args["coverup_id"], photo, source_ref=args["photo_ref"],
        physical_width_mm=float(args["physical_width_mm"]),
        physical_height_mm=float(args["physical_height_mm"]),
        orientation_deg=float(args.get("orientation_deg", 0.0)),
        curvature_note=args.get("curvature_note", ""),
        skin_note=args.get("skin_note", ""),
        threshold=int(args.get("threshold", 128)))
    _restash_design(ctx, record, doc)
    rec = {"coverup_id": cu.coverup_id, "design_id": args["design_id"],
           "record": cu.to_dict(), "status": "open",
           "created": _now(), "updated": _now()}
    _save_coverup_record(ctx["transport"], rec)
    return {"coverup_id": cu.coverup_id, "design_id": args["design_id"],
            "reference_layer_id": cu.reference_layer_id,
            "calibration": calibration(doc, cu),
            "guarantee_note": cu.guarantee_note,
            "revision": doc.revision}


def _op_coverup_analyze(ctx, args):
    """The darkness/coverage figures for the session, with the
    highlight written as a working-aid file. An artist aid —
    the result carries the guarantee note so the figures never
    travel without their limit."""
    from studio_design.coverup import (calibration, coverage_analysis,
                                       export_highlight)
    rec, cu = _load_coverup(ctx, args["coverup_id"])
    record, doc = _load_doc(ctx, rec["design_id"])
    analysis = coverage_analysis(doc, cu,
                                 margin=int(args.get("margin", 24)))
    highlight_ref = (f"file:designs/{rec['design_id']}/"
                     f"coverup-{cu.coverup_id}-highlight.png")
    ctx["files"].put_bytes(highlight_ref, export_highlight(analysis))
    figures = {k: analysis[k] for k in
               ("threshold", "margin", "old_dark_px", "covered_px",
                "uncovered_px", "coverage_ratio")}
    rec["last_analysis"] = {**figures, "highlight_ref": highlight_ref,
                            "ts": _now()}
    rec["updated"] = _now()
    _save_coverup_record(ctx["transport"], rec)
    return {"coverup_id": cu.coverup_id, "design_id": rec["design_id"],
            **figures, "highlight_ref": highlight_ref,
            "calibration": calibration(doc, cu),
            "guarantee_note": cu.guarantee_note}


def _op_coverup_overlay(ctx, args):
    """The working view (reference at its overlay opacity with
    the new art over it) as a file. A viewing aid — never a
    design export; the export op is coverup.export."""
    from io import BytesIO
    from studio_design.coverup import render_overlay
    rec, cu = _load_coverup(ctx, args["coverup_id"])
    record, doc = _load_doc(ctx, rec["design_id"])
    buf = BytesIO()
    render_overlay(doc, cu).save(buf, format="PNG")
    ref = (f"file:designs/{rec['design_id']}/"
           f"coverup-{cu.coverup_id}-overlay.png")
    ctx["files"].put_bytes(ref, buf.getvalue())
    return {"coverup_id": cu.coverup_id, "design_id": rec["design_id"],
            "overlay_ref": ref}


def _op_coverup_set_opacity(ctx, args):
    """Adjust the reference's overlay opacity through the core's
    sanctioned lock exception (the op log names it). Mutating:
    revision-guarded like every design change."""
    from studio_design.coverup import set_reference_opacity
    rec, cu = _load_coverup(ctx, args["coverup_id"])
    record, doc = _load_doc(ctx, rec["design_id"])
    _require_fresh(args, record)
    set_reference_opacity(doc, cu, float(args["opacity"]))
    _restash_design(ctx, record, doc)
    layer = doc.get(cu.reference_layer_id)
    return {"coverup_id": cu.coverup_id, "design_id": rec["design_id"],
            "reference_layer_id": cu.reference_layer_id,
            "opacity": layer.opacity, "locked": layer.locked,
            "revision": doc.revision}


def _op_coverup_export(ctx, args):
    """Export the NEW ART ONLY (the core removes the reference
    on a copy; the working doc is untouched). The exported
    bundle is stored as a file sidecar; the result names its
    layer list so the exclusion is read from the export itself,
    and the export record carries the guarantee note."""
    from studio_design.coverup import export_coverup_design
    from studio_design.document import DesignDoc
    rec, cu = _load_coverup(ctx, args["coverup_id"])
    record, doc = _load_doc(ctx, rec["design_id"])
    out = export_coverup_design(doc, cu)
    ref = (f"file:designs/{rec['design_id']}/"
           f"coverup-{cu.coverup_id}-export.zip")
    ctx["files"].put_bytes(ref, out["bundle"])
    exported = DesignDoc.load_bundle(out["bundle"])
    return {"coverup_id": cu.coverup_id, "design_id": rec["design_id"],
            "export_ref": ref, "record": out["record"],
            "guarantee_note": out["guarantee_note"],
            "layers": [{"id": l.id, "name": l.name, "role": l.role}
                       for l in exported.layers]}


def _op_coverup_get(ctx, args):
    rec, cu = _load_coverup(ctx, args["coverup_id"])
    return {"coverup": rec}


# ---------------------------------------------------------------------
# Library + stamp kits — the core ElementLibrary rebuilt from kv
# each cycle (the sidecar is stateless; the core owns the
# scoping rules: an artist's kits hold only their own elements,
# deletes are the owning artist's explicit act, nothing
# expires). Element records are durable kv records at
# designlib/<artist>/<element> + their PNG bytes; kits at
# designkit/<artist>/<kit>. Mutations persist the touched
# artist's slice back whole.
# ---------------------------------------------------------------------

_ELEMENT_CORE_FIELDS = ("element_id", "name", "kind",
                        "source_design_id", "tags", "created_ts")


def _load_library(ctx):
    """Rebuild (ElementLibrary, bytes-by-(artist, element)) from
    the fixed library/kit indexes. A record the index names but
    the store lacks is skipped here and reported by the ops that
    address it — never invented."""
    if ctx["library"] is not None:
        return ctx["library"]
    import json as _json
    from studio_design.library import ElementLibrary
    transport = ctx["transport"]
    elements: dict[str, list[dict]] = {}
    bytes_map: dict[tuple[str, str], bytes] = {}
    for entry in _index_ids(transport, LIBRARY_INDEX, "entries"):
        artist_id, _, element_id = entry.partition("/")
        rec = transport.get(f"designlib/{artist_id}/{element_id}")
        if not isinstance(rec, dict):
            continue
        elements.setdefault(artist_id, []).append(
            {k: rec.get(k) for k in _ELEMENT_CORE_FIELDS})
        bytes_map[(artist_id, element_id)] = load_element_bytes(
            ctx["files"], rec)
    kits: dict[str, list[dict]] = {}
    for entry in _index_ids(transport, KIT_INDEX, "kits"):
        artist_id, _, kit_id = entry.partition("/")
        rec = transport.get(f"designkit/{artist_id}/{kit_id}")
        if isinstance(rec, dict):
            kits.setdefault(artist_id, []).append(
                {"kit_id": rec["kit_id"], "artist_id": artist_id,
                 "name": rec["name"],
                 "element_ids": list(rec.get("element_ids", []))})
    meta = transport.get(LIBRARY_META)
    counter = int(meta.get("kit_counter", 0)) if isinstance(meta, dict) else 0
    lib = ElementLibrary.from_json(_json.dumps(
        {"elements": elements, "kits": kits, "kit_counter": counter}))
    ctx["library"] = (lib, bytes_map)
    return ctx["library"]


def _persist_library_artist(ctx, artist_id: str) -> None:
    """Write one artist's library slice back to kv: element
    records (with their byte-storage fields preserved — fresh
    bytes were stored by the save op before this runs), kit
    records, the artist's index entries, and the kit counter."""
    import json as _json
    lib, bytes_map = _load_library(ctx)
    transport = ctx["transport"]
    current_elements = {e["element_id"]: e
                        for e in lib.list_elements(artist_id)}
    old_entries = [e for e in _index_ids(transport, LIBRARY_INDEX,
                                         "entries")
                   if e.partition("/")[0] == artist_id]
    for entry in old_entries:
        element_id = entry.partition("/")[2]
        if element_id not in current_elements:
            old = transport.get(f"designlib/{artist_id}/{element_id}")
            transport.delete(f"designlib/{artist_id}/{element_id}")
            if isinstance(old, dict) and old.get("element_ref"):
                ctx["files"].remove(old["element_ref"])
            bytes_map.pop((artist_id, element_id), None)
    for element_id, core_rec in current_elements.items():
        key = f"designlib/{artist_id}/{element_id}"
        existing = transport.get(key)
        kv = dict(core_rec)
        if (artist_id, element_id) in bytes_map and not (
                isinstance(existing, dict)
                and (existing.get("element_b64")
                     or existing.get("element_ref"))):
            kv.update(store_element_bytes(ctx["files"], artist_id,
                                          element_id,
                                          bytes_map[(artist_id,
                                                       element_id)]))
        elif isinstance(existing, dict):
            for f in ("element_b64", "element_ref", "size_bytes"):
                if f in existing:
                    kv[f] = existing[f]
        else:
            raise ValueError(f"library element {element_id!r} has "
                             f"no stored bytes to persist")
        transport.put(key, kv)
    for kit in lib.list_kits(artist_id):
        transport.put(f"designkit/{artist_id}/{kit['kit_id']}", kit)
    other_e = [e for e in _index_ids(transport, LIBRARY_INDEX,
                                     "entries")
               if e.partition("/")[0] != artist_id]
    _index_set(transport, LIBRARY_INDEX, "entries",
               other_e + [f"{artist_id}/{eid}"
                          for eid in current_elements])
    other_k = [e for e in _index_ids(transport, KIT_INDEX, "kits")
               if e.partition("/")[0] != artist_id]
    _index_set(transport, KIT_INDEX, "kits",
               other_k + [f"{artist_id}/{k['kit_id']}"
                          for k in lib.list_kits(artist_id)])
    counter = _json.loads(lib.to_json())["kit_counter"]
    transport.put(LIBRARY_META, {"kit_counter": counter})


def _op_library_save_element(ctx, args):
    """Save one layer of a stored design into its artist's
    library: the core record (owner-stamped, no expiry — ever)
    plus the layer's PNG bytes. The design itself is only read,
    so no revision guard applies."""
    record, doc = _load_doc(ctx, args["design_id"])
    layer = doc.get(args["layer_id"])
    kind = args.get("kind")
    if kind is None:
        if layer.kind == "stamp":
            kind = "stamp"
        elif layer.role in ("line", "shading"):
            kind = layer.role
        else:
            kind = "raster"
    element_id = args.get("element_id") or f"{args['design_id']}-{layer.id}"
    lib, bytes_map = _load_library(ctx)
    saved = lib.save_element(args["artist_id"], {
        "element_id": element_id,
        "name": args.get("name", layer.name),
        "kind": kind,
        "source_design_id": args["design_id"],
        "tags": list(args.get("tags") or []),
        "created_ts": _now()})
    from io import BytesIO
    img = Image.open(BytesIO(doc.share_layer(layer.id)))
    img.load()
    buf = BytesIO()
    img.save(buf, format="PNG")
    bytes_map[(args["artist_id"], element_id)] = buf.getvalue()
    existing = ctx["transport"].get(
        f"designlib/{args['artist_id']}/{element_id}")
    if isinstance(existing, dict) and existing.get("element_ref"):
        ctx["files"].remove(existing["element_ref"])
    if isinstance(existing, dict):
        for f in ("element_b64", "element_ref"):
            existing.pop(f, None)
        ctx["transport"].put(
            f"designlib/{args['artist_id']}/{element_id}", existing)
    _persist_library_artist(ctx, args["artist_id"])
    stored = ctx["transport"].get(
        f"designlib/{args['artist_id']}/{element_id}")
    return {"element": saved,
            "storage": "element_ref" if "element_ref" in stored
                       else "element_b64",
            "size_bytes": stored.get("size_bytes")}


def _op_library_get_element(ctx, args):
    lib, _ = _load_library(ctx)
    rec = lib.get_element(args["artist_id"], args["element_id"])
    return {"element": rec,
            "provenance": lib.element_provenance(args["artist_id"],
                                                 args["element_id"])}


def _op_library_list(ctx, args):
    lib, _ = _load_library(ctx)
    return {"artist_id": args["artist_id"], **lib.artist_view(args["artist_id"])}


def _op_library_delete_element(ctx, args):
    """The ONLY removal path in the library, and it is the
    owning artist's explicit act (the core also pulls the
    element out of the artist's kits)."""
    lib, _ = _load_library(ctx)
    lib.delete_element(args["artist_id"], args["element_id"])
    _persist_library_artist(ctx, args["artist_id"])
    return {"artist_id": args["artist_id"],
            "deleted": args["element_id"]}


def _op_library_create_kit(ctx, args):
    lib, _ = _load_library(ctx)
    kit = lib.create_kit(args["artist_id"], args["name"])
    _persist_library_artist(ctx, args["artist_id"])
    return {"kit": kit}


def _op_library_add_to_kit(ctx, args):
    """Add one of the artist's OWN elements to their kit — the
    core refuses another artist's element (KeyError), and that
    refusal is the ownership rule working."""
    lib, _ = _load_library(ctx)
    kit = lib.add_to_kit(args["artist_id"], args["kit_id"],
                         args["element_id"])
    _persist_library_artist(ctx, args["artist_id"])
    return {"kit": kit}


def _op_library_remove_from_kit(ctx, args):
    lib, _ = _load_library(ctx)
    kit = lib.remove_from_kit(args["artist_id"], args["kit_id"],
                              args["element_id"])
    _persist_library_artist(ctx, args["artist_id"])
    return {"kit": kit}


_REUSE_ROLE = {"line": "line", "shading": "shading",
               "stamp": "line", "raster": "art"}


def _op_library_reuse(ctx, args):
    """Pull a library element into a (possibly different, later)
    design as a new layer, stamped with the core's provenance
    record — the reuse is on record through save/load. Design-
    mutating: revision-guarded."""
    from io import BytesIO
    lib, bytes_map = _load_library(ctx)
    provenance = lib.element_provenance(args["artist_id"],
                                        args["element_id"])
    record, doc = _load_doc(ctx, args["design_id"])
    _require_fresh(args, record)
    img = Image.open(BytesIO(bytes_map[(args["artist_id"],
                                        args["element_id"])]))
    img.load()
    element = lib.get_element(args["artist_id"], args["element_id"])
    role = args.get("role") or _REUSE_ROLE.get(element["kind"], "art")
    layer_id = doc.add_raster(args.get("name", element["name"]), img,
                              role=role, provenance=provenance)
    _restash_design(ctx, record, doc)
    return {"design_id": args["design_id"], "layer_id": layer_id,
            "provenance": provenance, "revision": doc.revision}


# ---------------------------------------------------------------------
# File exports (OPS18) — PSD (the doc's own layered export) and
# the S10 Procreate stamp interchange (.brush / .brushset).
# Exports are derived artifacts: the bytes go to the file store,
# the core's export record rides the job result verbatim, and
# exporting never mutates the design (no revision change). The
# brush records carry SPEC_STATUS — research-conformant, import
# UNPROVEN — and nothing here upgrades that claim.
# ---------------------------------------------------------------------

def _op_export_psd(ctx, args):
    """The design's layered PSD (the core's export_psd: reference
    layers excluded by the core), written as a file and recorded
    on the design record's exports. The result's layer list is
    read back through the core's own PSD reader, so what the job
    reports is what the file actually holds."""
    from studio_design.psd import read_psd
    record, doc = _load_doc(ctx, args["design_id"])
    data = doc.export_psd()
    ref = f"file:designs/{args['design_id']}/export.psd"
    ctx["files"].put_bytes(ref, data)
    parsed = read_psd(data)
    exports = dict(record.get("exports", {}))
    exports["psd"] = ref
    record["exports"] = exports
    record["updated"] = _now()
    _save_design_record(ctx["transport"], record)
    return {"design_id": args["design_id"], "psd_ref": ref,
            "size_bytes": len(data),
            "width": parsed["width"], "height": parsed["height"],
            "layers": [{"name": l["name"], "opacity": l["opacity"],
                        "visible": l["visible"]}
                       for l in parsed["layers"]]}


def _op_export_brush(ctx, args):
    """One design layer -> one .brush stamp file (the core's
    export_stamp_brush). Source layer: layer_id, else the
    structural outline, else the first line layer — a stamp is
    made from linework. The export record rides the result
    verbatim, spec_status included."""
    from io import BytesIO
    from studio_design.brush import export_stamp_brush
    record, doc = _load_doc(ctx, args["design_id"])
    layer_id = args.get("layer_id") or doc.outline_layer
    if not layer_id:
        line_layers = [l for l in doc.layers if l.role == "line"]
        layer_id = line_layers[0].id if line_layers else None
    if not layer_id:
        raise ValueError("export.brush needs a layer_id — this "
                         "design has no line layer to stamp from")
    layer = doc.get(layer_id)
    img = Image.open(BytesIO(doc.share_layer(layer_id)))
    img.load()
    data, rec = export_stamp_brush(img, args.get("name") or layer.name,
                                   grain=args.get("grain", "blank"))
    ref = (f"file:designs/{args['design_id']}/exports/"
           f"{rec['brushes'][0]['uuid']}.brush")
    ctx["files"].put_bytes(ref, data)
    return {"design_id": args["design_id"], "layer_id": layer_id,
            "brush_ref": ref, "size_bytes": len(data), "record": rec}


def _op_export_brushset(ctx, args):
    """One of an artist's stamp kits -> one .brushset file (the
    core's export_stamp_kit_as_brushset): the kit's element ids
    resolved to their stored library images, one stamp brush per
    element. An empty kit is refused by the core — a brushset
    needs at least one element."""
    from io import BytesIO
    from studio_design.brush import export_stamp_kit_as_brushset
    lib, bytes_map = _load_library(ctx)
    kit = lib.get_kit(args["artist_id"], args["kit_id"])
    elements = []
    for element_id in kit["element_ids"]:
        element = lib.get_element(args["artist_id"], element_id)
        img = Image.open(BytesIO(bytes_map[(args["artist_id"],
                                            element_id)]))
        img.load()
        elements.append({"name": element["name"], "image": img,
                         "element_id": element_id})
    data, rec = export_stamp_kit_as_brushset(
        elements, args.get("set_name") or kit["name"],
        grain=args.get("grain", "blank"))
    ref = f"file:library/{args['artist_id']}/{args['kit_id']}.brushset"
    ctx["files"].put_bytes(ref, data)
    return {"artist_id": args["artist_id"], "kit_id": args["kit_id"],
            "brushset_ref": ref, "size_bytes": len(data),
            "record": rec}


JOB_OPS = {
    "profile.seed": _op_profile_seed,
    "profile.get": _op_profile_get,
    "profile.update": _op_profile_update,
    "route_request": _op_route_request,
    "plan_versions": _op_plan_versions,
    "request.intake": _op_request_intake,
    "request.evaluate": _op_request_evaluate,
    "request.route": _op_request_route,
    "request.plan": _op_request_plan,
    "request.submit": _op_request_submit,
    "request.artist_approve": _op_request_artist_approve,
    "request.artist_reject": _op_request_artist_reject,
    "request.alert_artist": _op_request_alert_artist,
    "request.send": _op_request_send,
    "request.revision": _op_request_revision,
    "request.customer_approve": _op_request_customer_approve,
    "request.stencil_ready": _op_request_stencil_ready,
    "doc.build": _op_doc_build,
    "doc.validate": _op_doc_validate,
    "doc.export": _op_doc_export,
    "doc.op": _op_doc_op,
    "doc.get": _op_doc_get,
    "doc.set_structural_outline": _op_doc_set_structural_outline,
    "doc.outline_accept": _op_doc_outline_accept,
    "doc.shading_plan": _op_doc_shading_plan,
    "doc.measure_contours": _op_doc_measure_contours,
    "doc.set_lighting": _op_doc_set_lighting,
    "doc.snapshot_put": _op_doc_snapshot_put,
    "doc.snapshot_restore": _op_doc_snapshot_restore,
    "doc.snapshot_list": _op_doc_snapshot_list,
    "doc.snapshot_delete": _op_doc_snapshot_delete,
    "doc.undo": _op_doc_undo,
    "doc.redo": _op_doc_redo,
    "mask.put": _op_mask_put,
    "mask.list": _op_mask_list,
    "mask.delete": _op_mask_delete,
    "edit.request": _op_edit_request,
    "edit.apply": _op_edit_apply,
    "edit.get": _op_edit_get,
    "coverup.create": _op_coverup_create,
    "coverup.analyze": _op_coverup_analyze,
    "coverup.overlay": _op_coverup_overlay,
    "coverup.set_opacity": _op_coverup_set_opacity,
    "coverup.export": _op_coverup_export,
    "coverup.get": _op_coverup_get,
    "library.save_element": _op_library_save_element,
    "library.get_element": _op_library_get_element,
    "library.list": _op_library_list,
    "library.delete_element": _op_library_delete_element,
    "library.create_kit": _op_library_create_kit,
    "library.add_to_kit": _op_library_add_to_kit,
    "library.remove_from_kit": _op_library_remove_from_kit,
    "library.reuse": _op_library_reuse,
    "export.psd": _op_export_psd,
    "export.brush": _op_export_brush,
    "export.brushset": _op_export_brushset,
}


# ---------------------------------------------------------------------
# Cycle phases
# ---------------------------------------------------------------------

def run_jobs(transport, files) -> dict:
    """Phase 1 — execute queued jobs discovered ONLY through the
    fixed index key. A job already done/error is final (the agent
    queues a new job rather than re-running one).

    R1: a StaleRevisionError from a mutating op is a REFUSAL, not
    a failure — the job record closes status "error" (final, like
    any refusal) with a structured `refusal` naming both
    revisions, and the cycle report lists it under "refused" as
    well as "errors". Nothing was applied; the design record is
    exactly as it was."""
    from studio_design.document import StaleRevisionError
    report = {"executed": [], "errors": [], "missing_records": [],
              "refused": []}
    ctx = _ctx(transport, files)
    for job_id in _index_ids(transport, JOB_INDEX, "jobs"):
        job = transport.get(f"designjob/{job_id}")
        if not isinstance(job, dict):
            report["missing_records"].append(job_id)
            continue
        if job.get("status") != "queued":
            continue
        op = job.get("op")
        job["status"] = "running"
        transport.put(f"designjob/{job_id}", job)
        try:
            if op not in JOB_OPS:
                raise ValueError(
                    f"op {op!r} is not on the sidecar allowlist "
                    f"{sorted(JOB_OPS)} — refused, nothing ran")
            result = JOB_OPS[op](ctx, job.get("args") or {})
            job["status"] = "done"
            job["result"] = result
            job.pop("error", None)
            report["executed"].append(job_id)
        except StaleRevisionError as exc:
            job["status"] = "error"
            job["error"] = f"{type(exc).__name__}: {exc}"
            job["refusal"] = {"reason": "stale_revision",
                              "base_revision": exc.base_revision,
                              "current_revision": exc.current_revision}
            report["errors"].append({"job_id": job_id, "error": job["error"]})
            report["refused"].append(job_id)
        except Exception as exc:
            job["status"] = "error"
            job["error"] = f"{type(exc).__name__}: {exc}"
            report["errors"].append({"job_id": job_id, "error": job["error"]})
        job["finished"] = _now()
        transport.put(f"designjob/{job_id}", job)
    return report


def run_approvals(transport) -> dict:
    """Phase 2 — pull-sync's drafts phase, for designer drafts.
    kv is the ledger: a `decided` draft is terminal. An approved
    or rejected linked approval is applied ONCE (the package
    transition runs here) and the draft closes. A held draft with
    no live approval is carried (or re-carried after expiry)."""
    report = {"carried": [], "decided": [], "notes": []}
    approvals = transport.get_approvals()
    status_by_id = {a.get("id"): a.get("status") for a in approvals}
    flow = None
    for key, value in transport.list_pairs():
        if not key.startswith(DRAFT_PREFIX):
            continue
        draft = value
        if isinstance(draft, str):
            try:
                draft = json.loads(draft)
            except Exception:
                continue
        if not isinstance(draft, dict) or not draft.get("text"):
            continue
        if draft.get("status") == "decided":
            continue  # TERMINAL — the kv ledger outranks the API
        linked = status_by_id.get(draft.get("approval_id", ""))
        if linked in ("approved", "rejected"):
            rid = draft["request_id"]
            if flow is None:
                flow = _load_flow(transport)
            req = flow.requests.get(rid)
            if req is not None and req.status == "awaiting_artist":
                if linked == "approved":
                    flow.artist_approve(rid)
                else:
                    flow.artist_reject(rid)
                _save_request(transport, req)
                _save_designs(transport, flow)
            elif req is not None:
                report["notes"].append(
                    f"{key}: decision {linked} not applied — request "
                    f"is {req.status}, not awaiting_artist")
            draft["status"] = "decided"
            draft["decision"] = linked
            transport.put(key, draft)
            report["decided"].append({"draft": key, "decision": linked})
            continue
        if draft.get("approval_id") and linked == "pending":
            continue  # already live in Needs-you
        ap = transport.post_approval({
            "agent_id": transport.agent_id(),
            "tool_name": "design_approval",
            "description": draft["text"],
            "action_summary": "Design held for the artist's approval",
        })
        draft["status"] = "in-needs-you"
        draft["approval_id"] = ap.get("id", "")
        transport.put(key, draft)
        report["carried"].append({"draft": key,
                                  "approval_id": draft["approval_id"]})
    return report


def run_cycle(transport, files) -> dict:
    """One sidecar cycle: preflight, jobs, approvals, wake-poke
    naming the exact result keys (pull-sync's pattern — the agent
    is told keys, it never searches)."""
    ok, message = preflight()
    if not ok:
        return {"ok": False, "preflight": message}
    jobs = run_jobs(transport, files)
    approvals = run_approvals(transport)
    finished = (list(jobs["executed"])
                + [e["job_id"] for e in jobs["errors"]])
    if finished:
        keys = ", ".join(f"designjob/{j}" for j in finished)
        try:
            transport.wake(
                f"Designer sidecar finished job(s). Recall these exact "
                f"keys and report from the records: {keys}. "
                f"(memory_recall is exact-key only; do not guess keys.)")
        except Exception:
            pass  # a failed wake never fails the cycle; the sweep finds them
    return {"ok": True, "jobs": jobs, "approvals": approvals}


def main(argv=None) -> int:
    transport = HttpKvTransport()
    files = FileSidecarStore()
    report = run_cycle(transport, files)
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
