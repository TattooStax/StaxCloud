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

**Current live binary: `f1015029…`** (Corrections Round 2, deployed
2026-11-02 ~19:03 CST to fang.sefer.team; rollback on the box is
`openfang-pre-corrections2.bak`). Round 3 (drawer gestures + reaper
branding, commits `d0d6789` + `f7bd958`) is built and staged; it deploys
after this sync, so no screenshot set for it exists yet.

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
