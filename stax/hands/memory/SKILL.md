---
name: memory-skill
version: "1.0.0"
description: Durable customer facts proposed from real conversations — candidates carrying verbatim quotes, carried to Needs you by the sidecar, promoted into the contact's notes only on the owner's approval; rejection deletes the candidate
runtime: prompt_only
---

# Memory Skill

The Memory agent is woken by the deterministic enumeration pass with the exact keys of conversation records that changed (`sms/<digits>` threads, processed `formsub/<slug>/<uuid>` submissions) — it never goes looking on its own. From each named record it extracts durable customer facts in five classes (piece, placement, preference, life, artist_fit) and stores each as a candidate at `memcand/<first 16 of sha256(source_key + quote)>`, carrying the verbatim quote it was extracted from; a fact it cannot quote does not exist. The sidecar carrier takes candidates to Needs you. Approval wakes the hand to append exactly one `{"ts", "text"}` entry to the contact's `notes[]` — an artist_fit candidate promotes as a note, never as an assignment — and rejection deletes the candidate sidecar-side, since no hand holds a delete. A verification pass greps every candidate's quote against its source record: a quote that does not match verbatim is a fabrication and fails the run.
