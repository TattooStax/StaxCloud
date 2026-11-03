# Memory Seat — Shadow Battle Test (2026-11-03)

**Verdict: every end condition met.** Replay of real conversations produced candidates; 13/13 candidate quotes verified verbatim; the adversarial fabrication set was rejected 16/16 (100%); the false-reject rate on genuine quotes measured 0.0 (0/13); the owner-approval gate was dry-run with zero approvals submitted and zero production writes; production contact records are hash-identical before and after. Two design findings were filed (F-1, F-2) — neither is a verification failure; both are exactly what a shadow test exists to surface before arming.

**Basis.** Owner directive 2026-11-03 (~14:47 CST) commissioning shadow battle tests of the memory and System-1 decision seats; Director Call 1 (Fable 5.1 consult, adopted in full by the parent) set the end conditions and the never-skip list this test ran under. The activation runbook was not touched — this test executes zero runbook steps and arms nothing.

**Scope discipline (as re-dispatched).** The first dispatch halted when reading the staged sidecar file tripped a runtime safety check; the parent hash-verified that file as byte-identical first-party state and re-scoped the test to not invoke it (adjudication addendum, `director-consult-2026-11-03-calls.md`). Accordingly, this test's harness was written **fresh** from `MEMORY-SWEEP-BRIEF.md` and the `hands/memory/` masters; the staged sidecar (`sidecar-phases-v2-staged.py`) was never opened, copied, or executed. The test examines the seat's **design as specified**: LLM extraction under the hand's playbook discipline, deterministic verbatim-provenance verification, adversarial fabrication rejection, and the approval-gated promotion path — in shadow.

