# StaxCloud

This fork (branch `stax-ux`, pinned from upstream v0.6.9, tag `stax-base-0.6.9`)
reskins OpenFang's UX into StaxCloud — a proactive business system for
service-shop owners — while keeping every upstream function. UX-only scope:
everything lives in `crates/openfang-api/static/**` plus pure `include_str!`
additions in `crates/openfang-api/src/webchat.rs`. No backend changes.

## What changed

- **Shell**: StaxCloud design tokens (teal `#146e68`, DM Sans, canvas
  `#f4f2ec`/`#0c0c0e`), five-tab bottom dock — Home · Channels · Work ·
  Studio · System — with per-surface chips and per-module docks.
- **Home**: a morning brief projected from real records (Needs-you approvals,
  helpers, scheduled jobs, audit activity) — never model-minted items.
- **Needs-you**: plain-language approval cards in Work and inline in Channels,
  fed by the real approvals API.
- **Side panel**: slide-over with side chats (real sessions on their own
  socket) and cards (Needs-you, this chat, coming up).
- **Boards** (Studio): agent-spun surfaces rendered from kv-stored
  definitions (`surface/<slug>`) — heading/text/stats/list/kvlist blocks.
- **Forms** (Studio module: Agent · My Forms · Submissions · Preview):
  form definitions + submissions in kv; a public Cloudflare Worker intake
  (durable KV) + a pull-sync sidecar so submissions made while the device
  sleeps land on wake, deduped; the Forms hand resolves contacts and holds
  reply drafts for approval.
- **Contacts** (Work): the kv contact index as a searchable list with
  detail, joined submissions, and notes. Repeat submissions update the same
  contact (visits/last_seen) instead of duplicating.
- **Texts** (Channels module: Agent · Inbox · Contacts): kv-mirrored SMS
  threads; replies are held as drafts, carried to Needs-you, and only reach
  the outbox (`smsout/<uuid>`, status queued) after approval. The modem
  bridge to the shop's StaxCloud line is a separate Dell-side script.
- **Set up** (Home): first-run as a 3-question conversation; writes
  `setup/profile`, activates the hands matching the stated needs, and posts
  a "Your crew" board.
- **One Face**: the owner sees a fitted crew — Stax (the lead), Forms,
  Texts, Surface Builder, Deep Work — with human role labels; the full
  roster stays behind a "Show all helpers" toggle. Chat lands on Stax.

## The crew (in `stax/hands/`)

Hands are installed durably by copying a folder into `~/.openfang/hands/`:

- `stax` — the lead. Router playbook over `agent_list`/`agent_send`:
  answers from records or routes to the owning specialist; escalates hard
  jobs to deep-work.
- `deep-work` — escalation tier: `provider = "openrouter"`,
  `model = "moonshotai/kimi-k2-0905"` (the Kimi line), web-equipped.
- `forms` — form intake sweep: contact resolve-or-create via the kv contact
  index, held reply drafts. Grounding law: process only what you recalled;
  a missing record is a stop-and-report, never an invention.
- `sms` — text-thread sweep with the same discipline; personal threads are
  hands-off.
- `surface-builder` — composes boards from plain-language asks.

## Sidecar

`stax/pull-sync.sh` runs beside the daemon: pulls public form submissions
from the Cloudflare intake into kv (ack only after a local 200), and carries
held drafts (`draft/<uuid>`) into Needs-you as approvals — re-carrying on
expiry (Fang approvals are a live-action gate with a policy TTL, max 300s),
closing them on decision, and moving approved text replies to the outbox.

Live instance: https://fang.sefer.team (password-only login).
