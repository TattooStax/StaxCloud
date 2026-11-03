# Director Verdict #2 — Muse-like direction, tab set, and the road to beta

Director review commissioned by the owner 2026-11-01 ~14:14 CST, after the MUSE-LIKE
DIRECTION landed in LOOP.md. This verdict builds on Verdict #1 (UX-RESKIN-PLAN.md);
its scope law stands unless this document explicitly amends it.

## VERDICT: APPROVE-WITH-CHANGES

The Muse-like direction is approved. The owner's core read is correct: Fang already
contains the machinery (multi-session chat, persisted sessions, per-agent WebSockets,
approvals, scheduler, hands, kv + knowledge graph) — the Muse experience on Fang is
assembly, not invention. The changes below settle the tab set (his candidates are
partly rerouted, with reasons), insert two slices the queue didn't have (side panel,
surfaces engine), swap two slices' order for a trust reason, and grant exactly one
narrow backend exception. Everything else in Verdict #1 — static-only scope, labels-only
renames, prove-it gates, Sarah's box as proof target — remains binding.

---

## A. The bottom tabs — five, fixed

**Home · Channels · Work · Studio · System**

The dock is a fixed set of places, in this order, on every business. Muscle memory is
the product; tabs never appear, disappear, or reshuffle per business (the agent spins
up surfaces *inside* tabs — see B).

- **Home** — the brief. Found / Did / Needs-your-call, generated from real records
  (see R3's projection rule). A one-line health status. This is the landing screen and
  the proactive face of the product. Charts and analytics live in Work → Reports, not here.
- **Channels** — the conversation surface and the steering wheel. The main conversation
  with the agent, customer message streams, and side chats (B). Fang's Chat + Comms merge
  here. If you can send a text message, this tab is where you run the business from.
- **Work** — the business's operations. **Needs you** sits at the top (approval cards,
  held drafts). Below it: Team (the Helpers), Reports, and outcome **boards — Leads and
  SEO live here** as boards, not tabs (see candidate verdicts below), plus Contacts
  when the graft lands (R8).
- **Studio** — where things get made. Playbooks (Hands), Automations (Workflows +
  Scheduled), Forms, Capabilities (Skills), and every surface the agent spins up.
- **System** — the rack. **Connections** (all integrations, one place, plain status),
  Settings (plain sections; Advanced collapsed at the bottom holding Diagnostics and
  System status). Nobody's daily path runs through here — that's the point of the
  no-config law.

### Verdict on the owner's candidates

- **Needs-you as a tab: NO.** Needs-you is a queue, not a place. It gets a badge on the
  Work tab, a section on Home, and cards inline inside Channels conversations — it
  *finds the owner* in three places instead of waiting inside a fourth tab the owner
  must remember to check. A tab would also sit empty most of the day, training the
  owner to ignore it — the exact failure mode of the old StaxCloud Needs-you.
- **SEO / Leads as tabs: NO as tabs, YES as first-class boards.** They are outcomes
  the agent works, not places the owner goes. Tabs must be universal — every shop has
  a Home and a Work; not every shop's day is organized around SEO. Leads becomes a
  board in Work backed by Fang's bundled Lead hand (it already exists and already
  dedups and scores). SEO becomes a board the Scout-pattern hand maintains — and it
  is the demonstration surface for the surfaces engine (R6), so the owner's instinct
  gets a concrete, visible home without breaking the fixed dock.
- **"Connectors inside a mode section": YES, interpreted as inside the surfaces**
  (see C). Nothing lives in a config ghetto.

Grounding: this is the StaxCloud dock family (System · Work · Channels · Studio) with
Home promoted to first position because the brief — not a menu — is the product's
opening move; the owner's earlier first-screen steering (Forms, Channels, Email,
Calendar) is honored as *content* priority inside Home and Work, not as tab names.

## B. The Muse-like layer

### Side chats — real, and already plumbed
Fang persists sessions in SQLite and serves a WebSocket per agent; Comms already
multiplexes many conversations. Mapping: the **main conversation** is the owner's
primary session in Channels. A **side chat** is any other session — another agent, a
topic thread, a customer thread — opened in a slide-over panel on wide screens and a
full-screen push on narrow ones, without losing the main thread's place. Fang's
Sessions page stops being a page; it becomes the list inside that panel. This is
static-only work: one reusable Alpine panel component plus the conversation renderer
the chat page already has, instantiated twice.

