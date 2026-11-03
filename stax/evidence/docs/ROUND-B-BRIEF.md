# Round B — Boards (2026-11-02)

**STATUS: READY — DO NOT START ON RECEIPT.** This brief is complete and buildable, and its launch is sequenced by the director, not by the builder's readiness: the build starts only after (1) the decider/memory activation window has run and (2) the owner has given his Round A verdict at his own seat. If either has not happened when this brief reaches you, stop and confirm with the parent before touching the tree.

Base: Round A's deployed tree state — commit `69f0e0c` on `stax-ux` (seven Round A commits on `f7bd958`), live binary `b8dd9dfe…`; the tree's head may since have advanced through the repo-sync merge that contains it (remote head `2012eeb8`). **Before anything else, confirm the base with `git log`: if `69f0e0c` is not in the tree's history, STOP and report — do not build on a different base.** Presentation layer: `crates/openfang-api/static/**` plus permitted webchat.rs include lines if a new static file must be served — **plus two verdict-named exceptions**, scoped in Parts 2.2 and 2.3: the Designs board record's recomposition and the surface-builder playbook corrections. Verdict 4 orders both in this round, as record and playbook work through the paths that already maintain them; they are not license to widen further. No new machinery, no new routes, no kernel/sidecar changes, no Cloudflare Worker changes. Standing builder rules: own browser self-check on staging in all four configs (phone 390×844 + desktop, dark + light); found/fixed + found/not-fixed lists; glyph icons through the single sprite, raster art as static assets. Rulings source: DIRECTOR-VERDICT-4.md §1 + §6 (Round B) + §7 (ledger), the six glance rules as adopted there from ANALYSIS-2026-11-02.md §A.3, and tonight's close-out (Parts 1 and 3). The Ratchet binds this round — Round B ends net-negative, and Part 1 is how.

## PART 1 — The ledger opener: delete the dead i18n framework (do this first)

