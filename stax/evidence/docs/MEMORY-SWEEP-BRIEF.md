# Memory Sweep — durable facts from real conversations, proposed never planted (2026-11-02)

Base: the live crew as deployed (7 hands Running; standing jobs = 19, or 20 if the Decider Shadow has landed — this brief adds exactly ONE job to whichever count is standing). Rulings source: the owner's PRIMITIVES RULING (2026-11-02 ~22:06 CST — Fang's own primitives only; no foreign memory stack, no second store, no new retrieval model) and the GO that followed it; the GROUNDING LAW; the staff-separation ruling (soft separation, best-fit routing, 2026-11-02 ~22:03 CST); DIRECTOR-ADDENDUM-DATA.md (the Round C contact shape this brief promotes into); RATCHET.md.

**This is a build spec for work starting now.** It ships in **two independently shippable phases**: **Phase 1 — the brief-input digest only** (the deterministic pass of Part 1 reduced to its digest duty, Part 4): no new hand, no new job, no model spend — the lowest-risk piece in either brief, and it closes a named defect, so it goes first and can land alone. **Phase 2 — transcript extraction into candidates** (Parts 1–3, 5–7 whole): the hand, the carrier, the promotion path. Phase 2 does not depend on Phase 1's code beyond sharing the one sidecar file, and Phase 1 is never blocked by Phase 2's gate.

**What this is:** a new hand, `memory`, running a sweep beside Forms and Texts. A deterministic pass finds conversations that changed; the hand reads them and proposes durable customer facts as **candidate records, each carrying the exact quoted span it was extracted from**. Candidates reach the owner as Needs-you items. Approval promotes a fact into the contact's record; rejection deletes the candidate. **Nothing promotes silently, and the hand never writes a contact, a thread, or a draft — candidates are its only output.** This adopts the *pattern* of the memory-writer systems the owner asked about (distill conversations into durable assets, promotion as a reviewed step) built entirely from Fang's primitives.

## PART 1 — Inputs, and the deterministic pass that names them

**Named correction to the commissioning assumption:** session transcripts are **not** an input in v1, because no Fang primitive can enumerate them — sessions live in the kernel's own tables and no hand tool reads them; a hand told to "review the sessions" would be told to find records it cannot address, which is the fabrication setup the grounding law forbids. V1 inputs are the two conversation families that live in kv with exact keys:

- `sms/<digits>` — thread records (bridge-maintained): `{number, name, thread_id, messages[{id, dir, body, ts, status}]}`
- `formsub/<slug>/<uuid>` — submission records with `"processed": true` (the `data{…}` answers are conversation too)

