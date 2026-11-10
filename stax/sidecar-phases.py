#!/usr/bin/env python3
# sidecar-phases.py — deterministic sidecar phases beside the OpenFang daemon,
# invoked at the end of pull-sync.sh's run (Memory Sweep brief, 2026-11-02).
# One home for the deterministic phases the memory work needs; the phases are
# independently logged and independently failing — a phase error is logged and
# swallowed so it can never break pull-sync's intake cycles.
#
# Phase "digest" (Phase 1): maintain the brief-input digest. A hash ledger
# over the kv snapshot (memsweep/state) tracks first-seen for the sms/,
# formsub/ and memcand/ record families; each cycle the phase writes
# briefinput/<yyyy-mm-dd> with the live pending-approval count, the keys
# first seen since 06:00 local yesterday, and the count of memory candidates
# waiting. The ledger SEEDS BASELINE on its first run: every pre-existing key
# is recorded as baseline and never reported as new, so "new" in the digest
# means genuinely new since the digest landed. Deterministic code only — no
# model ever writes the digest.
import sys, os, json, hashlib, urllib.request, urllib.parse, urllib.error, datetime

API = "http://127.0.0.1:4200"
SHARED = "00000000-0000-4000-8000-000000000001"
FAMILIES = ("formsub", "sms", "memcand")
NEW_CAP = 50


def token():
    # Same source pull-sync uses: the api_key line of ~/.openfang/config.toml.
    with open(os.path.expanduser("~/.openfang/config.toml")) as f:
        for line in f:
            if line.strip().startswith("api_key"):
                return line.split('"')[1]
    raise RuntimeError("api_key not found in config.toml")


def req(tok, method, path, body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method)
    r.add_header("Authorization", "Bearer " + tok)
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def as_record(v):
    """kv values arrive as dicts or JSON strings; return the dict or None."""
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return None
    return v if isinstance(v, dict) else None


