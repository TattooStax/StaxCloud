# Step 1 Builder Brief — HOME (Director Verdict #3, Step 1)

You are Claude Opus 5.5, running in OpenCode on the Victus build machine, in
`~/openfang-build/repo` — the TattooStax/openfang fork, branch `stax-ux`, HEAD
`c9b93c7`. The product is the OpenFang pilot for Fargo Tattoo (owner: Shawn
Lowe), live at https://fang.sefer.team on Sarah's box. The plan of record is
Director Verdict #3; this brief is Step 1 of it, and it is your complete
instruction set. One slice. Nothing from Steps 2–6 starts here.

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
- Interactive-login facts, for the record: `opencode auth login -p openrouter`
  goes straight to a masked "Enter your API key" prompt — no browser/OAuth
  flow exists for OpenRouter (OAuth exists only for a few other providers).
  That path is deliberately unused.

## 2. The wiring law — absolute

Presentation only. The kernel, hands, sidecars (pull-sync, the Dell bridge),
workflows, schedules, and kv data DO NOT CHANGE. Concretely:

- Edits live in `crates/openfang-api/static/**`. The single permitted touch
  outside it: pure `include_str!` additions in `webchat.rs` if a new static
  file must be embedded. Everything else in the tree is read-only to you.
- Brief and Needs-you content is always a projection of real records
  (the `brief/<date>` kv record, the real approvals queue) — never invented,
  never model-minted.
- Renames are labels only: internal page keys, API fields, and record keys
  keep their upstream names.
- Demote, never delete: anything removed from an owner surface moves to the
  Advanced corner (§4), fully functional.
- No stacking: new content REPLACES or GATES stock content. Nothing gets
  prepended on top of stock markup.

## 3. The job — Step 1: HOME, the whole face, in one slice

Today there is no chat/home template: the conversation is a mode inside the
agents (helpers) page template, and the `chat` page key renders that template
— which is why the owner's landing is still the helpers console. Fix the
template, not the routing around it.

1. **Split the conversation out.** Create a dedicated home template that
   renders ONLY, in order:
   - the Stax identity header — avatar + "Stax"; tapping it opens the Stax
     card (Figma screen 4 is that card's spec; the header + tap target are
     this step, the card itself rides this step's header work);
   - status in plain words, from real state (the model is StaxCloud's pill,
     e.g. "Text replies: Automatic" — words a shop owner uses, never
     provider/model/kernel terms);
   - the **morning brief as the first card** — carry the existing brief card
     in from the overview template (its markup sits orphaned in
     index_body.html, ~lines 271–274; `loadMorningBrief()` in app.js already
     reads kv `brief/<browser-local date>`). Same real record, same loader —
     relocated, plus the real Needs-you count from the approvals queue;
   - the conversation thread with Stax (lead agent id
     `8cad1d3b-58f9-5563-ba0f-966d734c8a1f` — the chat machinery, WS +
     HTTP fallback, session handling all already work; move the markup,
     keep the wiring);
   - the **"Ask Stax" composer**.
2. **First open = Figma screen 1.** Mascot large and centered, status pill,
   greeting by name ("What's next, Shawn?"), and ONE next action:
   **"Set up my studio"** — which starts the setup AS A CONVERSATION with
   Stax. This retires the R10 stepper's front-door role (Verdict #2's R10 as
   originally specified: first run is a conversation, zero settings screens).
   Once a `setup/profile` exists, first open is the everyday state (Figma
   screen 2): avatar row, brief card, conversation.
3. **Landing discipline.** Fresh login lands on home. Stale hashes are
   demoted: `#overview` and `#agents` are currently valid page keys that land
   on the old overview and helpers pages — after this slice they land on
   home (the pages themselves survive under Advanced, §4).
4. **The dock is already right** — Stax · Work · Boards · Leads · Channels,
   badge on Work only — and the dock-width fix is already HEAD (`c9b93c7`).
   Do not rebuild either; they fold into this slice silently.

## 4. The hide list — binding (Verdict #3, correction D3)

None of the following may be visible on home or any owner surface after this
slice. All of it is demoted to a **Helpers view under System → Advanced**,
never deleted:

- the agents-page header actions: **+ New Helper**, **Stop All**;
- the helper catalog ("OR START A NEW HELPER" and the stock roster);
- the drawer's agent-picker chip wall (that is Step 2's surface — in this
  step, at minimum it must not appear on home);
- the stock Home cards: **Create Agent**, **Configure Provider**,
  **Browse Skills**;
