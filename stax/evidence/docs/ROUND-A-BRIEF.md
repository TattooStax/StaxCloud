# Round A — Navigation (2026-11-02)

Base: Round 3's deployed tree state — commits `d0d6789` (drawer gestures) + `f7bd958` (reaper branding) on `stax-ux`; remote head `a56dad9d` includes them. **Before anything else, confirm the base with `git log`: if `f7bd958` is not in the tree's history, STOP and report — do not build on a different base.** Presentation layer only: `crates/openfang-api/static/**` plus permitted webchat.rs include lines if a new static file must be served. No new machinery, no new routes, no kernel/hand/sidecar changes, no Cloudflare Worker changes. Standing builder rules: own browser self-check on staging in all four configs (phone 390×844 + desktop, dark + light); found/fixed + found/not-fixed lists; glyph icons through the single sprite, raster art as static assets. Rulings source: DIRECTOR-VERDICT-4.md §3 + §5 + §6 (Round A) and OWNER-NOTES-ROUND-A.md; the Ratchet binds this round — Round A is net-negative by construction.

## PART 1 — The dock is four

The bottom dock becomes **Stax · Work · Boards · Leads**, four wide tabs, nothing else.

1. **The Channels dock tab is REMOVED**, and with it the channels-page landing path: no owner-visible route lands on a "Channels" page as a destination. The conversation's only dock home is Stax. The Channels family (Inbox/Texts) lives only in the side card, reached from the drawer CHANNELS rows as today — the Texts module itself keeps working exactly as it does now; only its dock tab and landing path go.
2. No replacement fifth tab. Studio and Forms stay drawer families.

## PART 2 — Chip walls and duplicate paths out

