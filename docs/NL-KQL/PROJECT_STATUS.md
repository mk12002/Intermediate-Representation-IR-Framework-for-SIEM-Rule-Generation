# Project Status — NL-to-KQL Scope

**Last updated:** 2026-06-22
**Reference plan:** [`MASTER_PLAN.md`](MASTER_PLAN.md) — phases and section numbers below refer to it.

This document tracks the repository as it actually exists right now, not as
planned. It exists because the project's scope was just cut down from a
multi-platform (Sigma/KQL/SPL) framework to KQL-only/ASIM-only, and the
codebase has been restructured to match — this is the single place to check
"is X actually done" before assuming it from the docs alone.

---

## 1. Completed

### 1.1 Code restructure (KQL/ASIM-only scope)

| Component | File(s) | Status |
|---|---|---|
| Security IR schema | `src/ir_engine/ir_schema.py` | Rewritten — ASIM-only `SecurityIR`, `extra="forbid"`, 7 `ASIMEventType` values |
| Schema Validator | `src/ir_engine/ir_validator.py` | Rewritten + extended — FIELD_NOT_FOUND, MISSING_TIME_WINDOW, **INVALID_TIME_WINDOW** (ISO 8601 check), threshold-without-aggregation soft warning, Levenshtein `closest_match` |
| KQL Generator | `src/generator/compiler.py`, `filters.py`, `templates/kql_query.kql.j2` | Single Jinja2 template parameterized by IR (not 7 duplicate templates) — zero LLM calls, deterministic |
| Extraction Agent | `src/agents/extraction_agent.py` | Rewritten to loose `ExtractionOutput` per §11.1 |
| IR Builder Agent | `src/agents/ir_builder_agent.py` | Rewritten with build + repair-attempt prompt variants per §11.2 |
| Monolithic Agent | `src/agents/monolithic_agent.py` | New — Ablation 2 (merged extraction+IR-build) |
| Repair loop | `src/pipeline/repair_loop.py`, `system_b.py` | New — plain-function `run_with_repair()` per §12.3, no LangGraph (simpler, matches docs' literal pseudocode) |
| KQL Syntax Validator | `src/validation/syntax_validators.py` | Rewritten — scoped grammar check (no pySigma), strips comments/string literals before checks |
| System A baseline | `src/baseline/prompt.py`, `run.py`, `few_shot_examples.py` | New — direct-generation baseline, few-shot examples sourced from real ground truth |
| LLM provider | `src/agents/base_agent.py` | Pluggable via `LLM_PROVIDER` env var (ollama/anthropic/openai) |
| Eval harness | `eval/metrics.py`, `stats.py`, `run_comparison.py`, `run_ablations.py` | New — SVR/FVR/RRR metrics, bootstrap CI, McNemar's test, all 3 ablations wired |
| Dataset tooling | `src/data/pull_detections.py`, `extract_schema.py`, `tag_complexity.py`, `make_split.py`, `preflight_check.py` | New |

**Deleted** (out of scope): Sigma/SPL generators + templates, MITRE/metadata/threat-intel/coordinator/repair agents, OCSF resolver/mapper, telemetry sandbox + semantic validator, `src/api/`, `src/storage/`, stale `scripts/test_*.py`, dead `ir_engine/ir_builder.py`, empty `src/generators/` and `src/schema_mapping/` package dirs.

### 1.2 ASIM field reference (real, not guessed)

`data/schema/asim_field_reference.json` — built from the **authoritative
Microsoft Learn docs** (`learn.microsoft.com/.../normalization-schema-*`),
not the Azure-Sentinel repo's `ASIM/schemas/*.yaml` (that format uses
`Include:`/`<<Role>>` placeholder resolution requiring ASIM's own schema
compiler to resolve correctly — out of scope, documented as such in
`src/data/extract_schema.py`).

- 7 event types, 79–211 fields each
- Spot-checked against known-good/known-bad field names (`TargetUsername`,
  `SrcIpAddr` present; hallucinated `SourceIP` absent)
- Source attribution recorded in `data/raw/SOURCE_ATTRIBUTION.md` (doc
  `git_commit_id`, fetch date, all 8 source URLs)
- **Known gap:** field tables were hand-transcribed from fetched pages
  (descriptions dropped, only `Field`/`Class` kept) — re-verify against live
  docs before trusting beyond this project's validation use case

### 1.3 Local LLM setup

- Ollama 0.30.10 installed
- `qwen2.5:7b-instruct` (IR Builder Agent + System A baseline) and
  `qwen2.5:3b-instruct` (Extraction Agent) pulled — chosen for 6GB VRAM
  (Q4_K_M quantization fits comfortably)
- `LLM_PROVIDER=ollama` confirmed instantiating `ChatOllama` correctly
- `.env.example` updated with the new model defaults

### 1.4 Bugs found and fixed during integration review

