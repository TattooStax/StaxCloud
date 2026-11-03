# Builder Harness — prep for the Opus 5.5 builder (OpenFang UX build)

Prepared 2026-11-02. Status: **prepared, NOT activated.** No key exists in this
setup yet; nothing was installed, no repo file was touched, no OpenRouter API
call was made. The builder model is the director's pick (Verdict #3 addendum):
**Claude Opus 5.5 via OpenRouter**, model string `openrouter/anthropic/claude-opus-5.5`.
The owner is creating a NEW dedicated OpenRouter key with a $100 budget.

## 1. CLI inventory (read live 2026-11-02)

### This VM (Muse runtime host, Linux x86_64)

| CLI | State |
| --- | --- |
| opencode | absent |
| claude | absent |
| codex | **present** — /opt/hatch-image/bin/codex, codex-cli 0.164.0-alpha.9 |
| aider / cline / gemini / goose | absent |
| node / npm | v24.22.1 / 10.9.4 |

### Victus build lane (shawnlowe@100.94.221.70, Fedora 44)

| CLI | State |
| --- | --- |
| opencode | **present** — ~/.local/bin/opencode, **1.18.34** (user-space install) |
| claude | **present** — ~/.local/bin/claude, 2.1.285 (Claude Code) |
| codex / aider / cline / gemini / goose | absent |
| node / npm | v24.21.0 / 11.19.0 (user-space node under ~/.local/share/victus-dev/; `npm install -g` there needs no sudo) |
| Fang tree | ~/openfang-build/repo, branch `stax-ux`, HEAD c9b93c7 (the dock fix) |
| OpenCode auth | `opencode auth list` → **0 credentials** — no provider connected |
| OpenCode config | a global ~/.config/opencode/opencode.jsonc exists (50 bytes, not inspected); no opencode.json in the repo |

## 2. Recommended location: the Victus — and no install is needed

- The Fang build tree lives on the Victus and the loop builds there; this VM's
  builds/git writes are storage-broken (standing record).
- OpenCode 1.18.34 is **already installed user-space** on the Victus, beside the
  tree. Claude Code 2.1.285 is also there as a fallback harness (it would need
  Anthropic-side credentials, which are not connected — OpenCode + OpenRouter
  remains the route).
- This VM has no OpenCode and only OpenAI's codex — the wrong shape for an
  OpenRouter key without extra shims.
- **No installation was performed.** If a machine ever needs it, the official
  user-space methods (opencode.ai/docs, OpenCode 1 line) are
  `curl -fsSL https://opencode.ai/install | bash` or `npm install -g opencode-ai`,
  verified afterward with `opencode --version`.

## 3. OpenCode + OpenRouter — verified from official docs

Sources read live 2026-11-02: opencode.ai/docs (intro, providers, config, cli)
and OpenRouter's own cookbook (openrouterteam/docs, opencode-integration).

- **Provider:** OpenRouter is a built-in provider, id **`openrouter`**. No custom
  provider block or baseURL is needed.
- **Model string:** OpenCode composes `provider_id/model_id`, so the pick is
  **`openrouter/anthropic/claude-opus-5.5`** — set as the top-level `model` or
  passed per run with `--model` / `-m`. (The model slug's presence in
  OpenRouter's catalog was verified by the director on OpenRouter's model page;
  whether the Victus's local `opencode models openrouter` lists it before a key
  is connected is **unverified** — it returned nothing with 0 credentials.)
- **Key supply, three documented routes:** (a) `/connect` in the TUI or
  `opencode auth login` → stored in ~/.local/share/opencode/auth.json;
  (b) the `OPENROUTER_API_KEY` environment variable, auto-loaded (OpenCode also
  reads a project `.env`); (c) config interpolation — `"apiKey": "{env:OPENROUTER_API_KEY}"`
  under `provider.openrouter.options` (`{env:VAR}` and `{file:path}` substitution
  are documented config features). Route (c) is what the draft below uses: the
  config file itself never contains a key.
- **Project scoping:** `opencode.json` in the project root is the project config
  (configs merge; project overrides global). Alternatives: `OPENCODE_CONFIG`
  env var pointing at any file, `opencode run --dir <path>`.
- **Non-interactive runs:** `opencode run [message..]` with `--model`,
  `--dir`, `--format json` (raw JSON events), `--auto` (auto-approve
  permissions not explicitly denied), `--file`, `--session` / `--continue`.

## 4. The config that WILL be used (draft — not yet written anywhere)

