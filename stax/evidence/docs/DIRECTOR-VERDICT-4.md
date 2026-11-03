# Director Verdict #4 — the restructure: Boards, Leads, navigation, Forms

Commissioned by the owner 2026-11-02 ~19:11 CST, after his nine-screenshot audit
of the live app ("There are multiple paths to get to boards… consider what we're
going to change channels in for and look for those duplicate overlapping paths…
point Kimi 3.1 at it… and then have the director check the work"). This verdict
checks the two evidence documents the owner ordered, rules on them, and orders
the build rounds. The RATCHET (owner law, 2026-11-02 ~19:18 CST) binds every
round below.

Evidence base (firsthand, none taken from summaries):
- SCAN-KIMI-2026-11-02.md — Kimi K3.1 Pro's reads of the owner's nine phone
  screenshots and the corrections-2 staging renders, with the parent lane's
  verifications; three inventories; ten-worst list.
- ANALYSIS-2026-11-02.md — Boards mechanics and purpose, Leads research and
  proposal, the navigation inventory, the Forms block-builder spec; SOURCE and
  PROPOSAL labeled throughout.
- The owner's nine screenshots, re-read for this verdict (the Canvas board and
  the Texts inbox in full; the rest against the scan's quotes).
- DIRECTOR-VERDICT-3.md and OWNER-CORRECTIONS-2-BRIEF.md — the standing laws
  this verdict must not break: the hide list, the owner-seat gate, the
  section-navigation rule, the demote-never-delete wiring law.

## VERDICT IN ONE LINE

Both documents are sound and are adopted with the amendments below. Boards
stay — as dashboards under glance law, not as record dumps. Leads becomes a
real pipeline and Contacts goes home to Studio. The dock becomes four tabs
because the owner's own rule emptied the fifth and nothing he uses daily is
homeless. Forms gets the InkStax block engine on Fang's kv spine, last and
largest. Every round below is small, separately deployable, and pays for
itself in removals.

---

## 1. BOARDS — kept, redefined, and the three defects get named fixes

**Ruling: KEEP.** The fold options fail on the analysis's own evidence: Work
is a decision queue and a dashboard is not a decision; Studio is a drawer
family and a board is cross-cutting (the Walk-ins board summarizes Texts +
Forms + people, and no Studio app owns it). The machinery is already proven —
the SEO board follows the discipline the Canvas board violates. What failed
was never the concept; it was that nothing enforced dashboard discipline on
the renderer or the record.

**The owner definition (binding, one sentence):** *Boards are live dashboards
your team keeps for you — each one answers "how is this part of the shop
doing, and what needs doing next" at a glance.*

**The six glance rules are ADOPTED as build law**, with two amendments:
- Rule 2 is amended to name its mechanism: a kvlist row whose record carries
  no title/name/status renders as **one count line** ("3 designs stored") —
  the `JSON.stringify` fallback in `kvRows()` is deleted, not patched around.
  Raw JSON on an owner surface is a build failure, and the Boards round's
  gate includes a grep of the rendered page for `{` record debris.
- Rule 3's closed badge set — **Waiting · Doing · Done · Needs you** — is
  enforced at **render time** (any other badge value is dropped, never
  printed) *and* in the surface-builder playbook (which stops writing them).
  One without the other leaves the hole open.

**The board set:** (1) **Fargo Tattoo SEO** — kept as-is; it is the model
citizen and is re-checked against the six rules in the Boards round, not
rebuilt. (2) **Designs** — the Canvas board, fixed as an interim (below).
(3) **Saturday Walk-ins** — new, composed under the six rules from records
Fang already holds (walk-in inquiry count from threads + submissions,
artists on Saturday, days until Saturday, next actions). No fourth board
until these three each pass the five-second test at the owner's seat.

**The Canvas board's fate:** it is recomposed as the **Designs** board —
real counts in the stat slots, the latest designs listed by their own
title/status fields with closed-set badges — and it **exits Boards when the
Canvas app surface ships** (the standing Studio slice), becoming that
surface's front screen. The interim fix is renderer + record work only; no
Canvas-surface scope is pulled forward into the Boards round.

**The three named defects, each with its fix:**
1. **Raw-JSON dump** (`index {"designs":[]}`) — **renderer fix**: the
   `kvRows()` JSON fallback is deleted; summary-less records render as a
   count line (Rule 2 as amended). Playbook fix in the same round: kvlist
   blocks are composed only over prefixes whose records carry summaries, or
   are written as stats instead.
2. **Stored GATE/RULE badges** — **both**: the record is rewritten (the
   "HOW IT WORKS" list is recomposed with closed-set badges or none — its
   three items are policy statements, and in plain words they need no badge
   at all) *and* the renderer drops any badge outside the closed set. The
   board's description copy is rewritten in the same pass: "from the
   Designer hand", "a real record in shared memory", "stored bundles, never
   invented" are engine narration and come out.
3. **"see list below" placeholder** — **record fix**: the stats are
   recomposed with the real counts of the design records at composition
   time, and refreshed by the same crew path that maintains the board.
   Renderer backstop (Rule 1): a sentence stored in a stat's value slot is
   never rendered as the headline.

Two smaller Boards rulings: the board list's "**5 blocks**" metadata is
deleted — list cards show headline number + freshness (Rule 5). The red
**Delete board** button leaves the board header; board removal happens by
asking Stax, which is the agent-first pattern and removes the page's only
destructive control from a glance surface. The list header copy ("Ask a
helper in Channels") is rewritten to name Stax and the conversation, the
only place board-making lives.

## 2. LEADS — the pipeline is adopted; the test data is deleted, not hidden

**Stages ADOPTED as proposed:** **New · Talking · Waiting on an artist ·
Booked · Resting**, plus the quiet terminal **Not a fit**. They mirror this
shop's actual process (the research's one non-negotiable), they cap at five
visible stages because that is what a phone honestly holds, and "Waiting on
an artist" is the stage this two-artist shop actually routes on.

**Temperature ADOPTED:** **Ready · Interested · Just looking** — words, never
numbers, each mapped to a response plan (Ready surfaces in Needs-you today;
Interested is kept warm by drafts; Just looking gets one helpful answer +
the booking link, then Resting). A badge that forces an action or it does
not ship — the research is unambiguous and the proposal follows it.

**The lead card is ADOPTED as specified:** name · the piece in their words ·
artist (Shawn / Leni / unassigned) · last contact with waiting-on-whom ·
one plain next-action line · temperature badge. The top stats strip carries
real per-stage counts; stage sections are accordions (the Work pattern the
owner already approved); the only filter is All · Shawn · Leni. No kanban,
no drag — sections and agent moves are the phone-honest primitives.

**Birth and movement ADOPTED:** a form submission or a first inbound text
creates the lead in New, deduplicated against the contact index (an existing
customer re-opens as a lead, never duplicates); stage is a few fields on the
existing contact record, written by the sweeps that already touch it — a
projection, not a new store, per Verdict #2. Scripted moves (reply sent →
Talking; booking seen → Booked; 7 quiet days → Resting) apply themselves;
anything that commits the shop (an estimate, a design send) stays a
Needs-you approval. The owner moves a lead by telling Stax. A booked lead
whose day passes graduates to Contacts; Contacts itself does not change —
it stays the Studio address book, and it loses its second master (the dock
tab) in the navigation round.