The Round A builder found a dead i18n framework in the statics: **76 KB** (its report's figure — re-measure at the base and use the measured bytes in the ledger), **unserved** by the app shell, its entry point **`window.t` never defined** anywhere in the served tree. This round deletes it — as the round's first act and its ledger's first line.

1. **Re-verify deadness firsthand before deleting anything.** Grep the entire served tree — all of `static/**`, the served root document, and webchat.rs's include lines — for every reference: the framework's file names, its symbols, `window.t`, any script or link tag that loads it. Every hit is read, not assumed. A file that merely shares a name or a helper with the framework is not the framework.
2. **If anything live references it, STOP Part 1.** Report the reference in found/not-fixed and proceed to Parts 2–3; the round's ledger then names the missing trade explicitly at the gate instead of quietly passing. Do not delete a referenced file, and do not rewire a live reference to make the deletion possible — that is machinery work: reported, never built.
3. **If dead, delete the framework's files whole.** One home per thing: nothing i18n-shaped remains behind — no stub, no redirect, no emptied file kept for nostalgia.
4. **The ledger statement, explicit:** this deletion is the named trade that **closes Round A's books net-negative**. Round A's statics grew net on the owner-ordered tile artwork (its code delta was −11,831 B), and this removal was queued by name at Round A's close as the payment. The bytes leave the tree once, in this round, and are claimed once — both rounds' ledgers reference this single line by name rather than each silently counting it. It is also this round's opening ledger line; Round B must still finish net-negative across its own whole ledger (Gate, below).

## PART 2 — Boards under glance law

**The owner definition (binding):** *Boards are live dashboards your team keeps for you — each one answers "how is this part of the shop doing, and what needs doing next" at a glance.* A board that needs explaining has failed; the five-second test is this round's bar, self-assessed per board in the report.

**The six glance rules** (ANALYSIS-2026-11-02.md §A.3, adopted as build law by Verdict 4 §1; the verdict's two amendments are folded in and marked):

1. A stats value is a number or a short state ("3", "None waiting"). A sentence or placeholder in a stat slot renders as text, never as the headline — and the surface-builder playbook is forbidden from storing one.
2. A kvlist row must render a human summary (title/name/status). A record with no summary renders as **one count line**, named by what it counts ("3 designs stored"), never as raw JSON. Raw JSON on an owner surface is a build failure, full stop. *(Verdict amendment: the mechanism is named — the `JSON.stringify` fallback in `kvRows()` is **deleted**, not patched around — and this round's gate greps the rendered Boards pages for `{` record debris.)*
3. Badges come from a closed plain-words set — **Waiting · Doing · Done · Needs you**. *(Verdict amendment: enforced at **render time** — any other badge value is dropped, never printed — **and** in the surface-builder playbook, which stops writing them. One without the other leaves the hole open.)*
4. Every board ends with a **Next actions** list: named action, named owner ("Reply to the newest review — Stax has a draft waiting").
5. Board list cards show the board's headline number and freshness ("Designs — 4 stored · updated 2h ago"), never a block count.
6. Empty states say what the board *will* show ("No designs yet — new designs land here"), not that nothing is stored.

### 2.1 The renderer rules

Implement Rules 1, 2, 3, 5, and 6 in the Boards renderer (Rule 4 is composition, §2.2/§2.5, over renderer support that already lists blocks): the `kvRows()` JSON fallback is deleted and summary-less records group into count lines; badges outside the closed set are dropped at render; a sentence or placeholder sitting in a stat's value slot renders as a plain text line, never as the stat headline; list cards carry headline number + freshness. The renderer's other behavior does not change — this is discipline on the projection, not a new Boards page.

### 2.2 The Designs board, recomposed (record work — verdict-named exception 1)

The Canvas board is recomposed as the **Designs** board, from the design records themselves:

- **Stats hold real counts**, composed from the design records at composition time — designs stored, how many are waiting the owner's OK — and refreshed by the same crew path that maintains the board. The "see list below" placeholder stats are gone.
- **The latest designs list by their own title/status fields.** A row is the design's title with its status in plain words; any badge shown is drawn only from the closed set.
- **The "HOW IT WORKS" list is recomposed:** its three items are policy statements and in plain words need no badge at all — closed-set badges or none, and the stored GATE/RULE badges are gone from the record, not merely hidden by the renderer.
- **The board's description copy is rewritten:** "from the Designer hand", "a real record in shared memory", "stored bundles, never invented" are engine narration and come out. The copy says what the board is for the shop, in the shop's words.
- **Interim, and known to be:** Designs **exits Boards when the Canvas app surface ships**, becoming that surface's front screen. Build nothing around this board's permanence that the exit would have to undo. No Canvas-surface scope is pulled forward into this round.

The recomposed record is staged as the exact content the crew composition path writes, and is present in the staging store for the gate; it reaches live only through the parent's deploy step, like everything else in this round.

### 2.3 The playbook half (verdict-named exception 2)

Rules 1 and 3 bind the writer as well as the renderer. In the same round, the surface-builder hand's playbook masters in the tree gain/carry three standing rules, in the playbook's own voice — text corrections only, no new tool, no new record family:

1. Never store a sentence or a placeholder in a stat slot; stats are numbers or short states.
2. Never write a badge outside the closed set — **Waiting · Doing · Done · Needs you**.
3. Compose kvlist blocks only over prefixes whose records carry summaries (title/name/status); over any other prefix, write the block as stats instead.

### 2.4 SEO — re-checked, not rebuilt

**Fargo Tattoo SEO** is the model citizen and is **kept as-is**. Read it against all six rules, rule by rule, and report the six verdicts. Fix only what a rule actually flags — the §2.1 renderer changes may cure a finding globally, in which case the re-check is a read, not an edit. Its stats stay honest in the analysis's sense: a slot for something not yet measured reads as not measured, never as an invented number.

### 2.5 Saturday Walk-ins — composed from records

The new board, composed under the six rules **from records Fang already holds** — no new store, no new job, no new primitive; it is refreshed by the same crew path that maintains the other boards:

- **Stats:** walk-in inquiries this week (counted from text threads + form submissions); artists on Saturday (from the artist records); days until Saturday (computed at composition/refresh).
- **Next actions** per Rule 4 — named action, named owner, as the records support (the walk-in announcement draft; the Saturday sheet check).
- **The standing walk-in facts** — Saturdays noon–7, Leni works them, smaller pieces, first come first served — may appear **only where a record carries them**: projected from records, never hard-coded prose in the renderer or baked into the record where it can drift from the shop's truth. **If the records cannot support a truthful stat or line, that slot is omitted and the gap is reported in found/not-fixed.** An honest thin board beats an invented full one — grounding is an architecture property, and this board is where it proves itself.

### 2.6 Header and list copy

- **The red Delete button leaves the board header.** Board removal happens by asking Stax — the agent-first pattern — which also removes the page's only destructive control from a glance surface. The header keeps the board's title and freshness.
- **The "5 blocks" metadata is deleted from the board list cards**; Rule 5's headline number + freshness is what a card shows.
- **The list header copy is rewritten:** "Ask a helper in Channels" (and anything like it) comes out; the copy names **Stax and the conversation** — the only place board-making lives.

## PART 3 — Work-card link treatment

From Round A's own device captures: a long booking URL inside a Work / Needs-you card now wraps inside its card (Round A Part 8's fix), but it still **breaks mid-token** across lines. Give long URLs in Work and Needs-you cards the treatment chat replies received in Round A Amendment 2: **no mid-token breaks — the link renders on a single line with an ellipsis ending, and the tap still opens the full link.** Every other card behavior — layout, badges, Approve/Reject, counts, ordering — is identical. The underlying records are not yours to touch; this is render only.

## Gate (staging, final binary, all four configs)

- **Every disposition clicked, not assumed:** the Boards list and **all three boards** photographed at phone width in all four configs; each board's five-second self-assessment stated in the report (what it answers, in one line, or it has failed and says so); Designs shows its recomposed stats and list; Walk-ins shows its composed stats; SEO carries its six rule verdicts.
- **Renderer proofs, demonstrated on staging records:** a summary-less record renders as a count line (photographed); a record carrying an out-of-set badge (a GATE-style badge staged for the purpose) renders **without** it; a stat slot holding a sentence renders it as text, never as the headline. **The rendered-page debris grep is clean on every Boards page** — no `{` record debris anywhere on an owner surface.
- **Counts are hand-checked:** the Designs board's stats match a hand count of the staging store's design records; the Walk-ins stats match a hand count of their source records (threads + submissions for the week; the artist records for Saturday). A number nobody re-counted is not a gate pass.
- **Work cards:** a long-URL card photographed with the single-line ellipsis treatment, and the link **clicked** — it opens the full URL.
- **Round A re-verified intact — any regression fails the round:** four dock tabs and no Channels tab; drawer gestures exactly as Round 3/A left them (hamburger tap toggles, edge-drag with finger-follow, swipe/scrim/ESC close, sections start closed, no X); Home composition (mascot the only top element, sheet beneath); Library's own page and list; chat titles from the first message with the honest fallback; document title "StaxCloud"; module docks with Done → Home everywhere; Settings and Connections landings still plain lists; vocabulary scans clean on owner surfaces (machinery words only inside Advanced). **Work is photographed at phone + desktop, before and after, and filed with the round's evidence** — every round's shot set includes Work.
- **Non-regression (the Ratchet checklist, re-run whole):** crew health judged by **function** — Forms sweep / Texts sweep completing in the daemon log, approvals round-trip exactly once, brief readable, pull-sync green — **never by instantaneous agent-state reads** (the kernel watchdog marks idle agents "Crashed" and auto-recovers them; a state read is not a verdict). Cron table compared against the count read at this round's base: the standing table was 19 jobs before the decider/memory activation window, which arms its jobs deliberately — any difference from the base read is named and explained, never silently absorbed; Forms sweep / Texts sweep / Morning Brief enabled. Port 3121 untouched. Zero console errors beyond the known pre-existing noise.
- **Size ledger (Ratchet §1):** before-sizes of every static file this round touches are recorded at the base **before** editing — the ledger continues from Round A's and never resets. **Opening line: Part 1's i18n deletion**, with its measured bytes and the explicit statement that it is the trade closing Round A's books net-negative (Part 1, item 4). The report carries before/after per touched file and names every removal (the i18n framework, the `kvRows()` JSON fallback, the board header's Delete button, the "5 blocks" list metadata, the Designs record's placeholder stats and engine copy). **The round's final statics delta is net-negative or the report names the trade explicitly — untraded growth is a gate failure.**

## Commits and conduct

- **Two local commits minimum**, plain messages: (1) **ledger + renderer** — Part 1's deletion, Part 2.1's renderer rules, Part 3's card treatment; (2) **boards** — the Designs recomposition, the playbook corrections, the SEO re-check's fixes if any, the Walk-ins composition, the header/list copy. More commits are fine; one squashed commit is not.
- **Presentation layer only, plus the two verdict-named exceptions.** Never rebuild harness primitives: a machinery need (a route, a tool, a record shape, a refresh job) is reported in found/not-fixed, never built. Surfaces are projections of records and agent work; controls are few and cleanly operable or absent.
- **Build + stage only.** No deploy, no push, no contact with the live instance or Sarah's box beyond the staging environment. Deploy is a separate parent step, after this gate.
