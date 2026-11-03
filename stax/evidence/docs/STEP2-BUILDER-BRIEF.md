# Step 2 Builder Brief — SIDE CARD (Director Verdict #3, Step 2)

You are Claude Opus 5.5, running in OpenCode on the Victus build machine, in
`~/openfang-build/repo` — the TattooStax/openfang fork, branch `stax-ux`, HEAD
`eceb05e` (the Step 1 commit, local, unpushed). The product is the OpenFang
pilot for Fargo Tattoo (owner: Shawn Lowe), live at https://fang.sefer.team on
Sarah's box. The plan of record is Director Verdict #3; this brief is Step 2 of
it, and it is your complete instruction set. One slice. Nothing from Steps 3–6
starts here.

Step 1 (HOME) is built and live: the conversation sits in its own home
template, the dock is Stax · Work · Boards · Leads · Channels, and hide-list
markup is gated off home. This step changes ONE component: the drawer (side
card). Its shell — the hamburger, the left drawer, open/close behavior — is
Slice A chrome and it stays. Its CONTENT is replaced wholesale. What the
drawer renders today is two layers of the prepend era stacked in one panel:
a Slice A header block (wordmark, a TEAM block with a hardcoded status, section
links, a tiles strip, a footer) pasted over the untouched R4 side panel (a
"Chats / Cards" tab row with raw session titles, a "TEAM — Your team is
empty" block with an Invite button, WORK / SETTINGS / SYSTEM link lists,
"About OpenFang", Home / Sign out). Neither layer survives as-is. You are not
reskinning that content and you are not adding a third layer on top of it —
you are replacing the drawer's contents with the composition in §3, and
demoting everything else per §4.

## 1. Keying and launch — already proven, do not redo it