**Cleanup of the test records — the honest mechanism, named.** The records
are: the "John Doe" contact (the R7-era fabrication, never a person), the
Marta/Riley/Wanda test contacts, their held test drafts, and the R12
zombie-draft thread in Texts. Three facts decide the mechanism, all verified:
agent hands **cannot** delete (their only memory tools are store and recall);
the builder must not (presentation only); and the kv store **does** have a
delete route — `DELETE /api/memory/agents/{id}/kv/{key}` over the same
authenticated API the sidecars already use. Therefore:

- The cleanup is a **parent (Stax) data operation**, executed as step 0 of
  the Leads round — not a builder task, not an agent turn.
- Sequence: first decide the pending test approvals through the normal
  approvals path (reject), so nothing dangles; then delete the `draft/…`
  records; then the `contact/…` records. **Every deletion is read back**
  (GET → 404) and the read-backs are filed with the round's evidence.
- The zombie thread (`sms/2189792590`): its origin is established from the
  bridge's mirror records **before** deletion. If the Dell bridge mirrored
  it from Dell StaxCloud, it is deleted at that source too, or it returns on
  the next cycle and the deletion was theater. If it is Fang-native (created
  inside Fang by the R12 proof), the kv deletion sticks. Proof standard: the
  thread is still absent after **two full bridge cycles**, and the test
  contacts are still absent after **one full Forms sweep and one Texts
  sweep**. Nobody reports the cleanup done before those read-backs exist.
