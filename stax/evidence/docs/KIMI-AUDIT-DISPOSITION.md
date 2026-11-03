# KIMI AUDIT — DIRECTOR DISPOSITION — 2026-11-03

**Input:** `KIMI-AUDIT-2026-11-03.md` — 78 merged findings (S1 ×25, S2 ×27, S3 ×26 per the audit's own tally; Kimi's 104 raw were deduped and cross-checked against captures before merging, with 2 adjusted, 1 rejected, 1 disagreement — those audit-level rulings stand and are not re-litigated here). Finding #0 (the owner's Leads screenshot) is evidence, not a finding; the audit's one rejected raw item ("← All boards duplicates the Boards tab") is outside the 78 and stays rejected for the audit's stated reason.
**Disposition classes:** **(a) IN-ROUND** — already in a named round's scope, cited. **(b) NEW** — not in any round's scope; assigned a home here with a one-line reason. **(c) REJECTED** — not a defect, reason stated. Plus two director-marked classes: **NEXT-BUILD** (director ruling: the two transcript-rendering defects ship in the next build, whichever round it is) and **SPECIAL** (H-3, H-5 — dispositioned on Job 2's firsthand evidence, §4–§5).
**Job 2 evidence** (read-only, firsthand, 2026-11-03): the deployed frontend source (served root document), the kv store read via API and directly from `~/.openfang/data/openfang.db` (read-only), `sessions`/`usage_events`/`audit_entries` tables. Full Job 2 report at §5.

---

## 1. NEXT-BUILD (director ruling — HIDE-LIST class, next build regardless of round)

| ID | Defect | Note |
|---|---|---|
| H-1 | Raw `memory_store` tool-call JSON rendered as a chat message on Home | Render layer: a tool call emitted as text is never rendered as a message. The stored-record half of this failure is H-4 (activation window, briefstore). |
| H-2 | The kernel's `[AUTONOMOUS TICK]` prompt rendered as the owner's own bubble | Render layer: internal prompts never enter the owner's transcript. Same root as T-4's bubble half (Round D) — a fix in the shared transcript renderer should be checked against the Texts/Forms panels at the same gate. |

## 2. Round B — Boards (brief: ROUND-B-BRIEF.md)

**(a) IN-ROUND (15):**

| ID | Brief section |
|---|---|
| B-1 Raw JSON on Designs board | Part 2.1 (the `kvRows()` `JSON.stringify` fallback is deleted) + §2.2 recomposition |
| B-2 Board set missing (no SEO, no Walk-ins) | Walk-ins = §2.5 composition. SEO = §2.4 — **flag:** the brief's §2.4 presumes an existing SEO board to re-check ("kept as-is"); the audit finds no SEO board on the live list (only Canvas + Your crew). The §2.4 re-check converts to a composition from the `surface/seo` record family if the board record is truly absent — the round's first read settles which. Home stays Round B either way. |
| B-3 No Next actions on boards | Glance Rule 4; composition in §2.2 (Designs) and §2.5 (Walk-ins) |
| B-4 Sentence in a stat slot ("see list below") | Part 2.1 Rule 1 (renderer) + §2.2 (stats recomposed from records) + §2.3 (playbook writer half) |
| B-5 Crew board exposes "helper roster… under Channels" | §2.2 copy-rewrite family; the crew board's own fate is B-12's flag below — whichever way it goes, the roster copy dies in this round |
| B-6 Label in a stat slot ("Needs-you queue") | Part 2.1 Rule 1 |
| B-7 GATE/RULE badges outside the closed set | Part 2.1 Rule 3 (render drop) + §2.2 (badges removed from the record) + §2.3 (playbook) |
| B-8 Red Delete button in board header | §2.6 (Delete leaves the header) |
| B-9 List cards show block counts | §2.6 ("5 blocks" metadata deleted) + Part 2.1 Rule 5 (headline number + freshness) |
| B-10 "Canvas" chip vs "Designs" heading | §2.2 (the board is Designs throughout after recomposition) |
| B-11 Board copy narrates the machinery | §2.2 (description copy rewritten — this exact text is named in the brief) |
| B-13 "not by hand" in board footer | Part 2 board copy (§2.2 rewrite extends to the shared board footer) |
| B-14 Stat cards touch, pinched double border | Part 2.1 (Boards renderer) |
| S-3 Tip rotator renders raw i18n keys | Part 1 (the dead-i18n deletion) — **flag:** the rotator resolves *some* tips to real strings, so Part 1's step-1 deadness re-verification governs: if the tips are served by the framework Part 1 deletes, the keys die with it; if a live strings path serves them, Part 1 STOPs on that reference and the keys are reported found/not-fixed with the strings fix named. Round B owns the outcome either way. |
| W-5 Booking URL breaks mid-token in Work cards | Part 3 (Work-card link treatment — explicitly scoped) |

**(b) NEW → Round B (1):**

| ID | Reason |
|---|---|
| B-12 Crew board self-contradiction ("4 on your crew" over a 5-item list; phrase-stats; a setup recap, not a live board) | Not in the brief: Verdict 4's board set is three (SEO · Designs · Saturday Walk-ins) and the brief names no crew-board work. Round B owns Boards, so the round's gate must disposition this board — retire it (it is the setup flow's receipt, see §5) or recompose it to glance law. It cannot ship as-is. |

## 3. Round C — Leads + cleanup

**(a) IN-ROUND (12):** L-1 (broken card grid — the pipeline rebuild replaces the surface), L-2 (Leads = pipeline: stages/temperatures/counts/artist filter), L-3 (lead fields on detail + creation), L-4 (unthemed native inputs — Contacts instances; the systemic module-CSS half is cross-noted to Round D/E instances), L-5 (submissions as raw key dumps), L-6 ("Last seen 2024" vs 2026 submission — projection truth), L-7 ("Came in via: example" debris — cleanup), L-8 (address book is test fixtures — cleanup + import), L-10 (phone formats; add-form labels/Cancel), T-5 (inbox content is engineering test traffic — cleanup), T-11 (duplicate Oct-19 greeting — record debris, cleanup; the audit's own adjustment stands), W-7 (Work queue holds only test drafts — cleanup).

## 4. Round D — Texts + Connections truth

**(a) IN-ROUND (12):** D-1 (status pill — wording is Round D's; the flapping *source*, which the audit tags NEW, is assigned here too: the director's standing Round D scope already includes re-deriving the pill from last-successful-sweep instead of instantaneous agent state), T-1 (thread list layout — Verdict 4 §5.1's named defect), T-2 (Texts "Agent" tab = stock side-chat panel on the sweep session), T-3 (agent narrates the `attention/sms` key — dies with the T-2 panel replacement), T-4 (cron prompt as owner bubble + empty rectangles — Round D surface; its bubble half shares H-2's renderer root, see §1), T-6 (bubble geometry), T-7 (composer only at scrollback bottom), T-8 (Outbox duplicates the thread), T-9 (monogram "2"; number printed twice), T-10 (photo renders as "📷 Photo" text), F-2 (Forms "Agent" tab = same shared panel — Round D leads the shared-panel replacement, Round E's instance cures with it), S-1 (Connections reads the empty kernel registry instead of the real sidecar connections — Verdict 4 §5.3's named defect).

## 5. Round E — Forms

**(a) IN-ROUND (4):** F-1 (My Forms read-only; the builder is Round E), F-3 ("Ask the Forms helper" — One Face copy), F-4 (two doors to Preview/Submissions on one screen), F-5 ("PICKED UP" jargon pill).

**(b) NEW → Round E (2):** F-6 (unexplained "1" badge on the Submissions dock tab — the tab is Forms' own chrome and Round E rebuilds this module; the badge names its count or goes), P-1 (public form: "replies personally" promise vs both contact fields optional — field requiredness is a form-definition decision and Round E owns the form surface end to end, public render included).

## 6. Round F — Advanced honesty

**(a) IN-ROUND (4):** S-2 ("Message OpenFang…" placeholder), S-6 (superseded "Step-by-step setup" still offered), S-7 (Advanced console polish — RF primary, polish pass secondary), S-8 (raw model slug on the console selector chip — the audit's unverified sub-point, which model that agent actually ran, carries as unverified).

**(b) NEW → Round F (1):** S-4 ("StaxCloud 0.6.9" — the upstream engine's version presented as the product's; version truth is the honesty round's brief, and the Settings-footer instance rides along).

## 7. The Work build — NEW standalone item

**(b) NEW → standalone "Work build" (4):** W-1 (Work = approvals queue only; the Verdict 4 §3 composition — Front desk card over Needs you / Current work / Finished accordions with counts — was never built and no round letter owns it), W-2 (decided cards wear pending copy — rides the Work build), W-3 (One Face attribution in Work copy — rides the Work build), W-4 (draft body as card headline — rides the Work build). W-5 and W-7 already have homes (Round B Part 3; Round C cleanup).

## 8. Step 1.5, Canvas slice, polish pass, standalone items

**Step 1.5:** H-5 was the audit's Step 1.5 tag — Job 2 (§9 below) proves the Home build is behaving as designed and the defect is a data state, not a build gap. Step 1.5 takes **no** findings from this audit; its existing scope (avatar tap → full-screen Stax) is unchanged.

**Canvas app slice (2):** LB-2 (Canvas has no surface; drawer lands on the Designs board — already-scoped standalone slice, recorded so the gap is explicit), LB-1 **(b) NEW → Canvas slice** (Library lists the two boards as "Saved board" — Boards' second home, no shelf; Library's real content is designs + files, which arrives with the Canvas surface, so the shelf projection is defined there; the one-home violation is the interim harm).

**Polish pass (11 audit-tagged + 2 NEW):** H-6 (transcript clipped under composer), H-7 (send-glyph contrast — ratio unverified, carried), W-8 (chip contrast + stranded wrap — the audit's adjustment stands: the chips themselves are a settled exception), W-9 (card clipped by dock), L-9 ("(s)" pluralization habit), L-11 (serif note textarea; clip under sticky header), D-3 ("Show all 11" names nothing), D-4 (last chat row faded/clipped, no scroll cue), F-7 (submission card cut at dock), LB-3 (Library header lacks Refresh), P-2 (generic sync glyph as the shop's mark; faint field borders). **(b) NEW → polish (2):** H-8 (duplicate "That didn't go through…" notices stacked in history — transcript-render dedupe, same surface family as the polish pass's other Home items), W-6 (draft signed "[Your Name]" — the draft-quality pass already carried on the polish list; a draft reaches the queue signed and complete or not at all).

**Standalone NEW (2):** D-2 (four chat rows identically "Earlier conversation · Nov 2" — Verdict 4 §5.2 titles-from-first-message covers new sessions; legacy sessions need a title backfill or a first-message preview fallback; small deterministic item, no round owns the drawer list), P-3 (customer form served from a `workers.dev` address, not a shop domain — Cloudflare routing work, no round's UI scope).

**Activation window (1):** H-4 (brief card says "isn't in yet" while the transcript holds the brief marked "ready") — already scoped in the in-flight window as the **briefstore phase** (deterministic persist of the composed brief to `brief/<date>` with read-back). Mechanism reconciled at §9.3.

**Rejected (c): 0 of the 78.** Every merged finding stands as a defect, an incompleteness, or a data state to correct.

## 9. Job 2 — Home's setup signal: mechanism, evidence, proposed correction

### 9.1 The mechanism (from the deployed frontend source)

Home's first-open state is driven by exactly one record: **kv `setup/profile`**.

- `loadSetup()` (app store): GET `/api/memory/agents/{agents[0].id}/kv/setup%2Fprofile`; `setupDone = !!(v && v.business)` — the record's value must carry a truthy `business` field. On any error, `setupDone = false`.
- `homeFirstOpen = setupLoaded && !setupDone`. The hero — greeting "What's next, <owner>?" + the **"Set up my studio"** button — renders only while `homeFirstOpen && !homeEngaged`.
- The only in-app writer is the setup conversation's `finish()` (setupPage): PUT `setup/profile` = `{business: <bizOption id>, needs: [<needOption ids>], brief: <option>, ts: <ISO now>}`, then activates the matching hands, then PUTs the "Your crew" board to `surface/crew`.
- The Needs-you line is separate: `homeNeedsWords` reads only the pending-approval count. "Nothing needs you right now" was literally true of the approvals queue (0 pending at capture) — it was never a setup claim; it read as false only because Home simultaneously presented as fully set up.

**Access trap, proven:** the key must be URL-encoded. GET `…/kv/setup/profile` (literal slash) returns **HTTP 404** while GET `…/kv/setup%2Fprofile` returns 200 with the record. A reader using the unencoded form concludes the record does not exist. This is the reproducible mechanism that reconciles the Round A deploy-night read ("no setup/profile record — 404", 2026-11-02 ~23:20 CST) with the record's presence: the deploy-night conclusion cannot have come from a correctly-encoded read of this store. (Which exact read was made that night is not recoverable from today's records — labeled unverified; the trap itself is demonstrated.)

### 9.2 What the record holds, when it was written, what wrote it

Live read (API + DB, 2026-11-03):

- `setup/profile` = `{"brief":"live","business":"tattoo","needs":["boards","messages","forms","content","texts"],"ts":"2026-11-03T03:54:45.697Z"}` — `business:"tattoo"` is the setupPage bizOption id for "Tattoo studio"; `needs` is all five needOption ids; `brief:"live"` is the "As things happen" option. The value is byte-shaped exactly like `finish()` output.
- kv_store row: **version 1** (written once, never updated), `updated_at = 2026-11-03T03:54:44.573Z` = **2026-11-02 21:54:44 CST**. The value's `ts` (03:54:45.697Z) is ~1.1 s later — the writing device's clock vs the box clock; same event.
- Corroborating write: `surface/crew` row, version 1, `updated_at = 2026-11-03T03:54:44.908Z` — 0.34 s after the profile — carrying exactly the board `finish()` composes from this profile (Business "Tattoo studio", Brief "As things happen", the five needs). The B-12 audit finding (the crew board as a setup recap) is this receipt.
- **Attribution:** the write came from a real browser running the setup flow at 21:54:44 CST on Nov 2 — the minute the owner was in the app doing his owner-seat checks (his TWA question ~21:53, the playbook proof answer 21:56). The plausible writer is the owner himself, tapping through "Set up my studio" between those messages. The records prove the flow ran, from a browser, at that minute; whose finger it was is inference, labeled as such.
- **NOT the lead, NOT this morning:** the lead's `fargotattoo.com` and `fargotattoo.com/audit` rows are timestamped 2026-11-03T16:20:33Z / 16:21:44Z (10:20–10:21 CST today — the website chat), roughly twelve hours after the setup write and after the audit had already captured H-5's state. No agent write touched the setup signal; the signal reads only `setup/profile`, a key no sweep, sidecar, or lead turn writes.

**So H-5's premise inverts:** the audit's observation (no CTA, no greeting) is accurate as rendered, but its inference ("no setup/profile record exists… no setup conversation ever ran") is wrong. A setup/profile record exists, the flow did run, and Home is behaving exactly as the Round A design specifies — brief-led, no setup action — on the strength of a 40-second tap-through the owner may not remember making. **H-5 disposition: (b) NEW → data correction (proposed at §9.4) + the owner's call (§10). No build defect; Step 1.5 is not implicated.**

### 9.3 The brief-card contradiction, reconciled (H-4)

Two surfaces, two different sources, both "telling the truth" about different things:

- **The brief card** reads kv `brief/<local date>` and requires a `text` field (`loadMorningBrief()`). `brief/2026-11-03` returns **404** (re-verified today) → the card's "Today's brief isn't in yet" is the truthful read of the kv family. (Yesterday's `brief/2026-11-02` exists, version 2 — the card worked on Nov 2.)
- **The transcript** renders the stax lead's session history. The Nov 3 compose turn emitted its `memory_store` call **as plain text** instead of invoking it (established by the 2026-11-03 06:17 verification), so the history shows the tool-call JSON (H-1) whose value string contains `"status": "ready"` — the brief as *composed*, never as *stored*.
- The fix is the activation window's briefstore phase (H-4's home, §8): the composed brief is persisted deterministically and read back, so the card and the record agree by construction.

### 9.4 Proposed correction (reported, NOT executed)

To restore the pre-setup state so the owner can run the setup conversation deliberately:

- **DELETE kv `setup/profile`** (exact key; via the DELETE route with the key URL-encoded, then read back GET → 404 and a fresh Home load showing the hero + "Set up my studio"). That single deletion is the whole correction — `loadSetup()` keys off nothing else.
- Leave `surface/crew` in place: it is a board record, dispositioned in Round B (B-5/B-12); deleting the profile does not strand it, and the setup flow, when genuinely run, overwrites both records.
- Do **not** substitute a hand-written profile: if the owner wants the current answers (tattoo studio · all five needs · brief "as things happen"), the alternative correction is no correction — keep the record and treat setup as done (owner's call, §10).

## 10. H-3 — the fleet narration: evidence and disposition

The captured line — "There are no pending tasks in shared memory. The list of running agents includes 39 agents, each with a unique ID, state, and model." — is an **autonomous-tick turn's** reply (the lead answering the kernel's `[AUTONOMOUS TICK]` prompt after calling `agent_list`), and it occurs in three stax sessions (byte-level search of the session store):

| Session (created) | Fleet line | vs the playbook fix (rules 9–11 landed + proven owner-seat 2026-11-02 21:54–21:56 CST) |
|---|---|---|
| a18bb7aa — Nov 2 17:13Z, updated 18:13Z (11:13–12:13 CST) | yes | **Predates the fix** |
| 59429628 — Nov 3 02:14Z, updated 03:49Z (Nov 2 20:14–21:49 CST) | yes | **Predates the fix** |
| 0b8948e4 — Nov 3 03:52Z (21:52 CST), updated 04:53Z (22:53 CST) | yes — the session's last message | **Postdates the fix on the clock:** `usage_events` shows this session's completions at 03:53:47Z (the owner's TWA exchange) and **04:53:04Z = 22:53 CST**, and the fleet message is the final turn — produced ~59 minutes after the fix was proven live |

**Disposition: LIVE VIOLATION, contained — named fix recorded.** The 22:53 CST instance means H-3 cannot be dispositioned as simply covered by the playbook fix. The mechanism is nevertheless identified: session 0b8948e4 was created at 21:52 CST, two minutes *before* the fix, and ran under the playbook it loaded at creation; hand definitions reload at daemon restart, and the Round A restart (23:20 CST) is what put the current HAND.toml in force for every later session. Since that restart there are **zero** fleet narrations in any Nov 3 session (the current canonical session included — its failure was the different, wild-goose-chase class, dispositioned by the rules 13/14 added 2026-11-03). The owner-visible residue — old tick exchanges sitting in Home's history at all — is cured by H-2's NEXT-BUILD renderer fix. **Standing watch:** a fleet narration in any session created after the 2026-11-02 23:20 CST restart reopens H-3 as an uncontained playbook defect. (Rules cited as 10 + 13/14 per the director's instruction; the no-machinery-narration rule is the playbook's standing rule 10 family, and 13/14 are the 2026-11-03 additions from the website-chat failure.)

## 11. Counts per home

| Home | Count | Findings |
|---|---|---|
| NEXT-BUILD (director ruling) | 2 | H-1, H-2 |
| SPECIAL — violation, contained (named fix recorded) | 1 | H-3 |
| SPECIAL — data correction + owner's call | 1 | H-5 |
| Activation window (briefstore, already scoped) | 1 | H-4 |
| Round B (a) | 15 | B-1…B-11, B-13, B-14, S-3, W-5 |
| Round B (b) NEW | 1 | B-12 |
| Round C (a) | 12 | L-1…L-8, L-10, T-5, T-11, W-7 |
| Round D (a) | 12 | D-1, T-1…T-4, T-6…T-10, F-2, S-1 |
| Round E (a) | 4 | F-1, F-3, F-4, F-5 |
| Round E (b) NEW | 2 | F-6, P-1 |
| Round F (a) | 4 | S-2, S-6, S-7, S-8 |
| Round F (b) NEW | 1 | S-4 |
| Work build (b) NEW standalone | 4 | W-1, W-2, W-3, W-4 |
| Polish pass (audit-tagged) | 11 | H-6, H-7, W-8, W-9, L-9, L-11, D-3, D-4, F-7, LB-3, P-2 |
| Polish pass (b) NEW | 2 | H-8, W-6 |
| Canvas slice | 2 | LB-2 (already scoped), LB-1 (b) NEW |
| Standalone (b) NEW | 2 | D-2, P-3 |
| Owner's call | 1 | S-5 |
| Rejected (c) | 0 | — |
| **Total** | **78** | |

Below finding grade, carried not dispositioned: the audit §14 first-tap-swallowing observation (UNVERIFIED — synthetic taps ≠ fingers) belongs to the pre-beta human-touch pass; the sign-in screen was not capturable in a read-only audit and still lacks a post-Round-A owner-configuration capture.

## 12. Items needing the owner's own call

1. **Setup (from H-5).** The setup flow was completed at 9:54 PM on Nov 2 — tattoo studio, all five needs, brief "as things happen" — quite possibly by your own tap-through between messages that night. **Question: keep those answers and treat setup as done, or wipe the profile (one record, `setup/profile`) so Home goes back to "Set up my studio" and you run the setup conversation yourself, deliberately?**
2. **Settings values (S-5).** Settings today shows no current values — shop details, approval posture, and spending limit all just say "Ask Stax," which is the deliberate agent-first pattern. **Question: should Settings also show the shop's current values read-only (name/hours, what Stax checks first, the cap), or stay as pure ask-Stax pointers?**

Nothing else in the 78 needs the owner: every other finding already has a home under verdicts and rulings he has given.