The enumeration pass is deterministic code, on the pull-sync pattern (new sibling file `sidecar-phases.py`, invoked at the end of pull-sync's run; master beside `pull-sync.sh`, box copy beside it in `~/openfang-play/`):

1. GET the full kv snapshot (the read the drafts phase already performs). For every `sms/` and qualifying `formsub/` key, sha256 the canonical record and compare against `memsweep/state` (the hash ledger, bridge-style). Changed or new keys are this cycle's work list.
2. Update the hashes **only for keys it names in a wake** (a failed wake retries next cycle, like pull-sync's ack discipline).
3. Wake the memory hand by POST `/api/agents/<memory>/message` naming the exact keys — the wake-poke pattern pull-sync already uses for Forms. A key not named in a wake is not processed; the hand stores nothing on a wake that names no keys.

## PART 2 — Extraction scope: customer facts, quoted or nothing

From each named record the hand extracts **only** durable customer facts in these classes:

- **piece** — what they want tattooed, in their words ("a fine-line horseshoe pair")
- **placement** — where on the body
- **preference** — style, artist, scheduling, communication preferences they stated
- **life** — facts relevant to the work they volunteered (occasion, memorial subject, constraints)
- **artist_fit** — signals bearing on best-fit routing (style asked for, artist named, prior work with an artist) — the staff-separation rule's feedstock

Each candidate is one fact, one record, keyed by a content hash so re-extraction overwrites instead of duplicating (`memcand/<first 16 of sha256(source_key + quote)>`):

```
memcand/<hash16> = {
  "status": "candidate",
  "contact_key": "contact/<email|phone-digits>",   // resolved by the hand from the source record (thread number / submission data), using the established index rule
  "field": "piece|placement|preference|life|artist_fit",
  "value": "<the fact, in the customer's own terms>",
  "quote": "<the exact span from the source record this was extracted from>",
  "source_key": "sms/<digits>", "source_msg": "<message id, for sms sources>",
  "ts": "<iso>"
}
```

**The quote is the grounding mechanism, not decoration.** A candidate whose quote does not appear verbatim in its source record is a fabrication by definition — Part 7's proof gate greps every one. If nothing in a record meets the scope, the hand stores nothing for it and says so; an empty sweep is a valid sweep.

Out of scope, named: anything the customer did not actually say in the record (no inferences about identity, health, or means); prices and availability (never facts for the cabinet, per standing law); other people's facts appearing in a thread (the candidate belongs to the thread's contact only).

## PART 3 — Needs-you, promotion, rejection

Candidates become decisions through the one door the owner already uses — the approvals path, carried deterministically the way pull-sync's drafts phase carries `draft/` records. `sidecar-phases.py` gains a carrier phase that mirrors the drafts phase's discipline exactly (approval-id stamping, `decided` closure in kv as the ledger of record, expired approvals re-carried, decided records never re-carried):

1. For each `memcand/` record with `"status": "candidate"` and no live approval: POST `/api/approvals` {agent: memory, tool_name: "memory_candidate", description: *"<field>: <value> — from <source in plain words>"*, action_summary: "Remember this about <name>"}; stamp `approval_id`, set status `in-needs-you`.
2. **On approval** — the carrier wakes the memory hand with the exact candidate key. The hand promotes: recall the contact record at `contact_key`, append ONE entry to its `notes[]` — `{"ts": "<iso>", "text": "<field>: <value>"}` — and store the whole record back (the established contact shape per the Addendum: `notes[{ts, text}]`, `artist`/`artists[]` and `temperature` carried untouched). Then set the candidate's status to `promoted` with `promoted_into: <contact_key>`. One promotion, once: a candidate already `promoted` is never re-applied (the carrier's decided-closure enforces it).
   - **`artist_fit` promotes as a note, never as an assignment.** It does not write `contact.artist` — attribution changes stay with the import's deterministic rule and the owner's word. The note is the evidence; a human or the lead moves the stamp.
   - If the contact record does not exist at promotion time, the hand stops, leaves the candidate `in-needs-you`, and reports the missing key — a promotion into a void is an invention.
3. **On rejection** — the candidate is deleted by the carrier via `DELETE /api/memory/agents/{id}/kv/{key}` (the Verdict 4 §2 route) and read back GET → 404, filed with the run's evidence. Deletion is a sidecar act because it must be: **hands hold only `memory_store` + `memory_recall`** — no agent in this system can delete, and this brief does not pretend otherwise.

## PART 4 — The joint seat: the brief-input digest

The same deterministic pass writes the digest that closes the Morning Brief's known blind spot (LOOP.md R13: the compose step cannot read the approvals queue, so the brief can claim "nothing waiting" while approvals pend; the named fix path was always "pull-sync writes a daily brief-input digest"). Each pull-sync cycle, `sidecar-phases.py` maintains:

```
briefinput/<yyyy-mm-dd> = {
  "date": "<local date>", "updated": "<iso>",
  "pending_approvals": <count of GET /api/approvals with status "pending">,
  "new_keys": {"formsub": [...], "sms": [...], "memcand": [...]},   // exact keys first seen since 06:00 local yesterday, capped at 50 per family with the count carried when capped
  "candidates_waiting": <count of memcand/ in candidate or in-needs-you state>
}
```

The only other change: the Morning Brief workflow's compose step (Stax) gains one line — recall `briefinput/<today>` exactly and ground the "what's waiting" lines in it, saying plainly when the key is missing instead of claiming calm. Workflow edit via the existing POST /api/workflows route; the brief job itself (06:00 America/Chicago, WorkflowRun by name) is untouched. The digest is a projection of the approvals API and the hash ledger — no model writes it.

## PART 5 — The hand

Masters at `hands/memory/HAND.toml` + `hands/memory/SKILL.md` (frontmatter: name, version, description, `runtime: prompt_only`), installed to `~/.openfang/hands/memory/` on the box, masters mirrored into the repo at the round's sync.

