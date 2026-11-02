---
name: forms-skill
version: "1.0.0"
description: Forms ownership — definitions and submissions in shared memory, contact resolution in the knowledge graph, reply drafts held as approvals
runtime: prompt_only
---

# Forms Skill

The Forms agent keeps form definitions at `form/<slug>` and submissions at `formsub/<slug>/<uuid>` in shared memory. On each sweep it processes unprocessed submissions: resolve-or-create the contact in the knowledge graph (match on email/phone), hold a reply draft as an approval request (never send), and mark the submission processed with the contact name. Dedupe is structural — the submission uuid is part of its record key.