These were real defects caught by actually running things, not just reading code:

1. **`field_validity_rate` (`eval/metrics.py`)** — the metric backing H2/RQ1,
   the project's central claim — tokenized whole queries including string
   literals, `let` bindings, and `summarize` aliases, requiring every token
   to be a literal schema field name. Would have reported near-zero FVR on
   almost any real query. **Fixed**: strips comments/strings, excludes
   `let`/assignment-alias locals and the leading table reference, expanded
   KQL keyword/function list.
2. **SQL/SPL-leak check (`syntax_validators.py`)** — false-positived on the
   word "from" appearing inside a comment or string literal (real ground-truth
   queries contain this). **Fixed**: strips comments/strings first.
3. **`pull_detections.py`** — silently discarded the "non-ASIM, reserved"
   bucket the docs explicitly call for (extract_pair filtered before the
   bucket split could see non-matching rows); also used a bare substring
   `"im"` match that false-positives on words like "claim"/"victim".
   **Fixed**: word-boundary table-name regex, bucket split happens after
   extraction.
4. **`ir_validator.py`** missing two spec-mandated checks (MASTER_PLAN
   §10.3): ISO 8601 format validation on `time_window`, and the soft warning
   for "threshold set without aggregation". **Fixed** and unit-tested.
5. Dead code: `src/ir_engine/ir_builder.py` imported schema classes
   (`IRMetadata`, `DetectionLogic`, `MITREMapping`, etc.) removed in the
   rewrite — would have raised `ImportError` if anything imported it (nothing
   did). Deleted. Two empty leftover package dirs also deleted.

### 1.5 Verified working (actually run, not just unit-tested)

- `generate_kql()` output matches MASTER_PLAN's worked example byte-for-byte
- `validate_kql_syntax()` / `field_validity_rate()` give correct results
  against real ground-truth queries pulled from Azure-Sentinel (including the
  edge case of a genuinely deprecated ASIM field, `SrcDvcIpAddr`, correctly
  flagged rather than missed)
- `ExtractionAgent.extract()` — real call to local Qwen2.5 3B, parsed into
  valid `ExtractionOutput`
- Full `run_system_b()` pipeline (Extraction → IR Builder → Schema Validator
  → KQL Generator → Syntax Validator, with repair loop) — real call to local
  Qwen2.5 7B, no crashes, repair loop correctly triggered a retry on an
  `INVALID_TIME_WINDOW` failure
- 39 unit tests, all passing (`pytest tests/unit -q`)

---

## 2. Partially done

### 2.1 Dataset (Phase 1 — by far the most incomplete piece)

- **195 unique raw (NL, KQL) pairs** pulled from `Detections/` (33) +
  `Hunting Queries/` (21) + `Solutions/` (141) — `data/raw/*_raw.jsonl`.
  Exceeds the 100–150 target, but **zero pairs are verified**.
- Complexity auto-tagged (`data/processed/pairs_tagged_unverified.jsonl`) —
  **skewed: 92% complex, ~2% moderate, ~7% simple** against a 35/35/30
  target. Likely cause: the `filter_count >= 3` heuristic over-triggers on
  real ASIM rules that chain several `where` clauses for routine noise
  filtering, not genuine logical complexity. **Not fixed** — the threshold is
  a documented judgment call (§16.2 Step 5), not something to silently retune.
- Pre-flight mechanical triage run (`data/processed/preflight_report.jsonl`):
  syntax-fail 37%, no-event-type-detected 7%, unknown-fields 82%, clean 11%.
  This is a **triage signal, not a verdict** — it doesn't replace the manual
  rubric, and some "unknown fields" hits are real (deprecated field names),
  some are likely remaining gaps in the triage script's own KQL-function
  keyword list (diminishing returns on closing further — true KQL parsing is
  explicitly out of scope per §23).
- Paraphrasing: **not started**. Two few-shot baseline examples were hand-built
  from real pairs (caught and fixed my own drift once while doing this — see
  §1.4-adjacent note in conversation history), but the 195-pair dataset itself
  has no paraphrase variants yet.
- Train/test split: **script written (`src/data/make_split.py`), not run** —
  running it now would split unverified data, which the docs' own discipline
  forbids (§16.2 Step 6 happens after manual verification, not before).

### 2.2 Model quality (expected, not a bug)

Running the live worked example (`docs/NL-KQL/MASTER_PLAN.md` §14) through
the real pipeline failed to converge in 3 repair attempts — the IR Builder
Agent (Qwen2.5 7B) picked wrong filter fields and never added the aggregation
the case requires. The mechanics are correct (validator caught a malformed
`time_window` and forced a retry, as designed); the *model* just isn't
reliably solving this case yet at this size/quantization with the current
prompts. This is exactly the kind of signal H1/H3 are designed to produce —
not something to patch by hand-tuning the prompt against one example, since
that would be informal prompt engineering against what should become eval
data.