- **Tools:** `["memory_store", "memory_recall", "schedule_list"]` — the minimum. No `schedule_create` (standing law), no knowledge-graph tools (the graph is not the contact index), nothing else.
- **Model:** the same cheap fast model the Decider Shadow's Part 2 check selects (one measurement serves both seats; if this brief builds first, it runs that check itself under the same rules — 20 representative extraction prompts, TTFT + total + cost read back, Hy3's reported 30–90 s TTFT treated as a hypothesis to falsify).
- **Size rails in the agent config:** `temperature = 0.2`, `max_iterations = 20`, `max_tokens = 4096`.
- **Playbook, in substance** (written in the house voice of the forms/sms prompts): the wake discipline (named keys only; no keys named → report and store nothing); the recall order (source record → contact index if resolution is needed); the five field classes with one quoted example each; the quote rule stated as law (a fact you cannot quote does not exist); the outputs (candidates only — never a contact write, never a draft, never a send); promotion behavior on the approval wake (Part 3.2, verbatim discipline); the stop rule (never retry a blocked call with the same arguments).

**Job:** POST /api/cron/jobs — name **"Memory sweep"**, agent memory, expr `15 * * * *` (hourly, offset from the */15 intake sweeps), tz America/Chicago, message action carrying the standing instruction to await named keys. Armed by the parent via REST, as the brief job was — the hand never arms itself. **Standing job count rises by exactly one** (19 → 20, or 20 → 21 with the decider landed); recorded in the round report, the tripwire (Part 6), and the checklist below.

## PART 6 — Cadence and cost rails

- The sweep is **hourly**, not */15: memory does not decay in fifteen minutes, and the Forms/Texts cadence is intake urgency this work does not share.
- The wake names at most **10 source keys per run** (the pass defers the rest to the next cycle — the hash ledger makes deferral lossless).
- At most **20 candidates per run**; a record yielding more is reported by key for the director's eye, not mined deeper.
- Per-run spend is read back from the daemon's usage records into the run report (the Ratchet §5 discipline); a run whose cost exceeds the Forms sweep's median run cost is a case, filed and explained, before the next run is trusted.
- The carrier and digest phases are deterministic code: zero model spend by construction.

## PART 7 — The proof gate (Phase 2's first run, owner-inspectable; item 5 is Phase 1's proof and runs on Phase 1's clock)

1. **Named sources:** the first run processes the live thread records on the box at build time — the gate report names their exact keys (the census at drafting holds 3 `sms/` keys; the report names whichever exist when it runs, plus 2 processed `formsub/` records chosen by key in the report).
2. **Owner inspection:** every candidate from the first run is listed in the report — field, value, quote, source key — *before* any is carried to Needs-you. The owner reads what the machine thinks is worth remembering before it ever asks him to approve one.
3. **Fabrication check (mechanical, 100%):** a verification script in `sidecar-phases.py`'s test pass greps every candidate's `quote` against the raw JSON of its `source_key` record. **Every quote must match verbatim. One miss fails the run**, files a Ratchet case (quote, source key, candidate key), and no candidate from that run is carried until the case is re-run clean.
4. **Promotion proof:** with the owner's OK on one listed candidate, carry it, approve it, and read back: the contact's `notes[]` grew by exactly the one entry; the candidate reads `promoted`; reject a second candidate and read back its GET → 404. Exactly once, both directions.
5. **Brief proof:** the next 06:00 Morning Brief after the digest lands states the true pending-approval count (checked against GET /api/approvals at 06:05) — the R13 gap closes with a number, not a claim.

## Build order — two phases, activation last

**Phase 1 — the digest (ships alone).**
1. `sidecar-phases.py`, digest phase only (Part 4's writer, fed by the hash ledger from Part 1 step 1 — the enumeration machinery reduced to digest duty; the wake machinery is Phase 2's).
2. Staging: run the phase against a copied kv snapshot; read back `briefinput/<date>` — pending count matches a hand count of the snapshot's approvals state, new-keys lists match the ledger diff.
3. Deploy (parent step, **no daemon restart required** — pull-sync is a cron script; its new invocation takes effect on the next 5-minute cycle): sidecar file placed, pull-sync.sh gains the invocation line (`.bak` first).
4. The Morning Brief workflow's compose-step line (Part 4) is edited in the **activation window** below, and Part 7.5's brief proof runs at the next 06:00 after it.

