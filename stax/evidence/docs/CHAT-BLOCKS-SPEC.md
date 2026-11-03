# Chat Blocks + Uploads — Feasibility & Spec

**Commissioned:** 2026-11-03 (owner, with Muse demo-gallery screenshots, filed in
`screenshots/blocks-reference/`). **Scope:** research + spec only. No builds, no live changes.
**Method:** every current-state claim below was read firsthand from the Fang source tree
(`~/openfang-build/repo` on the Victus, HEAD `2012eeb8` — the tree the deployed Round A binary
was built from) or from the project's own wiring records. Line citations are to that tree.

**The owner's ask, in his words' substance:** OpenFang's main chat has no way to upload a file
or image; he wanted to test image generation inside the main chat with a reference image and
could not attach anything. He wants the conversation to work like Muse's main chat — uploads
in, images generated right inside the thread, and the agent pulling up **blocks** in the
conversation (browser card, scheduled-task card, embedded HTML, choice buttons, list card,
map card) — "same with forms, websites": forms and websites also present as blocks in the chat.

**Headline verdict:** this is mostly a *restoration and composition* job, not a construction
job. Upstream OpenFang already ships the entire upload → image-into-the-turn → image-out-of-
the-turn pipeline; the Round A reskin's Home composer dropped the one button that reaches it.
Blocks are the genuinely new piece, and they can be built entirely in the presentation layer
plus kv records — **no kernel change is required for v1 of anything in this spec.** The
exceptions that would need the owner's word are listed in §6, and none of them blocks v1.

---

## 1. Current state — verified from source

### 1.1 Uploads: the plumbing exists end-to-end; the Home composer dropped the button

**The owner's claim is verified for the surface he uses.** The main chat (Home) composer is a
textarea and a send button, nothing else:

- `crates/openfang-api/static/index_body.html:648-662` — the "Ask Stax" composer: one
  `<textarea id="msg-input">`, a send button disabled unless `inputText.trim()` is non-empty,
  a stop button while sending. No attach button, no file input, no attachment preview strip,
  no drop zone.

But one layer down, the same shipped bundle carries the complete stock machinery:

- **Composer (stock per-agent console, now under System → Advanced → Helpers):**
  `index_body.html:861-896` — attachment preview chips, a paperclip button
  (`@click="$refs.fileInput.click()"`, title "Attach file"), and
  `<input type="file" multiple accept="image/*,.txt,.pdf,.md,.json,.csv,.mp3,.wav,.ogg,.webm,.m4a,.flac">`.
- **Client flow:** `static/js/pages/chat.js` — `addFiles()` (:1290-1312; 10 MB cap, type
  checks, image previews), `sendMessage()` uploads attachments *first* via
  `OpenFangAPI.upload()` (:1100-1121), then sends the text with `attachments` refs on both
  transports: WS payload (`chat.js:1172`) and HTTP body (`chat.js:1189`).
  `OpenFangAPI.upload` is a multipart POST (`static/js/api.js:313-325`).
  Drag-and-drop exists (`handleDrop`, chat.js) but its drop zone is wired only on the stock
  console, not on Home. Home and the stock console run the **same** `chatPage` component,
  the same WS + HTTP fallback, and the same sessions (`index_body.html:502-512` — the Round A
  header comment says so in as many words).
- **Upload endpoint:** `POST /api/agents/{id}/upload` (registered `server.rs:289-290`;
  handler `routes.rs:10543`). Multipart; **max 10 MB** (`routes.rs:10531`); allowed content
  types `image/`, `text/`, `application/pdf`, `audio/` (`routes.rs:10534`). Files are written
  to **`$TMPDIR/openfang_uploads/<uuid>`** (`routes.rs:10648`); metadata (filename,
  content type) lives in an **in-memory registry** (`UPLOAD_REGISTRY`, `routes.rs:10528`).
  Audio uploads are auto-transcribed by the media engine (Whisper STT, `routes.rs:10675+`).