### Side cards — the inspector, borrowed from StaxCloud's sidecar
StaxCloud already owns this primitive (the contextual sidecar). On Fang: tapping any
card — an approval, a lead, a form submission, a contact — opens its detail as a
**side card** alongside the conversation instead of navigating away. One panel
component, three slots (title, body, actions), fed by endpoints that already exist
(approvals API, kv, knowledge graph). Approving from a side card and approving from
Work → Needs you are the same API call behind the same card.

### Proactive brief — Home, and echoed in Channels
The brief lives on Home and is also posted as the first card of the main Channels
conversation each morning, so it reaches the owner wherever they actually are.
Machinery is native: a Scout-pattern Hand on a schedule collects the day-state and
writes brief items; Home renders them. **Hard rule (new, binding): the brief is a
projection of real records — pending approvals, new kv submissions, schedule results,
lead-hand state — never items the model invents.** The hand may summarize records;
it may not mint them. This is StaxCloud's false-Needs-you wound, closed by
construction rather than by cleanup.

### "The agent spins up a surface" — what it concretely means in v1
Three tiers, in order of preference. No new framework anywhere.

1. **Composition (the v1 engine).** A *surface definition* — a JSON list of blocks
   (cards, lists, a form, a status row) plus a data pointer — stored in Fang's kv
   store. One generic static renderer page in Studio draws any definition. The agent
   writes definitions with the memory tools it already has; a "surface builder" Hand
   teaches it the block vocabulary, which is StaxCloud's block discipline shrunk to
   what the renderer supports. Owner asks in chat → definition lands in kv → surface
   appears under Studio. Survives restart because kv is SQLite.
2. **Playbook activation.** Turning on a Hand (Lead, Forms, Scout-pattern) *is*
   spinning up a capability: it gets a live entry in Studio and its boards appear in
   Work. Most "new surface" requests in a real shop resolve to an existing playbook.
3. **Authored pages — explicitly OUT of v1.** The agent can write HTML files, but
   Fang serves only its embedded dashboard (verified in FORMS-RESEARCH §1):
   authoring ≠ hosting. Bespoke agent-authored pages need either the Cloudflare
   Pages route (public things — the Forms pattern) or a backend serving route.
   Neither is in beta. Anyone promising "the agent builds any screen" before that
   route exists is overselling; the composition tier covers the honest 90%.

## C. Connectors — the rack in System, the work in the surfaces

- Fang's "Channels" page — integrations — keeps its Slice-1 rename to **Connections**
  and lives under **System**: every connector as a card with a plain status
  ("Connected", "Needs sign-in") in one rack the owner can glance at.
- Additionally, a connector appears **inside the surface it feeds**: the modem/SMS
  card inside the SMS module, email inside Channels, the form's public link inside
  Forms. The rack is for inventory; the surface is where the work happens.
- No setup wizard, no config forms as the primary path: where a connection needs a
  human step, the card says what and the agent walks it through in conversation.
  (In beta, the existing connect buttons stay on the System cards — plain, buried,
  and not on anyone's daily path. Agent-driven connection via the browser hand is
  post-beta.)

## D. Per-module bottom panels — the rule, and the first two modules

**Rule:** the global dock belongs to the top level. Inside a module, the bottom bar
becomes that module's own panel: **the agent tab first**, then the module's tabs —
the same muscle-memory slot (far left) always returns you to the conversation.
A persistent way back to the global dock sits in the module header. Implementation:
one dock component, two modes (global / module); a module declares its tabs in its
surface definition. This is the owner's standing StaxCloud law, unchanged.

- **Forms panel: Agent · My Forms · Submissions · Preview.** Agent first (ask for a
  form, ask about a submission). Submissions is where the intake lands; Preview is
  what the public sees (rendered from the same definition the Pages page uses).
