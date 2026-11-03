# DATA MIGRATION MAP — Production StaxCloud (Dell) → OpenFang Fork ("the new StaxCloud")

**Status:** census + mapping only. Read-only on both systems; no record was written,
moved, or deleted anywhere. **Date:** 2026-11-02. **Decisions needed:** §11 (director).

**Method.** Source census ran over the production StaxCloud owner API on the Dell
(127.0.0.1:3121), using the same session pattern the modem bridge uses
(password login → cookie; credential read from the bridge env at runtime, never
printed). Target census read the Fang kv store directly
(`~/.openfang/data/openfang.db`, SQLite `mode=ro`, table `kv_store`).
**No PII appears in this document** — counts, field names, and shapes only.

---

## 0. The one discovery that shapes everything: artist scoping

StaxCloud scopes nearly every read to an "active artist." The default owner
session sees **Artist A (staff `b1070e91…`) only**. The scope switches with an
`X-Artist-Id` header (query-param variants are ignored). Under Artist B's scope
(staff `1e11bee0…`) a second, disjoint book appears. Any census — or import —
that skips the header pass silently loses Artist B's data. True totals are the
sum of both scopes:

| Family | Artist A scope | Artist B scope | **Total** |
|---|---|---|---|
| Clients (contacts) | 143 | 23 | **166 rows** |
| Form definitions | 15 | 3 | **18** |
| Form submissions | 216 | 26 | **242** |
| Records docs (notes) | 19 | 2 | **21** |
| Projects (via client records) | 63 | 1 | **64** |
| Appointments | 22 | 0 | **22** |
| Studio assets (Library) | 7 | 0 | **7** |
| Site pages | 2 | 0 | **2** |
| SMS threads | 2 (87 messages) | 0 | already synced — §4.8 |

Staff roster = 2 records (`{active, color, id, name}`). Which staff id is
`artist/shawn` and which is `artist/leni` is resolved at build time (§5) — the
census deliberately does not print names.

---

## 1. Source census — production StaxCloud (Dell)

### 1.1 Clients — 166 rows (143 A + 23 B)
Fields on every row: `id, person_id, name, email, phone, artist_id, artist_name,
status, lead_status, source, notes, has_prep, summary_only, visits, points,
total_spend, square_customer_id, square_card_id, first_seen, last_interaction,
created_at, updated_at`. All `status = active`.

- **Attribution is explicit**: every row carries `artist_id` + `artist_name`;
  each scope's rows belong entirely to that scope's artist.
- **Source mix:** form 152 (A 129 + B 23), manual 9, booking 4, inquiry 1.
- **Lead status today:** `cold` 165, `hot` 1 — a two-value vocabulary (§10).
- **Identity coverage:** has email 159, has phone 162, has both 157,
  email-only 2, phone-only 5, **neither 2** (both in A scope — unkeyable, §4.1).
- **Duplicates:** 0 duplicate emails; 1 phone shared by 2 A-scope rows.
- **Cross-scope people:** 3 emails and 3 phones appear in **both** scopes —
  the same people are clients of both artists (166 rows → 163 unique people
  by email; §4.1 merge rule).
- **Notes:** 102 of 166 rows carry a notes text (A 101, B 1).
- **Commercial rollups are empty:** `total_spend > 0` on 0 rows, `points > 0`
  on 0, `square_customer_id` set on 0. `visits > 0` on 159 rows (real data).
- `person_id`: only 24 distinct values across A scope's 143 rows — semantics
  not established by the census (carried as provenance, §8).
- A-scope clients span back to at least 2026-03; B-scope clients were created
  2026-09-08 → 2026-10-28 (a newer, all-form-born book).

### 1.2 Form definitions — 18 (15 A + 3 B)
Fields: `id, name, description, fields[], blocks[], design{font,theme},
layout{embed_type,form_layout,form_width}, settings{language,post_submit},
integrations{}, template_type, schema_version, published, folder_id,
draft_revision_id, created, updated`. Field/block item shape (identical for
both): `{config, id, label, order, required, type}`.
7 of A-scope's 15 are published. A-scope folder: 1 form folder exists.
Field `type` vocabulary observed (both scopes): `field-name, field-email,
field-phone, field-short-text, field-long-text, field-dropdown, field-choice,
field-file, field-image-choice, field-consent, artist-select, booking-form,
booking-widget, customer-service, studio-ref-images`, and the consent family
`consent-client-info, consent-tattoo-details, consent-medical,
consent-medical-disclosure, consent-minor-parent, consent-legal,
consent-aftercare, consent-photo-release, consent-touchup, consent-initials,
consent-signature`, plus layout types `field-heading, field-paragraph`.
The system's form-design vocabulary also lives in `/api/forms/recipes`
(13 recipes, aliases `booking-form / consent / contact / minor-consent`,
block defaults) — configuration, not customer data (§8).