**Phase 2 — extraction (builds immediately, activates in the window).**
1. Masters: `hands/memory/` (HAND.toml + SKILL.md) + the shared model check if the decider's Part 2 hasn't already produced a winner.
2. `sidecar-phases.py` additions: the wake/enumeration phase + the memcand carrier phase (Part 3) — one file, its phases independently logged.
3. Staging tests: the hand in a scratch HOME woken over copied thread/submission records; candidates read back against Part 2's shape; the fabrication grep (Part 7.3) run over them; a staging promotion + rejection walked end to end (notes append read back; candidate GET → 404).
4. **ACTIVATION — last, inside the Round A deploy's restart window** (shared with the Decider Shadow's activation — one restart serves all three): hand masters installed to the box, the "Memory sweep" job armed via REST, the tripwire extended (crew entry + job check in pull-sync phase 3) so a dead memory hand is a repair, not a silence. Standing job count rises by exactly one at this step and not before (19 → 20, or 20 → 21 with the decider activated first — the report records the standing count it actually changed). If the Round A window slips, activation slips with it rather than taking a second restart.
5. First live run under Part 7's gate; report filed with the full candidate list, the grep result, and both ledgers.

## Gate

- **Phase 1 gate (independent):** `briefinput/<today>` exists and its pending count equals a live GET /api/approvals count taken in the same cycle; its new-keys lists match the hash ledger; after the compose-step line lands, Part 7.5's brief proof passes. Non-regression for Phase 1 is the standing checklist unchanged — crew 7, jobs 19, no new job, no restart taken.
- **Phase 2 non-regression (the Ratchet checklist, re-run whole):** crew Running (7 standing, +memory and +decider per activation order); cron table = standing count +1 with Forms sweep / Texts sweep / Morning Brief **and Memory sweep** enabled; sweeps completing in the daemon log; approvals round-trip exactly once (a form draft and a memcand each, counted separately); brief readable and digest-grounded; pull-sync phases green incl. the new ones; port 3121 untouched; activation read-backs timestamped inside the Round A restart window (one restart serving all three activations, or the gate explains why not).
- **Grounding:** the fabrication grep at 100% (Part 7.3); a wake with no keys named produced zero candidates (staging or a controlled live poke); no `contact/` record on the box differs from its pre-round state except by the Part 7.4 promotion.
- **Candidate hygiene:** every live `memcand/` record carries quote + source_key; none is older than 7 days in `candidate` state without having been carried (the carrier's log shows why, or it's a case).
- **Size ledger (Ratchet §1):** before/after for pull-sync.sh (invocation lines only — growth beyond ~10 lines means the phase leaked into the wrong file and the build stops), sidecar-phases.py counted as a named addition shared with the Decider Shadow (one home for deterministic phases — it is not charged twice), hands/memory/ files at their created sizes. Trade named in advance: none claimed. The round report states the addition plainly and the director judges it — an unargued "net-negative" claim for a new capability would be exactly the bookkeeping this law exists to prevent. The capability's *operating* trade is real and stated instead: the digest retires the brief's false-calm failure mode, and the sweep's extractions replace extractions the specialists currently improvise inside their own, more expensive turns — measured in the run reports, not asserted here.

## Commits and conduct

- **Commits:** (1) the hand masters; (2) the sidecar phases + pull-sync invocation + tripwire extension; (3) the gate evidence (first-run report, candidate list, grep output, promotion/rejection read-backs) under the round's evidence home at sync time.
- **Primitives only.** The hand judges and proposes; deterministic code enumerates, carries, deletes, and digests. If a step seems to need a new route, a new tool, or a second store, it is reported as a machinery note, never built.
- **Build + stage, then the gate.** Deploy (box install + restart) is a parent step after the masters read clean, exactly as the other hand rounds ran.

## Open questions for the director

1. **Candidate expiry:** a candidate the owner neither approves nor rejects sits in Needs-you's 300-second approval TTL cycle, re-carried by design. Is a 14-day candidate expiry (carrier deletes unapproved candidates older than 14 days, counted in the digest) the right horizon, or should memory candidates persist until decided, unlike drafts?
2. **Digest window:** `new_keys` is defined since 06:00 yesterday (a brief-shaped day). If the memory sweep's candidates are meant to feed a *weekly* people-review later, does the digest need a 7-day rolling family too — or is that scope the Leads round's to ask for?
3. **Session transcripts, deferred not dropped:** if the owner later wants facts extracted from his *dashboard conversations* with Stax (not customer threads), the honest route is a sidecar that exports session records into kv under exact keys for this same pass. Worth queuing as a named follow-up, or is customer-conversation memory the whole of the owner's ask?
