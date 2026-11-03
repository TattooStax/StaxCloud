# BUILD H BRIEF — Home transcript truth (H-1, H-2) + attach restore (U-1)

**Authority:** Director Verdict #5 §6 (~/workspace/openfang-fork/DIRECTOR-REVIEW-FABLE-2026-11-03.md) + KIMI-AUDIT-DISPOSITION.md findings H-1/H-2 + CHAT-BLOCKS-SPEC.md (U-1). **Closed scope: H-1, H-2, U-1 — nothing else.** Sequencing note: Verdict #5 placed Build H after the activation window; the window is HELD (safety-flag hold, 2026-11-03) and the owner directed production not to slow down, so Build H proceeds on staging now under the director rule — the decision is recorded in evidence/activation-completion-2026-11-03.md's chain and in the parent's memory. Build H touches no window artifact (no sidecars, hands, workflows, kv data, or daemon config).

**Base:** TattooStax/openfang branch stax-ux @ d0ff7d5 (contains the deployed Round A tree). Verify the Victus checkout (~/openfang-build/repo) matches that head before starting; if it differs, sync it to d0ff7d5 first and report.

## Hard constraints
- `crates/openfang-api/src/routes.rs` **byte-identical** at the end. Report its sha256 before and after. All work lands in `crates/openfang-api/static/**` and, only if unavoidable, the webchat.rs include block (Round A precedent).
- **Ratchet ledger:** the thread component + renderer must shrink, or any growth is traded with named removals — the optimistic-echo code path is named out in lines in the ledger. No new file unless one retires in the same commit set.
- No sidecar, hand, workflow, cron, kv, or daemon-config changes. If any step seems to need one: STOP, file the case in the report, do not improvise.
- Builders build + stage only. **No deploy, no push.** Deploy and push are parent steps after the parent's own battle test.

## Scope
**H-1 — stored-turn rendering.** The thread renders the STORED turn record, not the client's optimistic echo. An optimistic placeholder may show while a turn is in flight but is REPLACED by the stored record on completion — never kept as the record. Nothing in the render layer may present a local echo as a completed action (no "sent/saved/produced" state without the stored record behind it). A failed or interrupted turn renders in-thread as interrupted, in plain Stax voice, and the stored record agrees with what is shown.

**H-2 — whole-thread rehydration.** On reload, on resume, and on TWA background-return, the thread rehydrates whole and in order from stored turns. Incomplete partials render as incomplete — not as finished turns, not silently dropped. Legacy rows render as stored.

**U-1 — attach restore.** Home's composer regains the attach affordance through the EXISTING turn-scoped uploads path (the stock attach UI already in the bundle + POST /api/agents/{id}/upload + GET /api/uploads/{file_id}); an attached image renders in-thread. Copy/labels must NOT promise durability the route lacks: attachments are turn-scoped, and the UI says so plainly in One Face voice (no "agent/crew/hand" words on the face). No routes.rs change.

## Gate — all on staging, all read-back
1. **Interrupted-send proof:** interrupt a send mid-flight; the thread shows it interrupted AND the stored record agrees.
2. **Rehydration proof:** a 20-turn thread reloaded three ways (full reload, session resume, background-return simulation) matches the stored sequence turn for turn.
3. **Attach proof:** an image attached in staging renders in-thread under Stax's reply, and its bytes match what the uploads route holds.
4. **Non-regression checklist:** document title "StaxCloud"; four-tab dock (Stax · Work · Boards · Leads); brief-first Home composition; drawer composition per Round A; Forms and Texts surfaces intact; module docks intact; sign-in intact.
5. **Builder self-check:** the builder's own browser pass at phone width over staging, with found/fixed lists.

## Lane + deliverables
- Lane: OpenCode on the Victus beside ~/openfang-build/repo, model `openrouter/anthropic/claude-opus-5.5`, key = vault `openrouter-builder-next` released via `staxvault-remote geturl openrouter-builder-next https://openrouter.ai` into `OPENROUTER_API_KEY` env only — never stored, never printed (see BUILDER-HARNESS.md). Staging: a fresh staging instance on the Victus per the established pattern (scratch port, fresh HOME under ~/openfang-build/, env -i, no LLM key needed for render proofs that don't call a model; where a turn must complete, use the daemon-plumbing pattern from Round A staging).
- Fallback (Verdict #5 ruling 14): if the build fails its gate twice for the same cause, stop and report — the parent decides the lane revert. Do not push through a second same-cause failure.
- Deliverables: commits on a local branch in ~/openfang-build/repo (not pushed), and a report at **~/workspace/openfang-fork/evidence/build-h-builder-report.md** containing: per-proof evidence (what was done, what was read back), the size ledger (per file: lines and bytes, with the optimistic-echo path named out), routes.rs before/after sha256 (must be identical), found/fixed lists, self-check captures, and spend (from OpenRouter usage reads — metadata only).