Placement at activation: `~/openfang-build/opencode.builder.json` on the
Victus — **outside** the repo tree (the fork is public; the repo stays
untouched) — selected via `OPENCODE_CONFIG` at launch. Its contents:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "openrouter/anthropic/claude-opus-5.5",
  "provider": {
    "openrouter": {
      "options": {
        "apiKey": "{env:OPENROUTER_API_KEY}"
      }
    }
  }
}
```

Launch shape once keyed (key injected into the environment only, §5):

```bash
cd ~/openfang-build/repo
OPENCODE_CONFIG=~/openfang-build/opencode.builder.json \
  opencode run --auto --format json \
  -m openrouter/anthropic/claude-opus-5.5 "<task>"
```

Notes: no `small_model` is set, so OpenCode's lightweight calls (titles etc.)
fall back to the main model unless a cheaper OpenRouter model is configured —
a cost line the owner/director may want to settle before long runs. The
existing global opencode.jsonc on the Victus merges underneath; the builder
config wins on the keys it sets.

## 5. Credential hand-off — the problem, stated plainly

The Muse **custom.openrouter connector credential cannot be read by an
external CLI.** It lives in the connector runtime; there is no key file on
either machine for OpenCode to pick up (verified on the Victus: 0 stored
credentials). That is also the wrong key: it is the director key ($50/mo cap,
expires 2026-11-27). The owner's new dedicated $100 builder key needs its own
route to the CLI. Viable routes:

1. **staxvault release + launch-time env injection (recommended).** The owner
   stores the new key in staxvault as a dedicated entry (e.g.
   `openrouter-builder`) with the geturl allowlist set to the origin
   `https://openrouter.ai`. At launch, the parent agent calls
   `staxvault-remote geturl openrouter-builder https://openrouter.ai`, takes
   the released secret field, and injects it as `OPENROUTER_API_KEY` into the
   environment of the ssh command that runs OpenCode on the Victus. The value
   is never written to disk on either machine, never appears in chat or argv,
   and release stays gated by the vault's exact-origin allowlist; revoking =
   delete the vault entry and/or rotate the key at OpenRouter. Caveat: the
   vault's allowlist was designed for browser sign-ins; using the same
   origin gate to release an API key for that origin is a judgment call.
2. **One-time `opencode auth login` on the Victus.** The owner (or a session
   he supervises) runs it once and pastes the key at the prompt; OpenCode
   persists it in ~/.local/share/opencode/auth.json and every later launch
   just works. Simplest and durable — but the key then sits at rest, in
   plaintext JSON, on the Victus disk.
3. **Manual per-launch injection.** The owner hands the key to the parent
   agent out-of-band for each run; exported for that run only. Nothing at
   rest, but the key transits an agent's hands every time — least preferred.

**Recommendation: route 1**, with route 2 as the fallback if the vault's
release semantics are judged browser-only. **This choice is the owner's.**

## 6. First task once keyed — Verdict #3, Step 1: HOME

One slice, presentation only (static/** templates), wiring untouched:

- Split the conversation markup out of the agents template into a dedicated
  home template rendering ONLY: the agent identity header (avatar + "Stax";
  tap → Stax card, Figma 4); status in plain words from real state ("Text
  replies: Automatic"); the morning brief as first card (the existing
  brief/<date> record + real Needs-you count — the brief card currently sits
  orphaned in the overview template and is carried in); the conversation
  thread; the "Ask Stax" composer. Stale #overview / #agents routes are
  demoted so a fresh or stale-hash open lands on home.
- First-open state per Figma screen 1: mascot centered, greeting by name,
  ONE action — "Set up my studio" — which starts the setup *conversation*
  (retiring the R10 stepper).
- Every hide-list item gated out of home and owner surfaces, demoted (never
  deleted) to a Helpers view under System → Advanced: + New Helper / Stop
  All, the helper catalog, Create Agent / Configure Provider / Browse Skills
  cards, the raw activity feed, fleet lists.
- The dock-width fix (already HEAD c9b93c7 on the Victus tree) folds into
  this build and stops being a separate milestone.
- **Gate (Verdict #3):** after deploy, a fresh login on the live instance;
  phone-width and desktop screenshots of the actual landing, filed beside
  Figma screens 1–2. The slice is reported only as what those screenshots
  show; served-bytes/grep/smoke results are never reported as UX progress.

## Unverified / open items

- Local model-catalog visibility of `anthropic/claude-opus-5.5` on the Victus
  before a key is connected (see §3).
- Contents of the pre-existing global ~/.config/opencode/opencode.jsonc
  (not inspected; merges under the builder config).
- Everything above is written against the OpenCode **1.x** docs, matching the
  installed 1.18.34; OpenCode 2 is a separate release line and was not
  evaluated.