- **Serving:** `GET /api/uploads/{file_id}` (`server.rs:295-296`, `routes.rs:10716`) — and it
  is **public by design**: the auth middleware exempts GET /api/uploads/*
  (`middleware.rs:111`), reachable by anyone holding the unguessable UUID.
- **Rendering of uploaded images already works on Home:** the Home thread renders a user's
  uploaded images (`index_body.html:573-575`, `msg.images` → `/api/uploads/<file_id>`) and an
  agent turn's tool-result images (`index_body.html:561-562`, `tool._imageUrls`).

**What does not exist / the honest weaknesses of what does:**

- **Durability:** files sit in the OS temp dir and their metadata in process memory. A daemon
  restart forgets the registry; a reboot or tmp cleanup loses the files. Attachments today
  are *turn-scoped*, not records. (The session-history read path re-persists image blocks it
  finds into the upload dir, `routes.rs:521-546`, which heals some cases by re-minting a new
  file_id — the image survives, its identity doesn't.)
- **Only images reach the model** (see §1.2). A PDF or text file uploads fine and renders as
  a chip, but the turn receives only a `[File: name]` text marker.
- The Home send button's disabled logic keys on text only (`!inputText.trim()`), so even with
  a button restored, an attachment-only message needs the stock composer's condition
  (`!inputText.trim() && !attachments.length`, chat.js `sendMessage()` guard) to send.

### 1.2 Images into an agent's turn: exists

- The message model is structured, not text-only: `MessageContent::Text | Blocks(Vec<ContentBlock>)`
  (`crates/openfang-types/src/message.rs:63`), and `ContentBlock` includes
  `Image { media_type, data /* base64 */ }` (`message.rs:86-105`) alongside Text, ToolUse,
  ToolResult, Thinking.
- On send, the API resolves attachment refs into image blocks
  (`resolve_attachments`, `routes.rs:250-296` — reads the file, base64-encodes it, image
  types only, UUID-validated against path traversal) and pre-inserts them into the session
  (`inject_attachments_into_session`, `routes.rs:301+`; wired into the message route at
  `routes.rs:372-376` and the WS handler at `ws.rs:638-647`).
- The kernel passes image blocks through the agent loop to the provider drivers
  (`ContentBlock::Image` is handled in `openfang-runtime/src/drivers/openai.rs:528` —
  serialized as an image part — and in the anthropic/bedrock/gemini drivers, the compactor,
  and the session store). Fang's crew runs through the OpenAI-compatible driver via
  OpenRouter, so an image attached to a lead turn *can* reach the model.
- **Vision is per-model.** The model catalog carries `supports_vision` flags
  (`openfang-runtime/src/model_catalog.rs:1082+`) and the stock model switcher shows a vision
  badge. Whether the daemon's *default* model (the lead's `model = "default"`,
  `stax/hands/stax/HAND.toml:13`) accepts image parts is a configuration fact to verify at
  build time, not a code gap. Deep-work's Kimi is vision-capable (proven firsthand by the
  2026-11-03 surface audit, run over OpenRouter direct). A fallback also exists in the tool
  catalog: `image_analyze` (vision-LLM description of an image file,
  `tool_runner.rs:1025`) and `image_analyze`'s sibling media tools.
- One transport caveat: the SSE streaming message route does not support attachments
  (`routes.rs:1577`, "SSE streaming doesn't support image attachments yet"). The webchat
  tries WS first and falls back to the non-streaming POST, both of which carry attachments —
  so this does not affect the shipped UI.

### 1.3 Images out of an agent's turn: the render path exists; two generation engines, neither wired for the owner's ask today

- **Tool-result images render inline on Home already** (§1.1, `tool._imageUrls`). Any tool
  whose result carries images gets them into the thread with zero new rendering work.
- **The kernel has a native `image_generate` tool** (`tool_runner.rs:1049` catalog,
  `:335` dispatch; engine `openfang-runtime/src/image_gen.rs`): OpenAI Images API
  (DALL-E 3 / DALL-E 2 / GPT-Image-1), results saved to the workspace *and* to the uploads
  dir so the web UI serves them (§1.1's route). Three blockers for Fang as-is:
  1. It requires `OPENAI_API_KEY` in the daemon's environment (`image_gen.rs:22-24`).
     Sarah's box runs the daemon on an OpenRouter key; no OpenAI key is present.
     (`MediaConfig.image_gen_base_url` can redirect the same wire format to any
     OpenAI-compatible image endpoint — a configuration route, not code.)
  2. **It is text-to-image only.** `ImageGenRequest` is `{prompt, model, size, quality,
     count}` — there is no reference-image input, so it cannot do the reference-anchored
     generation the owner asked to test, nor the shop's design work.
  3. **No crew hand holds the tool.** Crew tool grants are explicit lists in each
     HAND.toml; none includes `image_generate`.
- **The shop's real design engine is the Canvas sidecar** (see §1.5) — reference-anchored by
  design — but its results land in design records and files, never in a chat thread.

### 1.4 Blocks in chat: absent as a system — but four precedents already ship

There is no block/card mechanism in the chat message stream today: a Home message renders as
markdown text (`renderMarkdown`, `static/js/app.js:24`, with the Round A Amendment 2 rules —
accent links, the `/download/staxcloud.apk` link rendered as a "Get the StaxCloud app"
button, `app.js:66`), plus tool cards and tool images. The Amendment 2 renderer rules also
mean a block mechanism must never surface as raw text in the message body (the H-1 failure —
a raw `memory_store` JSON rendered as a chat message — is the standing counterexample), and
`homeShowMsg` (`static/js/pages/home.js:166-168`) filters wordless/system-shaped entries, so
blocks must ride *inside* a normal message's rendering, not as pseudo-messages.

Precedents the spec builds on instead of inventing:

1. **Surfaces (Boards)** — kv `surface/<slug>` = `{title, blocks[]}` with typed block
   renderers `heading / text / stats / list / kvlist` (`index_body.html:5241-5325`;
   `js/app.js:1148+`). A working typed-block vocabulary and renderer already exist — just
   bound to a page, not to a conversation.
2. **The setup conversation's choice replies** — Home already renders tappable option
   buttons inside the thread that answer the agent (`index_body.html`, the `homeSetup`
   block: `home-replies` buttons for business / needs / brief choices). Choice buttons in
   chat are a shipped pattern, currently hard-wired to one flow.
3. **Out-of-band cards composed by the frontend** — the Morning brief card reads kv
   `brief/<date>` and the Needs-you row reads the approvals count, both rendered by Home
   outside the message stream. The frontend already composes cards from records.
4. **The approvals machinery** — `GET/POST /api/approvals`, `POST /api/approvals/{id}/approve`,
  `POST /api/approvals/{id}/reject` (`server.rs:537-545`). Any in-chat approval card must
  call these exact endpoints; Work (Needs you) remains the queue of record.

### 1.5 The designer / Canvas path today: kv job queue → sidecar → records + files

Verified from the Canvas ops wiring records (`~/workspace/canvas-ops-wiring/RESULTS17-FANG-OPS.md`):

- The designer hand's tools are only `memory_store, memory_recall, knowledge_*, schedule_*`
  (`stax/hands/designer/HAND.toml:6`) — it generates nothing itself. Per its playbook it
  writes **`designjob/<id>`** kv records; a deterministic sidecar (cron-invoked from
  `~/openfang-play/`) executes them against the Canvas engine; results land as
  **`design/<id>`** records plus bundle **files** on the box, with library elements in
  `designlib/` (small elements ride inline in kv, ~72 KB observed — the exception, not the
  pattern; bundles are files).
- Jobs already reference files by path (an edit proposal was supplied as
  `file:edits/ops17-edit-1-result.png`), and cover-ups take a **reference image file** as
  input — reference-anchored work is the engine's native mode, matching the owner's
  standing preference (Canvas law: reference-anchored generation preferred; transparent
  layered output; artist profile + style presets steer it).
- **Nothing in this path can put an image into a chat thread today:** the designer's reply
  is text; the result PNG sits in a design bundle; no step registers it with the uploads
  route or references it from a message. That last mile is the only missing piece (§3).

---

## 2. Spec — Uploads

**Route:** the existing one. `POST /api/agents/{id}/upload` → `GET /api/uploads/{file_id}`.
No new endpoint, no kernel change. The work is in the Home composer (statics) plus one
optional API-layer hardening.

**U-1 — Restore the attach affordance on Home (statics only).**
- Add the paperclip button + hidden file input to the Home composer, reusing the stock
  markup and the sprite's paperclip glyph through the single icon swap point (Verdict 3
  icon law), beside the "Ask Stax" textarea (`index_body.html:648-662` region).
- Add the attachment preview strip above the composer (the stock chip markup,
  `index_body.html:861-872`, restyled to the Home sheet).
- Fix the send enablement to the stock condition: send when text *or* attachments are
  present; the Enter-key handler likewise.
- Wire the existing `handleDrop` onto the Home sheet as a drop zone (drag-over styling in
  the sheet's own idiom).
- `accept` list: keep the server's truth — `image/*,.txt,.pdf,.md,.json,.csv` plus audio.
  All flow logic already exists in `chatPage.sendMessage()`/`addFiles()`; the Home
  composer calls the same functions today. This slice is markup + two conditions.
- Gate: owner-seat proof — attach a photo on the phone, see the chip, send, see the image
  in the thread, and (with U-3 verified) Stax's reply proves it saw the image.

**U-2 — Storage: binaries are files; kv never carries them.**
- Today: `$TMPDIR/openfang_uploads/<uuid>` + in-memory registry. Honest label for v1:
  attachments are *turn-scoped* — good enough to show Stax a reference and have it routed
  to a design job in the same working session (the sidecar copies what it needs, U-4).
- **Hardening (API layer only, `routes.rs`):** point the upload dir at
  `~/.openfang/data/uploads/` and persist the registry to a JSON file beside it, loaded at
  boot. Two contained changes in the API crate; no kernel, no data-model change. This makes
  an attachment survive restarts and makes `file_id` a durable reference the rest of this
  spec can lean on. Recommended before the designer loop (§3) is declared done, not before
  U-1 ships.
- Never store image bytes in kv. (The design library's small inline elements are a bounded
  exception inside the Canvas package, not a pattern to generalize; a 10 MB upload in a
  JSON store would poison every kv snapshot read.)

**U-3 — Presentation to the turn.**
- Images: already resolved into `ContentBlock::Image` and injected (`routes.rs:250-376`).
  At build time, verify the daemon default model accepts image parts end-to-end on the box
  (one live turn with a photo, read back). If the default model is not vision-capable, the
  playbook route is: reference-bearing asks go to deep-work (Kimi — vision-proven) via the
  lead's normal routing, and the lead says so in its one status line. No code either way.
- Non-image files: today the model sees only `[File: name]`. Spec keeps that for v1 and
  labels it honestly in the UI chip (a document is *attached*, not *read*). Turning
  document contents into turn content (PDF/text extraction) is an exception candidate —
  §6, not v1.
- Limits: keep the shipped ones — 10 MB/file, the existing type allowlist, multiple files
  per message. The public-by-UUID serve route is acceptable for owner-uploaded references
  (unguessable id, same posture the TWA download uses); note it plainly in the build's
  evidence, don't silently inherit it.

**U-4 — Reference flow into the design path.**
- An uploaded image's durable handle is its `file_id` (post U-2). When the owner attaches
  a reference and asks for design work, the lead routes to the designer with the file_id
  named (playbook line); the designer writes the `designjob/` record carrying
  `reference_upload: <file_id>`; the Canvas sidecar — same box, deterministic — copies
  `$UPLOADS/<file_id>` into the design workspace as the job's reference file (the job
  protocol already speaks in `file:` paths) and proceeds exactly as it does for a cover-up
  reference today. No base64 through kv, no new service.

---

## 3. Spec — Image generation inside the chat

The loop the owner asked to test, expressed with the machinery that already exists:

1. **Ask.** Owner, in the main chat: "Make me a dagger-and-rose flash piece from this
   photo, black and grey, for a forearm" — with the photo attached (U-1/U-4). He sees his
   image in the thread (already renders) and one status line from Stax (playbook rule 11).
2. **Route + job.** The lead routes to the designer (`agent_send`, as today); the designer
   composes the designjob per its playbook — artist profile + style preset resolution
   exactly as the Canvas package already does (per-artist opt-in, versions-per-request,
   reference-anchored mode preferred) — naming the reference upload. Stax's reply in the
   thread is words: what's being made, for whom, how many versions.
3. **Execute.** The Canvas sidecar runs the job (unchanged machinery) and lands the design
   record + bundle files (unchanged).
4. **Result in the thread — the one new mile.** On completion the sidecar registers each
   result PNG with the uploads route (it is an HTTP client of the daemon already; the
   upload endpoint is the same one the browser uses) and stamps the returned `file_id`s
   into the design record. The designer's completion turn then emits an **image block**
   (§4) pointing at those file_ids. The owner sees the actual images *in the conversation*,
   under Stax's reply — not a file path, not "saved to memory."
5. **Iterate by reply.** "Deepen the shading," "try it as linework only" — the lead routes
   a follow-up designjob (edit ops already exist in the Canvas job protocol: edit.request /
   edit.apply with revision discipline), and the new version lands in the thread the same
   way. Versions accumulate in the design record; the thread shows each as it arrives.
6. **Approval stays approval.** Nothing customer-facing leaves from the thread; if a
   design is to be sent to a client, it goes through the existing Needs-you machinery —
   the thread can carry the approval *card* (§4.4), the queue of record stays Work.

**What about the kernel's `image_generate` tool?** Not part of the recommended loop: it is
text-only (no reference input), needs an OpenAI key the box doesn't have, and bypasses the
Canvas package's artist profiles, layer discipline, and style presets — the things that
make shop designs come out as *his* designs. If the owner later wants quick non-design
images in chat (a meme for a post, a moodboard pull), granting the tool to deep-work plus
setting `OPENAI_API_KEY` (or an `image_gen_base_url`) is a configuration + playbook step,
no build — his call, recorded as an option, not a dependency (§6).

---

## 4. Spec — Blocks in the conversation

### 4.0 The carrier decision (applies to every block)

**Decision: the payload lives in a kv record; the message carries a one-line reference.**
A crew member that wants to show a block writes `chatblock/<uuid>` via `memory_store`
(tools every crew hand already holds) and includes in its reply text a single reference
line the renderer recognizes and replaces with the card:

```
[[block:chatblock/<uuid>]]
```

Why this carrier, against the alternatives:

- **It survives history.** Session history is rebuilt from stored messages; a reference in
  the stored text round-trips through WS, HTTP, and the history read with zero API or
  kernel change. (A payload embedded in the message JSON would need the message model —
  kernel territory — to change.)
- **The payload stays out of the token stream.** Blocks are data for the owner's eyes;
  embedding them in message text would feed them to the compactor and every later turn.
  A kv payload is also *inspectable and cleanable* (the Round C hygiene pattern) and
  *updatable* — a card whose state changes (an approval decided elsewhere) re-reads its
  source of truth instead of freezing a copy.
- **Failure is quiet.** If the record is missing or malformed, the renderer shows a plain
  one-line note ("That card isn't available anymore") — never the raw marker, never JSON
  (the H-1/H-2 lesson: machinery text in the owner's bubbles is the defect class this
  whole mechanism must be built to make impossible). The marker line is stripped by the
  markdown pipeline before display in all paths, including failure.
- **Authorship is crew-only by construction.** Only agent turns can write kv; the owner
  cannot be sent a block by anyone else, and the renderer validates every payload against
  a fixed type allowlist + per-type schema before drawing anything. All text fields are
  escaped; no block type renders raw HTML (see §4.5).

Renderer home: the Home thread's message rendering (`index_body.html` home template +
`js/pages/home.js`/`chat.js`), reusing the surface block vocabulary where the shapes match
(§1.4 precedent 1). Blocks render *inside* the owning message's card, beneath its text —
the same slot tool images already occupy.

**The tool question.** Crew create blocks with `memory_store` + a playbook convention
(the stax/designer/surface-builder playbooks name the block types and payload shapes —
the same discipline as `designjob/` and `surface/` composition today). A dedicated
`chat_block` kernel tool would be nicer (schema-validated at call time) but the tool
catalog lives in the runtime — that is a **kernel-side change and is flagged as an
exception** (§6), not assumed. v1 proves the pattern with the kv carrier; if block
authoring becomes frequent, the tool is the owner's call with this spec as its brief.

### 4.1 Browser card

- **Reference shape:** a dark card: page title, domain, a screenshot thumbnail, an
  **Open browser** button; status line while the visit is in flight ("Completed" in the
  reference).
- **Data:** `{type:"browser", title, url, screenshot_file_id?, summary?}` — payload in
  `chatblock/`, screenshot (when any) served via `/api/uploads/<file_id>`.
- **Producer:** an agent that actually visited the page. Upstream tooling exists —
  `web_fetch` / `web_search` and a full `browser_*` toolset including
  `browser_screenshot` (`tool_runner.rs:212-435`) — but **no Fang crew hand holds those
  tools today, and whether a headless browser runs on Sarah's box is unverified.** v1
  therefore scopes the card to *fetched* pages: title + URL + agent's one-line summary,
  screenshot only when a producing path exists. Verifying the browser tools on the box
  is a build-time check, not a spec assumption.
- **Fidelity note:** the reference card shows the page rendered *live inside* the card.
  Arbitrary sites refuse framing (X-Frame-Options/CSP) and a live webview inside the
  owner's authenticated app is a security posture of its own. v1 is screenshot + Open
  (the Open button follows the Amendment 2 link rules). Live embed: not recommended (§5).
- **Interaction:** read-only; Open follows the link in a new tab.

### 4.2 Scheduled-task card

- **Reference shape:** calendar icon, task name, "Scheduled task" label, the schedule in
  words ("tomorrow, Sunday … at about 9:00 AM"), a **View scheduled task** button.
- **Data:** `{type:"task", job_id}` — a *pointer only*. The card's truth (name, cron
  expression in words, next run, enabled) is read live from `GET /api/cron/jobs`
  (existing API, `server.rs:646-662`) at render time, so the card can never wear stale
  state — the Work W-7 lesson (decided cards wearing pending copy) applied in advance.
- **Producer:** the lead already holds `schedule_create` / `schedule_list`; when a turn
  creates or confirms a task, its reply carries the block. (The standing playbook rule —
  never create schedules inside conversation turns unless the owner is asking for exactly
  that — is unchanged; the card *reports* a task, it doesn't license creating them.)
- **Interactions:** View → the task's detail (Scheduler surface in Advanced, or the
  job's plain detail card); Pause/Resume → `PUT /api/cron/jobs/{id}/enable` (existing).
  Both reuse existing endpoints; no parallel scheduler state.

### 4.3 Choice buttons

- **Reference shape:** a short question with full-width tappable options ("Remove the
  example scheduled task" / "Keep the example scheduled task").
- **Data:** `{type:"choices", prompt?, options:[{label, send}]}` — `send` defaults to the
  label.
- **Interaction:** a tap sends `send` as the owner's next message (`sendMessage()`), so
  the conversation itself is the state machine — exactly how the shipped setup flow's
  in-thread reply buttons already work (§1.4 precedent 2). No callback endpoint, no
  hidden state; the owner's tap is visible in the thread as his own message, and the
  record can stamp itself answered (renderer reads the following user message).
- **Producer:** any crew hand via the §4.0 carrier. Playbook guidance: choices are for
  *owner decisions the agent would otherwise ask in prose* — the decision lands in the
  transcript either way; the buttons just make it one tap.

### 4.4 Approval card (the embedded-HTML demo's real need)

- **Reference shape:** a card titled with the action, a plain description, **Approve** /
  Reject buttons, and a state line ("Not approved · Test taps: 0" in the demo).
- **Data:** `{type:"approval", approval_id}` — pointer only. Title, description, and
  **status are read live from the existing approvals API**; Approve/Reject call
  `POST /api/approvals/{id}/approve|reject` — **the existing machinery, never a parallel
  one.** After action, the card re-reads and wears its decided state in decided words
  (the W-7 copy defect is designed out here from the start, not patched later).
- **Relationship to Work:** Work (Needs you) stays the queue of record and the Home
  Needs-you row keeps counting from the same API. The in-chat card is a *second window
  onto the same approval*, for the moment the owner is already looking at the thing —
  approving in either place decides it in both, because there is only one record.
- **Producer:** whoever raises the approval (today: pull-sync's draft phase stamps
  approvals; a crew turn that creates one can carry the block in the same reply that
  explains it). TTL honesty: approvals are a live-action gate (≤300 s in-memory) — if
  the approval has expired by render time, the card says so plainly and points at Work.

### 4.5 Embedded HTML block — specified, and recommended NOT to build in v1

The demo's approval card was arbitrary HTML/JS rendered inside the chat bubble, with
working buttons and remembered state. In Fang that pattern has a specific danger the
demo doesn't: **the chat page is the owner's authenticated session.** Arbitrary HTML/JS
in the page's own origin can reach everything the page can reach. Crew-authored or not,
one bad generation turns "the agent can show me things" into "the agent can act as me,"
silently. The two concrete needs inside the demo are already covered natively —
interactive approval = §4.4, stateful buttons = §4.3.

If the owner later wants it anyway, the only acceptable shape: an `<iframe>` with
`sandbox="allow-scripts"` and **never** `allow-same-origin`, `srcdoc` payload from the
block record (size-capped), no access to the page's storage/token (the sandbox origin is
opaque by construction), crew-only authorship, and a visible "interactive card" frame so
it never masquerades as Stax's words. Flagged here as the riskiest item in this spec;
deferred until a real need survives the typed blocks.

### 4.6 List card

- **Reference shape:** native rows — plain items, links, calendar/email-style entries,
  tap-to-send replies.
- **Data:** `{type:"list", title?, items:[{label, sub?, href?}]}` — deliberately the
  **same item shape as the surface `list` block** (§1.4), so one renderer vocabulary
  serves Boards and chat, and the surface-builder's composition discipline carries over.
- **Interaction:** rows with `href` follow the Amendment 2 link rules; a row may instead
  carry `send` (tap = send as message, §4.3 mechanics) for reply-style lists.

### 4.7 Map card + place card

- **Reference shape:** a small map with a pin, then a place card (name, "Local place",
  full address).
- **Data:** `{type:"place", name, address, lat?, lng?, note?}`.
- **Rendering:** v1 is a **data card** — name, address, note, and an "Open in Maps" link
  (external maps app) — with **no third-party tile dependency**. A live tile embed
  (OpenStreetMap iframe, as in the reference) is an optional dressing: it adds an
  external network dependency to the owner's home screen and an iframe to the thread;
  include it only behind the same framing discipline as §4.5 and only if the owner
  wants the picture. The studio's own address is a record (setup/profile + the site
  knowledge), so the common case — "show me / show the client where we are" — needs no
  geocoding service: lat/lng ride in the payload when the producer knows them.
- **Producer:** any crew hand composing from records (an artist's location, a client's
  address on file); no new service.

### 4.8 Forms and websites as blocks (the owner's "same with forms, websites")

**Form block** — `{type:"form", form_slug}` (pointer; fields read from the live
`form/<slug>` record, the R7 spine):

- *Owner-facing mini-form:* when Stax needs structured answers from the owner (shop
  details, a style preset's fields), the block renders the form's fields inline in the
  thread; Submit writes through the same dashboard kv path the setup flow already uses
  from the frontend — answers land as records, and Stax's next message confirms what was
  saved (read back, per playbook rule 14). This generalizes the setup conversation from
  a hard-wired flow into a reusable shape.
- *Customer-facing form:* the block is a **share card** — form title, what it's for, the
  public link, and submission count read from the forms spine — so "send Maria the
  consent form" produces the card in the thread; the actual collecting still happens on
  the hosted public form (Cloudflare Pages intake, already built) and submissions still
  arrive through pull-sync. The block never becomes a second intake path.
- Round E's block-builder grows form *definitions*; this block only *renders* them —
  no dependency conflict (§5).

**Website block** — `{type:"site", title, url, screenshot_file_id?, note?}`: the browser
card's sibling for pages that are *ours* — the studio's site, a preview the
surface-builder produced, a published form page. Same read-only card + Open; the
difference is provenance (a surface-builder/designer artifact, not a fetched page) and
the action set (Open + "Ask for changes," which sends the owner back into conversation
with the surface-builder — no in-card editing in v1).

---

## 5. Sequence — foundation order, sizes, and how it interleaves

Sizes are honest single-builder slices including their owner-seat gates, in the project's
usual currency (one slice ≈ one build + staging proof + deploy window).

| # | Slice | Size | Depends on | Slot |
|---|---|---|---|---|
| 1 | **U-1 Home attach restore** (§2) — button, chips, drop zone, send condition | **S** | nothing | **First.** Rides the NEXT-BUILD window beside H-1/H-2 (all three are Home-thread work) or stands alone before Round B — it is the owner's witnessed defect and the foundation everything else touches |
| 2 | **U-2 Upload durability** (§2) — persistent dir + persisted registry (API layer) | **S** | U-1 (to be worth hardening) | Same window as #1 if the API touch is welcome then; otherwise immediately after — must land before #4 is declared done |
| 3 | **Blocks v1 renderer + carrier** (§4.0) with **choices, list, image** block types | **M** | U-1 (image block consumes uploads) | With **Round B** — the Boards renderer cleanup (JSON fallback deletion, typed renderers) and the chat renderer are one vocabulary; building them together keeps the Ratchet's one-home rule. Playbook updates for stax + surface-builder ride along |
| 4 | **Designer-in-chat loop** (§3) — reference upload → designjob → result image blocks in thread | **M** | U-2, #3 (image block), Canvas sidecar as-is | After Round B, before or fused with the **Canvas app surface slice** (the thread loop is the thinner half of that slice and proves the result path the surface will reuse) |
| 5 | **Approval + task cards** (§4.4, §4.2) — pointer blocks over existing APIs | **S–M** | #3 | With the **Work build** slot (W-1…W-4, Verdict 4 §3 composition) — in-chat approval cards and Work's composition are the same subject seen from two sides; building them together prevents a second approvals dialect |
| 6 | **Browser + site + place cards** (§4.1, §4.7, §4.8) | **S** | #3 | Polish-adjacent; any round boundary. Browser screenshot support only if the box browser check passes |
| 7 | **Form block** (§4.8) | **S** (render) | #3; definitions grow in Round E | Render slice can ride #3; the owner-input submit path aligns with **Round E** (Forms builder), where form semantics are already in motion |
| — | **Embedded HTML** (§4.5) | **L** | — | **Not scheduled.** Owner call if a typed block ever fails a real need |

**Interleaving rules (so the rounds' gates stay honest):** no slice inserts itself into a
round already in flight; #1 is the only piece allowed to jump the queue, because it repairs
an owner-witnessed absence on the product's face and touches nothing the rounds own. Round
C (Leads) and Round D (Texts/Connections) are untouched by this spec — the blocks work
neither needs nor changes their scope. Step 1.5's avatar view is unaffected.

**Explicitly NOT to build:**

- **No parallel approvals.** Any design that stores approval state in a block record
  instead of reading the approvals API is rejected at brief time (§4.4).
- **No live webview / arbitrary HTML in v1** (§4.1 fidelity note, §4.5).
- **No image bytes in kv, no second file store.** Uploads route + design files are the
  two homes; blocks point, they don't carry (§2 U-2, §4.0).
- **No new "media service."** The daemon's upload route + the Canvas sidecar cover every
  flow in this spec; a third carrier is how wiring stops speaking one language.
- **No block types beyond the reference set in v1.** The vocabulary grows by owner-seen
  need (the surface system's discipline), not by anticipation.

## 6. Exceptions — where this spec touches the wiring law (owner's word required)

v1 of everything above needs **no kernel change**. These are the points where going
further crosses the line the wiring law draws, named in advance so none arrives as a
surprise inside a build:

1. **A real `chat_block` tool** (schema-validated block authoring instead of the kv +
   marker convention) — a new tool in the runtime catalog (`openfang-runtime`). Smallest
   shape: one tool, `chat_block {type, payload}`, result rendered by the §4 renderer;
   the kv carrier retires. *Owner call; not needed for v1.*
2. **Document content into turns** (PDF/text extraction so an attached document is read,
   not just named) — the media/link-understanding engines exist upstream but are not
   wired into the attachment path (API + runtime seam). *Owner call; v1 labels documents
   as attached-not-read.*
3. **The kernel `image_generate` tool for chat** — no code change, but two owner-level
   decisions ride with it: an OpenAI key (or compatible endpoint) on the box = a new
   credential and a new spend line, and accepting a second, non-Canvas image dialect in
   the product. *Owner call; §3 recommends the Canvas loop instead.*
4. **Embedded HTML** (§4.5) — presentation-layer only, but a security-posture decision,
   which in this project is always the owner's. *Owner call; recommended against.*

## Appendix A — Reference screenshots (owner's, 2026-11-03)

Filed in `screenshots/blocks-reference/`:

| File | Shows |
|---|---|
| `browser-card-fargotattoo-gallery-intro.png` | Browser card (Completed, page preview of fargotattoo.com, Open browser) + gallery intro |
| `scheduled-task-card-and-embedded-html.png` | Scheduled-task card (View scheduled task) + embedded HTML block header |
| `list-card-and-map-card.png` | List card (native rows, links, tap-to-send) + map card |
| `map-card-and-place-card.png` | Map card + place card (Fargo Tattoo, address) |
| `embedded-html-approval-demo-and-choice-buttons.png` | Embedded HTML approval-card demo (Approve / Test tap, state line) + choice buttons |
| `gallery-rundown-text.png` | The gallery's own rundown: scheduled task / embedded HTML / choice buttons / list / map |

## Appendix B — Citation index (all read firsthand, 2026-11-03)

- Home composer (no attach): `crates/openfang-api/static/index_body.html:648-662`
- Home template = chat page, same component/transports: `index_body.html:502-512`
- Home renders user images / tool images: `index_body.html:573-575` / `:561-562`
- Stock composer attach UI: `index_body.html:861-896`
- Client upload + send flow: `static/js/pages/chat.js:1100-1121, 1172, 1189, 1290-1325`; `static/js/api.js:313-325`
- Upload handler, limits, storage, registry: `crates/openfang-api/src/routes.rs:10528-10740`
- Serve route + public-GET exemption: `server.rs:295-296`; `middleware.rs:111`
- Attachment resolution + session injection: `routes.rs:250-376`; WS: `ws.rs:638-647`; SSE gap: `routes.rs:1577`
- Message/content model: `crates/openfang-types/src/message.rs:63, 86-105`
- Driver image handling: `crates/openfang-runtime/src/drivers/openai.rs:528`; vision flags: `openfang-runtime/src/model_catalog.rs:1082+`
- Kernel image tools: `tool_runner.rs:335, 901-1054`; engine: `openfang-runtime/src/image_gen.rs:1-60`
- Surfaces/blocks vocabulary: `index_body.html:5241-5325`; `js/app.js:1148+`; `~/workspace/openfang-fork/R6-SURFACES-PLAN.md:12`
- Approvals + cron APIs: `server.rs:537-545, 646-662`
- Chat render rules / filters: `js/app.js:24, 66`; `js/pages/home.js:165-168`
- Designer hand tools: `stax/hands/designer/HAND.toml:6`; lead tools/model: `stax/hands/stax/HAND.toml:6, 13`
- Canvas job path: `~/workspace/canvas-ops-wiring/RESULTS17-FANG-OPS.md` (designjob/ queue, design/ results, `file:` job references, reference-image cover-up leg)
