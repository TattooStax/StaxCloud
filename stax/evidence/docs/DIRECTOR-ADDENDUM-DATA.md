# Director Addendum — the StaxCloud → Fang data migration map

Ruling on DATA-MIGRATION-MAP.md (2026-11-02), against DIRECTOR-VERDICT-4.md
and RATCHET.md. Ruling only — nothing here builds, moves, or deletes. The
map's census and mechanics (§§0–3, 5–9) are adopted as the evidence base;
the rulings below settle its §12 questions and the two items the map left
blocking. Where a ruling amends Verdict 4, it says so.

## 1. THE TEN QUESTIONS

**Q1 — Projects home. ADOPT the `project/` family**, keyed
`project/<contact-key>/<source-id>`, record carried whole as mapped (§4.4).
57 active projects are the shop's live work book; burying them in a contact's
`notes[]` would make the shop's most important list unfindable, and the
`projects[]`-on-contact fallback is rejected for the same reason. The
family's surface fate is ruled in §4 of this addendum.

**Q2 — Appointments. ADOPT the fold-in.** The 18 client-linked appointments
append one history entry each to their contact's `notes[]` in the mapped
format. The 4 unlinked appointments are counted in the import report and
not imported — no honest home exists and none is invented. No appointments
primitive is built; Square owns booking, by standing law.

**Q3 — Records docs. ADOPT the `note/` family now**, 1:1 as mapped (§4.6),
folder carried as a name string. Data homes precede surfaces; whether a
Records surface later reads `note/` is a UX-round question, not a reason to
leave 21 real documents homeless.

**Q4 — Lead vocabulary. RULED in §2 below** (the blocking item).

**Q5 — Cross-scope attribution. ADOPT `artist` + `artists[]`.** Three real
people are clients of both artists; a single-artist field would falsify
them. `artist` = the scope with the later `last_interaction`; `artists[]`
present only when both scopes claim the person.

**Q6 — Binaries. ADOPT phase 2.** Metadata + sha256 land with the import;
the bytes (28 attachment-bearing submissions in A scope, B scope counted by
the translator; 7 studio asset binaries) are a **separate counted pass**
after the Round C gate (§3), hash-verified per file against the sha256s the
import already stored. Bytes never land inside kv records — the phase-2
pass stores files and writes the file reference onto the record. The pass
does not block Rounds D–F.

**Q7 — Form slugs. ADOPT name-slug with `-<first 8 of source id>` suffix on
collision.** Slugs are owner-visible (URLs, the Forms list); the source id
rides inside the record for stability. One named consequence: if a source
form slugifies onto a key Fang already holds with different content — the
live `form/contact` is the case to check — the suffix rule fires and the
live record is never overwritten. The translator reports every suffixed
slug in the run report.

**Q8 — Evidence bundles. ADOPT sha-only carry.** `evidence_state` +
`evidence_sha256` migrate; the bundles do not. StaxCloud remains the
evidence archive until its retirement is separately decided — and that
retirement is already the owner's gate under the standing production rule
(StaxCloud stays authoritative until parity is proven), so no new decision
is created here. No `evidence/` family is built.

**Q9 — Named exclusions. ADOPT.** The root-locked agent-side families stay
out of scope by design (the fork's crew builds its own memory), and the 2
unpublished site-page drafts do not translate. No owner-run export is
commissioned. The single exception stands: `cs_knowledge` is eyeballed at
translator build time; if it holds shop-facing Q&A copy, that copy — and
only that copy — is reported to the director before the import runs, as a
candidate for a content carry. It does not silently join the import.

**Q10 — Sequencing. ADOPT with one amendment** — ruled in §3 below.

## 2. THE BLOCKING ITEM — temperature mapping and stage derivation

Verdict 4's vocabulary stands unchanged: stages **New · Talking · Waiting
on an artist · Booked · Resting** (+ Not a fit); temperatures **Ready ·
Interested · Just looking**. StaxCloud's `lead_status` does **not** map
one-to-one onto it, and this addendum rules what happens to the signal
instead of pretending it does:

**Temperature mapping (deterministic, at import):**
- `hot` (1 record) → **Interested**.
- `cold` (165 records) → **Just looking**.
- **Ready is never inherited.** Ready means "act today" in Verdict 4's
  response plan; no historical field earns it. It is earned by live
  behavior on the fork only.

**The source field does not survive as a live field.** The imported contact
carries Verdict 4's `temperature` at top level. The source `lead_status`
value is preserved **inside the `staxcloud` provenance block only**
(`staxcloud.lead_status`) — an audit trail, not a second vocabulary living
on the record. One vocabulary per surface, per the Ratchet's one-home rule;
the map's §4.1 target shape is amended accordingly (its top-level
`★lead_status` becomes `temperature`, derived as above).

**Stage derivation (deterministic, at import).** Every imported contact
lands in exactly one stage, by this precedence — first matching rule wins:

1. **Booked** — the contact holds a project with status `active` or
   `in_progress` (57 people). A live project is work underway; it outranks
   every recency test.
2. **Resting** — no active project, and `last_interaction` is 90+ days
   before the import date. The historical book goes to rest honestly
   instead of flooding Talking with people nobody has heard from since
   spring.
3. **Talking** — has ≥1 form submission on file, or `source = booking`,
   and interacted within 90 days. A real exchange happened and is recent.
4. **New** — everything else (manual/inquiry rows with no submission).
5. **Not a fit** is **never** assigned by import. It is a human judgment
   (owner or agent-proposed through Needs-you), not a derivation.

Imported contacts **never** land in **Waiting on an artist** — nothing in
the source records an outstanding artist obligation, and inventing one
would mint Needs-you noise from history.

