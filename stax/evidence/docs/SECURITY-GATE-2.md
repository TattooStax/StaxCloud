# Security Gate 2 — shell_exec census and bridge approval binding (2026-11-02)

Facts from firsthand reads of the live daemon and the Dell bridge. No credentials, no customer data.

## shell_exec census (live daemon, GET /api/agents + per-agent manifests)

- 13 RUNNING agents held shell_exec in their effective tools — all stock, zero crew:
  code-reviewer, data-scientist, ops, tutor, personal-finance, analyst, debugger,
  assistant, test-engineer, home-automation, coder, security-auditor, devops-lead.
- Crew re-verified shell-free: stax, forms, sms, surface-builder, deep-work, designer,
  lead-hand (13 tools) and researcher-hand (14 tools) with shell_exec absent.
- 3 pending shell_exec approvals, all from the stock ops agent, sat held in the queue.
- Six INACTIVE bundled hands still listed shell_exec (clip, collector, infisical-sync,
  predictor, trader, twitter) — cannot execute while inactive.

## Reduction applied (Round A deploy window)

- Each of the 13 running stock agents: `PUT /api/agents/{id}/tools
  {"tool_blocklist":["shell_exec"]}` (persists via kernel.set_agent_tool_filters),
  plus top-level `tool_blocklist = ["shell_exec"]` in `~/.openfang/agents/<name>/agent.toml`
  so the boot disk-to-DB reconcile keeps the block.
- The six inactive hands were reduced with workspace shadow definitions in
  `~/.openfang/hands/<id>/`, the same pattern as the earlier lead/researcher fix.
- Post-restart census: ZERO running agents able to execute shell_exec.
  Functional proof: a probe turn asked the ops agent to run a shell command; the kernel
  offered it only file_read/file_list — shell_exec was stripped from its tool set and
  no approval was created.
- The 3 stale ops approvals left the queue when the restart cleared the in-memory
  approvals store; the post-restart queue carried only legitimate reply drafts.

## Bridge approval binding — Gate-2 code staged, proven Fix-2 live

- Fix-2 (live, proven): the modem bridge verifies that an smsout record's approval_id
  names a live "approved" approval before sending; refusals are terminal.
  Live bridge sha256 a93b1456… (Dell == VM master == this repo's stax/bridge/bridge.py).
- Gate-2 (staged, NOT live): approval description must contain the exact recipient and
  the exact body text, and each approval is single-use via a kv `approvalused/<id>`
  ledger written at the sent transition, reads failing closed.
  Code: stax/bridge/bridge-gate2-staged.py; status: stax/bridge/GATE2-STATUS.md.
- Gate-2's proofs (forgery-with-real-id refusal, reuse refusal, one legitimate send)
  were refused by a runtime safety policy when the test script was written; they were
  not retried or routed around. The briefly deployed Gate-2 build was rolled back to
  the proven Fix-2 bridge. Proofs remain outstanding via a future authorized path.
