"""The carrier's promotion: approved memory candidates become ONE contact
note, in code, with every other contact field left exactly as it was.

    python3 stax/tests/test_memcarry.py
"""
import importlib.util
import json
import os
import urllib.error
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "phases", os.path.join(HERE, "..", "sidecar-phases.py"))
phases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phases)

PREFIX = f"/api/memory/agents/{phases.SHARED}/kv/"


class Store:
    """Just enough of the daemon: kv GET/PUT/DELETE, approvals, agents."""

    def __init__(self, kv, approvals):
        self.kv = dict(kv)
        self.approvals = dict(approvals)
        self.posted = []
        self.superseded = []
        self.wakes = []
        self.wake_error = None

    def req(self, tok, method, path, body=None, timeout=20):
        if path.startswith(PREFIX):
            key = urllib.parse.unquote(path[len(PREFIX):])
            if method == "GET":
                if key not in self.kv:
                    raise urllib.error.HTTPError(path, 404, "nf", {}, None)
                return {"value": self.kv[key]}
            if method == "DELETE":
                self.kv.pop(key, None)
                return {}
        if path == "/api/approvals" and method == "POST":
            self.posted.append(body)
            aid = f"ap{len(self.posted)}"
            self.approvals[aid] = "pending"
            return {"id": aid}
        if path.endswith("/supersede") and method == "POST":
            aid = path.split("/")[3]
            self.superseded.append(aid)
            self.approvals[aid] = "superseded"
            return {"decision": "superseded"}
        if path.startswith("/api/agents/") and path.endswith("/message"):
            self.wakes.append(body)
            if self.wake_error:
                raise urllib.error.HTTPError(path, self.wake_error, "boom", {}, None)
            return {"response": "ok"}
        raise AssertionError(f"unexpected {method} {path}")

    def kv_put(self, tok, key, value):
        self.kv[key] = value


def run(store):
    phases.req = store.req
    phases.kv_put = store.kv_put
    phases.kv_snapshot = lambda tok: dict(store.kv)
    phases.approvals_map = lambda tok: (store.approvals, [])
    phases.agent_id = lambda tok, name: "mem-1"
    phases.memcarry_phase("tok")


CONTACT = {"name": "Jane Ink", "artist": "Leni", "artists": ["Leni"],
           "temperature": "warm", "visits": 3,
           "notes": [{"ts": "2026-10-01T10:00:00", "text": "first visit"}]}


def cand(status="in-needs-you", approval="ap-yes", ck="contact/7015550101"):
    return {"status": status, "approval_id": approval, "contact_key": ck,
            "field": "placement", "value": "left forearm",
            "quote": "on my left forearm", "source_key": "sms/7015550101"}


def test_approved_candidate_becomes_one_note_and_nothing_else_changes():
    s = Store({"contact/7015550101": dict(CONTACT, notes=list(CONTACT["notes"])),
               "memcand/aaaa": cand()}, {"ap-yes": "approved"})
    run(s)
    c = s.kv["contact/7015550101"]
    assert len(c["notes"]) == 2, c["notes"]
    note = c["notes"][-1]
    assert note["text"] == "placement: left forearm"
    assert note["from"] == "memcand/aaaa" and note["quote"] == "on my left forearm"
    for f in ("name", "artist", "artists", "temperature", "visits"):
        assert c[f] == CONTACT[f], f
    m = s.kv["memcand/aaaa"]
    assert m["status"] == "promoted" and m["promoted_into"] == "contact/7015550101"
    # A second cycle changes nothing: a promoted candidate is final.
    run(s)
    assert len(s.kv["contact/7015550101"]["notes"]) == 2


def test_contact_stored_as_a_string_stays_a_string():
    s = Store({"contact/7015550101": json.dumps(CONTACT),
               "memcand/aaaa": cand()}, {"ap-yes": "approved"})
    run(s)
    raw = s.kv["contact/7015550101"]
    assert isinstance(raw, str)
    assert len(json.loads(raw)["notes"]) == 2


def test_missing_contact_keeps_the_candidate_for_later():
    s = Store({"memcand/aaaa": cand()}, {"ap-yes": "approved"})
    run(s)
    assert s.kv["memcand/aaaa"]["status"] == "in-needs-you"
    assert "contact/7015550101" not in s.kv