**Who classifies: the deterministic rule, run by the translator — not a
crew pass.** 163 records classified by an LLM turn-chain would be
unauditable and non-reproducible; this rule re-runs to the same answer
from the same source fields, and the import report states the per-stage
counts it produced. Crew-proposed classification governs live-born records
after import, under Verdict 4's birth/movement rules — unchanged. The
imported book is treated as already-born (map §11.1): the pipeline's first
run over it is rendering + the scripted moves, never a birth pass.

**Rider — the card's "piece idea" for imported records** (map §11.5,
required to complete Verdict 4's card spec on real data), first match
wins: (a) the active project's title; (b) the newest submission's
idea/placement/description answers, where the form collected them;
(c) blank — the card shows last contact and next action only. An idea is
never synthesized from notes text.

## 3. SEQUENCING — the import inside Round C

**Verdict 4's A–F order is unchanged.** The import slots inside **Round C**
as its second half, with the internal order fixed as:

0. **Cleanup** (Verdict 4 §2, unchanged — deletions + read-backs filed first);
1. **Import** — the translator run, including the §2 derivation written at
   import time, the manifest written to `migration/staxcloud-<date>`, and
   the map §10 read-backs (per-family counts, hash coverage, second run =
   0 writes);
2. **Pipeline build** — the Leads surface (stages, temperatures, cards,
   counts strip, accordions, All · Shawn · Leni filter) built against the
   real book, not the test set;
3. **Gate on the real book** — Verdict 4's Round C gate, extended: counts
   strip totals equal the kv census; the artist filter splits match the
   map §5 per-artist counts (the lopsided 143/23 book is the truth, and
   the counts strip showing per-artist counts is what keeps it from
   reading as missing data); no card shows a raw id or a test record.

What this displaces: **nothing.** Round 3 finishes untouched; the security
fixes precede Round A as already ordered; Rounds A and B run as ruled;
D–F keep their slots, with the Q6 bytes pass running after the Round C
gate as a parent data operation that blocks none of them. The import is a
**parent (Stax) data operation** — like the cleanup, it is not builder work
and not an agent turn; the builder's Round C scope is the pipeline surface
only, now specced against §2 and the rider.

One binding companion requirement (map §4.3/§10.5): imported submissions
carry `processed: true` and `source: "staxcloud-import"`, and the Forms
sweep's birth pass must treat that marker as already-triaged — the sweep
minting drafts for 242 historical submissions is an import failure, and
the Round C gate proves zero minted.

## 4. THE PROJECTS FAMILY — home ruled, surface deferred

The `project/` family is the data home (Q1). **No Projects surface is
built in the A–F sequence.** Projects reach the owner through what already
exists: the Leads card (active project title as the piece idea, §2 rider;
a project is what puts a lead in Booked) and, after import, an
agent-composed Library shelf entry is permitted — Library's Verdict 4
definition ("what the shop keeps… client files") covers project records,
and composing that list is surface-builder agent work, not a new round.
Projects are **not** a Round B board: Verdict 4 closed the board set at
three, and a work-list is not a glance dashboard.
**Deferral trigger:** a dedicated Projects surface is revisited when the
Round C gate shows the Booked cards cannot carry the work list (57 active
projects is the number to watch), or when the owner asks — whichever comes
first. Until then the deferral is explicit, not a gap.

## 5. RATCHET ACCOUNTING — data is not code

The Ratchet's size ledger binds **files** (statics, code). The import
grows **data**, and the two are accounted in separate ledgers, both filed
with the Round C report:

- **Code ledger (unchanged discipline):** the translator is code. Its one
  home: a **single Python-stdlib file**, master in the fork repo's tooling
  area beside the bridge master (`migration/` next to `bridge/`), running
  copy on the Dell beside bridge.py — the lane whose session pattern it
  reuses. Single file, stdlib only, modeled on bridge.py; it replaces
  nothing because no importer exists — and it does not become standing
  machinery: after the cutover delta run (§9 of the map) verifies, the
  Dell copy is removed and the repo master remains as the migration
  record. A translator that grows a framework, a config system, or a
  second file without a named trade fails the Round C gate like any other
  untraded growth.
- **Data ledger (new, this addendum):** the import reports **record
  counts per family written, skipped-by-hash, and left unlinked** — the
  `migration/staxcloud-<date>` manifest *is* the data ledger, filed with
  the round's evidence. Data growth is not charged against file budgets,
  and file shrinkage is never used to "pay" for data. Round C's code-side
  removals stand as Verdict 4 already counted them (the four test
  contacts, their drafts, the zombie thread, contacts.js's second master)
  — the import's additions are not netted against them; both ledgers are
  shown, neither is hidden inside the other.

## 6. OWNER CALLS — none

No ruling in this addendum spends money, contacts a customer, or touches a
taste the owner has claimed — the integration itself is his commission,
the vocabulary is Verdict 4's (already his law), and the one future act
that is genuinely his — the final cutover freeze of StaxCloud — is already
reserved to him by the standing production rule and is not part of this
import, which is a copy that writes nothing on the Dell. The director
decides the rest, above.

## 7. REVISED ROUND SEQUENCE

Unchanged from Verdict 4, with Round C's interior made explicit:

**Round 3** (in flight, untouched) → **security fixes** (as ordered) →
**A Navigation** → **B Boards** → **C Leads** — *cleanup → import (§2
derivation, manifest, read-backs) → pipeline build → gate on the real
163-contact book* — → **D Texts + Connections truth** → **E Forms
builder** → **F Advanced honesty**. The Q6 bytes pass runs after the
Round C gate, in parallel with D–F, blocking none of them.

---

*Filed by the plan director, 2026-11-02. Binding on the migration and the
Round C build until the owner or a later verdict amends it.*
