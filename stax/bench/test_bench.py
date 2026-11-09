"""Offline checks for the benchmark harness: scripted model replies, no network.

    python3 -m unittest stax/bench/test_bench.py
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402

CASES = {c["id"]: c for c in bench.load_cases(Path(bench.HERE / "cases.jsonl"))}


def scripted(*steps):
    """A fake OpenRouter: each step is a list of (tool, args) or a final string."""
    it = iter(steps)

    def fake_call(body, key, timeout=180):
        step = next(it)
        usage = {"cost": 0.0001, "prompt_tokens": 1000, "completion_tokens": 50}
        if isinstance(step, str):
            return {"choices": [{"message": {"content": step}}], "usage": usage}, 0.1
        tcs = [{"id": f"t{i}", "type": "function",
                "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(step)]
        return {"choices": [{"message": {"content": "", "tool_calls": tcs}}], "usage": usage}, 0.1
    return fake_call


def run(case_id, *steps):
    bench.call = scripted(*steps)
    case = CASES[case_id]
    r = bench.run_loop("fake/model", None, case, "k", 12)
    return bench.grade(case, r), r


BOOK = "https://squareup.com/appointments/book/L7VAHB1TPFGN2/start"
P = "7015550101"


class Grader(unittest.TestCase):
    def test_every_case_names_a_real_hand(self):
        for c in CASES.values():
            if c["role"] in ("image", "vision"):
                continue
            prompt, _ = bench.hand_prompt(c["hand"])
            self.assertTrue(prompt, c["id"])

    def test_booking_draft_with_link_passes(self):
        draft = {"kind": "sms_reply", "to": "+1" + P, "body": f"Hi Jane! You can grab a time here: {BOOK}",
                 "thread": f"sms/{P}", "status": "held"}
        fails, _ = run("texts-booking-ask",
                       [("memory_recall", {"key": "attention/sms"})],
                       [("memory_recall", {"key": f"sms/{P}"})],
                       [("memory_store", {"key": f"draft/sms-{P}-m3", "value": json.dumps(draft)})],
                       "Drafted a reply to Jane; it's waiting in Needs you.")
        self.assertEqual(fails, [])

    def test_availability_claim_fails(self):
        draft = {"body": f"We have an opening Tuesday! {BOOK}"}
        fails, _ = run("texts-booking-ask",
                       [("memory_store", {"key": f"draft/sms-{P}-m3", "value": json.dumps(draft)})],
                       "Done.")
        self.assertTrue(any("opening" in f for f in fails), fails)

    def test_price_quote_fails(self):
        fails, _ = run("texts-price-ask",
                       [("memory_store", {"key": f"draft/sms-{P}-m4", "value": json.dumps({"body": "Around $800 for that."})})],
                       "Done.")
        self.assertTrue(any("$" in f for f in fails), fails)

    def test_empty_sweep_storing_something_fails(self):
        fails, _ = run("texts-empty-sweep",
                       [("memory_store", {"key": "draft/sms-1-m1", "value": "{}"})], "Done.")
        self.assertTrue(fails)
        fails, _ = run("texts-empty-sweep", [("memory_recall", {"key": "attention/sms"})], "Nothing waiting.")
        self.assertEqual(fails, [])

    def test_decider_fields_graded(self):
        rec = {"decisions": {"scope": {"choice": "business", "confidence": 0.95},
                             "action": {"choice": "draft_reply", "confidence": 0.9},
                             "link": {"choice": "link", "confidence": 0.9}}}
        fails, _ = run("decide-booking",
                       [("memory_store", {"key": f"decide/sms-{P}-m3", "value": json.dumps(rec)})], "Decided 1.")
        self.assertEqual(fails, [])
        rec["decisions"]["link"]["choice"] = "no_link"
        fails, _ = run("decide-booking",
                       [("memory_store", {"key": f"decide/sms-{P}-m3", "value": json.dumps(rec)})], "Decided 1.")
        self.assertTrue(any("link.choice" in f for f in fails), fails)

    def test_memory_quote_must_be_verbatim(self):
        good = {"status": "candidate", "field": "preference", "value": "Saturdays only",
                "quote": "I can only come in on Saturdays btw."}
        bad = dict(good, quote="I can only do Saturdays")
        doc = "portrait forearm "
        fails, _ = run("memory-extract",
                       [("memory_store", {"key": "memcand/0123456789abcdef", "value": json.dumps(dict(good, value=doc + "Saturdays only"))})],
                       "Proposed 1.")
        self.assertEqual(fails, [])
        fails, _ = run("memory-extract",
                       [("memory_store", {"key": "memcand/0123456789abcdef", "value": json.dumps(dict(bad, value=doc))})],
                       "Proposed 1.")
        self.assertTrue(any("verbatim" in f for f in fails), fails)

    def test_routing_and_schedule_rules(self):
        fails, _ = run("stax-route-research",
                       [("agent_send", {"agent_id": "deep-work", "message": "research"})],
                       "Ink Spot Fargo 4.6, Northern Lights Tattoo 4.8, Red River Ink 4.3.")
        self.assertEqual(fails, [])
        fails, _ = run("stax-no-schedule", [("schedule_create", {"description": "x", "schedule": "*/15"})], "Done.")
        self.assertTrue(any("schedule_create" in f for f in fails), fails)

    def test_fake_store_matches_daemon_replies(self):
        s = bench.FakeStore({"a": {"x": 1}}, {}, {})
        self.assertEqual(s.run("memory_recall", {"key": "zz"}), "No value found for key 'zz'.")
        self.assertEqual(s.run("memory_store", {"key": "b", "value": "1"}), "Stored value under key 'b'.")


if __name__ == "__main__":
    unittest.main()
