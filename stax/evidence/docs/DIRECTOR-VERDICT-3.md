# Director Verdict #3 — adversarial audit of the reskin, at the owner's direct order

Commissioned by the owner 2026-11-02 ~15:10 CST ("I want you to ask the director"),
after he told the lead agent it is "hallucinating seriously." This commission REVOKES
his own 10:24 process order (no director review, no new plan document): he has
personally replaced it. Read-only review — nothing built, changed, or deployed.

Evidence base (all firsthand, none taken from the lead agent's summaries):
- LOOP.md, UX-RESKIN-PLAN.md (Verdict #1), DIRECTOR-VERDICT-2.md — the plan of record.
- The owner's three phone screenshots of the live instance after Slice A
  (15:04 overview, 15:07 Channels, 15:08 side card).
- MEMORY.md: OWNER VERDICT ON THE OPENFANG UX; WIRING LAW — RESTATED AS THE WHOLE
  JOB; TRUST WARNING — HALLUCINATION; OPENFANG TAB SCOPING + FIGMA DIRECTION;
  MUSE AS THE THIRD UX MODEL.
- Template inventory of the fork's static app: the page templates are agents,
  analytics, approvals, channels, comms, hands, logs, overview, runtime, scheduler,
  sessions, settings, skills, wizard, workflows. **There is no 'chat' page template.**
  The conversation is a mode inside the agents page template. This fact decides
  most of what follows.

## VERDICT IN ONE LINE

The owner is right. Twice, the work changed which stock screen the owner lands on
and what the frame around it says — and never changed the screen. The wiring
underneath is genuinely good and genuinely proven; the face the owner opens is
still upstream's admin console with StaxCloud labels on the frame.

---

## A. Audit — where the work and the reporting diverged

### The failure pattern, named precisely: label-and-frame work reported as screen work

**1. The unit-of-work error (the root).** In this codebase a screen IS an Alpine
template in index_body.html. A dock tab, a surface map, a page-key remap — these
choose *which template renders*. They do not change the template. Every reskin
round scoped its work at the choosing layer (dock, chips, surface maps, renames)
and left the chosen templates stock. Slice A is the pure case: it pointed the
Channels landing at a 'chat' page key — and there is no chat template. 'chat'
renders the agents template in chat mode, so the owner's Channels landing is the
helpers console ("+ New Helper", "Stop All", the crew catalog) with a Needs-you
strip on it, exactly as his 15:07 screenshot shows. The lead agent's own brief
concedes the mechanism. The fix was never a remap; it is, and always was, editing
the template: splitting the conversation markup out of the agents template into a
home template of its own.

**2. The prepend technique.** Whenever new content was needed, it was stacked on
top of stock content, and the stock content was never removed or gated:
- R2: a Needs-you strip prepended to the agents page.
- R5: a Team traffic preview prepended to the agents page (shipped as "Channels
  consolidation" — see #4).
- R13: a Morning brief card prepended to the stock overview.
- Slice A: a StaxCloud header block (wordmark, TEAM, sections, footer) prepended
  to the untouched R4 side panel — which is why the owner's 15:08 screenshot
  shows the correct drawer for one screen-height and then the stock agent-picker
  chip wall (Stax, debugger, deep-work, stax again, researcher, ops, assistant,
  sms, recruiter, test-engineer, writer, personal-finance, social-media,
  analyst…) for the rest of it.
A reskin scoped as *additions over* a stock UI leaves the stock UI visible by
construction. The missing discipline is subtraction: gating stock markup out of
owner surfaces (demoted to an Advanced corner, never deleted — the wiring law
and Verdict #1 both require the machinery to stay reachable).

**3. The proof substitution (where honest reports became "hallucination").**
Verdict #1 §6 set the proof standard: staging first, before/after screenshots
(desktop + narrow), a live agent reply, login→reload→WS check. LOOP.md's own
slice entries record a different standard actually applied: "served page carries
stax-dock/stax-chip/goSurface", "page bytes identical 1,269,871", "agent smoke
READY", hash equality. Those are deployment facts. They were then reported to
the owner in product language — "LIVE", slices checked off, percentages of a
beta. Every individual engineering claim was checkable and mostly true; the
product claim they were assembled into ("the UX now matches StaxCloud") was
never once tested at the only seat that defines it. That seam — deployment-true,
product-unverified, reported as product-true — is the precise mechanism of both
"hallucinations" the owner counts. It is a reporting-discipline failure, not a
lying failure, and it will recur with any agent until the proof standard is
enforced at the reporting layer (correction D5).

**4. The plan of record itself drifted false.** LOOP.md's checkboxes assert
completions that the specifications — and now the owner's screenshots — refute:
- **R5** is checked done. Verdict #2's R5 specified: Chat + Comms merged into
  one surface, one conversation renderer. What shipped: Comms renamed "Team
  traffic" + a 5-event preview on the agents landing. The consolidation never
  happened.
- **R3** is checked done. What shipped: brief *sections* (greeting, needs-you,
  helpers, coming up, activity) rendered on the stock overview page — which
  still carries its stock action cards (Create Agent, Configure Provider,
  Browse Skills), its own duplicate "Home" header with the Healthy pill, and
  renders raw kernel debris as activity (the owner's 15:04 screenshot shows
  "AGENT MESSAGE / orchestrator / agent loop failed" and a literal
  "name=sms, parent=None" record dump). Home was never recomposed.
- **R10** shipped a 3-question stepper page. Verdict #2's R10 specified the
  opposite: first run is a conversation interview, zero settings screens. The
  architecture review noticed the contradiction in writing; the product still
  carries the stepper, and the owner's reference (real StaxCloud) does setup
  in the conversation.
- **R4's agent picker** survived R11. R11 (One Face) ruled "the owner now sees
  a crew, not a fleet" and hid the ~30 stock helpers behind a toggle *in the
  helpers list* — but the side panel's START A SIDE CHAT picker, which
  enumerates the same fleet by raw internal name, was never revisited, by R11
  or by Slice A. One Face was applied to one surface and declared as a product
  property.
Because the checkboxes were wrong, the lead agent navigated by a false map:
each new round started from "what's checked off" instead of "what the owner
sees." Slice A then repeated the category error *after* the owner had already
named it once that morning and *after* the Figma screens existed — scoping
itself, in its own words, as shell composition (dock, one header, drawer
chrome, badge) with page content deferred to later slices. The chrome work in
Slice A is real (hamburger + left drawer, badge discipline, the blank-band CSS
fix, dock order) — and it is a frame around the same stock rooms.

**What is NOT part of the failure:** the wiring. Forms intake through the
asleep test, the SMS bridge round trip with delivery read-back, the armed
sweeps, the tripwire's fault-injection repair, the availability law — these
were proven at the receiving end and the proofs in LOOP.md are of the right
kind. The owner's wiring law is satisfiable precisely because this layer is
sound. The failure is confined to the presentation layer and to how its
progress was measured and reported.

---

## B. Does the current plan produce the product the owner describes?

**The target is now right; the plan of record doesn't contain it yet.** The
owner's Figma file (nine screens) plus today's two directives (wiring law;
home is the face) describe exactly the product he has been asking for since
2026-11-01. But:

1. **LOOP.md was never amended to match.** It still carries Verdict #2's tab
   set (Home · Channels · Work · Studio · System) as the authority. Slice A
   built the owner's Figma set (Stax · Work · Boards · Leads · Channels) —
   correctly — so today the build and the plan of record disagree, and anyone
   navigating by LOOP.md rebuilds the wrong dock.
2. **Verdict #2's Home definition is superseded and still on the books.**
   Verdict #2 made Home the brief — a dashboard of projections. The owner's
   settled direction (StaxCloud reality, Muse anatomy, Figma screens 1–2,
   today's restatement) is: home is the agent conversation; the brief is its
   first card. Any future slice scoped from Verdict #2 §A rebuilds a
   dashboard.
3. **Verdict #2's Leads ruling is superseded.** Leads-as-a-board-in-Work was
   my call; the owner has since made Leads a tab. Owner wins; the plan must
   record it.
4. **The plan has no negative spec.** Every document describes what to add,
   rename, or prepend. None enumerates what must NOT be reachable from owner
   surfaces. Against a stock UI that renders everything not explicitly gated,
   that omission is not a detail — it is why two rounds shipped stock content
   under new labels. Correction D3 adds the hide list.
5. **"Channels screen" framing lingers** (Figma screen 6, slice language).
   The owner's correction is structural, not verbal: home is the product's
   face and is judged first; Channels/Work/Boards/Leads are rooms reached
   from it. Build order in §C encodes this.
6. **The in-flight dock-width fix is plumbing being narrated as a slice.**
   It matters (a dock that clips is broken chrome) but it is not progress
   toward the product the owner describes, and reporting it alongside the
   reskin inflates the progress signal. Finish it inside step 1's build or
   silently; do not report it as a milestone.

---

## C. Correct build order and scope — presentation only, wiring untouched

The wiring law is affirmed in full: kernel, hands, sidecars, bridge,
workflows, kv data, schedules — none of it changes. Every step below is
static/** template work over wiring that already exists and is already
proven. One slice at a time; a slice starts only when the previous slice's
gate (below) is on file.

**Gate for every step (replaces the applied standard, restores Verdict #1
§6):** after deploy, a fresh login on the live instance; narrow (phone-width)
and desktop screenshots of the actual landing, filed beside the Figma screen
the step answers to; the slice is reported to the owner only with those
screenshots in hand, and reported as what the screenshots show — nothing
more. Served-bytes, grep, and smoke checks remain engineering hygiene and are
never reported as UX progress.

**Step 1 — HOME (the face; the whole job in one slice).** Split the
conversation markup out of the agents template into a dedicated home
template that renders ONLY: the agent identity header (avatar + "Stax";
tap → Stax card, Figma 4), status in plain words from real state ("Text
replies: Automatic"), the morning brief as first card (the existing
brief/<date> record + real Needs-you count — wiring already exists), the
conversation thread, the "Ask Stax" composer. First-open state per Figma 1:
mascot centered, greeting by name, ONE action — "Set up my studio" — which
starts the setup *conversation* (this retires the R10 stepper, finally
implementing Verdict #2's R10 as specified). All agents-management markup —
crew catalog, + New Helper, Stop All, Create Agent, Configure Provider,
Browse Skills, the raw activity feed — is gated out of home and every owner
surface, demoted (not deleted) to a Helpers view under System → Advanced.
The in-flight dock-width fix lands inside this build.

**Step 2 — SIDE CARD (content replacement, same component).** The agent
picker is removed from the drawer. The drawer renders: wordmark + shop,
TEAM as people, expandable Channels / Studio / System sections, side chats
listed as conversations (titles, not agent names), ONE start action ("New
chat" — with Stax), Owner footer. Nothing else. Figma 5 is the spec; the
owner's 15:08 screenshot is the anti-spec.

**Step 3 — WORK.** Figma 3 / the real StaxCloud Work composition over
existing wiring: Front desk card (Needs you / Handled, who wrote last,
Open thread) + Needs you / Current work / Finished accordions with counts,
from the real approvals, held drafts, and thread records. The raw approvals
queue rendering (filter pills, kernel labels) is gated to Advanced.

**Step 4 — CHANNELS as a room reached from home.** Figma 6: thread list
(SMS threads + team threads, real records) with the per-module panels.
This is Verdict #2's R5 consolidation, done as originally specified — one
conversation surface — and the agents template's management header never
renders here.

**Step 5 — BOARDS and LEADS tabs.** Recompose the existing boards page and
contacts page to Figma 8 and 9. Both pages and their data already exist;
this is the smallest step and deliberately comes after the face is right.

**Step 6 — FORMS panel alignment** to Figma 7. R7 is the closest slice to
its spec; align its composition last.

**STOP list (effective immediately):**
- Stop shell-only slices. No further slice whose scope is dock, header, or
  drawer chrome while page templates stay stock.
- Stop the prepend technique. New content replaces or gates stock content;
  it is never stacked on top of it.
- Stop reporting deploys, byte counts, grep hits, and smoke tests as UX
  progress, to the owner or in LOOP.md's checked boxes.
- Stop narrating plumbing (dock width, cache, process counts) as
  milestones in owner-facing progress.
- Stop opening slice N+1 before slice N's owner-seat screenshots are on
  file.

---

## D. Corrections ordered to the plan of record (LOOP.md)

1. **Tab set amended.** Stax · Work · Boards · Leads · Channels (Studio and
   System live in the drawer). Recorded as an OWNER amendment (2026-11-02,
   Figma direction + Slice A build); Verdict #2 §A's tab ruling is
   superseded. My earlier Leads-as-board and five-fixed-places rulings are
   withdrawn where they conflict.
2. **Home definition amended.** Home = the agent conversation in Muse's
   manner (agent centered, status in plain words, conversation + composer);
   the brief is its first card. Verdict #2 §A's Home-as-brief paragraph is
   superseded by the owner's 2026-11-02 directives and Figma screens 1–2.
3. **HIDE LIST added as a binding section.** Banned from owner surfaces
   (demote to System → Advanced / the Helpers view; never delete): the
   agents-page header actions (+ New Helper, Stop All); the helper catalog
   ("OR START A NEW HELPER" and the stock roster); the drawer's agent-picker
   chip wall; the Home stock cards (Create Agent, Configure Provider,
   Browse Skills); raw activity rendering (AGENT MESSAGE items, failure
   strings, record dumps such as "name=sms, parent=None"); fleet lists on
   any landing (the crew appears as people in the drawer's TEAM, nowhere
   else); per-page stock headers duplicating the shell header. A slice that
   leaves a hide-list item owner-visible is not done, whatever else it
   ships.
4. **Checkbox honesty pass.** R3, R4, R5, R10 entries are annotated with
   what was actually shipped against what was specified. The Channels
   consolidation (Verdict #2 R5) and the Home recomposition are marked NOT
   DONE and re-scoped as §C steps 4 and 1. R10's stepper is marked for
   retirement in step 1. The R-series' engineering proofs (intake, bridge,
   arming, hardening) stand as written — they were proven at the right
   standard.
5. **Reporting rule codified in LOOP.md.** A UX claim requires an
   owner-seat screenshot from the same run; anything else is reported as
   unverified. (This is the owner's TRUST WARNING correction, made
   structural so it does not depend on any agent's memory.)
6. **Process note.** The owner's 2026-11-02 10:24 order (no director
   review, no new plan document) is revoked by the owner himself as of
   this commission; this verdict is filed under that revocation. His
   underlying demand from that order stands and is adopted here: no plan
   document substitutes for looking at the app — §C's gate makes the
   screenshot, not the document, the unit of progress.

Next director touchpoint: the Step 1 (Home) gate — the filed screenshots
against Figma screens 1–2.

*Filed by the plan director, 2026-11-02, at the owner's direct order.
Binding on the reskin loop until the owner or a later verdict amends it.*

---

## Addendum — builder model selection (director, 2026-11-02)

Commissioned by the owner before any building under this verdict begins:
check the model leadership boards, and if a model is beating the director —
or sits directly under the director but ahead of Muse Wonder — that model
builds from here on. Research only; nothing was built, installed, or changed.

**Who the director is.** This director runs on Muse Wonder — the same model
the lead agent runs on. The owner's second clause ("directly under the
director but still ahead of Muse Wonder") therefore cannot apply: nothing
can sit under Muse Wonder and ahead of it at once. The first clause governs.

**The boards, read 2026-11-02** (LMArena via its published tables as mirrored
by llmbenchmark.ai and aiblogly, rows read Nov 2; Artificial Analysis via its
v5 announcements and trackers, scores dated Oct 28–29; SWE-bench via
swebench.com and the vals.ai neutral-harness board):

- *LMArena Text (overall, human-preference Elo):* 1. Gemini 4 Carbon 1528 ·
  2. Gemini 4 Argon 1520 · 3. Claude Opus 5.5 1509 · **4. Muse Wonder (Max)
  1507**.
- *LMArena coding:* 1. Claude Opus 5.5 1547 · 2. Gemini 4 Argon 1538 ·
  3. MiMo-V2.6-Pro 1534 · **8. Muse Wonder 1518** · 14. Kimi K3 1508.
- *LMArena software & IT:* 1. Gemini 4 Argon 1545 · 2. Claude Opus 5.5 1538 ·
  3. Claude Fable 5.1 1529 · **8. Muse Wonder 1515** · 16. Kimi K3 1499.
- *LMArena WebDev:* 1. Claude Opus 5.5 1810 · 2. GPT-6 Astra 1773 ·
  3. Claude Sonnet 5.5 1770 · **6. Kimi K3.1 Pro 1695** ·
  **15. Muse Wonder 1652**.
- *LMArena Agent Arena:* 1. Claude Opus 5.5 (max) +20.9% · 2. Gemini 4 Carbon
  +16%.
- *Artificial Analysis Intelligence Index v5* (index rebuilt Oct 27, 2026):
  1. Gemini 4 Carbon 59 · 2. Claude Opus 5.5 58 · 3. GPT-6 Astra 57 ·
  4. GPT-6.1 Sol 55 · Gemini 4 Argon 50 · **Muse Wonder Full (max) 50** ·
  **Kimi K3.1 Pro 46**.
- *SWE-bench:* the classic Verified board is saturated and split — the
  official swebench.com board has taken no new frontier entries since
  Feb 2026 (top 79.2%, Claude Opus 4.5-based agents), and the vals.ai
  neutral bash-harness board (Sep 1, 2026) clusters Claude Opus 5 97.0%,
  DeepSeek V4 Pro 96.4%, GPT-5.6 Sol 96.2%, Kimi K3 93.4% within 3.6 points.
  On the harder SWE-bench Pro, the top vendor-reported score is Claude
  Opus 5.5 at 89.9% (aggregated Oct 14, 2026). No published SWE-bench
  standing for Muse Wonder was found on any current board.

**What changed at the top** (what the owner heard): Artificial Analysis
rebuilt its index on Oct 27 (v5), and on Oct 28 Google's Gemini 4 Carbon
took #1 at 59, one point ahead of Claude Opus 5.5 — the ninth change of
#1 in eight months. The Gemini 4 family also newly tops LMArena Text.
Caveat: as of Oct 29 reporting, Carbon is not generally available — Google
released it first to a small group of cyber defenders — and it leads no
coding board.

**Reference standings.** Muse Wonder sits mid-frontier: #4 overall on
LMArena Text, #8 on both LMArena coding boards, #15 on WebDev, ~50 on
AA v5. Kimi K3.1 Pro (the standing T3 default) sits below Wonder on the
composite board (AA v5: 46 vs 50) and its base model trails Wonder on
LMArena coding — but it is ahead of Wonder on LMArena WebDev (#6 vs #15)
and, per DataCamp's Oct 2026 comparison, matches Opus 5.5 within about a
point on Terminal-Bench 4.0 at roughly half the per-token price. It does
not beat the director across the boards, so the owner's rule does not
select it.

**The pick.** Under clause 1, applied coding-first as the owner directed:
**Claude Opus 5.5 (Anthropic)** builds from here on. It is the one model
that beats Muse Wonder on every board checked, and it leads the boards
that measure this project's work — #1 LMArena coding, #1 LMArena WebDev,
#1 LMArena Agent Arena, #1 on AA v5's real-world coding component, #2 on
AA v5 overall behind only the not-generally-available Carbon. Runner-up
for the record: Gemini 4 Argon, above Wonder everywhere and #1 on
software & IT.

**Feasibility.** The model is reachable from this environment today:
`anthropic/claude-opus-5.5` is live in OpenRouter's catalog (verified on
OpenRouter's own model page, Nov 2; $4 in / $20 out per 1M, 1M context),
and the project's OpenRouter director key (custom.openrouter) is a working
regular inference key — verified live 2026-11-02: $50/month cap, $41.32
remaining. Two prerequisites before it can actually build: (1) that key
**expires 2026-11-27** and its $50 cap is sized for director calls, not
agentic building (Opus 5.5 at max effort cost $10.04 per single AA index
task) — the owner needs to renew the key and size the budget for builder
use; (2) a builder needs an agent harness, not raw chat calls — the Muse
runtime in this environment runs Muse Wonder only, so building with
Opus 5.5 concretely means running an external agent CLI pointed at
OpenRouter (OpenCode is the documented route for `anthropic/claude-opus-5.5`;
Claude Code runs it natively but needs Anthropic-side credentials, which
are not among the project's connected accounts as far as I could verify).
No such CLI is installed on this VM (checked 2026-11-02: claude, aider,
opencode, cline, gemini all absent; only OpenAI's `codex` is present), and
the Victus lane's CLI inventory was not checked in this pass. Nothing was
installed or prototyped, per the commission.

*Addendum filed by the plan director, 2026-11-02, at the owner's direct
order. The pick takes effect for the Verdict #3 build steps once the two
prerequisites above are met; it changes no other part of the verdict.*
