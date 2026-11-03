# KIMI AUDIT — OpenFang / StaxCloud full-surface UX/UI audit — 2026-11-03

**Commissioned by:** Shawn Lowe, 2026-11-03 09:33 CST ("Leads are still broken. That's just one spot that I've noticed." — order: search EVERY surface for UX bugs, UI bugs, and incomplete parts).
**App under audit:** the live OpenFang app at https://fang.sefer.team, Round A build (binary b8dd9dfe…), in the owner's configuration (dark theme).
**Reviewer:** Kimi K3.1 Pro via OpenRouter direct — exact slug `moonshotai/kimi-k3.1-pro`, resolved from OpenRouter's live model list at run time. 10 review calls (one per surface group), 122,635 prompt + 136,916 completion tokens, **total spend $1.56** on the vaulted builder key (env-injected only, never stored). Criteria: the design-review suite staged at ~/openfang-build/skills/ (better_interface / better_ui / better_typography / better_colors / better_layout / better_accessibility / better_writing / impeccable) + DIRECTOR-VERDICT-3 (HIDE LIST) + DIRECTOR-VERDICT-4 (glance rules, navigation law, plain language).
**Captures:** 44 phone-width screenshots from the bench 6T (Wi-Fi adb, TWA `ai.tattoostax.fang`, dark theme), filed under `screenshots/kimi-audit-2026-11-03/`, plus the owner's own screenshot under `screenshots/owner-flags/`. Every finding below was cross-checked against the captures firsthand; Kimi is the reviewer, not ground truth. Items the captures do not support are marked as such in §12.
**Posture:** READ-ONLY audit. No records written, no approvals actioned, no sends, no config changes, no daemon/job/sidecar touches.
**Not capturable in this pass:** (a) the sign-in screen — the bench device is signed in and signing out is a state change outside a read-only audit; (b) a *live pending* approval card — no approval was pending at capture time (0 pending, independently confirmed); the decided-state cards were captured instead (07, 08).

**Severity:** S1 = broken, misleading, or raw machinery on an owner surface. S2 = real usability/consistency defect. S3 = polish.
**Classes:** `visual` (UI), `ux` (flow/copy/truth), `incomplete` (missing or stock parts).
**Scope mapping:** RB = Round B (Boards) · RC = Round C (Leads + cleanup) · RD = Round D (Texts + Connections) · RE = Round E (Forms) · RF = Round F (Advanced honesty) · H15 = Step 1.5 (Home) · AW = activation window (in flight 2026-11-03) · POL = polish pass · NEW = not in any current scope.

---

## Finding #0 — owner-witnessed, 2026-11-03 09:33 CST

**Evidence:** `screenshots/owner-flags/2026-11-03-0933-owner-leads-shows-stock-contacts.png` (sha256 ee3a17fc…). The owner's phone: the Leads tab renders the stock Contacts page — white cards overlapping in a broken grid, black-on-white against the dark theme, showing the 4 test-era contacts (John Doe, Marta/Riley Testcase, Wanda Testlead). His dock renders correctly above the Android nav bar (dock-inset proof: settled positive).
**Reproduced exactly on the bench phone** in this audit: capture `14-leads-contacts.png`. Findings L-1…L-11 below.

---

## 1. Home & chat with Stax
Captures: `01-home-initial.png` (light theme, first launch), `03-chat-raw-toolcall-and-tick.png`, `04-home-top.png`, `41-home-raw-toolcall-full.png`, `42-home-top-final.png`.

- **H-1 · S1 · incomplete · NEW** — **A raw tool call is rendered as a chat message.** The assistant bubble contains the full `memory_store` JSON verbatim: `{"name": "memory_store", "parameters": {"key": "brief/2026-11-03", "value": "{\"date\": …", "status": "ready"}}}`, escaped quotes and all (03, 41). Right: a tool call emitted as text is never rendered as a message; the brief shows as a brief or not at all.
- **H-2 · S1 · incomplete · NEW** — **The kernel's autonomous-tick prompt is rendered as the owner's own bubble**: "[AUTONOMOUS TICK] You are running in continuous mode. Check your goals, review shared memory for pending tasks, and take any necessary actions. Agent: stax" (03, 41, 42). Right: internal prompts never enter the owner's transcript.
- **H-3 · S1 · incomplete · NEW** — **Stax's reply narrates the fleet**: "There are no pending tasks in shared memory. The list of running agents includes 39 agents, each with a unique ID, state, and model." Agent counts, IDs, models, and "shared memory" on the product's face violate One Face (03, 42). Right: "Nothing is waiting right now," in one voice.
- **H-4 · S1 · ux · AW** — **The brief card contradicts the transcript on the same screen.** The card says "Today's brief isn't in yet. It lands here each morning," while the conversation below holds the Nov 3 brief with `"status": "ready"` (04 vs 41). The composed brief was emitted as text (H-1) and never stored. Right: the card renders the brief, or plainly says the save failed — never both stories at once.
- **H-5 · S1 · incomplete · H15** — **No "Set up my studio" action exists on Home**, although no setup/profile record exists on the live box — and the Needs-you row therefore lies: "Nothing needs you right now" while setup is outstanding (04, 42). No greeting either ("What's next, Shawn?" is absent in this state). Right: one clear setup action ahead of the conversation until setup exists.
- **H-6 · S2 · visual · POL** — **The transcript scrolls under the fixed composer**; at rest the tick bubble's last line is sliced by the composer boundary (42). Same class as T-6 / F-5: scroll areas need bottom inset above fixed bars. Right: full bubble + rounded edge rest clear of the composer.
- **H-7 · S3 · visual · POL** — **Send-button contrast**: the ↑ glyph is dark teal on a muted dark-teal circle, weak against the dark field (04, 42). Contrast ratio not measured — flagged visually. Right: ≥3:1 non-text contrast for the control.
- **H-8 · S3 · incomplete · NEW** — **Duplicate failure notices sit in the transcript**: "That didn't go through. Give it a moment and send it again." appears twice, stacked, unexplained (01). Right: one notice, with what failed and what happened next.

