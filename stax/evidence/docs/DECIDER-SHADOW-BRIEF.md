# Decider Shadow — a Fang-native System-1 seat, proven before it acts (2026-11-02)

Base: the live crew as deployed (7 hands Running; standing jobs = 19). This brief adds ONE hand, ONE cron job, and one measurement-only sidecar client. It touches no statics, no kernel, no existing hand's behavior. **This is a build spec for work starting now, not a queued proposal:** definitions, scripts, the Jev client, and all staging tests proceed immediately; the single ACTIVATION step (box install + job arming + tripwire extension) comes LAST and rides the Round A deploy's scheduled daemon restart, so the box takes one restart, not two. Rulings source: the owner's PRIMITIVES RULING (2026-11-02 ~22:06 CST — Fang's own primitives only: hands, cron, kv families, approvals; the kernel's existing OpenRouter chat plumbing; no decisions-endpoint client, no foreign stack), the GO that followed it (~22:10 CST — "have the decision model prove and sharpen our system… the plan anyways"), the GROUNDING LAW, and RATCHET.md (which binds this build: size ledger, non-regression checklist, failure → case → fix → proof).

**What this is:** a new hand, `decider`, that watches the same Texts inputs the sms hand watches and writes down what it *would* decide — as records, never as actions. A deterministic scorecard compares its calls against what the Texts sweep actually did. The decider earns a live seat only through the promotion gate in Part 7, or it stays a measurement instrument forever. Shadow first is not caution theater: the System-1 category is seven weeks old with vendor-run benchmarks, and claims about it get tested here with numbers, not adopted on reputation.

**The shadow is a three-way measurement on the same real sweep calls:**
- **(a) The incumbent** — the Texts sweep's own judgments, as recorded in the drafts it wrote, held, or never wrote (Part 6's observed behavior), graded where verified outcomes exist (the owner's approval decisions and delivery read-backs on its drafts).
- **(b) The native decider** — the Fang hand of Part 3, on a cheap fast chat model through the kernel's existing plumbing (the primitives ruling's seat).
- **(c) Jev** — TypeSafe's decision model (`typesafe/jev-1.14`), reached through OpenRouter's decisions endpoint (Part 5). The owner has heard Jev "is a strong model and shrinks API usage significantly"; this shadow exists to find out whether that is true *on this shop's calls*. The Jev leg is **measurement-only**: a thin sidecar client replays the same typed inputs and records Jev's answers beside the others. It is wired into no live path, consulted by no agent, and deletable as one file.

## PART 1 — The seat: which decisions, typed how

The sms hand's recurring judgments, read from its master (`hands/sms/HAND.toml`) — these are the decisions the shadow scores:

| # | Decision | Typed output | Where the playbook makes it |
|---|---|---|---|
| D1 | **Scope** — is this thread the shop's business at all? | `choice: business \| personal \| unsure` + confidence 0–1 | "If a thread's latest message is personal in nature, leave it entirely alone… When unsure, hold and flag." |
| D2 | **Action** — draft a reply, or hold for the artist without drafting? | `choice: draft_reply \| hold_flag` + confidence | Drafting is the default for business; hold-and-flag when the ask needs an answer the agent has no grounded source for (availability beyond the link, prices, anything committing the shop). |
| D3 | **Link** — does the reply carry the booking link? | `choice: link \| no_link` + confidence | "If they ask to book, include the booking link — the only URL you may use." |

**Named correction to the commissioning assumption:** there is **no "script-eligible" decision in the Fang sms hand**, and this brief does not invent one. The Fang Texts pipeline drafts *everything* and holds it for the owner (HAND.toml: "You never send anything"); the owner's send-the-script ruling lives on the StaxCloud line, not in Fang. If a script-send path is ever built for Fang, it gets its own decision type then — designed against a real mechanism, not ahead of one.

Each shadow decision is ONE record, keyed deterministically so it joins 1:1 with the draft the sweep may write for the same inbound message:

