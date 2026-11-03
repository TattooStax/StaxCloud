# Activation Runbook — Decider Shadow + Memory Sweep Phase 2

Construction is done and staged. This runbook is the activation window's
checklist, in order — it executes inside the Round A deploy's daemon
restart, so the box takes ONE restart for all three (Round A + decider +
memory). If the Round A window slips, activation slips with it; never take
a second restart for these seats alone.

Standing counts this window moves: crew 7 → 9 Running; cron jobs 19 → 21
("Decider shadow", then "Memory sweep"). Sources: DECIDER-SHADOW-BRIEF.md,
MEMORY-SWEEP-BRIEF.md. Open questions listed at the ends of those briefs go
to the director — they are not the activation operator's to improvise.

## Step 1 — The model measurement (before anything is installed)

Both hands name their model from this ONE measurement (Decider brief
Part 2; the memory hand rides the same winner).

1. Verify candidate slugs against the live OpenRouter catalog. Candidates:
   `tencent/hy3`, `tencent/hunyuan-a13b-instruct`, plus one small fast tier
   from an incumbent family as the control.
2. Build 20 representative decision prompts from real thread records
   already on the box (bodies used locally in the harness, never quoted in
   any report) and 20 representative extraction prompts the same way.
3. Put each set to each candidate THROUGH THE DAEMON'S OWN CHAT PLUMBING
   (a throwaway agent config — not a side client). Record TTFT, total
   latency, and cost per call from the daemon's usage records.
4. Winner = the cheapest candidate whose p95 total latency is under 5 s
   across the twenty. If Hy3's reported 30–90 s TTFT reproduces, it is
   disqualified by the number and the case is filed.
5. File the measurement table in the round report. No table, no install.
6. Set the winner into BOTH masters — `hands/decider/HAND.toml` and
   `hands/memory/HAND.toml`, the `[agent] model` field, replacing
   `PART2-WINNER-SET-AT-ACTIVATION` — and confirm no placeholder remains
   anywhere (`grep -r PART2-WINNER hands/`).

## Step 2 — Place the files (box + masters)

1. Hands: copy `hands/decider/` → `~/.openfang/hands/decider/` and
   `hands/memory/` → `~/.openfang/hands/memory/` on the box.
2. Sidecar merge: merge `sidecar-phases-v2-staged.py` into the live
   `sidecar-phases.py` master per its MERGE-1…MERGE-4 comments (live
   helpers win; the four phases and their dispatch entries move over).
   Place the merged master on the box beside `pull-sync.sh`.
3. Jev leg: place `jev-shadow.py` beside `pull-sync.sh` on the box.
   Run `python3 jev-shadow.py --selftest` on the box first — it must pass
   offline before the file earns a cycle. Confirm the OpenRouter key
   source resolves on the box (daemon env file) WITHOUT printing it.
4. `pull-sync.sh`: `.bak` first, then add the invocation lines from
   MERGE-3 (memwake, verify, memcarry, scorecard, jev) immediately BEFORE
   the existing digest line. Growth beyond ~10 lines fails the Ratchet
   gate — stop and report instead of proceeding.

## Step 3 — The restart (the Round A window's one restart)

1. Restart the daemon by the established pattern (graceful stop, exact-PID
   discipline, env-sourced start).