- The form-submission records that produced the test contacts **stay** —
  they are the intake audit trail and already carry the "test" badge in
  Submissions. Deleting the contact index entries is what removes the
  "people"; the trail is not falsified to match.
- The one honest exception: the knowledge-graph fake entity from the same
  fabrication incident has **no delete route in 0.6.9**. It stays in the
  graph, documented here, and it never renders — owner surfaces project kv,
  and no Leads/Contacts surface may read the graph for people. That limit is
  stated, not papered over.
- Going forward (backstop, not substitute): test records are created only
  under test-flagged keys, and owner-surface renderers skip test-flagged
  records. Hiding live test data behind a filter while it sits in the store
  is the prepend-era dishonesty in a new coat; deletion is the fix, the
  filter is only a seatbelt.

## 3. NAVIGATION — four tabs, and the ten dispositions

**The dock is FOUR tabs: Stax · Work · Boards · Leads.** Justification, in
the owner's terms: his 19:11 rule took Channels out of the dock — that was
his amendment, not this verdict's preference. The only question left was
whether something replaces it, and the answer is no. His own StaxCloud
reference runs a four-item dock. Each of the four is a daily destination
with a distinct job, and none duplicates the side card. **Studio** is a
family, not a destination — a dock tab for it would open a menu, which is
the side card's job. **Forms** would elevate one Studio app over the
shop's actual lifeline (texts) for no principle. Four tabs are wider, more
thumb-honest targets. Verdict #3 §D.1's five-tab set — recorded from the
owner's Figma direction that afternoon — is superseded by the owner's own
later rule, and LOOP.md is amended to say so (§7). Stax does not invent a
fifth tab the owner never asked for.

**The ten dispositions from the analysis (§C.3):**
1. Dock Channels tab removed — **ADOPT.** Stax is the conversation's only dock home; the Channels family lives in the side card.
2. Drawer Library row stops landing on Boards; Library gets its own surface — **ADOPT** (surface defined below).
3. Drawer Canvas row preselects the Canvas board until the Canvas surface ships, then lands there — **ADOPT**; it is the last Boards path out of the card and is removed when Canvas lands.
4. Contacts' three paths become one (drawer STUDIO row); the Texts module dock loses its Contacts button, becoming Agent · Inbox · Done — **ADOPT.** A thread still opens its own person's record from inside the thread.
5. Studio chip wall removed entirely; Automations, Scheduler, Playbooks, Capabilities move behind System → Advanced — **ADOPT.**
6. Channels chip wall removed (Chat · Team traffic · Texts) — **ADOPT.** Texts navigates by its module dock alone.
7. Module-dock "Done" normalized: every module dock's Done returns to **Stax (Home)** — **ADOPT.** The Forms (Done→Boards) and Texts (Done→agents page) special cases are deleted; one behavior, learned once, is what makes "Done" self-explaining.
8. Home/Work top chip rows removed wherever they still render — **ADOPT.**
9. TEAM Stax row (the Stax card) vs Stax dock tab (the conversation) kept as two surfaces; Report a bug / Sign out in both the drawer OWNER block and the Settings list kept — **ADOPT.** The first is the Muse pattern the owner asked for; the second is his own StaxCloud reference composition.
10. Scheduler exists only under Advanced — **ADOPT.** The standing violation the owner photographed at 16:49 is closed by disposition 5; this records that no other owner-level path may be reintroduced.

