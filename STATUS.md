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
| 7 Ship hardening | `strike-7-ship-hardening` | Photo uploads fixed (designs in chat), no template blanks in drafts, helper jobs survive updates, daily backups, background helper health in Connections | Not yet deployed; then the 30-day shop run |

Still open, plainly:
- The Memory helper asks the model to compute SHA-256 keys, which models
  cannot do; its key design needs changing before it can work.
- Model pins for driver, vision and image wait on a benchmark rerun.
- Contacts has no Rewards and no appointment-based Today: the fork holds no
  visit, points or appointment data (Square holds the schedule).
- The four Python sidecars are still separate processes; they now report health to Connections, and folding them into the daemon is a post-launch job.

Checks that exist: `cargo test`, `node stax/tests/forms_builder.test.js`,
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