### 1.3 Form submissions — 242 (216 A + 26 B)
Fields on every row: `id, form_id, form_name, client_id, client_name,
client_email, data{}, files{}, evidence{}, evidence_sha256, evidence_state,
form_fields_snapshot[], form_name_snapshot, form_revision_id,
renderer_version, snapshot_taken_at, snapshot_version_hash, status,
needs_triage, ip, submitted`. All `status = submitted`; `needs_triage` false
on all 242. Submitted range: 2026-03-03 → 2026-10-27.

- **Orphans dominate A scope:** only 95 of A's 216 submissions sit on a live
  form def; **121 rows reference 8 form ids with no live def** (deleted or
  replaced forms — the consent forms churned). Every submission carries
  `form_name_snapshot` + `form_fields_snapshot`, so orphan defs are
  reconstructable (§4.3). B scope: 26 submissions across its 3 live forms.
- **Evidence split:** `evidence_state = ready` on 48 rows (A 22 + B 26),
  `legacy` on 194 (all A). The ready set carries the full evidence bundle
  (`answers, artist_assignment{…10 keys}, attachments[], form_document,
  raw_values, …`); `artist_assignment` includes `selected_artist_id` —
  submission-level attribution, agreeing with scope in the ready set.
- **Attachments (A scope):** `files` non-empty on 6 rows; `evidence.attachments`
  non-empty on 22. (B-scope attachment counts were not separately taken —
  the translator reports both scopes.) Binaries sit behind
  `/api/forms/submissions/{sid}/attachments/{aid}` (§8 — metadata now,
  bytes are a phase-2 decision).
- **Every row carries the submitter's `ip`** — deliberately NOT migrated (§8).
- Record-view linkage (submissions visible inside client records) totals 209
  of 242; the remaining 33 don't resolve inside either scope's client views.
  The translator links by `client_id` across both scopes and counts the
  unresolvable (§9) — submissions carry name/email snapshots and stay
  intelligible unlinked.

### 1.4 Projects — 64 (63 A + 1 B), via client record views
Shape: `{id, name, description, status, total_price, created_at, updated_at}`,
client linkage via the owning client record. Statuses: active 57,
in_progress 1, completed 5, archived 1. **This is the shop's live book of
work** — 57 active tattoo projects. No Fang primitive exists yet (§4.4, Q1).

### 1.5 Appointments — 22 (all A scope, all past: 2026-03-04 → 2026-07-22)
Shape: `{id, client_id, client_name, client_email, client_phone, date, time,
start_time, duration, service, status, notes, custom_description, deposit,
deposit_amount, deposit_paid, staff_name, staff_color, created_at}`.
Statuses: confirmed 19, pending 3. All 60-minute, one staff member,
`deposit_paid` on 0, 18 of 22 carry `client_id`. Attribution is the
denormalized `staff_name` string — no `artist_id`. Square Appointments is
the live booking system; this family is **history only** (§4.5, Q2).
(The per-client record view exposes a 7-row subset of this family; the
appointments endpoint is authoritative.)

### 1.6 Records docs — 21 (19 A + 2 B)
Shape: `{id, title, mode, content[{type, text}], artist_id, client_id,
appointment_id, folder_id, image_refs[], source, status, revision,
created_at, updated_at}`. Modes: note 17, session 3, consultation 1.
All `source = human`, all `active`. 7 are client-linked (A scope);
the other 14 carry an empty `client_id` (studio-level notes).
`image_refs` non-empty on 0 docs. 1 doc folder exists (A scope; folder
records carry `artist_id, client_id, kind, parent_id, …`).

### 1.7 Studio assets (Library) — 7 assets, 1 collection (all A scope)
Asset shape: `{id, title, artist_id, purpose, origin, source{client_id,
client_image_id}, status (draft 3 / approved 4), rights_state, style_state,
style_notes, collection_ids[], current_revision{sha256, byte_size, mime,
width, height}, revision, approved_at, url, created_at, updated_at}`.
Collection shape: `{id, name, artist_id, purpose, brief, asset_count, status,
revision, created_at, updated_at}`. Asset bytes are fetchable at
`/api/studio/assets/{id}/bytes`. `source.client_image_id` is null on all 7
(none originated as client uploads).

### 1.8 Artist profiles — 2 (one per scope)
`/api/staxbox/profile` under each scope returns that artist's public profile:
`{artist_id, name, bio, tagline, specialties, style_tags, experience,
years_experience, pronouns, location, instagram_url, website_url,
booking_notes, cover_up_capable, cta_label, appearance{}, visibility{},
profile_template, …}` — materially richer than Fang's current `artist/*`
records (§4.7).