```
decide/sms-<thread digits>-<inbound message id> = {
  "thread": "sms/<digits>", "inbound_id": "<message id>", "ts": "<iso>",
  "model": "<the model slug that decided>", "shadow": true,
  "decisions": {
    "scope":  {"choice": "business|personal|unsure", "confidence": 0.0},
    "action": {"choice": "draft_reply|hold_flag",   "confidence": 0.0},
    "link":   {"choice": "link|no_link",            "confidence": 0.0}
  }
}
```

## PART 2 — Measure the model, don't assume it (runs before the hand is built)

The research behind this seat carries a live caution: Tencent's Hy3 — the obvious cheap candidate, ~$0.08–0.13/M in on OpenRouter with a no-think mode — was measured by one reviewer at 30–90 s time-to-first-token through OpenRouter's upstream. A decider that takes a minute is not a decider. So the model's seat is earned by measurement:

1. Candidates (slugs verified against the live OpenRouter catalog at build time; candidates, not commitments): `tencent/hy3`, `tencent/hunyuan-a13b-instruct`, plus one small fast tier from an incumbent family as the control.
2. Twenty representative decision prompts, built from real thread records already on the box (bodies used locally in the test harness, never quoted in the report), put to each candidate *through the daemon's own chat plumbing* — a throwaway agent config, not a side client — recording TTFT, total latency, and cost per call from the daemon's usage records.
3. The winner is the cheapest candidate whose p95 total latency is under 5 s across the twenty. If Hy3's TTFT reproduces anywhere near the reported range, it is disqualified by the number, not by debate, and the case is filed.
4. The measurement table ships in the round report. No table, no hand — the shadow does not start on an assumed model.

## PART 3 — The hand

Masters at `hands/decider/HAND.toml` + `hands/decider/SKILL.md` (frontmatter: name, version, description, `runtime: prompt_only` — the house shape), installed to `~/.openfang/hands/decider/` on the box at deploy, masters mirrored into the repo at the round's sync, exactly as the other seven hands are kept.

- **Tools:** `["memory_store", "memory_recall", "schedule_list"]` — deliberately the minimum. No `schedule_create`: standing law (the stax and forms playbooks both carry it) is that standing schedules are managed outside the agents; the decider's job is armed by the parent via REST (Build order, step 6), and the hand never arms, re-arms, or backstops itself. No knowledge-graph tools: the graph is not the contact index and plays no part here.
- **Model:** Part 2's measured winner (below), set as `provider = "openrouter"`, `model = "<slug>"` in the `[agent]` table — the deep-work hand's pattern for naming a non-default model through the kernel's existing plumbing.
- **Size rails in the agent config:** `temperature = 0.1` (decisions, not prose), `max_iterations = 15`, `max_tokens = 4096`.
- **Playbook, in substance** (written in the house voice of the forms/sms system prompts): recall `attention/sms` first and nothing else until it answers; for each named thread recall the thread record, the contact index record, and any existing `decide/…` / `draft/…` key for the latest inbound before deciding; decide the *latest inbound message only*; store one record in the Part 1 shape; the grounding law verbatim (a missing record is stop-and-report; inventing a thread, sender, or message is the worst failure); the stop rule (never retry a blocked call with the same arguments); a closing report of how many threads were decided and how many skipped, in plain words.

## PART 4 — How the shadow receives the sweep's inputs

The bridge is the input surface, and its shapes are fixed (read from `bridge/bridge.py`):

- `attention/sms` = `{"threads": ["sms/<digits>", …], "updated": "<iso>"}` — every thread whose latest message is an unanswered inbound. Absent key = healthy empty state.
- `sms/<digits>` = `{"number", "name", "thread_id", "messages": [{"id", "dir", "body", "ts", "status"}]}`.
- `contact/<email|phone-digits>` — the shared index the sms hand resolves against; the decider recalls the same record for the same thread.

