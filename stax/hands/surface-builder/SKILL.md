---
name: surface-builder-skill
version: "1.0.0"
description: "How to compose, update, and remove Studio boards (surfaces) stored as kv records — block schema, slugs, and honesty rules"
runtime: prompt_only
---

# Surface Builder — skill notes

Surfaces are kv records under `surface/<slug>` rendered by Studio → Boards.

## Compose
1. Pick a slug from the request (short, lowercase, dashes).
2. `memory_recall` the key — if a board already exists there, edit it instead of overwriting blindly.
3. Compose blocks (schema in the system prompt) under the glance law: stats are numbers or short states, badges only Waiting / Doing / Done / Needs you, kvlist only over records that carry a title/name/status, and a closing "Next actions" list.
4. `memory_store` the full JSON value, with `updated` set to now.
5. Confirm to the owner: title + "Studio → Boards".

## Update
Recall → edit the JSON in place → store the whole value back. Never store partial blocks.

## Remove
Store `{"deleted": true}` at the key. The Boards page hides tombstones. Board removal happens by asking Stax — Boards has no delete control.

## Honesty
Boards are maintained workspaces, not reports. Unknown metrics read "Not measured". Statuses (Waiting/Doing/Done/Needs you) must reflect what the owner or a real check established — never optimism. A stat or line the records cannot support is left out.