def sha_of(v):
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            pass
    blob = v if isinstance(v, str) else json.dumps(
        v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def kv_put(tok, key, value):
    enc = urllib.parse.quote(key, safe="")
    req(tok, "PUT", f"/api/memory/agents/{SHARED}/kv/{enc}", {"value": value})


def digest_phase(tok):
    now = datetime.datetime.now().astimezone()
    today = now.date()
    window_start = (now.replace(hour=6, minute=0, second=0, microsecond=0)
                    - datetime.timedelta(days=1))

    kv = req(tok, "GET", f"/api/memory/agents/{SHARED}/kv")
    pairs = kv.get("kv_pairs", []) if isinstance(kv, dict) else []
    snapshot = {p.get("key", ""): p.get("value") for p in pairs}

    approvals = req(tok, "GET", "/api/approvals")
    ap_list = approvals if isinstance(approvals, list) else approvals.get("approvals", [])
    pending = sum(1 for a in ap_list if a.get("status") == "pending")

    old = as_record(snapshot.get("memsweep/state")) or {}
    old_entries = old.get("entries") if isinstance(old.get("entries"), dict) else None
    baseline_mode = old_entries is None
    if baseline_mode:
        old_entries = {}

    entries = {}
    candidates_waiting = 0
    for key, raw in snapshot.items():
        fam = next((f for f in FAMILIES if key.startswith(f + "/")), None)
        if fam is None:
            continue
        rec = as_record(raw)
        if rec is None:
            continue
        if fam == "memcand" and rec.get("status") in ("candidate", "in-needs-you"):
            candidates_waiting += 1
        prev = old_entries.get(key)
        if prev:
            entries[key] = {"sha": sha_of(raw),
                            "first_seen": prev.get("first_seen", now.isoformat(timespec="seconds")),
                            "baseline": bool(prev.get("baseline", False))}
        else:
            entries[key] = {"sha": sha_of(raw),
                            "first_seen": now.isoformat(timespec="seconds"),
                            "baseline": baseline_mode}

    if baseline_mode or entries != old_entries:
        kv_put(tok, "memsweep/state",
               {"version": 1, "updated": now.isoformat(timespec="seconds"),
                "entries": entries})

    new_keys, capped = {}, {}
    for fam in FAMILIES:
        fresh = []
        for key, e in entries.items():
            if not key.startswith(fam + "/") or e.get("baseline"):
                continue
            try:
                seen = datetime.datetime.fromisoformat(e.get("first_seen", ""))
            except Exception:
                continue
            if seen >= window_start:
                fresh.append(key)
        fresh.sort()
        if len(fresh) > NEW_CAP:
            capped[fam] = len(fresh)
            fresh = fresh[:NEW_CAP]
        new_keys[fam] = fresh

    digest = {"date": today.isoformat(),
              "updated": now.isoformat(timespec="seconds"),
              "pending_approvals": pending,
              "new_keys": new_keys,
              "candidates_waiting": candidates_waiting}
    if capped:
        digest["new_keys_total"] = capped
    kv_put(tok, f"briefinput/{today.isoformat()}", digest)
    total_new = sum(len(v) for v in new_keys.values())
    print(now.isoformat(timespec="seconds"),
          f"digest: briefinput/{today.isoformat()} pending={pending} "
          f"candidates_waiting={candidates_waiting} tracked={len(entries)} "
          f"new={total_new} baseline={'seeded' if baseline_mode else 'no'}")



# ── Memory helper phases (memwake → verify → memcarry) ───────────────────
# memwake names changed conversation records to the Memory helper; the
# helper proposes facts with the memory_propose tool (the daemon checks the
# exact words and computes the key). verify greps every candidate's quote
# against its source. memcarry carries candidates to Needs you, deletes
# rejected ones, and on approval appends ONE note to the contact in code.
# All three do nothing until a "memory" agent exists.

# At most 10 source keys named per wake; the ledger makes deferral lossless.
WAKE_CAP = 10


def kv_snapshot(tok):
    kv = req(tok, "GET", f"/api/memory/agents/{SHARED}/kv")
    pairs = kv.get("kv_pairs", []) if isinstance(kv, dict) else []
    return {p.get("key", ""): p.get("value") for p in pairs}


def now_local():
    return datetime.datetime.now().astimezone()


def agent_id(tok, name):
    agents = req(tok, "GET", "/api/agents")
    if isinstance(agents, dict):
        agents = agents.get("agents", [])
    return next((a.get("id") for a in agents if a.get("name") == name), None)


def approvals_map(tok):
    approvals = req(tok, "GET", "/api/approvals")
    ap_list = approvals if isinstance(approvals, list) else approvals.get("approvals", [])
    return {a.get("id"): a.get("status") for a in ap_list}, ap_list


# Ledger note (why TWO ledgers exist): memsweep/state belongs to the digest
# — it answers "when did we first see this key" and refreshes every key's
# sha every cycle by design. Extraction needs the opposite discipline —
# "update the hash only for keys named in a wake" — so a changed record the
# wake cap defers is still changed next cycle instead of being silently
# absorbed. memwake/state is that ledger; do not unify them. There is
# deliberately NO baseline seed here (the digest's seeding was digest-only):
# the first live run is the brief's Part 7 gate run, which must process the
# thread records already on the box; the 10-key cap drains any backlog over
# the first hours and the ledger makes the drain exact.

def qualifying_keys(snapshot):
    """Conversation records the sweep may process: sms/<digits> threads and
    formsub/<slug>/<uuid> submissions already marked processed. The shape
    tests are what keep the family's debris keys (a bare formsub/ key,
    formsub/status, unslugged copies) out of the work list."""
    out = {}
    for key, raw in snapshot.items():
        rec = as_record(raw)
        if rec is None:
            continue
        if key.startswith("sms/") and key.count("/") == 1:
            out[key] = raw
        elif (key.startswith("formsub/") and key.count("/") >= 2
              and rec.get("processed") is True):
            out[key] = raw
    return out


def memwake_phase(tok):
    now = now_local()
    stamp = now.isoformat(timespec="seconds")
    snapshot = kv_snapshot(tok)
    state = as_record(snapshot.get("memwake/state")) or {}
    entries = state.get("entries") if isinstance(state.get("entries"), dict) else {}
    work = []
    for key, raw in qualifying_keys(snapshot).items():
        sha = sha_of(raw)
        prev = entries.get(key)
        if not prev or prev.get("sha") != sha:
            work.append((key, sha))
    work.sort()
    named = work[:WAKE_CAP]
    if not named:
        print(stamp, "memwake: no changed conversation records")
        return
    mem_id = agent_id(tok, "memory")
    if not mem_id:
        # Ledger untouched on purpose: the same diff is retried next cycle.
        print(stamp, "memwake: memory agent not found — ledger untouched, will retry")
        return
    keys = ", ".join(k for k, _ in named)
    msg = ("New or changed conversation records are waiting at these exact "
           f"keys: {keys}. Recall each key exactly and extract per your "
           "playbook (candidates only — quote or nothing). Keys not named "
           "here are not yours to process.")
    r = req(tok, "POST", f"/api/agents/{mem_id}/message",
            {"message": msg}, timeout=220)
    if not (isinstance(r, dict) and r.get("response")):
        print(stamp, "memwake: wake got no response — ledger untouched, will retry")
        return
    for k, sha in named:
        entries[k] = {"sha": sha, "named_ts": stamp}
    kv_put(tok, "memwake/state",
           {"version": 1, "updated": stamp, "entries": entries})
    print(stamp, f"memwake: woke memory over {len(named)} key(s); "
                 f"{len(work) - len(named)} deferred")


def string_leaves(v, out):
    if isinstance(v, str):
        out.append(v)
    elif isinstance(v, dict):
        for x in v.values():
            string_leaves(x, out)
    elif isinstance(v, list):
        for x in v:
            string_leaves(x, out)


def verify_phase(tok):
    """Mechanical, 100%: every memcand quote must appear verbatim in its
    source record. The haystacks are the source's raw stored string (when
    it is one), its canonical JSON, and every string leaf it holds — the
    quote must match the record's actual text, not an artifact of JSON
    escaping. One miss fails the run: the caller files a Ratchet case and
    no candidate from the batch is carried until a re-run is clean.
    Also reports (warning only) keys that differ from their content hash —
    the hand derives hash16 by reasoning, so the deterministic side owns
    checking its work. Since the memory_propose tool, the daemon computes
    the key itself, so a key warning now means a hand-written candidate."""
    stamp = now_local().isoformat(timespec="seconds")
    snapshot = kv_snapshot(tok)
    fails, warns, checked = [], [], 0
    for key in sorted(snapshot):
        if not key.startswith("memcand/"):
            continue
        rec = as_record(snapshot[key])
        if rec is None:
            fails.append((key, "candidate is not a record"))
            continue
        quote, src_key = rec.get("quote"), rec.get("source_key")
        if not quote or not src_key:
            fails.append((key, "missing quote or source_key"))
            continue
        src_raw = snapshot.get(src_key)
        if src_raw is None:
            fails.append((key, f"source {src_key} not in store"))
            continue
        hay = []
        if isinstance(src_raw, str):
            hay.append(src_raw)
        src = as_record(src_raw)
        if src is not None:
            hay.append(json.dumps(src, ensure_ascii=False))
            string_leaves(src, hay)
        checked += 1
        if not any(quote in h for h in hay):
            fails.append((key, "quote not verbatim in source"))
        expect = hashlib.sha256((src_key + quote).encode("utf-8")).hexdigest()[:16]
        if key != "memcand/" + expect:
            warns.append((key, "key != content hash " + expect))
    for k, why in fails:
        print(stamp, "verify FAIL:", k, "—", why)
    for k, why in warns:
        print(stamp, "verify warn:", k, "—", why)
    print(stamp, f"verify: {checked} candidate(s) checked, "
                 f"{len(fails)} failed, {len(warns)} key warnings")
    return len(fails)


def source_plain(rec, snapshot):
    sk = rec.get("source_key", "")
    if sk.startswith("sms/"):
        digits = sk.split("/", 1)[1]
        thread = as_record(snapshot.get(sk)) or {}
        contact = as_record(snapshot.get("contact/" + digits)) or {}
        name = contact.get("name") or thread.get("name")
        return f"a text conversation with {name}" if name else "a text conversation"
    if sk.startswith("formsub/"):
        parts = sk.split("/")
        slug = parts[1] if len(parts) > 1 else "web"
        return f"their {slug} form submission"
    return "a conversation record"


def contact_name_for(rec, snapshot):
    ck = rec.get("contact_key", "")
    contact = as_record(snapshot.get(ck)) if ck else None
    if contact and contact.get("name"):
        return contact["name"]
    sk = rec.get("source_key", "")
    if sk.startswith("sms/"):
        thread = as_record(snapshot.get(sk)) or {}
        if thread.get("name"):
            return thread["name"]
    return "this customer"


def delete_candidate(tok, key):
    """DELETE the candidate and read back GET: gone (404 / null value) is
    the only success. Returns True only on a verified absence."""
    enc = urllib.parse.quote(key, safe="")
    path = f"/api/memory/agents/{SHARED}/kv/{enc}"
    req(tok, "DELETE", path)
    try:
        after = req(tok, "GET", path)
        return not (isinstance(after, dict) and after.get("value") is not None)
    except urllib.error.HTTPError as e:
        return e.code == 404


def note_text(rec):
    return f"{rec.get('field', 'fact')}: {rec.get('value', '')}"


def promote_candidate(tok, key, rec, stamp):
    """Approved: append ONE note to the contact and mark the candidate
    promoted. Done here in code, never by a model — the contact is read
    fresh, only notes[] grows, every other field is written back exactly as
    read. Idempotent: a note already carrying this candidate's key is not
    added twice. A missing contact leaves the candidate as it is (retried
    next cycle) — promotion never invents a contact."""
    ck = rec.get("contact_key", "")
    if not ck.startswith("contact/"):
        print(stamp, "memcarry: approved candidate has no contact_key:", key)
        return False
    path = f"/api/memory/agents/{SHARED}/kv/" + urllib.parse.quote(ck, safe="")
    try:
        raw = req(tok, "GET", path)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        raw = None
    raw = raw.get("value") if isinstance(raw, dict) else None
    contact = as_record(raw)
    if contact is None:
        print(stamp, "memcarry: approved, but no contact at", ck,
              "yet — candidate kept, will retry:", key)
        return False
    notes = contact.get("notes") if isinstance(contact.get("notes"), list) else []
    if not any(isinstance(n, dict) and n.get("from") == key for n in notes):
        notes.append({"ts": stamp, "text": note_text(rec), "from": key,
                      "quote": rec.get("quote", "")})
        contact["notes"] = notes
        kv_put(tok, ck, json.dumps(contact) if isinstance(raw, str) else contact)
        back = as_record((req(tok, "GET", path) or {}).get("value"))
        if not back or not any(isinstance(n, dict) and n.get("from") == key
                               for n in back.get("notes") or []):
            print(stamp, "memcarry: note read-back MISSING on", ck, "— will retry:", key)
            return False
    rec["status"] = "promoted"
    rec["promoted_into"] = ck
    rec["promoted_ts"] = stamp
    kv_put(tok, key, rec)
    print(stamp, "memcarry: promoted", key, "into", ck)
    return True


def memcarry_phase(tok):
    stamp = now_local().isoformat(timespec="seconds")
    snapshot = kv_snapshot(tok)
    ap_status, _ = approvals_map(tok)
    mem_id = agent_id(tok, "memory")
    if not mem_id:
        print(stamp, "memcarry: memory agent not found — nothing carried")
        return
    carried = deleted = woken = 0  # woken = promotions applied
    for key in sorted(snapshot):
        if not key.startswith("memcand/"):
            continue
        rec = as_record(snapshot[key])
        if rec is None:
            continue
        if rec.get("status") == "promoted":
            continue  # decided closure: a promoted candidate is final
        linked = ap_status.get(rec.get("approval_id", ""))
        if linked == "rejected":
            if delete_candidate(tok, key):
                deleted += 1
                print(stamp, "memcarry: rejected candidate deleted + verified:", key)
            else:
                print(stamp, "memcarry: DELETE read-back STILL PRESENT:", key)
            continue
        if linked == "approved":
            done = promote_candidate(tok, key, rec, stamp)
            if done:
                woken += 1
            continue
        if linked == "pending":
            if rec.get("status") == "candidate":
                rec["status"] = "in-needs-you"
                kv_put(tok, key, rec)
            continue
        # No live link — a fresh candidate, or an approval that expired
        # undecided (the 300 s TTL): (re-)carry it, like the drafts phase.
        if rec.get("status") not in ("candidate", "in-needs-you"):
            continue
        desc = (f"{note_text(rec)} — they said \u201c{rec.get('quote', '')}\u201d "
                f"in {source_plain(rec, snapshot)}")
        ap = req(tok, "POST", "/api/approvals",
                 {"agent_id": mem_id, "tool_name": "memory_candidate",
                  "description": desc,
                  "action_summary": "Remember this about "
                                    + contact_name_for(rec, snapshot)})
        rec["status"] = "in-needs-you"
        rec["approval_id"] = ap.get("id", "")
        kv_put(tok, key, rec)
        carried += 1
        print(stamp, "memcarry: candidate carried to Needs you:", key,
              "approval:", rec["approval_id"])
    print(stamp, f"memcarry: {carried} carried, {woken} promoted, "
                 f"{deleted} rejected+deleted")



def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "digest"
    try:
        tok = token()
        if phase == "digest":
            digest_phase(tok)
        elif phase == "memwake":
            memwake_phase(tok)
        elif phase == "verify":
            verify_phase(tok)
        elif phase == "memcarry":
            memcarry_phase(tok)
        else:
            print(datetime.datetime.now().isoformat(timespec="seconds"),
                  "sidecar-phases: unknown phase", phase)
    except Exception as e:
        # Never break pull-sync: log and exit clean; the next cycle retries.
        print(datetime.datetime.now().isoformat(timespec="seconds"),
              "sidecar-phases", phase, "FAILED:", repr(e)[:200])
    sys.exit(0)


if __name__ == "__main__":
    main()