- You were launched with your credential in the environment only: the parent
  released the builder key from staxvault (`geturl` for origin
  https://openrouter.ai), piped it over SSH (never in argv, never printed),
  and injected it as `OPENROUTER_API_KEY` into your process environment.
- Env-only auth is PROVEN live on this exact setup (2026-11-02): with zero
  stored credentials, `opencode run -m openrouter/anthropic/claude-opus-5.5`
  answered on this key. OpenCode's provider loads off the env var alone.
- `~/.local/share/opencode/auth.json` is intentionally empty (0 credentials).
  NEVER run `opencode auth login`, never write the key (or any credential) to
  any file, config, commit, or log. If a run ever reports a missing provider,
  stop and report it — do not attempt a login flow.
- Your model string is `openrouter/anthropic/claude-opus-5.5`. No builder
  config file exists or is required; the `-m` flag is the selector.

## 2. The wiring law — absolute

Presentation only. The kernel, hands, sidecars (pull-sync, the Dell bridge),
workflows, schedules, and kv data DO NOT CHANGE. Concretely:

- Edits live in `crates/openfang-api/static/**`. The single permitted touch
  outside it: pure `include_str!` additions in `webchat.rs` if a new static
  file must be embedded. Everything else in the tree is read-only to you.
- Everything the drawer shows is a projection of real records or real state —
  the lead agent's real sessions, the same live status source Home reads,
  the shop's actual people. Never invented, never model-minted.
- Renames are labels only: internal page keys, API fields, and record keys
  keep their upstream names. Every drawer destination targets an EXISTING
  page key / surface — the same target its dock tab or module already uses.
  No new routes, no new data, no new machinery.
- Demote, never delete: anything removed from the drawer stays reachable
  under System → Advanced (§4), fully functional.
- No stacking: new content REPLACES or GATES stock content. Nothing gets
  prepended on top of stock markup. The finished drawer is ONE composition,
  not layers.
- One Face holds in the drawer too: the owner sees Stax and people.
  Specialist agents, hand names, and the stock fleet never appear here in
  any form.

## 3. The job — Step 2: SIDE CARD, content replacement, same component

### 3.1 The target composition — in order, and nothing else

1. **Wordmark + shop.** "StaxCloud" wordmark with "Fargo Tattoo" as the
   shop line. Quiet; this is a header, not a hero.
2. **TEAM — people, not agents.** Section label "TEAM". Three rows, each an
   avatar/initial mark + name:
   - **Stax** — with its live status in plain words as a second line (§3.3);
   - **Shawn Lowe**;
   - **Leni Bee**.
   No other rows. No "Your team is empty" state — these are the shop's
   actual people, already the product's own facts. No Invite button.
3. **Expandable sections** — three, in this order, each a header row
   (one-family icon + label + expand/collapse affordance) over plain child
   rows (icon + label, labels always visible):
   - **CHANNELS** → **Inbox**
   - **STUDIO** → **Forms**, **Library**, **Contacts**
   - **SYSTEM** → **Settings**, **Connections**
   The owner's reference is StaxCloud's EXPANDED drawer: children visible
   without hunting, sections collapsible by tap. Each child navigates to
   the surface its dock tab / module already opens (Inbox → the Channels
   surface; Forms → the forms panel; Library → the boards/library surface;
   Contacts → the contacts page; Settings → the settings page; Connections
   → the connections page). Wire to the existing targets you find in the
   shell's navigation code — do not invent routes.
4. **Side chats — as conversations.** A "Chats" list under the sections:
   the lead agent's existing sessions, most recent first, each rendered as
   a conversation title from its session record. Tapping one opens that
   conversation on Home. ONE start action: **"New chat"**, which starts a
   fresh conversation with Stax through the existing session machinery.
   Nothing else from a session record renders — no agent names, no session
   ids, no timestamps-as-titles, no kernel fields. Specialist sessions
   never appear.
5. **Tiles strip.** One strip of app tiles (icon + label, the same icon
   family as the dock and the section rows) mirroring the drawer's own
   destinations: Inbox · Forms · Library · Contacts · Settings. This is
   the owner's tiles idea in its drawer form — a second, visual path to
   the same places, duplicating nothing else.
6. **OWNER footer.** Section label "OWNER". Two rows: **Report a bug** and
   **Sign out** — both keep their existing Slice A behaviors (Report a bug
   opens the Stax chat; Sign out ends the session). Nothing else in the
   footer.

### 3.2 Disposition of what the drawer renders today

Every current item is accounted for — replaced, removed, or demoted.
Nothing current survives merely because it was already there:

- Slice A header block (wordmark, TEAM block, section links, tiles strip,
  footer) → REPLACED by §3.1's real implementation. Its hardcoded status
  text dies with it (§3.3). Its two footer behaviors (Report a bug, Sign
  out) are wiring and are preserved.
- "Chats / Cards" tab row → GONE from the drawer. Chats are §3.1 item 4.
  The Cards view is demoted to System → Advanced with the rest of the R4
  panel machinery — demoted, not deleted.
- Raw session titles listed across all agents → REPLACED by §3.1 item 4
  (lead's sessions only, as conversations).
- "TEAM — Your team is empty" + Invite → REPLACED by §3.1 item 2. Invite
  is gone from the owner surface.
- WORK section (Your studio, Board tasks, Leads, Channels) → REMOVED from
  the drawer. Those places live on their dock tabs; the drawer does not
  duplicate them. The surfaces themselves are untouched.
- Standalone SETTINGS row → becomes SYSTEM → Settings (§3.1 item 3).
- SYSTEM list (System health, Usage, Setup, Activity) → Settings and
  Connections are the owner-facing SYSTEM children (§3.1 item 3). Health,
  Usage, Activity, and the Setup item demote to System → Advanced. (Setup
  itself is a conversation now — Step 1 retired the stepper's front-door
  role; the drawer does not re-offer it as a page.)
- "About OpenFang" → REMOVED from the owner surface; demoted to Advanced
  with the rest. Upstream branding is not owner content.
- "Home" link → REMOVED. The dock covers it.

### 3.3 Status: one source, one wording — plus two inherited notes

- The Slice A drawer carries a FIXED status string ("Stax: Automatic").
  The Home status pill reads real state and can say something else — the
  two already contradict each other on the live app. That ends here: the
  TEAM Stax row's status line binds to the SAME state source, the SAME
  expression the Step 1 home header pill renders. No status literal may be
  hardcoded anywhere in the drawer. One source, one wording, everywhere
  status appears.
- Two Step 1 inheritances are recorded here so this step does not entrench
  them. Do NOT solve either in this slice; do not build drawer behavior on
  top of either:
  - Step 1's setup turns are scripted rather than agent-conducted.
  - The Home pill's exact wording is builder-inferred, not owner-approved.
  Your obligation is only the binding above: wherever the drawer shows
  status, it reads what the pill reads.

## 4. The hide list — binding (Verdict #3, correction D3)

None of the following may be visible in the drawer or on any owner surface
after this slice. All of it is demoted to System → Advanced (the Helpers
view Step 1 established), never deleted:

- the drawer's agent-picker chip wall — this is YOUR surface and this
  step's primary hide-list item; after this slice no agent roster, chip,
  or picker exists in the drawer in any form;
- the agents-page header actions: **+ New Helper**, **Stop All**;
- the helper catalog ("OR START A NEW HELPER" and the stock roster);
- the stock Home cards: **Create Agent**, **Configure Provider**,
  **Browse Skills**;
- raw activity rendering: AGENT MESSAGE items, failure strings ("agent loop
  failed"), record dumps (e.g. `name=sms, parent=None`);
- fleet lists on any landing (people appear as people in the drawer's
  TEAM, nowhere else);
- per-page stock headers duplicating the shell header;
- raw session dumps and kernel-worded lists generally — the R4 panel's
  machinery (tab row, Cards view, cross-agent session lists) leaves the
  drawer whole and lands in Advanced intact.

A slice that leaves a hide-list item owner-visible is NOT done, whatever
else it ships.

## 5. Visual spec

- **Figma:** file "OpenFang — StaxCloud UX Plan", page **Screens**,
  **screen 5** (side card). You have no Figma access; the composition
  below IS screen 5, in words:
  - The drawer is a single calm column on the StaxCloud canvas, surface
    background, hairline border on its open edge. Same composition in
    light AND dark.
  - Top: wordmark + shop name, small and quiet.
  - TEAM: three people rows — round avatar/initial marks, names in the
    primary text color; Stax's row carries the status line beneath the
    name in the muted color, in plain words.
  - Sections: CHANNELS / STUDIO / SYSTEM as muted small-caps-style
    section headers with chevrons; children as full-width rows, icon +
    label, generous hit height. Section accent colors: Channels
    `#3f6486`, Studio `#885264`, System `#576373`.
  - Chats: conversation titles as simple rows, one line, no metadata
    clutter; "New chat" as the section's one clear action.
  - Tiles strip: a neat row/grid of rounded tiles (icon over label),
    visually consistent with the InkStax-desktop tile feel the owner
    pointed at — neat, clean, organized, a little bit delightful, never
    dashboard-grey.
  - OWNER footer pinned at the bottom: Report a bug, Sign out.
  - The owner's 15:08 screenshot of the old drawer (correct content for
    one screen-height, then the stock chip wall and empty space) is the
    anti-spec: no second layer, no fleet, no cavernous gaps.
- **Tokens (StaxCloud's, adopted literally — already in the codebase):**
  canvas `#f4f2ec` / dark `#0c0c0e`; surface `#fff` / `#121214`; border
  `#d9d4c8` / `#2a2a2e`; text `#1b1a17` / `#e8e4dc`; Stax teal `#146e68`
  (dark accent `#5cbcae`); Channels `#3f6486`, Studio `#885264`, System
  `#576373`. Spacing scale 4–40; radii 6 / 10 / 14 + pill; 44px minimum hit
  area; typeface DM Sans.
- Tagline where branding appears: "Run your business. Grow your business.
  One intelligent system."
- Reference feel: StaxCloud's side card and Muse's drawer — people and
  places, in plain words. "It should not feel like a dashboard; it should
  feel like Muse or chat." (owner)

## 6. Design skills — read before you edit

Staged copies sit at `~/openfang-build/skills/` when you are launched
(source: `~/workspace/custom-skills/` on the parent VM). Mandatory pre-reads:

- `frontend_design/SKILL.md` — Anthropic's art-direction discipline; the
  anti-template baseline, applied here to a component, not a page.
- `impeccable/reference/craft-floor.md` — the floor every UI edit must
  clear (the rest of `impeccable/reference/` is the fix-and-polish
  playbook set; this slice — replacing an existing component's content
  without breaking its shell — is squarely its territory).

Reference library, consult as needed: the jakubkrehel set (`better_interface`,
`better_ui`, `better_typography`, `better_colors`, `better_layout`,
`better_writing`, `better_accessibility`) and `ui_ux_pro_max` (palettes,
type pairings, style data — reference only, not a driver).
If the staged copies are absent, say so in your report and proceed on §5 —
do not stall the slice over it.

## 7. The stylish bar

The owner's word is **stylish**: distinctive art direction, not a tidy
wireframe. The drawer is the owner's daily reach — it should feel like
opening a well-made app, not a control panel. Spend the boldness on the
tiles strip and the wordmark moment; keep the people and section rows
quiet and disciplined; cut any decoration that does not help the shop
owner get somewhere. A drawer that could belong to any admin tool has
failed this bar even if every box in §3 is ticked.

## 8. Build, stage, handoff — deploy is the parent's step

- Build on the Victus only: `OPENSSL_NO_VENDOR=1 cargo build --release
  -p openfang-cli` (full build ~14 min; static files embed at compile
  time, so template changes need the rebuild). Verify completion from
  the build log's exit marker, not process greps.
- Stage first: fresh HOME, throwaway port, no LLM key — open the drawer
  there and exercise it (sections expand, chats list, tiles navigate,
  footer actions wired) before anything ships.
- **You do not deploy.** The parent deploys to Sarah's box with the
  standing discipline (previous binary kept as rollback, sha256 verified
  before swap, graceful `./openfang stop`, restart sourcing `./env` in
  `~/openfang-play`, exactly-one-process check, health local + public).
  For your awareness only: the live binary is Step 1's (sha256
  `29a8d4bf…`), and its rollback `openfang-pre-step1.bak` sits on the box.
  Do not touch Sarah's box, and never touch Sarah's StaxCloud (port
  3121) — a different product on the same box.
- Commit your work locally on `stax-ux` with a clear message. **Do not
  push.** Commits stay local until the parent reviews them.
- Leave handoff facts in your report: the built binary's sha256, the
  staging result, and exactly which staged build the parent is deploying.

## 9. The done-gate — the ONLY one

Fresh login on the live app; **phone-width and desktop screenshots of the
OPEN DRAWER**, filed beside Figma screen 5. The parent captures these at
the owner seat immediately after deploying your build — your job is to
leave a staged, verified build the parent can deploy as-is.

Your own report is engineering facts only: files changed, build result,
staging result, anything from §4 still visible that you could not gate,
the §3.3 status binding as implemented (which source, which expression),
anything unverified. You do not declare the slice done, and you never
describe deploys, byte counts, greps, or smoke checks as UX progress —
the screenshots are the only UX evidence, and the slice is reported to
the owner strictly as what they show.

## Later steps — owner notes

- **Step 3 — Work:** StaxCloud composition (Front desk card; Needs you /
  Current work / Finished) over existing wiring.
- **Step 4 — Channels as a room:** one conversation surface from home
  (the consolidation Verdict #2's R5 originally specified). This step's
  Inbox row already points at that surface; Step 4 recomposes the room
  behind it.
- **Step 5 — Boards and Leads:** recompose the existing pages to Figma
  screens 8–9.
- **Step 6 — Forms panel** (Figma screen 7). **Owner direction,
  2026-11-02: the form builder should feel like the InkStax form builder.
  In the owner's judgment the InkStax form builder looks cleaner than the
  StaxCloud form builder — "at least the block engine does." The InkStax
  block engine is the feel reference for the Forms build; examine it
  firsthand before that step, per the owner's examine-first process
  order.**

Each step starts only when the previous step's gate screenshots are on
file. That sequencing is binding, not advisory.

## Parent amendment (Stax, 2026-11-02, before launch)

Two scope questions the brief flagged are decided here:

1. **TEAM row taps.** The Stax row in TEAM opens the Stax card — the same
   card Home's avatar tap opens (the owner's standing Muse-pattern rule:
   the agent's avatar opens the agent's card). The Shawn Lowe and Leni Bee
   rows are plain people rows in this step: no tap behavior, no menus, no
   status beyond what §3 specifies.
2. **Tiles strip.** Contents stay tied to the drawer's own destinations
   (Inbox · Forms · Library · Contacts · Settings), as §3 specifies. The
   status tile and date widget from the owner's InkStax tile screenshot
   are NOT in this step — the owner marked that screenshot idea fuel,
   not gospel.

Step 1 gate status at this launch, for the record: fresh-login DESKTOP
captures of Home are on file and the hide list verified absent; the
builder's phone-width staging renders are filed at
`~/workspace/openfang-fork/screenshots/step1/` (VM side). The live
phone-width capture is the owner's to take on his own device and remains
open; this step proceeds under the owner's takeover directive, and any
Home defect his phone check surfaces queues as a fix ahead of Step 3.