### 1.9 Config & empty families (censused, not customer data)
Teams 1; booking widgets 1; services **0** (Square is the services/booking
record); CS (website chat) conversations **0**; flashbooks **0** books;
form recipes 13 (system vocabulary, §1.2); availability config exists
Dell-side (not censused — it is shop config, and Square owns availability).

### 1.10 Unreachable without root — named gap
`/var/lib/staxbox/data` is locked to the `staxbox` service user; the census
used the owner API only, per the read-only brief. The kernel database also
holds agent-side families the owner API doesn't enumerate (from the kernel's
own schema notes: `logic_cards, memory_entries, agent_facts, cs_knowledge,
claw_messages, claw_conversations, onboarding_tokens, widget_artists`).
Unblocking would take an owner-run export or a root window on the Dell.
**Recommendation: out of migration scope by design** — they are the old
system's agent working state, not Fargo Tattoo business records; the fork's
crew builds its own memory. One exception to eyeball at build time:
`cs_knowledge` (if it holds shop-facing Q&A copy, that's content — but CS
conversations are 0 and widgets 1, so exposure looks minimal). Q9.

---

## 2. Target census — Fang kv store (Sarah's box, 2026-11-02)

`kv_store`: **66 rows total.** Business families:

| Family | Count | Notes |
|---|---|---|
| `contact/` | 4 | **All test-era records** (Round C deletes them) |
| `form/` | 1 | `form/contact` — the live intake form |
| `formsub/` | 5 keys | 3 well-formed (`formsub/contact/<uuid>`); 1 unslugged duplicate, 1 bare `formsub/` debris key |
| `draft/` | 5 | 4 `in-needs-you`, 1 `decided`; includes the R12 zombie SMS draft and one literal `draft/<uuid>` debris key |
| `sms/` | 3 | 2 bridge-mirrored Dell threads + 1 test thread (Round C) |
| `smsout/` | 3 | all `delivered` |
| `artist/` | 3 | `artist/index`, `artist/shawn`, `artist/leni` |
| `surface/` | 2 | `surface/designer`, `surface/seo` boards |
| `brief/` | 1 | today's brief |
| `crew/health` | 1 | tripwire record |
| `design/ designjob/ designrec/ designreq/` | 4 + indexes | Canvas (Designer) landing, Fang-native |
| `work/` | 1 | a research finding record, Fang-native |
| *(no-slash keys)* | 32 | stock-agent scratch state (`lead_hand_*`, demo trackers, `*_name`) — not business data |

**Established target shapes (read from live records):**

- **Contact** (richest live instance): `{name, email, phone, entity_id,
  source_form, first_seen, last_seen, visits, notes[{ts, text}]}` — leaner
  instances carry subsets (`{name, email}`, `{name, phone}`). **No artist
  field exists in any current Fang contact** — attribution is a shape
  extension this migration introduces (§4.1). `notes` is a **list** of
  `{ts, text}`.
- **Form def** (`form/contact`): `{title, fields[{key, label, required,
  type}], public_url}` — field types in use: `text, email, phone, textarea`.
- **Form submission**: `{form (slug), uuid, ts, source, data{…},
  processed, contact (key), draft (key)}`, some carry `test: bool`.
- **Draft**: `{approval_id, kind, status, …}` (form drafts add
  `form, submission, text, to_name`; SMS drafts add `body, thread, to`).
- **SMS thread**: `{number, name, thread_id, messages[{id, dir, body, ts,
  status}]}` — maintained by the bridge.
- **Artist**: `{artist_id, display_name, allow_customer_designs,
  approved_library[], generated_history[], specialties[], style_note,
  styles[], versions_per_request}` — design-offering focused.
- **Surface/board**: `{title, blocks[]}`.
- The kv store also sits beside non-kv tables (`entities`, `relations`,
  `memories`, `sessions`, …). Contact records reference an `entity_id`;
  the translator does **not** write graph rows (§8).

---

## 3. Identity & dedupe rules (apply to every family)

1. **Contact key = the established Fang index**: `contact/<email>` when the
   person has an email (normalized: trimmed, lowercased), else
   `contact/<phone-digits>` (digits only, leading US `1` stripped). This is
   the rule the live Forms pipeline already dedupes by; the import uses the
   same rule so imported and live-born records collide into one home.
2. **Email wins over phone** as the primary key. Phone is a secondary match
   key only for rows that lack an email. The 1 source phone-collision pair
   (two rows, one phone) is listed in the import report by count for owner
   eyeballing — never auto-merged on phone alone when both rows have emails.
3. **Cross-scope merge**: where the same normalized email (or, failing that,
   phone) appears in both artists' scopes, the import writes **one** contact
   carrying both attributions (§5). Expected merges: 3.
