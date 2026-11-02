# Designer — Studio Design Generator on OpenFang

Source of record for the Designer landing (installed live on
fang.sefer.team 2026-11-02). The hand lives in
`stax/hands/designer/` (HAND.toml + SKILL.md — the playbook is
the contract). This folder holds the deterministic half:

- `designer_sidecar.py` — the executor beside the daemon
  (5-minute flock cron, same pattern as `stax/pull-sync.sh`).
  Discovers jobs ONLY via the fixed kv index `designjob/index`,
  runs a 21-op allowlist against the package core, carries
  `draft/design-<request_id>` approval holds into Needs-you and
  writes decisions back onto `designreq/<id>`.
- `studio_design/` — the package core (plug-in
  studio-design-generator v0.10.0). Box runtime deps:
  Pillow>=9.0, numpy>=1.26, scipy>=1.11 (python3, user site).
- `surface-designer.json` — install artifact; the installer
  stores its `value` (exactly {title, blocks}) at kv key
  `surface/designer`.

Install (durable): copy `stax/hands/designer/` to
`~/.openfang/hands/designer/`; copy `designer_sidecar.py` +
`studio_design/` beside the daemon (~/openfang-play) with
PYTHONPATH pointing there; add the flock cron line beside
pull-sync's; graceful restart (`./openfang stop`, then start);
activate the hand (POST /api/hands/designer/activate). Full
contract + proof record: the plug-in's RESULTS13-OPENFANG-LANDING.md
(studio-design-plugin workspace folder).
