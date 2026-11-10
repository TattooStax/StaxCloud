# StaxCloud (fork) — status, 2026-11-10

Work resumed on the owner's word on 2026-11-09 under a seven-strike plan to
make the product shippable. The rule from the stop notice below still
stands: **"done" means the owner used it at his seat and it worked — not a
test result.** Every strike below is built and tested; none is "done" until
the owner has used it.

| Strike | Branch (each sits on the one before) | What it adds | Owner gate |
|---|---|---|---|
| 1 Foundation | `strike-1-foundation` | Studio export/import, uploads survive a reboot, model pins per role | Passed on live 2026-11-09 (959 records round-tripped) |
| 2 Bench + meter | `strike-2-bench-meter` | Model benchmark, live prices, enforced budget with saver model | Deployed; first scoreboard in, pins not chosen yet |
| 3 Stax works directly | `strike-3-stax-worker` | Sign-in required for customer data, record search tool, Stax gets web + records | Live; sign-in gate verified off-box |
| 4 Style + designs | `strike-4-style-images` | Designs in chat, Style helper learns each artist, Canvas under Advanced | Live; designs in chat FAILED on the box (photo upload cap) — fixed in Strike 7 |
| 5 Contacts + Forms | `strike-5-contacts-forms` | Form builder, forms hosted at `/f/<slug>`, Contacts in the Records layout | Live; builder -> publish -> phone submit -> contact -> draft verified on the box |
| 6 Clean surfaces | `strike-6-clean-surfaces` | One file per page, consistent headers/empty/error states, surface audit | Live (9686562) |
| 7 Ship hardening | `strike-7-ship-hardening` | Photo uploads fixed (designs in chat), no template blanks in drafts, helper jobs survive updates, daily backups, background helper health in Connections | Live (e004d64); designs in chat verified on the box |
| 8 Memory | `strike-8-memory` | Memory helper proposes facts through a checking tool (exact words, customer only, key in code); approval adds one contact note in code; uploads can be deleted | Deploying (Muse's lane started 2026-11-10; memory on qwen3.7-flash) |
| 9 UI primitives | `strike-9-ui-primitives` | V4's shared behaviours in the fork's look: one question box (dangerous ones open on Cancel, buttons name the action, focus kept and returned), Undo toasts, every pop-up window takes and returns focus and stays on screen, one focus ring, Reduce Motion honoured, no browser pop-ups; Forms asks before discard/take down/remove and offers Undo for a removed block | Not yet deployed |
| 10 Lean and quiet | `strike-10-lean-quiet` | Helpers see only their own instructions, tools and listed skills (per step 40-50% smaller); [wake] rules skip the model when nothing new is waiting; background wakes start clean; a receipt per wake (woke/skipped, steps, tokens, cost) | Not yet deployed. Live test copy: empty sweep 0 model calls, new text wakes it, unchanged thread skips |
| 11 Style in code | `strike-11-style-code` | style_learn/style_correct do the bookkeeping (find pictures, no re-reads, real dates, counts from records, profiles rebuilt); old duplicates merged; kernel keeps helpers' schedules; Style 8 steps on Gemma 4 26B | Not yet deployed. Against fargotattoo.com: 10 pages, 103 pictures found, no picture read twice, counts match records, ~5k tokens per wake |
| 12 Stax finds and builds | `strike-12-stax-finds-builds` | customer_lookup (one call, one person), email_draft (held for approval, threaded), form_draft (builder's own blocks, unpublished, "Drafted by Stax"); Texts/Forms sweeps kept by the kernel (no schedule_create); pinned models in the built-in catalog | Not yet deployed. Live test copy: lookup merged two contacts, email in Needs you, blank refused, form opens in the builder, unknown block refused, restart keeps 4 schedules |

Still open, plainly:
- Memory helper: the Strike 8 deploy is running on the box (its phases are
  in sidecar-phases.py since Strike 8); live result pending Muse's report.
- No browser the agent can drive (log in, click): a later strike.
- Contacts has no Rewards and no appointment-based Today: the fork holds no
  visit, points or appointment data (Square holds the schedule).
- The four Python sidecars are still separate processes; they now report health to Connections, and folding them into the daemon is a post-launch job.

Checks that exist: `cargo test`, `node stax/tests/forms_builder.test.js`,
`python3 stax/tests/test_memcarry.py`, `node stax/tests/ui_primitives.test.js`,
`node stax/tests/ui_primitives_browser.js` (local daemon),
`node stax/tests/form_blocks_sync.test.js`,
`python3 -m unittest stax/bench/test_bench.py`, and
`node stax/tests/surface_audit.js <dir>` (walks every screen on iPad and
phone against a local daemon).

---

## Stop notice of 2026-11-08 (kept for the record)

This repository is the OpenFang fork being reshaped into StaxCloud for
Fargo Tattoo. As of 2026-11-08, **development is stopped at the owner's
order.** The owner does not use this system day to day and does not
consider it usable yet; the shop's working system is the V4 product
(TattooStax/StaxCloud-V4).

Nothing in this repo should be read as live or complete from the
owner's seat. Known state, plainly:

- Surfaces are incomplete. In Forms, a read-only form preview shipped
  2026-11-06; the inline block editor was never built — there is no
  way to build or edit a form from the Forms surface.
- Several surfaces are lists and plumbing rather than finished
  workflows; passing test suites were reported as progress while the
  owner-facing product stayed broken.
- Production branch at stop: `stax-ux` @ 10f879b (the W-4 websites
  surface deploy, 2026-11-07). `stax-ux-v2` is the staging line.

Work resumes only on the owner's word, and "done" means the owner has
used it at his seat and it worked — not a test result.