4. **Unkeyable rows**: the 2 A-scope clients with neither email nor phone are
   never keyed by name. They land in a single `migration/unkeyed` holding
   record (full source rows, counted, owner-dispositioned later) — visible,
   never silently dropped.
5. **Deterministic keys everywhere**: form submissions reuse the source
   submission's UUID as the Fang record UUID; form defs, projects, notes,
   and assets key by a slug derived in §4 plus the source id carried inside
   the record. Re-running the import targets the same keys (§9).
6. **`import_hash`**: every imported record carries
   `staxcloud: {…, import_hash}` = sha256 of the canonical source record.
   A re-run skips records whose stored hash matches the source's current
   hash — idempotent and cheap (§9).

---

## 4. The map — family by family

### 4.1 Clients → `contact/`
**166 rows → ~163 contacts + 1 holding record.**

Target record (a superset of the established Fang contact shape; new fields
marked ★):

```jsonc
contact/<email|phone-digits> = {
  "name": str, "email": str|null, "phone": str|null,
  ★"artist": "shawn"|"leni",            // primary attribution (§5)
  ★"artists": ["shawn","leni"],          // only when >1 scope claims them (3 people)
  "source": "form"|"manual"|"booking"|"inquiry",   // source.source verbatim
  "source_form": <form slug>,            // when source=form and the form resolves
  ★"lead_status": "cold"|"hot",          // carried verbatim pending Q4
  "first_seen": ts, "last_seen": ts,     // from first_seen / last_interaction
  "visits": num,
  "notes": [ {"ts":…, "text":…}, … ],    // source notes text = first entry;
                                          // appointment history folds here if Q2 = yes
  "staxcloud": { "ids": [source client ids], "person_id": str,
                 "artist_ids": [staff ids], "import_hash": "…" }
}
```

- Fields dropped: `points`, `total_spend` (zero on all 166 rows — dropping
  empty rollups, not data), `square_customer_id`, `square_card_id` (unset on
  all rows), `has_prep`, `summary_only` (false on all rows), `status`
  (uniformly `active`), `artist_name` (denormalized copy of the attribution
  the slug now carries). `entity_id` is **not** carried — Fang's graph mints
  its own (§8).
- Merge rule for the 3 cross-scope people: one record; `artist` = the scope
  with the later `last_interaction`; `artists` lists both; `notes` entries
  from both rows, source-tagged; `visits` summed; `first_seen` = earlier,
  `last_seen` = later.

### 4.2 Form definitions → `form/<slug>`
**18 defs.** Slug rule (Q7): slugified form name; on collision, suffix
`-<first 8 of source id>`. The record:

```jsonc
form/<slug> = {
  "title": str,                          // source name
  "fields": [ { "key": str,              // slugified label, stable per form
                "label": str, "required": bool,
                "type": <mapped type>,   // table below
                "stype": <source type verbatim>,
                "config": {…source config…} } ],
  "blocks": [ …same item shape… ],       // source blocks carried alongside fields
  "public_url": null,                    // until the form is republished on Fang
  "published": bool,
  "folder": str|null,                    // folder name, not a family (1 folder exists)
  "staxcloud": { "id": uuid, "schema_version": num, "template_type": str,
                 "import_hash": "…" }
}
```

**Field-type mapping** (faithful where Fang renders the kind today;
Round E owns the final kind catalog — a kind ships only when Build *and*
the public form render it):

| Source type | Fang `type` | Class |
|---|---|---|
| field-name | text | faithful |
| field-short-text | text | faithful |
| field-long-text | textarea | faithful |
| field-email | email | faithful |
| field-phone | phone | faithful |
| field-heading / field-paragraph | text (label-only block) | approximate |
| field-dropdown / field-choice / field-image-choice | text + `stype` preserved | **deferred kind** — options ride in `config` |
| artist-select | text + `stype` preserved | deferred (options = the two artists) |
| field-file / studio-ref-images | text + `stype` preserved | deferred (uploads) |
| consent-* (11 kinds) / field-consent | text + `stype` preserved | deferred (consent rendering is Round E scope) |
| consent-signature / consent-initials | text + `stype` preserved | deferred (signature) |
| booking-form / booking-widget / customer-service | text + `stype` preserved | deferred (connected blocks) |

Nothing is lost by a deferred mapping: `stype` + `config` preserve the full
source definition, and Round E can upgrade `type` in place when a kind ships.

### 4.3 Form submissions → `formsub/<slug>/<source-uuid>`
**242 submissions.** Record:

```jsonc
formsub/<slug>/<uuid> = {
  "form": <slug>, "uuid": <source submission id>, "ts": <submitted>,
  "source": "staxcloud-import",
  "data": { …source data answers, verbatim… },
  "processed": true,                     // historical: no draft is minted
  "contact": <contact key>|null,        // resolved by client_id across both scopes
  "staxcloud": { "id": uuid, "form_id": uuid, "evidence_state": "ready"|"legacy",
                 "evidence_sha256": "…", "files": [ {attachment metadata} ],
                 "import_hash": "…" }
}
```

