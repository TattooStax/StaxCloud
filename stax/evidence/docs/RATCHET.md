# THE RATCHET — standing quality law for the Fang/StaxCloud build

Owner law (Shawn, 2026-11-02 ~19:18 CST): polish is not just UI. Polish = agent function. Vertical loops tested and proven; failure data collected and used to strengthen; code stays clean and easy for an agent to reason about. **Files can never get bigger — only smaller. Things can never get messier — only cleaner. Nothing regresses — only progress. Agent functions never get worse — only better.**

## How the ratchet is enforced on every builder round

1. **Size ledger.** Before a round starts, record the byte size of every file it will touch (statics first). The round's report carries before/after sizes. A touched file may shrink or stay; it may grow ONLY if the same round splits or deletes at least as much elsewhere, and the report names the trade. Untraded growth = gate failure.
2. **One home per thing.** No new destination, primitive, helper, or icon path without naming what it replaces and removing the old one in the same round. Duplicates found during a round are removed or explicitly dispositioned in the report — never left "for later" silently.
3. **Non-regression checklist.** Every deploy re-runs the standing functional checks, not just the round's new feature: crew 7 Running; cron table = 19 jobs with Forms sweep / Texts sweep / Morning Brief enabled; sweeps complete in the daemon log; approvals round-trip (draft → decide → outbox) with no duplicates; brief readable; pull-sync phases green; port 3121 untouched. A check that passed last round and fails now blocks the report of "done."
4. **Failure → data → fix → proof.** Every failure (failed turn, loop-guard block, fabrication, missed sweep, rendering defect) is written down as a case with its evidence. A fix is not done until the recorded case re-runs clean. The case list only shrinks by proof, never by forgetting.
5. **Agent-function quality is measured at the receiving end.** A hand's turn counts as good only when its effect reads back correctly where it acts (record stored, draft held, message delivered exactly once). Turn counts, token spend, and loop-guard hits per hand are part of the round report; a hand that got slower, loopier, or more expensive is a regression even if the UI improved.
6. **Director applies the ratchet to proposals.** Any plan that adds surface, files, or concepts must state its removals. "Also add" without "and remove" is rejected at review.

## Current size ledger (statics, as of Round 3 base 1f03d4b)
_To be filled by the next round's before-read; the ledger starts with that round and never resets._