**Shadow guarantees.** Production data (the box's kv `sms/`, `formsub/`, `contact/` families) was read **GET-only** over the established VM → Victus → box route. The harness runs entirely in local scratch (`~/workspace/openfang-fork/.scratch/memory-battle-test/`); it holds no production write credential and its only network calls are OpenRouter chat completions. Nothing was messaged to anyone; no approval was submitted.

## Method

1. **Snapshot.** Full kv snapshot fetched from the box (GET, bearer key read on-box from the daemon config, never moved off the box): **87 records**. Filtered locally to the test families: `sms/` 3 threads, `formsub/` 9 keys, `contact/` 4 records.
2. **Source selection** (per the brief: named, addressable conversation records only). **7 source records replayed**: all 3 `sms/` threads, plus the 4 `formsub/` records carrying `"processed": true` and a `data` dict. Excluded as non-records: 5 `formsub` debris keys holding status strings (`formsub`, `formsub/`, `formsub/<slug>/<uuid>`, `formsub/new-submissions`, `formsub/status`).
3. **Extraction.** A model call stands in for the memory hand: `openai/gpt-4o-mini` (a cheap fast model of the seat's class — the seat's own model is chosen at activation, not here), temperature 0.2 and max_tokens 4096 per the hand's configuration, system prompt mirroring `hands/memory/HAND.toml` (five fact classes; the quote rule as law; inbound-only quoting for threads; prices/availability out of scope; candidates only). One call per source record, full record as input. Deterministic harness code resolved each candidate's `contact_key` (the brief's index rule) and `memcand/` key (`sha256(source_key + quote)`, first 16) and applied the 20-per-record cap (never reached).
4. **Verification** (Brief Part 7.3, deterministic, no model): a candidate passes the **spec check** iff its `quote` appears verbatim in its source record's raw JSON text (string-stored values: the stored string itself; object-stored values: canonical compact dump). A **content check** runs alongside as a diagnostic: the quote must appear in an actual content string (a message body or a `data` answer value), with origins recorded — this separates "genuine quote the grep missed" (false reject) from "words that match record machinery, not customer text" (spec-only match), and exposes quotes taken from shop-side (outbound) messages.
5. **Adversarial set.** 16 cases, 4 per class, built from the verified genuine quotes and validated at construction time to be genuinely absent from their claimed source (a case that accidentally matched verbatim was not counted): **paraphrase** (model-rewritten genuine quotes), **splice** (two spans of one record joined), **near-miss** (a genuine quote with exactly one word changed), **wrong-contact** (a genuine quote attributed to a different contact's record). Every case ran through the identical `verify_quote()` as the real candidates; rejection requires failing both the spec and content checks.
6. **Approval dry-run.** For each verified candidate, the harness assembled — in scratch only — the carrier's Needs-you payload (Brief Part 3.1 shape) and the promotion result (a copy of the contact record with exactly one `{"ts","text"}` entry appended to `notes[]`, all other fields carried). Where the contact record does not exist, the playbook's stop rule was recorded instead of fabricating a record. Nothing was POSTed.
7. **Untouched proof.** All 4 production `contact/` records were sha256-hashed (canonical dumps) from the before snapshot and from a fresh after snapshot fetched at the end of the test.

*Privacy note:* the report masks the one real-looking phone number as `sms/218…2590`. Exact keys and full result JSONs live in the local scratch evidence (`candidates.json`, `verify_results.json`, `adversarial_cases.json`, `dryrun_results.json`), which is not pushed. All other records in the replay are the store's test-era data (John Doe, the Testcase/Testlead contacts, example-form submissions) plus the owner's own test thread on the shop line.

## Results, by end condition

**1. Replay produced candidates — 13 candidates from 7 sources.**

| Source | Candidates | Note |
|---|---|---|
| `sms/218…2590` (25 msgs) | 5 | the substantive customer thread (unicorn piece) |
| `sms/1234567890` (1 msg) | 0 | only message is "Hello, how are you?" — empty sweep is correct |
| `sms/7018317231` (63 msgs) | 0 | the owner's own line: test probes ("TEST 4817") plus availability/price questions, which are out of scope by law — the extractor stored nothing rather than mining them |
| `formsub/7c9e6679…` (form "example") | 2 | same submission uuid also stored at the next key, with slightly different data ("her ankle" vs "my ankle") — a store-level duplicate; each record was replayed as its own source, per the brief |
| `formsub/contact/7c9e6679…` | 2 | |
| `formsub/contact/8aa00e30…` | 2 | |
| `formsub/contact/c41d77b2…` | 2 | |

**2. Every quote grep-verified — 13/13 verified.** Spec check 13/13, content check 13/13, origins all inbound messages or `data` answers. Fabrications produced by the extractor and caught: **0**. Shop-side (outbound) quotes: **0**. The extractor, on this corpus, fabricated nothing for the gate to catch — the gate's catching power is proven by condition 3 instead.

**3. Adversarial rejection — 16/16 (100%). Required: 100%. PASS.**

| Class | Cases | Rejected | Example (claimed against → quote) |
|---|---|---|---|
| paraphrase | 4 | 4 | `sms/218…2590` → "I want it to be around 4 inches in height, I believe, on my shoulder." (genuine: "I would like it to be 4 inches tall I think on my shoulder") |
| splice | 4 | 4 | `sms/218…2590` → "Tes and I'm just testing the new system." (two spans joined) |
| near-miss | 4 | 4 | `formsub/7c9e6679…` → "a **large** sunflower on her ankle" (genuine: "a **small** sunflower…") |
| wrong-contact | 4 | 4 | "I want that unicorn that I showed you." claimed against a form submission — genuine in the sms thread, absent from the claimed record, rejected: verification is per-source-record, which is the discipline working |

**4. False-reject rate on genuine quotes — 0.0 (0 of 13).** Reported as measured; no mid-test tuning was done. Known gap, stated plainly: no genuine quote in this corpus contained characters that JSON-escaping transforms (double quotes, newlines), so the raw-JSON grep's one theoretical false-reject mode was **not exercised**. The content check runs in the harness precisely so a future run detects that case instead of silently failing a run on it; a corpus with escapable characters is the battery's first extension.

**5. Approval gate dry-run; zero contact writes.** 13 Needs-you payloads assembled in scratch; **0 approvals submitted**. Promotions: **8 assembled** (each target contact's `notes[]` grew by exactly one entry, every other field carried untouched — verified in the assembled copies); **5 would-stop** — all five `sms/218…2590` candidates resolve to `contact/218…2590`, which does not exist in Fang's contact index (the index holds only the 4 test-era contacts; the real book lands with the Round C import). The playbook's stop rule ("a promotion into a void is an invention") held by construction. This is the expected pre-import state, and it quantifies the dependency: until the import lands, sms-thread candidates can be proposed and verified but **cannot promote**.

**6. Production untouched.** Contact hashes before == after, **4/4 identical**; the store still holds 87 records; the harness made no production writes of any kind (its box-side footprint was GET requests plus scratch files in the home directory, removed at the end).

**Candidate list (all 13; quotes verbatim from the records):**

| Candidate key | Field | Value | Quote | Source |
|---|---|---|---|---|
| memcand/10f7a4fe164a4c0a | piece | the unicorn | "I want that unicorn that I showed you." | sms/218…2590 |
| memcand/3eab244b89c7a046 | placement | on my shoulder | "I would like it to be 4 inches tall I think on my shoulder" | sms/218…2590 |
| memcand/8e2a8da650414c76 | preference | I'd like the color in the picture | "I'd like the color in the picture" | sms/218…2590 |
| memcand/3eab244b89c7a046 | life | 4 inches tall | "I would like it to be 4 inches tall I think on my shoulder" | sms/218…2590 |
| memcand/cfd26078ffd777a4 | artist_fit | Leni Bee | "What about Leni Bee?" | sms/218…2590 |
| memcand/4aa26b06579c9306 | piece | a small sunflower | "a small sunflower on her ankle" | formsub/7c9e6679… |
| memcand/5f35e3372fd9b16d | placement | ankle | "ankle" | formsub/7c9e6679… |
| memcand/086502b2182c0397 | piece | A small sunflower | "A small sunflower on my ankle" | formsub/contact/7c9e6679… |
| memcand/d1dec06c914df618 | placement | ankle | "ankle" | formsub/contact/7c9e6679… |
| memcand/5c354b576d69b8c0 | piece | A small black and grey mountain scene | "A small black and grey mountain scene, forearm" | formsub/contact/8aa00e30… |
| memcand/c079382394aafd9a | placement | left forearm | "left forearm" | formsub/contact/8aa00e30… |
| memcand/3a6b11f90a8f96e3 | piece | a small moon phase above the mountains | "could we add a small moon phase above the mountains?" | formsub/contact/c41d77b2… |
| memcand/14c9e02f79d3f26c | placement | left forearm | "left forearm" | formsub/contact/c41d77b2… |

(Uuid suffixes are shortened in this table; full keys are in the local result files.)

## Failure cases and design findings

No end condition failed. The adversarial battery passed in full and the verification gate passed in full. Two findings about the seat's design came out of the replay; both are recorded with evidence because they are invisible to the verification gate:

- **F-1 — Candidate-key collision on multi-fact quotes.** The extractor returned two candidates from the *same* quote with different fields (`placement`: "on my shoulder" and `life`: "4 inches tall"). The Part 2 key — `sha256(source_key + quote)` — is identical for both (`memcand/3eab244b89c7a046`), so in the live store the second write would silently overwrite the first: one fact lost, no error anywhere. The keying assumes one fact per quote; the extraction discipline does not guarantee it. Candidate remedies (a design decision for the seat's owner, not made here): include the field in the hash input, or instruct one candidate per quote span with facts merged. Evidence: `candidates.json` rows 2 and 4.
- **F-2 — The gate proves provenance, not classification.** "4 inches tall" classified as `life` is a misclassification (it is a piece attribute) riding on a perfectly genuine quote. The grep gate cannot catch this class — by design: in the live system the owner's Needs-you review is the classification check, and this finding is the argument for keeping that review human until classification accuracy is itself measured. A related granularity note: placement candidates quoted at whole-answer granularity ("a small sunflower on her ankle" as a piece quote; "ankle" alone as a placement quote) — both verbatim, both acceptable, but quote-length discipline is worth one line in the playbook before arming.

**Limitations.** The corpus is small (7 records, 13 candidates) and mostly test-era data; exactly one substantive customer thread. The extractor is a single stand-in model at the hand's settings; the seat's model selection (and any accuracy comparison across models) belongs to the activation measurement, not this test. The paraphrase class is model-generated (construction-validated deterministically); a fully hand-built paraphrase set is a possible battery extension. None of these soften the adversarial result — fabrication rejection is a property of the deterministic gate, exercised at 100% — but extraction *quality* numbers (0 fabrications, 1 misclassification, 1 key collision in 13) are single-corpus measurements, to be re-measured on the post-import book.

## Spend

Total model spend: **$0.00223** on `openrouter-builder-next` (extraction $0.00215 across 7 calls; paraphrase generation $0.00008 across the adversarial build). Verification, dry-run, and hashing are deterministic: $0.

## Rerun procedure (this harness is the regression battery)

Harness: `~/workspace/openfang-fork/.scratch/memory-battle-test/harness/` (`mbt_common.py`, `mbt_extract.py`, `mbt_verify.py`, `mbt_adversarial.py`, `mbt_dryrun.py`, `make_subset.py`, `run_all.sh`).

1. Fresh snapshot, GET-only: on the box, read `api_key` from `~/.openfang/config.toml` (on-box only), then
   `curl -H "Authorization: Bearer $KEY" http://localhost:4200/api/memory/agents/8cad1d3b-58f9-5563-ba0f-966d734c8a1f/kv` → `snapshot.json`.
2. `python3 harness/make_subset.py snapshot.json .` → `kv-subset.json` + `contact-hashes.json` (the "before" hashes).
3. `bash harness/run_all.sh` — injects the OpenRouter key into env via `~/bin/staxvault-remote geturl openrouter-builder-next https://openrouter.ai` (never printed/stored) and runs extract → verify → adversarial → dry-run, writing `candidates.json`, `extraction_log.json`, `verify_results.json`, `adversarial_cases.json`, `adversarial_results.json`, `dryrun_results.json`, `promotions/`.
4. Re-fetch the snapshot (step 1), re-run step 2 into a second directory, and diff the two `contact-hashes.json` files — they must be identical.
5. Pass bar (unchanged): ≥1 candidate from real records; 100% of candidates spec-verified or explicitly classified; adversarial rejection 100% in all four classes; false-reject rate reported; promotions assembled only in scratch; contact hashes identical.

*Report pushed as a docs-only commit to TattooStax/StaxCloud `stax-ux`, per Director Call 1's end conditions.*
