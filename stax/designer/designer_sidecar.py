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
- `draft/design-<request_id>`  the durable approval hold

REVISIONS (R1): every `design/<id>` record carries `revision`,
the core document's mutation counter, rewritten from the loaded
doc after every mutating job. A mutating job (doc.op,
doc.set_structural_outline, doc.set_lighting, doc.snapshot_restore)
MAY carry `base_revision` in its args — the revision the caller
computed against. When it is present and no longer equals the
record's revision, the job is REFUSED before anything runs: the
job record closes status "error" with a structured `refusal`
{reason: "stale_revision", base_revision, current_revision} and
the cycle report lists it under "refused". A delayed result can
never overwrite newer edits. Jobs without base_revision are
legacy/unguarded (the pre-R1 protocol) and run as before.

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
the chat/host image path, as in every package slice.
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
    the R1 revision read back off the doc, and the timestamp."""
    record.pop("bundle_b64", None)
    record.pop("bundle_ref", None)
    record.update(store_bundle(ctx["transport"], ctx["files"],
                               record["id"], doc.save_bundle()))
    record["revision"] = doc.revision
    record["updated"] = _now()
    _save_design_record(ctx["transport"], record)


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
            "store": None, "flow": None}


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
    return {"design_id": args["design_id"], "exports": written}


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
    record's revision advances with the doc's."""
    from studio_design.outline import set_structural_outline
    record, doc = _load_doc(ctx, args["design_id"])
    _require_fresh(args, record)
    set_structural_outline(doc, args["layer_id"])
    _restash_design(ctx, record, doc)
    return {"design_id": args["design_id"],
            "outline_layer": doc.outline_layer,
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
    "doc.shading_plan": _op_doc_shading_plan,
    "doc.measure_contours": _op_doc_measure_contours,
    "doc.set_lighting": _op_doc_set_lighting,
    "doc.snapshot_put": _op_doc_snapshot_put,
    "doc.snapshot_restore": _op_doc_snapshot_restore,
    "doc.snapshot_list": _op_doc_snapshot_list,
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
