# OpenFang fork — StaxCloud UX reskin plan

Owner commission 2026-11-01 (Shawn): fork OpenFang, keep it working, make the UX match StaxCloud.
Director verdict 2026-11-01: **APPROVE-WITH-CHANGES** (conditions below are binding).

## Fork state (verified)
- GitHub fork: TattooStax/openfang (parent RightNow-AI/openfang), created 2026-11-01.
- Local: ~/workspace/openfang-fork/repo — origin = fork, upstream = RightNow-AI.
- Pin: tag `stax-base-0.6.9` at acf2587 (v0.6.9), pushed to the fork and read back via API.
- Sarah's running instance untouched: v0.6.9 binary on her box, port 4200, separate from her StaxCloud (3121). It is the proof target, never the dev target.

## Current frontend (verified by direct read)
- crates/openfang-api/static/, embedded via include_str! in crates/openfang-api/src/webchat.rs. No build step, no framework. Vanilla HTML/CSS/JS + vendored Alpine.js, Chart.js, marked, highlight.js, KaTeX.
- Monoliths: index_body.html 5,411 lines (all pages inline as Alpine templates), components.css 3,459 lines.
- 16 page scripts: overview, chat, agents, hands, skills, workflows, workflow-builder, scheduler, channels, sessions, approvals, comms, usage, logs, runtime, settings, wizard (+ app.js, api.js).
- Slice-0 grep (evidence/slice0-backend-refs.txt): backend Rust references NO page keys; coupling is the include_str! file list in webchat.rs only. routes.rs / server.rs / ws.rs are read-only for this project.

## Director conditions
1. UX-only scope: crates/openfang-api/static/** only. webchat.rs embedding change allowed in Slice 8 only. Any slice needing a routes.rs change stops and returns to the director.
2. Keep no-build vanilla + Alpine. No framework, no bundler, no Node toolchain on Sarah's box.
3. Tokens adopted literally from StaxCloud (tokens.css): canvas #f4f2ec/#0c0c0e, surface #fff/#121214, border #d9d4c8/#2a2a2e, text #1b1a17/#e8e4dc, Stax teal #146e68 (replaces indigo #6366f1), Channels #3f6486, Studio #885264, System #576373; spacing 4-40, radii 6/10/14+pill, 44px hit area, dock 56px, header 52px, DM Sans.
4. Renames are owner-facing labels ONLY — internal page keys, crate names, API fields keep upstream names (mergeability).
5. Upstream absorption monthly via staging, never mid-slice; api.js diff is the canary.
6. Prove-it per slice: staging first, before/after screenshots (desktop + narrow), live agent reply on Sarah's box port 4200, login->reload->WS reconnect check, service-worker cache bump. No read-back = not done, next slice does not start.

## Mapping (16 pages -> StaxCloud dock: Home · Work · Studio · Tools · System)
- Overview -> Home: brief cards Found / Did / Needs-your-call; charts demoted to Reports
- Chat + Comms -> Channels (home surface): one conversation surface, shared renderer, composer + context chips
- Sessions -> drill-in history inside a conversation (never top-level)
- Approvals -> Work / Needs-you: AppShell ask/confirm cards naming the exact action
- Agents -> Work / Team: "Helpers", plain role + status
- Hands -> Studio / Playbooks: starter library of specialist packages to turn on
- Workflows + Workflow-builder + Scheduler -> Studio / Automations (tabs: Automations / Scheduled)
- OpenFang "Channels" (= integrations) -> Connections (critical rename — in StaxCloud, Channels = conversations)
- Skills -> Tools / Capabilities: plain-language groups, manifests behind Advanced
- Usage/Analytics -> Work / Reports
- Logs -> Settings / Advanced / Diagnostics (not owner-facing; health status on Home only)
- Runtime -> Settings / Advanced / System status (not a page)
- Settings -> System surface, plain sections, Advanced collapsed at bottom
- Wizard -> first-run Setup flow, not a page

Never owner-facing as concepts: Runtime, raw Logs, raw Sessions, workflow JSON, skill manifests, kernel terms.

## Slices
0. Baseline: screenshot inventory all 16 pages, record live reply / approval / workflow on current binary. (Grep inventory done.)
1. Shell + tokens only: dock/header, --stax-* tokens, fonts, 44px targets, sidebar regrouped + plain renames incl. Channels->Connections. No page logic or page-key changes.
2. Needs-you: Approvals as ask/confirm cards under Work.
3. Home brief: Overview -> Found/Did/Needs-you; charts to Reports.
4. Channels consolidation: Chat+Comms merged; Sessions demoted. Highest Alpine-state risk — own gate.
5. Automations consolidation: Workflows+Builder+Scheduler; proof = a scheduled workflow actually fires.
6. Capabilities: Agents->Team, Hands->Playbooks, Skills->Capabilities.
7. Demotions: Logs+Runtime under Settings/Advanced; Settings reorganized.
8. Monolith split (internal, zero visual change): split index_body.html + components.css per-surface; webchat.rs embedding change permitted here only.
9. Setup + PWA: Wizard on AppShell primitives; manifest/SW versioning verified.

## Round A — completion (2026-11-02)

Deployed 2026-11-02 ~23:31 CST to fang.sefer.team. Code: HEAD `69f0e0c`
(7 commits on `f7bd958`). Live binary sha256 `b8dd9dfe…`; rollback on the
box: `openfang-pre-roundA.bak`. Evidence: `screenshots/roundA/` (350 files,
incl. both-navigation-mode device captures).

What landed:

- Navigation restructure per Director Verdict 4: the dock is FOUR —
  Stax · Work · Boards · Leads. Channels lives only in the side card;
  Boards only in the dock; chip walls and duplicate paths removed;
  Scheduler / Automations / Playbooks / Capabilities demoted intact to
  Advanced; "Done" returns Home everywhere; document title is "StaxCloud".
- Home composition: the mascot is the sole top element, the conversation
  a sheet beneath it; brief-first with the Needs-you row.
- Traditional tile set wired through the single sprite (8 of 12 tiles;
  envelope / links / contacts / machine staged for later rounds).
- Amendment 1 (dock vs. the Android navigation bar): `viewport-fit=cover`
  added so the docks' safe-area inset actually applies; bench-proven on
  the 6T in three-button and gesture modes. The non-zero-inset case in the
  installed WebAPK cannot be bench-proven — the owner-phone check after
  deploy is the outstanding gate.
- Amendment 2 (external-review items; both relayed review rounds are now
  closed): chat titles from the first message + date; the "Working on it"
  status resolves into the answer instead of persisting; links in replies
  are tappable, never break mid-word, and the app-download link renders as
  a button; Home hides "Set up my studio" once a setup-complete record
  exists (the live box has no `setup/profile` record yet — the behavior is
  staging-verified, and creating the record is the owner's setup
  conversation with Stax, never a faked record); the status-bar theme
  color follows the app theme (device-proven; the TWA wrapper's own
  `themeColorDark` value is a specified follow-up rebuild). A
  reply-brevity conduct rule was added to the stax hand (rule 12) and
  loaded at this restart.
- The same restart window carried the Security Gate 2 shell reduction
  (tool blocklist for the 13 running stock agents + 6 inactive hand
  shadows; post-restart census zero, functionally probed — see
  `docs/SECURITY-GATE-2.md`) and the Canvas designer hand's refreshed
  SKILL.md.

Size ledger: statics net +43,725 B for the round — code −11,831 B against
the owner-ordered tile assets (+55,556 B, the recorded exception class).
Queued as Round B's first ledger line: delete the dead i18n framework
(76 KB, unserved, never wired), which closes Round A net-negative.