- **SMS panel: Agent · Inbox · Contacts.** Deliberately no Settings tab — reply
  posture (the owner's deliberate "Automatic" choice) shows as a plain status line
  in the Inbox ("Replies: automatic — tell me to change it"), changed by talking to
  the agent, never by a settings screen. Three tabs is fine; the law says up to
  five, not always five.

## E. The road to a working beta

### What "beta" means — concretely
One real shop runs its day on fang.sefer.team (Sarah's box is the pilot instance):

1. The owner logs in with a password only and lands on a morning brief that is
   *true* — built from yesterday's real approvals, submissions, and scheduled work.
2. The owner asks the agent, in plain words in Channels, to do a real task end to
   end (follow up leads, draft replies, change a form) and watches it happen.
3. Anything the agent wants to send or change arrives as a card the owner approves
   or denies in one tap — from the conversation, from a side card, or from Work —
   without leaving the screen they're on, and the decision is read back in the audit.
4. A customer submits the shop's public form while the box is asleep; by morning it
   is a contact and a Needs-you item, exactly once (deduped), with a draft reply held.
5. A customer text to the shop line appears in the SMS inbox; the owner (or the
   agent, per posture) replies from Fang and delivery is read back.
6. The owner opens a side chat to ask a side question mid-task and loses nothing.

Voice answering is **not** in beta (feasibility is proven on the Dell modem; the
build is its own post-beta track). Tenancy/billing/provisioning are **not** in beta —
beta is one shop, perfectly; sellable is the product layer after.

### Revised slices (R-series; replaces the LOOP queue from Slice 2 on)

Per-slice proof gates inherit Verdict #1 §6 unchanged (staging first, before/after
screenshots desktop + narrow, live agent reply on Sarah's box, login → reload → WS
reconnect, SW cache bump). Scope flags are per slice.

- **R1 — The dock.** Sidebar gone; bottom dock Home · Channels · Work · Studio ·
  System; each tab's pages become chips at the top of the surface; chat/composer is
  present as the steering surface. *Static-only.* Extra gate: switching tabs
  mid-stream does not drop the WebSocket conversation.
- **R2 — Needs-you cards.** Approvals as ask/confirm cards — in Work (top), with the
  dock badge, fed by the existing approvals API. *Static-only.* Gate: provoke a real
  approval (a policy-gated tool call), approve once and reject once, read both back
  in the audit log. **Pulled ahead of the Home brief on purpose**: the brief displays
  this queue, so the queue's presentation is proven before it gets a prettier frame.
- **R3 — Home brief.** Brief Hand (Scout pattern, scheduled) writes items that are
  projections of real records only (approvals, kv submissions, schedule results,
  lead state); Home renders Found / Did / Needs-your-call; the brief also posts into
  the main Channels conversation. Leads board appears in Work (bundled Lead hand).
  *Static + a Hand (playbook/config), no backend.* Gate: the brief runs overnight
  unattended; every item on the morning screenshot traces to a record the director
  can open; an empty day renders an honest empty brief.
- **R4 — Side panel.** The slide-over component: side chats (session list + second
  live conversation) and side cards (detail inspector for approvals, leads,
  submissions, contacts). Sessions page demoted into the panel. *Static-only.*
  Gate: side chat streams while the main chat streams; both survive a page reload.
- **R5 — Channels consolidation.** Chat + Comms merged into one surface, one
  conversation renderer, composer + context chips. *Static-only; highest Alpine-state
  risk in the plan — own gate, no other slice in flight alongside it.*
- **R6 — Surfaces engine v1.** kv surface-definition convention + the generic block
  renderer in Studio + the surface-builder Hand. *Static page + Hand.* Gate: from
  Channels, the owner asks for a board; it appears under Studio, survives a daemon
  restart, and can be deleted by asking. Demonstration surface: the **SEO board**
  (Scout-pattern hand maintains it) — the owner's SEO candidate, delivered as a
  spun-up surface, which is the whole thesis in one proof.
- **R7 — Forms graft.** Per FORMS-RESEARCH §7, unchanged: Forms Hand cloned from the
  Lead hand, definitions/submissions in kv, public page on Cloudflare Pages with
  D1 + Queue, on-box pull-on-wake sync (a script beside the daemon, **not** a Fang
  backend change), Forms page in Studio with the Forms module panel (D) — the first
  per-module panel. Gate: the full asleep test — submit while the box sleeps; on
  wake it is in Submissions, deduped on re-delivery, contact resolved, draft held
  in Needs you.
- **R8 — Contacts.** Knowledge-graph-backed contacts surface in Work: list, detail,
  notes (StaxCloud Records shape), resolve-or-create wired from Forms and Comms.
  *Static page on existing REST.* Gate: a form submission creates a contact; a
  second submission from the same person updates it instead of duplicating; a note
  the owner types in the UI is quoted back by the agent in chat.
- **R9 — SMS module.** Beta scope is **agent-mediated**: an SMS Hand works the
  existing Dell modem service (staxbox-mms) through its API with the agent's native
  HTTP tools — inbox surface in the SMS module panel (D), threads as conversations,
  sends as tool calls with delivery read-back. *Static surface + Hand + connector
  config; no Fang backend.* Gate: text the shop line from a real phone; thread
  appears; reply from Fang; delivery confirmed on the phone.
- **R10 — First run + demotions.** The wizard leaves the nav: first login opens a
  Channels conversation where the agent interviews the owner and sets the shop up
  (every write through approvals). Logs and Runtime finish their demotion into
  System → Advanced. Settings shrinks to plain sections. *Static + Hand.* Gate: a
  fresh instance (staging home) goes from first login to a configured shop —
  name, hours, one playbook active — in one conversation, zero settings screens.

**Beta gate:** all six beta criteria above, demonstrated end-to-end on the pilot
box in one sitting, screenshots + read-backs filed. Then the product-layer
conversation (tenancy, provisioning, billing) starts — with a working product in
hand, not before.

### Scope-law amendments (the only ones)

1. **webchat.rs include-list exception — APPROVED, narrow.** From R7 on, new static
   page files may be added to the `include_str!` list in webchat.rs. Pure additions
   to the include list only; no logic changes; the diff is reviewed line-by-line in
   the slice's gate. Rationale: grafted surfaces (Forms, Contacts) need page modules,
   and forcing them into the existing monolith files would make the eventual split
   worse, not cleaner.
2. **Public unauthenticated POST endpoint in routes.rs — NOT approved.** The
   Cloudflare relay design (R7) makes it unnecessary; do not reopen unless the
   relay proves out as a real-world failure, with evidence.
3. **Native SMS channel (a Rust crate in openfang-channels) — NOT approved for
   beta.** R9's hand-mediated route is the beta answer. A native channel is a
   post-beta director item, judged on R9's operational evidence.
4. **Monolith split — deferred past beta.** It stays in the plan (it is the
   long-term maintainability floor), but it no longer gates any beta slice. The
   api.js canary duty for upstream absorption continues regardless.

## F. The reliability case — and what could prove it wrong

### Why this gets to a reliable StaxCloud faster

- **The deploy is one file.** StaxCloud's standing wound is merged-but-not-deployed:
  work spread across services, boxes, and 13k-line files, landing days after it
  merges (the Dell sat on the Oct 29 build while merges piled up). Fang is a single
  binary with the entire frontend embedded; a slice deploys as one file swap with
  the previous binary sitting beside it as an instant rollback. Proven twice already
  today: Slice 1 and the branding pass both went from build to live-proved at
  fang.sefer.team in hours, with login, health, agent reply, and WebSocket all read
  back.
- **The hard machinery is inherited, not rebuilt.** Scheduler, approvals, sessions,
  workflow engine, triggers, metering, durable SQLite — StaxCloud is still growing
  several of these; Fang ships them today, and upstream maintains them. Monthly
  absorption replaces a whole category of owned bugs.
- **The grafts ride data, not services.** Forms and Contacts are JSON in kv and the
  knowledge graph, written durable-before-ack, idempotent by primary key. There is
  no new daemon to fall over, no sync protocol to invent — the failure surface of
  each graft is a playbook and a page.
- **The scope law caps the blast radius.** Static-only slices cannot break the
  kernel; the one approved backend touch is an include list. Most of the road to
  beta physically cannot regress the agent.

### Top 3 risks

1. **Upstream is pre-1.0 and not ours.** OpenFang is v0.6.9; a monthly absorption
   can bring breaking API or static changes that stall slices — or, if upstream
   stalls entirely, we inherit a large Rust workspace we never budgeted to
   maintain. Mitigation: the pin + staging absorption + api.js canary already in
   Verdict #1; the fork keeps every StaxCloud addition fork-side (hands, pages,
   kv conventions) so even a frozen upstream leaves a working product. Residual
   risk is real and is the price of the head start.