- **Orphan forms (121 A-scope rows, 8 dead form ids):** the translator first
  writes a **stub def** for each orphan form id — `published: false`,
  `title` from `form_name_snapshot`, `fields` from the **newest**
  submission's `form_fields_snapshot` for that form id — then files the
  submissions under it. The archive stays browsable and honest (the def is
  marked as reconstructed in `staxcloud`).
- **Linkage:** `client_id` resolves against the union of both scopes'
  clients. Unresolvable submissions (≤33 by the record-view delta) land
  with `contact: null` and are counted in the import report.
- `processed: true` is load-bearing: the Forms sweep must not mint drafts
  for 242 historical submissions (§10 has the companion requirement — the
  sweep's birth pass treats `source = staxcloud-import` as already-triaged).
- The submission `data` includes consent answers (medical disclosures,
  dates of birth, signature representations) — the same sensitivity class
  the data already has in StaxCloud; it lands in the shop's own store on
  the shop's own box. No new exposure is created; `ip` is the one field
  deliberately dropped (§8).

### 4.4 Projects → proposed `project/<contact-key>/<source-id>` (Q1)
**64 projects** (57 active). No established Fang family fits: boards are
dashboards, contact `notes[]` would bury the shop's live work list, and
Canvas's `designrec/` is for generated designs. Proposal — a dedicated
family, record carried whole:

```jsonc
project/<contact-key>/<source-project-id> = {
  "title": str (source name), "description": str, "status": str (verbatim:
  active|in_progress|completed|archived), "total_price": num,
  "artist": slug, "contact": <contact key>,
  "created_at": ts, "updated_at": ts,
  "staxcloud": { "id": uuid, "import_hash": "…" }
}
```

Projects are also the strongest **Booked-stage evidence** for the Leads
pipeline (§10). If the director rejects a new family, the fallback is a
`projects[]` summary array on the contact record — named here so the
rejection has a landing spot.

### 4.5 Appointments → history fold-in (Q2)
**22 appointments, all past.** No Fang appointments primitive exists and
none is proposed (Square owns booking). Proposal: each client-linked
appointment (18) appends one entry to its contact's `notes[]`:
`{ts: <date>, text: "Appointment <date> — <service> · <status> (StaxCloud
history)"}`. The 4 unlinked appointments are counted in the import report
and not imported (no honest home). Deposit fields are dropped (all unpaid;
Square owns money truth). If the director prefers, the whole family can be
deferred to a phase 2 without blocking anything else — it is history, not
working state.

### 4.6 Records docs → proposed `note/<source-id>` (Q3)
**21 docs.** Proposal — a faithful 1:1 family:

```jsonc
note/<source-doc-id> = {
  "title": str, "mode": "note"|"session"|"consultation",
  "content": [ {"type":…, "text":…} ],   // source blocks verbatim
  "artist": slug, "contact": <contact key>|null,
  "folder": str|null,
  "created_at": ts, "updated_at": ts,
  "staxcloud": { "id": uuid, "import_hash": "…" }
}
```

Client-linked docs (7) resolve `contact` through the same union lookup.
Studio-level docs (14) land with `contact: null`. Whether a surface reads
`note/` later is a UX-round question; the data home comes first.

### 4.7 Artist profiles → enrich `artist/shawn` + `artist/leni`
The two profiles merge **additively** into the existing artist records —
Designer fields (`allow_customer_designs`, `versions_per_request`,
`approved_library`, …) are never overwritten. Added from the profile:
`bio, tagline, experience, years_experience, pronouns, location,
instagram_url, website_url, booking_notes, cover_up_capable, cta_label`,
and profile `specialties`/`style_tags` merge into the existing
`specialties`/`styles` lists (union, deduped). Staff→slug resolution in §5.

### 4.8 SMS — explicitly NOT part of the one-shot import
The Dell bridge already mirrors StaxCloud's threads into `sms/` live
(2 threads, 87 messages) and owns delivery read-back for `smsout/`. The
import must not touch `sms/`, `smsout/`, or `attention/sms`. SMS cutover
(the bridge's retirement in favor of the fork's own modem path) is a
separate, later decision — when it happens, the thread history is already
in Fang by construction.

### 4.9 Everything else
- **Studio assets → proposed `asset/<source-id>`** metadata records
  `{title, artist, purpose, status, rights_state, style_state,
  collections: [names], revision: {sha256, byte_size, mime, width, height},
  staxcloud: {id, bytes_route, import_hash}}`; the 1 collection carries as
  names on the assets. A `surface/library` board can be composed by the
  surface-builder agent **after** import (agent work, not translator work).
  **Bytes are phase 2 (Q6)** — the metadata + sha256 land now; the binary
  fetch (`/api/studio/assets/{id}/bytes`) is a separate, countable pass.
- **Site pages (2 drafts):** do not translate. Fang has surfaces, not a
  website builder; both pages are unpublished drafts. Named, not waved (Q9
  can revisit if the owner wants the site on the fork).
- **Form/doc folders (1 + 1):** carried as name strings on their records
  (§4.2, §4.6), not as families.
- **Teams (1), widgets (1), services (0), CS conversations (0),
  flashbooks (0):** nothing to move.

---

## 5. Artist attribution mapping

- Every source business record is attributable: clients/docs/projects carry
  `artist_id`; submissions carry it via scope + the ready set's
  `evidence.artist_assignment.selected_artist_id`; appointments carry only
  `staff_name` (single-artist family, folds into that artist's contacts).
- **Join rule:** the translator holds a two-row map `{staff_id → slug}`.
  It is built at build time by matching each scope's `/api/staxbox/profile`
  `artist_id` against the `artist_id` fields already inside Fang's
  `artist/shawn` / `artist/leni` records; if those don't resolve it, the
  map is a two-line owner-confirmed config in the translator's env — never
  guessed from names in code.
- **The honest headline for the owner:** the two books are real but unequal
  — Artist A's book is the shop's history (143 clients, all 22 appointments,
  all 7 assets), Artist B's is newer and form-born (23 clients since
  2026-09-08, 26 submissions, 1 project). Only 3 people appear in both.
  The Leads pipeline's artist filter (§10) will therefore be lopsided at
  first — that is the data telling the truth, not an import defect.

---

## 6. Ordering constraints

1. **Round C cleanup lands first.** Verdict 4 Round C deletes Fang's test
  contacts (4), held test drafts, and the zombie test thread. The import
  must land **after** those deletions: imported records dedupe against what
  survives, and no real record may merge into a test record's key. (The
  live Forms pipeline keeps minting real contacts in the meantime — the
  import dedupes against them by the same index, §3.)