2. Read back: `GET /api/agents` shows `decider` and `memory` alongside the
   standing crew; `GET /api/hands` (or each agent's manifest) shows each
   new hand's tools are exactly `memory_store`, `memory_recall`,
   `schedule_list` — no `schedule_create`, no `shell_exec`, nothing else.
3. Confirm the shell census from the security work still holds (crew
   shell-free; the restart-window blocklist application, if scheduled in
   this same window, is verified by its own census re-read).

## Step 4 — Arm the two jobs (parent, via REST — hands never arm themselves)

Read one existing sweep job from `GET /api/cron/jobs` and mirror its
action shape exactly, substituting agent, expr, and message:

1. **Decider shadow** — agent `decider`, expr `3,18,33,48 * * * *`,
   tz `America/Chicago` (three minutes behind the Texts sweep's
   quarter-hour, by design), message: the standing shadow instruction —
   recall `attention/sms`, decide the latest inbound of each named thread
   per the playbook, store `decide/` records only. Jobs: **19 → 20**.
2. **Memory sweep** — agent `memory`, expr `15 * * * *`,
   tz `America/Chicago`, message: the standing instruction to await named
   keys (process exactly the keys a wake names; a wake naming none is a
   report, not a task). Jobs: **20 → 21**.
3. Read the job table back: 21 jobs, Forms sweep / Texts sweep / Morning
   Brief / Decider shadow / Memory sweep all enabled.

## Step 5 — Extend the tripwire (pull-sync.sh phase 3)

1. CREW map gains `decider` and `memory` with their agent ids as read back
   in step 3 (copy from the tool output — never reconstruct an id).
2. Job checks gain `has_job("decider")` (its `3,18,33,48` expr) and a
   "Memory sweep" presence check, beside the existing sweep checks.
3. Next pull-sync cycle: phase 3 silent (healthy), `crew/health` clean.

## Step 6 — First runs, under the gates

1. **Scorecard staging proof** (before the first live Sunday boundary, or
   accepted from the first live week): run the scorecard phase over copied
   staging records; every disagreement key resolves (GET → 200); n equals
   the `decide/` census for the window; the record states its inference
   rule and both contestants' coverage parity. While here, pin the daemon
   usage route's live shape for `fetch_usage` and adjust that one helper
   if the build's shape differs.
2. **Memory first run — the Part 7 gate, in this order:**
   a. Let memwake name the live records (cap: 10 keys per wake, hand rail
      20 candidates per run — both already in the code/playbook; do not
      raise them for the first run).
   b. Run the `verify` phase. The candidate list — field, value, quote,
      source key for EVERY candidate — goes in the round report for the
      owner's inspection BEFORE anything is carried. One verbatim-quote
      miss fails the batch: file the Ratchet case, carry nothing from it,
      re-run clean.
   c. Only then let memcarry take candidates to Needs-you.
   d. Promotion proof, exactly once, both directions: with the owner's OK
      on one listed candidate — approve it, read back the contact's
      `notes[]` grew by exactly the one `{"ts", "text"}` entry and the
      candidate reads `promoted`; reject a second candidate and read back
      its GET → 404.
3. **Decider shadow discipline** (after one full day live): kv census
   shows `decide/` records and ZERO writes attributable to the decider
   outside `decide/` (draft / smsout / contact counts unchanged from the
   pre-round census, modulo the sweeps' own work); a wake with
   `attention/sms` absent produced zero `decide/` records and an honest
   report line.
4. **Jev leg:** the ledger shows its call count and token totals; kill
   the client once on staging and confirm the scorecard degrades to a
   parity note, never an error.

## Step 7 — Non-regression (the Ratchet checklist, re-run whole)

- Crew **9 Running** (7 standing + decider + memory).
- Cron table = **21**, canonical enabled set incl. Decider shadow +
  Memory sweep.
- Sweeps completing in the daemon log; approvals round-trip exactly once
  (a form draft and a memcand, counted separately).
- Morning Brief readable and digest-grounded; `briefinput/<today>`
  present.
- Pull-sync phases green incl. memwake / verify / memcarry / scorecard /
  tripwire's new checks; digest line unchanged in behavior.
- Port 3121 untouched; activation read-backs timestamped inside this one
  restart window.
- Size ledger filed: pull-sync.sh (invocation lines only), sidecar-phases.py
  and `hands/decider/` + `hands/memory/` + `jev-shadow.py` as named
  additions; the round removes nothing and says so.

## Rollback

- Shadow phase: disable the two jobs (`PUT /api/cron/jobs/{id}/enable`
  `{"enabled": false}`) — the system is bit-for-bit the system before
  this window; `decide/` and `memcand/` records remain as inert history.
- Jev leg: delete `jev-shadow.py` + its ledger and its pull-sync line.
- Any live rung later is reversed by removing the one playbook step from
  the sms master (its own read-back) plus the same job disable. The
  sweeps never depend on the shadow: a missing `decide/` record degrades
  them to exactly their current behavior.