def test_rejected_candidate_is_deleted_and_fresh_one_is_carried():
    s = Store({"memcand/rej": cand(approval="ap-no"),
               "memcand/new": cand(status="candidate", approval="")},
              {"ap-no": "rejected"})
    run(s)
    assert "memcand/rej" not in s.kv
    assert s.kv["memcand/new"]["status"] == "in-needs-you"
    assert s.kv["memcand/new"]["approval_id"] == "ap1"
    assert s.posted[0]["tool_name"] == "memory_candidate"


def fresh(n, ts):
    c = cand(status="candidate", approval="")
    c["ts"] = ts
    c["quote"] = f"quote {n}"
    return c


def test_at_most_five_memory_facts_show_in_needs_you_oldest_first():
    kv = {"contact/7015550101": dict(CONTACT)}
    for i in range(8):
        kv[f"memcand/c{i}"] = fresh(i, f"2026-11-10T0{i}:00:00Z")
    s = Store(kv, {})
    run(s)
    assert len(s.posted) == 5
    shown = sorted(k for k, v in s.kv.items() if k.startswith("memcand/") and v.get("status") == "in-needs-you")
    assert shown == ["memcand/c0", "memcand/c1", "memcand/c2", "memcand/c3", "memcand/c4"], shown
    # Next cycle with nothing decided: nothing new is added.
    run(s)
    assert len(s.posted) == 5
    # The owner decides one: the next oldest takes its place.
    s.approvals[s.kv["memcand/c0"]["approval_id"]] = "rejected"
    run(s)
    assert "memcand/c0" not in s.kv
    assert s.kv["memcand/c5"]["status"] == "in-needs-you"
    assert len(s.posted) == 6


def test_an_old_backlog_is_pulled_back_to_five():
    kv = {"contact/7015550101": dict(CONTACT)}
    approvals = {}
    for i in range(7):
        c = cand(approval=f"old{i}")
        c["ts"] = f"2026-11-10T0{i}:00:00Z"
        kv[f"memcand/b{i}"] = c
        approvals[f"old{i}"] = "pending"
    s = Store(kv, approvals)
    run(s)
    assert sorted(s.superseded) == ["old5", "old6"], s.superseded
    assert s.kv["memcand/b6"]["status"] == "candidate" and "approval_id" not in s.kv["memcand/b6"]
    assert s.kv["memcand/b0"]["status"] == "in-needs-you"
    assert s.posted == []


def run_wake(store):
    phases.req = store.req
    phases.kv_put = store.kv_put
    phases.kv_snapshot = lambda tok: dict(store.kv)
    phases.agent_id = lambda tok, name: "mem-1"
    phases.memwake_phase("tok")


def thread(n):
    return {"number": f"+1701555{n:04d}", "messages": [{"id": "m1", "dir": "in", "body": f"hello {n}"}]}


def test_memwake_names_three_records_per_wake():
    s = Store({f"sms/701555{n:04d}": thread(n) for n in range(5)}, {})
    run_wake(s)
    assert len(s.wakes) == 1
    assert s.wakes[0]["message"].count("sms/") == 3
    run_wake(s)
    assert s.wakes[1]["message"].count("sms/") == 2, "the rest next cycle"
    run_wake(s)
    assert len(s.wakes) == 2, "nothing left"


def test_a_failing_wake_is_retried_once_then_set_aside():
    s = Store({"sms/7015550001": thread(1)}, {})
    s.wake_error = 500
    run_wake(s)
    assert len(s.wakes) == 1
    assert s.kv["memwake/state"]["entries"]["sms/7015550001"].get("pending")
    run_wake(s)
    assert len(s.wakes) == 2
    e = s.kv["memwake/state"]["entries"]["sms/7015550001"]
    assert e.get("set_aside") == "HTTP 500" and not e.get("pending")
    run_wake(s)
    assert len(s.wakes) == 2, "set aside: not woken again"
    # A new message gives it a fresh try.
    s.wake_error = None
    s.kv["sms/7015550001"]["messages"].append({"id": "m2", "dir": "in", "body": "one more"})
    run_wake(s)
    assert len(s.wakes) == 3
    assert "set_aside" not in s.kv["memwake/state"]["entries"]["sms/7015550001"]


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok", name)
    print(f"{n} passed")