2. **The Alpine monolith ceiling arrives early.** index_body.html is 5,411 lines
   behind one global store; R4 (two live conversations) and R5 (merged Channels)
   pile state onto exactly the fragile part, and the monolith split is deferred
   past beta by this very verdict. If state bugs (stale panes, dropped WS
   reconnects) start eating slice time, the split gets pulled forward mid-beta —
   the riskiest slice, done under pressure. Mitigation: R5 is isolated with its
   own gate for this reason; if R4's gate shows store-level flakiness, stop and
   re-plan before R5, don't push through.
3. **Playbooks are discipline, not code.** The brief, Forms processing, the SMS
   inbox, dedup — all ride on Hand playbooks executed by a model, on a kernel that
   validates none of it, with an in-memory trigger registry that forgets on
   restart. The failure shape is StaxCloud's original trust wound: a brief that
   invents a "needs you," a submission quietly dropped, a duplicate contact.
   Mitigation: R3's projection rule (brief items must trace to records), the
   schedule-sweep backstop behind every trigger (already the Forms design), and
   gates that test the miss cases (asleep submission, re-delivery, restart)
   rather than the happy path. This risk never fully closes; it is managed per
   slice or it manages us.

---

*Filed by the plan director (second mind), 2026-11-01. Binding on the reskin loop
until the owner or a later verdict amends it. Next director touchpoints: R5's gate
(state-risk review) and the post-beta product-layer pass.*