2. **Within the import:** artist profiles → form defs (incl. orphan stubs)
  → contacts → submissions (linkage resolves against imported contacts) →
  projects / notes / assets → manifest. Contacts precede submissions so
  `formsub.*.contact` pointers resolve in one pass.
3. **Leads pipeline:** the import lands **before** the Leads pipeline's
  birth/movement rules run over real data — ideally as Round C's second
  half, so the pipeline's acceptance test is the real 163-contact book,
  not the 4 test records it was designed against (§10).
4. **The bridge keeps running throughout.** SMS is a standing sync (§4.8);
  the import neither pauses nor duplicates it. Fang's own Forms pull-sync
  also keeps running — the import window is not a freeze.
5. **StaxCloud stays authoritative until parity is proven** (standing
  production rule). The import is a copy; nothing on the Dell is written,
  and the final cutover re-run (§9) is a separate, owner-visible step.

---

## 7. What does NOT translate (named, with reasons)

| Thing | Why not |
|---|---|
| Submission **evidence bundles** (answers/form_document/raw_values/receipts/provenance internals) | StaxCloud's legal-evidence machinery; Fang's formsub shape has no home for it and the fork's forms design doesn't replicate the evidence model. The `evidence_sha256` + `evidence_state` carry over, so existence stays provable against StaxCloud, which remains the evidence archive until its retirement is separately decided. (Q8) |
| Submission **`ip`** (on all 242 rows) | Submitter network metadata; no Fang consumer; dropping it is a privacy improvement, done deliberately. |
| Attachment **binaries** (A scope: 6 file-bearing + 22 attachment-bearing submissions; 7 studio asset binaries) | Metadata + sha256 translate now; bytes are a phase-2 fetch with its own count proof (Q6). Routes named in §1.3/§1.7. |
| Square linkage fields | Verified **unset on all 166 clients** — nothing exists to translate. Square stays its own system of record. |
| `total_spend`, `points` | Zero on every row — empty rollups, not data. (`visits` is real and carries.) |
| Appointment deposit/money fields | All unpaid; Square owns money truth; the family imports as history only (§4.5). |
| Knowledge-graph rows (`entities`/`relations`; contact `entity_id`) | Fang's graph mints its own entities (the fake-entity precedent: surfaces project kv, never the graph). Imported contacts arrive without `entity_id`. |
| StaxCloud agent-side families (`logic_cards`, `memory_entries`, `agent_facts`, `claw_*`) | The old system's agent working state; also unreachable without root (§1.10). The fork's crew builds its own memory. |
| Site pages (2 drafts) | No website-builder primitive on the fork; unpublished drafts (§4.9). |
| Form recipes / block defaults (13) | System design vocabulary, not customer data. (Round E should *read* them when finalizing the field-kind mapping in §4.2 — reference, not migration.) |
| Availability config, services list | Services list is empty; availability belongs to Square by standing law. |
| `person_id` as a key | Semantics unproven (24 distinct over 143 A-rows); carried as provenance inside `staxcloud.person_id`, never used as identity. |

