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
3. Compose blocks (schema in the system prompt). Lead with a heading, keep it scannable.
4. `memory_store` the full JSON value.
5. Confirm to the owner: title + "Studio → Boards".

## Update
Recall → edit the JSON in place → store the whole value back. Never store partial blocks.

## Remove
Store `{"deleted": true}` at the key. The Boards page hides tombstones; the owner's Delete button in Boards removes the record outright.

## Honesty
Boards are maintained workspaces, not reports. Unknown metrics say "not measured yet". Statuses (queued/doing/done) must reflect what the owner or a real check established — never optimism.
