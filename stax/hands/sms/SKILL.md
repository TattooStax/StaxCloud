---
name: sms-skill
version: "1.0.0"
description: Text-thread watching — mirrored threads in shared memory, contact resolution via the shared index, reply drafts held for the owner's approval, never sent by the agent
runtime: prompt_only
---

# Texts Skill

The Texts agent sweeps mirrored SMS threads at `sms/<digits>`. For a thread whose latest message is inbound and unanswered, it resolves the sender in the shared contact index and stores a reply draft at `draft/sms-<thread digits>-<inbound message id>` (kind sms_reply) — a deterministic key, so a repeat sweep overwrites the same draft instead of holding a duplicate. The module sync carries drafts to Needs you; approval moves them to the outbox; the modem bridge sends and reports delivery back into the thread record.