---

## 8. Named gaps (what the census could not reach)

1. **Root-locked database families** (§1.10): agent-side tables are
   unreachable via the owner API. Unblocks: an owner-run export or a root
   window. Recommended disposition: excluded by design; `cs_knowledge`
   eyeballed at build time as the single exception.
2. **Scope reliance:** the entire census (and any API-based import) depends
   on the `X-Artist-Id` header mechanism working per scope. It was verified
   live for clients/forms/submissions/docs/appointments/assets/pages/
   threads. Doc-folder and form-folder counts were verified in A scope
   only (1 + 1); the translator enumerates folders per scope at run time
   and reports both.
3. **Linkage delta:** 33 of 242 submissions don't appear in any client
   record view. The translator resolves `client_id` against the raw client
   union (not the record views), so the true unresolvable count may be
   lower — it is whatever the import report counts, and the report is a
   required artifact (§9).
4. **B-scope doc folders / form folders:** not separately censused;
   expected 0–1 each; translator enumerates and reports.

---

## 9. Migration mechanics (proposal)

**Form:** a **one-shot translator script**, re-runnable — *not* a standing
sync. A standing sync would put two writers (StaxCloud and the fork's own
live Forms/Texts pipelines) into `contact/` with merge ambiguity; the one
standing sync that exists (SMS via the bridge) already covers the only
family that changes minute-to-minute. Cutover = freeze StaxCloud writes
(owner action), re-run the translator (hash-skip makes it a delta run),
verify, done.

