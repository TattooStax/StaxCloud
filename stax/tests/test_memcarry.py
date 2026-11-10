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
        self.approvals = approvals
        self.posted = []

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
            return {"id": f"ap{len(self.posted)}"}
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


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok", name)
    print(f"{n} passed")