The decider's job fires on expr `3,18,33,48 * * * *` (three minutes behind the */15 Texts sweep's cadence, inside the same quarter-hour), tz America/Chicago. Three minutes behind is the design: the sweep has normally already acted, so most decisions are written against a settled outcome — but the shadow's record is keyed to the inbound message, not to the sweep's timing, so the scorecard (Part 6) derives the sweep's behavior from records, never from racing it. The decider reads the same index and the same threads the sweep saw; where the bridge mirrors a newer message between the two reads, the scorecard's join on inbound id keeps the comparison honest (an inbound the shadow decided that the sweep never saw is excluded, and counted as excluded).

**Write discipline (the shadow's whole law):** the decider writes `decide/` records and nothing else. It never writes `draft/`, `smsout/`, `contact/`, or `sms/`; it never messages another agent; it never creates an approval. There is no code path — prompt or otherwise — from a shadow decision to a customer.

## PART 5 — The Jev leg (measurement-only)

Jev does not speak chat-completions; it answers typed questions over OpenRouter's decisions endpoint — `POST https://openrouter.ai/api/v1/systemone` (alias `/api/alpha/decisions`) — taking a state plus `choice` / `score` / yes-no questions and returning probabilities, generating no text. That is exactly why it cannot be a hand — and exactly why its shadow leg is a client, not an agent.

- **The client** is one file, `jev-shadow.py`, beside `sidecar-phases.py` (master here, box copy in `~/openfang-play/`). It runs on pull-sync's cycle, after the native decider's quarter-hour tick, and for every `decide/` record the native hand wrote that lacks a Jev counterpart, it replays the same decision:
  1. **State, built deterministically from the same records the hand recalled:** the thread's latest inbound body, the prior two messages for context, and whether a contact record exists — assembled by code from the kv snapshot, never by a model.
  2. **Questions, one per decision type:** D1 scope as a `choice` among business/personal/unsure; D2 action as a `choice` between draft_reply/hold_flag; D3 as a yes-no (link / no link). The question wordings are constants in the client, versioned in its header — a wording change is a new measurement series, and the record carries the wording version.
  3. **The record:** `decide/jev-sms-<digits>-<inbound id>` — the native record's shape with `"contestant": "jev"`, probabilities mapped into the same `confidence` fields (the chosen option's probability), plus `"jev": {"endpoint": "systemone", "wording": <v>}`. Same join key, same scorecard.
- **Credentials and cost:** the client uses the OpenRouter key the box already holds for the daemon (read the same way pull-sync reads its config; never printed, never committed). Jev spend does not appear in the daemon's usage records, so the client keeps its own ledger line per call (tokens in, per the endpoint's response) appended to its log; the scorecard computes Jev's cost per decision from the published list price ($0.042/M input, output free — flagged in the scorecard as *computed from list*, not metered).
- **Data path, stated plainly:** replay sends the same customer message text to OpenRouter that the crew's own turns already send there — no new recipient, no new data class. No other external call exists in this leg.
- **Retirement is a feature:** if Jev loses, `jev-shadow.py` is deleted and its `decide/jev-…` records remain as the research evidence. One file, one family — nothing else in the system ever knew it existed.

## PART 6 — The scorecard (deterministic; a sidecar phase, not an agent)

Comparison is bookkeeping, and bookkeeping in this system is deterministic code. It lives in **one new file, `sidecar-phases.py`**, beside `pull-sync.sh` (master in this directory; box copy in `~/openfang-play/`), invoked once per pull-sync run, doing its work only on its weekly boundary. Justification for the placement, since the alternative was a pull-sync phase: pull-sync.sh is already the system's long pole (three embedded Python phases + the shell pull); the Ratchet's one-home rule is served by one *sibling* home for deterministic phases rather than a fourth heredoc — and the Memory Sweep's carrier phase lands in the same file for the same reason. pull-sync.sh itself grows by only the invocation lines.