**Where it runs:** on the **Dell**, beside the bridge. The source API is
localhost-only there, the session pattern is proven, and the box already
holds the Fang write route (bridge/pull-sync lane — browser-UA HTTPS to
fang.sefer.team with the daemon key, read from env at runtime, never
printed). The translator is Python stdlib only, modeled on bridge.py.
It enumerates **both scopes explicitly** (default pass + `X-Artist-Id`
pass per staff id from `/api/staxbox/staff` — the roster is read, never
hardcoded, so a future third artist can't be silently skipped).

**Writes:** Fang kv PUTs only, through the daemon API — the same surface
the crew and sidecars use. **Put-only: the translator never deletes
anything, anywhere.** All keys deterministic (§3.5); every record carries
`import_hash` (§3.6).

**Manifest & report:** the run ends by writing `migration/staxcloud-<date>`
in Fang kv — per-family counts written, skipped-by-hash counts, unresolved
linkage counts, the unkeyed-holding count — and printing the same report
locally. The report is a required artifact of the run, filed with the
round's evidence.

**Failure behavior:** a failed family stops that family, not the run;
re-running resumes by hash-skip. A scope pass that returns zero rows for a
family known non-empty aborts the run before any write in that scope
(the §0 lesson, enforced in code).

---

## 10. Verification proposal (receiving-end, per the standing rule)

1. **Count read-back per family** from the Fang API (not the translator's
   own log): `contact/` ≈ 163 + 1 holding record; `form/` = 1 existing +
   18 imported + orphan stubs (8); `formsub/` grows by 242;
   `project/` 64; `note/` 21; `asset/` 7 — each compared against §1
   numbers, differences explained in the run report.
2. **Hash totals:** sum of `import_hash` coverage per family = source
   count per family; a second translator run reports 0 writes
   (idempotency proof).
3. **Shape spot-checks without PII:** for a sample of imported records,
   print field-name sets + value *types* only (the census method) and
   diff against §4 shapes.
4. **Dedupe proof:** pick the known collision cases by count — the 3
   cross-scope people exist exactly once each in `contact/` with
   `artists` of length 2; the phone-collision pair matches the report's
   disposition.
5. **Pipeline proofs on real data:** the Forms sweep completes over the
   imported submissions minting **zero** drafts; the Texts sweep and
   Morning Brief still complete; the non-regression checklist (crew 7
   Running, 19 jobs, approvals round-trip) passes; a brief generated after
   import reads the real book (counts of new submissions/projects) without
   inventing records.
6. **Leads surface proof:** the Round C pipeline renders the imported book
   — counts strip totals equal the kv census, the artist filter splits
   match §5's per-artist counts, and no card shows a raw id or test record.

---

## 11. Impact on the Leads pipeline design (Verdict 4 Round C) — read before building Round C

Round C was designed against **4 test contacts**. The import changes its
ground truth in five specific ways:

1. **Birth must be retroactive.** The pipeline's birth rule (form
   submissions + `attention/sms`) describes live arrivals. 152 of the 166
   source rows are form-born *historically*; imported contacts arrive with
   `source` + `source_form` already set and their submissions already
   filed as `processed`. The pipeline must treat the imported book as
   already-born — its first run over real data is a *classification* pass,
   not a birth pass. (§4.3's `processed: true` + `source:
   "staxcloud-import"` markers exist precisely so this is mechanical.)
2. **`lead_status` has no home in the verdict's vocabulary.** The source
   carries `cold` (165) / `hot` (1); the verdict's temperatures are
   Ready / Interested / Just looking. A mapping must be ruled **before**
   import, or 163 contacts land carrying an unmapped field (Q4).
3. **Stage derivation gets real evidence — use it.** The imported data can
   seed stages honestly: has submissions → at least Talking; has an
   **active project** (57 people) → Booked/work-underway; no interaction
   since long before import → Resting. Designing derivation against the
   test set would have missed the project signal entirely — projects are
   the strongest stage evidence the shop has (Q4).
4. **The artist filter will look broken unless §5 is understood.** All ·
   Shawn · Leni against a 143/23 split (with 3 people in both) is the
   truth of the current book. The counts strip must show per-artist counts
   so an empty-looking side reads as "newer book," not as missing data.
5. **Card density changes.** 102 of the imported contacts carry notes;
   183+ submission summaries hang off the A book alone. The verdict's
   lead-card spec (name, piece idea, last contact, waiting-on, next
   action) needs its "piece idea" source defined for imported records:
   the newest formsub's `data` (placement/idea fields where the form
   collected them) or the active project's title — a derivation rule
   Round C must state, because imported records have no single "idea"
   field.

---

## 12. Open questions for the director

1. **Projects: new `project/` family (§4.4) or `projects[]` on the
   contact?** *Recommendation: the family.* 57 active projects are the
   shop's live work list; they need their own surface-able home, and the
   contact record stays a contact record.
2. **Appointments: fold into contact `notes[]` (§4.5), defer the family,
   or skip it?** *Recommendation: fold.* It's 18 honest history entries in
   the place history is actually read; the family blocks nothing either
   way.
3. **Docs: dedicated `note/` family (§4.6) or wait for a Records surface
   design?** *Recommendation: `note/` now.* Data homes precede surfaces;
   the shape is a faithful 1:1 carry.
4. **Lead vocabulary mapping (blocks §10):** rule the `lead_status` →
   temperature map and the stage-derivation table before import.
   *Recommendation:* `hot` → Interested, `cold` → Just looking (Ready is
   earned by live behavior on the fork, not inherited); stages derived —
   active project → Booked, has submissions → Talking, imported-only with
   no submission → New, no interaction in 90+ days → Resting.
5. **Cross-scope contacts: `artist` + `artists[]` (§4.1) — accept the
   plural field?** *Recommendation: yes.* Three real people are both
   artists' clients; a single-artist field would falsify them.
6. **Attachment & asset binaries: phase 2 or never?** *Recommendation:
   phase 2, as its own counted pass* (A scope alone: 28 attachment-bearing
   submissions; plus 7 asset
   binaries), after the metadata import proves out. The sha256s land now,
   so phase 2 can verify every byte it fetches.
7. **Form slug derivation (§4.2): name-slug (human, mutable) or
   id-derived (stable, opaque)?** *Recommendation: name-slug with
   source-id suffix on collision* — Fang's surfaces are owner-facing and
   slugs appear in URLs the owner sees; the source id rides inside the
   record for stability.
8. **Evidence bundles: sha-only carry (§7) — accept?**
   *Recommendation: yes*, with StaxCloud remaining the evidence archive
   until a separate retirement decision. If the director wants the full
   bundles preserved inside Fang, that's a storage-shape decision (an
   `evidence/` family) — costed by the ready set's 48 bundles only; the
   194 legacy bundles are thinner. Either way it should be ruled, not
   defaulted.
9. **Root-locked families (§1.10) + site pages (§4.9): accept the named
   exclusions, or commission an owner-run export for a completeness
   pass?** *Recommendation: accept*, with `cs_knowledge` eyeballed at
   build time as the sole exception.
10. **Sequencing: does the import slot as Round C's second half**
    (cleanup → pipeline build → import → gate on real data), **or as its
    own round after Round C gates on test data?** *Recommendation: Round
    C's second half.* Gating Leads on 4 test records and then discovering
    the real book's shape afterward is how the §10 surprises happen;
    importing first makes the gate honest. This also fixes the import's
    position relative to Rounds D–F: before all of them.

---

*End of map. Census scripts were run read-only from the Dell and Sarah's
box on 2026-11-02; all counts above are from those runs. No record on
either system was created, modified, or deleted.*