**Sound here (do not regress):** mascot large/centered, single teal accent, brief empty-state copy is honest in isolation, "Ask Stax" composer, four-tab dock fully above the nav bar.

## 2. Work
Captures: `05-work.png`, `06-work-scrolled.png`, `07-work-approved.png`, `08-work-all.png`.

- **W-1 · S1 · incomplete · Known (Verdict 4 §3 — no round letter assigned yet)** — **Work is the approvals queue only.** Heading "Needs you" + Refresh + filter chips + empty state. No Front desk card, no "Decisions, current work and results", no Current work / Finished accordions, no counts (05; 06 proves nothing exists below). The page the verdict specified was never built.
- **W-2 · S1 · ux · (with W-1)** — **Decided work still wears pending language.** Under All/Approved the heading stays "Needs you"; both REJECTED cards end "forms is asking first · Reply draft held for your call" — on cards rejected 9h earlier — and the bare "9h ago" never says what happened then (07, 08). Right: outcome copy with the decision and its time ("Rejected by you · Reply not sent · 9h ago").
- **W-3 · S1 · ux · (with W-1)** — **Attribution breaks One Face**: the empty state says "When a helper wants to do something sensitive…"; card footers name the engine agent "forms" (05, 08). Right: only Stax asks.
- **W-4 · S2 · visual · (with W-1)** — **The draft body is the card headline**: the full reply renders as one wall of large bold text with no summary line, preview hierarchy, or collapse (08). Right: person + one-line summary as the headline; full draft on expansion.
- **W-5 · S2 · visual · RB (Part 3)** — **The booking URL breaks mid-token** across lines inside the draft ("…book/L" / "7VAHB1TPFGN2/start") and reads as body text (08). Right: a labelled link ("Booking page") with ellipsis, full destination in detail. Already scoped in ROUND-B-BRIEF Part 3.
- **W-6 · S2 · incomplete · NEW** — **A customer-ready draft carries a template placeholder**: the Marta draft is signed "Best regards, [Your Name]" (08). Right: drafts reach the queue signed and complete, or not at all.
- **W-7 · S2 · incomplete · RC (cleanup)** — **The queue's only records are test drafts** (Wanda Testlead, Marta Testcase) — the operational surface holds fixtures, not work (08).
- **W-8 · S3 · visual · POL** — Selected filter chips put white text on light teal (weak contrast, ratio unverified), and the chip row wraps with "Expired" stranded alone on a second row (05, 07, 08). (Kimi framed the row as a chip-wall law violation; the chips are a settled case-by-case exception — the defects are the contrast and the wrap, not the chips' existence.)
- **W-9 · S3 · visual · POL** — The second card's bottom edge is clipped by the fixed dock in the All view (08). Global class with H-6.

## 3. Boards
Captures: `09-boards-list.png`, `10-board-canvas.png`, `11-board-canvas-scrolled.png`, `12-board-crew.png`, `13-board-crew-scrolled.png`, `32-canvas-entry.png`.

- **B-1 · S1 · incomplete · RB** — **Raw JSON on the Designs board**: the DESIGNS block renders `index {"designs":[]}` — the exact `JSON.stringify` fallback Verdict 4 ordered deleted (glance rule 2: raw JSON on an owner surface is a build failure) (10). Right: "0 designs" as a count line or the rule-6 empty state.
- **B-2 · S1 · incomplete · RB** — **The designed board set does not exist.** The list holds only "Canvas" and "Your crew". There is no Fargo Tattoo SEO board (the verdict's model citizen) and no Saturday Walk-ins board (09).
- **B-3 · S1 · incomplete · RB** — **No Next actions list ends either board** (glance rule 4). Both boards end at "Want changes? Ask Stax — boards are kept by your team, not by hand." (11, 13).
- **B-4 · S1 · incomplete · RB** — **A sentence sits in a stat slot**: headline "see list below" over "Designs stored" (glance rule 1) (10).
- **B-5 · S1 · ux · RB** — **"Your crew" exposes the roster and points at a ghost**: "The full helper roster is still under Channels — this is just who starts on your team." Channels contains no roster (the drawer holds one Inbox row); "helper roster" is hide-list vocabulary (12).
- **B-6 · S2 · incomplete · RB** — **A label sits in the second stat slot**: headline "Needs-you queue" over "Approvals waiting" (rule 1) (10).
- **B-7 · S2 · incomplete · RB** — **Badges outside the closed set**: HOW IT WORKS rows carry GATE / GATE / RULE pills (rule 3 permits Waiting · Doing · Done · Needs you only) (10, 11).
- **B-8 · S2 · ux · RB** — **Red "Delete board" button in every board header** (10, 12). Verdict 4 orders it out of the header. (Kimi praised the button's clarity as a destructive control; the project law still removes it from the header — see §12.)
- **B-9 · S2 · visual · RB** — **Board list cards show block counts** — "Canvas — 5 blocks", "Your crew — 4 blocks" — with no headline number and no freshness (rule 5) (09).
- **B-10 · S2 · visual · RB** — **One destination, two names, one screen**: header chip "Canvas" above the board heading "Designs" (10).
- **B-11 · S2 · writing · RB** — **Board copy narrates the machinery**: "Layered tattoo designs from the Designer hand. Every design listed here is a real record in shared memory; previews are rendered from the stored bundles, never invented." (10). Right: "Saved tattoo designs and their previews appear here."
- **B-12 · S2 · incomplete · RB** — **The crew board contradicts itself and holds no live values**: stat "4 / On your crew" sits over a five-item "YOU ASKED FOR HELP WITH" list; the other stat slots hold phrases ("Tattoo studio / Business", "As things happen / Brief"); it is a setup recap, not a live board (12, 13).
- **B-13 · S3 · writing · RB** — Footer "…kept by your team, **not by hand**" — "hand" is an engine term (11, 13).
- **B-14 · S3 · visual · RB/POL** — The two stat cards touch with a pinched double border instead of the standard card gap (10).

## 4. Leads — the Contacts surface (finding #0 family)
Captures: `14-leads-contacts.png`, `15-contact-open.png`, `16-contact-open-scrolled.png`, `17-add-contact.png`; owner evidence in §Finding #0.

- **L-1 · S1 · visual · RC** — **The card grid is broken**: four white/light cards of differing heights overlap in a ragged grid on the dark theme; Marta's card covers its neighbours; names and emails run to or past card edges ("Riley Testcase" clipped at the edge) (14, 17). Owner-witnessed (finding #0).
- **L-2 · S1 · incomplete · RC** — **Leads is the stock address book, not the pipeline**: no stages (New · Talking · Waiting on an artist · Booked · Resting), no per-stage counts, no temperature, no All · Shawn · Leni filter. The tab says Leads; the page says Contacts (14).
- **L-3 · S1 · incomplete · RC** — **No lead can be worked here**: the detail has no stage, artist, waiting-on-whom, or next action; the creation form captures Name/Email/Phone only — nothing a lead decision needs (15, 17).
- **L-4 · S2 · visual · RC (+ POL family)** — **Unthemed native form controls**: the search field, all three add-contact inputs, and the note textarea are raw white boxes on the dark theme (14, 16, 17). The same family recurs in the Texts reply box (23) and the in-app form preview (28) — one systemic theming gap in the module CSS.
- **L-5 · S2 · incomplete · RC** — **Submissions render as raw key dumps** in the detail: lowercase `email:` / `idea:` / `name:` / `phone:` / `placement:` lines, with the field ORDER differing between the two submissions on the same screen (15, 16). The Forms module's own submission cards (27) prove the composed alternative exists in the same app.
- **L-6 · S2 · ux · RC** — **"Last seen: May 20, 2024" contradicts the same screen**, which lists a submission dated Nov 1, 2026 (15).
- **L-7 · S2 · writing · RC (cleanup)** — **Source debris as data**: "Came in via: example", "May 20, 2024 – example" (15).
- **L-8 · S2 · incomplete · RC (cleanup)** — **The entire address book is test fixtures**: John Doe, Marta Testcase, Riley Testcase, Wanda Testlead (14). No real lead exists on the live instance yet (import is Round C).
- **L-9 · S3 · writing · POL** — Programmer pluralization: "2 form(s)" on cards (14, 17); same habit in Forms ("3 submission(s)", 26).
- **L-10 · S3 · ux · RC** — Phone formats disagree: "5550001111" on a card vs "701-555-0119" in a detail (14, 15); the add-contact panel has placeholder-only labels and no Cancel/Close (17).
- **L-11 · S3 · visual · POL** — The note textarea renders in a serif-like face unlike the UI font (16); detail content clips mid-glyph under the sticky module header (16).

**Sound here:** the contact detail view itself is dark-themed and grouped; submissions are newest-first; the note placeholder copy ("healed well, prefers Leni, allergic to latex…") is a genuinely good example.

## 5. Drawer / side card
Captures: `18-drawer.png`, `19-drawer-channels.png`, `24-drawer2.png`, `25-drawer-studio.png`, `30-drawer-status-paused.png`, `33-drawer-system.png`, `39-drawer-open.png`, `40-drawer-bottom.png`.

- **D-1 · S1 · ux · RD (wording) + NEW (source)** — **Stax's status line flips with nothing changing.** "Text replies: You approve" (teal dot) in captures 18, 19, 25, 33 and on Home (42); "Text replies: Paused" (grey dot) in 30 and 39 — five reads across ~20 minutes of a read-only audit, no setting touched. The pill follows an instantaneous agent state (the watchdog flap), so the owner's one status signal cannot be trusted. Verdict 4 assigned the pill's *wording* to Round D; the flapping *source* is new.
- **D-2 · S2 · ux · NEW** — **Chat rows are indistinguishable**: four rows read identically "Earlier conversation · Nov 2" — no title content, preview, or time (18, 40). Verdict 4 §5.2 derives titles from first messages for new sessions; the visible list is still a wall of identical rows.
- **D-3 · S3 · writing · POL** — "Show all 11" never names what it counts (18, 40). Right: "Show all 11 conversations".
- **D-4 · S3 · visual · POL** — The last chat row sits faded and clipped at the drawer's bottom edge at rest, with no scroll cue (19).

**Sound here (do not regress):** the drawer composition matches the design exactly — wordmark, TEAM as people (Stax · Shawn Lowe · Leni Bee), CHANNELS (one Inbox row) / STUDIO (Forms · Library · Contacts · Canvas) / SYSTEM (Settings · Connections), glyph-tier discipline, OWNER footer (Report a bug · Sign out) present and reachable (40).

## 6. Texts
Captures: `20-texts-inbox.png`, `21-texts-agent.png`, `22-texts-thread.png`, `23-texts-thread-scrolled.png`.

- **T-1 · S1 · visual · RD** — **The thread list has no layout**: three cards at three different content widths (~27% / ~44% / ~82%), light cards on the dark theme, previews clipped at card edges, timestamps floating centred (20). This is Verdict 4 §5.1's named defect — one full-width row layout — still live.
- **T-2 · S1 · incomplete · RD** — **The "Agent" tab opens the stock Side chats panel on the sms agent's sweep session**, not a conversation with Stax: header "Side chats", Chats/Cards chip rows, a session chip named by raw ID fragment "**Chat 5e6d54**", a "LIVE" badge, and the sweep's own transcript (21). See T-3/T-4 for its contents.
- **T-3 · S1 · incomplete · RD** — **The panel's transcript exposes the engine**: the agent narrates a database key — "Since there is no value found for the key 'attention/sms', it means that there are no unanswered inbound texts." (21).
- **T-4 · S1 · incomplete · RD** — **Cron prompts pose as owner messages, and wordless entries render as furniture**: a large teal bubble contains only "Texts sweep" (the sweep trigger, styled as if the owner typed it); two tall outlined rectangles render completely empty (21). The same pattern recurs in Forms (29).
- **T-5 · S1 · incomplete · RC (cleanup)** — **Engineering test traffic is the inbox's content**: previews read "Approval-gate test — please ignore" and "R12 zombie-draft test - approving this once must never send it twice."; the thread itself contains "Bridge test from Stax: the Texts module on the new system is now connected…", "R12 fault-injection test – the bridge should adopt this draft, not duplicate it." (20, 22, 23).
- **T-6 · S2 · visual · RD** — **Bubble geometry is content-sized and inconsistent**: short outbound messages are narrow right-side rectangles with text flush to the edges; long ones span the full card width; inbound messages have no bubbles at all (22, 23).
- **T-7 · S2 · ux · RD** — **The reply composer exists only at the very bottom of the scrollback** — the initial thread view shows history with no reply affordance; the composer ("Write a reply – it waits in Needs you before anything is sent" + "Hold reply for approval") appears only after scrolling past every message (22 vs 23). The copy itself is honest and should be kept.
- **T-8 · S2 · ux · RD** — **An Outbox section under the composer duplicates the thread**: the bridge-test message appears in the conversation marked delivered AND again in Outbox with a DELIVERED pill (23).
- **T-9 · S3 · visual · RD** — A number-only thread's monogram renders as a bare "**2**" (20); the thread header prints the number twice — big, then small directly beneath (22).
- **T-10 · S3 · incomplete · RD** — A photo message renders as the text line "📷 Photo"; no image is shown (23). (Kimi rated the labelled placeholder acceptable communication; it still is not the photo.)
- **T-11 · S3 · record · RC (cleanup)** — The thread record holds two identical delivered greetings one minute apart ("Hi! What would you like help with?", Oct 19 6:14 PM and 6:15 PM) (22). October history from before the approval-gate fixes — a record observation, not a current renderer defect.

**Sound here:** delivery state is printed in words ("– delivered"), timestamps are chronological, "Hold reply for approval" is a large honest target.

## 7. Forms
Captures: `26-forms-landing.png`, `27-forms-submissions.png`, `28-forms-preview.png`, `29-forms-agent.png`. Public page: §10.

- **F-1 · S1 · incomplete · RE** — **My Forms is a read-only dead end**: one form card ("Say hello — 5 fields – 3 submission(s)"), a Public form link, Preview/Submissions buttons — and no way to create or edit. The owner's ruled builder (InkStax-feel inline blocks) is Round E; today the surface can only look (26).
- **F-2 · S1 · incomplete · RD/RE (shared panel)** — **The Agent tab is the same stock side-chat panel as Texts** (T-2 family): "Chat ad7695" raw session chip, "Sweep for new form submissions" rendered as a giant owner bubble, one-line replies in oversized cards, two tall empty rectangles (29).
- **F-3 · S2 · writing · RE/POL** — Landing copy breaks One Face: "Want a new form, or changes? **Ask the Forms helper** — the Agent tab below." There is no "Forms helper"; there is Stax (26).
- **F-4 · S2 · ux · RE** — **Two doors to the same rooms on one screen**: the card's Preview/Submissions buttons duplicate the dock's Preview/Submissions tabs (26).
- **F-5 · S2 · writing · RE** — Submission status is pipeline jargon: every card wears a "**PICKED UP**" pill — a word from the intake machinery, not from the owner's vocabulary, and not one of the plain status words (27).
- **F-6 · S3 · visual · NEW** — An unexplained "**1**" badge rides the Submissions dock tab in every Forms view, including while Submissions is the open view (26, 27, 28). Nothing on any screen says what it counts.
- **F-7 · S3 · visual · POL** — The third submission card is cut off at the fixed dock (27) — global class with H-6.

**Sound here (do not regress):** submission cards are the best-composed records in the app — real field labels ("What are you thinking of getting?", "Where on you?"), values, timestamps, a Contact line; the Preview is honestly framed ("This is a test — submitting saves a test submission your team can see" / "Send test submission") (27, 28).

## 8. Library & Canvas entry
Captures: `31-library.png`, `32-canvas-entry.png`.

- **LB-1 · S2 · incomplete · NEW** — **Library lists the boards, not a shelf**: its only rows are "Your crew — Saved board" and "Canvas — Saved board". No designs, no files, no dates — and it gives Boards content a second home under another name, contradicting the designed shelf ("Designs and files Stax saves for the shop land here") and one-home-per-destination (31).
- **LB-2 · S2 · incomplete · Known (Canvas app slice owed)** — **Canvas has no surface of its own**: the drawer's Canvas row lands on the Designs board (32 is byte-for-byte the board of capture 10). By design until the Canvas app ships — recorded so the gap is explicit.
- **LB-3 · S3 · visual · POL** — Library's header is the only module header without a Refresh button (31 vs 20/26/36).

## 9. Settings · Connections · Advanced
Captures: `34-settings.png`, `35-connections.png`, `36-advanced.png`, `37-advanced-scrolled.png`, `38-advanced-helpers.png`, `38b-advanced-helpers-tips.png`.

- **S-1 · S1 · ux · RD** — **Connections lies**: "Nothing is connected yet. Stax can set up texting, chat apps, and email for you." — on the same morning the Texts module shows delivered messages (22, 23) and Forms shows collected submissions (27). Verdict 4 §5.3's named defect, still live: the page reads the empty kernel channel registry instead of the real sidecar connections.
- **S-2 · S2 · incomplete · RF** — **The platform's name leaks in Advanced**: the agent console's composer placeholder reads "Message **OpenFang**… (/ for commands)" (38). Advanced is the machinery corner by design, but the owner never bought a product called OpenFang.
- **S-3 · S3 · incomplete · RB (Part 1 family)** — **The tip rotator renders raw i18n keys**: "tips.commands" in one read, "tips.think" in another, while neighbouring tips resolve to real strings ("/model to switch models") (38, 38b). A live symptom of the dead i18n framework Round B Part 1 deletes.
- **S-4 · S3 · writing · NEW** — Version line mislabels the product: Settings footer and the Advanced footer both read "StaxCloud **0.6.9**" — the upstream engine's version presented as StaxCloud's (34, 37).
- **S-5 · S3 · ux · (observation)** — Settings shows no current values: Shop details, "What Stax checks with you first", and Spending limit all defer to "Ask Stax" without showing the shop's name/hours, the current approval posture, or the cap (34). The agent-first pattern is deliberate; the total absence of state on a Settings screen is a tension worth a design call, not a clear defect.
- **S-6 · S3 · ux · RF** — Advanced still offers "**Step-by-step setup**" (36, 37) — the stepper Verdict 3's setup conversation superseded; two doors to setup remain.
- **S-7 · S3 · visual · RF/POL** — Advanced console polish: the first history bubble is clipped under the header controls; the composer placeholder wraps and clips at the field's bottom edge; Stop/Uninstall put white text on light salmon (weak contrast, ratio unverified) (38, 38b).
- **S-8 · S3 · incomplete · RF** — A raw model slug is an owner-visible control in the console: the selector chip reads "moonshotai/kimi-k2-09…" (38). Inside Advanced, machinery is allowed; the label is still a fingerprint of the engine room, and it names k2 while the crew's deep-work seat is K3.1-class — which model that agent actually ran is **unverified** from the UI.

**Sound here (do not regress):** the Advanced landing is honestly framed ("The full controls behind StaxCloud, kept as they were. Most changes are easier by asking Stax.") and every demoted console is present behind it; Settings' list is plain, grouped, and consistent; the duplicated Advanced row is gone from the Settings list (Verdict 4 §3 holds).

## 10. Public form page (customer-facing)
Captures: `43-public-form.png`, `44-public-form-bottom.png` (fang-forms Worker, rendered on the bench phone).

- **P-1 · S3 · ux · NEW** — **The promise and the form disagree**: the intro says "Shawn reads every one of these and replies personally," but Email and Phone are both optional — a customer can send a lead with no reply route at all (43, 44).
- **P-2 · S3 · visual · POL** — The header mark is a generic circular-arrows (sync) glyph in a teal circle — not the shop's reaper mark or a Fargo Tattoo monogram (43); field borders are faint white-on-white (43, 44).
- **P-3 · S3 · ux · NEW** — The customer-facing address is a `workers.dev` subdomain, not a shop domain (43).

**Sound here (do not regress):** this is the best-composed surface in the audit — persistent labels, required asterisks only where required, warm plain copy, a full-width "Send it over" submit, and the shop's name and address in the footer.

---

## 11. Consolidated defect table (severity order)

| ID | Sev | Class | Defect | Evidence | Scope |
|---|---|---|---|---|---|
| H-1 | S1 | incomplete | Raw `memory_store` tool-call JSON rendered as a chat message | 03, 41 | NEW |
| H-2 | S1 | incomplete | [AUTONOMOUS TICK] kernel prompt rendered as the owner's bubble | 03, 41, 42 | NEW |
| H-3 | S1 | incomplete | Stax narrates the fleet: "39 agents, each with a unique ID, state, and model" | 03, 42 | NEW |
| H-4 | S1 | ux | Brief card says "isn't in yet" while the transcript holds the brief marked "ready" | 04 vs 41 | AW |
| H-5 | S1 | incomplete | No "Set up my studio" action; "Nothing needs you right now" is false while setup is outstanding | 04, 42 | H15 |
| W-1 | S1 | incomplete | Work = queue only; no Front desk card, Current work, or Finished sections | 05, 06 | Known, unassigned |
| W-2 | S1 | ux | REJECTED cards keep pending copy ("held for your call"); heading stays "Needs you" | 07, 08 | Known, unassigned |
| W-3 | S1 | ux | "When a helper wants…" / "forms is asking first" — One Face broken | 05, 08 | Known, unassigned |
| B-1 | S1 | incomplete | Raw JSON `index {"designs":[]}` on the Designs board | 10 | RB |
| B-2 | S1 | incomplete | Designed board set missing: no SEO board, no Saturday Walk-ins | 09 | RB |
| B-3 | S1 | incomplete | No Next actions list on either board | 11, 13 | RB |
| B-4 | S1 | incomplete | Sentence in a stat slot: "see list below" | 10 | RB |
| B-5 | S1 | ux | Crew board exposes "the full helper roster… under Channels" (no roster exists there) | 12 | RB |
| L-1 | S1 | visual | Contacts grid: white cards overlapping, text clipped at edges (finding #0) | 14, 17 + owner | RC |
| L-2 | S1 | incomplete | Leads tab = stock Contacts; no stages/temperatures/counts/filter | 14 | RC |
| L-3 | S1 | incomplete | Detail + creation form carry no lead fields (stage/artist/next action) | 15, 17 | RC |
| D-1 | S1 | ux | Status pill flips "You approve" ↔ "Paused" with nothing changing | 18–42 series | RD + NEW |
| T-1 | S1 | visual | Thread list: three cards, three widths, light on dark, previews clipped | 20 | RD |
| T-2 | S1 | incomplete | Texts "Agent" tab = stock Side chats panel on the sweep session; chip "Chat 5e6d54" | 21 | RD |
| T-3 | S1 | incomplete | Agent narrates the kv key 'attention/sms' in chat | 21 | RD |
| T-4 | S1 | incomplete | "Texts sweep" cron prompt as an owner bubble; tall empty bubble rectangles | 21 | RD |
| T-5 | S1 | incomplete | Inbox content is engineering test traffic (approval-gate / R12 / bridge tests) | 20, 22, 23 | RC |
| F-1 | S1 | incomplete | My Forms is read-only; no create/edit path exists | 26 | RE |
| F-2 | S1 | incomplete | Forms "Agent" tab = same side-chat panel; chip "Chat ad7695"; sweep bubble | 29 | RD/RE |
| S-1 | S1 | ux | Connections: "Nothing is connected yet" while Texts delivers and Forms collects | 35 vs 22/27 | RD |
| W-4 | S2 | visual | Draft body is the card headline — wall of bold text, no summary hierarchy | 08 | Known, unassigned |
| W-5 | S2 | visual | Booking URL breaks mid-token inside approval cards | 08 | RB (Part 3) |
| W-6 | S2 | incomplete | Draft signed with the placeholder "[Your Name]" | 08 | NEW |
| W-7 | S2 | incomplete | The Work queue's only records are test drafts | 08 | RC |
| B-6 | S2 | incomplete | Label in a stat slot: "Needs-you queue" | 10 | RB |
| B-7 | S2 | incomplete | GATE / RULE badges outside the closed set | 10, 11 | RB |
| B-8 | S2 | ux | Red Delete board button in the board header | 10, 12 | RB |
| B-9 | S2 | visual | Board list shows block counts, no headline number or freshness | 09 | RB |
| B-10 | S2 | visual | "Canvas" header vs "Designs" heading on one screen | 10 | RB |
| B-11 | S2 | ux | Board copy narrates storage ("shared memory", "stored bundles", "Designer hand") | 10 | RB |
| B-12 | S2 | incomplete | Crew board self-contradiction: "4 on your crew" over a 5-item list; phrase-stats | 12, 13 | RB |
| L-4 | S2 | visual | Unthemed white native inputs across Contacts (search/add/note) — family in Texts + Forms too | 14, 16, 17, 23, 28 | RC + POL |
| L-5 | S2 | incomplete | Submissions render as raw lowercase key dumps, field order inconsistent | 15, 16 | RC |
| L-6 | S2 | ux | "Last seen: May 20, 2024" vs a Nov 1, 2026 submission on the same screen | 15 | RC |
| L-7 | S2 | ux | "Came in via: example" source debris | 15 | RC |
| L-8 | S2 | incomplete | The whole address book is test fixtures | 14 | RC |
| D-2 | S2 | ux | Four chat rows identically titled "Earlier conversation · Nov 2" | 18, 40 | NEW |
| T-6 | S2 | visual | Outbound bubbles content-sized, text flush to edges; inbound has none | 22, 23 | RD |
| T-7 | S2 | ux | Reply composer only at the very bottom of the scrollback | 22 vs 23 | RD |
| T-8 | S2 | ux | Outbox section duplicates messages already shown in the thread | 23 | RD |
| F-3 | S2 | ux | "Ask the Forms helper" — One Face broken in Forms copy | 26 | RE |
| F-4 | S2 | ux | Preview/Submissions reachable from card buttons AND dock tabs on one screen | 26 | RE |
| F-5 | S2 | ux | Submission status word "PICKED UP" is pipeline jargon | 27 | RE |
| LB-1 | S2 | incomplete | Library lists the two boards as "Saved board" — Boards' second home, no shelf | 31 | NEW |
| LB-2 | S2 | incomplete | Canvas has no surface; drawer entry lands on the Designs board | 32 | Known (Canvas slice) |
| S-2 | S2 | incomplete | "Message OpenFang…" placeholder leaks the platform name in Advanced | 38 | RF |
| H-6 | S3 | visual | Transcript clipped under the fixed composer at rest | 42 | POL |
| H-7 | S3 | visual | Send (↑) glyph low contrast on its muted circle (ratio unverified) | 04, 42 | POL |
| H-8 | S3 | incomplete | Duplicate "That didn't go through…" notices stacked in history | 01 | NEW |
| W-8 | S3 | visual | Selected chips: white on light teal; "Expired" stranded on its own row | 05, 07, 08 | POL |
| W-9 | S3 | visual | Card bottom clipped by the fixed dock (All view) | 08 | POL |
| B-13 | S3 | ux | "kept by your team, not by hand" — engine term in board footer | 11, 13 | RB |
| B-14 | S3 | visual | Stat cards touch with a pinched double border | 10 | RB/POL |
| L-9 | S3 | ux | "(s)" pluralization: "2 form(s)", "3 submission(s)" | 14, 26 | POL |
| L-10 | S3 | ux | Phone formats inconsistent; add-form has placeholder-only labels, no Cancel | 14, 15, 17 | RC |
| L-11 | S3 | visual | Note textarea in a serif-like face; detail clips under the sticky header | 16 | POL |
| D-3 | S3 | ux | "Show all 11" doesn't name what it counts | 18, 40 | POL |
| D-4 | S3 | visual | Last chat row faded/clipped at the drawer's bottom edge, no scroll cue | 19 | POL |
| T-9 | S3 | visual | Number-thread monogram is a bare "2"; thread header prints the number twice | 20, 22 | RD |
| T-10 | S3 | incomplete | Photo message renders as "📷 Photo" text; no image | 23 | RD |
| T-11 | S3 | incomplete | Duplicate delivered greeting in the thread record (Oct 19, pre-gate era) | 22 | RC |
| F-6 | S3 | visual | Unexplained "1" badge on the Submissions dock tab in all Forms views | 26, 27, 28 | NEW |
| F-7 | S3 | visual | Third submission card cut off at the fixed dock | 27 | POL |
| LB-3 | S3 | visual | Library header lacks the Refresh button other modules have | 31 | POL |
| S-3 | S3 | incomplete | Tip rotator renders raw i18n keys "tips.commands" / "tips.think" | 38, 38b | RB (Part 1) |
| S-4 | S3 | ux | "StaxCloud 0.6.9" — upstream engine version presented as the product's | 34, 37 | NEW |
| S-5 | S3 | ux | Settings rows show no current values (observation; agent-first pattern is deliberate) | 34 | — |
| S-6 | S3 | ux | Advanced still offers the superseded "Step-by-step setup" | 36, 37 | RF |
| S-7 | S3 | visual | Advanced console: bubble clipped under header; placeholder wraps/clips; salmon-button contrast | 38, 38b | RF/POL |
| S-8 | S3 | incomplete | Raw model slug on the console's selector chip ("moonshotai/kimi-k2-09…") | 38 | RF |
| P-1 | S3 | ux | "replies personally" promise vs both contact fields optional | 43, 44 | NEW |
| P-2 | S3 | visual | Generic sync-glyph as the shop's mark; faint white-on-white field borders | 43, 44 | POL |
| P-3 | S3 | ux | Customer form served from a workers.dev address, not a shop domain | 43 | NEW |

**Counts: 78 findings — S1 ×25, S2 ×27, S3 ×26. By class: incomplete ×32, ux ×25, visual ×21.**
Scope tally (a finding can sit in two scopes; counted once by its primary): Round B ×15 · Round C ×12 · Round D ×12 · NEW ×12 · Polish ×11 · Round E ×4 · Round F ×4 · Known-but-unassigned (Work build) ×4 · Step 1.5 ×1 · Activation window ×1 · Canvas slice ×1 · unscoped observation ×1.

## 12. The incomplete-parts list (what is missing or still stock)

1. **The Leads pipeline** — the entire surface (stages, temperatures, artist, next actions, stats) does not exist; the stock Contacts page stands in its place (L-1…L-3).
2. **Work's composition** — Front desk card, Current work and Finished sections never built (W-1).
3. **Two of the three designed boards** — Fargo Tattoo SEO and Saturday Walk-ins do not exist (B-2).
4. **Next actions on boards** — absent from every board (B-3).
5. **The Canvas app surface** — only the interim Designs board exists (LB-2).
6. **The Library shelf** — no designs/files content model renders; board records stand in (LB-1).
7. **The Forms builder** — My Forms is read-only; creation/editing has no UI (F-1).
8. **The Nov 3 morning brief record** — composed but never stored; its only trace is raw JSON in the chat (H-1, H-4).
9. **Home's setup action and greeting** in the not-set-up state (H-5).
10. **A truthful Connections projection** — the page reports the empty kernel registry, not the working sidecars (S-1).
11. **A real Texts list layout** — §5.1's one-layout fix not yet applied (T-1).
12. **Module "Agent" conversations** — both modules open a stock side-chat panel onto sweep sessions instead of a Stax conversation (T-2, F-2).
13. **Real data on the live instance** — contacts, inbox, and the Work queue hold only test-era fixtures pending Round C cleanup + import (L-8, T-5, W-7).

## 13. Cross-check record (Kimi vs the captures)

- **Sustained:** every Kimi finding in the ten group reviews is visible in the named captures, with the adjustments below. Kimi's sharpest independent catches: the brief-card/transcript contradiction (H-4), "Show all 11" naming nothing (D-3), the crew board as a setup recap (B-12), and the public form's promise/optionality mismatch (P-1).
- **Adjusted — Work filter chips:** Kimi scored the row as a NO CHIP WALLS violation. The chips are a settled case-by-case exception in this project; the sustained defects are the selected-state contrast and the stranded wrap (W-8, S3), not the chips' existence.
- **Adjusted — duplicate greeting (T-11):** Kimi's "ensure one approval produces one send" reads it as a current defect. The messages are October 19 record history, predating the approval-gate fixes; kept as record debris, not a renderer defect.
- **Adjusted — model selector (S-8):** Kimi flagged the slug's mid-version truncation. Truncation itself is conventional; the sustained point is the raw slug's presence on an owner-reachable control.
- **Not sustained — "← All boards duplicates the Boards tab" (Kimi, boards group, ×2):** an in-surface back link is conventional navigation, and the one-home law targets destinations with two homes (e.g., Contacts in dock + drawer), not back links. Rejected, with this reason recorded.
- **Disagreement noted — Delete board (B-8):** Kimi's CLEAN note praises the button as "clearly destructive". Verdict 4 explicitly orders the header to lose it; the law governs, the finding stands.
- **Kimi's CLEAN notes** are folded into the "Sound here" lines per section — the drawer's composition, the Forms submission cards, the Advanced landing's honesty, and the public form's construction are genuinely good and should not be regressed by the fix rounds.

## 14. Observations held below finding grade

- **First-tap swallowing (UNVERIFIED):** throughout the capture session, first synthetic taps were intermittently consumed (drawer hamburger, contact cards, dock tabs, module buttons) and a second tap landed. adb-injected taps are not fingers, so this is **not** counted as a defect — but Round 3 recorded the same class on real hardware ("hamburger tap-toggle dead on device", "minimally repaired" in Round A), so a human-touch pass over the same controls is worth ten minutes before beta.
- **Sign-in screen:** not captured (bench device signed in; read-only audit). Its last owner-seat evidence is from Round 3 and pre-dates Round A.
- **Light theme:** capture 01 shows the app under a light system theme (the app follows Auto). The overlapping-card and unthemed-input defects in Contacts/Texts are theme-independent in kind (they are unstyled components, not dark-mode misses), but the audit's primary configuration is the owner's: dark.

## 15. Method note

Captures were taken on the bench 6T against the LIVE app between 09:36 and 10:07 CST, 2026-11-03, in the owner's configuration (dark theme via the device's night mode, app Appearance = Auto). Navigation was touch-only (taps, edge drag, swipes); nothing was submitted, saved, approved, or sent. The Kimi reviews ran 10:11–10:40 CST against those captures. Status-pill reads (D-1) are timestamped by capture order within that window. The daemon, jobs, sidecars, and records were not touched; a separate activation window was running on the same box and was kept out of this audit's path entirely.
