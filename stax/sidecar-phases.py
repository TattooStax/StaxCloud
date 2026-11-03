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
import sys, os, json, hashlib, urllib.request, urllib.parse, datetime

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


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "digest"
    try:
        tok = token()
        if phase == "digest":
            digest_phase(tok)
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
