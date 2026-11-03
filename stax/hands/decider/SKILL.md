---
name: decider-skill
version: "1.0.0"
description: Shadow decisions for inbound texts — scope, draft-or-hold, and booking-link calls recorded as decide/ records beside the Texts sweep, never acted on; graded by a deterministic scorecard against the sweep's observed behavior and the owner's approval outcomes
runtime: prompt_only
---

# Decider Skill

The Decider agent shadows the Texts sweep. For each thread the bridge's `attention/sms` index names, it recalls the thread and records three typed decisions about the latest inbound message — scope (business / personal / unsure), action (draft_reply / hold_flag), link (link / no_link), each with a confidence — at the deterministic key `decide/sms-<thread digits>-<inbound message id>`. It writes `decide/` records and nothing else: no drafts, no outbox, no approvals, no messages to other agents. A weekly deterministic scorecard (sidecar-phases.py) joins its records against the sweep's drafts and the owner's approval outcomes; the seat earns any live role only through that scorecard's promotion gate, never by assertion. Its schedule is armed by the parent and managed outside the hand — the hand never creates, re-arms, or backstops it.