Weekly (Sunday, first pull-sync run after 18:00 America/Chicago), the scorecard:

1. Enumerates `decide/` records from the trailing 7 days — both contestants' families, `decide/sms-…` (native) and `decide/jev-…` (Jev) — (kv snapshot read — the same GET the drafts phase uses; agents never enumerate, this code may). Coverage parity is computed first: inbound ids decided by one contestant but not the other are listed, and a contestant under 95% parity is reported as *incompletely measured* for that window, not graded on a partial field.
2. For each, derives the sweep's **observed behavior** from records, for the same inbound id:
   - a `draft/sms-<digits>-<inbound id>` exists → the sweep drafted; the draft's body is checked for the booking link (D3's ground truth); the draft's later state (`decided`, its approval outcome, any `smsout/` record and its delivery read-back) is the outcome trail.
   - no draft, and the thread has since gained an outbound message → answered outside the draft path (owner's own hand in StaxCloud) — scored as *drafted-equivalent* for D1/D2, excluded from D3.
   - no draft and no outbound after a 24 h settle window → the sweep left it alone.
3. Grades **verified outcomes** wherever the record carries them, for all three contestants at once: a held draft the owner approved (and the bridge delivered) verifies the incumbent's draft decision as *right*; a rejected draft marks it *wrong*; an expired-undecided draft scores as *unverified* and is excluded from outcome rates. Each challenger is graded two ways — agreement with observed incumbent behavior, and agreement with these verified outcomes where they exist — because beating the incumbent at imitating itself is not the prize; matching what the owner actually decided is.
4. Writes ONE record, `decide/scorecard-<yyyy-mm-dd>`: **per contestant** — per-decision-type n, behavior-agreement count and rate, outcome-agreement count and rate, agreement split by confidence buckets (<0.7 / 0.7–0.9 / ≥0.9), median + p95 decision latency, and **cost per decision** (native: from the daemon's usage records; Jev: from the client ledger, flagged computed-from-list); and **every disagreement listed as exact key pairs** (`decide/…` vs `draft/…` or the thread key) — the review surface is the list itself, readable by the lead or the director without tooling.
4. Logs one line per run to pull-sync.log; files nothing else. No model is consulted by the scorecard, ever.

**Honest limit, stated in the brief so the gate doesn't overclaim:** the sweep does not record its D1 reasoning — scope ground truth is *inferred* from behavior (drafted ⇒ treated as business; left alone past the settle window ⇒ treated as personal/unsuitable). A left-alone business thread the sweep simply missed scores as a decider "disagreement" — which is the useful direction for the error to fall, since those keys are exactly the ones a human should eyeball. The scorecard reports this inference rule inside the record itself.

## PART 7 — The promotion gate, and the rollback

A challenger earns the **first live seat** when ALL of these hold, read from the scorecard records (not from anyone's impression). The seat goes to whichever challenger clears them — the native hand, or Jev in the primitives ruling's named exception: *the native seat proved the value, and the scorecard is the measured gap*. If neither clears them, the incumbent keeps its seat and the shadow files that result — a measured "no" is a deliverable, not a failure:

- **Volume:** ≥ 100 scored inbound messages across ≥ 3 weekly scorecards.
- **D1 + D2 agreement ≥ 95%** overall, and **≥ 98% in the ≥0.9 confidence bucket** — the bucket is what goes live, so the bucket is what must be near-clean.
- **Zero dangerous disagreements** in the final two scorecards: a dangerous disagreement is the decider at confidence ≥0.9 saying `draft_reply` where observed behavior was *left alone on a personal thread* (the 831-line failure shape — a shop reply drafted into a personal conversation). One occurrence resets the count.
- **Cost proof:** the challenger's cost per decision over the window is ≤ 10% of the incumbent's per-decision cost (the sms hand's sweep spend ÷ its scored decisions) — the seat exists to save inference; if it doesn't, it doesn't promote. On this test the owner's Jev claim ("shrinks API usage significantly") is graded with the same numbers as everything else.
- **Head-to-head:** where both challengers clear the bars above, the seat goes to the higher outcome-agreement; a tie goes to the native hand (the primitives ruling prefers the seat with no new endpoint, all else equal).

**The first live seat, exactly one rung (native winner):** the sms hand's playbook gains one step — before drafting, recall the `decide/…` record for the inbound; where it says `scope: personal` at confidence ≥0.9, the sweep skips drafting and notes the skip in its report. Nothing else changes: business drafting, hold-for-flag, approvals, and the bridge gate all run as before. Further rungs (D2/D3 going live) are separate director calls on later scorecards, not momentum from this one.

**If Jev wins — the live wiring, sketched now so the exception is never improvised later:** the client stays exactly where it is — sidecar-resident, one file, outside the kernel and outside every hand. What changes is its cadence and its reader: `jev-shadow.py` (renamed `jev-live.py` at promotion, so the file's name never lies about its job) runs on the bridge's rhythm instead of the shadow's, writing its `decide/jev-…` records within a minute of a thread's mirror landing; the sms hand's new playbook step recalls the Jev record by the same key discipline as the native rung. The kernel learns nothing new; no hand gains a tool; the endpoint is spoken by exactly one audited file. Kill switch: stop the client and delete the playbook step — the sweep degrades to incumbent behavior on the next tick, and the shadow's records remain as the evidence that justified the seat. A Jev outage reads as missing records, and missing records read as the incumbent deciding alone — never as a blocked sweep.

**Rollback, both phases:** shadow phase — disable the one cron job (PUT enable `{"enabled": false}`) and the system is bit-for-bit the system before this brief; the `decide/` records remain as inert history. Live-rung phase — the same disable, plus the one playbook step comes out of the sms master (a one-line revert with its own read-back). **The sweep never depends on the shadow:** a missing `decide/` record at any point degrades the sms hand to exactly its current behavior.

## Build order — construction now, activation last

Everything through step 5 proceeds **immediately**; nothing here waits for a slot.

1. Part 2 measurement (native model); winner recorded in the report draft.
2. Masters: `hands/decider/HAND.toml` + `hands/decider/SKILL.md`.
3. `sidecar-phases.py` (scorecard phase) + `jev-shadow.py` (Part 5) + pull-sync.sh invocation lines + the tripwire extension (step 6) drafted.
4. Staging tests, all against staging/simulated inputs: the hand in a scratch HOME beside a staging daemon, woken over copied thread records, its `decide/` records read back against the Part 1 shape; the Jev client replaying the same copied inputs (its records shape-checked, its ledger line verified); the scorecard run over the staging records, its disagreement keys all resolving.
5. Found/fixed + found-not-fixed lists from staging, filed with the round evidence.
6. **ACTIVATION — last, and inside the Round A deploy's restart window.** When Round A deploys and the daemon restarts, the same window carries: hand masters installed to the box, daemon comes up on the new hand with the rest of the crew, the "Decider shadow" job armed via POST /api/cron/jobs, the Jev client + sidecar phases placed beside pull-sync, and pull-sync **phase 3's tripwire extended** — the CREW map gains `decider`, and a `has_job("decider")` check joins the sweep checks, so a crew-kill that takes the decider (or its job) is repaired like the others instead of failing silent. Standing job count: **19 → 20, named "Decider shadow"** — the new standing count for every checklist from this round on. One restart serves both rounds; if the Round A window slips, activation slips with it rather than taking a second restart of its own — the shadow's evidence clock starts at activation, not at construction.
7. First weekly scorecard read at its boundary; promotion clock starts.

## Gate

- **Non-regression (the Ratchet checklist, re-run whole):** crew Running — 7 standing + decider = 8; cron table = **20** with Forms sweep / Texts sweep / Morning Brief **and Decider shadow** enabled; sweeps completing in the daemon log; approvals round-trip exactly once; brief readable; pull-sync phases green (incl. the tripwire's new check reporting healthy); port 3121 untouched.
- **Shadow discipline:** after one full day live, the kv census shows `decide/` records and **zero** writes attributable to the decider outside `decide/` (draft count, smsout count, and contact count unchanged from the pre-round census, modulo the sweeps' own work); a wake with `attention/sms` absent produces zero `decide/` records and an honest report line.
- **Measurement filed:** the Part 2 table (candidates, p50/p95 latency, cost per decision) is in the round report; the hand's model matches the winner.
- **Scorecard proof (staging or first live week, whichever the director accepts):** a scorecard record exists whose disagreement list keys all resolve (GET each → 200), whose n equals the `decide/` census for its window, whose inference rule is stated inside it, and which carries **both contestants'** lines with coverage parity stated.
- **Jev leg, measurement-only proven:** during shadow, no playbook, workflow, or sidecar phase reads `decide/jev-…` records except the scorecard (grep of the masters + sidecar files filed); the client's ledger shows its call count and token totals; a killed client (staging) degrades the scorecard to a parity note, never to an error that blocks the native leg.
- **Activation discipline:** the activation read-backs (crew 8 Running incl. decider, job 20 present and enabled, tripwire healthy) are timestamped inside the Round A deploy's restart window — one daemon restart in the box log serves both rounds, or the gate explains why not.
- **Size ledger (Ratchet §1):** before/after for every touched file — pull-sync.sh (invocation lines only; growth beyond ~10 lines fails this gate and means the phase leaked into the wrong file), `sidecar-phases.py` and `hands/decider/` as named additions. Their trade, stated now rather than discovered later: this round **removes nothing**, and says so. The removals this capability exists to earn are booked at promotion (the sms playbook's duplicate classification prose is what a live decider replaces); a shadow that never promotes files its own retirement instead (Part 7's rollback + record cleanup), so the addition is never silently permanent.

## Commits and conduct

- **Commits:** (1) the Part 2 measurement record + hand masters; (2) sidecar-phases.py + pull-sync invocation + tripwire extension; (3) the gate evidence at sync time. Plain messages, no squash.
- **Primitives only.** The decider is a hand; the scorecard is deterministic code beside the existing sidecar; the gate is the approvals path that already exists. If a step seems to need a new endpoint, a new tool for the hand, or a kernel change, it stops and is reported as a machinery note — never built.
- **Build + stage only in the builder's lane.** Deploy, job-arming, and the tripwire edit land as the parent's deploy step, as every hand round before this one ran.

## Open questions for the director

1. **Scorecard cadence vs. patience:** weekly scorecards put the earliest possible promotion ~3 weeks out at current text volume (and the ≥100-scored floor may bind longer than the calendar). Is that the intended proof horizon for a seat this small, or should the first scorecard run at 50 scored with the promotion floor unchanged?
2. **The excluded middle:** threads answered by the owner's own hand in StaxCloud are scored drafted-equivalent for D1/D2. If their share grows, the shadow is increasingly graded against the owner rather than the sweep — is there a share (say >25%) at which the scorecard should report the window as unrepresentative instead of reporting a rate?
3. **Jev's D2 shape:** D2 (draft vs hold-for-the-artist) is the decision most entangled with shop commitments; as a bare `choice` question Jev answers it without the reasoning the sweep would give. Should Jev's shadow be scored on all three decision types as briefed, or restricted to D1 + D3 — the two that are pure classification — with D2 graded only for the native hand?
4. **Bucket threshold:** the live rung keys on confidence ≥0.9. The scorecard reports the 0.7–0.9 bucket separately precisely so this can be tuned — should the *first* live rung start at ≥0.95 for its first scorecard cycle and relax to 0.9 on evidence, or is one threshold, cleanly kept, worth more than the extra caution?
