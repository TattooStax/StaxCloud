# StaxCloud Deterministic Anticipation Engine (DAE) — implementation RFC v0.1
Status: isolated proposal; no runtime behavior changed.
Branch: feature/deterministic-anticipation-engine
Scope: StaxCloud V4 / Rust Axum SQLite; reusable core crate later.

## Goal
Interpret incoming prompts/events, shortlist and stage relevant tools, and execute only approved, validated deterministic workflows. LLM is fallback for ambiguous tasks. Never bypass existing tool registry, auth, or approvals.

## Request lifecycle
1. Capture user request and verified runtime context (tenant, permissions, available tools, tool health, state version).
2. Normalize task using exact intent patterns + typed slots; ambiguity -> LLM; no guessed arguments.
3. Retrieve tool candidates from registry by capability tags and input/output contracts; use lexical scoring first, optional compact embeddings later.
4. Construct dependency DAG: tool preconditions, required inputs, effects, read/write classification, expected outputs, compensation.
5. Produce bounded proposal: ranked tool bundle, predicted next steps, confidence evidence, missing fields, required approvals.
6. Execute deterministic read-only steps when authorized; queue writes for approval under existing policy; validate every result.
7. Persist state transitions, receipts, outcome labels, errors, latency, tool health, consent provenance.
8. Update candidate rankings only from verified outcomes; simulation data kept separate and lower trust.

## Initial modules (proposed, adapt after source audit)
- crates/stax-anticipation/src/{lib,intent,registry,rank,planner,policy,executor,memory,telemetry}.rs
- migrations/anticipation_001.sql (idempotent, versioned)
- tests/anticipation/{routing,policy,recovery,replay,adversarial}.rs
- feature flag: anticipation.enabled=false; shadow mode first.

## Data contracts
Intent {kind, slots, source, evidence, uncertainty}
Capability {tool_id, schema_version, tags, requires, produces, effect, auth_scope}
Plan {request_id, state_version, steps, dependencies, confidence, approval_requirements}
Trace {request_id, tool_id, arguments_hash, state_before, state_after, outcome, elapsed_ms, provenance}
Store no raw sensitive prompts by default; redact PII and secrets; tenant-scoped retention.

## Hard invariants
- Tool selection never grants permission.
- Read-only prefetch only for explicit request-relevant authorized data; no background sensitive retrieval.
- No irreversible writes without existing approval requirements.
- No learned rule can mutate policy or executable code automatically.
- Idempotency keys for writes; replay protection; crash-safe checkpoints; bounded retries.
- If state/tool health changes, revalidate before dispatch.
- On low confidence or missing required slot, ask or escalate to LLM; no fabricated results.
- Simulation outcomes cannot be treated as ground truth.

## Milestones
S0 Audit current agent loop, tool registry, persistence, permission and tests; capture baseline.
S1 Instrument traces and add feature-flagged shadow router.
S2 Typed tool registry adapter and deterministic intent extraction.
S3 Dependency planner, read-only prefetch, tool-bundle prompt injection.
S4 Approval-safe execution, resume, idempotency, recovery.
S5 Outcome memory, calibrated ranking, tool health and drift.
S6 Synthetic user simulation plus real trace evaluation, release gate.

## Initial test scenarios
- Find client appointment: retrieve contact + calendar, no writes.
- Reschedule appointment: check availability, hold draft, require approval.
- Send message: resolve recipient, create held draft, no unauthorized send.
- Missing recipient: clarify, no dispatch.
- Tool timeout: bounded retry, no duplicate side effects.
- Prompt injection in tool result: never expand permissions.
- Two simultaneous turns: state version conflict detected.
- Wrong tenant / revoked permission: deny even when ranked top.
- Offline/no model: execute supported typed workflows, explain unsupported intent.

## Release gates (targets, not measured)
- 100% unauthorized-write prevention in adversarial test suite.
- >=95% top-3 relevant tool recall on held-out labeled workflows.
- >=90% deterministic workflow completion on supported cases.
- Zero duplicate external side effects in replay tests.
- Compare against baseline on latency, token use, success and false-positive anticipation.
- Record p50/p95 RAM and latency on Dell OptiPlex 5050 Micro.

## Research pointers
Cloudflare Agents Harnesses (2026); LangGraph durable state orchestration; SHIFT Dynamic Harness Search (2026); Agent Harness Awareness (2026); JevAgentHarness decision models (2026).
Do not adopt model-reported metrics without local reproduction.

## Integration rule
Separate worktree/clone from other StaxCloud strikes. Rebase on latest main only after tests; PR review before merge. No direct edits to main.