---

## 3. Left to do

Mapped to MASTER_PLAN §22/§27 phases — see the Execution Checklist there for
the exhaustive version. Condensed here to what's not yet even partially done:

- **Phase 1 (Dataset):** manual verification rubric application to all 195
  pairs; paraphrasing (2–3 styles) + drift review; spot-check the complexity
  skew; generate + commit the train/test split.
- **Phase 2 (MVP):** run the 10-hand-picked-case MVP inspection MASTER_PLAN
  calls for before touching the full dataset (not done — we smoke-tested 1
  case, not 10, and not the hand-picked diverse set the docs specify).
- **Phase 3 (Baseline):** few-shot examples are drafted but not finalized/frozen.
- **Phase 4 (Full eval):** `eval/run_comparison.py` and `run_ablations.py` are
  wired and import-clean but have never been run against real data — they
  need a finished, verified, split dataset first.
- **Phase 5 (Analysis):** nothing started — depends entirely on Phase 4.
- **Phase 6 (Write-up):** nothing started.

---

## 4. What you have to do (irreducibly human)

These aren't blocked on more agent time — they're blocked because the docs'
own methodology requires human judgment here, and faking that judgment would
corrupt the ground truth the whole evaluation rests on:

1. **Manual verification** of all 195 pairs against the 4-point rubric (KQL
   parses, description matches query logic, no orphaned complexity, fields
   current) — MASTER_PLAN §16.2 Step 4. Expect to discard 15–25%.
2. **Paraphrasing review** — every paraphrase (once drafted) needs your read
   against the original KQL for drift, even if LLM-assisted to draft.
3. **Spot-check the complexity tagging skew** (92% complex looks wrong; only
   a human read of a sample can say whether the heuristic or the data is off).
4. **Logic Correctness manual scoring** (Phase 5) — inherently manual, no
   way around it.
5. Optional but recommended: a second KQL-familiar reviewer for inter-rater
   reliability (Cohen's κ) on a 20-case sample.

---

## 5. What's confirmed working vs. not, right now

| | Status |
|---|---|
| `generate_kql()` / template compiler | ✅ Working, verified against worked example |
| Schema Validator (`validate_ir`) | ✅ Working, all rules implemented incl. the 2 found gaps |
| KQL Syntax Validator | ✅ Working after the comment/string-literal fix |
| FVR/SVR metrics (`eval/metrics.py`) | ✅ Working after the critical fix — verified against real ground truth |
| Extraction Agent (live model call) | ✅ Runs, returns valid structured output |
| IR Builder Agent (live model call) | ✅ Runs without crashing; ⚠️ output *quality* unreliable on the one case tested so far |
| Repair loop | ✅ Mechanically correct (retries on the right trigger) |
| System A baseline | ✅ Imports/instantiates correctly; **never run end-to-end** (no test yet) |
| `eval/run_comparison.py`, `run_ablations.py` | ✅ Import-clean; **never run** (no dataset to run against) |
| Dataset (195 pairs) | ⚠️ Pulled, **not verified** — do not treat as usable yet |
| Complexity tagging | ⚠️ Runs, but output distribution looks wrong — unconfirmed |
| Pre-flight triage | ⚠️ Useful signal, not authoritative |
| Train/test split | ❌ Not generated (intentionally — see §2.1) |
| Paraphrasing | ❌ Not started |
| Full evaluation / ablations | ❌ Not run |
| Logic Correctness scoring | ❌ Not started |

---

## 6. Future plans

**Immediate next step (yours):** start manual verification on
`data/processed/pairs_tagged_unverified.jsonl`, using
`data/processed/preflight_report.jsonl` to triage review order (clean-flagged
pairs first to bank quick wins, syntax-fail-flagged pairs likely discards).

**Then, in order:**
1. Finish Phase 1 (verification → paraphrasing → split), committing
   `train_ids.json`/`test_ids.json` immediately and never touching the test
   split again during development.
2. Run the Phase 2 MVP — 10 hand-picked cases across complexity tiers,
   inspect every stage manually before trusting the pipeline on the full set.
   Given today's single smoke test struggled, expect to iterate on the IR
   Builder Agent's prompt here, not later.
3. Freeze the System A baseline prompt and few-shot examples.
4. Run the full primary comparison + all 3 ablations.
5. Statistical analysis (bootstrap CI, McNemar, Wilcoxon — `eval/stats.py` is
   ready) + manual Logic Correctness scoring.
6. Write-up.

**Open technical question to revisit:** whether Qwen2.5 7B at this
quantization is strong enough for the IR Builder Agent's task, or whether the
Phase 2 MVP will reveal a need for a larger/different model — worth deciding
*before* running the full 100+ case evaluation, not after, since the model
choice should be fixed for the whole study (MASTER_PLAN §20).