- raw activity rendering: AGENT MESSAGE items, failure strings ("agent loop
  failed"), record dumps (e.g. `name=sms, parent=None`);
- fleet lists on any landing (people appear as people in the drawer TEAM,
  nowhere else);
- per-page stock headers duplicating the shell header.

A slice that leaves a hide-list item owner-visible is NOT done, whatever
else it ships.

## 5. Visual spec

- **Figma:** file "OpenFang — StaxCloud UX Plan", page **Screens**,
  **screen 1** (Stax home — first open: dark; mascot, status, "What's next,
  Shawn?", "Set up my studio", Ask Stax, five-tab dock) and **screen 2**
  (Stax home — everyday: light; avatar row, Morning brief card, message
  card). Match their composition in both themes.
- **Tokens (StaxCloud's, adopted literally — already in the codebase):**
  canvas `#f4f2ec` / dark `#0c0c0e`; surface `#fff` / `#121214`; border
  `#d9d4c8` / `#2a2a2e`; text `#1b1a17` / `#e8e4dc`; Stax teal `#146e68`
  (dark accent `#5cbcae`); Channels `#3f6486`, Studio `#885264`, System
  `#576373`. Spacing scale 4–40; radii 6 / 10 / 14 + pill; 44px minimum hit
  area; dock 56px; header 52px; typeface DM Sans.
- Tagline where branding appears: "Run your business. Grow your business.
  One intelligent system."
- Reference feel: Muse and StaxCloud — conversation is home, one clear
  next action, plain words. "It should not feel like a dashboard; it should
  feel like Muse or chat." (owner)

## 6. Design skills — read before you edit

Staged copies sit at `~/openfang-build/skills/` when you are launched
(source: `~/workspace/custom-skills/` on the parent VM). Mandatory pre-reads:

- `frontend_design/SKILL.md` — Anthropic's art-direction discipline; this
  slice is a new page, and it is the anti-template baseline.
- `impeccable/reference/craft-floor.md` — the floor every UI edit must clear
  (the rest of `impeccable/reference/` is the fix-and-polish playbook set).

Reference library, consult as needed: the jakubkrehel set (`better_interface`,
`better_ui`, `better_typography`, `better_colors`, `better_layout`,
`better_writing`, `better_accessibility`) and `ui_ux_pro_max` (palettes,
type pairings, style data — reference only, not a driver).
If the staged copies are absent, say so in your report and proceed on §5 —
do not stall the slice over it.

## 7. The stylish bar

The owner's word is **stylish**: distinctive art direction, not a tidy
wireframe. Spend boldness in one place (the mascot/first-open moment),
keep everything around it quiet and disciplined, and cut decoration that
does not serve the shop owner reading it. A home screen that could belong
to any admin tool has failed this bar even if every box in §3 is ticked.

## 8. Build, deploy, rollback — the loop's discipline

- Build on the Victus only: `OPENSSL_NO_VENDOR=1 cargo build --release
  -p openfang-cli` (full build ~14 min; static files embed at compile time,
  so template changes need the rebuild). Verify completion from the build
  log's exit marker, not process greps.
- Stage first: fresh HOME, throwaway port, no LLM key — exercise the new
  home template there before anything ships.
- Deploy to Sarah's box (`ssh staxbox@192.168.40.27` from the Victus; your
  session carries agent forwarding — if auth fails, stop and report, do not
  hunt for keys):
  1. copy the current binary aside as the rollback (`openfang-<prev>.bak`);
  2. stage the new binary as `openfang-new` and verify its sha256 equals
     the Victus build BEFORE swapping;
  3. `./openfang stop` — graceful, always (kv can lose the last write on a
     hard kill); swap; restart from `~/openfang-play` sourcing `./env`
     (sourcing `../env` starts the daemon keyless — that mistake is on
     record; do not repeat it);
  4. confirm EXACTLY ONE openfang process is running (a lingering old
     process has happened once — if there are two, report it, do not
     guess which to kill);
  5. health: local `:4200` and https://fang.sefer.team.
- Sarah's StaxCloud (port 3121) is a different product on the same box:
  never touch it.
- Commit your work locally on `stax-ux` with a clear message. **Do not
  push.** Commits stay local until the parent reviews them.

## 9. The done-gate — the ONLY one

Fresh login on the live app; **phone-width and desktop screenshots** of the
actual home landing, filed beside Figma screens 1–2. The parent captures
these at the owner seat immediately after your deploy — leave the live
instance deployed and healthy.

Your own report is engineering facts only: files changed, build result,
staging result, deploy + health facts, anything from §4 still visible that
you could not gate, anything unverified. You do not declare the slice done,
and you never describe deploys, byte counts, greps, or smoke checks as UX
progress — the screenshots are the only UX evidence, and the slice is
reported to the owner strictly as what they show.

## Later steps — owner notes

- **Step 2 — Side card:** content replacement (people on top, sections,
  side chats as conversations, one "New chat", owner footer).
- **Step 3 — Work:** StaxCloud composition (Front desk card; Needs you /
  Current work / Finished) over existing wiring.
- **Step 4 — Channels as a room:** one conversation surface from home
  (the consolidation Verdict #2's R5 originally specified).
- **Step 5 — Boards and Leads:** recompose the existing pages to Figma
  screens 8–9.
- **Step 6 — Forms panel** (Figma screen 7). **Owner direction, 2026-11-02:
  the form builder should feel like the InkStax form builder. In the
  owner's judgment the InkStax form builder looks cleaner than the
  StaxCloud form builder — "at least the block engine does." The InkStax
  block engine is the feel reference for the Forms build; examine it
  firsthand before that step, per the owner's examine-first process
  order.**

Each step starts only when the previous step's gate screenshots are on
file. That sequencing is binding, not advisory.