1. **Every chip wall is deleted.** The Studio chip wall (Boards · Forms · Automations · Scheduler · Playbooks · Capabilities) and the Channels chip wall (Chat · Team traffic · Texts) are removed as components, everywhere they render. **Home and Work lose their top chip rows** wherever any still render. A section's sub-navigation lives in its module dock or the side card — never a chip wall, never both.
2. **Demoted, never deleted:** Scheduler · Automations · Playbooks · Capabilities lose their owner-level paths and live under **System → Advanced**, intact, alongside the stock consoles already there. Nothing in Advanced is removed or broken.
3. **The Texts module dock loses its Contacts button** — it becomes **Agent · Inbox · Done**. Contacts has exactly one path left: the drawer STUDIO Contacts row. (A thread still opens its own person's record from inside the thread — that is not a navigation path and stays.)
4. **"Done" is normalized:** every module dock's Done returns to **Stax (Home)** — Forms (today Done→Boards) and Texts (today Done→agents page) special cases are deleted; the System corner already behaves this way and does not change. One behavior, learned once.
5. **The Settings list loses its Advanced row.** The System module dock's Advanced tab is the only door to Advanced from the corner. The list keeps Appearance, its Ask Stax rows, Report a bug, Sign out, and the plain-words version line.
6. **Drawer Canvas row preselects the Canvas board** (interim, as Verdict 4 disposition 3): tapping Canvas in the drawer lands on Boards with the Canvas/Designs board already open, not on the board list. This is the last Boards path out of the card and is understood to be temporary — do not build anything around it beyond the preselect.
7. **Drawer scroll cue:** when drawer content continues below the fold, the drawer shows a bottom fade/cue; when the end of the single scroll is reached, no cue. (The scan found CHATS cut mid-row with no indication more exists.)

## PART 3 — Library v1: its own surface

The drawer STUDIO **Library row stops landing on Boards** and opens Library's own page.

- **What Library is:** the shop's records shelf — what the shop keeps. V1 is **one plain list, newest first, and nothing more**: saved designs (title + date, from the design record families Fang already holds), plus any saved surface/reference records the existing kv families carry.
- **What it reads:** the list is a projection over the existing kv snapshot — the same snapshot read the Boards renderer already performs — over the `surface/` family and the design record families. No new store, no new endpoint, no new primitive.
- **The honest limit, stated rather than papered over:** client files and reference material have no dedicated kv family yet. The v1 list shows what the records support today (designs and saved records); anything without records behind it does not get a fake section. The empty state says what will live there, in the verdict's words: *"Designs and files Stax saves for the shop land here."*
- Library is not Boards (no dashboards, no blocks) and not Contacts (no people). No sort/search machinery in v1 — one list.

## PART 4 — The title is "StaxCloud"

The served root document's title becomes **StaxCloud** — one line in the head template; every owner-visible surface that derives its title from it follows. The platform name leaves the app's public face. (The edge-served manifest is already StaxCloud-branded — do not touch the Worker or anything it serves.)

## PART 5 — Chat titles from the first message

New chats take their title from their first message: at the moment the first message is sent, the session's label is stored as that message's first line, trimmed to a few words — through the existing session-label mechanism (the labeled staging sessions prove it exists; use it, do not build a parallel one). The drawer's side-chats list and the history list then show the real title. Existing unlabeled sessions keep the honest "Earlier conversation" fallback — **no invented titles are backfilled**. New chat creation otherwise behaves exactly as today.

## PART 6 — Home composition: the mascot is the only top element

Owner direction (OWNER-NOTES-ROUND-A.md), on top of Round 3 — read the caution twice:

**CAUTION — Round 3 is settled, not reopened.** Round 3 shipped the reaper centerpiece, the drawer, and the gestures, and they are deployed. This part removes two redundant rows and applies the sheet composition. It does NOT redo the centerpiece, the avatar placements, the drawer, or any gesture. If a change here seems to require touching Round 3's gesture or drawer code, stop and report it as a machinery note instead of doing it.

1. **The Chat/Texts chip row on Home is removed** (with Part 2's chip-wall deletion — on Home it goes even though it renders as part of the page header furniture).
2. **The separate small "Stax" name/avatar header row on Home is removed.** Home currently stacks three headers — chip row, name row, centerpiece. After this round it stacks one: **the mascot**. Identity comes from the mascot itself. The top-left hamburger stays exactly where Round 3 left it — it is the drawer toggle, not a header row.
3. **The sheet floats beneath the mascot** (the Muse pattern the owner pointed at): the status pill, greeting, next action, and the conversation live on one raised sheet under the centerpiece — visually quiet, one focal point. The elements themselves keep their Round 3 order and behavior; this is composition (grouping, surface, spacing), not new content and not new controls.

## PART 7 — The traditional tiles land on their surfaces

The 12 owner-approved tiles (masters: `~/workspace/openfang-fork/icon-tiles/`, 512×512 PNG; provenance + 48px verdicts in its NOTES.md) wire into the surfaces they mark, under the icon-tier law: **colorful filled tiles at the outer level (dock, drawer section headers, a surface's own page mark); subtle single-tone glyphs on rows inside the drawer — the rows do not change.** Tiles are raster: serve display-size derivatives (128×128, generated from the canonical 512 masters) as static assets by the same mechanism as the brand assets; the 512 masters do not enter the statics at full size. **The brand mascot stays the canonical reaper files from Round 3** (centerpiece, avatars, drawer brand tile, sign-in mark) — the reaper *tile* below marks a destination, it does not replace the character art anywhere.

Wired in this round (each tile's one home):

| Tile | Destination | Placement |
|---|---|---|
| stamp | **Work** | dock tab |
| clipboard | **Boards** | dock tab |
| magnet | **Leads** | dock tab |
| bubble | **CHANNELS** | drawer section header |
| frame-rose | **STUDIO** | drawer section header |
| toolbox | **SYSTEM** | drawer section header |
| reaper | **Stax card** | the identity surface's page mark (TEAM Stax row still opens it; the row's own glyph stays subtle) |
| book | **Library** | the new surface's page mark (Part 3) |

Mapped but **not wired in this round** — their surfaces get their outer-level moment in their own rounds; forcing them in now would invent placements: **envelope → Inbox** (Round D, Texts), **links → Connections** (Round D), **contacts → Contacts** (its surface is reworked in Round C's wake, not A), **machine → Canvas** (the Canvas surface slice; also the set's one soft tile at 48px per NOTES.md — flagged there for a possible profile-silhouette redraw before it ships as a mark). Name all four in the round report as staged, not skipped.

The glyph sprite remains the single source for every glyph icon. Where a drawer header's colorful mark is replaced by its tile, the replaced sprite symbol is removed if nothing else references it — one home per thing applies to symbols too.

## PART 8 — Device-proven defect fixes (added 2026-11-02 ~20:50 CST, from the live 6T captures)

Round 3's staging gate passed behaviors that a real device then disproved. These three fixes are in this round's scope, with device proof required (below). Evidence: `screenshots/round3/live-6t/` (12 captures, hash-verified).

1. **The hamburger tap-toggle is dead on a real device.** On the bench 6T's Chrome, four taps on the hamburger (including a firm 150 ms hold) toggled nothing in either direction, and a tap on the drawer's dimmed background did not close it — while the left-edge swipe opened the drawer reliably and every row inside the drawer responded to taps. The dead surface is the gesture layer's own elements: the toggle button and the scrim. **Scope carve-out from Part 6's caution:** you ARE authorized to repair the tap path in the gesture layer — minimally. The drag/swipe mechanics, thresholds, and finger-follow behavior do not change; what changes is that a plain tap on the hamburger toggles the drawer and a plain tap on the scrim closes it, on touch devices as well as with a mouse. If the repair turns out to require redesigning the gesture handling rather than fixing the tap path, stop and report it as a machinery note instead.
2. **The docks sit below the visible viewport — in Chrome AND under the Android navigation bar.** On the bench device in Chrome, neither the main dock nor any module dock is visible — the page's visible area ends where Chrome's bottom toolbar begins. And the owner's own phone (21:38 CST, the installed WebAPK, screenshot filed with the round) shows the same dock reduced to a sliver above the Android navigation bar: in the WebAPK there is no browser toolbar, so the dock is being laid out into the system navigation area. **Owner's requirement, verbatim in substance: the default must work for both Androids — with a navigation bar and without one.** Anchor every dock (main dock + all module docks) to the visual viewport with dynamic viewport units, and clear the system inset through the viewport's own safe-area value (`viewport-fit=cover` + `env(safe-area-inset-bottom)`), which reads ~0 on a no-bar device and the bar's height on a bar device. **Do NOT hard-code a fixed bottom padding** — that trades a hidden dock on one configuration for a floating gap on the other, and fails the owner's both-configurations requirement.
3. **Work surface render defects** (from the first Work capture, `07-work.png`): (a) a long booking URL in an approval card overflows the card's right edge unbroken — long unbroken strings wrap inside their card; (b) a draft card's title renders a literal placeholder ("Draft reply to Marta Testcase (<slug>)") — a missing value renders as nothing, never as a placeholder token; (c) the "an agent is waiting for approval" toast appears while the approvals surface itself is already open — a surface does not toast over itself. All three are render rules in the existing surface code; the underlying records are test data and not yours to touch.
4. **Not in scope, noted so it is not papered over:** the status pill oscillates ("Paused" ↔ "You approve") because the texting agent's own state cycles. The pill is honestly reflecting that state — do not stabilize the words in the UI. It is a parent-side agent-health item.

**Work-count legibility — resolved by evidence before this round starts:** the 6T capture shows Work's count IS legible in words ("7 PENDING" beside the heading, plus the chip badge). The Gate's badge-in-words contingency below is therefore satisfied as-is: change nothing about the count's presentation.

## Gate (staging, final binary, all four configs)

- **Every disposition clicked, not assumed:** four dock tabs and no Channels tab; no chip wall on any surface (Home, Work, Forms, Texts, Boards photographed); Texts dock = Agent · Inbox · Done; Done returns Home from Forms, Texts, and System alike; Settings list has no Advanced row and Advanced still opens from the module dock; Scheduler/Automations/Playbooks/Capabilities reachable under Advanced and nowhere at owner level; Canvas row lands on the preselected board; drawer scroll cue appears when content continues and is gone at the end of the scroll.
- **Library:** the drawer row opens Library's own page (not Boards); the list renders from real records, newest first; empty state photographed if a family is empty.
- **Title:** the browser tab reads "StaxCloud" on the served document.
- **Chat titles:** a fresh chat, one message sent, the drawer shows the derived title; an old unlabeled chat still shows the honest fallback.
- **Home:** mascot is the only top element — no chip row, no name/avatar row; pill, greeting, action, conversation on the sheet beneath; **Round 3 re-verified intact** — hamburger toggles the drawer open AND closed, edge-drag opens with finger-follow, swipe/scrim/ESC close, drawer sections start closed, X still absent, reaper still the centerpiece uncropped at phone width.
- **Work capture:** Work photographed at phone + desktop, before and after, and filed with the round's evidence. (The first-ever Work capture was filed early by the Round 3 live pass — `screenshots/round3/live-6t/07-work.png` — and its count proved legible in words; see Part 8. This round's before/after pair supersedes it as the current record.)
- **Device gate (Part 8, on the bench 6T via adb from this machine — the phone is attached here):** with the staging build served to the phone's Chrome, prove with captures: an adb tap on the hamburger OPENS the drawer and a second adb tap CLOSES it; a tap on the scrim closes it; the main dock is fully visible on Home and the module dock fully visible on Settings, in Chrome, above the browser toolbar. **Both-configurations dock proof (owner's requirement): the dock captures are taken twice — once with the phone's three-button navigation bar enabled and once with gesture navigation enabled (Settings → System → Gestures → System navigation) — fully visible and tappable in both, no floating gap in the gesture configuration; restore the phone's original navigation mode afterward.** Staging-only proof does not pass Part 8 — the defects were staging-invisible. If the staging instance cannot be reached from the phone, or the navigation mode cannot be switched, say so in found/not-fixed rather than substituting desktop proof.
- **Non-regression (the Ratchet checklist, re-run whole):** Settings and Connections landings still plain lists; System module dock intact; vocabulary scans clean on owner surfaces (machinery words only inside Advanced); zero console errors beyond the known pre-existing noise (pre-login 401s, fresh-instance 404s for the brief/setup records). Crew 7 Running; cron table = 19 jobs with Forms sweep / Texts sweep / Morning Brief enabled; sweeps completing; approvals round-trip exactly once; brief readable; pull-sync green; port 3121 untouched.
- **Size ledger (Ratchet §1):** before-sizes of every static file this round touches are recorded at the base **before** editing (the ledger starts with this round and never resets); the report carries before/after per touched file and names every removal (the Channels tab + landing path, both chip-wall components, the Texts Contacts button, both Done special cases, the Settings Advanced row, the Home name row, replaced sprite symbols). Round A is net-negative by construction — if the final statics delta is not net-negative, the report names the trade explicitly or the round has not passed its gate.

## Commits and conduct

- **Two local commits minimum**, plain messages: (1) **structure** — Parts 1, 2, 3, 4, 5 and the tile wiring mechanics of Part 7; (2) **composition** — Part 6 (Home) and the tile placements' visual finish. More commits are fine; one squashed commit is not.
- **Presentation layer only.** Never rebuild harness primitives: a machinery need (a route, a tool, a record shape) is reported in found/not-fixed, never built. Surfaces are projections of agent work; controls are few and cleanly operable or absent.
- **Build + stage only.** No deploy, no push, no contact with the live instance or Sarah's box beyond the staging environment. Deploy is a separate parent step, after this gate.
