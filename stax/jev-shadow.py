#!/usr/bin/env python3
# jev-shadow.py — the Jev leg of the Decider Shadow: MEASUREMENT ONLY.
#
# Jev (typesafe/jev-1.14, a System-1 decision model) does not speak
# chat-completions, so it cannot be a hand. This one file is its whole
# footprint: on pull-sync's cycle it finds native decide/sms-… records that
# lack a Jev counterpart, replays the same three decisions (scope / action /
# link) against the decisions endpoint, and writes decide/jev-sms-… records
# in the native shape so the weekly scorecard (sidecar-phases.py) can grade
# all contestants on the same joins. It is wired into no live path, read by
# nothing but the scorecard, and consults no agent. If Jev loses, delete
# this file and its ledger; the decide/jev-… records remain as evidence.
#
# Data path, stated plainly: a replay sends the same customer message text
# to OpenRouter that the crew's own turns already send there — no new
# recipient, no new data class. No other external call exists in this file
# (the daemon kv API on localhost is the only other endpoint).
#
# Cost: Jev spend never appears in the daemon's usage records, so each call
# appends one JSON line to jev-ledger.jsonl beside this file:
# {ts, key, inbound, tokens_in, cost_usd_computed, cost_basis, wording}.
# cost_usd_computed = tokens_in x list price — COMPUTED FROM LIST, not
# metered; the scorecard carries that flag through.
#
# Wording is measurement: the question texts below are constants, and
# WORDING_VERSION versions them. Changing any wording starts a new
# measurement series — bump the version, and every record carries it.
import sys, os, json, urllib.request, urllib.parse, urllib.error, datetime

API = "http://127.0.0.1:4200"
SHARED = "00000000-0000-4000-8000-000000000001"
ENDPOINT = "https://openrouter.ai/api/v1/systemone"
# The same surface answers at https://openrouter.ai/api/alpha/decisions;
# the request/response shapes are identical. If one path 404s at activation,
# switch this constant to the alias — nothing else changes.
MODEL = "typesafe/jev-1.14"
WORDING_VERSION = 1
LIST_PRICE_IN_PER_M = 0.042  # USD per 1M input tokens; output free (list, 2026-11-02)
LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "jev-ledger.jsonl")

QUESTIONS = {
    "scope": {
        "type": "choice",
        "instructions": "Is this conversation about the tattoo studio's "
                        "business, or is it personal?",
        "criteria": {
            "business": "About the studio: booking, designs, appointments, "
                        "prices, aftercare",
            "personal": "Personal in nature, not about the studio",
            "unsure": "Cannot be told from the messages",
        },
    },
    "action": {
        "type": "choice",
        "instructions": "Should the studio draft a reply to the latest "
                        "message, or hold it for the artist without drafting?",
        "criteria": {
            "draft_reply": "A reply can be drafted from what the customer "
                           "actually said",
            "hold_flag": "The ask needs an answer there is no grounded "
                         "source for: availability beyond the booking link, "
                         "prices, or anything committing the shop",
        },
    },
    "link": {
        "type": "noul",
        "instructions": "The reply to this message should carry the "
                        "studio's booking link.",
        "criteria": {
            "true": "They are asking to book or schedule",
            "false": "They are not asking to book or schedule",
        },
    },
}


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def token():
    # The daemon's kv API key — the same source pull-sync reads. Never printed.
    with open(os.path.expanduser("~/.openfang/config.toml")) as f:
        for line in f:
            if line.strip().startswith("api_key"):
                return line.split('"')[1]
    raise RuntimeError("api_key not found in config.toml")


def openrouter_key():
    # The daemon's own OpenRouter key: the environment first, then the env
    # file the daemon is started with. Read, never printed, never stored.
    k = os.environ.get("OPENROUTER_API_KEY")
    if k:
        return k.strip()
    for path in (os.path.expanduser("~/openfang-play/env"),
                 os.path.expanduser("~/.openfang/env")):
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENROUTER_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    raise RuntimeError("OPENROUTER_API_KEY not found in env or daemon env file")


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
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return None
    return v if isinstance(v, dict) else None


def kv_snapshot(tok):
    kv = req(tok, "GET", f"/api/memory/agents/{SHARED}/kv")
    pairs = kv.get("kv_pairs", []) if isinstance(kv, dict) else []
    return {p.get("key", ""): p.get("value") for p in pairs}


