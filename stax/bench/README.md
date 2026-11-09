# StaxCloud benchmark and cost meter (Strike 2)

Which model should do which job, measured on the shop's own rules, at what it
really costs.

## Files

- `bench.py` — runs every candidate through the real hand loop (real system
  prompt from `stax/hands/<hand>/HAND.toml`, real tool definitions) against a
  fake records store, then grades what it stored and what it said.
- `cases.jsonl` — 24 shop scenarios (texts, owner asks, decider, memory,
  research, two image prompts). Phone numbers are 555 test numbers. Add a case
  by adding a line; the header comment lists the checks available.
- `candidates.toml` — models per role (checked against OpenRouter's live
  catalog 2026-11-09) and the monthly traffic guess used for cost.
- `sync-prices.py` — writes OpenRouter's live prices into
  `~/.openfang/custom_models.json` so the daemon meters calls correctly.
- `test_bench.py` — offline checks of the grader (no network):
  `cd stax/bench && python3 -m unittest test_bench`

## Run it

```bash
export OPENROUTER_API_KEY=...            # or have it in ~/.openfang/.env
python3 stax/bench/bench.py --dry-run    # the plan, nothing spent
python3 stax/bench/bench.py              # everything (~193 runs, roughly $1-3)
python3 stax/bench/bench.py --images ~/portfolio   # add vision cases from photos
```

Open `stax/bench/results/<time>/scoreboard.md`. Each role lists pass rate,
billed cost, latency, average prompt size, and an estimated monthly cost.
Generated designs land in `results/<time>/images/` — judge those by eye.

For vision grading, put a `labels.json` in the photo folder:
`{"rose-wrist.jpg": "black and grey realism", ...}`.

## Pin the winners

1. Edit `stax/models.toml` (one line per role).
2. `python3 stax/apply-models.py --installed`, then restart the daemon.
3. `python3 stax/bench/sync-prices.py`, then restart again so the meter knows
   the new models' prices.

## Budget

`[budget]` in `~/.openfang/config.toml`:

```toml
[budget]
max_monthly_usd = 5.0                  # whole studio, all agents together
saver_model = "qwen/qwen3.7-flash"     # cheaper model near the limit
saver_at_pct = 0.8                     # switch at 80% of any limit
```

- At `saver_at_pct` of any limit, every agent runs on the saver model.
- At 100% the call is refused with a plain "budget exceeded" message.
- `PUT /api/budget` changes limits and saver at runtime (not saved to
  config.toml).
- `GET /api/usage/agents` shows each agent's average prompt size and cost per
  call. That number is what the monthly cost rests on.
