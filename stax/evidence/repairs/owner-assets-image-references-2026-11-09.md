# Owner work and image-reference repair

Scope: the OpenFang fork requested as `TattooStax/openfang` (GitHub redirects that repository to `TattooStax/StaxCloud`, repository ID 1442119094). Base: `968656217521b4cc68b5e5dd47aa5773de9d5ac9`, `strike-6-clean-surfaces`. No Dell or StaxCloud-V4 access or changes.

## Production inspected first

Authenticated reads from `https://fang.sefer.team` on November 9, 2026 CST:

| Seat/configuration | Observed setting | State |
| --- | --- | --- |
| Stax | `google/gemma-4-26b-a4b-it`, OpenRouter | Active |
| Memory | `google/gemma-4-26b-a4b-it`, OpenRouter | Active |
| Designer hand | `google/gemma-4-31b-it`, OpenRouter | Active |
| Deep work | `google/gemini-3.1-flash-lite`, OpenRouter | Installed, inactive |
| Style | `meta-llama/llama-3.3-70b-instruct`, OpenRouter | Installed, inactive |
| Global default, Forms, SMS | `meta-llama/llama-3.3-70b-instruct` | Active/default |
| Router; image/vision tool environment pins | Not exposed by the authenticated config API | Unverified; not changed |

The Stax agent's installed system prompt already included `WHO YOU ARE TALKING TO`, Shawn Lowe/Fargo Tattoo ownership, and permission to copy/migrate his assets. Those paragraphs and the Gemma seat pin were preserved. The swap was partially installed, not uniformly complete. `/api/version` reports 0.6.9 but `git_sha: unknown`; the production commit attribution comes from the owner's reported checkpoint, not an independently exposed binary SHA.

## Root causes

1. **Driver refusal was accepted as a valid final answer.** The hand's broad crew description named inactive helpers; the composed generic safety section offered no distinction between authorized owner preparation and an external customer effect. The lead also lacked the shipped Websites record/job workflow. Neither the web-fetch guards nor capability/approval guards contains the reported policy-style website-clone refusal. The exact refusal is reproducible with a scripted driver and was returned verbatim before this patch. Existing safety checks remain in place.
2. **Attachments were hints to the driver, not enforced tool inputs.** HTTP and WebSocket attachments resolve to image blocks plus `[Attached image: file_id ...]` text. Generation depended entirely on the driver copying that marker into `references` on every retry. Missing files were silently removed by attachment resolution. `stax_image_generate` ignored non-array references and non-string entries. Its provider helper silently truncated more than six references, while the tool could report every requested ID. The OpenAI generation-only branch ignored references altogether.
3. **Tool success and visible success were different facts.** A successful generation with `references_used: []` was treated as sufficient grounding for whatever the driver said next. Error guidance was prompt-only; neither final text nor streamed deltas enforced the image receipt. The outer generic tool timeout was 120 seconds while image requests legitimately allow 300 seconds per route, causing premature cancellation before images/chat fallback could finish.
4. **Style interpretation was treated as fact.** Vision returned a free-form category, and the lead offered an installed Style hand as if it were a running agent. No transport can prove a model's visual interpretation or output fidelity merely because a reference was submitted.

## Changes

- A shared turn contract binds current attachments (and explicitly referred-to prior attachments) into every image-generation call before hook checks, guard hashing, persisted ToolUse blocks, and execution. The original owner request is included with its palette/style/composition constraints. Malformed reference arguments remain errors.
- Missing image uploads retain their identity, so a failed reference produces an honest tool failure instead of text-to-image generation. All requested reference entries are validated. Excess references fail; unsupported OpenAI editing fails before generation.
- Both OpenRouter routes serialize the same reference bytes and require supported parameters. Neither fallback removes references. The receipt reports requested customer IDs, byte counts, SHA-256 hashes, accepted route/model and submitted-reference count. Submission is explicitly distinct from visual fidelity. The existing six-reference limit also covers added portfolio exemplars.
- Untruncated image receipts control the final image reply, including streaming. Raw prose and thinking deltas are held for image-capable/protected turns; tool and phase events remain live. Failed, missing or mismatched receipts cannot be narrated as a successful redo. Images are shown for review without asserting likeness or style verification. Errors and prior failed attempts remain visible.
- Known owner-asset refusals get one bounded replan using the existing permissions. A repeated refusal becomes a concrete source-input request. Actual tool denials/errors are retained and are never retried or bypassed by this recovery. Third-party requests do not enter owner recovery.
- The Stax hand explicitly opts into owner-facing behavior, explains Websites drafts and publisher read-back, and can inspect/activate an installed helper before verified delegation. The source hand's provider/model fields are not repinned. The install helper merges into the installed hand and verifies all existing agent settings except prompt/owner-facing opt-in remain identical.
- Vision instructions ask for observable palette/linework/shading, allow uncertainty, and treat category labels as interpretations. Owner corrections win. This is not a claim that vision classification has become infallible.

OpenRouter request shape checked against the primary [image API tutorial](https://openrouter.ai/blog/tutorials/image-generation/) and [image model catalog](https://openrouter.ai/collections/image-models/). Local HTTP tests verify serialized request bodies independently of provider behavior.

## Validation and deployment

Before implementation, three runtime regressions failed with the expected bugs: verbatim owner refusal, malformed references reaching provider configuration, and OpenAI references being discarded. A separate API regression failed because an unavailable upload lost its identity.

Targeted coverage includes both agent loops, streamed-refusal suppression, attached-file binding despite omitted tool arguments, false success after tool failure, the exact `/images` payload, identical fallback reference bytes, provider rejection without unreferenced retry, excess references, receipt integrity, and preserved approval denials. The installed-hand merge has offline idempotence/pin/context-preservation tests.

The live Stax system prompt was hot-patched through its supported configuration API. Fresh read-back verified that the pre-existing owner-context text remains and the model is still Gemma 4 26B. Its tools and every other seat were unchanged. A before/after record is kept on the build host under `fork-backups/owner-image-repair-20261109/`.

The binary/runtime changes require installation on the fork host and are **not yet live**. The established fork SSH host is `staxbox@192.168.40.27`; the available identities were rejected (`Permission denied (publickey)`). No alternative shell capability was enabled to get around this. Do not label the runtime repair deployed without receiving-end verification.

For the authorized operator with fork-host access:

1. Back up the current fork binary and installed Stax hand; keep the current environment and pins.
2. Install the tested release binary using the fork's normal service owner, with rollback retained.
3. Run `python3 stax/repair-owner-image-hand.py --hand /home/staxbox/.openfang/hands/stax/HAND.toml`. This merges into the current installed hand; do not copy stale model defaults over it.
4. Restart the fork daemon through its existing service, reactivate Stax if needed, and verify the same model pins and owner text.
5. In an isolated test conversation, request an owner-site draft and a reference edit. Inspect the receipt's file ID/hash and actual returned image. Confirm missing references fail visibly and never generate without the supplied reference. Keep customer-facing publishing/design sends behind existing approvals.

This patch does not migrate Fargo Tattoo's website or publish customer material; it repairs the product behavior used to do that authorized work.