def kv_put(tok, key, value):
    enc = urllib.parse.quote(key, safe="")
    req(tok, "PUT", f"/api/memory/agents/{SHARED}/kv/{enc}", {"value": value})


# ── The replay: state and questions built by code, never by a model ────────

def build_state(thread_key, thread_rec, contact_exists):
    """Deterministic state from the same records the native hand recalled:
    the latest inbound body, the prior two messages for context, and whether
    a contact record exists. Returns (state, inbound_id) or (None, None)
    when the thread has no inbound message to decide."""
    msgs = [m for m in thread_rec.get("messages", []) if isinstance(m, dict)]
    inbound_idx = None
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].get("dir") == "in":
            inbound_idx = i
            break
    if inbound_idx is None:
        return None, None
    context = msgs[max(0, inbound_idx - 2):inbound_idx + 1]
    state = {
        "thread": thread_key,
        "contact_on_file": bool(contact_exists),
        "latest_inbound": msgs[inbound_idx].get("body", ""),
        "recent_messages": [{"dir": m.get("dir", ""),
                             "body": m.get("body", "")} for m in context],
    }
    return state, msgs[inbound_idx].get("id", "")


def build_request(state):
    return {"model": MODEL, "state": state, "questions": QUESTIONS}


def jev_call(key, request_body):
    data = json.dumps(request_body).encode()
    r = urllib.request.Request(ENDPOINT, data=data, method="POST")
    r.add_header("Authorization", "Bearer " + key)
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read())


def parse_response(resp):
    """Map the endpoint's answers onto the native record's decisions shape.
    A choice answer carries a probability per option; the record's
    confidence is the chosen option's probability. A noul (yes/no) answer
    carries no confidence field — its value IS P(yes), so the chosen side's
    probability is the value or its complement."""
    answers = resp.get("answers", {})
    decisions = {}
    for name in ("scope", "action"):
        a = answers.get(name, {})
        choice = a.get("choice", "")
        probs = a.get("probabilities", {}) or {}
        decisions[name] = {"choice": choice,
                           "confidence": float(probs.get(choice, 0.0))}
    link_a = answers.get("link", {})
    p_yes = float(link_a.get("noul", 0.0))
    decisions["link"] = {"choice": "link" if p_yes >= 0.5 else "no_link",
                         "confidence": p_yes if p_yes >= 0.5 else 1.0 - p_yes}
    usage = resp.get("usage", {}) if isinstance(resp.get("usage"), dict) else {}
    return decisions, int(usage.get("input_tokens", 0) or 0)


def make_record(native_rec, decisions):
    return {
        "thread": native_rec.get("thread", ""),
        "inbound_id": native_rec.get("inbound_id", ""),
        "ts": now_iso(),
        "model": MODEL,
        "shadow": True,
        "contestant": "jev",
        "jev": {"endpoint": "systemone", "wording": WORDING_VERSION},
        "decisions": decisions,
    }


def ledger_line(key, inbound_id, tokens_in):
    return {"ts": now_iso(), "key": key, "inbound": inbound_id,
            "tokens_in": tokens_in,
            "cost_usd_computed": round(tokens_in * LIST_PRICE_IN_PER_M / 1e6, 8),
            "cost_basis": "list", "wording": WORDING_VERSION}


def run_once():
    tok = token()
    snapshot = kv_snapshot(tok)
    done = skipped = 0
    for key in sorted(snapshot):
        if not key.startswith("decide/sms-"):
            continue
        native = as_record(snapshot[key])
        if native is None:
            continue
        jev_key = "decide/jev-" + key[len("decide/"):]
        if jev_key in snapshot:
            continue
        thread_key = native.get("thread", "")
        thread_rec = as_record(snapshot.get(thread_key))
        if thread_rec is None:
            print(now_iso(), "jev: thread record missing, skipped:", thread_key)
            skipped += 1
            continue
        digits = thread_key.split("/", 1)[1] if "/" in thread_key else ""
        state, inbound_id = build_state(
            thread_key, thread_rec, ("contact/" + digits) in snapshot)
        if state is None:
            print(now_iso(), "jev: no inbound in thread, skipped:", thread_key)
            skipped += 1
            continue
        try:
            resp = jev_call(openrouter_key(), build_request(state))
            decisions, tokens_in = parse_response(resp)
        except Exception as e:
            # A Jev outage reads as missing records, never as a crash loop:
            # the scorecard reports the parity gap and moves on.
            print(now_iso(), "jev: call failed for", key, repr(e)[:160])
            skipped += 1
            continue
        kv_put(tok, jev_key, make_record(native, decisions))
        with open(LEDGER, "a") as f:
            f.write(json.dumps(ledger_line(jev_key, inbound_id, tokens_in)) + "\n")
        done += 1
        print(now_iso(), "jev: decided", jev_key, f"tokens_in={tokens_in}")
    print(now_iso(), f"jev: cycle complete — {done} replayed, {skipped} skipped")


