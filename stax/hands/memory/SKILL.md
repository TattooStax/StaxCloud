---
name: memory-skill
version: "1.0.0"
description: Durable customer facts proposed from real conversations — candidates carrying verbatim quotes, carried to Needs you by the sidecar, added to the contact's notes only on the owner's approval; rejection deletes the candidate
runtime: prompt_only
---

# Memory Skill

The Memory agent is woken by the deterministic enumeration pass with the exact keys of conversation records that changed (`sms/<digits>` threads, processed `formsub/<slug>/<uuid>` submissions) — it never goes looking on its own. From each named record it extracts durable customer facts in five classes (piece, placement, preference, life, artist_fit) and files each with the `memory_propose` tool, which checks the quote is word for word in something the customer (not the studio) said, resolves the contact, and stores the candidate at `memcand/<first 16 of sha256(source_key + quote)>` — the hand never computes keys or writes records itself. The sidecar carrier takes candidates to Needs you. On approval the carrier appends exactly one `{"ts", "text", "from", "quote"}` entry to the contact's `notes[]` in code, leaving every other field as read — an artist_fit candidate becomes a note, never an assignment — and on rejection it deletes the candidate. A verification pass greps every candidate's quote against its source record: a quote that does not match verbatim is a fabrication and fails the run.
