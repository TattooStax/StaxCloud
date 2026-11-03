# stax/evidence — UX evidence for the StaxCloud reskin of OpenFang

This folder is the inspection record for the Fang → StaxCloud UX work on
branch `stax-ux`: the screenshots that prove each round at the owner's seat
and in staging, the design assets, and the documents that directed the
build. It exists so any agent (or the owner) can audit what was claimed
against what was captured, without needing access to the build machine.

## Layout

- `screenshots/` — per-round capture sets (see the deploy map below).
- `design/` — the traditional-flash tile production:
  - `icon-sheet-candidates/` — the two generated candidate sheets
    (sheet-a.png, sheet-b.png) and the per-cell assessment (NOTES.md).
  - `icon-tiles/` — the final 12 tiles cut from the owner-approved mix
    (Sheet A + Sheet B's contacts and bubble redrawn in A's hand), the
    48px legibility contact sheet, and provenance notes.
- `docs/` — the plans, verdicts, briefs and research that directed the
  work, plus the 2026-11-02 restructure package (Kimi screen scan,
  analysis, Director Verdict 4) and the data-migration map set.

## Screenshot sets → deploy map

| Set | Round | Code | Live binary (sha256 prefix) |
|---|---|---|---|
| `baseline-owner/` | Owner's baseline captures of the stock UI (pre-reskin reference) | — | — |
| `owner-flags/` | Screens the owner flagged himself (e.g. the stock Settings console) | — | — |
| `step1/` | Step 1 — HOME | commit `eceb05e` | `29a8d4bf…` |
| `step2/` | Step 2 — SIDE CARD | commits `a23f4e4`, `5fd143a`, `f7824cb` | `20451972…` |
| `step2-patch/` | Step 2 patch — sections start closed, tiles strip removed, OWNER footer in flow | commit `f4bacb4` | `b067997e…` |
| `corrections2/` | Corrections Round 2 — our icon family (tiers swapped), Settings/Connections become owner surfaces | commits `f33f428`, `b47c7f9`, `1f03d4b` | `f1015029…` |
| `twa/` | TWA build + OnePlus 6T bench proof (v3, then v4 with the reaper tile) | — | — |
| `round3/` | Round 3 — drawer gestures + reaper branding (incl. `live-6t/` device captures) | commits `d0d6789`, `f7bd958` | `2b64573c…` |
| `roundA/` | Round A — navigation restructure (four-tab dock), Home composition, chat titles + dates, status-bubble resolution, tappable links, theme-following status bar, dock safe-area inset | HEAD `69f0e0c` (7 commits) | `b8dd9dfe…` |

**Current live binary: `b8dd9dfe…`** (Round A, deployed 2026-11-02
~23:31 CST to fang.sefer.team; rollback on the box is
`openfang-pre-roundA.bak`). Round 3 (drawer gestures + reaper branding,
commits `d0d6789` + `f7bd958`, binary `2b64573c…`) deployed earlier the
same evening; its captures are in `screenshots/round3/`.

## Also synced in this push (security fixes, 2026-11-02 evening)

- `stax/hands/lead/` and `stax/hands/researcher/` — NEW hand masters
  (HAND.toml + SKILL.md): the shell_exec removal shadowing the bundled
  lead/researcher definitions, so their effective grants no longer hold
  shell access.
- `stax/bridge/bridge.py` (sha256 `a93b1456…`) and `stax/pull-sync.sh`
  (sha256 `4de0359c…`) — refreshed from the running masters: the SMS
  approval-gate enforcement. pull-sync copies the approval id into each
  outbox record and the bridge verifies it live against /api/approvals
  before sending; an unapproved or unverifiable record is refused, never
  sent.

## Deliberately NOT in this public repo

Secrets of any kind, the Cloudflare Worker source (it carries the forms
pull secret), keystores and signing material, APK/AAB binaries (the APK
is the `twa-v4` release asset), and `LOOP.md` (the internal running log).
The TWA wrapper source lives at `stax/twa/` with its own README.

## Also synced in this push (Round A close-out, 2026-11-02 night)

- `screenshots/round3/` (114 files incl. `live-6t/`) and
  `screenshots/roundA/` (350 files) — the evidence top-up for the two
  rounds deployed after the previous sync.
- `docs/SECURITY-GATE-2.md` and `docs/GATE2-STATUS.md` — the shell_exec
  census (13 running stock agents held it, zero crew) and its reduction
  at the Round A deploy (per-agent tool blocklist + workspace hand
  shadows; post-restart census zero, functionally probed), plus the
  staged bridge Gate-2 status: binding + single-use code preserved at
  `stax/bridge/bridge-gate2-staged.py`, proofs outstanding, proven Fix-2
  bridge still live.
- New masters, constructed and validated but NOT yet activated
  (activation is its own window): `stax/hands/decider/`,
  `stax/hands/memory/`, `stax/sidecar-phases.py` (the live digest
  sidecar), `docs/ACTIVATION-RUNBOOK.md`, `docs/DECIDER-SHADOW-BRIEF.md`,
  `docs/MEMORY-SWEEP-BRIEF.md`.
- Refreshed masters: `stax/pull-sync.sh` (sha256 `e067c896…` — the
  digest-phase invocation added; supersedes the `4de0359c…` copy named
  above) and `stax/hands/stax/HAND.toml` (sha256 `990ecfa4…` — conduct
  rule 12, reply brevity, live since the Round A restart).