**Library's own surface, defined:** Library is **the shop's records shelf —
what the shop keeps**: saved designs (the design library, with titles and
dates; previews when the Canvas surface lands them), reference material,
and client files, projected from the records Fang already holds, newest
first, one plain list. It is not Boards (no dashboards, no blocks) and not
Contacts (no people). Its empty state says what will live there ("Designs
and files Stax saves for the shop land here"). V1 is the list and nothing
more; anything richer waits until real records exist to shelve.

**One addition the scan forces into this round:** the Settings list loses
its **Advanced row** — the module dock's Advanced tab is the corner's
navigation, and the row is a second door on the same screen (scan §9b). The
row is removed; the list keeps Appearance, its Ask Stax rows, Report a bug,
Sign out, and the plain-words version line.

## 4. FORMS — the block builder is adopted, on Fang's spine, sequenced last

**The spec (analysis §D.3) is ADOPTED:** the form def stays a kv record at
`form/<slug>`; `fields[]` grow into blocks `{id, kind, label, required,
config?}`; Build lives one level in from the unchanged module dock (Agent ·
My Forms · Submissions · Preview · Done) via "+ New form" and per-card
Edit; the canvas is the form rendered as itself in edit mode; tap selects,
toolbar is ↑ · ↓ · Edit · ✕; Edit opens a bottom sheet (label, Required,
kind config — options one-per-line); "+ Add block" opens the picker sheet
grouped by category with search, inserting after the selected block. The
agent path stays the front door — Build is for the owner's own hands, per
the agent-first law — and owner edits and agent edits write the **same
record**, never two copies.

**Amendments:**
- **Migration proof is a gate, not a hope.** The five existing field types
  map 1:1 to kinds; before Build ships, every existing def on the live
  instance (starting with "Say hello") is read back rendering identically
  under the block shape, and the Forms hand's sweep + the asleep test
  re-run clean on the new shape (the standing non-regression checklist).
  The Forms hand's playbook learns the block shape in the same round.
- **The v1 catalog is adopted as tabled** — 20 kinds: Fields (Short Text,
  Long Text, Email, Phone, Number, Date), Selection (Dropdown, Choice,
  Star Rating, Thumbs, Number Scale), Structure (Section Heading,
  Instruction Text, Divider), Tattoo (Tattoo Description, Previous
  Tattoos, Allergy note), Consent (Consent Checkbox, Photo Release,
  Aftercare acknowledgment). A kind ships only when **both** the Build
  canvas and the public form render it — InkStax's own discipline. The
  deferred list is named, not dropped: File Upload / Reference Images
  (public upload leg first), Signature / Initials (a signature control
  first), composite groups (Medical History, Client Info — v2), Connected
  blocks (Square owns booking; the booking link stays a Structure text
  block).
- **Sequencing:** Forms is the **last and largest** build round (§6). It
  lands on a settled navigation map, and nothing in the earlier rounds may
  pre-build pieces of it.

## 5. The scan's remaining defects — disposition and owning round

1. **Texts list rendering** (three cards at three widths, the first running
   off the right edge with avatar/preview/timestamp clipped; unstyled light
   cards on the dark theme; "Texts" as both chip and heading) — **FIX**,
   Round D: the thread list renders as one list — full-width themed rows,
   name or number, one-line preview, timestamp, unread state — in the
   Texts module's own layout. The heading duplication dies with the chip
   wall in Round A. The zombie record itself is deleted in Round C (§2);
   Round D's gate photographs the same inbox clean *and* well-formed.
2. **Chat history titled "Earlier conversation"** — **FIX**, Round A. New
   chats take their title from their first message (first line, trimmed to
   a few words) at the moment that message is sent, stored as the session
   label through the mechanism the labeled staging sessions already prove
   exists. Existing unlabeled sessions keep the honest fallback — no
   invented titles are backfilled. Gate: a fresh chat, one message, the
   drawer shows the derived title.
3. **Connections' "Nothing is connected yet"** — **FIX**, Round D.
   Connections projects the connections the shop actually has, from the
   health records the sidecars already maintain: **Texts** (bridge
   heartbeat/`attention` freshness → "Working", or plainly "Not answering
   — tell Stax" when stale) and **Forms** (pull-sync cycling → "Working"),
   listed above any kernel channels, each with its plain status. A
   connection that exists must never again read as absent; a broken one
   must never read as fine.
4. **Advanced → Helpers printing raw daemon errors under RUNNING cards** —
   **FIX**, Round F: traffic rows render a plain one-line summary ("A
   helper couldn't start · 2m ago") with the sender named in human terms;
   the raw string lives one tap down in an expandable detail — Advanced is
   where raw belongs, demoted within the page, not deleted, and never in a
   list row. A helper whose latest traffic is a start failure may not sit
   under an unqualified RUNNING label on the same screen.
5. **Document title "OpenFang Dashboard"** — **FIX**, Round A: the title
   becomes "StaxCloud". One line in the head template; the platform name
   leaves the app's public face.
6. **Settings' duplicated Advanced entry + unexplained "Done"** — **FIX**,
   Round A: the Advanced row is removed from the Settings list (§3), and
   "Done" is cured by normalization (disposition 7) — identical behavior
   in every module dock is the explanation.
7. **The missing Work capture** — **FIX (process)**, Round A and every
   round after: Round A's gate files the **first Work capture** (phone +
   desktop, before and after) and every subsequent round's shot set
   includes Work. If the Round A capture shows the dock badge's count is
   not legible in words on Work's own Front desk card, labeling it there
   ("Needs you · 4") enters Round A's scope as a named fix — the badge
   never again floats unexplained in someone else's screenshot.
8. **Two notes, dispositioned so they are not lost:** the Home/TEAM status
   wording ("Text replies: You approve") is builder-inferred copy, and
   Kimi reads it as an internal mode label — Round D normalizes the pill
   and the drawer row (one shared source, as built) to a plain sentence
   that says what the mode does. And the **cropped brand graphic** on Home
   is Round 3's problem, not an R4 round's: Round 3's gate must show the
   reaper centerpiece fully inside the phone viewport, uncropped (§6).
   The drawer's expanded-state bottom clipping (CHATS cut mid-row, no
   scroll cue) is fixed in Round A with a bottom fade/cue whenever drawer
   content continues below the fold.

## 6. SEQUENCING — six small rounds, each with its gate

Global gate for every round (Verdict #3's gate, plus the Ratchet): fresh
login on the live instance; phone-width and desktop screenshots of the
round's surfaces filed beside the work; the Ratchet's non-regression
checklist re-run (crew 7 Running; cron table 19 with the three standing
jobs enabled; sweeps completing; approvals round-trip exactly once; brief
readable; pull-sync green; port 3121 untouched); the round's size ledger
filed (before/after for every touched file); reported to the owner only as
what the screenshots and read-backs show.

- **Round A — NAVIGATION.** Four-tab dock; both chip walls out; Done
  normalized to Home; Settings list loses its Advanced row; document title;
  Library's own page (v1 list); Canvas row preselect (interim); chat titles
  from the first message; drawer bottom scroll cue; first Work capture.
  *Gate: dock + drawer + Forms + Texts photographed with no chip wall and
  no Channels tab; a new chat wearing its first message as its title.*
- **Round B — BOARDS.** The renderer rules (count line, closed badge set,
  stat-slot discipline, list headline + freshness, Next actions); the
  Designs record recomposed; SEO re-checked; Walk-ins composed; Delete off
  the header; list/header copy rewritten. *Gate: the Boards list and all
  three boards at phone width pass the five-second test; the rendered-page
  debris grep is clean.*
- **Round C — LEADS + CLEANUP.** Step 0 is the §2 data cleanup (deletions +
  read-backs filed before any UI claim). Then the pipeline surface: stages,
  temperatures, cards, counts, accordions, artist filter; stage fields on
  the contact record via the sweeps. *Gate: Leads at the owner's seat shows
  real people in real stages on a clean store; Studio Contacts unchanged
  as the address book; cleanup resurrection checks passed.*
- **Round D — TEXTS + CONNECTIONS TRUTH.** The one-layout thread list;
  Connections projecting Texts + Forms from sidecar health; status-pill
  copy normalized. *Gate: the inbox photographed clean and well-formed;
  Connections photographed telling the truth in both directions (a working
  connection shown working; the stale case shown plainly in staging).*
- **Round E — FORMS BUILDER.** The §4 spec: block-shape migration with
  read-back proof, Build view, picker, edit sheet, 20-kind v1 catalog,
  playbook update. *Gate: the owner-path proof — a form created and edited
  by hand in the Build view, an agent-made form edited by hand and still
  rendering publicly, the asleep test re-run clean.*
- **Round F — ADVANCED HONESTY.** Helpers traffic in plain summaries with
  raw detail one tap down; RUNNING labels qualified by latest traffic; the
  helper cards' stray monospace subtitle face and unlabeled circular
  control normalized or labeled (controls keep working — demoted never
  deleted, inside Advanced too). *Gate: the Helpers page photographed with
  a failure present in staging and no raw daemon string in any list row.*

**Round 3 (in flight — drawer gestures + reaper branding) absorbs NONE of
this.** Specifically not: the dock change, the chip walls, chat titles, the
Connections projection, the Settings row, the title line, or any
Boards/Leads/Forms content. It finishes as briefed — gestures and the
reaper — deploys, and passes its own gate (which must additionally show the
Home centerpiece uncropped at phone width). Round A starts from Round 3's
deployed base, so the nav map is photographed against the final drawer.

## 7. RATCHET LEDGER — the removals that pay for the additions

Additions in this package: the Leads pipeline renderer; the Library list
page; the Forms Build view (canvas, picker, edit sheet); the Connections
projection rows; the Walk-ins board record; chat-title derivation.

Removals, by round — each is deleted or demoted in the same round that
spends it:
- **Round A:** the Channels dock tab and the channels-page landing path ·
  the Studio chip wall and the Channels chip wall (two whole navigation
  components) · the Texts dock's Contacts button · the Forms Done→Boards
  and Texts Done→agents-page special cases (replaced by one shared Done) ·
  the Settings list's Advanced row · Scheduler/Automations/Playbooks/
  Capabilities' owner-level paths · Home/Work top chip rows.
- **Round B:** the `kvRows()` JSON-stringify fallback · the "5 blocks"
  list metadata · the board header's Delete button · the Canvas record's
  placeholder stats and engine copy (the record itself shrinks).
- **Round C:** four test contact records, their held test draft records,
  and one test thread record, deleted from kv (§2) · the Leads tab's tenancy
  of the Contacts renderer (contacts.js loses its second master).
- **Round D:** the thread list's content-width card layout (one layout
  replaces three) · Connections' kernel-registry-only read.
- **Round E:** the read-only dead end on My Forms (cards that could only be
  looked at) · the five-type ceiling on the def shape.
- **Round F:** raw daemon strings in list rows · the unqualified RUNNING
  label.

Discipline: every round files its size ledger per RATCHET.md §1. A round
whose statics grow net must name its trade in the round report or it has
not passed its gate. Rounds A and C are net-negative by construction; if
Round E (the one genuine build) grows the Forms files, its trade is named
in advance: the chip-wall and special-case deletions banked in Round A are
**not** transferable credit — Round E pays its own way or reports the
growth as a named, director-visible exception before deploy, never after.

**Corrections to the plan of record (LOOP.md), ordered with this verdict:**
(1) the tab set is amended to Stax · Work · Boards · Leads, recorded as the
owner's 2026-11-02 19:11 amendment superseding §D.1 of Verdict #3; (2) the
Boards definition and six glance rules are entered as the Boards spec;
(3) the Leads definition (stages, temperatures, card) is entered, closing
Verdict #3 Step 5's "recompose the contacts page" scoping, which specified
the wrong surface; (4) the Forms block-builder spec (§4) replaces Step 6's
"panel alignment" scoping — R7's panel was never the gap; the missing
builder was.

## 8. OWNER CALLS — one

Everything else in this verdict is decided. One question changes what the
product *is* rather than how it is built, and it is the owner's:

**May Stax send the set scripted replies to leads on its own — the booking
link, the hours, the "no openings listed" script — holding only estimates,
designs, and anything custom for your OK?**

The Leads design (§2) keeps an Interested lead warm between artist touches.
Under the standing construction, every one of those sends waits in
Needs-you, which means a warm lead cools at exactly the speed the research
says kills it — while the scripts themselves are words the owner has
already approved verbatim (and, on StaxCloud's own line, he ruled the same
evening that the availability script sends rather than holds).
**Recommendation: yes for the scripted set, named and bounded** — scripts
live as records Stax can quote exactly and never improvise around;
estimates, designs, prices, and any free-written reply stay approval-gated
without exception. If the answer is no, the pipeline still ships: Interested
leads are kept warm by drafts in Needs-you instead, and the stage design is
unchanged.

---

*Filed by the plan director, 2026-11-02, at the owner's direct order.
Binding on the restructure rounds until the owner or a later verdict
amends it. Next director touchpoint: the Round A gate — dock, drawer, and
the first Work capture, at the owner's seat.*