# ── Selftest: offline, stubbed transport, recorded response shape ─────────

def selftest():
    ok = True

    def check(label, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + label)
        ok = ok and bool(cond)

    thread = {"number": "7015550100", "name": "Test Person", "messages": [
        {"id": "m1", "dir": "in", "body": "Hi, do you do fine-line work?",
         "ts": "2026-11-02T10:00:00-06:00", "status": "received"},
        {"id": "m2", "dir": "out", "body": "We do — want the booking link?",
         "ts": "2026-11-02T10:05:00-06:00", "status": "sent"},
        {"id": "m3", "dir": "in", "body": "Yes please, can I book for Saturday?",
         "ts": "2026-11-02T10:06:00-06:00", "status": "received"},
    ]}
    state, inbound_id = build_state("sms/7015550100", thread, True)
    check("state picks the latest inbound", inbound_id == "m3")
    check("state carries prior two + inbound",
          len(state["recent_messages"]) == 3
          and state["latest_inbound"] == "Yes please, can I book for Saturday?")
    check("state flags the contact", state["contact_on_file"] is True)
    empty_state, empty_id = build_state(
        "sms/7015550100", {"messages": [{"id": "x", "dir": "out", "body": "hi"}]},
        False)
    check("no inbound -> no state", empty_state is None and empty_id is None)

    body = build_request(state)
    check("request shape: model + state + keyed questions",
          body["model"] == MODEL and body["state"] is state
          and set(body["questions"]) == {"scope", "action", "link"}
          and body["questions"]["link"]["type"] == "noul")

    stub = {"model": "typesafe/jev-1.14-20261101",
            "answers": {
                "scope": {"type": "choice", "choice": "business",
                          "probabilities": {"business": 0.82, "personal": 0.03,
                                            "unsure": 0.15},
                          "confidence": 0.82},
                "action": {"type": "choice", "choice": "draft_reply",
                           "probabilities": {"draft_reply": 0.77,
                                             "hold_flag": 0.23},
                           "confidence": 0.77},
                "link": {"type": "noul", "noul": 0.9}},
            "usage": {"input_tokens": 421, "output_tokens": 70,
                      "cost": 0.000017682},
            "provider": "TypeSafe"}
    decisions, tokens_in = parse_response(stub)
    check("choice mapping keeps chosen probability",
          decisions["scope"] == {"choice": "business", "confidence": 0.82}
          and decisions["action"] == {"choice": "draft_reply",
                                      "confidence": 0.77})
    check("noul mapping: >=0.5 is link at P(yes)",
          decisions["link"] == {"choice": "link", "confidence": 0.9})
    low = dict(stub)
    low["answers"] = dict(stub["answers"])
    low["answers"]["link"] = {"type": "noul", "noul": 0.2}
    d2, _ = parse_response(low)
    check("noul mapping: <0.5 is no_link at 1-P(yes)",
          d2["link"] == {"choice": "no_link", "confidence": 0.8})
    check("usage tokens read", tokens_in == 421)

    native = {"thread": "sms/7015550100", "inbound_id": "m3",
              "ts": "2026-11-02T10:09:00-06:00", "model": "native-slug",
              "shadow": True, "decisions": {}}
    rec = make_record(native, decisions)
    check("record shape joins the native key family",
          rec["thread"] == "sms/7015550100" and rec["inbound_id"] == "m3"
          and rec["contestant"] == "jev" and rec["shadow"] is True
          and rec["jev"] == {"endpoint": "systemone",
                             "wording": WORDING_VERSION})
    line = ledger_line("decide/jev-sms-7015550100-m3", "m3", 421)
    check("ledger cost = tokens x list price (421 -> 0.00001768)",
          abs(line["cost_usd_computed"] - 0.00001768) < 1e-9
          and line["cost_basis"] == "list")
    print("SELFTEST", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    try:
        run_once()
    except Exception as e:
        # Never break pull-sync: log and exit clean; the next cycle retries.
        print(now_iso(), "jev-shadow FAILED:", repr(e)[:200])
    sys.exit(0)


if __name__ == "__main__":
    main()
