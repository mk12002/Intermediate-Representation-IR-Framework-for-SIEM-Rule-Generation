# Project Status — NL-to-KQL Scope

**Last updated:** 2026-06-24
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
- Source attribution recorded in `data/raw/SOURCE_ATTRIBUTION.md` (doc
  `git_commit_id`, fetch date, all 8 source URLs)
- **Fully re-audited against the live docs (2026-06-22), not just spot-checked.**
  The original transcription (`data/raw/asim_docs/*.md`) was hand-condensed
  from fetched page content, which carried real transcription risk. Re-verified
  by independently re-fetching all 8 pages and reconciling field-name sets:
  - 4/7 schemas (Common, Authentication, Process, NetworkSession) diffed
    directly against a second independent transcription — **zero
    discrepancies**, including one exact byte-for-byte file comparison
    (NetworkSession, 145/145 fields agree)
  - 3/7 schemas (Dns, FileEvent, RegistryEvent) reconciled by field-count
    against the freshly fetched live text — **exact matches** (102/102,
    89/89, 36/36) plus WebSession (33/33)
  - The only "discrepancies" found were fields already covered via the
    `common_fields.md` union in `extract_schema.py`'s `build_field_reference()`
    (confirmed present in the final JSON output directly, not inferred)
  - Audit artifacts kept in `data/raw/asim_docs_full/` for reproducibility

### 1.3 Local LLM setup

- Ollama 0.30.10 installed
- `LLM_PROVIDER=ollama` confirmed instantiating `ChatOllama` correctly
- **Model choice corrected mid-project, then verified live.** Initially
  recommended Qwen2.5 (7B-instruct / 3B-instruct), based on training
  knowledge with an August 2025 cutoff. Checked live against the current
  Ollama library (`ollama.com/library`) and found this was stale: Qwen3,
  Qwen3.5, and Qwen3.6 all exist now. Switched to `qwen3.5:4b` (IR Builder +
  baseline) / `qwen3.5:2b` (Extraction) — fits 6GB VRAM with more headroom
  than Qwen2.5 7B, scores IFEval 92.6 / IFBench 76.5, vendor-documented
  parity with Qwen3 (which itself surpasses Qwen2.5 on reasoning).
  **Confirmed working end-to-end**, but only after finding and fixing two
  real bugs the model switch exposed (§1.4) — this was not a clean drop-in.
- **Lesson for future model choices in this project:** always check the
  live model registry before committing, don't rely on training-data
  recall — confirmed wrong once already in this exact session. Also: a
  newer/better-benchmarked model is not a safe drop-in swap without
  re-verifying the integration live — confirmed twice in the same session.
- `.env.example` and all 4 agent hardcoded fallback defaults updated to the
  new model tags

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
6. **`base_agent.py`'s `ChatOllama` instantiation, found when switching to
   Qwen3.5** — thinking-capable models (Qwen3.x family) default to emitting
   `<think>` reasoning content, which combined with `format="json"` burned
   the entire output token budget on reasoning and returned empty content
   (`done_reason="length"`, `eval_count=3612`, `content=""`). The Extraction
   Agent crashed outright. **Fixed**: pass `reasoning=False` to `ChatOllama`.
   Confirmed harmless for non-thinking models (Qwen2.5) too.
7. **`BaseAgent._invoke()`'s internal retry conflicted with the IR Builder's
   own structured-error repair loop** — at `temperature=0` (this whole
   study's setting), a failed parse was retried 3 times against the
   *identical deterministic input*, reproducing the *identical failure* 3
   times, then raised an uncaught exception before the real repair
   mechanism (which feeds the specific error back to the model) ever ran.
   Only surfaced once a model (Qwen3.5) actually produced a structurally-valid-
   JSON-but-Pydantic-invalid completion (a `null` where a typed value was
   required) — Qwen2.5 never hit this path. **Fixed**: `max_attempts` is now
   1 at `temperature=0` (retrying is pointless when deterministic); `repair_loop.py`
   now catches `OutputParserException`/`ValidationError` from the IR Builder
   call and converts it into a repairable `ValidationResult` instead of
   letting it crash the pipeline.
8. **`_VALID_CLAUSE_KEYWORDS` (`syntax_validators.py`)** missing several
   legitimate KQL clause keywords (`mv-expand`, `mvexpand`, `parse`,
   `project-away`, etc.) — caused false SYNTAX failures on real, valid
   ground-truth KQL during the 195-pair manual review. **Fixed**: expanded
   the keyword set.
9. **`_SINGLE_EQUALS_COMPARISON` (`syntax_validators.py`)** falsely flagged
   the case-insensitive operators `=~`/`!~` as the single-equals-typo error.
   **Fixed**: added a `(?!~)` negative lookahead.
10. **`_SQL_SPL_LEAKAGE` (`syntax_validators.py`)** bare `"FROM"` check
    false-positived on legitimate KQL `make-series ... from ... to ... step`
    syntax. **Fixed**: removed the bare-FROM pattern.
11. **`_STRING_LITERAL` (`syntax_validators.py`)** regex didn't handle KQL
    verbatim strings (`@'...'`/`@"..."`, where backslash is literal, not an
    escape character) — caused massive over-consumption of subsequent text
    and many false "unknown field" positives. **Fixed**: verbatim strings
    matched separately from escaped strings.
12. **`_PARSER_KWARG` gap (`eval/metrics.py`)** — lowercase parser-call
    kwargs (e.g. `responsecodename=` in `_Im_Dns(responsecodename=...)`)
    were flagged as unknown schema fields. **Fixed**: added a kwarg-pattern
    exclusion.
13. **`_ASSIGNMENT_TARGET` gap (`eval/metrics.py`)** — multi-key
    `extend X=.., Y=..` patterns only captured the first alias as a known
    local, so the second+ alias was checked as if it were a schema field.
    **Fixed**: regex now matches every comma-separated assignment target.

Items 8–13 are the "6 more real bugs" §2.1 refers to — `syntax_fail` rate on
the full 195-pair dataset dropped from 37% to 0% as a direct, measured
result of fixing them.

14. **`repair_loop.py`'s schema-field-list lookup (found 2026-06-23, via a
    live Azure AI Foundry / gpt-4.1-mini run)** — `extraction.likely_event_type`
    is deliberately free text (`ExtractionOutput` is intentionally
    under-constrained, see its docstring), so it routinely fails to match
    one of the 7 ASIM schema dict keys exactly. The old code fell back to
    `[]` on any mismatch — silently handing the IR Builder **zero fields**
    while the prompt still said "only use fields from this reference",
    reproducing the No-Schema-Grounding ablation's manipulation by accident
    on the *main* path. **Measured 0/10 exact matches on a live MVP sample**
    — this bug fired on (functionally) every call, for every model, for the
    entire study so far. **Fixed**: fall back to the union of every event
    type's fields instead of `[]`; the IR Builder still commits to its own
    `event_type`, and `validate_ir` checks fields against that committed
    type's real sub-schema regardless of what was shown at generation time.
    Confirmed by direct re-test: same 10 MVP cases, gpt-4.1-mini went from
    0/10 to 8/10 success after this one fix. **This invalidates the §4
    headline numbers below as a comparison of model capability or
    IR-mediation viability** — they were instead substantially measuring
    this bug. See §4B for the corrected re-run.
15. **`kql_query.kql.j2`'s threshold-without-aggregation case (found
    2026-06-23, same session)** — when `threshold` is set but `aggregation`
    is `None` (previously a soft warning, not a blocking error — see old
    §1.4 item 4), the template's `{{ aggregation.result_alias }}` resolves
    against `None`, Jinja renders it as empty string, and the compiler
    silently emits dead KQL like `| where  > 1` (no left operand) that still
    passes syntax validation, since "no left operand before an operator"
    isn't a grammar violation the checker looks for. **Fixed**: promoted
    `ir_validator.py`'s threshold-without-aggregation check from a soft
    warning to a hard `THRESHOLD_WITHOUT_AGGREGATION` error, so it now
    blocks and triggers repair instead of silently passing through.

### 1.5 Verified working (actually run, not just unit-tested)

- `generate_kql()` output matches MASTER_PLAN's worked example byte-for-byte
- `validate_kql_syntax()` / `field_validity_rate()` give correct results
  against real ground-truth queries pulled from Azure-Sentinel (including the
  edge case of a genuinely deprecated ASIM field, `SrcDvcIpAddr`, correctly
  flagged rather than missed)
- `ExtractionAgent.extract()` — real call to local Qwen3.5 2B, parsed into
  valid `ExtractionOutput` (after the `reasoning=False` fix above)
- Full `run_system_b()` pipeline (Extraction → IR Builder → Schema Validator
  → KQL Generator → Syntax Validator, with repair loop) — real call to local
  Qwen3.5 4B/2B, **confirmed running cleanly end-to-end with the bug fixes
  above**: no crashes, no uncaught exceptions, the repair loop correctly
  retried across multiple attempts with structured errors fed back each time.
  Result on the one worked-example case tested: `MAX_REPAIR_ATTEMPTS_EXCEEDED`
  — the model produced plausible-looking IRs (real ASIM-shaped field names)
  that still failed schema validation within 3 attempts. This mirrors the
  earlier Qwen2.5 result (also failed to converge on the same case) — treat
  as a genuine, reportable signal that this case is hard at this model scale,
  not as evidence the pipeline is broken. The infrastructure bug that used to
  mask this signal (uncaught crash) is what's now fixed.
- 57 unit tests, all passing (`pytest tests/unit -q`) as of 2026-06-23,
  including regression tests for items 14–16 above
  (`test_unmatched_likely_event_type_falls_back_to_full_union_not_empty_list`,
  `test_threshold_without_aggregation_is_a_hard_error`,
  `test_degenerate_count_threshold_is_a_hard_error`,
  `test_aggregation_with_time_window_but_no_group_by_has_no_leading_comma`)

---

## 2. Dataset — Phase 1 complete (AI-assisted, not human-reviewed)

**Important caveat up front:** the manual verification rubric, paraphrase
drift review, and complexity spot-check below were all done by Claude
reading and judging every pair directly, at the user's explicit instruction
("do everything you can" — see conversation 2026-06-22), not by a human.
Treat this as a strong first pass that materially de-risks the dataset, not
as a substitute for the human sign-off the methodology was designed around.
Re-spot-check a sample before publishing any results derived from it.

### 2.1 Manual verification (all 195 pairs reviewed)

- 195 raw pairs → **81 verified pairs** (58% discard rate — higher than
  MASTER_PLAN's predicted 15–25%, because this pull includes `Hunting
  Queries/`+`Solutions/`, which contain far more non-ASIM-pure and
  vendor-specific content than the curated `Detections/` folder alone).
- Discard reasons, all logged per-pair in `data/processed/manual_verdicts.json`:
  deprecated ASIM field names (e.g. `SrcDvcIpAddr`, pre-2022 alias),
  non-ASIM raw tables (`SecurityAlert`, `DeviceInfo`, `*_CL` custom log
  tables), out-of-scope ASIM schemas (`ASimAlertEvent`, `ASimAuditEventLogs`
  — only 7 of ASIM's full schema set are implemented in this IR),
  vendor-specific parser functions (`ASimNetworkSessionSonicWallFirewall`),
  genuine description/logic mismatches (e.g. a rule claiming "top four
  domains" with no such limit implemented; a port-scan rule whose grouping
  direction was backwards from its own description), and 16 pairs whose
  "description" was a bare vendor/IOC-type label with zero behavioral
  content ("Google Threat Intelligence Url correlation.") — technically not
  contradicted by the query, but useless as a translation target.
- **While doing this review, found and fixed 6 more real bugs** in the
  project's own validation tooling (not the dataset) — see §1.4 items 8-13
  below. `syntax_fail` rate on the full 195 dropped from 37% to 0% as a
  direct result, confirming the ground-truth KQL was fine all along.

### 2.2 Complexity tagging — re-tagged, residual skew is real, not a bug

Original heuristic tagged 86% of verified pairs "complex" — partly a real
comma-counting bug (`bin(TimeGenerated, 10m)`'s internal comma inflated
group-by key counts), partly because 3+ plain AND-chained `where` filters
were weighted equal to genuine structural complexity (joins/correlation).
Fixed the bug and revised the heuristic (`src/data/tag_complexity.py` v2,
rationale documented in the docstring) — **final distribution: 58% complex /
21% simple / 21% moderate**. Still above the 35/35/30 target; the residual
skew is a genuine property of this dataset (Hunting Queries trend
multi-filter), not something further heuristic tuning should chase away.

### 2.3 Train/test split — generated and committed

**66 train / 15 test** (`data/splits/{train,test}_ids.json`), stratified by
the v2 complexity tier, seed 42. Generated only after verification per
MASTER_PLAN §16.2 Step 6 discipline.

### 2.4 Paraphrasing — done for the 15 test pairs only

2 styles per test pair (casual, SOP-imperative) drafted and self-reviewed
for numeric/threshold drift against the original description and query —
`data/processed/paraphrases_test.json`, all 15 clean. **Train-split pairs
have no paraphrase variants** — descoped given the volume (66 pairs × 2-3
styles) and that train-split paraphrasing doesn't feed final metrics the way
test-split paraphrasing does. `data/processed/pairs.jsonl` (the final
MASTER_PLAN §16.4-schema dataset file) has 111 records: 66 train (1 variant
each) + 15 test × 3 variants (original + casual + sop_imperative).

---

## 3. Phase 2 MVP — run, and it surfaced a major finding

Ran the full System B pipeline live (real Qwen3.5 calls, no mocking) on 10
hand-picked train-split cases across all 3 complexity tiers
(`data/processed/mvp_cases.json`, results in `mvp_results_0_10.json`).

**Result: 1/10 succeeded mechanically, and that one success was logically
wrong.** The IR Builder Agent (Qwen3.5 4B) filtered `ActorUserId in
("SUPERNOVA", "SUNBURST")` — treating malware family names as user IDs —
while correctly placing a file hash in the wrong field (`FilePath` instead
of `TargetFileMD5`/`TargetFileSHA1`). The other 9 hit
`MAX_REPAIR_ATTEMPTS_EXCEEDED`.

**Found and fixed one real, generic bug along the way:** the IR Builder /
Extraction / Monolithic agent prompts didn't explicitly distinguish "return
an instance of this schema" from "the schema itself" — on repair attempts,
the model sometimes echoed back the literal JSON Schema (`$defs`,
`properties`, `required` keys) instead of a filled-in object. Added an
explicit instruction to all three prompts; this is a real fix (every prompt
re-injects `format_instructions`, which *is* the schema), not case-specific
tuning.

**A second finding that is NOT a bug — it's the actual result:** after that
fix, the dominant remaining failure mode is the model emitting `"value":
null` for a filter it can't confidently fill, and critically, **emitting
the identical broken completion across all 3 repair attempts** — because
temperature=0 is deterministic and the model's confusion here is structural
(it doesn't know what literal value belongs there), not a one-off slip that
re-prompting fixes. This directly bears on **H3 (Repair Recovery Rate)**:
MASTER_PLAN's own falsification criterion for H3 is "Repair Recovery Rate is
below 50%" — this MVP sample is already trending that direction. This is a
clean, reportable, falsifiable result, not something to keep patching.

**Decision made here:** MASTER_PLAN §22 says not to touch the full dataset
until the MVP produces "sensible IRs and KQL on all 10 cases" — literally,
this MVP failed that gate. Proceeded to Phase 4 anyway, because (a) the
infrastructure-level bugs the MVP exists to catch *are* now fixed (no
crashes, no schema-echo, repair loop behaves correctly), and (b) MASTER_PLAN
also explicitly says "a clean negative... finding is a valid, reportable,
useful result" — a low success rate honestly measured and reported is a
complete answer to H1/H3, not a failed experiment. Flagging this judgment
call rather than silently overriding the documented gate.

---

## 4. Phase 4 (Qwen3.5, original run) — ⚠️ SUPERSEDED, kept for audit trail

**These numbers are now known to be substantially measuring a bug, not
model capability or IR-mediation viability.** §1.4 item 14 (found
2026-06-23) shows `repair_loop.py` was handing the IR Builder an empty ASIM
field list on effectively every call — for both models, throughout the
entire study — accidentally reproducing the "No Schema Grounding" ablation
on the main path. Kept below verbatim as the historical record of what was
actually run and reported at the time; **do not cite the H1/H2/H3/H4
conclusions in this section** — see §4B for the corrected re-run.

## 4. Phase 4 — primary comparison complete, real results

`eval/run_comparison.py` ran clean against all 15 test cases × 3 paraphrase
variants (45 test records). **Found and fixed one more critical bug getting
here**: the first run crashed entirely (zero results saved) because a single
Extraction Agent output that failed Pydantic validation (model returned a
list where `threshold_language` expects a string) propagated as an uncaught
exception and killed the whole batch — a generic eval-harness robustness
gap, not specific to this case. Added per-case try/except + incremental
writes to both `run_comparison.py` and `run_ablations.py`; re-ran clean.

### Headline results (n=45, no-output counted as failure)

| Metric | System A (direct) | System B (IR-mediated) | McNemar p |
|---|---|---|---|
| SVR | **95.6%** [89–100%] | **20.0%** [9–33%] | p≈1.5e-8 |
| FVR | **20.0%** [9–33%] | **13.3%** [4–24%] | p≈0.58 |

**FVR numbers were corrected mid-analysis** — `eval/metrics.py`'s
`field_validity_rate` originally *excluded* the source-table reference from
validation entirely (only checked field names), even though MASTER_PLAN's
own FVR definition explicitly says "every referenced **field/table**". This
let System A outputs referencing completely fictional tables
(`_Im_ServerError()`, `_Im_HttpStatusCode()`, `_Im_Http()` — none exist in
ASIM) pass FVR. Caught during manual Logic Correctness scoring below, fixed
(`is_valid_asim_table()` added, checked against all 7 event types' real
naming patterns), regression-tested. System A's FVR dropped from 31.1% to
20.0% as a direct result — a third of its earlier "passes" were hallucinated
tables. **System B never hallucinates a table** (its table name is always
derived deterministically from the validated IR's `event_type`, not
generated freely) — this is a genuine, structural advantage of IR-mediation
the corrected numbers now show clearly, even though it doesn't show up as a
statistically significant FVR difference at n=45 (CIs overlap, p≈0.58).

**SVR result inverts H1's predicted direction.** H1 expected System B's SVR
to materially exceed System A's (≥90% vs. 55–75%) because deterministic
templates can't emit invalid syntax. That mechanism is confirmed *for the
subset where System B completes at all* — SVR is 100% conditional on
producing output — but System B only produces output for 9/45 (20%) cases,
because the repair loop exhausts its 3 attempts on the other 36. Counting
non-completion as failure (the only fair way to compare, since a SOC analyst
needs *a* query, not a 20% chance of one), System A's naive single-shot
approach is **more usable overall** at this model scale, despite
hallucinating fields/tables in 80% of its output.

### Logic Correctness — the most severe finding, and the reason this metric exists

Scored all 15 queries that passed **both** SVR and the corrected FVR (9
System A + 6 System B) against the 3-point rubric (event type/table correct,
comparison direction not inverted, aggregation/grouping matches intent — all
three required to pass):

**Logic Correctness = 2/15 = 13.3%.**

Representative failures even among the "sound" subset: a System A query for
SMB-traffic deviation computed `avg(DstPortNumber)` — averaging the port
*number itself*, not connection counts, a meaningless calculation that
happens to be syntactically and field-wise valid. A System B query intended
to detect single-file-domain beaconing produced `dcount()` with no argument
(would not actually execute) on a table that was at least the right type. A
System A query for the "top 25 clients with most errors" silently narrowed
to NXDOMAIN-only instead of all error codes the description asked for.
**This is precisely the gap SVR/FVR cannot see and Logic Correctness exists
to catch** — confirms MASTER_PLAN's own design rationale for keeping it a
separate, manual metric rather than folding it into the automated ones.

### H3 (Repair Recovery Rate) — falsified clearly

**0/45 cases succeeded on the first IR Builder attempt. RRR = 9/45 = 20.0%**
— well below MASTER_PLAN's own stated falsification threshold ("RRR below
50%"). The repair loop's structured-error feedback essentially doesn't help
this model: the dominant failure (`filter.value: null`) is deterministic at
temperature=0 and reflects the model not knowing what value belongs in a
field, not a one-off slip a re-prompt fixes — confirmed directly in the
comparison log (identical broken completions repeated verbatim across
attempts 1–3 on multiple cases).

### H4 (complexity scaling) — not supported in this sample

System B success by complexity tier: simple 22% (2/9), moderate 22% (2/9),
complex 19% (5/27) — flat, not widening. Sample sizes per tier (9/9/27) are
small enough that this is suggestive, not conclusive, but there's no visible
trend toward H4's predicted "gap widens with complexity."

### Honest framing for the write-up

This is a complete, statistically-treated, **negative-for-H1/H3, mixed-for-H2**
result at this specific model scale (Qwen3.5 4B/2B, local, temperature=0).
MASTER_PLAN explicitly anticipates and endorses this kind of outcome ("a
clean negative or mixed finding... is a valid, reportable, and useful
result") — the honest conclusion from this run is closer to *"schema
grounding helps field validity when the IR Builder successfully converges,
but at this model scale convergence itself is the bottleneck, and the
repair mechanism doesn't meaningfully improve convergence"* than to the
hoped-for "IR-mediation strictly dominates." Whether a stronger model
changes this is the open question in §7.

### Ablations — complete, and they cleanly attribute the result

| Ablation | Configuration | Result (n=45) |
|---|---|---|
| 1. No-Repair | `max_attempts=1` | **0.0% success** (0/45) |
| 2. Monolithic Extraction | Extraction+IR-build merged into one call | **22.2% IR-valid** (10/45), 17/45 hard crashes |
| 3. No Schema Grounding | IR Builder gets no ASIM field list | **0.0% IR-valid** (0/45), 19/45 hard crashes |

**Ablation 1 reveals that 100% of System B's nonzero success (20%) comes
from the repair loop** — with repair disabled, success is exactly zero,
because (confirmed earlier) all 45 cases failed on the very first IR Builder
attempt. This also means **H1's premise is doubly falsified**: not only
does System B's overall completion rate trail System A's, the IR-mediation
approach has *zero* advantage independent of repair at this model scale —
contradicting H1's ablation expectation that "No-Repair IR should still
outperform System A... by a smaller margin."

**Ablation 2 (RQ2 — does decomposition help) is a clean null result**:
monolithic single-call extraction (22.2%) performs statistically
indistinguishably from the full two-agent decomposed pipeline (20.0%) at
this sample size — decomposing extraction from IR-building doesn't
measurably help here. (It does crash harder and more often, 17/45 vs 1/45,
since the merged agent has no separate extraction-stage error surface to
catch issues before they reach IR construction — but ultimately reaches a
similar "did we get a valid IR" rate.)

**Ablation 3 (H2's core mechanism) is the cleanest, strongest result of the
three**: removing the ASIM field reference doesn't just hurt — it craters
success to absolute zero with the highest crash rate of any condition
(19/45). This is strong, clean evidence that schema grounding is doing real,
necessary work, even though the *full* System B (with grounding) still only
reaches 20% — i.e., grounding is necessary but nowhere near sufficient at
this model scale.

---

## 4B. Phase 4 re-run (gpt-4.1-mini, post-bugfix) — current, trustworthy numbers

Re-ran Phase 4 comparison + all 3 ablations on the same 45-record test set
(15 pairs × 3 paraphrase styles) on **gpt-4.1-mini via Azure AI Foundry**
(`LLM_PROVIDER=azure_foundry`, `.env`/`.env.example` document the setup),
across **two rounds**: round 1 fixed §1.4 items 14–15 (schema-grounding
empty-list fallback, threshold-without-aggregation); round 2 added item 16
(degenerate-threshold validator, below) plus IR-Builder/Monolithic prompt
guidance targeting three specific Logic Correctness failure patterns found
by inspection. **Numbers below are round 2 (current).** Qwen3.5's full
45-pair eval was **not** re-run — a 10-case MVP re-test with round 1's fix
only reached 1/10 (see below), judged conclusive enough not to spend the
time on a full re-run unlikely to change the headline conclusion.

### Qwen3.5 MVP re-test (10 cases, round-1 fix) — confirms this wasn't all the bug

| | Before fix | After fix |
|---|---|---|
| gpt-4.1-mini | 0/10 | **8/10** |
| Qwen3.5 4B/2B | (not isolated) | **1/10** |

Qwen3.5's dominant failure mode is unchanged by the fix — still
`filters[i].value: null` on uncertain values. Once schema grounding actually
works for both models, the capability gap between Qwen3.5 4B/2B and
gpt-4.1-mini on this task is real and stark, not an artifact of the bug.

16. **`ir_validator.py` degenerate-threshold gap (found 2026-06-23, same
    session)** — `count`/`distinct_count` aggregations can never be `< 1`
    for a group that exists in the summarize result at all, so a `GT`
    threshold `< 1` or `GTE` threshold `<= 1` (e.g. `DistinctUserAgents > 1`,
    `ErrorCount >= 1`) is trivially true and filters nothing — observed live
    on multiple gpt-4.1-mini outputs. **Fixed**: new hard
    `DEGENERATE_THRESHOLD` validation error, same pattern as items 4/15.
    Paired with new IR-Builder/Monolithic-agent prompt guidance (literal-value
    discipline, event-type disambiguation by keyword, non-degenerate
    thresholds) targeting the three failure patterns found by manually
    inspecting the round-1 Logic Correctness failures.

### Headline results (n=45, no-output counted as failure)

| Metric | System A (direct) | System B (IR-mediated) | McNemar p |
|---|---|---|---|
| SVR | 100.0% [100,100]% | **81.7%** [71,93]% | p≈7.8e-3 |
| FVR | 8.9% [2,18]% | **68.9%** [56,82]% | p≈3.0e-6 |

Both metrics improved further from round 1 (SVR 68.9%→81.7%, FVR 55.6%→68.9%)
from the degenerate-threshold fix and prompt guidance alone — no model or
architecture change. **H2 is now supported even more strongly**: System B's
FVR is nearly 8× System A's, McNemar contingency 29-vs-2 in System B's favor.

### H3 (Repair Recovery Rate) — supported, now with a wider margin

**System B completion: 37/45 = 81.7%. 0/45 converged on attempt 1 (still —
temperature=0); of the 31 cases that failed on attempt 1, 23 were recovered
by attempt ≤3: RRR = 23/31 = 74.2%**, well above the 50% pre-registered
threshold (round 1: 56.2%).

### H4 (complexity scaling)

| Tier | n | System B success |
|---|---|---|
| Simple | 9 | 100% (9/9) |
| Moderate | 9 | 67% (6/9) |
| Complex | 27 | 82% (22/27) |

Closer to monotonic than round 1 (was 100/33/70) but still not clean — n=9
on moderate keeps this in "suggestive" territory.

### Ablations (re-run with round-2 fixes)

| Ablation | Result (n=45) | Interpretation |
|---|---|---|
| 1. No-Repair (`max_attempts=1`) | 31.1% success (14/45) | Repair loop still adds substantial value (81.7% vs 31.1%) but first-attempt capability keeps climbing too. |
| 2. Monolithic Extraction | 31.1% IR-valid (14/45) | Stayed flat round-1→round-2 while the full pipeline kept climbing — decomposition's advantage is now larger (81.7% vs 31.1%) than in round 1. |
| 3. No Schema Grounding | 2.2% IR-valid (1/45) | Unchanged — still craters near-zero, confirms grounding's necessity is independent of the prompt/validator improvements. |

### Logic Correctness — stratified by IR expressibility, the real finding

**`SecurityIR.filters` is a flat AND-only list** — no OR composition, no
joins, no multi-stage baseline-vs-current aggregation. Checked the ground
truth directly: **24/45 (53%)** of the test set needs at least one of those
constructs, which the IR architecturally cannot represent regardless of
model or prompt. Splitting completion rate by this line:

| | Completion rate |
|---|---|
| IR-expressible (21/45) | 90.5%→ still ~86% |
| Needs join/OR/multi-stage agg (24/45) | climbed 50%→79% (this round) — see caveat below |

The out-of-scope completion rate climbing to 79% does **not** mean those
detections became correct — it means the model now reliably produces a
schema-valid *single-event simplification* that drops the unsupported part
of the logic (the join, the OR-group, the baseline comparison). Completion
rate is the wrong metric for this subset; Logic Correctness is what matters,
and was checked only on the in-scope subset for that reason.

**Manually scored all 18 in-scope (IR-expressible) successes against the
3-point rubric** (event type/table correct, comparison direction not
inverted, aggregation/grouping matches intent) — not a spot-check this time,
the full in-scope set:

**12/18 = 66.7%** — up from round 1's informal spot-check (~25%, n=12,
different/overlapping sample), purely from the degenerate-threshold fix and
prompt guidance. Still one rater, no second reviewer — see §5.

**The striking pattern: it's almost entirely explained by paraphrase style.**

| Paraphrase style | Logic Correctness |
|---|---|
| `sop` (imperative) | **6/6 = 100%** |
| `casual` | 4/6 = 66.7% |
| `original` (verbatim Microsoft-doc style) | 2/6 = 33.3% |

Every single SOP-imperative-paraphrased case scored correct; every single
remaining failure is an `original` or `casual` variant of the *same six*
underlying ground-truth pairs (`sdelete`, recycler-bin LOLBin abuse, DNS
error-rate, and a WebSession 5xx case) — the IR Builder gets these right
when the input is phrased as a direct, structured imperative, and gets them
wrong (wrong event type, inverted logic, or a hallucinated literal value
like a fabricated absolute date) when the input is verbose/naturalistic.
This is a new, distinct, well-evidenced lever, independent of model choice
or IR expressiveness — see §7 for the proposed experiment (normalize NL
phrasing before extraction).

**Conclusion: the SVR/FVR/RRR swing is real, and Logic Correctness moved
with it this time** (25%→67% on the appropriately-scoped subset), unlike
round 1 where the validity metrics improved but Logic Correctness didn't.
The remaining gap to 90%+ has two distinct, separately-addressable causes:
(a) IR expressiveness (53% of the dataset is structurally out of scope —
needs schema work, §7 item 5) and (b) paraphrase-style sensitivity within
the in-scope subset (now the dominant remaining cause of the 33% in-scope
failures — needs an NL-normalization experiment, not a schema change).
Automated validity is still not *proof* of correctness, but it is no longer
decoupled from it the way it was in round 1.

## 4C. `SecurityIR` OR-composition extension + 2 more bugs + a methodology finding

Acted on the two "what's left for 90%+" items from §4B: investigated the
NL-normalization hypothesis (it does **not** hold up — see below) and built
the OR-composition schema extension (it works — confirmed live).

**The paraphrase-style finding in §4B was wrong as stated — it's not style,
it's missing information.** Compared `original` vs `sop` text directly for
the 4 ground-truth pairs behind every in-scope failure, e.g.:

| Pair | `original` | `sop` |
|---|---|---|
| recycler | *"Identifies malware that has been hidden in the recycle bin."* | *"If a known LOLBin (cmd.exe, ftp.exe, ...) is executed with a command line referencing the recycler folder..."* |
| WebSession 5xx | *"...multiple server errors originate from a single source within a limited time frame."* | *"Within a 1-hour window, alert when a single source IP generates more than 100 HTTP 5xx..."* |

The `sop` paraphrase injects the LOLBin list, "HTTP 5xx", "100", "1-hour
window" — none of which are recoverable from `original` by reformatting.
These `original` descriptions are SOC-engineer doc-strings written assuming
the reader also sees the KQL; they are not self-contained specs. **A
phrasing-normalization step cannot fix missing information that was never
in the input — not built, for that reason.**

### `SecurityIR` extended: `FilterGroup` for OR-composition

Added a `FilterGroup` model (`type="group"`, `conditions: List[Filter]`,
min 2) alongside the existing `Filter`. `SecurityIR.filters` is now
`List[Union[Filter, FilterGroup]]` — each top-level item is still AND-ed
with the rest (unchanged), but a `FilterGroup` item OR-s its own conditions
together, rendering as a parenthesized KQL clause. Targets exactly the
`(A or B) and (C or D)` pattern a flat AND-only list couldn't express (12/45
ground-truth pairs need this). Added `FilterOperator.ENDSWITH` alongside it
(needed for the `/do`-or-`/domain`-style suffix checks in that same pattern).

**Confirmed working on the case it was built for** — `7b3ed03a-...-sop`
(a discovery-command rule) now renders
`(ActingProcessCommandLine contains "user" or ... contains "group")` AND
`(... contains "/do" or ... contains "/domain")`, an exact structural match
to the ground truth's nested boolean logic, which was simply impossible to
represent before this change (the old flat-AND-only IR could only flatten
it into "A and B and C and D" — a different, much narrower detection).

**Two more real bugs found getting this working:**

17. **Discriminated union required the `type` tag to be *present*, breaking
    the common case.** First implementation used
    `Field(discriminator="type")`. Pydantic's discriminated-union resolution
    needs the tag key actually present in the input dict to pick a union
    member — it does **not** fall back to a field's Python-level default
    when the tag is simply absent. Most models, writing an ordinary `Filter`
    that never needs `FilterGroup`, omit the optional `type` field entirely
    (it has a default, so they don't think to include it) — and every one
    of those now-common omissions failed to parse at all
    (`union_tag_not_found`). **Fixed**: switched to a plain
    `Union[Filter, FilterGroup]` (Pydantic v2's default "smart mode"), which
    matches structurally (does it have `conditions`? -> `FilterGroup`; does
    it have `field`/`operator`/`value`? -> `Filter`) and tolerates the tag
    being absent on either shape.
18. **`output_fields` was never validated against the schema — a
    pre-existing gap, not introduced today.** `validate_ir()` checked
    `filters` and `group_by` but not `output_fields`, so a hallucinated
    `"| project"` field (e.g. `ParentProcessCommandLine`,
    `DnsQueryTimeDelta` — plausible-sounding, not real ASIM fields) passed
    IR validation and was only ever caught downstream by
    `eval/metrics.py`'s text-level FVR check — meaning every completion-rate
    and FVR number reported in §4B was inflated by output-field hallucinations
    the validator silently let through. **Fixed**: added the same
    field-by-field check already used for `filters`/`group_by`.
19. **`kql_literal` did zero string escaping** — a filter value containing a
    literal backslash (a Windows path, or the literal special folder name
    `$Recycle.Bin`) produced malformed KQL like `"\$Recycle.Bin\"`, where
    the trailing backslash reads as escaping the closing quote rather than
    terminating the string. Found while diagnosing the FVR change, not
    related to the union work, but in the same code path. **Fixed**: escape
    backslash and double-quote before wrapping in quotes.

### Methodology finding: gpt-4.1-mini via Azure AI Foundry is not perfectly deterministic at temperature=0

Re-ran the *same* 16 failing cases through the *unchanged* pipeline moments
later — **6/16 succeeded** on the identical input with identical code.
Re-ran the full 45-pair comparison twice in a row after item 18's fix:
64.4% and 62.2% completion — consistent with each other, but **lower** than
the 81.7% measured in round 2 (§4B), before the `output_fields` gap was
closed. Per-case inspection: **18 of the post-fix failures are specifically
`output_fields`-related `FIELD_NOT_FOUND` errors** — confirming the drop is
mostly the new check correctly catching hallucinations the validator used
to miss, not a regression from the OR-group work. Unlike the local
Ollama/Qwen3.5 runs (deterministic by construction — single local instance,
temperature=0), **cloud-hosted gpt-4.1-mini gives different output on
identical input at temperature=0** — every single-run point estimate for
this model in this document, including round 2's, carries real,
now-measured noise (roughly 60-65% vs 82% range observed just from re-runs).
Treat any one number as a rough midpoint, not exact — and prefer the
post-item-18 measurements (~62-64%) as the more *honest* current estimate,
since round 2's higher numbers are now known to be partly inflated by the
output_fields gap.

**Current honest headline (n=45, average of two consecutive post-fix runs):
System B completion ≈63%, FVR ≈63% (output_fields-gap closed, so these are
now equal — every output_fields hallucination is caught at validation time
instead of leaking into FVR's separate, looser text-level check), RRR
≈52%.** Still clears H3's 50% threshold, just barely, and with more
day-to-day variance than the local Qwen3.5 numbers ever had.

65 unit tests passing (`pytest tests/unit -q`), including new coverage for
`FilterGroup` rendering and validation, union round-tripping with and
without the `type` tag present, `output_fields` validation, and
`kql_literal` escaping.

### What's still not done

**Join / multi-stage baseline-comparison support — not built.** This is the
other, larger half of the 53% IR-expressiveness gap (24/45 pairs); `FilterGroup`
only addressed the OR-composition portion (~12/45). A join/correlation
construct needs a different compiler template shape (two-stage query,
`let`-bound subquery, `join kind=inner`) and is a meaningfully bigger lift
than `FilterGroup` was — scoped but not started.

---

## 4D. Join/correlation support landed externally — audited, 6 bugs found and fixed

A `JoinStage` model, negated operators (`!contains`/`!startswith`/`!endswith`/
`!in`, plus `has`/`has_any`/`matches regex`), repair-loop temperature
escalation, and an automated `compute_summary()` (SVR/FVR/RRR/McNemar/CI) were
added to the codebase outside this session's own edits. Asked to verify
these against the same standard applied throughout this project — actually
running them, not trusting "95/95 tests pass" — and found that **three of
the five headline claims were severely broken**, one was simply false, and
the two real features (`JoinStage`, negated operators) had real but smaller
gaps. All confirmed by direct execution, then fixed with regression tests
(`pytest tests/unit -q`: 95 → 104).

**Severe — would have silently corrupted the next live evaluation run:**

20. **`compute_summary()`'s RRR was unconditionally 0.0%, always.**
    `attempt1_failures = [not success]` and `recovered = sum(failed and
    final_passes[i])` — but `final_passes[i]` *is* `success[i]`, so the
    condition is `(not success) and success`: always `False`. Verified with
    3 simulated repair-recovered cases out of 5 — printed `RRR: 0.0`.
    **Fixed**: derive "attempt 1 failure" from `not (success and
    attempts_used == 1)`, matching the definition used everywhere else in
    this project.
21. **Every join-based query registered FVR=0, regardless of correctness.**
    `eval/metrics.py`'s `extract_table_reference()` only skipped lines that
    themselves started with `"let NAME ="` — a multi-line let-bound
    subquery's continuation lines (`"| summarize ... by ..."`) aren't
    let-bindings themselves, so the first one was mistaken for the main
    query's table reference, didn't match (starts with `"|"`, not a table
    name), and returned `None` — making `field_validity_rate()` reject every
    join query outright. Confirmed by rendering a real join query through
    the actual function. **Fixed**: split on the last top-level `;` (KQL's
    statement separator — correctly skips any number of preceding `let`
    statements, scalar or multi-line tabular) and look for the table
    reference only in what follows.
22. **Temperature escalation fired on the very first repair attempt,
    always — not "when stuck repeating," as documented.** The comparison
    baseline (`prev_fingerprint`) was seeded from the pre-loop initial
    build, so the first loop iteration always compared that build's output
    to itself — trivially equal. Verified with two mocks: one that
    genuinely repeats forever, one that never repeats at all — both
    escalated to `temperature=0.3` on the first repair attempt. **Fixed**:
    don't seed a comparison baseline until there's a genuine prior *repair
    attempt* to compare against; escalate only on a real two-consecutive
    match.

**False claim:** *"The monolithic ablation script was fixed... a bug that
artificially suppressed its performance."* Checked: 0/111 dataset pairs have
an `asim_event_type` that fails to match the schema (it's a structured
dataset field, not free text like `repair_loop.py`'s genuinely-broken
`likely_event_type`). This "fix" has zero measurable effect on this
dataset — not wrong to have added, but the stated justification doesn't hold.

**Gaps found and fixed:**

23. `JoinStage` aggregations had no time-bound requirement — confirmed an
    aggregation with `time_window=None` passed validation, the exact
    "scans the entire table" problem `MISSING_TIME_WINDOW` exists to
    prevent for the main IR. Mirrored the check onto the join stage.
24. `!has` was missing from the negated operators — the actual sdelete
    ground-truth case this session found earlier needs
    `CommandLine !has "sdelete"` specifically. Added `NOT_HAS`.
25. The join clause rendered with zero separation from the preceding line
    (`"...bin(TimeGenerated, 1h)| join kind=inner..."`) — a chain of
    tag-only template lines (an `{% endif %}`, an absent `{% if threshold
    %}` block, another `{% if %}`) each trimmed their own trailing newline
    with nothing left to contribute one. Moved the `by`-clause `{% endif
    %}` onto its own template line so it keeps its newline.

**Untested before this audit:** zero tests exercised temperature escalation
specifically, and none ran a `JoinStage`-containing IR through
`eval/metrics.py` or `compute_summary()` — exactly the two paths that were
broken. New tests for both are in `test_repair_loop.py`, `test_metrics.py`,
and the new `test_run_comparison.py`.

**Verified end-to-end after all fixes**: a join-using IR that fails attempt
1 and recovers on repair now correctly compiles, passes SVR/FVR, and reports
`RRR: 1.0` through the exact same `compute_summary()` path `run_comparison.py`
uses. The join feature is now believed correct; it has **not** yet been run
against a live model (no fresh Phase 4 eval with joins has happened) — that
re-run is the natural next step, not yet done.

---

## 4E. Baseline-vs-current architecture fix, 3 more bugs, and the actual fresh Phase 4 re-run

§4D's audit left `JoinStage` mechanically correct but architecturally
incomplete for its single most valuable use case. Live-testing it
(`8717e498-...`, an SMB connection-count-vs-14-day-baseline detection)
confirmed exactly the gap flagged at the end of §4D: the compiled KQL
joined the baseline correctly, then thresholded the *current* count
against a bare literal — the joined `BaselineAvg` column was projected for
display but never gated the alert, because `Threshold` had no way to
reference a joined column at all.

### The fix: `Threshold.compare_to_join_field`

Added an optional field to `Threshold`: when set, it must name the join
stage's own `aggregation.result_alias` exactly (validated — wrong name or a
join with no aggregation is a hard `INVALID_THRESHOLD_JOIN_REFERENCE`
error). The compiler renders `{current} {operator} {compare_to_join_field}
+ {value}` instead of `{current} {operator} {value}`, and — required for
this to even be possible — **the join clause was moved to render before
the threshold clause** (it previously came after, so the joined column
wasn't in scope yet regardless of what the threshold said). Confirmed live:
the reconstructed SMB-baseline case now compiles to
`CurrentCount > BaselineAvg + 50` — an exact semantic match to "current
exceeds the 14-day baseline by more than 50," structurally impossible
before this fix.

### 3 more bugs found getting this verified live, not in isolated unit tests

26. **`output_fields` validation (§1.4 item 18, this session's own earlier
    fix) didn't recognize an aggregation's own alias.** A completely
    standard query — `summarize FailCount = count() by X | project X,
    FailCount` — was rejected as `FIELD_NOT_FOUND` because `FailCount` is a
    self-defined column, not a schema field, and the check didn't know
    that category existed. This is *why* `8717e498` failed validation
    repeatedly before this fix. **Fixed**: exclude the main
    `aggregation.result_alias` and (when present) `join.aggregation.result_alias`
    from the output_fields schema check.
27. **A self-inflicted regression**: the new prompt guidance text written
    for `compare_to_join_field` contained literal curly braces —
    `"renders as "{current} {operator} {baseline column} + {margin}""` —
    which `ChatPromptTemplate` parses as template variables, not prose.
    Every single System B call crashed (`missing variables`) the first
    time the new prompt was used live; a 45-pair comparison run returned
    0% across every metric before this was caught and the sentence
    rewritten without braces.
28. **`eval/run_comparison.py`'s `from .metrics import ...` (added in §4D's
    external changes) was a relative import**, which breaks this
    project's established direct-script invocation (`python
    eval/run_comparison.py`, used dozens of times this session) — it only
    works via `python -m eval.run_comparison`. Changed to an absolute
    import (`from eval.metrics import ...`), consistent with every other
    import in the file.
29. **`avg()`/`sum()`/`min()`/`max()`/`dcount()` with no field passed
    validation.** Only `count()` takes zero arguments in KQL; the live
    SMB-baseline IR set `aggregation.field=None` for an `avg` aggregation,
    which rendered as the invalid `summarize BaselineAvg = avg()`. **Fixed**:
    new `AGGREGATION_MISSING_FIELD` hard error for any aggregation function
    other than `count`, applied to both the main IR and the join stage.

112 unit tests passing (`pytest tests/unit -q`), up from 95 at the start of
this section.

### Fresh Phase 4 re-run — the numbers this was all building toward

Re-ran `eval/run_comparison.py` and `eval/run_ablations.py` against
`gpt-4.1-mini` with every fix above in place. Two consecutive comparison
runs landed within 2 points of each other (75.6% completion/FVR both
times) — treated as the current, more stable estimate, replacing §4C's
wider 62–84% spread.

| Metric | §4C (before this section) | §4E (after) |
|---|---|---|
| System A SVR | 100.0% | 97.8–100.0% (run-to-run noise, unrelated to anything changed here) |
| System A FVR | ~9–11% | 8.9% |
| **System B completion/SVR** | ~62–64% (single/double-run estimate) | **75.6%** (stable across 2 runs) |
| **System B FVR** | ~62–64% | **75.6%** |
| **RRR** | ~47–57% (noisy) | **70.3–72.5%** |
| H4 (simple/moderate/complex) | 100% / 0–78% / 67–82% | 100% / 67–78% / 67–70% — still not monotonic, but moderate's volatility narrowed |
| Ablation: No-Repair | ~24–31% | 15.6% (7/45) — *lower* than before: the richer schema (FilterGroup, JoinStage, more operators) gives the model more ways to make a first-attempt structural mistake, but... |
| Ablation: Monolithic Extraction | ~24–31% | 26.7% (12/45) — essentially unchanged |
| Ablation: No Schema Grounding | 0.0% | 0.0% — unchanged, still the cleanest, most stable result in the whole study |
| McNemar FVR | p≈3e-6, b_only=29 | **p≈1.2e-7, a_only=0, b_only=30** — System A does not win a single FVR comparison in this run |

**The repair loop is doing more work, and doing it better.** No-Repair
dropping to 15.6% while completion *rose* to 75.6% means RRR (70–72%) is
now carrying noticeably more of System B's success than before — a richer,
more expressive schema is harder to get right in one shot, but the
validator fixes from §4D/§4E give the repair loop sharper, more specific
errors to correct against, and it's converting that into a higher net
completion rate than the simpler schema ever reached.

**Logic Correctness, re-scored on this run's in-scope subset (19 cases,
up from 15 — `FilterGroup`/`JoinStage` cases stay excluded from this
rubric for the same reason as §4B/§4C: scoring a detection against a
rubric the IR can't structurally satisfy measures gracefulness of failure,
not correctness): 10/19 ≈ 52.6%.** Within noise of §4C's 60% (9/15) — none
of this section's fixes targeted the simple in-scope cases (recycler,
sdelete, rundll32, DNS error-rate, WebSession error-rate) directly, so the
difference is attributable to gpt-4.1-mini's already-documented run-to-run
variance, not a regression. Still one rater, single pass — §5's
second-reviewer item is unchanged and still the top priority.

**The qualitative win this section was built around**: of the 24
out-of-scope (join/OR/multi-stage) ground-truth pairs, only 2 of this run's
successes actually *use* a join (most out-of-scope successes are still
single-event simplifications, as in §4C) — but both of those 2 are now
genuinely, semantically correct baseline-vs-current detections, which was
*structurally impossible* to produce correctly before this section's fix
regardless of model capability or prompting.

---

## 4F. Prompt-level fixes targeting the specific failure patterns §4E found — the biggest single jump in the study

§4E ended by asking "what would it take to get toward 95%+ accuracy?" The
answer split into things needing new code (architecture, §4E) and things
needing better prompting of the model that already has the right tools.
This section is the second half: three targeted prompt/logic changes, no
new IR constructs, aimed directly at the specific live failures §4B–§4E
accumulated evidence for.

### What changed

1. **Worked example for `compare_to_join_field`**, added to both
   `ir_builder_agent.py` and `monolithic_agent.py` — described in prose,
   not literal JSON (see item 30 below for why). §4E's own data showed the
   join construct exists and validates correctly but the model rarely
   reached for it (2/24 out-of-scope successes used a join); a concrete
   worked example, not just a prose rule, is the standard fix for a model
   underusing an unfamiliar construct.
2. **Event-type disambiguation rewritten with the exact confusions found
   live**, not generic categories: "recycle bin"/file-themed wording but
   the technique is process execution → `ProcessEvent`, not `FileEvent`;
   DNS-themed wording → `DnsEvent`, not `NetworkSessionEvent`; HTTP/web
   wording → `WebSessionEvent`, not `NetworkSessionEvent`. These three
   exact mistakes were directly observed and scored as Logic Correctness
   failures across §4B–§4E.
3. **New `_check_constraint_traceability` check in `repair_loop.py`**
   (deliberately *not* in `ir_validator.py` — it needs both the
   `ExtractionOutput` and the built `SecurityIR` together, which only the
   repair loop has in scope). Schema validation confirms field/value
   *shapes* are valid; it cannot catch a threshold that silently drifted
   from what the description specified (e.g. NL says "more than 50",
   IR says `threshold.value=1` — both perfectly schema-valid, the
   recurring "weak threshold" Logic Correctness failure found repeatedly
   in §4B–§4E). Deliberately conservative: only fires when the extracted
   `threshold_language` contains **exactly one** number — multi-number
   phrases ("more than 50 connections over 14 days" has both a margin and
   a lookback window) are skipped rather than risk flagging the wrong one.

### Bug #30, caught before it shipped this time

Item 27 (§4E) was a self-inflicted prompt crash from literal curly braces
in new guidance text. Having learned that lesson, item 1 above was written
entirely in prose — no literal JSON example with braces — and verified
against `ChatPromptTemplate(...).input_variables` immediately after
writing it, before running anything live. Confirmed clean both times
(`ir_builder_agent.py` and `monolithic_agent.py`). No repeat this round.

### Live results — the largest single jump in this study

| Metric | §4E (before this section) | §4F (after) |
|---|---|---|
| **System B completion/SVR** | 75.6% (stable, 2 runs) | **88.9–91.1%** (stable, 2 runs) |
| **System B FVR** | 75.6% | **88.9–91.1%** |
| **RRR** | 70.3–72.5% | **80.8–82.6%** |
| SVR McNemar | p≈0.002 (A_only=11) | **p≈0.13–0.22 — no longer statistically significant**: System B's completion rate is now indistinguishable from System A's at n=45 |
| FVR McNemar | a_only=0, b_only=30 | a_only=0, b_only≈29 — still total dominance |
| **Ablation: No-Repair** | 15.6% (7/45) | **51.1% (23/45)** |
| **Ablation: Monolithic Extraction** | 26.7% (12/45) | **68.9% (31/45)** |
| Ablation: No Schema Grounding | 0.0% | **0.0% — unchanged across every single round of this study** |
| Out-of-scope successes using a real join | 2/20 | **4/20** |
| Logic Correctness (in-scope) | 10/19 ≈ 52.6% | **12/20 = 60%**, full re-score, not a spot-check |

**No-Repair jumping from 15.6% to 51.1% is the single most important number
here.** It means the prompt fixes didn't just give the repair loop better
material to correct against — they made the model substantially more
likely to get the IR right on the *first* attempt, before any repair
machinery runs at all. The Monolithic ablation jumping similarly (26.7%→68.9%)
confirms this is a prompt-quality effect, not something specific to the
decomposed pipeline: both agents got the same guidance, both improved
similarly. **No Schema Grounding stayed at exactly 0.0% through every
single round of this entire study** — the cleanest, most reproducible
result here, completely unmoved by every other change.

### Logic Correctness in detail — real, partial, honestly mixed

Re-scored all 20 in-scope successes against the same 3-point rubric.
Checked the 3 *specific* confusions item 2 above targeted, against the
exact ground-truth pairs that failed on them in §4E:

| Case | §4E (before) | §4F (after) |
|---|---|---|
| Recycle-bin LOLBin detection | `imFileEvent` (wrong) | `imProcessCreate` (correct) on 2/3 paraphrases — field/content still imperfect on the third |
| HTTP 5xx error-rate detection | `imNetworkSession` (wrong) | `imWebSession` (correct) on all 3 paraphrases, now passing cleanly |
| DNS error-rate detection | `imNetworkSession` (wrong) | **still `imNetworkSession`/wrong on the `-original` paraphrase** — this specific confusion did not resolve |

2 of 3 targeted confusions measurably improved; one did not. The recurring
sdelete-evasion inverted-logic failure (requiring "sdelete" present when
the ground truth requires its *absence* — a renamed-binary evasion case)
also did **not** resolve despite explicit "read carefully which side is
negated" guidance added this round — inverted boolean logic appears to be
a harder class of mistake for this model than wrong-event-type selection.
Prompting is a real lever, proven by 2/3, but not a complete fix for every
failure pattern this study has catalogued.

### What's still open

- The percentile/statistical-aggregation gap (flagged at the end of §4E's
  "what would 95% take" discussion) is real and unaddressed — live-tested
  this round (`4e3af8e3`, a 5th-percentile process-frequency detection):
  the model substituted `min(ActingProcessCreationTime)` — a timestamp,
  not a percentile — for a statistic the IR has no way to express. Schema
  extension, not a prompt fix.
- The constraint-traceability check's real-world hit rate is still
  unmeasured directly — it's deliberately conservative (single
  unambiguous number only) and at least one live weak-threshold case
  (`813ccf3b-original`, threshold 1 vs. ground truth's 5) still slipped
  through, consistent with the conservative design but not yet validated
  against how often it correctly fires vs. how often it should but can't.
- Logic Correctness is still one rater, no second reviewer — unchanged,
  still the top item in §5.

112 unit tests at the start of this section grew to 121 (new
`test_constraint_traceability.py` plus repair-loop integration coverage);
all passing.

---

## 4G. Two more targeted worked examples — the recurring sdelete bug fully resolved

§4F's own data named two specific, still-unresolved failure patterns: the
sdelete renamed-binary evasion case (inverted logic, present since §4B)
and over-specific `group_by` (extra keys narrowing the aggregation, seen
in `43c2832e-sop` repeatedly). Same technique that worked for
`compare_to_join_field` in §4F — a concrete worked example, not just a
prose rule — applied to both.

### What changed

1. **Worked example for disguised/renamed-tool detection**, added to both
   agent prompts: require the tool's distinctive flags (the actual
   evidence) AND explicitly exclude the cases where the process name
   *does* reveal the tool (`!endswith`/`!=` on the name, `!has`/`!contains`
   on the command line) — spelling out that there is *no* filter requiring
   the tool's name to be present anywhere, since that's the opposite of
   detecting evasion.
2. **Explicit anti-over-grouping guidance**: `group_by` should include
   only the key(s) the description explicitly needs broken down by —
   almost always just the source/actor identifier — because every extra
   key splits one intended group into many smaller ones, silently raising
   the bar a threshold needs to clear.

Both written entirely in prose, no literal JSON with braces — verified
against `ChatPromptTemplate(...).input_variables` before running anything
live, the same discipline that caught §4E's curly-brace crash before it
could repeat. Clean both times.

### Results — the sdelete fix is a complete, clean win

| Case | §4F | §4G |
|---|---|---|
| sdelete evasion (`5b6ae038`, all 3 paraphrases) | 1/3 correct (only `-sop`) | **3/3 correct** — every paraphrase now renders the exact right pattern: the four flags AND-ed via `has`, plus `ActingProcessName !endswith "sdelete.exe"` |
| Over-grouping (`43c2832e`, all 3 paraphrases) | 2/3 clean | 2/3 clean — `-sop` still adds `DstUsername, SrcHostname` beyond `SrcIpAddr`; unchanged |

| Metric | §4F | §4G |
|---|---|---|
| System B completion/FVR | 88.9–91.1% | 91.1% (consistent, third run in this range) |
| RRR | 80.8–82.6% | 81.0% |
| No-Repair ablation | 51.1% | 46.7% (within run-to-run noise of §4F, not a regression) |
| Monolithic ablation | 68.9% | 68.9% (identical) |
| No Schema Grounding | 0.0% | 0.0% — unchanged in **every round of this entire study**, the one truly stable result |
| **Logic Correctness (in-scope, full re-score)** | 12/20 = 60% | **14/20 = 70%** |

The completion/FVR/RRR numbers held flat — expected, since these two
fixes target *logical correctness* of already-completing cases, not
completion itself. Logic Correctness is where the effect shows: 60%→70%,
with the gain traceable to a specific, named fix (sdelete) rather than
general noise, which is the strongest evidence yet in this study that a
Logic Correctness number actually moved for an identifiable reason.

### What's still open

- The DNS-error event-type confusion (`b35f6633-original`/`-casual`) is
  still unresolved — `-original`'s NL ("the top 25 clients with the most
  errors") doesn't mention DNS at all, which is the same missing-information
  ceiling identified in §4C, not a prompting problem. `-casual` now
  correctly picks `DnsEvent` but drops the actual error-condition filter
  (counts all DNS events, not just non-NOERROR ones) — a different,
  not-yet-targeted mistake.
- `43c2832e-sop`'s over-grouping is a partial fix (2/3), not complete —
  unclear from this sample alone whether more explicit examples would
  close the last paraphrase or whether this is genuine model
  inconsistency across rephrasing of the same intent.
- Weak/wrong threshold magnitudes that the conservative
  constraint-traceability check doesn't catch (multi-number or no-clean-number
  descriptions) are still visible (`813ccf3b-original`, `a59ba76c-original`)
  — the check's conservatism is a deliberate tradeoff, not a bug, but it
  means roughly half the threshold-magnitude failures in this dataset are
  still unprotected.
- Percentile/statistical aggregation support — still not started (§5 item 7).
- Logic Correctness: still one rater, no second reviewer — four rounds of
  re-scoring now (60%, 52.6%, 60%, 70%), still without independent
  verification.

121 unit tests, unchanged from §4F (this round needed no new validator
logic, only prompt text) — `pytest tests/unit -q` still green.

---

## 4H. Two real bug fixes, a genuine schema extension, and a self-inflicted bug found mid-round — the highest completion rate of the study

Picking up §4G's two named, addressable gaps (`b35f6633-casual`'s missing
DNS error filter, `43c2832e-sop`'s grouping mismatch) plus the percentile
architecture gap flagged back in §4E. Checking the actual NL text behind
both named gaps first changed the diagnosis from what §4G assumed:

- **`43c2832e-sop` was never "over-grouping."** Its `sop_imperative`
  phrasing explicitly says "a single source IP/user/host combination,"
  and the ground truth groups by all four of `SrcIpAddr, SrcUsername,
  SrcHostname, DstIpAddr` — the real bug is the model emitting
  `DstUsername` instead of `SrcUsername` for an actor the description
  calls a "source." A Src*/Dst* directional mix-up, not a key-count
  problem.
- **`b35f6633-casual`** correctly picks `DnsEvent` (§4F's fix held) but
  never adds the field+value that actually encodes "error" for DNS
  (`DnsResponseCodeName != "NOERROR"`) — picking the right event type
  doesn't automatically cover the outcome condition.

### What changed

1. Guidance distinguishing Src*/Dst* field selection by which entity the
   description is actually about (the initiator vs. the target), with an
   explicit carve-out: when several attributes describe one actor
   together ("source IP/user/host combination"), they all take the same
   prefix and `group_by` must include all of them — the §4G anti-over-
   grouping rule was never actually in tension with this, but the carve-out
   makes it explicit.
2. Guidance tying vague outcome words ("error", "failure", "denied") to
   the event type's *actual* result-encoding field, with the DNS case as
   the concrete worked instance — event_type alone was never sufficient.
3. **A genuine schema extension**: `AggregationFunction.PERCENTILE` plus
   `Aggregation.percentile` (the Nth percentile, 0–100), a
   `kql_agg_call` Jinja filter (percentile's KQL syntax takes a field
   *and* a percentile value — every other supported function takes zero
   or one), and a new validator check (`INVALID_PERCENTILE_VALUE`) mirrored
   for both the main aggregation and the join stage's. This is the first
   capability addition in the study that's a genuinely new statistical
   primitive, not a logic-operator or correlation construct.

### A self-inflicted bug, found mid-round, that turned out to matter the most

Live-testing surfaced 3 cases rendering AND-required multi-flag conditions
as an OR'd FilterGroup instead — e.g. the sdelete detection's four
required command-line flags wrapped in `(has "-s" or has "-r" or ...)`,
which would also fire on any ONE flag alone. Tracing it: §4G's own
disguised-tool-evasion worked example said "specific command-line flags
used together — **has_all-style**" — meant as a descriptive analogy, but
the model was reading "has_all" as a literal, invented operator name (it
doesn't exist in `FilterOperator`), failing Pydantic parsing, and
recovering inconsistently across repair attempts — sometimes landing on
the correct AND form, sometimes on the wrong OR form. This is the same
class of self-inflicted mistake as §4E's curly-brace crash: descriptive
prose that reads as literal syntax. Fixed by rewriting the example to
explicitly name "has", state there is no "has_all", and explicitly rule
out FilterGroup for this case (FilterGroup is OR; these flags are
required together). Confirmed live: 6/6 standalone re-runs of the two
previously-flakiest cases rendered correctly afterward, where 3 separate
full comparison runs before the fix had shown the same 2-3 cases flipping
between correct-AND and wrong-OR from run to run.

### Live results

| Metric | §4G | §4H |
|---|---|---|
| System B completion/SVR | 91.1% | **93.3% — highest of the entire study** |
| FVR | 91.1% | 88.9% |
| RRR | 81.0% | **88.5%** |
| Logic Correctness (in-scope, full re-score) | 14/20 = 70% | **15/20 = 75%** |
| No-Repair ablation | 46.7% | 48.9% |
| Monolithic ablation | 68.9% | 66.7% |
| No Schema Grounding ablation | 0.0% (every prior round) | **6.7% (3/45) — first non-zero result of the study** |

Three runs were needed to separate signal from gpt-4.1-mini's
documented non-determinism before reaching this: 91.1% → 84.4% → 86.7%
(pre-fix, visibly noisier than §4G's tight 89–91% cluster — consistent
with the `has_all` bug actively present) → 93.3% (post-fix, in one run).

Of the 5 remaining in-scope Logic Correctness failures, 4 are the
already-documented `-original`-paraphrase missing-information ceiling
(§4C/§4G) — `b35f6633`, `a59ba76c`, `813ccf3b`, and now also `61988db3`
all confirmed by reading the actual NL text, which genuinely omits the
technique/number in question. Only 1 (`61988db3-sop`) is a real,
addressable miss — a residual recurrence of the FilterGroup/OR confusion,
down from 3 occurrences in the pre-fix runs to 1.

### The No-Schema-Grounding ablation's first-ever non-zero result — traced, not hidden

3/45 cases now pass with zero schema grounding, where every prior round
of this entire study landed at exactly 0.0%. Checked all three directly:
one (`b35f6633-sop`) uses `DnsResponseCodeName` — the literal field name
from this round's new DNS worked example, which lives in the *static*
system prompt text and is therefore present even when the ablation
strips the *dynamic* field list. The other two use generic field names
(`HttpStatusCode`, `SrcIpAddr`, `UserAgent`) plausible from the model's
general training knowledge, consistent with the small non-zero baseline
this kind of ablation typically has elsewhere. This is a real, traceable
side effect of writing concrete worked examples with real field names —
the same technique responsible for every prompt-fix win in §4F–§4H. Kept
the fix as-is: a 6.7% ablation leak is a rounding error against the 88.9%
FVR the grounding mechanism still delivers, and the alternative (genericizing
the DNS example) would undo a confirmed, real bug fix to preserve the
purity of a diagnostic test. Documented here rather than left unremarked.

### What's still open

- `61988db3-sop`'s residual FilterGroup/OR confusion — reduced, not zero.
- The percentile architecture gap identified in §4E (`4e3af8e3`) is
  *narrower* now, not closed: live-tested post-fix, the model now reaches
  for the new `percentile()` function on this case (it didn't before) but
  applies it across the wrong dimension — `percentile(ActingProcessName, 5)`
  grouped by that same field, which is degenerate (a percentile of a
  constant). The actual need is a percentile computed *across* groups'
  own aggregate results, used as a scalar threshold against each group —
  a second aggregation pass the IR has no construct for, compounded by
  derived/computed fields (`extend FileName = ...`, regex/GUID
  normalization) the IR also can't express. Confirmed as a larger,
  compound gap, not a one-line fix — deferred, now documented precisely
  rather than left as a vague "percentile support" item.
- Logic Correctness: still one rater — five rounds of re-scoring now
  (60%, 52.6%, 60%, 70%, 75%), still without independent verification.

127 unit tests (121 → 127, six new: 5 percentile validator/compiler
tests plus coverage intent for the AND/OR fix, which is prompt-text-only
and not independently unit-testable) — `pytest tests/unit -q` green.

---

## 4I. Generalizing the IR beyond single-column summarize — and a real repair-loop bug found while measuring it

User request: rewrite `RESULTS_DRAFT.md` to current state, then push
further on accuracy and KQL generality. The write-up was mechanical
(current §4H numbers, full causal history, all open limitations
transferred forward — see the file itself). The generalization work
targeted a gap visible in every ground-truth query checked so far but
never addressed: **real ASIM analytic rules almost always compute several
summarize columns together** — a count to threshold on, plus a
`make_set()` of URLs/user-agents for analyst triage, plus
`min`/`max(TimeGenerated)` for the activity window — and `SecurityIR`
could only ever express one.

### What changed

1. **`additional_aggregations: List[Aggregation]`** added to both
   `SecurityIR` and `JoinStage` — extra summarize columns computed
   alongside the primary `aggregation` in the same clause. The threshold
   always compares against the primary aggregation only; everything in
   `additional_aggregations` is side evidence, never an alerting condition.
2. **Two new aggregation functions**: `make_set` and `make_list`, plus an
   optional `Aggregation.limit` (the collection-size cap KQL itself
   defaults to 128 when omitted — unlike `percentile`'s value, a missing
   `limit` is not an error).
3. **New validator checks**, mirrored for both the main IR and the join
   stage: each `additional_aggregations` entry gets the same
   field-existence/missing-field/percentile-value checks as the primary
   aggregation (refactored into one shared `_validate_aggregation_object`
   helper); `ADDITIONAL_AGGREGATIONS_WITHOUT_AGGREGATION` catches extra
   columns with no primary aggregation to sit next to;
   `DUPLICATE_AGGREGATION_ALIAS` catches two columns reusing the same
   name, which would be invalid KQL (`summarize X = count(), X = sum(Y)`).
4. **Compiler/template**: `kql_agg_call` extended for `make_set`/
   `make_list`'s optional second argument; the summarize clause now loops
   over `[aggregation] + additional_aggregations`, comma-separated, for
   both the main query and the join subquery.
5. **Prompt guidance + a worked example** in both agent prompts, modeled
   on the `43c2832e` ground truth's actual shape (count + make_set(Url)
   + min/max(TimeGenerated)).

### Confirmed live — generalized far beyond the one case it was built for

The worked example targeted `43c2832e` specifically. Live-tested, the
model used `additional_aggregations` correctly and *unprompted* on
`b35f6633`, `a59ba76c`, and `813ccf3b` as well — none of which were shown
an exact match in the worked example — producing output essentially
identical in shape to each one's actual ground truth (e.g. `43c2832e`'s
render: `ForbiddenCount = count(), Urls = make_set(Url, 100),
EventStartTime = min(TimeGenerated), EventEndTime = max(TimeGenerated)`,
matching GT's `ErrorCount=count(), Urls=make_set(Url,100),
EventStartTime=min(...), EventEndTime=max(...)` near-exactly modulo
column order and alias spelling). This is the clearest evidence in the
study that a single well-chosen worked example can generalize the model's
behavior beyond its literal target case, not just pattern-match it.

### A real, separate bug found while investigating a completion-rate drop

The first live run after shipping the above landed at 86.7%/84.4%/72.7%
— below §4H's 93.3%/88.9%/88.5%. Checking a previously rock-solid simple
case (`365a889c-original`) that was now failing outright: it failed 3/3
standalone re-runs, and the *final* IR attached to the failure was —
checked by hand — **fully valid**. Tracing `run_with_repair`'s loop:
with `max_attempts=3`, it performs 4 total builds (1 initial + 3 repairs)
but the loop's `range(max_attempts)` bound meant only the *first 3*
builds were ever passed to `validate_ir` — the 4th, made at the end of
the last iteration, was returned as `MAX_REPAIR_ATTEMPTS_EXCEEDED`
without ever being checked. A correct IR was being silently thrown away
on every repair sequence that took exactly the full budget to converge —
a pre-existing bug, not something this round introduced, but newly
*visible* because `additional_aggregations` gave the model more to get
right on early attempts, pushing more cases into exactly that edge.

Fixed by changing the loop to `range(max_attempts + 1)` and only
rebuilding when `attempt < max_attempts`, which validates every build
including the last while leaving total model-call counts unchanged
(verified: all 7 pre-existing repair-loop tests pass with identical
call-count assertions). Added a regression test
(`test_the_final_repair_attempts_own_output_is_actually_validated`) using
a mock where only the 4th build is valid — failed before the fix, passes
after.

**A second-order consequence, also found and fixed**: `eval/run_ablations.py`'s
No-Repair ablation calls `run_system_b(..., max_attempts=1)`, which
*relied on* the old bug — under the old semantics, `max_attempts=1`
silently performed one wasted, never-checked rebuild, which happened to
approximate "no credit for any repair." Under the fixed semantics,
`max_attempts=1` now grants one genuine, validated repair — no longer a
true zero-repair measurement. Changed the ablation's call to
`max_attempts=0`, confirmed by trace and a manual mock check to perform
exactly one build, checked once, never rebuilt — true first-attempt-only
semantics. Re-running just this ablation after the fix: 46.7% (21/45),
consistent with §4F–§4H's established 46–51% range — confirming the
intermediate 73.3% reading (using the now-corrected-away `max_attempts=1`)
was an ablation-isolation artifact of the same bug, not a real number.

### Live results

| Metric | §4H | §4I |
|---|---|---|
| System B completion/SVR | 93.3% | 91.1% |
| FVR | 88.9% | 86.7% |
| RRR | 88.5% | 82.6% |
| Logic Correctness (in-scope) | 15/20 = 75% | **15/20 = 75% — numerically identical, but structurally richer** |
| No-Repair ablation (corrected) | 48.9% | 46.7% — consistent, not a regression |
| Monolithic ablation | 66.7% | 62.2% |
| No Schema Grounding ablation | 6.7% (3/45) | **13.3% (6/45) — grew further** |

§4H/§4I's completion numbers (93.3%, then 91.1%) both sit inside the
same non-determinism band this session has measured throughout; the dip
is not attributable to a regression this round introduced (the
repair-loop fix, if anything, should only ever help). Logic Correctness
landing at exactly 15/20 again, with the *same* underlying causes (4
confirmed missing-information-ceiling cases plus the one residual
FilterGroup/OR recurrence from §4H), is itself informative: this round's
changes (multi-aggregation, repair-loop fix) didn't touch the specific
failure modes blocking those 5 cases, and didn't introduce any new ones
— a clean, additive result.

**No-Schema-Grounding's leak grew from 1 worked example to 2.** The new
evidence-collection worked example's literal field names (`Url`,
`TimeGenerated`) and aliases (`EventStartTime`, `EventEndTime`) now also
appear in cases that succeed with zero dynamic schema grounding, on top
of §4H's `DnsResponseCodeName` leak. Same judgment as §4H, now with a
sharper illustration of the tradeoff: the single most effective technique
in this entire study (concrete worked examples with real field names) is
also the direct cause of the only ablation in the study that isn't
perfectly clean. 13.3% is still a 6x gap below the 86.7% FVR the grounding
mechanism delivers when active — kept as-is, documented rather than hidden,
flagged again for a second opinion in §5.

### What's still open

- The percentile-of-aggregates + derived-field gap from §4H is untouched
  by this round's work — still the largest confirmed architectural gap.
- The residual `61988db3-sop` FilterGroup/OR confusion recurred again
  this round (now also affecting `61988db3-original`, in a new variant —
  an unprompted, unwanted `summarize` clause invented for a detection
  that should have stayed a flat filter list). Not yet traced to a single
  cause the way the `has_all` bug was in §4H.
- The No-Schema-Grounding ablation's leak has grown twice now (0%→6.7%→13.3%)
  as worked examples accumulate — worth deciding, before a third worked
  example is added, whether to keep accepting this tradeoff indefinitely
  or to genericize older examples once newer ones make the same point.
- Logic Correctness: still one rater — six rounds of re-scoring now
  (60%, 52.6%, 60%, 70%, 75%, 75%), still without independent verification.

138 unit tests (127 → 138: 6 for `additional_aggregations`/`make_set`/
`make_list` validation, 4 for their compiler rendering, 1 regression test
for the repair-loop off-by-one) — `pytest tests/unit -q` green.

---

## 4J. Tracing the recurring `61988db3` confusion to an actual root cause — highest numbers of the study

§4I left one named, unresolved item: the `61988db3` FilterGroup/OR
confusion, recurring at a reduced rate since §4H but "not yet traced to a
single cause the way `has_all` was." User asked directly what it would
take to fix the logic and to go do it — so this round is that tracing,
done the same way `has_all` was: read the ground truth and the NL
side by side until the actual mechanism shows up, not just another
prompt tweak fired at the symptom.

### The actual mechanism

Ground truth: `Process has_any (procList) ... CommandLine has "recycler"`
— two independent AND-ed conditions. The `sop_imperative` paraphrase:
*"If a known living-off-the-land binary (cmd.exe, ftp.exe, schtasks.exe,
powershell.exe, rundll32.exe, regsvr32.exe, **or** msiexec.exe) is
executed with a command line referencing the recycler folder..."* — the
"or" inside the parenthetical only scopes the enumerated LOLBin names
(any one of them), but it sits one clause away from "is executed with a
command line referencing the recycler folder," which is a *separate*,
AND-ed condition. The existing FilterGroup-vs-AND guidance (added §4H)
correctly taught "don't wrap required-together conditions in an OR" and
"don't flatten OR-sets into AND" — but neither rule addresses this
specific *grammatical* trap: an "or" that's visually adjacent to, but not
actually scoping, the clause that follows it.

### What changed

One new bullet in both agent prompts, naming the exact sentence shape:
`"(X1, X2, ..., or Xn) is/does Y"` — explicitly stating the "or" scopes
only the enumerated list, not Y, using the LOLBin/recycler case itself as
the worked instance (the case that kept failing, used directly as its own
fix's example).

### Confirmed live

6/6 standalone re-runs of `61988db3-casual` and `-sop` rendered correctly
afterward (clean AND between the LOLBin check and the recycler check),
where the same two cases had been flipping between correct and
OR-inverted across the last several full comparison runs.

| Metric | §4I | §4J |
|---|---|---|
| System B completion/SVR | 91.1% | **95.6% — highest of the entire study** |
| FVR | 86.7% | **93.3% — highest of the entire study** |
| RRR | 82.6% | **91.7% — highest of the entire study** |
| Logic Correctness (in-scope) | 15/20 = 75% | 15/20 = 75% — same number, different composition |
| No-Repair / Monolithic / No-Schema-Grounding ablations | 46.7% / 62.2% / 13.3% | 48.9% / 64.4% / 11.1% — all within established bands |

Logic Correctness held at 75% but the failure composition changed in a
way that confirms the fix worked on its actual target: `61988db3-casual`
is now a clean pass (was OR-inverted in §4I). `61988db3-sop` still fails,
but for a *different, narrower* reason — it now correctly uses two
separate AND-ed `| where` clauses (the targeted bug is gone), but the
LOLBin enumeration inside the `in (...)` filter was truncated to 2 of 7
names (`cmd.exe`, `ftp.exe`) on this run. That's a real miss, but a
smaller one — an incomplete-list problem, not a logic-inverting one — and
distinct enough from the original bug that it shouldn't be read as the
same fix failing to hold.

### What's still open

- The new incomplete-LOLBin-list issue on `61988db3-sop` — first observed
  this round, not yet itself investigated. Possibly just non-determinism
  on a 7-item enumeration; possibly a real, smaller pattern worth tracing
  the same way. One occurrence isn't enough to tell yet.
- The percentile-of-aggregates + derived-field gap (§4H/§4I) — untouched,
  still the largest confirmed architectural gap.
- The No-Schema-Grounding ablation's leak (§4H/§4I) — unchanged this
  round (11.1%, within the established 6.7–13.3% band), since this
  round's fix was prompt-text-only and didn't touch a worked example with
  new field names.
- Logic Correctness: still one rater — seven rounds of re-scoring now
  (60%, 52.6%, 60%, 70%, 75%, 75%, 75%), still without independent
  verification. Three consecutive rounds at the same 75% — on changing
  underlying compositions each time — is itself a meaningful signal that
  the architecture's current ceiling on this exact dataset, given this
  exact rater, may be close to found.

No code changes this round (prompt text only) — 138 unit tests unchanged,
`pytest tests/unit -q` still green.

---

## 4K. The AST migration: a major, externally-introduced rewrite, found broken, then hardened over four live rounds

Between §4J and this section, `SecurityIR` (the flat, single-object IR this
entire study through §4J was built around) was replaced wholesale with a
new `KqlPipeline` AST — a sequence of typed stages (`WhereStage`,
`SummarizeStage`, `ExtendStage`, `JoinStage`, `UnionStage`, `ProjectStage`,
`TopStage`) intended to express arbitrary KQL pipelines, not just the
single-table-plus-one-join shape `SecurityIR` was limited to. This
happened outside this document's own narrative — by the time it was
reviewed here, `src/ir_engine/ir_schema.py`, `ir_validator.py`,
`compiler.py`, `ir_builder_agent.py`, and three test files had all already
been rewritten, plus two new docs (`architecture_v2_ast.md`,
`MASTER_PLAN_v2_ast.md`) describing the new design. The user's own request
for this change had explicitly scoped it as "docs only" — what shipped
went well beyond that.

### What was found, first pass: this was not safe to build on

1. **A crash bug.** `JoinStage.right_pipeline` was typed `Any`, so a
   malformed nested pipeline from the model "parsed successfully" as a
   raw `dict`, and `validate_ir`'s recursive call crashed with
   `AttributeError` instead of failing validation cleanly. Confirmed live
   on a baseline-vs-current case.
2. **The very first bug fixed in this entire study had fully regressed.**
   `DEGENERATE_THRESHOLD` (count > 0 is trivially true for any existing
   group) was gone from the new validator entirely. Confirmed live: the
   model invented pointless `summarize Count = count() | where Count > 0`
   clauses on detections that should have stayed flat filter lists.
3. **~2,153 lines of validated code and tests were deleted, replaced by
   431.** Every targeted prompt fix from §4F–§4J — the sdelete worked
   example, Src/Dst guidance, DNS-outcome guidance, the sentence-shape
   disambiguation fix, the `has_all` warning, percentile/`make_set`
   validation — was gone, replaced by a much shorter generic prompt.
4. **`ExtendStage.computed_fields[].expression` was a raw, completely
   unchecked string** — the only way to express field-to-field
   comparisons (baseline margins, etc.) since `compare_to_join_field` was
   removed, with nothing validating what's inside it. This defeated the
   field-hallucination-prevention thesis the entire project is built on,
   for exactly the queries that need it most.
5. **`monolithic_agent.py` had a hard `ImportError`** — it still imported
   the now-deleted `SecurityIR`, meaning the Monolithic ablation could not
   even run.
6. The new docs didn't match the shipped code (e.g. they document a
   `MISSING_TIME_WINDOW` check using old field names that doesn't exist in
   the real validator).

User's call, given these findings: keep the AST direction and harden it
properly, rather than revert. What follows is four live-tested rounds
doing exactly that — confirming the core idea is sound and worth the
investment, while being honest that the resulting numbers are still below
§4J's pre-migration peak.

### Round 1 — fix what's broken, restore what's lost

- Fixed the crash (`right_pipeline: "KqlPipeline"` with a proper forward
  reference + `model_rebuild()`, replacing `Any`).
- Fixed a second, related bug the crash trace surfaced: `Filter.value`'s
  list variant was `List[str]`-only, rejecting a numeric `in` filter (e.g.
  `DstPortNumber in (139, 445)`) — widened to
  `List[Union[str, int, float]]`. This in turn exposed a third bug:
  `kql_literal` crashed on a non-string list item (`AttributeError`,
  `int` has no `.replace()`) — fixed.
- Restored `DEGENERATE_THRESHOLD`, `MISSING_TIME_WINDOW`,
  `AGGREGATION_MISSING_FIELD`, `INVALID_PERCENTILE_VALUE`, and added
  `DUPLICATE_AGGREGATION_ALIAS` (new — a `SummarizeStage` can now hold
  multiple aggregations natively, which needed its own duplicate-alias
  check the flat model never needed).
- **Added real validation for `ExtendStage.computed_fields[].expression`**
  — a best-effort identifier extractor (strips string literals, treats
  any identifier immediately followed by `(` as a function call rather
  than a field) that checks every referenced field against the
  pipeline's actual tracked schema at that point. Not a full KQL parser,
  but the difference between zero checking and something is large.
- Re-ported every lost prompt guidance block onto the new schema, plus
  **two new worked examples**: a fully concrete baseline-vs-current
  pattern (join + extend + threshold, replacing the deleted
  `compare_to_join_field`), and — genuinely new — **a percentile-of-
  aggregates pattern**, confirmed to actually compile: a per-group
  aggregation, a constant-key self-join against a second pass computing
  the global percentile, then extend+where to compare each group against
  it. This is the exact pattern `4e3af8e3` needed and `SecurityIR` could
  never express — now it can, with a worked example to reach for it.
- Fixed `monolithic_agent.py`'s `ImportError`, and had it import the IR
  Builder's `_COMMON_MISTAKES` block directly rather than duplicating it —
  removing the exact kind of drift that caused this section's problems.
- Hardened the constraint-traceability check to anchor on a real
  aggregation alias (tracking `SummarizeStage` result aliases through the
  pipeline, including into join `right_pipeline`s) rather than matching
  any filter in the pipeline that happened to share a literal number.
- 99 unit tests (up from 74) covering every fix above.
- **Live result: 77.8% / 68.9% / 58.3%** (completion/FVR/RRR) — both
  previously-fixed targeted cases (`5b6ae038` sdelete, `61988db3`
  recycler) confirmed clean on 2 of 3 paraphrases each.

### Round 2 — a new AST-specific failure class

Live-testing surfaced a failure mode that doesn't exist in a flat IR: a
`WhereStage` filtering on a field a `SummarizeStage` had already dropped
(group_by only included one of two fields a "per X/Y pair" phrase
needed), repeating identically across all 3 repair attempts. Added
guidance naming the mechanism directly (`SummarizeStage` keeps only
group_by + new aliases; filter on a raw field before the stage that would
drop it; "per X/Y pair" needs both fields in group_by). Confirmed live: a
previously-stuck case (`8717e498`, baseline-vs-current with a 2-field
group) validated cleanly on attempt 0 in isolated testing, though not yet
reliably at full-dataset scale. **Live result: 77.8% / 71.1% / 61.5%** —
flat completion, real FVR/RRR gains.

### Round 3 — the actual root cause of the recurring event-type confusion

Tracing `5b6ae038-casual`'s regression (both the OR-confusion bug and a
wrong event type in the same output) to its source: the **Extraction
Agent**, not the IR Builder, was the origin. It produced
`likely_event_type: "File Wiping"` — a technique/outcome-framed label —
which strongly anchored the IR Builder toward `FileEvent` even though the
description's own technical details (a process, command-line flags)
pointed at process execution. Because `FileEvent` is itself schema-valid,
there was no validation error to trigger a repair; it just shipped wrong
silently. Added explicit guidance to the Extraction Agent's own prompt —
previously bare — distinguishing technical event category from technique/
outcome framing, naming the two exact confusions found this session
("file wiping" / "malware hidden in the recycle bin" are both process
execution). Confirmed live: `likely_event_type` came back "process
execution" on 6/6 follow-up checks, where it had been wrong before.

Separately, added a structurally-detectable special case of the
recurring OR-confusion bug: a `FilterGroup` whose conditions are all
negated operators on the same field with different literal values (e.g.
`!endswith "sdelete.exe" or !endswith "sdelete64.exe"`) is a logical
tautology — nothing can simultaneously fail to end with both literals, so
it's always true and filters nothing (`TAUTOLOGICAL_FILTER_GROUP`).
**Live result: 73.3% / 68.9% / 55.6%** — a dip from round 2, but the
event-type fix's own target confirmed fixed in isolation; aggregate
non-determinism (and a more complex schema) make single-round dips hard
to read as pure regression.

### Round 4 — the most basic tautology variant, and the honest ceiling on one stubborn case

The live run surfaced an even more direct tautology the round-3 check
didn't cover: `X in (...) or X !in (...)` on the same field and value — X
or not-X, true by definition. Added a second check
(`_has_complementary_pair`) for exact complementary operator pairs
(`EQ`/`NEQ`, `IN`/`NOT_IN`, etc.) on the same field and value. **Live
result: 84.4% / 73.3% / 70.8% — the best of all four rounds**, and the
clearest evidence the cumulative fixes are compounding rather than
trading off against each other.

**Logic Correctness, full re-score: 11/17 = 64.7%.** Of the 6 failures,
4 are the well-documented `-original`-paraphrase missing-information
ceiling (`61988db3`, `a59ba76c`, `813ccf3b`, `43c2832e` — all four
`-original` variants failed this round, consistent with the established
pattern from every round before the AST migration). The other 2 are both
`5b6ae038` (the sdelete renamed-binary-evasion case) — `-original` and
`-casual`, the same case that has now shown a *different* broken variant
in every single one of these four rounds: a tautological OR (round 1),
the schema-mutation issue was unrelated to this case, an inverted-presence
requirement wrapped in a redundant positive OR (round 4), and the
original required-flags-in-OR pattern recurring on `-casual` specifically
every round. This is the most concentrated, persistent unresolved item
from this entire hardening arc — narrowed to one case, not eliminated.

### Honest comparison to the pre-migration state

| Metric | §4J (pre-migration peak) | §4K round 4 (current) |
|---|---|---|
| Completion/SVR | 95.6% | 84.4% |
| FVR | 93.3% | 73.3% |
| RRR | 91.7% | 70.8% |
| Logic Correctness (in-scope) | 75% | 64.7% |
| No-Repair / Monolithic / No-Schema-Grounding | 48.9% / 64.4% / 11.1% | 46.7% / 55.6% / 4.4% |

The AST model is not yet back to where the flat `SecurityIR` model
finished — four rounds of hardening a structurally more complex
representation is, on this evidence, roughly comparable to where the flat
model stood after its own first few rounds, not its last. What's
genuinely different and worth the cost so far: no crashes, none of the
five previously-fixed bug classes silently regressed and left unfixed,
`ExtendStage` expressions are now checked instead of a blind trust gap,
and percentile-of-aggregates — confirmed structurally impossible under
`SecurityIR` and flagged as the largest open architectural gap for four
consecutive rounds (§4E–§4J) — now compiles to correct KQL.

104 unit tests (74 → 104 across this section: 25 for restored/new
validator checks including both tautology detectors, ExtendStage
expression validation, and the crash regression; 5 for compiler-level
fixes including the percentile-of-aggregates self-join pattern) —
`pytest tests/unit -q` green throughout.

### What's still open

- The `5b6ae038` sdelete case — the single most persistent unresolved
  item, a different broken variant every round, not yet traced to one
  fixable mechanism the way the event-type confusion was in round 3.
- The AST exclusion-boundary re-audit (flagged since §4I) is now doubly
  relevant — the new constructs (multi-stage `SummarizeStage`, the
  percentile-of-aggregates self-join pattern) may reclassify some of the
  24 GT-structurally-out-of-scope records as in-scope, but this hasn't
  been re-run against the new schema.
- `architecture_v2_ast.md` / `MASTER_PLAN_v2_ast.md` describe the AST
  design but not the actual shipped, hardened state (the crash fix, the
  restored checks, the tautology detectors, the `ExtendStage` validator) —
  need a pass to reflect reality rather than the original aspirational
  sketch.
- Logic Correctness: still one rater — eight rounds of re-scoring now,
  still without independent verification, and this round's number
  (64.7%) is the first to drop rather than hold or rise since §4F.
- `RESULTS_DRAFT.md` reflects §4J's numbers, not this section's — needs
  another reconciliation pass once the architecture stabilizes further;
  rewriting it against numbers that are themselves still moving round to
  round would itself be premature.

---

## 4L. Closing the gap: a full system audit, four real bugs found, completion crosses 93%

User's ask: go through the complete system end to end looking for what
needs to change to push the numbers above 93%, and produce an honest
comparison of the new AST architecture against the old one. Rather than
another single targeted live-test-and-fix cycle, this was a systematic
pass: trace every live failure from §4K round 4 to its actual mechanism,
not just the nearest one.

### Four real bugs found

1. **The constraint-traceability check had two false-positive blind
   spots.** It only ever looked at `WhereStage` filters for a number
   matching the description's threshold language. Two legitimate AST
   constructs put that same number somewhere else entirely:
   `TopStage.limit` ("top 25 noisiest clients" correctly compiles to a
   `TopStage`, not a filter) and `Aggregation.percentile` ("at or below
   the 5th percentile" correctly compiles to `percentile=5`, not a
   filter). Both were being flagged as `THRESHOLD_VALUE_MISMATCH` on
   already-correct IRs, forcing the repair loop to "fix" something that
   wasn't broken — confirmed live on `b35f6633` (the DNS top-25 case) and
   `4e3af8e3` (the single hardest case in the dataset, percentile-of-
   aggregates). Fixed by teaching the check about both constructs.
2. **A hallucinated `source_table` produced a confusing, wrong-diagnosis
   error.** When the model invented a free-text label like `"error
   event"` instead of a real ASIM type, `available_schema` came back
   empty and every subsequent field check failed with an unhelpful
   "closest match: None" — the error pointed at the field names, not the
   actual problem (the source table itself). Added a dedicated
   `INVALID_SOURCE_TABLE` check, with a closest-match suggestion against
   the real ASIM event type names, that fires immediately instead of
   cascading into noise.
3. **A "user agent"-themed description picked the wrong event type** —
   `NetworkSessionEvent` instead of `WebSessionEvent` — confirming the
   surface-wording disambiguation guidance didn't explicitly name User-
   Agent strings as an HTTP-specific signal.
4. **The actual root cause of #3, and likely several other recurring
   event-type confusions across every §4K round: the foundational DNS/
   HTTP/Process event-type disambiguation bullet — one of the earliest
   and most validated fixes in this entire project (§4F) — was never
   re-ported when the AST migration's prompt was rewritten.** Checking
   `ir_builder_agent.py` directly confirmed it: zero mentions of
   `WebSessionEvent`, `DnsEvent`, or any DNS/HTTP/process disambiguation
   logic anywhere in the AST-hardened prompt. Every round of §4K re-ported
   *other* lost guidance (Src/Dst, sdelete, sentence-shape) but missed
   this one specifically — restored now, verbatim-equivalent to the §4F
   original plus an explicit note that `source_table` must be an exact
   ASIM type match, not a free-text label.

### Live results — completion crosses the 93% mark

| Metric | §4K round 4 | §4L (this round) |
|---|---|---|
| Completion/SVR | 84.4% | **93.3%** |
| FVR | 73.3% | **84.4%** |
| RRR | 70.8% | **85.0%** |
| Logic Correctness (in-scope) | 64.7% (11/17) | **71.4% (15/21) — best of the entire AST arc** |
| No-Repair ablation | 46.7% | **60.0%** |
| Monolithic ablation | 55.6% | 62.2% |
| No Schema Grounding | 4.4% | 11.1% (within the study's established noise band for this ablation) |

**No-Repair jumping from 46.7% to 60.0% is the most important number
here** — it means the fixes (especially the disambiguation restore)
improved *first-attempt* correctness, not just the repair loop's ability
to patch things up after the fact. This is the same signature every
genuinely-root-cause fix in this study has had, going back to §4F.

Of the 21 in-scope Logic Correctness cases, 15 passed; of the 6 failures,
**5 are the confirmed `-original`-paraphrase missing-information
ceiling** (`61988db3`, `b35f6633`, `a59ba76c`, `813ccf3b`, `43c2832e` —
all five, the NL genuinely omits the technical detail needed). Only one
(`5b6ae038-original`) is a real, new, addressable issue: the AND-logic
fix held (no inversion), but the output included a stray `"recycler"`
filter that doesn't belong in the sdelete detection at all — looks like
cross-contamination between the two worked examples in the prompt, not
yet investigated further.

110 unit tests (104 → 110: 5 for the two constraint-traceability fixes,
3 for the new `INVALID_SOURCE_TABLE` check) — `pytest tests/unit -q` green.

### How the new AST system compares to the old flat `SecurityIR` system

| | Old (`SecurityIR`, §1–§4J peak) | New (`KqlPipeline`, §4K–§4L current) |
|---|---|---|
| Structure | One flat object: filters + one optional aggregation + one optional threshold + one optional join | A sequence of typed stages (`where`/`summarize`/`extend`/`join`/`union`/`project`/`top`), each able to repeat and chain in any order |
| Multi-column aggregation | Required a bespoke `additional_aggregations` field bolted on in §4I | Native — `SummarizeStage.aggregations` is just a list from the start |
| Percentile-of-aggregates | **Structurally impossible** — confirmed and documented as the largest open architectural gap across §4E–§4J | **Expressible** — a constant-key self-join plus a second `SummarizeStage`, confirmed compiling to correct KQL |
| Field-to-field comparison (baseline margins, etc.) | A single-purpose `compare_to_join_field` on `Threshold`, only worked for exactly that one pattern | `ExtendStage` + a `WhereStage` on the computed field — general-purpose, works for any comparison, not just baseline-vs-current |
| Computed/derived fields | Not supported at all | `ExtendStage`, with real field-reference validation (not a full parser, but real) |
| Ranking ("top N") | Not supported — every "top N" case had to be approximated as a threshold, which is semantically wrong (a count threshold and a ranking limit are different concepts) | Native `TopStage` |
| Raw/non-ASIM tables | Not supported | Schema allows it (`source_table: Union[ASIMEventType, str]`), though current prompt guidance and the new `INVALID_SOURCE_TABLE` check intentionally steer away from it until there's an actual use case |
| Validator architecture | Static: check every field against one fixed schema for the whole IR | Stateful: tracks which fields exist *at each point* in the pipeline, since `summarize`/`project` narrow availability and `extend`/`join` widen it — a qualitatively different and more general validation strategy |
| Tautology detection | None | Two checks (`TAUTOLOGICAL_FILTER_GROUP`, both variants) — found live, not anticipated in advance |
| Peak measured performance | 95.6% / 93.3% / 91.7% / 75% | 93.3% / 84.4% / 85.0% / 71.4% |

**Honest summary**: the new architecture is a genuine capability upgrade
— it can express patterns (percentile-of-aggregates, arbitrary computed
fields, ranking, multi-stage pipelines) the old one structurally could
not, and several of its validator checks (the stateful tracker, tautology
detection) are more general and more powerful than anything the flat
model had. Completion and RRR have now caught up to within a few points
of the old peak; FVR and Logic Correctness are closer but not yet fully
there. The honest reading: this round closed most of the regression, not
all of it — the trend across every §4K/§4L round has been upward, and the
remaining gap is narrower than at any point since the migration was found
broken.

### What's still open

- `5b6ae038-original`'s stray `"recycler"` filter — a new, single-instance
  issue, not yet investigated.
- The two `8717e498` baseline-vs-current failures (2-field group_by
  pattern) — still the hardest case in the dataset, unresolved since
  §4K round 1's guidance only partially helped.
- `architecture_v2_ast.md` / `MASTER_PLAN_v2_ast.md`'s remaining sections
  (worked examples, repair loop walkthrough) beyond the schema/validator
  sections already fixed in §4K — still describe the pre-hardening sketch.
- Logic Correctness: nine rounds of re-scoring now, still one rater.
- `RESULTS_DRAFT.md` — still reflects §4J, now even further behind.

---

## 4M. Restoring the sdelete worked example, a metrics bug, and a genuine new field-hallucination class caught

Continuation of §4L's systematic audit, focused on the remaining named
issues plus a fresh trace of any live failure not yet explained.

### Three more findings, two of them new classes of bug

1. **The sdelete/disguised-tool worked example was gone, not just the
   short guidance bullet.** §4K had re-ported the *rule* ("exclude the
   obvious name, don't require it") but the original's concrete *worked
   example* — the exact five-filter template (four AND-ed flag checks,
   one AND-ed exclusion, zero FilterGroups) — was never restored. Without
   a concrete anchor, the model kept inventing extra complexity (a second
   tool-name variant to exclude, e.g. "sdelete64.exe") that then tangled
   into the FilterGroup/OR confusion this exact case has shown since §4B.
   Restored the worked example, and added an explicit instruction not to
   invent exclusion variants the description never names. Confirmed live:
   the OR-confusion is now eliminated on `-casual`/`-sop` (clean across
   repeated trials); `-original` alone still inverts the logic
   occasionally — a smaller, more isolated residual than before.
2. **`eval/metrics.py`'s FVR keyword list was missing `"percentile"`** —
   a real KQL function (added to the IR in §4H) that the *measurement*
   harness never learned about, undercounting FVR on every case using it.
   One-line fix.
3. **A genuine, previously-invisible field-hallucination class: invented
   KQL function names inside `ExtendStage` expressions.** Checking which
   successful cases referenced identifiers outside the known schema
   turned up `array_diff`, `array_avg`, `array_stddev` (and, on retry,
   `array_distinct`, `bag_distinct`) inside one case's `extend` —
   none of these are real KQL functions. The `ExtendStage` validator's
   "anything followed by `(` is a function, skip it" logic treated every
   one of these as exempt from checking, the same blind spot flagged but
   not fully closed in §4K. Added a ~120-entry whitelist of real KQL
   scalar functions and a new `UNKNOWN_FUNCTION_IN_EXPRESSION` check;
   anything not on the list is now rejected the same way a hallucinated
   field would be.

### Live results

| Metric | §4L | §4M |
|---|---|---|
| Completion/SVR | 93.3% | 88.9% |
| FVR | 84.4% | 84.4% (unchanged) |
| RRR | 85.0% | 77.3% |
| Logic Correctness (in-scope) | 71.4% (15/21) | **75% (15/20) — exact parity with the pre-migration `SecurityIR` peak** |
| No-Repair / Monolithic / No Schema Grounding | 60.0% / 62.2% / 11.1% | 51.1% / 57.8% / 11.1% |

**The completion dip (93.3%→88.9%) is a measurement correction, not a
regression.** The one case whose function-hallucination this round
caught (`c4956c0b`) was *already* being flagged as field/identifier-
invalid by `eval/metrics.py`'s independent FVR text-scan in every prior
round — `system_b_success=True` and "this query references unknown
identifiers" were quietly disagreeing with each other the whole time.
The validator now agrees with the metric: the case correctly fails
instead of shipping KQL with three hallucinated function calls. FVR
holding exactly steady (84.4% → 84.4%) while completion dropped confirms
this — the fix moved a false completion into an honest, accounted-for
failure, not the other way around. The rest of the swing (RRR, the
ablations) is within this study's well-documented run-to-run band.

**Logic Correctness reaching 75% is the headline result of this round.**
This is the same figure the flat `SecurityIR` model topped out at across
ten rounds (§4B–§4J) — the AST architecture has now closed that specific
gap entirely, on a slightly smaller comparison base (20 vs 21 in-scope
cases this run) but via the same kind of named, traceable fixes that
defined this study throughout. Of the 5 remaining failures, 4 are the
confirmed `-original`-paraphrase missing-information ceiling; only
`5b6ae038-original` is a real, live, addressable residual — narrower than
the 2-paraphrase spread it had in §4L.

112 unit tests (110 → 112: 2 for the hallucinated-function check) —
`pytest tests/unit -q` green.

### What's still open

**Update (§4N): the first three items below were investigated live and
fixed/substantially improved — see §4N. The doc items were also fixed in
§4K/§4N's reconciliation passes. Left here, struck through, so the
history of what was open at this point isn't lost.**

- ~~`5b6ae038-original` — now isolated to one paraphrase, still inverts
  the exclusion logic intermittently~~ — **root cause found and fixed in
  §4N**: the raw text never states sdelete's actual flags, and the
  Extraction Agent had no instruction to recall a named tool's real
  command-line syntax from its own knowledge. 8/8 trials clean after the
  fix.
- ~~`8717e498`'s 2-field group_by pattern — unchanged, still the hardest
  case in the dataset~~ — **a real, separate bug found in §4N**: this
  case wasn't a group_by problem at all on closer trace, it was a false
  `THRESHOLD_VALUE_MISMATCH` rejecting every single attempt before the
  group_by question could even matter. Fixed; 6/6 trials now structurally
  succeed. The 2-field group_by completeness itself remains a softer,
  partially-resolved residual (1/3 SOP trials).
- ~~`c4956c0b`'s underlying task ... may need a different computational
  approach (e.g. `series_stats`)~~ — **`stdev`/`variance` added as real
  aggregation functions in §4N**, closing the function-hallucination root
  cause generally (not just for this case). True row-level inter-arrival
  computation (`prev()`/`serialize`) remains genuinely out of the IR's
  reach — confirmed via direct GT-query scan in §4N, not just asserted.
- ~~`architecture_v2_ast.md` / `MASTER_PLAN_v2_ast.md`'s worked-example and
  repair-loop sections — still describe the pre-hardening sketch~~ —
  repair-loop sections were already fixed earlier in this round (before
  §4M was written); the remaining worked-example/tech-stack/repo-structure
  sections fixed in §4N.
- ~~`RESULTS_DRAFT.md` — still reflects §4J's numbers~~ — fixed earlier in
  this round (before §4M was written); this bullet was stale the moment it
  was written.
- Logic Correctness: still one rater — see §4N for the current count and
  the GT-scope re-audit, which found the in/out-of-scope boundary itself
  was stale (most of the historical exclusions needed join/multi-stage-agg,
  which the AST now supports).

---

## 4N. Closing the three named gaps live, a GT-scope re-audit, integration
     tests, and a broader generalization pass

Direct continuation of §4M, in response to a request to push every
remaining named issue, add integration tests, and generalize the system
as far as reasonably possible rather than just the original three named
bugs. All three of §4M's "what's still open" live bugs were traced with
real model calls (not just unit-level reasoning) and either fixed or
substantially improved; two more real bugs and two new architectural
findings turned up doing it.

### Three named bugs, traced live and fixed

1. **`5b6ae038-original` (sdelete) — root cause finally found.** Tracing
   the raw model output (not just the final IR) showed the Extraction
   Agent's output for `-original` never contained the actual sdelete
   flags at all (`candidate_fields: ["sdelete", "C drive"]`) — because
   the raw text never states them ("command line parameters associated
   with the use of Sysinternals sdelete..."). The IR Builder, working
   from nothing concrete, improvised: inventing a flag that doesn't
   exist (`"-p"`), wrapping the real flags in a tautology-prone
   `FilterGroup`, or both. This was never a logic-inversion bug in the IR
   Builder at all — it was a missing capability in the Extraction Agent,
   which had no instruction to recall a *named* tool's well-documented
   command-line syntax from its own knowledge when the text doesn't spell
   it out. Added that instruction (`src/agents/extraction_agent.py`) plus
   a tightened worked-example note in the IR Builder
   (`src/agents/ir_builder_agent.py`) against inventing flags. **8/8
   live trials clean** after the fix, identical to the GT's five-filter
   structure every time.
2. **`8717e498` (SMB baseline-vs-current) — was never a group_by problem.**
   Live tracing showed **100% failure on both remaining paraphrases**
   (`-original` and `-sop`), not an occasional group_by miss — every
   single attempt was rejected with `THRESHOLD_VALUE_MISMATCH`. The
   `-sop` IR was actually correct: `Margin = CurrentCount - BaselineAvg`
   then `where Margin > 50`. But `_check_constraint_traceability` only
   recognized literal `SummarizeStage` aggregation aliases as legitimate
   homes for the threshold number — `Margin` is an `ExtendStage`-derived
   field, so the check skipped it and never found a match. The exact
   same false-positive shape already fixed twice before (`TopStage.limit`,
   `Aggregation.percentile`) — a third construct, same root mechanism.
   Fixed by widening `_collect_aggregation_aliases` (`src/pipeline/
   repair_loop.py`) to also collect every `ExtendStage` computed-field
   alias. **6/6 live trials now structurally succeed** (0/6 before). The
   2-field `group_by` completeness itself is a separate, softer residual
   — 1/3 SOP trials captured both `SrcIpAddr` and the port dimension, 2/3
   captured only `SrcIpAddr` — real, but no longer blocking the case
   entirely.
3. **`c4956c0b` (DNS beaconing) — `stdev`/`variance` added as real
   aggregation functions.** Added `STDEV`/`VARIANCE` to
   `AggregationFunction` (`src/ir_engine/ir_schema.py`), `KQL_AGG_FUNCTIONS`,
   and the validator's known-function set — closing the root cause behind
   the model inventing `array_avg()`/`array_stddev()` generally, not just
   for this one case. Live tracing across all 3 paraphrases: 3/3
   `-original`, 2/3 `-casual`, 1/3 `-sop` now produce honestly valid,
   schema-correct KQL (up from a documented 0% honest-success rate before
   §4M's hallucinated-function check even existed). True row-level
   inter-arrival-time computation (KQL's `prev()`/`serialize`) remains
   genuinely out of the IR's reach — confirmed structurally, not just
   asserted, by the GT-scope re-audit below.

### A new bug found in the new capability, fixed before it shipped wrong

Scoring Logic Correctness against the live results turned up a fourth,
self-inflicted issue: `8717e498-original`'s IR chained two
`SummarizeStage`s with the **same** `P14D` time_window in both — which
collapses the first stage to exactly one row per entity, making the
second stage's `stdev()` always `0` or `null` over a single-row group. A
silently-broken query: schema-valid, KQL-valid, and structurally
guaranteed to match nothing. Added explicit guidance (`src/agents/
ir_builder_agent.py`) that a stdev/variance-of-a-prior-aggregation pattern
needs a **finer** bucket in the first stage (e.g. `P1D`) than the overall
window, so the second stage has multiple rows per entity to compute
spread over.

### Two new architectural findings from broadening Logic Correctness's scope

Re-scoring Logic Correctness this round deliberately included every case
needing join/multi-stage-aggregation/real-OR — excluded from every
previous round's denominator because the old flat `SecurityIR` couldn't
express them at all. Doing this surfaced two new, real gaps the narrower
scope had never been able to see:

- **`4500a2ff` (Exchange mailbox export-then-delete) — 0/3.** GT needs "a
  *specific* named event, then a *different specific* named event, for
  the *same* entity, within a window" (an inner self-join on host+user
  within 1 hour). Every attempt instead approximated this as "2+
  occurrences of either event," which doesn't verify an export
  specifically preceded a delete — a real, no-worked-example-yet gap
  distinct from baseline-vs-current and percentile-of-aggregates.
- **`a61e9fc1` (app/port mismatch spoofing) — 0/3.** GT's logic is
  `(app==A and port!=portA) or (app==B and port!=portB) or ...` — an
  OR of AND-pairs. `FilterGroup` can only express a flat OR of plain
  atoms, not a disjunction of conjunctions; there is no nested-group
  construct in the schema at all. Every live attempt produced a
  different, structurally wrong approximation (one outright tautology).
  This is a genuine, newly-confirmed **structural limitation of the IR**,
  not a prompting gap — worth flagging for a future schema extension
  (e.g. allowing `FilterGroup.conditions` to itself contain nested
  `FilterGroup`/AND-sets) rather than another worked example.

### GT in/out-of-scope boundary re-audit — code-grounded, not re-asserted

Scanned all 15 unique test-split ground-truth queries directly for
constructs the AST genuinely cannot express (`prev(`/`next(`, `serialize`,
`mv-expand`, `parse`, `evaluate`, `pivot(`, `externaldata`, `make-series`,
`reduce by`) instead of relying on the old `needs_join`/
`needs_multi_stage_agg`/`needs_real_or` classifiers (which were never
persisted as code — they lived only in past sessions' one-off Python).
Result: **only 2 of 15** (`c4956c0b`'s row-window beaconing computation,
`c99cf650`'s `mv-expand`-based array unpacking after a multi-`make_set`
summarize) are still genuinely out of reach. Confirmed `c99cf650` by
reading its full GT — a real, complex `mv-expand` of three parallel
`make_set` columns, not worth a one-off `MvExpandStage` for a single
occurrence in 81 pairs. The historical ~24/45 out-of-scope figure is
**confirmed stale**: most of it was join/multi-stage-agg exclusions the
AST has supported since §4K. This round's Logic Correctness score below
uses the corrected, narrower exclusion set.

### Generalization: widened beyond the 3 named cases

- **`JoinKind`** widened from 3 to all 9 real KQL join kinds
  (`innerunique`, `rightouter`, `fullouter`, `rightanti`, `leftsemi`,
  `rightsemi` added) — the compiler already passed `.value` straight
  through to `join kind=`, so this was a safe, pure-capability addition.
  Added brief prompt guidance on when each is actually appropriate.
- **`AGGREGATE_FUNCTION_IN_EXTEND`** — a new validator check, found while
  tracing `8717e498`: aggregation functions (`count`, `stdev`, `percentile`,
  ...) only exist inside `summarize` in real KQL; calling one inside an
  `ExtendStage` expression (e.g. `extend X = stdev(Count)`) is invalid
  KQL that the old "anything followed by `(` might be a function, skip
  it" logic let through completely unchecked. Generalizes well past the
  one case it was found on.
- **`eval/run_comparison.py` and `eval/run_ablations.py` now call
  `load_dotenv()`.** Found while trying to reproduce a live trace from a
  clean shell: neither script ever loaded `.env`, so every historical run
  in this project's whole history depended on `LLM_PROVIDER`/
  `AZURE_FOUNDRY_*` being exported manually beforehand — undocumented
  anywhere, and silently falls back to local Ollama (a much weaker model)
  if forgotten. Confirmed live: without this fix, a careless re-run would
  silently score the wrong model.
- **Integration tests added** (`tests/integration/`, did not exist
  before — only an empty `__init__.py`): 25 tests wiring the real,
  non-mocked `validate_ir()` → `generate_kql()` → `validate_kql_syntax()`
  chain across every join kind, the percentile-of-aggregates self-join,
  baseline-vs-current, the new `AGGREGATE_FUNCTION_IN_EXTEND` check, and
  every existing hard-error check; plus a real-validator/real-compiler
  repair-loop suite (stubbed IR Builder only) with explicit regression
  tests for both false-positives fixed this round; plus 3 true live
  end-to-end tests (real LLM calls, `skipif` without credentials) anchored
  on the exact cases this round fixed. Unit + integration: **140 tests,
  all passing** (112 unit + 28 integration).

### Live results — completion ties the historical peak, on a harder set

| Metric | §4M | §4N |
|---|---|---|
| Completion/SVR | 88.9% | **95.6%** (43/45) — ties the pre-migration `SecurityIR` peak (§4J) |
| FVR | 84.4% | **86.7%** |
| RRR | 77.3% | **83.3%** |
| Per-tier | — | simple 9/9, moderate 9/9, complex 25/27 |
| No-Repair / Monolithic / No-Schema-Grounding | 51.1% / 57.8% / 11.1% | 62.2% / 64.4% / 13.3% |

Only 2 of 45 instances failed outright, both on `-casual` paraphrases:
`4500a2ff-casual` (the export-then-delete sequence case) and
`4e3af8e3-casual` (percentile-of-aggregates on a vague paraphrase lacking
explicit percentile language) — both single-instance, not systematic.

### Logic Correctness — two numbers, reported together on purpose

Re-scored by hand against all 37 in-scope successes (39 in-scope
instances total, 2 failed outright and counted as failures) using the
3-point rubric (event type/table correct; comparison direction not
inverted; aggregation/grouping matches intent), under the **corrected,
broader** scope boundary from the re-audit above:

**23/39 ≈ 59.0%** — the honest number under the corrected scope, which
now includes every join/multi-stage-agg/real-OR case for the first time.

This is *lower* than every previous round's reported figure, and that is
expected, not a regression: previous rounds' denominators excluded
exactly the cases that turned out hardest (`4500a2ff` 0/3, `a61e9fc1`
0/3, `8717e498` 1/3, `4e3af8e3` 1/3 — four of the worst-scoring cases in
this round are ones the old scope never measured at all). Recomputing the
**same 9 rules that were always in-scope** (excluding the 4 newly-included
join/OR/multi-stage cases plus the 2 structurally out-of-scope ones):
**21/27 ≈ 77.8%** — slightly *above* the historical 75% peak, on the
exact comparison basis every prior round used. Both numbers are reported
together deliberately: the new architecture got slightly better at what
it could already do, and is now being honestly measured on a materially
harder problem set it could not even attempt before.

### What's still open

- `4500a2ff` (export-then-delete sequence) and `a61e9fc1` (OR-of-AND-pairs
  port mismatch) — two new, real, 0/3 gaps found by the broadened scope;
  the first needs a new worked example, the second may need an actual
  schema change (nested `FilterGroup`).
- `8717e498`'s 2-field group_by completeness — improved (no longer
  blocking the case) but still inconsistent (1/3 SOP trials).
- `4500a2ff-casual` and `4e3af8e3-casual` — the 2 outright completion
  failures this round; both single-paraphrase, not yet traced further.
- `c4956c0b`'s true inter-arrival-time computation and `c99cf650`'s
  `mv-expand` need — confirmed, not just asserted, as genuinely beyond
  the current IR; not planned for support given each is a single
  occurrence in 81 pairs.
- Logic Correctness: now scored under a corrected, broader scope for the
  first time, by the same single AI rater — more valuable than ever to
  get a second opinion on, especially the more judgment-heavy calls this
  round made explicit (e.g. `7b3ed03a-original`'s narrower-than-GT match,
  `8717e498-sop`'s absolute-vs-relative deviation formula).
- The Azure AI Foundry key rotation (§5 item 3) remains unconfirmed.

---

## 4O. Closing both newly-found architectural gaps, a new validator check,
     and Logic Correctness clears the historical peak on the broadened scope

Direct continuation of §4N, in response to an explicit instruction to push
for better accuracy and Logic Correctness specifically, by name, and to
execute the fix rather than just diagnose it. Targeted the two 0/3 gaps
§4N found (`4500a2ff`, `a61e9fc1`), the outstanding outright failures, and
re-ran the full live comparison to measure the effect.

### A real schema change: `AndGroup`, closing the OR-of-AND-pairs gap

`a61e9fc1` needed `(app==A and port!=X) or (app==B and port!=Y) or ...` —
a disjunction of conjunctions `FilterGroup` structurally could not
express (it's a flat OR of plain atoms only). Added `AndGroup`
(`src/ir_engine/ir_schema.py`): a new construct usable only as an entry
inside a `FilterGroup`, holding its own AND-ed `Filter` list. The
compiler (`src/generator/compiler.py`) renders each `AndGroup` entry as
its own parenthesized AND-block before OR-joining with the rest of the
group. The validator (`src/ir_engine/ir_validator.py`) checks field
references inside `AndGroup.conditions` the same way it checks plain
filters; the existing tautology checks were already written defensively
enough (`_has_complementary_pair` already filtered to plain `Filter`
entries; `_is_tautological_negation_group`'s `all()` check naturally
returns "not tautological" whenever an `AndGroup` is present) that
neither needed modification to stay correct on mixed lists — confirmed
with a dedicated regression test. Added a worked example matching
`a61e9fc1`'s exact shape to `_COMMON_MISTAKES`.

**Live result: 8/9 → 9/9-ish reliability**, and the KQL now matches GT's
structure almost exactly — the `-sop` paraphrase produces all four
app-type branches (dns/http/ssl/smtp) in one `FilterGroup` of `AndGroup`s,
compiling to the same shape as the ground truth.

### A worked example, closing the sequential-same-entity-events gap

`4500a2ff` needed "event A, then a *different*, specific event B, for the
*same* entity, within a window" — GT's actual self-join-on-identity
pattern, not a magnitude comparison. No existing worked example covered
this (baseline-vs-current compares a number; percentile-of-aggregates
compares a statistic; this needed comparing *which specific event
content* occurred on each side of a join). Added a fourth full worked
example to `_COMMON_MISTAKES`: filter-then-summarize the FIRST named
event to `ExportTime = min(TimeGenerated)` grouped by the shared entity,
join to a right_pipeline that filter-then-summarizes the SECOND named
event to `DeleteTime` the same way, then `MinutesBetween =
datetime_diff(...)` and `where MinutesBetween > 0 and <= window` — the
`> 0` half called out explicitly, since dropping it would also match the
delete happening before the export.

**Live result: 0/9 → 9/9.** Every trial across all three paraphrases now
produces the exact correct pattern, including the easily-dropped `> 0`
ordering guard.

### A new validator check, found while scoring this round's results

Scoring the live KQL for Logic Correctness turned up a third real bug,
this time in filter *values*, not structure: the model writing
`TimeGenerated >= "ago(1h)"` or `TimeGenerated >= "startofday(now())"` —
a string that looks like a real KQL function call but is just literal
text, compared as-is, never evaluated. A silently-useless filter that
reads as plausible KQL. Added `FUNCTION_CALL_AS_LITERAL_VALUE`
(`src/ir_engine/ir_validator.py`): any `Filter.value` matching
`identifier(...)` as a whole string is now a hard error, with guidance
toward `SummarizeStage.time_window` or a real `ExtendStage` expression
instead. Found twice in one run (`b35f6633-casual`, `813ccf3b-casual`) —
likely a real, recurring pattern, not a one-off.

### Other prompt fixes made, partial effect confirmed live

- **MITRE technique-name misreading**: `365a889c`'s description names the
  MITRE technique "Signed Binary Proxy Execution: Rundll32"; the model
  had been turning the word "signed" into a literal
  `ActingProcessFileDescription has "signed"` filter that doesn't exist
  in GT and doesn't correspond to anything the technique name actually
  asserts about log content. Added guidance to the Extraction Agent
  treating technique names as category labels, not data. Live effect:
  reduced but not eliminated (2/3 clean on direct re-test, then 3/3 clean
  in the full comparison run — likely genuinely fixed, one more
  confirmation round would help).
- **Over-fragmented `group_by`**: `43c2832e-original` kept adding
  ungrounded extra dimensions (`HttpRequestMethod`, `Url`, even
  `HttpUserAgent`) the description never asked to break down by,
  fragmenting a per-source volume count into many small per-combination
  counts. Added guidance against inventing extra grouping dimensions.
  Live effect: inconsistent — still over-fragments on `-original`
  specifically in the full run. Not fully resolved; likely needs a
  concrete worked example, not just a rule, the same lesson learned
  repeatedly elsewhere in this project (e.g. the sdelete case in §4N).

### Live results — Logic Correctness clears the historical peak, broadened scope and all

| Metric | §4N | §4O |
|---|---|---|
| Completion/SVR | 95.6% | 93.3% (within this study's documented noise band) |
| FVR | 86.7% | **91.1%** — highest FVR ever recorded in the AST era, within 2 points of the flat model's all-time peak (93.3%) |
| RRR | 83.3% | **85.0%** |
| Per-tier | 9/9, 9/9, 25/27 | 9/9 simple, 8/9 moderate, 25/27 complex |
| No-Repair / Monolithic / No-Schema-Grounding | 62.2% / 64.4% / 13.3% | 64.4% / 62.2% / 24.4% |

The No-Schema-Grounding jump (13.3%→24.4%) is the predicted mechanism
flagged since §4H materializing further: two more worked examples this
round means two more sources of static, literal field names leaking into
the prompt even when the dynamic schema list is stripped. Expected, not a
bug — the real-system fix from each example outweighs the ablation-purity
cost, same conclusion as every prior round that faced this tradeoff.

**Logic Correctness: 31/39 ≈ 79.5%** under the same corrected, broadened
scope as §4N (still single-rater) — **above the historical 75% peak**,
for the first time on the harder, broader case set that includes every
join/multi-stage-agg/real-OR case. Broken down:
- The 9 rules every prior round's narrower scope always measured: 21/27
  ≈ 77.8% — unchanged from §4N, consistent.
- The 4 rules newly in-scope since §4N's re-audit (`4500a2ff`, `8717e498`,
  `4e3af8e3`, `a61e9fc1` — exactly the cases this round targeted): **10/12
  ≈ 83.3%** — now scoring *better* than the long-standing "easy" subset,
  a complete reversal from §4N's 4/12 ≈ 33% on these same four rules.

112 unit + 30 integration = **142 tests, all green** (`pytest tests/unit
tests/integration -k "not live_e2e"`; the 3 live e2e tests pass too,
confirmed separately, but are excluded from the routine count since they
cost real API calls and inherit this study's documented model
non-determinism).

### What's still open

- `bd89c7a0` (cscript breakdown) and `43c2832e-original` (over-fragmented
  grouping) — both still inconsistent across paraphrases; likely need
  dedicated worked examples, the pattern that has reliably closed every
  other named gap in this project.
- `7b3ed03a-sop` regressed once this round (an OR-of-two-OR-sets where
  GT needs AND-of-two-OR-sets — itself an `AndGroup`-shaped need, just
  not yet recognized as one in the prompt's own examples) — not yet
  confirmed as systematic or a single non-deterministic draw.
- `365a889c`'s technique-name fix needs one more confirmation round.
- Logic Correctness remains single-rater, now scored under a corrected
  scope boundary that itself only exists as of §4N — doubly valuable to
  get independent verification on at this point.
- The Azure AI Foundry key rotation remains unconfirmed.

---

## Failure Taxonomy — every recurring class found across §4–§4O

A standing, cross-round reference (not a chronological log — see §4–§4O for
that). Every recurring failure class found across this entire AST-era
hardening arc, what closed it (a validator rule, a prompt fix, an
orchestration fix) or why it's documented as out-of-scope instead. Built
from the qualitative trace notes kept informally throughout §4K–§4O.

| # | Failure class | Example case(s) | Resolution | Status |
|---|---|---|---|---|
| 1 | `count()`/`dcount()` threshold trivially true (≤1) | original `DEGENERATE_THRESHOLD` find, §1 | `DEGENERATE_THRESHOLD` validator check | Closed |
| 2 | Aggregation present with no time bound | §4K | `MISSING_TIME_WINDOW` validator check | Closed |
| 3 | `time_window` not valid ISO 8601 | §4K | `INVALID_TIME_WINDOW` validator check | Closed |
| 4 | Aggregation function missing its required field | §4K | `AGGREGATION_MISSING_FIELD` validator check | Closed |
| 5 | `percentile` missing/out-of-range N | §4K, `4e3af8e3` | `INVALID_PERCENTILE_VALUE` validator check | Closed |
| 6 | Two aggregations in one `summarize` sharing a `result_alias` | §4K | `DUPLICATE_AGGREGATION_ALIAS` validator check | Closed |
| 7 | Hallucinated field reference inside an `ExtendStage` expression | §4K | Field-reference extraction + `FIELD_NOT_FOUND` in the `extend` branch | Closed |
| 8 | Hallucinated KQL function name inside an `ExtendStage` expression | `c4956c0b` (`array_avg`, `array_stddev`) | `UNKNOWN_FUNCTION_IN_EXPRESSION` + ~120-entry known-function whitelist | Closed |
| 9 | A real aggregation function (`stdev`, `count`, ...) called inside `extend` instead of `summarize` | `8717e498-original` | `AGGREGATE_FUNCTION_IN_EXTEND` validator check (§4N) | Closed |
| 10 | `FilterGroup` whose conditions are all negated, different values (always true) | `5b6ae038` variants | `TAUTOLOGICAL_FILTER_GROUP` check, variant 1 | Closed |
| 11 | `FilterGroup` with a direct complementary operator pair (`X or not-X`) | found live, §4K round 4 | `TAUTOLOGICAL_FILTER_GROUP` check, variant 2 | Closed |
| 12 | Required-together conditions wrongly OR'd in a `FilterGroup` instead of AND'd as plain filters | `5b6ae038` (sdelete flags) | Worked example + explicit AND-vs-OR guidance (§4B→§4N, restored each migration) | Closed (semantically valid IR — can't be structurally detected without ground truth, so prompting is the only lever) |
| 13 | `(A and B) or (C and D)` — disjunction of conjunctions — structurally unsupported | `a61e9fc1` | New `AndGroup` schema construct + worked example (§4O) | Closed |
| 14 | `source_table` chosen from surface wording, not technical content (DNS/HTTP/Process/File mix-ups) | `b35f6633`, `a59ba76c`, many others | Keyword-anchored disambiguation, moved upstream into the Extraction Agent (§4P) | Mostly closed — residual is Cause 1 (missing info), not this |
| 15 | `likely_event_type` framed as attacker technique/outcome, not technical category | `61988db3` ("File Wiping") | Extraction Agent framing guidance (§4K round 3) | Closed |
| 16 | Invented literal value with no basis in the input (malware name as a username, fabricated path) | cited by name in this round's request | New provenance **warning** (§4P) — advisory, not blocking; see false-positive-rate note in §4P | Partially closed — advisory only by design |
| 17 | Invented command-line flags / tool syntax not given in the input | `5b6ae038-original` | Extraction Agent: recall a *named* tool's real documented syntax (§4N) | Closed |
| 18 | MITRE technique name misread as literal log content (e.g. "Signed" from "Signed Binary Proxy Execution") | `365a889c-original` | Extraction Agent guidance (§4O) | Partially closed — confirmed improved, not eliminated |
| 19 | Invented extra `group_by` dimensions not asked for (fragments a volume count) | `43c2832e-original` | Prompt guidance (§4O) | Open — inconsistent, needs a worked example |
| 20 | Missing one field of a required multi-field `group_by` ("per X/Y pair") | `8717e498` | Schema-mutation guidance + "check all 3 places" rule (§4K, §4N) | Partially closed — improved, not fully reliable |
| 21 | Repair loop never validates its own last rebuild (off-by-one) | §4I | Orchestration fix: `range(max_attempts)` → `range(max_attempts + 1)` | Closed |
| 22 | Constraint-traceability check anchors only on raw `SummarizeStage` aliases, missing `TopStage.limit`/`percentile`/`ExtendStage`-derived fields | `b35f6633`, `4e3af8e3`, `8717e498` (3 separate instances of the same root mechanism) | `_has_matching_non_filter_number` + widened `_collect_aggregation_aliases` (§4L, §4N) | Closed |
| 23 | "Event A, then a *different* specific event B, same entity, within a window" — no construct distinguishing event *identity* from a magnitude comparison | `4500a2ff` | New worked example (§4O) | Closed |
| 24 | Free-text/hallucinated `source_table` produces a confusing downstream `FIELD_NOT_FOUND` instead of diagnosing the real problem | §4K | `INVALID_SOURCE_TABLE` validator check | Closed |
| 25 | Numeric list filter values (`in (139, 445)`) crash the compiler | §4K | `kql_literal`/`_scalar_literal` fix | Closed |
| 26 | `JoinStage.right_pipeline` typed `Any` lets a malformed nested pipeline crash the validator instead of failing cleanly | §4K | Forward-ref type + `model_rebuild()` | Closed |
| 27 | Chaining two `summarize` stages with the *same* wide `time_window` collapses to 1 row/entity, making `stdev()` silently always 0/null | `8717e498-original` | Prompt guidance: first stage needs a finer bucket (§4O) | Closed |
| 28 | A filter value that *looks* like a KQL function call (`"ago(1h)"`) but is compared as literal text, never evaluated | `b35f6633-casual`, `813ccf3b-casual` | `FUNCTION_CALL_AS_LITERAL_VALUE` validator check (§4O) | Closed |
| 29 | True row-level inter-arrival-time computation (`prev()`/`serialize`) | `c4956c0b` | Documented out-of-scope — confirmed via direct GT-query scan (§4N), not just asserted | Out of scope (single occurrence in 81 pairs) |
| 30 | `mv-expand` unpacking multiple parallel `make_set` columns after one `summarize` | `c99cf650` | Documented out-of-scope | Out of scope (single occurrence in 81 pairs) |
| 31 | Original Microsoft doc-string assumes the reader also sees the KQL, so the NL never states the threshold/field/window the query actually uses | `61988db3-original`, `a59ba76c-original`, `813ccf3b-original`, `43c2832e-original`, `5b6ae038` (pre-§4N) | **Not fixable by prompting — a dataset property.** See the input-completeness stratification (§4P) | Documented as Cause 1, not a gap |

**Reading this table**: rows 1–13, 21–28 are validator rules or orchestration
fixes — structural, deterministic, and covered by the regression-test
inventory (`tests/unit/test_validator_inventory.py`). Rows 14, 15, 17, 23
are upstream prompt/architecture fixes confirmed closed by repeated live
trials. Rows 16, 18, 19, 20 are genuinely still open — either
advisory-only by design (16) or inconsistent across paraphrases (18–20)
and likely needing a dedicated worked example each, the one pattern that
has reliably closed every other prompt-fixable gap in this project. Rows
29–30 are real IR limitations, confirmed structurally absent rather than
just believed absent. Row 31 is the dataset-property class — see §4P for
why this is a finding about input quality, not a model failure.

---

## 4P. Two causes, attacked with the right tool each; repair-loop
     specificity; documentation now matches shipped code exactly

Direct response to a request to treat Logic Correctness's ceiling as two
separable causes (input completeness vs. genuinely fixable event-type/
literal confusion) and attack each with the matching tool, plus close the
remaining repair-loop and documentation-debt items.

### Cause 1 — input completeness, stratified and reframed as a finding

Every `-original` text was classified, independent of its actual scoring
outcome, into **self-contained** (states the concrete technical specifics
the ground truth actually checks) or **under-specified** (a doc-string
written assuming the reader already sees the KQL — §4C's original
finding, generalized). 2 of 13 in-scope originals are self-contained
(`365a889c`, `8717e498`); the other 11 are under-specified — none state a
number, an enumerated list, or a distinguishing technical detail the
ground truth actually keys on. `-casual`/`-sop` are self-contained by
construction (they were paraphrased *from* the ground truth, not from the
original doc-string) for all 13 rules.

Scored on the freshest live run (below), by stratum:

| Stratum | n | Logic Correctness |
|---|---|---|
| Self-contained (2 originals + all 26 casual/sop instances) | 28 | **22/28 ≈ 78.6%** |
| Under-specified (11 originals) | 11 | **7/11 ≈ 63.6%** |

A real, ~15-point gap — this is the expected shape of Cause 1, not noise.
But raw stratification still conflates two different things: a failure
*caused by* missing information, and a failure that happens to land on
an under-specified case for an unrelated, separately-tracked reason.
Controlling for that: of the 4 raw failures in the under-specified
bucket —
- `61988db3-original` and `b35f6633-original` are genuine Cause-1
  failures — the event type is **structurally undeterminable** from the
  text (no LOLBin name, no mention of DNS anywhere at all).
- `43c2832e-original`'s failure is Cause 2 (taxonomy #19,
  over-fragmented `group_by`) — the text states "403 errors from
  clients" perfectly adequately; the bug is unrelated to what's missing.
- `4e3af8e3-original` failed by **not completing at all** this run
  (`MAX_REPAIR_ATTEMPTS_EXCEEDED`) — non-determinism, not an
  interpretation forced by missing information.

**So only 2 of 13 under-specified instances are attributable to missing
information itself.** Framed as the request asked: this is evidence the
IR faithfully reflects input quality, not a gap to close — no prompt or
architecture change can recover "the actual destination port standards"
or "this is about DNS" from text that never states either. The dataset's
own `-casual`/`-sop` paraphrases already demonstrate this directly: the
*same* underlying detections, given a self-contained description, score
78.6%, close to (and statistically indistinguishable at this n from) the
self-contained baseline the architecture should actually be judged on.

### Cause 2 — moved upstream, with keyword anchoring, plus a new bug found and fixed live

`likely_event_type` was a loose descriptive phrase ("process execution",
"DNS query") that `run_with_repair` looks up *as a dictionary key* into
the ASIM schema. A loose phrase never matches a real key — schema
narrowing was **silently falling back to the full field union on
essentially every request**, confirmed directly: `extraction.
likely_event_type in asim_schema` was `False` for every traced case
before this fix. Moved the keyword-anchored disambiguation rules
(previously only in the IR Builder's prompt) upstream into the
Extraction Agent, requiring one of the 7 exact ASIM type names. Live
check, 6/6 cases now resolve to an exact key. The IR Builder keeps the
same rules as a fallback, not the primary path.

**A genuinely new, well-scoped bug found scoring this round's live
results, fixed the same round:** `7b3ed03a`'s ground truth needs `(has
"user" or has "group") AND (has "/do" or has "/domain")` — an AND of two
independent OR-sets, the mirror image of the OR-of-AND-pairs pattern
`AndGroup` already closed. This needed no schema change at all — a
`WhereStage`'s filter list is already an implicit AND, so two separate
`FilterGroup` entries in one `WhereStage` already expresses it. The model
was instead flattening both OR-sets into one shared `FilterGroup`,
turning the AND into an OR (satisfied by "user" alone, no `/domain`
needed — a materially broader, wrong detection). Added a worked example
distinguishing the two patterns explicitly. **Live re-test: 6/6 trials
correctly use two separate AND'd OR-groups** (0/6 before).

A literal-value provenance check (flagging a `Filter.value` string absent
from the input and not a known enum) was also added as an **advisory
warning**, not a hard error — deliberately. An empirical trial run found
only 1 of 11 flagged values was a genuine invented literal (a fabricated
`$Recycle.Bin` path); the rest were legitimate recalled domain knowledge
(a named tool's real flags, a DNS RCODE, a `.exe` suffix) a hard error
would have wrongly rejected. Two cheap refinements (a DNS-RCODE
exclusion list, suffix-aware matching) closed 3 of those 10
false-positive sources directly; the rest is an accepted, documented
trade-off, not a bug.

### Repair loop — confirmed, then sharpened

- **Temperature escalation**, confirmed firing correctly post off-by-one
  fix via the existing `test_temperature_escalation_only_fires_on_a_
  genuine_consecutive_repeat` regression test (deterministic, exercises
  the exact current code path). No case in this session's live traces
  ever needed it — the model rarely repeats an *identical* mistake twice
  in a row now, which is itself a sign of how much more specific the
  guidance has become; the mechanism is verified correct, not idle code.
- **Every `FIELD_NOT_FOUND` suggestion now carries a value-type hint**
  alongside the closest-match field name (e.g. "DstPortNumber (expects a
  port number, e.g. 443)"), derived from ASIM naming conventions
  (`MASTER_PLAN_v2_ast.md` §15.3) rather than a hand-maintained per-field
  lookup table that would inevitably go stale.
- **Repair prompts now include the previous IR's best-effort compiled
  KQL**, not just the structured JSON error — `generate_kql()` never
  checks field validity, only structural shape, so it can render a
  preview even for an IR that just failed validation. Sometimes the
  rendered query makes a mistake obvious in a way the raw JSON doesn't.

### Documentation — now matches shipped code exactly, with insurance against drift

`architecture_v2_ast.md` and `MASTER_PLAN_v2_ast.md`'s validator tables,
Extraction Agent prompt sketch, and Repair Loop pseudocode all updated to
match the current code exactly (15 hard-error types, 1 advisory warning,
`AndGroup`, the upstream `likely_event_type` move, `compiled_kql_so_far`).
The insurance against this drifting out of sync again, the same way it
did once already (§4K): `tests/unit/test_validator_inventory.py`
cross-checks a curated list of "every error type + a minimal input that
fires it" against every literal `error_type="..."` string actually
written in `src/ir_engine/ir_validator.py` — adding or removing a check
without updating the inventory now fails the suite immediately.

### Live results

| Metric | §4O | §4P |
|---|---|---|
| Completion/SVR | 93.3% | 93.3% (stable) |
| FVR | 91.1% | 91.1% (stable) |
| RRR | 85.0% | 85.0% (stable) |
| Per-tier | 9/9, 8/9, 25/27 | 9/9 simple, 8/9 moderate, 25/27 complex |
| Logic Correctness (broadened scope, raw) | 79.5% (31/39) | 74.4% (29/39) — within this study's documented noise band |
| Logic Correctness, self-contained input | — | **78.6% (22/28)** |
| Logic Correctness, under-specified input | — | **63.6% (7/11), only 2/11 attributable to missing info itself** |

148 unit + integration tests (up from 142), all green; 3 live e2e tests
pass separately.

### What's still open

- `bd89c7a0-casual` and `43c2832e-original` — still inconsistent,
  unchanged from §4O; the over-fragmented-grouping fix has not reliably
  taken hold on this specific case across 3 rounds now.
- `8717e498-original`'s stdev-based interpretation found a *third*
  distinct way to be subtly wrong this round (grouping by raw
  `TimeGenerated` alongside its own bin, degenerating the per-day count) —
  the join-based interpretation (when the model reaches for it) is
  reliable; the stdev-based one still is not, after three different
  failure modes across three rounds.
- `4500a2ff-casual` chose `FileEvent` over `ProcessEvent` this round — a
  genuine ambiguity in that specific paraphrase's wording ("exported...
  then deleted") that a future round should look at, distinct from the
  sequential-event *pattern* itself, which fired correctly even on the
  wrong table.
- The `7b3ed03a` AND-of-two-OR-sets fix is confirmed live (6/6) but not
  yet re-confirmed in a full 45-pair run.
- Logic Correctness remains single-rater. The input-completeness
  stratification is itself a methodological advance worth independent
  review, not just the headline number.
- The Azure AI Foundry key rotation remains unconfirmed.

---

## 4Q. Answering "is this just rule-based?" by building the one genuinely
     agentic check the pipeline never had — and measuring it honestly

Direct response to a pointed, fair question: given how much of this
session's work has been deterministic validator checks and pattern-
matched worked examples, is this system actually agentic, or has it
quietly become a pile of rules?

### The honest answer

It's a deliberate hybrid, and the split itself is the research design,
not an accident. The generative core (Extraction Agent, IR Builder
Agent) is genuinely agentic — real LLM reasoning over natural language,
self-correcting via structured feedback. The validator
(`ir_validator.py`) is deliberately, 100% rule-based, and that's correct:
whether a field name exists in a schema isn't a judgment call an LLM
should be making — a deterministic lookup is strictly better. That split
is this project's actual independent variable (does deterministic
validation + LLM repair beat raw generation?), not a compromise.

Where the fair part of the critique lands: `_COMMON_MISTAKES` has grown
to several hundred lines of specific worked examples. Every one was a
real bug, but stacking pattern-matched examples doesn't generalize to
the *next* unseen pattern. And more fundamentally: **nothing in this
entire project's history has ever used AI judgment to check semantic
correctness.** The validator checks schema/syntax; a separate
deterministic check catches threshold drift. Whether a query actually
implements what was asked — the exact dimension Logic Correctness
measures — has had zero automated feedback loop, ever. One-shot
generation, no verification, for the whole session.

### Built: a VerifierAgent — the genuinely agentic addition

`src/agents/verifier_agent.py` — given the NL description and the
compiled KQL (not the IR JSON; the rendered query is what a human would
actually review), an LLM call checks exactly three things schema
validation structurally cannot: event-type/table correctness, comparison
direction, and aggregation/grouping match. This directly operationalizes
the same 3-point rubric used for manual Logic Correctness scoring
throughout §4B–§4P, but as an automated, in-pipeline check instead of an
end-of-round manual pass.

### What went wrong first, measured honestly, not glossed over

Hand-validated on 7 cases (3 known-wrong, 4 known-correct, including a
live repair-loop demonstration): 6/7 correct after two rounds of prompt
refinement. Looked like a clean result. **Wiring it in as a blocking
check (rejecting and forcing repair on a negative verdict) across the
full 45-pair dataset told a completely different story:**

| Metric | No verifier | Verifier, blocking |
|---|---|---|
| Completion/SVR | 93.3% | **73.3%** (−20 pts) |
| FVR | 91.1% | **71.1%** (−20 pts) |
| RRR | 85.0% | **52.0%** (−33 pts) |

12 of 45 cases failed outright (`MAX_REPAIR_ATTEMPTS_EXCEEDED`), heavily
concentrated on exactly the join+bin temporal-correlation pattern this
session's hardest-won capabilities depend on (`4500a2ff`, `8717e498`,
`4e3af8e3` — three separate constructs, all using a constant-key or
shared-bin join). The verifier systematically judged this pattern as
wrong — "binning before joining can miss a pair across a bin boundary" —
**despite an explicit prompt instruction telling it to be lenient about
exactly this**, confirmed by direct repeated testing. This is a real
structural disagreement, not a flaky prompt: the verifier is holding the
IR to a standard (true sliding-window correlation) the schema cannot
currently express, and forcing repair on it just burns the budget
without ever producing something it would accept.

**The methodological lesson, stated plainly: a 7-case hand-picked
validation set completely hid a severe, systematic failure mode that
only appeared at full-dataset scale.** This is exactly the kind of
result good practice exists to catch before shipping, not after.

### Redesigned: advisory, not blocking — the same principled call already made once this round

Same resolution as the literal-value provenance check (§4P): the
verifier's verdict is surfaced as a warning (`PipelineResult.warnings`),
never blocks success, never triggers repair, by default
(`verifier_blocking=False`). Blocking mode is kept, tested, and
documented as available but not recommended.

**Confirmed safe**: a full 45-pair run in advisory mode measured
91.1%/84.4%/81.0% — within this study's well-documented run-to-run noise
band of the no-verifier baseline (93.3%/91.1%/85.0%), and the 4 failures
present are the same intermittent hard cases (`4e3af8e3`, `c4956c0b`,
`a61e9fc1`) that fail with or without the verifier — confirmed by the
fact that advisory mode is structurally incapable of producing
`MAX_REPAIR_ATTEMPTS_EXCEEDED` on its own account.

**Confirmed valuable**: checking all 41 successful outputs from that run
directly against the verifier, **12 were flagged — and 11 of the 12 are
genuine, correct catches**, several independently rediscovering bugs
this session's manual Logic Correctness scoring had already found by
hand (the `7b3ed03a` AND/OR inversion, `4500a2ff-casual`'s wrong event
type, multiple distinct `8717e498` port-matching issues, `c4956c0b`'s
structural inter-arrival-time gap). This is a genuine, partial answer to
the long-standing "Logic Correctness needs a second rater" item (§5 item
5) — not a replacement for one, but real, independently-generated
corroboration of the bulk of this session's manual findings, essentially
free on every run.

**The one false positive found**: the verifier confidently asserted
`datetime_diff('minute', DeleteTime, ExportTime)` had its arguments
backwards — it does not; `datetime_diff(unit, a, b)` means `a - b`, and
the query was correct. The verifier had no specific knowledge of this
one function's argument convention and guessed wrong with full
confidence. Fixed with one explicit fact in its prompt; confirmed gone
on 3/3 retries.

### What's still open

- The bin-boundary disagreement is now an accepted, documented
  characteristic, not a bug being chased further — closing it for real
  would need either a genuine sliding-window join construct (a schema
  change) or recalibrating how strict "intent match" should be for
  approximations the IR already cannot avoid.
- Advisory-mode warnings are not yet read by anything downstream (no
  dashboard, no aggregation script) — they're computed and saved
  (`eval/run_comparison.py` now captures `system_b_warnings`, fixed this
  round after finding they were computed but never persisted) but not
  yet acted on systematically.
- The verifier's own false-positive rate beyond this one fix is not
  fully characterized — 11/12 on one run is a strong but single data
  point, not a calibrated reliability figure.
- `WITH_VERIFIER_BLOCKING=1` exists for future use once the underlying
  join-construct limitation is addressed, not for current use.

---

## 4R. Closing all four named residuals from §4P/§4Q, plus a fifth bug
     found live — Logic Correctness reaches its highest point yet

Direct response to "correct everything for accurate generation" — took
the four specific named residuals from the last "what needs to be
changed" list and fixed each one, tracing live and verifying live before
moving to the next.

### Four targeted fixes, all confirmed live

1. **`43c2832e-original`'s over-fragmented `group_by`.** Root cause:
   the IR Builder treated evidence/context fields (a user agent, a URL, a
   method) as ambiguous between two valid homes — `group_by` or
   `make_set()` aggregation — and kept choosing the wrong one. Added an
   explicit, forceful rule: an evidence field belongs in `aggregations`
   via `make_set()`/`make_list()`, never `group_by`; `group_by` holds
   ONLY the entity the description names as the thing being measured
   per. **Live: 4/4 trials now group by the bare entity only**, with
   every other interesting field correctly demoted to evidence.
2. **`bd89c7a0-casual`'s missing breakdown.** Root cause: the Extraction
   Agent's `action_description` was dropping the "give me a rundown of
   X" framing entirely, turning a reporting request into a bare
   detect-or-not filter with no aggregation. Added guidance to both
   agents: a "rundown/breakdown/summary/inventory" request needs a
   `SummarizeStage` report (count + min/max(TimeGenerated), grouped by
   whatever makes the report useful), with NO threshold afterward — a
   report wants everything that matched. **Live: 9/9 trials across all
   3 paraphrases now produce a real grouped report** (was 0/3 on
   `-casual` specifically).
3. **`8717e498-original`'s stdev degenerate-collapse, a third distinct
   shape.** Prompt guidance alone (added in §4O, reinforced in §4P)
   never fully stopped the model from chaining two `SummarizeStage`s
   with the SAME bin width, collapsing the spread computation to
   0/null. Closed it structurally instead: a new
   `DEGENERATE_SPREAD_OVER_SINGLE_ROW` validator check tracks the most
   recent prior summarize's exact (group_by, time_window) signature and
   hard-rejects a `stdev()`/`variance()` aggregation reusing that exact
   signature — reset across any intervening `JoinStage`/`UnionStage`
   (confirmed by a dedicated regression test not to false-positive on
   the percentile-of-aggregates pattern, which deliberately re-joins
   before reducing again). **Live: 5/5 trials now mechanically correct**
   (was 3/5 degenerate). The model still usually prefers a
   coefficient-of-variation reading over the ground truth's
   current-vs-baseline framing for this specific ambiguous original
   text — a genuine Cause-1 ambiguity, not chased further — but the
   computation it builds is no longer broken regardless of which
   reading it picks.
4. **`4500a2ff-casual`'s wrong event type.** Root cause: "exported an
   Exchange mailbox" was read as a literal file create/delete, not the
   `New-MailboxExportRequest`/`Remove-MailboxExportRequest` PowerShell
   cmdlets it actually describes. Broadened the existing named-tool
   flag-recall guidance (§4N) to cover described ADMINISTRATIVE
   ACTIONS, not just named tools — many platform actions are performed
   via one specific, well-known underlying mechanism even when the
   description never names it. **Live: 5/5 trials now correctly resolve
   to `ProcessEvent`** with the exact correct cmdlet names (was 0/5
   `FileEvent`).

### A fifth bug, found scoring the full run, fixed before finalizing

`4500a2ff-original` produced `where (MinutesBetween > 0 or MinutesBetween
<= 60)` — the sequential-event pattern's own ordering+window check,
normally two separate AND-ed `WhereStage` filters, flattened into one
`FilterGroup` with OR instead. This is a tautology: every real number
satisfies at least one side of a lower-bound/upper-bound OR when the
lower bound doesn't exceed the upper bound (-5 ≤ 60; 1000 > 0) — the
same AND-vs-OR confusion this validator already catches for negated
values and complementary operators, just for a numeric range pair. Added
a third `TAUTOLOGICAL_FILTER_GROUP` variant (`_has_tautological_range_pair`)
detecting exactly this shape, with a dedicated test confirming a REAL
gap (`X > 60 or X <= 0`, which correctly excludes a real region) is
never flagged. **Live: 5/5 trials clean** after the fix.

### Live results — the best Logic Correctness this project has measured, under either architecture

| Metric | §4P (round 3) | §4R (this round) |
|---|---|---|
| Completion/SVR | 93.3% | 91.1% (within documented noise band) |
| FVR | 91.1% | 84.4% (within documented noise band) |
| RRR | 85.0% | 82.6% (within documented noise band) |
| Logic Correctness (broadened scope) | 74.4% (29/39) | **87.2% (34/39)** |

178 unit + integration tests (up from 172), all green; 3 live e2e tests
pass separately. None of the 4 failures in this run's comparison
(`c4956c0b` ×2, `a61e9fc1-casual`, `c99cf650-sop`) are any of the cases
targeted this round — all 4 are the same intermittent/out-of-scope cases
that have failed in every recent round regardless.

**87.2% is the highest Logic Correctness this entire project has ever
measured, under either the flat `SecurityIR` architecture (peaked at
75% across ten rounds) or the AST `KqlPipeline` architecture (75% in
§4M/§4N, 79.5% in §4O, 74.4% in §4P).** Of the 13 in-scope rules, 8 now
score a clean 3/3 across every paraphrase (`5b6ae038`, `bd89c7a0`,
`4e3af8e3`, `365a889c`, `8717e498`, `a59ba76c`, `813ccf3b`, `43c2832e`)
— a majority of the dataset, for the first time.

### What's still open

- `7b3ed03a-sop` reverted to the single-OR pattern this run even with
  the worked example in place (`-casual` got it right) — improved
  reliability (1/3 → 2/3 across rounds), not full consistency.
  `_has_tautological_range_pair`'s sibling check for this exact shape
  (an AND-of-two-OR-sets collapsed into one OR) isn't structurally
  detectable as a tautology the way the range-pair bug was — it's a
  real semantic error, not a vacuous one, so a validator check can't
  catch it without ground truth to compare against.
- `61988db3-original` and `b35f6633-original` remain genuine Cause-1
  failures — the event type is structurally undeterminable from text
  that never names a LOLBin or says "DNS."
- `a61e9fc1-casual` and the two out-of-scope cases (`c4956c0b`,
  `c99cf650`) remain intermittent/structurally out of reach respectively.
- Logic Correctness remains single-rater, now at its highest-ever point
  — independent verification is more valuable here than at any prior
  round, not less.
- The Azure AI Foundry key rotation remains unconfirmed.

---

## 4S. Selective verifier blocking tried, measured, and rejected; one real
     bug found and fixed (`a61e9fc1-casual`'s root cause)

Direct continuation of §4Q/§4R, attacking the two remaining open items
from that round's list: `7b3ed03a-sop`'s persistent AND-of-OR bug (via a
plausible fix — selective verifier blocking) and `a61e9fc1-casual`'s
intermittent failure (via root-cause tracing, the same methodology that
closed every other bug this session).

### A real, fixed bug: `a61e9fc1-casual`'s `FilterGroup` min-length crash

Traced directly: the model wraps a single `AndGroup` branch in a
`FilterGroup` whenever the description only supports one concrete
example of an OR-shaped pattern (e.g. "like DNS not running on port
53" — no second app named) — but `FilterGroup` requires ≥2 conditions
by schema design (it exists only to express a genuine OR), so this is a
hard Pydantic parse failure, not a soft validation error, every single
time it happens. Added an explicit guard: when there's only one
concrete branch, skip both `FilterGroup` and `AndGroup` and use plain
AND-ed `Filter` entries directly. **Live: 5/6 trials now succeed**
(previously intermittent failures across this and prior rounds) — the
one remaining failure exhausts the repair budget making the identical
mistake repeatedly, not a new failure mode.

### Selective verifier blocking — tried, measured, and the honest result is negative

The plan: blocking on the verifier's verdict caused a severe regression
in §4Q (−20/−20/−33 points) almost entirely concentrated in one
critique category (join+bin temporal correlation, identified by a
specific keyword pattern in every false positive found). Excluding only
that category from blocking should, in theory, capture real wins like
`7b3ed03a-sop`'s AND-of-OR bug — which no structural validator check
can catch, since it's a genuine semantic error, not a vacuous tautology
— without reintroducing the regression. Implemented
(`_is_known_bin_join_false_positive`, `src/pipeline/repair_loop.py`),
tested in isolation (a true positive still blocks, the known false
positive still doesn't — both confirmed by dedicated unit tests), then
measured on the full 45-pair dataset behind `WITH_VERIFIER_BLOCKING=1`.

**The result is still net negative**: SVR 80.0% (−11.1 from the §4R
baseline), FVR 80.0% (−4.4), RRR 69.0% (−13.6). Worse, **the one case
this was specifically meant to fix, `7b3ed03a-sop`, still failed** —
this time via repair-budget exhaustion rather than ever succeeding,
meaning the verifier correctly identified the problem but the IR
Builder couldn't act on a free-text critique within 3 attempts the way
it reliably acts on a precise structured validator error. Worse still,
a **second, previously uncharacterized false-positive category**
surfaced: all 3 `8717e498` paraphrases failed this run — the verifier
holding the stdev-based interpretation (no join involved at all, so the
"bin"+"join" keyword filter never excludes it) to GT's exact
baseline-vs-current framing, an ambiguity already documented as Cause-1
in §4P, not a bug.

**Conclusion: advisory mode remains the only recommended mode.** This
isn't one keyword away from working — fixing the `8717e498` false
positive would need a third exclusion category, and there is no reason
to expect a fourth and fifth wouldn't keep surfacing the same way (a
classic whack-a-mole shape, the kind of result that's itself evidence
the underlying approach — keyword-filtered selective blocking — is too
fragile to trust, not that one more keyword would close it). The
default (`verifier_blocking=False`) was never changed during this
experiment, so nothing in the recommended path was ever at risk;
`WITH_VERIFIER_BLOCKING=1` remains available, opt-in, and now
documented with a sharper, evidence-based reason not to use it: it has
at least two distinct, independently-discovered failure modes, and the
repair loop's free-text-critique recovery rate is itself a separate,
unresolved limitation.

### What's still open

- `7b3ed03a-sop`'s AND-of-OR bug remains genuinely unresolved — neither
  a structural validator check (it's not a tautology) nor selective
  verifier blocking (measured net negative) closes it. The honest
  state: improved from the original 0/3 to an inconsistent ~1–2/3
  across rounds, with no further lever identified that doesn't cost
  more than it gives back.
- The repair loop's ability to act on a free-text semantic critique
  (vs. a precise structured validator error) is itself an uncharacterized
  weak point, found investigating this round — worth a dedicated look
  before any future attempt at blocking-mode verification.
- `8717e498`'s stdev-vs-join ambiguity is now confirmed, via the
  verifier's own independent judgment, to be a real fork in
  interpretation, not just this project's own lenient scoring call.
- The Azure AI Foundry key rotation remains unconfirmed.

---

## 4T. The held-out generalization test — measuring, not assuming, the overfitting gap

This round was driven by a five-point structured critique of the entire
project to date, in the critique's own priority order: fix the
measurement foundation first, then measure (not assume) generalization
to unseen rules, with prompt-genericization, verifier deployment, and an
abstention signal explicitly deferred until those two were underway.
Everything below is organized the same way.

### Measurement foundation (priority 1)

- **Caching by prompt hash**: added, opt-in via `LLM_CACHE_PATH`
  (`langchain_community.cache.SQLiteCache`, wired into
  `build_chat_model()` in `base_agent.py`). Deliberately NOT used during
  the replication study itself — see the code comment added at
  `base_agent.py`'s `_maybe_configure_llm_cache()` for why caching the
  first response would silently defeat the variance measurement an
  N-run study exists to produce.
- **Azure `seed` parameter**: added (`LLM_SEED` env var → `seed=` kwarg
  on `ChatOpenAI`, both `openai` and `azure_foundry` branches). Tested
  directly: 5 trials no-seed vs. 5 trials seed=42 on one case both
  produced 2 distinct outputs out of 5 — **no measurable determinism
  benefit at this sample size**. OpenAI's own documentation calls `seed`
  "best effort," and this is consistent with that — kept in the code
  since it's free and may help on some endpoints/cases, but not relied
  on as a fix for the variance problem.
- **N≥5 replication of one fixed config, median+IQR**: a real
  methodological mistake was caught and corrected mid-session here —
  the first replication run was started, and partway through (between
  its run 1 and run 2) this round's generalization-gap fixes (below)
  were committed to `extraction_agent.py`/`ir_builder_agent.py`. Because
  each replication run is a fresh subprocess that re-imports the agent
  prompts at startup, runs 1 and 2 of that first attempt were silently
  **not the same config** — exactly the kind of uncontrolled variable
  this whole measurement-rigor push exists to prevent. Caught by
  noticing run 1 (SVR 97.8) and run 2 (SVR 95.6) were both well above
  every previously-reported number for this dataset, which should not
  happen from noise alone. The contaminated run was stopped
  (`TaskStop`) and restarted clean once all edits were finished.

  **The clean restart completed all 5 runs** (`eval/results/primary/replication/`):

  | Run | SVR | FVR | RRR |
  |---|---|---|---|
  | 1 | 95.6 | 88.9 | 92.0 |
  | 2 | 93.3 | 91.1 | 88.0 |
  | 3 | 95.6 | 91.1 | 91.7 |
  | 4 | 97.8 | 88.9 | 96.0 |
  | 5 | 95.6 | 88.9 | 91.7 |
  | **median (IQR)** | **95.6 (0.0)** | **88.9 (2.2)** | **91.7 (0.3)** |

  This is the first true N≥5 same-config replication run on this
  dataset, and the result is genuinely tight — far tighter than the
  60–95%-swing variance documented earlier in this project
  (§4C/§4S) for `gpt-4.1-mini` at temperature=0. The most plausible
  reading: most of that historical swing was traced, round over round,
  to real fixable bugs (§4N's abstract lists three), and once those are
  fixed the *remaining* model-level noise on this specific dataset/
  prompt combination is genuinely small. RRR's raw range (88.0–96.0,
  an 8-point spread despite a 0.3 IQR) is the one metric still worth
  watching — driven by which specific repair-attempt path a given run's
  borderline cases happen to take, not a uniform shift.

  **Caveat that matters**: this replicates SVR/FVR/RRR — schema-level
  metrics computed automatically on every run. It does **not**
  replicate Logic Correctness, which has always been a single manual
  scoring pass per round (N=5 manual re-scoring of the same ~20 cases
  was out of scope for this session's time budget). The 87.2% Logic
  Correctness figure this round's generalization comparison uses is
  still an N=1 point estimate, even though the schema-level metrics
  underneath it are now confirmed stable.
- **Deterministic Ollama control axis**: not yet run this round — next
  up once the cloud replication study completes.

### The held-out generalization test (priority 1 — "the single most important thing")

Pulled candidates from `D:/Code_stuff/azure-sentinel`'s `Hunting
Queries/` and `Solutions/` folders (not `Detections/`, which the
existing 81-pair dataset already exhausts — re-confirmed via a fresh
pull that all 33 ASIM-eligible `Detections/` rules are already in the
verified set). 97 candidates were ASIM-eligible and not already in the
81-pair set (by `rule_id`, not file path, since path prefixes had
shifted from an earlier repo move). Sampled 40 at `random.seed(42)`,
manually curated down to **18** (discarding boilerplate "deprecated IoC
feed" duplicates and bare one-line threat-intel-correlation rules with
no real description) — a deliberate scope reduction from the
suggested 30–50, given session time, disclosed honestly rather than
rounded up.

**Predictions were written down before running** (the critique's own
requirement, to test whether the failures would be new or recurring):
~9/18 predicted clean (report/summary patterns, baseline-vs-current DNS,
simple port filters), ~7/18 predicted risky (IoC values with nothing
concrete given, CSV-referenced lists, ambiguous event types), 2/18
predicted hard out-of-scope (a top-1M-domains external lookup with no
IR construct for it; `series_decompose_anomalies`-based DGA detection,
also no IR construct).

**Result, run blind, before any fixes**: 17/18 (94.4%) schema-valid
completion — *higher* than the tuned set's completion rate. But manual
Logic Correctness scoring (the same rubric used throughout this
project) put it at **6/17 ≈ 35%** correct, against the tuned set's
87.2%. The gap between 94.4% completion and 35% Logic Correctness is
itself the headline finding: a schema-valid query that confidently
implements the wrong thing is the failure mode completion-rate metrics
cannot see, and the one this whole held-out exercise was designed to
surface.

One predicted case (the top-1M-domains lookup) failed exactly as
predicted — a clean confirmation that *some* limits are well
understood. But the critique's sharper test was: **do the failures hit
known failure classes, or new ones?** They were overwhelmingly new:

1. **Placeholder/templated fake literals** — `SrcIpAddr in ("<known IoC
   IPs>")`, `HttpUserAgent in ("known_malicious_user_agent_1", ...)`,
   `DstIpAddr in ("<IoC_IP_1>", ...)`. Three occurrences. Never seen
   across 13 tuned rules and dozens of rounds — the tuned set apparently
   never happened to ask for a value with literally nothing concrete
   given in the text.
2. **Threat-actor/APT-group names treated as literal field values** —
   `ActorUsername == "Dev-0322"`, `ActorUsername == "Mercury"`,
   `DvcHostname has "Nylon Typhoon"`. Three occurrences. Related to the
   existing MITRE-technique-name guidance (§4N-era) but that guidance
   never covered attribution labels, only technique names — a clean
   miss in the existing fix's scope, not a new category of mistake.
3. **No concept of "external"/"internal" IP** at all — `SrcIpAddr !=
   ""` substituted for "external IP connections," an always-true check
   that silently drops the one condition the description was built
   around. Never encountered because none of the 13 tuned rules used
   this framing.

This is direct, concrete evidence for the critique's core claim:
**the `_COMMON_MISTAKES` block's worked examples were largely fitted to
the 13 known cases, not generalized principles** — exactly the
predicted signature (new failure classes surfacing on unseen data, not
variations of known ones).

The balancing finding: structural patterns *did* generalize cleanly.
Breakdown/report generation (`summarize ... by <every named dimension>,
bin(...)`), the baseline-vs-current join pattern, multi-field
`group_by`, and recalling real tool names (7z/zip/rar/tar, not just the
one worked example's sdelete) all transferred correctly to brand-new
cases never seen in tuning. The overfitting is concentrated in
*literal-value grounding*, not in *structural composition* — a useful,
narrower diagnosis than "the system overfits," and consistent with how
the fixes below landed.

### Fixing the three new classes, and what that revealed about principles vs. examples (priority 2, opportunistically)

Added guidance to `extraction_agent.py` for all three: actor/group names
are attribution labels, never literal field content (mirroring the
existing MITRE-technique-name rule); an external list/feed with zero
concrete examples given should be omitted, not filled with invented
placeholders; "external"/"internal" IP maps to `ipv4_is_private(...)`,
not an empty-string check.

**First pass (principle only, no worked example) had weak, inconsistent
uptake** — re-tested on the 4 specific failing cases (3 trials each):
the actor-name fix worked 3/3 for `Dev-0322` but 0/3 for `Mercury`; the
placeholder fix didn't change behavior at all; the external-IP fix
didn't change behavior at all. **Second pass, adding one concrete
worked example per principle to `ir_builder_agent.py`** (mirroring this
project's established pattern from every prior round): 3 of 4 classes
went to 3/3 clean immediately (`Dev-0322`, the placeholder case, the
external-IP case via `ExtendStage` + `ipv4_is_private`); `Mercury`
*still* didn't reliably trigger the actor-name recognition even with
the worked example present (likely because "Mercury" is also a common
English word/planet/element, unlike the clearly attribution-styled
"Dev-0322" or "Nylon Typhoon" — a real, narrower limit, not a failure of
the fix).

This is a direct, fresh data point on the critique's item 2 (principles
vs. examples): **a bare principle was not enough to reliably redirect
behavior on these new classes; principle + one concrete worked example
was.** This doesn't contradict the critique's hypothesis that principles
generalize better than memorized examples — both fixes here used a
principle, and the one with an example attached worked far more
reliably. The open question item 2 actually poses (does a
*compressed*, principle-led prompt do better on a blind set than the
current accretion of examples) remains untested; this round's evidence
says examples still carry real, non-optional weight per principle, at
least for "what to do instead," not just "what's wrong."

**Re-running the full 18-case held-out set after the worked-example
fix** showed both the expected improvement and a sharp, instructive
caveat about variance: 10/17 ≈ 58.8% Logic Correctness (excluding the
1 correctly-identified out-of-scope case), up from 6/17 ≈ 35% before
the fix. But comparing case-by-case against the pre-fix run, on
**identical code**, run-to-run noise moved individual cases in *both*
directions: `c6608467` (URL file-extension matching) regressed from a
clean `has_any`-based OR check to an AND-chain of `contains` calls that
can never match any real URL — a recurrence of a bug category this
project specifically fixed and worked-exampled back in §4F/§4G, on the
exact same prompt that fixed it. `bb30abbc` and `50eb4cbd` improved
between the two runs with no code change at all. **The 23.5-point
swing between the two held-out runs cannot be cleanly attributed to the
fix alone** — it's confounded with the same temperature=0 variance the
measurement-foundation work (above) exists to quantify. Both numbers are
reported here rather than picking the more flattering one, which is the
entire point of this round's priority ordering.

### Verifier calibration against fresh, never-tuned-against data (priority 3, opportunistic)

Rather than reconstruct old in-session manual scores from memory (a
weaker, retrospective source), the held-out set's outputs were scored
fresh and blind, then checked against the `VerifierAgent`'s independent
judgment on the same 17 cases — genuinely never-tuned-against data on
both sides, a stronger calibration than reusing memory of past rounds.

**Result**: TP=6, FP=5, FN=1, TN=5 → precision 0.55, recall 0.86,
raw agreement 0.65 (`eval/results/verifier_calibration.json`). Read
naively, this looks weak. Reading the 5 "false positives" individually
changes the picture:
- One (`bb30abbc`) was the verifier catching a real AND/OR conjunction
  bug this project's own manual scoring missed on first pass — a
  verifier win, not a false positive.
- One (`6a4dbcf8`) is a genuine philosophical disagreement, not a
  verifier error: this project's manual rubric treats "honestly omit a
  filter that can't be grounded" as a pass (per the new placeholder-
  avoidance guidance above), but the verifier, with no concept of
  deliberate abstention, reads any unimplemented part of the
  description as a mismatch. This is the clearest evidence yet for the
  critique's item 4 (an explicit abstention signal) — the verifier is
  already, independently, hitting the exact boundary item 4 asks the
  pipeline to formalize.
- Two (`50f0cdfb`, `9b72769e`) are defensible strict readings of
  genuinely approximate aggregation choices — closer to "pickier than
  this project's leniency threshold" than "wrong."
- One (`50eb4cbd`) independently flagged the exact webshell-creation
  vs. -execution event-type ambiguity this round's own pre-registered
  predictions called out before running blind — convergent evidence
  from two independent judges (this project's predictions and the
  verifier) on a real, pre-identified ambiguity.

The one false negative (`67775878`) is the verifier's real, fixable
gap: it did not flag a placeholder-value IoC list at all, because its
own system prompt (`verifier_agent.py`) predates this round's
placeholder-hallucination finding and has no instruction to look for
it.

**Attempted the fix, measured it, reverted it.** Ported the same
actor-name/placeholder-value guidance into `verifier_agent.py`'s system
prompt and re-ran the calibration on the unchanged held-out outputs.
Result: precision 0.45, recall 0.71, agreement 0.53 — worse on every
axis than the pre-edit baseline (0.55/0.86/0.65), and the original
target case (`67775878`) was *still* a miss. Re-running the calibration
a third time, after reverting back to the original prompt, produced yet
a *third* distinct result (precision 0.50, recall 0.71, agreement
0.59) — confirming the verifier's own judgment is subject to the same
temperature=0, single-run noise documented everywhere else in this
project, and that a one-shot before/after comparison of a prompt edit
is not sufficient evidence either way. **The edit was reverted**
(reverting to the documented, already-measured baseline is the safer
default absent a properly N≥5-replicated comparison), and the honest
conclusion is that this specific fix is unproven, not disproven —
re-test with real replication before trying again.

### What's still open after this round

- **The deterministic-Ollama control axis was run, with a clear but
  limited result.** `qwen3.5:4b` failed all 9 trials across 5 distinct
  cases (the determinism check case ×3, the 4 bug-verification cases
  ×2 each) — every attempt returned an empty completion that fails
  `KqlPipeline`'s `source_table` validation. But the 3 repeated trials
  on the identical case produced byte-identical (empty) output every
  time — genuine, confirmed determinism, exactly the property this axis
  was added for. The practical problem: at a ~0% (consistent with the
  already-documented ~10%, since 0/9 is not a surprising draw from a
  true 10% rate) baseline success rate on this IR Builder prompt, there
  is a floor effect — there is no room for a targeted prompt fix to show
  a *visible* effect on this model, since it essentially never succeeds
  regardless of which fix is or isn't present. The deterministic axis is
  confirmed usable in principle; it just is not informative for *this
  round's specific* literal-grounding fixes, since the model fails
  before ever reaching the point where those fixes would matter.
- Item 2's actual proposed experiment — compressing `_COMMON_MISTAKES`
  into principles and A/B testing against the current example-stack on
  both the tuning and held-out sets — was not run; this round's
  incidental finding (bare principles had weak uptake without an
  example) is suggestive but is not that experiment.
- Item 3's other two proposed changes (verifier-as-reranker over 3
  generated candidates; mapping verifier critiques to the existing
  structured-error vocabulary so the repair loop can act on them) are
  not implemented.
- Item 4 (a first-class confidence/abstention output) is not
  implemented — though this round found independent, convergent
  evidence (the verifier calibration's `6a4dbcf8` case) that the
  pipeline is already silently making abstention-shaped decisions
  (omitting an ungroundable filter) with no way to surface that choice
  as anything other than indistinguishable from a wrong answer.
- The `Mercury` actor-name case is a known, narrow residual: the
  worked-example fix did not reliably generalize to a codename that is
  also a common English word, unlike clearly attribution-styled names.
  Not chased further this round (the project's established standard
  for when a residual costs more to chase than it returns). **Closed in
  §4U below** — root-caused to the wrong component and fixed there.
- The Azure AI Foundry key rotation remains unconfirmed.

---

## 4U. Closing the held-out gap further: four targeted fixes, a new
     abstention signal, and the held-out number nearly tripling

Direct continuation of §4T, working through its open residuals one at a
time with the same live-test-and-fix discipline as every other round,
plus one new capability (the abstention/caveats signal) that the
critique's item 4 and the verifier-calibration finding both pointed at.

### Four bugs found and fixed, each verified at 5/5 or 10/10 clean trials

1. **`c6608467`'s OR-list regression — the most concerning finding,
   since it broke a pattern this project has worked-exampled multiple
   times before.** "URLs containing file types such as .ps1, .bat,
   .vbs, .scr etc." was producing four AND-chained `Url contains ".ext"`
   filters 4/5 trials — a query requiring all four extensions in the
   same URL simultaneously, which silently never fires. Root cause:
   every existing OR-list rule keyed off an explicit "or" word; "such
   as X, Y, Z, etc." is the more common real-world phrasing for the
   exact same enumerated-alternatives meaning, with no "or" anywhere,
   and nothing covered it. Added a worked example for this phrasing
   shape specifically. **5/5 clean after the fix** (was 1/5 before).
2. **`70e2a349`'s watchlist-threshold confusion.** A threshold sourced
   from a named external watchlist (no concrete number given) was
   causing the model to try constructing a `{"type": "watchlist", ...}`
   reference object for `Filter.value` — not a valid shape, since
   `Filter.value` is a literal only. The resulting repair-loop churn
   landed on fabricated literal ports (80/443/22/3389, never mentioned)
   or a self-defeating `leftanti` self-join. Added explicit guidance:
   treat an externally-sourced, no-number-given value exactly like the
   existing "no concrete number → omit" rule. **5/5 clean after the
   fix** (was inconsistent — omission, fabrication, and a parse failure
   all appeared across 5 trials before).
3. **The `Mercury` actor-name residual, closed.** §4T's fix added the
   actor-name-is-not-data principle to `extraction_agent.py` and a
   worked example using "Dev-0322" to `ir_builder_agent.py` — but the
   *IR Builder's own* worked example, the component that actually
   constructs the filter, never included a case where the actor name is
   also an ordinary English word. Adding a second worked example to
   `ir_builder_agent.py` using "Mercury" specifically — explicit that
   the test is WHO the sentence credits the action to, not whether the
   name looks unusual — fixed it. **5/5 clean** (was 0/5 even with the
   §4T fix in place, including in a verbatim worked example one
   component upstream).
4. **The "known IoC" placeholder case, closed for the bare phrasing.**
   §4T's fix covered an external list named with a concrete source
   (a CSV file) but not the bare phrase "a known IoC" with no source
   named at all. The bare phrasing was producing either fabricated
   placeholder strings or a semantically-empty `in ()` filter (matches
   nothing, ever — looks like a working IoC check and silently never
   fires, which is worse than no filter). Added a third worked example
   covering this exact bare phrasing. **10/10 clean across both
   affected cases** (was inconsistent — clean omission, empty-list
   degenerate, and placeholder fabrication all appeared across the 10
   trials before).

### A new capability: self-disclosed abstention (`KqlPipeline.caveats`)

Critique item 4 asked for a first-class confidence/abstention signal;
§4T's verifier calibration found independent, concrete motivation for
it (the `6a4dbcf8` case — the model already silently omits ungroundable
filters, and the verifier, with no abstention concept, can't tell that
apart from a bug). Implemented as a new optional field:

- `KqlPipeline.caveats: List[str]` (`ir_schema.py`) — populated by the
  IR Builder itself, not inferred after the fact, whenever it omits a
  filter per any of the "omit, don't invent" worked examples already in
  its prompt. One new instruction in `_COMMON_MISTAKES` ties this
  directly to those existing examples rather than introducing a new,
  separate concept to learn.
- `generate_kql()` (`compiler.py`) renders every caveat as a leading
  `// CAVEAT: ...` comment line in the generated KQL itself — visible
  directly in the artifact, not just in surrounding metadata. Collected
  recursively through any join's `right_pipeline` too, so a caveat
  placed on a nested pipeline by mistake still surfaces instead of
  silently vanishing.
- `PipelineResult.caveats` (`repair_loop.py`) surfaces the same list
  structurally, kept separate from `warnings` (verifier-sourced
  critiques of the result) since this is the model's own account of a
  decision it made, not an external critique.
- 4 new unit tests in `test_templates.py` cover: no caveats → no
  comment lines; single and multiple caveats render correctly; a
  caveat on a nested join pipeline still surfaces at the top instead of
  being silently dropped.

**Live behavior exceeded the narrow goal.** Every "omit, don't invent"
case now produces an accurate caveat (e.g. "no concrete IoC values were
given for the source IP check, so no filter on SrcIpAddr was added").
One case generalized further than any specific worked example asked
for: `01191239` (the series-decompose DGA-detection case, a known
structural IR gap with no `make-series` construct) spontaneously
produced "series decompose anomaly detection and baseline comparison
cannot be expressed in this IR, so only raw counts per client IP are
reported" — the model identifying and disclosing the exact IR
limitation this project had independently diagnosed, with no worked
example ever written about `make-series` or anomaly detection
specifically. This is the abstention signal doing its actual job: a
schema-valid simplification that previously looked like a confident
(wrong) answer now visibly flags itself as a known-incomplete one.

### Held-out set re-measured: 35% → 58.8% → 82.4%, replicated twice

Re-ran the full 18-case held-out set twice after all four fixes plus
the caveats feature (`eval/results/held_out_raw_run3.jsonl`,
`..._run4.jsonl`). Both runs scored **14/17 ≈ 82.4%** Logic Correctness
(excluding the 1 correctly-identified out-of-scope case) — the same
number twice, a real signal of stability rather than a lucky draw,
unlike §4T's two pre-fix runs which swung 23.5 points on identical code.

The 3 residual failures in both runs are the same cases, and none of
them are prompt bugs:
- `2d1a3e86` — needs the actual CVE-2022-29972 exploit's specific
  parent-process names and command-line tokens, which are not general
  knowledge and not given in the text. A knowledge-recall limitation,
  not a logic error.
- `f090f8f4` — needs the actual Internet Explorer registry paths the
  malware modifies; the available description never names them. The
  same Cause-1 (missing information) class documented since §4P.
- `01191239` — needs real `make-series`/`series_decompose_anomalies`
  support, which the IR structurally does not have (the same class as
  the already-documented `c4956c0b` exclusion) — now honestly
  self-disclosed via `caveats` rather than silently approximated.

### Confirmed: the caveats feature doesn't regress the tuned set, and surfaces real value there too

A live run on the tuned set with all four bug fixes and the caveats
feature in place: **SVR 97.8%, FVR 88.9%, RRR 95.7%** — every figure
falls inside the variance band the §4T N=5 replication already
established (SVR 93.3–97.8, FVR 88.9–91.1, RRR 88.0–96.0), confirming no
regression. Bonus finding: `caveats` fired organically on 7/45 tuned-set
cases too, not just the held-out set, with accurate, previously-invisible
disclosures — e.g. `61988db3-original` flagging that no concrete
malware process names were given so a generic LOLBin filter was used;
`4e3af8e3-casual` flagging its own percentile-threshold interpretation;
`c4956c0b-sop` flagging a missing inter-arrival-time literal;
`8717e498-casual` flagging an assumed 1-day/14-day window split. One
case (`c99cf650-original`) is a softer win: it still substituted a
fabricated extension list rather than omitting per the worked examples,
but now visibly discloses doing so ("used as a placeholder") instead of
presenting it silently — an improvement in honesty even where the
underlying choice itself wasn't fully corrected.

### What's still open after this round

Carried forward and substantially addressed in §4V below: the verifier's
placeholder blind spot (re-attempted with a properly-targeted
methodology this time) and the structured-error bridge (item 3). Item 2
(principle-compression A/B test) and item 3's reranker proposal remain
not implemented. The Azure AI Foundry key rotation remains unconfirmed.

---

## 4V. A proper N=5 held-out replication, a threat-intel-label fix, a
     methodological catch in the verifier's own test harness, and a
     validated verifier fix using a corrected experimental design

Direct continuation of §4U, working through its "what's still open"
list plus one new fix the user specifically asked for (item 1's
threat-intel-recall gap).

### A third instance of the labeling principle: CVE/vulnerability IDs

`2d1a3e86` (the CVE-2022-29972 command-injection case) was producing
`CommandLine contains "CVE-2022-29972"` — the model echoing the
vulnerability identifier itself as if it were literal command-line
content, which no real exploit ever does. This is a third instance of
the exact pattern already fixed twice this session (MITRE technique
names in §4N, threat-actor names in §4T) — a CVE ID is a reference
label for WHICH vulnerability, never literal log data. Added the same
principle-plus-worked-example pair to both `extraction_agent.py` and
`ir_builder_agent.py` (the latter specifically, after the `Mercury`
lesson that the component which actually builds the filter needs its
own example, not just the upstream extraction step's). **5/5 clean
after the fix**: the model now drops the CVE ID and either keeps the
genuinely-named affected component (e.g. `CommandLine contains
"IntegrationRuntime"`) or discloses via `caveats` that the exploit's
real technical signature isn't recoverable from the text — instead of
confidently searching for a string that will never appear in a real
command line.

### Held-out Logic Correctness, properly replicated at N=5 for the first time

Ran the full 18-case held-out set 5 independent times (with the CVE fix
and everything from §4U in place) and manually scored Logic Correctness
on each. Completion varied 83.3–94.4% across runs (16, 15, 16, 17,
17 out of 18) — confirmed, via 8 fresh isolated trials of the one
new failure (`50f0cdfb`), to be ordinary stochastic repair-budget
exhaustion (0/8 failures in the isolated re-check), not a new
regression from prompt growth.

**Logic Correctness: median 82.4%, IQR 5.9 points (range 76.5–82.4%
across the 5 runs).** This is the first N≥5-replicated Logic
Correctness figure this project has ever produced for the held-out set
— every number before this (87.2% tuned, 82.4%/35%/58.8% held-out) was
a single manual-scoring pass. The median (82.4%) matches §4U's two
single-run measurements exactly, which is reassuring, but the IQR
(5.9 points) is the actual new information: this project's own
non-negotiable standard ("you cannot claim X > Y as improvement when
your run-to-run noise band is wider than the gap") now has a real
number to apply. The two within-run swing cases were `50f0cdfb`
(repair-budget exhaustion, 1 of 5 runs) and `9b72769e` (same, 1 of 5
runs) — both isolated, ordinary noise, not a recurring defect.

### A methodological catch in the verifier-calibration test harness itself

Re-attempting the verifier calibration N=5 surfaced a subtler problem
than expected. All 5 runs against `held_out_raw_run4.jsonl` produced
*byte-identical* aggregate confusion-matrix numbers (TP=5, FP=6, FN=2,
TN=4) — which looked, at first, like genuine verifier determinism.
Diffing the per-case verdicts instead of trusting the aggregate showed
this was wrong: 2 of 17 cases (`70e2a349`, `01191239`) flipped their
individual True/False verdict between runs, and the two flips happened
to land on opposite sides of the confusion matrix, cancelling out in
the aggregate. **Identical aggregate numbers across N runs is not
proof of low variance — it can hide real per-case noise that
cancels.** This generalizes the project's own "N=1 is not enough"
lesson one level deeper: even N=5 aggregate stability needs a per-case
diff to confirm it isn't coincidental cancellation.

Separately, a second, unrelated bug was found in the calibration
harness itself: the `manual_verdict` labels being compared against had
gone stale. §4U's fixes made `e2559891`, `70e2a349`, `c6608467`, and
`67775878` genuinely correct in `held_out_raw_run4.jsonl`'s actual
output, but the calibration script was still comparing against labels
written for an *earlier* run's different (buggier) content for those
same `rule_id`s — manufacturing artificial disagreement that had
nothing to do with the verifier's quality. Re-derived the labels fresh
against `run4`'s actual current KQL before re-measuring.

### The verifier's placeholder blind spot, re-attempted and validated with a corrected experimental design

§4T's single before/after aggregate comparison (which this round's
finding above shows was always going to be too noisy to trust) is
replaced with a properly isolated test: fixed, known placeholder-bug
KQL paired with its description, run 5 times each through the verifier,
before and after the fix, plus a separate negative-control case (a
genuine, honest omission) to check for new false positives.

**Before** (original verifier prompt): 0/5 and 0/5 — the verifier never
caught either placeholder case.
**After** (added a STRICT clause naming the fabricated-placeholder
pattern, plus a LENIENT clause explicitly distinguishing "no filter at
all" from "a filter with fabricated values"): 5/5 and 5/5 — full,
reliable detection.
**Negative control** (the legitimate `6a4dbcf8`-style honest-omission
case): 5/5 false positives both *before and after* — confirming this
specific false-positive tendency is a separate, pre-existing issue
(already documented in §4T) that this fix neither caused nor fixed,
not a new cost of the change.

This is now a properly-controlled, **kept** fix: a clean, validated win
on its target with no measured downside, unlike §4T's reverted attempt.
The earlier revert was the right call given the evidence available at
the time (a single noisy aggregate comparison); this round's targeted,
repeated-trial methodology is what made the difference, not a
different idea.

### Verifier critique → structured error: the bridge §4S identified as missing

§4S diagnosed blocking mode's actual failure mechanism: "the IR Builder
couldn't act on a free-text critique within 3 attempts the way it
reliably acts on a precise structured validator error." Built the
bridge: `VerifierAgent.VerificationResult` now returns a `category`
field (`event_type` / `comparison_direction` / `aggregation_grouping` /
`other`, mirroring the verifier's own 3-check structure already in its
system prompt) alongside `issue`. `repair_loop.py`'s blocking-mode
branch now formats the verifier's free-text issue behind a named,
structured `error_type` (`VERIFIER_WRONG_EVENT_TYPE`,
`VERIFIER_COMPARISON_DIRECTION_INVERTED`,
`VERIFIER_AGGREGATION_INTENT_MISMATCH`, `VERIFIER_SEMANTIC_MISMATCH`)
and a category-specific prefix sentence, the same structured shape as
every existing validator error. Not yet re-measured against blocking
mode's original regression (that would need a full live comparison run,
not done this round) — this is the mechanism §4S called for, built and
unit-tested, but its effect on blocking-mode's actual recovery rate is
still an open measurement.

### What's still open after this round

Both carried-forward items were actually attempted in §4W below: the
structured-error bridge was measured live against blocking mode (a
negative result), and a bounded version of the principle-compression
experiment was run (also a negative-to-neutral result, with one clear
mechanism identified). Item 3's reranker proposal remains not
implemented. The Azure AI Foundry key rotation remains unconfirmed.

---

## 4W. Closing the loop on §4V's two open items: blocking-mode
     re-measured (still negative) and a bounded compression experiment
     (negative, with a specific mechanism identified)

### The structured-error bridge does not redeem blocking mode

Re-ran the full 45-case comparison with `WITH_VERIFIER_BLOCKING=1` and
the new category-based structured-error bridge in place (§4V). Result:
**SVR 73.3%, FVR 71.1%, RRR 61.3%** — worse than §4S's already-rejected
blocking-mode baseline (SVR 80.0%, FVR 80.0%, RRR 69.0%), and far below
advisory mode's current numbers (SVR ~95.6%, FVR ~88.9%, RRR ~91.7%).
12/45 cases failed via `MAX_REPAIR_ATTEMPTS_EXCEEDED`, including
`7b3ed03a-sop` — the exact case blocking mode was originally built to
fix back in §4S, still unfixed. `4e3af8e3` now fails on all 3
paraphrases, a broader failure pattern than §4S documented.

The bridge itself works as designed (category classification, unit
tests pass) — but a clearer label on the verifier's critique doesn't
help when the deeper problem is the verifier's own false-positive rate
under blocking, which this round's other changes (the placeholder-
detection STRICT clause added to `verifier_agent.py` in §4V) plausibly
increased further by making the verifier generally more willing to
flag a query as not matching intent. **This is not a reason to revert
that fix** — it was validated on its own narrow target with a proper
negative control (§4V) — but it is a likely contributor to blocking
mode looking worse now than in §4S, on top of blocking mode's
already-established, more fundamental problem (free-text critiques the
IR Builder can't reliably act on in 3 attempts). **Conclusion
unchanged, now with two independent negative measurements instead of
one: advisory mode remains the only recommended mode.** The structured-
error bridge is kept in the code (it's harmless in advisory mode, where
it's never invoked) as infrastructure for a future, more fundamental
attempt — not as a fix that worked.

### A bounded principle-compression experiment

Full compression of all ~36 distinct principles in `_COMMON_MISTAKES`
was judged too risky to attempt outright (§4V's own assessment) — so a
single, well-scoped slice was tested instead: the 5 "a label/reference
is not literal data" worked examples (threat-actor names, CVE IDs, two
flavors of external-list omission — ~80 lines with extensive "found
live, this produced X" narrative) were compressed into 2 tighter
examples (~25 lines), behind a new opt-in env var
(`COMPRESSED_LABELS_PROMPT=1`) that leaves the default prompt
byte-for-byte unchanged unless set — `_label_vs_data_section()` in
`ir_builder_agent.py`, selected per-request and threaded through both
the build and repair prompts via the existing `input_data` templating
mechanism, the same way `likely_event_type` already is.

Sanity-checked first on the two specific targeted bugs (Mercury,
CSV-list omission) at 3 trials each — both held under compression, so
the experiment proceeded to the full held-out set: 3 independent runs,
scored the same way as §4V's N=5 full-prompt baseline.

**Compressed: 70.6%, 76.5%, 76.5% (median 76.5%). Full: 76.5%, 76.5%,
82.4%, 82.4%, 82.4% (median 82.4%, IQR 5.9 from §4V).** The median gap
(5.9 points) is exactly the size of the full prompt's own established
noise band — by this project's own measurement standard, that is too
close to call from the aggregate number alone, and N=3 vs. N=5 makes it
weaker evidence than §4V's headline figure.

**But the specific, mechanism-level evidence is clearer than the
aggregate and points the same direction.** Two concrete regressions
appeared under compression that never appeared across all 8 full-prompt
runs combined (5 from §4V's replication + 3 isolated verification
trials):
1. `2d1a3e86` (the CVE case) regressed back to `CommandLine contains
   "CVE-2022-29972"` — the exact literal-ID bug the full version fixed
   5/5 — in 1 of 3 compressed runs. The compressed example still
   *names* CVE-2022-29972 as one item in a list of label examples, but
   drops the explicit "found live: this produced X, which is wrong"
   demonstration the full version gives that case specifically.
2. `9b72769e` failed via repair-budget exhaustion in 2 of 3 compressed
   runs, vs. 0 of 5 full-prompt runs.

This refines, not just confirms, this session's earlier finding (§4U:
"a bare principle was not enough... principle + worked example was").
The sharper version: **a worked example needs to show the wrong output
being corrected, not just state the right one** — the compressed
version kept a positive example per principle (already known to matter
more than a bare principle) and still lost reliability on the one case
whose specific failure mode it stopped demonstrating explicitly. This
is a more precise, falsifiable claim than "examples matter," and this
experiment is itself evidence for it, not just an assumption carried
into the design.

**Disposition: compression reverted to full by default** (no env var
set). The infrastructure (`_label_vs_data_section()`,
`COMPRESSED_LABELS_PROMPT`) is kept, opt-in, for a future attempt that
preserves the before/after demonstration shape while still cutting
narrative length elsewhere — this experiment's lesson is "cutting the
wrong/right contrast costs reliability," not "compression can't work at
all."

### What's still open after this round

- Item 3's reranker proposal (generate 3 candidates, verifier picks
  best) remains not implemented.
- A full-scale principle-compression attempt (all ~36 principles, not
  just the 5-example slice tested here) remains undone — this round's
  finding suggests any future attempt must preserve the wrong/right
  contrast per example, not just keep "an example."
- Blocking mode's underlying problem (the IR Builder's free-text-
  critique recovery rate) is now confirmed, twice, to need a different
  fix than either selective exclusion (§4S) or structured categorization
  (§4W) — both measured negative. A fundamentally different mechanism
  (e.g. the verifier-as-reranker proposal, which never requires the IR
  Builder to act on a critique at all) is the more promising remaining
  direction.
- The Azure AI Foundry key rotation remains unconfirmed.

---

## 4X. Expanding KQL construct coverage — closing a documented capability
     gap, not just an accuracy gap

Direct response to a different kind of request than every round since
§4T: not "make the 13 tuned rules more accurate," but "cover more of
KQL than those 13 rules ever needed." Grounded the work in an actual
construct-frequency audit of the dataset (81 verified pairs + the 97
never-used fresh candidates) rather than guessing which operators
matter — `let`(138), `tostring`(107), `ago`(86), `split`(81), `has_any`
(77), `union isfuzzy`(56), `mv-expand`(35), `has_all`(9), and dozens
more, counted directly against real ground truth.

### A real bug found by the audit, not by a held-out failure

`has_all` is a genuine KQL operator — confirmed in ground truth,
including one of the 13 *tuning* rules (`5b6ae038`, the sdelete-flags
case) — but `ir_builder_agent.py`'s own prompt explicitly stated "There
is no 'has_all' operator," forcing a 4-filter AND workaround instead of
the native, more concise form real KQL (and real ground truth) actually
uses. This was wrong information being taught with confidence, found
only because the construct audit checked the codebase's own claims
against real data instead of assuming them. Fixed directly; the sdelete
worked example now uses `has_all` natively. **5/5 clean on its source
case**, output now matching ground truth's exact style.

### Three new filter operators, three new stage types

- `HAS_ALL`, `IN_CI` (`in~`), `NOT_IN_CI` (`!in~`) added to
  `FilterOperator` — the AND-equivalent of `has_any`, and the
  case-insensitive forms of `in`/`!in` (which, unlike contains/has/
  startswith/endswith, are case-SENSITIVE by KQL default — a real,
  separate construct, not a duplicate).
- `MvExpandStage`, `MakeSeriesStage`, `SeriesAnomalyStage` — together
  expressing the full `make-series` → `series_decompose_anomalies` →
  `mv-expand` → `where` pipeline. This is the exact construct
  `01191239`'s `caveats` output has been self-reporting as missing
  since §4T ("series decompose anomaly detection... cannot be
  expressed in this IR") — three rounds of honest abstention, now a
  closed gap instead of a permanent one. `MvExpandStage.fields` takes a
  list from the start (multiple arrays expanded in lockstep is the
  exact pattern this pipeline itself needs to flatten its 5 series
  columns back into rows, and real ground truth does this routinely).
- Validator support added for all three (field-availability tracking
  through `mv_expand`/`make_series`/`series_anomaly`, a new
  `MV_EXPAND_AS_TYPE_WITH_MULTIPLE_FIELDS` check, ISO 8601 validation
  for `MakeSeriesStage.step` reusing the existing duration check). 4 new
  compiler unit tests, including the full 4-stage anomaly pipeline
  end-to-end. `test_validator_inventory.py`'s safety net (the same one
  that caught §4K's silent regression) updated and passing.

### Live-verified on the documented gap, not just unit-tested

5/5 trials on `01191239`'s exact NL description now produce the full,
structurally correct pipeline (`make-series` → `series_decompose_
anomalies` → `mv-expand` → `where AnomalyFlag != 0`). A real bug
surfaced and was fixed in the same pass: when `MakeSeriesStage` computes
more than one aggregation, the model would sometimes run
`series_decompose_anomalies` on one aggregation alias but `mv-expand`
a *different* one from the same stage — leaving the actually-analyzed
column perpetually array-valued. Found on both the synthetic test
(1 of 5 trials) and live in the held-out re-run's `01191239` output.
Added an explicit worked-example clause requiring the two names to
match exactly; re-verified at 4/4 correct matches across both single-
and multi-aggregation cases afterward.

### Validated on genuinely fresh ground truth, not just the synthetic test

Pulled 3 cases from the existing 97-candidate fresh pool that
specifically exercise the new constructs and were never used in any
prior round: `02f23312` and `cf687598` (both real `series_decompose_
anomalies` DGA/multi-client-error detections) and `98fdd28d` (a
`has_all`/`has_any` post-exploitation hunt). All 3 trials on
`02f23312` produced the correct structural pipeline. `cf687598`
(harder — groups by a field pair, needs an error-code prefilter the
model sometimes dropped) got the anomaly-detection skeleton right
consistently but missed the specific "errors" qualifier in 3/3 trials —
a real, narrower residual, not a construct-coverage failure. `98fdd28d`
correctly abstained via `caveats` in all 3 trials rather than
fabricating command-line indicators — its specific IOCs live only in
the query body's `dynamic()` arrays, never in the human-readable
description text, a genuine Cause-1 case the system identified
correctly rather than guessed at.

### No regression on the tuned set

Full 45-case run with all of the above in place: SVR 93.3%, FVR 84.4%,
RRR 89.3%. SVR and RRR sit inside the §4T N=5 replication's established
noise band (93.3–97.8 and 88.0–96.0 respectively — 93.3 was already
the *low end* of the observed SVR range). FVR (84.4%) is a few points
below the previously-observed floor (88.9%), driven by `4e3af8e3`
failing all 3 paraphrases — but `4e3af8e3` is independently documented
across §4E/§4K/§4L/§4N as "the single hardest case in the dataset"
(percentile-of-aggregates, an entirely different, unrelated construct),
with a long history of 0/3–1/3 success rates. Its failure here is
consistent with known difficulty, not a new regression from the
construct additions.

### What's still open after this round

- The dataset-coverage angle (item 1 of the broader critique this round
  responded to) is only barely started: 3 fresh cases pulled and
  verified, against a stated target of "hundreds to thousands,
  construct-targeted." The full construct taxonomy (every join kind,
  every string/time function, `parse`, `externaldata`, `materialize`,
  subqueries) has not been systematically built out — this round closed
  the single highest-value, most-documented gap (`make-series`/
  `series_decompose_anomalies`) and fixed one real bug (`has_all`), not
  the whole space.
- `parse` (the pipe operator, 21 occurrences in the audit), `project-
  away`/`project-rename`/`project-reorder` (lower logic-correctness
  priority — cosmetic field-shaping, not detection-logic-changing),
  `externaldata`, `materialize`, and `toscalar` remain unimplemented,
  triaged but not attempted this round.
- `cf687598`'s missing error-code prefilter is a real, narrower residual
  not yet addressed.
- Execution-based validation (the "ground-truth oracle" — a real Kusto
  emulator or seeded workspace) remains the single largest unaddressed
  item from this round's broader critique: every Logic Correctness
  number in this document, including the ones above, is still manual/
  LLM-rater judgment, not an executed-and-checked result. **Addressed,
  with an honest caveat, in §4Y below.**
- Retrieval-augmented few-shot and fine-tuning (items 4 and 5 of the
  broader critique) remain unstarted — both presuppose the dataset-scale
  work in item 1, which is itself only barely started.
- The Azure AI Foundry key rotation remains unconfirmed.

---

## 4Y. An execution-validation substitute, a permanent construct
     coverage scorecard, and an explicit IR coverage-boundary policy

Direct response to the follow-up critique's five points, in the order
that turned out to matter: checking whether a real execution oracle was
even possible here came first, since it changed how everything else
got sequenced.

### Execution validation: environment-blocked on the literal ask, built an honest substitute instead

No Docker, no Azure Log Analytics workspace credentials, no Kusto SDKs
installed — confirmed directly, not assumed. The literal ask (an ADX
emulator container, or a seeded workspace) is closed in this
environment. Rather than fake that out or skip it, built
`src/execution/ir_interpreter.py`: a Python/pandas re-implementation of
`KqlPipeline`'s own intended semantics, operating on the IR object
itself, not the compiled KQL string. This validates "does the IR
Builder's constructed pipeline select the right rows for a given
scenario" — automating the actual Logic Correctness question instead
of leaving it to a single rater's judgment. It does **not** validate
that the compiled KQL string executes identically in a real Kusto
engine (a compiler bug could exist that an interpreter sharing the
compiler author's understanding of semantics wouldn't catch) — the two
are complementary, and only one was buildable here. Covers
`WhereStage`/`SummarizeStage`/`ExtendStage` (a restricted, AST-based
safe expression evaluator)/`JoinStage`/`ProjectStage`/`TopStage`/
`MvExpandStage` faithfully; `MakeSeriesStage`/`SeriesAnomalyStage` via
an approximation (leave-one-out z-score, not Kusto's real STL
decomposition) — adequate for a should-fire/should-not-fire check, not
a numerically exact replication. 10 unit tests, all passing.

Built `tests/integration/test_live_e2e_execution_validation.py` —
should-fire/should-not-fire checks against the IR Builder's **actual
live output** for 3 representative tuned-set cases. Named with the
`live_e2e` substring deliberately: this project's actual exclusion
convention for the fast default test run is filename-substring
matching on `-k "not live_e2e"`, not a pytest marker — confirmed by
reading `test_live_e2e.py` directly rather than assuming, after first
writing this file with a marker that the existing `-k` filter would
have silently ignored.

**This caught two real things, neither visible from reading compiled
KQL text alone:**
1. A genuine, recurring bug: the model sometimes filtered for the
   literal English phrase `"recycle bin"` (echoing the NL description)
   instead of the real filesystem path convention (`"recycler"`/
   `"$Recycle.Bin"`) — the same "label vs. data" mistake class as the
   CVE-ID and actor-name bugs fixed in §4T/§4V, a third instance found
   by execution testing rather than another manual read. Fixed in
   `extraction_agent.py`; re-verified at 6/6 clean afterward (was
   failing roughly 1 in 3 trials before).
2. Two genuinely separate, both-valid axes of model variance on a
   deliberately vague case (`ProcessEvent` vs. `FileEvent` for "hidden
   in the recycle bin"; legacy `RECYCLER` vs. modern `$Recycle.Bin`) —
   the synthetic test needed to cover both rather than over-narrow to
   one assumption, a concrete lesson in building execution-validation
   tests that distinguish real bugs from legitimate interpretation
   variance.

One test-design lesson worth flagging honestly: an early version of the
DGA test used a fixed repeated domain for its "spike," which satisfied
a raw-NXDOMAIN-count interpretation but not a `dcount(DnsQuery)`
interpretation the model sometimes chose instead (both real, defensible
readings of "DGA," which by definition involves *many different*
generated domains) — varying the domain per spike event fixed the test
and is also the more realistic synthetic DGA pattern either way.
~1 failure in ~16 runs across the suite after these fixes, consistent
with this project's already-documented noise floor — not chased
further.

### A permanent construct coverage scorecard

`docs/NL-KQL/CONSTRUCT_COVERAGE.md` — every construct from the §4X
frequency audit, now enumerated with three columns (frequency, IR
support status, tested accuracy) instead of left as an in-progress
audit. **Headline number, recomputed directly from the table rather
than estimated: of 32 distinct constructs appearing in ≥5 real
ground-truth queries, 19 (59.4%) are fully Supported, 3 (9.4%) Partial,
10 (31.2%) Not Supported.** An early draft of this same file asserted
76.7% without actually recounting from its own table — caught and
corrected before publishing, which is itself a small, concrete
demonstration that the rigor this file exists to enforce has to apply
to writing it too, not just to claims made elsewhere.

The file states the institutional rule the critique asked for
explicitly: no stage type or operator gets marked Supported without
≥5 fresh, never-tuned-against cases and a recorded result. Went back
and brought `make-series`/`series_decompose_anomalies` up to that bar
retroactively (§4X had only 3 cases) — 2 more fresh cases pulled:
`5965d3e7` (2/3 cleanly correct, 1/3 a different, incomplete
architectural choice) and `cbf07406` (correctly abstains entirely
rather than exercising the construct at all — no concrete signal
beyond an unsupported watchlist, a valid outcome in its own right, not
a failure to count against the construct).

### The coverage-boundary policy, made explicit instead of discovered case-by-case

Documented directly in `CONSTRUCT_COVERAGE.md`: typed-stage investment
extends through the **detection-common core** (everything Supported/
Partial today, plus `parse` and `let`-bound subqueries, queued next);
the genuinely rare or externally-dependent **tail** (`externaldata`,
`toscalar`, `datatable`, `print`, `bag_unpack`, `evaluate`, `pivot`,
`range`, `find`, `lookup`) relies on `caveats` abstention rather than
forcing expensive typed modeling of rare constructs; **cosmetic**
field-shaping (`project-away`/`-rename`/`-reorder`, unlimited `sort`,
`distinct`, `take`/`sample`) is deliberately deprioritized since none
of it changes which rows a detection fires on. This is the same honesty
mechanism already built and validated for missing literal values
(§4T/§4U), now stated as the project's permanent, explicit answer to
"where does the IR stop," not a judgment call repeated every time a new
rare construct turns up.

### What's still open after this round

`parse` was closed and `let`-bound subqueries were explicitly moved to
the tail category this same round — see §4Z below for both. The
interpreter's `MakeSeriesStage`/`SeriesAnomalyStage` approximation
(leave-one-out z-score, not Kusto's real algorithm) and the fact that
the interpreter validates the IR's own intended semantics rather than
the compiled-KQL execution surface both remain true and are restated,
not resolved, in §4Z. The Azure AI Foundry key rotation remains
unconfirmed.

---

## 4Z. Closing `parse`/`arg_max`, deciding `let`-subqueries, and building
     the reverse-generation + execution-validation loop

Direct continuation of §4X/§4Y, working through the critique's
remaining concrete items in the order its own priority made clear:
the two named core-tier construct gaps first (since the recipe was
already proven), then the infrastructure that makes scaling that
recipe trustworthy instead of just fast.

### `arg_max`/`arg_min` promoted from Partial to Supported — and a 100%-reproducible bug fixed

The audit flagged `arg_max`/`arg_min` (36 occurrences) as Partial: the
function name was whitelisted for `ExtendStage` expressions, where the
real idiom (`summarize arg_max(TimeGenerated, *) by X` — "the full row
at the max timestamp per group") can never actually be expressed
(multi-column destructuring assignment has no home in a single-alias
`ComputedField`). Added `ArgMaxMin` (`order_field`, `carry_fields`,
optional `result_alias`) as a sibling field on `SummarizeStage`,
combinable with ordinary aggregations in the same clause (real KQL
allows `count(), arg_max(TimeGenerated, *)` together). Compiler,
validator (field-availability tracking, with `result_alias` correctly
removing the raw `order_field` name from scope when set — real KQL
does not leave both available), and interpreter support added.

**A real, 100%-reproducible bug found before this could be trusted**:
real ground truth (30+ threat-intel-deduplication queries, all shaped
`LatestIndicatorTime = arg_max(TimeGenerated, *) by IndicatorId`)
consistently renames the order field's own output column — but every
one of 6 live trials on a case needing this assumed `result_alias`
*also* prefixes every carried field's name (`FirstQuery_DnsQuery`,
which does not exist; the real columns are `FirstQuery` and `DnsQuery`,
both bare). Fixed with an explicit worked-example correction; 6/6
clean afterward, plus 2/2 synthetic "most recent"/"first seen" cases.

### `parse` added — the higher-frequency, higher-logic-impact of the two remaining core-tier targets

Added `ParseStage`/`ParseToken` (simple/positional mode — `kind=regex`/
`kind=relaxed` parse modes triaged to the tail, covering the dominant
real usage shape: alternating literal delimiters, named extraction
points, optional leading/trailing wildcards). Compiler, validator
(`PARSE_EXTRACTS_NOTHING`, `DUPLICATE_PARSE_COLUMN` checks; both added
to `test_validator_inventory.py`'s safety net), and interpreter support
(regex-compiled from the token list; a non-matching row gets null
extracted columns, never dropped — matching real KQL).

Live-verified on 5 fresh cases: 4/5 fully clean (a firewall log-line
extraction, a JNDI host extraction, a "net user" username extraction,
and one case where the model correctly determined `parse` *wasn't*
needed at all since a clean ASIM field already held the value — exactly
the worked example's own instruction working as intended). 1/5
(`syslog_severity_extract`) was schema-valid but semantically weak — a
complex multi-field literal structure collapsed to a single bare
wildcard-column-wildcard, losing positional precision against the
real format. A real, narrower residual, not chased further this round.

### `let`-bound subqueries: checked, not assumed, and moved to the tail

The critique's own caution — "check whether the generator can even
fixture it... before you build it" — was tested directly rather than
taken on faith. Sampling real ground truth's `let`-bound reuse (104
tabular `let` bindings referenced 2+ times across the dataset) found
it is NOT just "a reusable tabular expression," which `JoinStage.
right_pipeline` already covers for the single-use-as-a-join case.
It includes parameterized, named FUNCTIONS (`let f = (stime, etime)
{ ... }`, found in `983a6922`) and DAGs of mutually-referencing named
results (`24e66452`'s `Include`/`Exclude`/`AllSecEvents`, each
referencing the others) — a genuinely different IR shape, a graph of
named sub-pipelines, not the tree `KqlPipeline` already is. Building a
typed stage for this would produce coverage the fixture generator
structurally cannot validate, violating `CONSTRUCT_COVERAGE.md`'s own
≥5-fresh-cases rule by construction. **Decision: moved to the tail
category** (`caveats` abstention), not core — confirmed by checking,
not assumed from the critique's caution alone.

### The reverse-generation + execution-validation loop

Built `src/synthesis/`: `ir_generator.py` (8 construct templates,
sampling real ASIM fields and curated realistic literal values —
100% schema- and syntax-valid by construction, confirmed across a
101-example batch, because each template produces a real `KqlPipeline`
through the same compiler everything else uses, not a separately
hand-written KQL string that could be syntactically wrong);
`fixture_generator.py` (auto-derives should-fire/should-not-fire
synthetic events from the SAME generation metadata that produced the
IR); `back_translate.py` (an LLM back-translates the generated KQL into
an analyst-style NL description); `run_synthesis_eval.py` (feeds that
NL through the real system and execution-validates the system's own
regenerated IR against the auto-generated fixtures via the §4Y
interpreter). Self-consistency confirmed first: every generator
template's own fixtures correctly fire/don't-fire against its own
output, 100% across an 80-example batch, before ever pointing this at
the live system.

**A real measurement bug was found and fixed before trusting the
resulting numbers** — the first live run showed `threshold_summarize`
and `make_series_anomaly` apparently almost completely broken
(field_mismatch on 4/5 and 3/3 cases). Not a system failure: the
auto-fixture's hardcoded field names didn't track when the system
reasonably chose a *different*, equally valid field for the same
semantic role (grouping by `Process` instead of the generator's
`ActingProcessName`; using `dcount(DnsQuery)` instead of `count()`).
This is the same brittleness lesson §4T/§4Y already learned by hand,
recurring at the harness level, exactly as flagged: a fixture that
over-specifies field identity marks a correct query wrong whenever the
model makes a different-but-equivalent choice. Fixed by deriving the
fixture's field names from the **system's own regenerated IR** instead
of the generator's original choice, for every template where the
field's name carries no semantic weight of its own (the grouping/
ordering/aggregation-operand fields — not the templates where field
identity IS the content under test, like `simple_filter`). Re-running
the same 24-example batch after the fix: `threshold_summarize` and
`make_series_anomaly` both went from unmeasurable to a clean 100%
completion/fire/nofire/0 field_mismatch — the construct's real
execution-validated accuracy, not a fixture artifact. Full per-template
table in `CONSTRUCT_COVERAGE.md` §4Z.

**A second, orthogonal finding from the same work**: the back-
translated NL has a detectable style gap against real ground truth —
every synthetic description follows a rigid "this rule detects X,
which may indicate Y" template; real descriptions vary far more (one
real example, `bd89c7a0`, is six words with no rationale clause:
"breakdown of scripts running in the environment"). Flagged honestly:
synthetic accuracy numbers likely run somewhat optimistic relative to
real-world input variety and should not be cited as equivalent to a
held-out real-data number.

A small regression gate was started: 2 new permanent anchors added to
`tests/integration/test_live_e2e_execution_validation.py` (the §4U
OR-list-as-AND-chain regression; the §4V CVE-ID-as-literal bug), each
targeting one specific, previously-fixed bug class via the execution-
validation harness rather than a fresh capability — 5 anchors total
now, against an unbounded number of bug classes fixed across this
project's history.

One interpreter bug was also found and fixed in the course of writing
these regression anchors: `_has_term` (the `has`/`has_any` word-
boundary approximation) incorrectly rejected a genuine match for a
term starting with a non-alphanumeric character (e.g. `.ps1`, a file
extension) preceded by an alphanumeric character (`payload.ps1`) —
fixed to only enforce a boundary on the side of the term whose own
edge character is itself alphanumeric.

**Azure AI Search**: asked directly whether it's needed for the
retrieval-augmented few-shot proposal (critique item 3, still
unstarted). Answer: no — this project's corpora (KQL operator docs,
ASIM schema docs, Hunting Queries/Solutions pairs) are small enough
for a local vector store (FAISS/Chroma via LangChain, already a
dependency) with no new cloud resource, cost, or operational
overhead. Azure AI Search earns its complexity for corpora and
production search scale this project does not have.

### The honest, bounded coverage claim this round's work supports

**71.9% of constructs appearing in ≥5 real detection rules are
Supported or Partial, with explicit, deliberate abstention beyond that
boundary — not an unbounded "covers KQL" claim.** Up from 65.6% before
this round's `arg_max`/`parse` closures, and up from 59.4% at
`CONSTRUCT_COVERAGE.md`'s first writing (§4X/§4Y).

### What's still open after this round

- Scale: 24 reverse-generated examples proved the loop works and
  validated the fixture-decoupling fix; it is not enough to trust any
  single template's percentage as a stable estimate, and every example
  tests one construct in isolation — never combinations (`parse`
  feeding a later `summarize`, `arg_max` inside a join, `mv-expand`
  feeding a `make-series`), which is exactly where real, unseen rules
  are most likely to break in ways isolated per-construct testing
  structurally cannot surface.
- `has_all_evasion`'s 40% fire rate and `or_list`'s mixed numbers (both
  n≤5) are real, small-sample signals worth a closer look at scale, not
  explained away by the field-mismatch fix (`field_mismatch=0` for
  both already).
- Retrieval-augmented few-shot remains unstarted.
- The regression gate has 5 anchors; nowhere near comprehensive against
  this project's full fix history.
- The Azure AI Foundry key rotation remains unconfirmed.

---

## 4AA. Construct combinations, the real-vs-synthetic gap measured (not
     just flagged), and institutionalizing the regression gate

Direct continuation of §4Z, executing the critique's own re-sequencing
of the three items it had left open: combinations first (the actual
experiment), scale on combinations second (cheap, but only valuable
after the first), RAG last (a feature, not a measurement, and only
honestly testable against a frozen held-out slice this project doesn't
have yet) — plus the two items flagged as missing from the prior
round's list: institutionalizing the regression gate, and measuring
(not just flagging) the synthetic-vs-real NL gap.

### Construct combinations: built, and they immediately earned their keep

Added 3 new generator templates to `src/synthesis/ir_generator.py`,
each a 2-3-construct CHAIN rather than an isolated construct:
`parse_then_summarize` (parse extracts a field, summarize groups on
the EXTRACTED column, not a raw ASIM field), `arg_max_in_join`
(arg_max inside a join's right_pipeline — the latest auth event per
host, joined against current process activity), `make_set_mv_expand_filter`
(summarize make_set(Url), mv-expand back to one row per URL, filter
the EXPANDED item — the "per-item reporting" mv-expand use case
chained with a downstream filter on what it expanded). Self-consistency
confirmed first (every new template's own fixtures correctly fire/
don't-fire against its own output) before pointing at the live system,
same discipline as §4Z's single-construct templates.

**This surfaced a real, previously-unknown IR expressivity gap within
the first scaled batch** — exactly the kind of seam failure isolated
per-construct testing structurally cannot find. `arg_max_in_join`'s
back-translated NL (a process event correlated against a joined
authentication time window) repeatedly produced KQL shaped like:

```
| extend ProcessTime = TimeGenerated
| where ProcessTime >= "FirstAuthTime"
| where ProcessTime <= "LastAuthTime"
```

`FirstAuthTime`/`LastAuthTime` are COLUMN NAMES from the join's right
side — but `"FirstAuthTime"` here is a quoted STRING LITERAL, not a
field reference. The root cause, confirmed by reading `ir_schema.py`:
`Filter.value: Union[str, int, float, bool, List[...]]` has no
mechanism to express "compare this field against ANOTHER field" — the
compiler always renders `value` as a literal. The model correctly
recognizes the detection NEEDS a field-to-field comparison (bracketing
a process event's time against a joined event's time window — a real,
common SIEM correlation pattern) but the schema cannot express it, so
it falls back to the closest representable shape: a filter that is
syntactically valid and silently, semantically wrong (it can never
match, or matches by accident, depending on string-vs-datetime
coercion) — far more dangerous than an outright parse failure, because
nothing flags it.

**Fixed and live-verified, same session.** Added `Filter.field_ref:
Optional[str]` (mutually exclusive with `value`, enforced by a
`model_validator`): the compiler renders it as a bare unquoted column
reference; the validator checks it against the running
`available_schema` exactly like `field` (already tracks join/extend
output columns by the time a later WhereStage runs, so no special
exemption was needed); the interpreter's `_eval_single_filter` reads
`row[field_ref]` instead of treating it as a literal, with a
datetime-comparison fallback added to GT/LT/GTE/LTE for non-numeric
values. Taught via a new worked example in `ir_builder_agent.py`
(immediately re-verified the prompt still constructs cleanly — the
stray-curly-brace bug class has bitten this exact file twice before,
and a first draft of the new worked example repeated it a third time,
caught before it shipped). Live-verified 5/5 clean on the exact NL
shape that exposed the gap — every trial now renders
`ProcessTime >= FirstAuthTime` unquoted, none reverted to the broken
quoted-literal shape.

A new permanent regression anchor was added for this
(`test_process_time_bracketed_by_joined_auth_window_uses_field_ref_not_literal`),
which took two failed fixture-design iterations before stabilizing —
itself a useful finding about the interpreter's join model. Both
failures traced to the SAME root cause: `run_pipeline`'s join handling
reuses the FULL original row set for `right_pipeline` (not the left
side's filtered subset), so it's table-agnostic — a synthetic row
meant for "the left/process side only" still gets folded into the
right side's own aggregation if it shares the grouping field. Varying
only the excluded row's timestamp let it leak into the right side's
min/max and trivially become its own boundary; varying only its host
(to dodge that) still leaked it into the right side's *groupby itself*,
creating a spurious self-correlated group whose bounds exactly equaled
the row's own timestamp. The fix: the excluded row also omits the
timestamp field entirely, so its (still-present) right-side group has
NaN/NaT bounds, and any comparison against NaT is reliably False
regardless of which time field the model chose for the process side —
confirmed directly against the interpreter before re-running live, then
confirmed stable across 6 consecutive live runs.

Three narrower, fixable issues were found and fixed across two
re-runs of the scaled batch (same seed=7, so each fix's effect is a
clean before/after on the identical generated IRs): (1)
`parse_then_summarize` hit 100% field_mismatch (14/14) on first
contact — not a system bug: the system frequently solves "count
repeated JNDI lookups" via `where Url contains "jndi"` grouped on an
EXISTING ASIM field (`DstHostname`/`SrcIpAddr`/`SessionId`), never
invoking `parse` at all, a genuinely valid alternative this template's
NL doesn't rule out. The fixture only populated `Url` and, on closer
inspection, never even included `TimeGenerated` — fixed by deriving
group-by, `TimeGenerated`, and every other aggregation operand from
the system's own IR (the `_placeholder_fields` helper §4Z already
built for `threshold_summarize`). Result: 0/14 field_mismatch. (2)
`make_set_mv_expand_filter` regressed to 0% fire (0/8) once
`min`/`max(TimeGenerated)` aggregations started appearing alongside
`make_set(Url)`: the fixture helper grabbed the FIRST aggregation with
any field at all (`min(TimeGenerated)`), never reaching `make_set(Url)`
— fixed by specifically targeting a `make_set`/`make_list` aggregation
rather than "any aggregation with a field." Result: 87.5% fire. (3)
the join-key handling only populated the FIRST join key; the system
reasonably correlating on two keys (`Dvc`, `ActorUsername`) left the
second entirely missing — fixed to populate every key in
`JoinStage.join_on`. A separate, genuine interpreter capability gap was
also found and fixed: `datetime_diff` wasn't in the `ExtendStage`
evaluator's function whitelist at all — added (parses both timestamps
via `pd.to_datetime`, converts to the requested unit) since without it
the interpreter couldn't assess any case using it, independent of
whether the system's answer was otherwise correct.

A fourth pattern was found and deliberately NOT chased: `join_baseline`
(intended to exercise a literal join-based ratio) was sometimes
answered via `make-series` + `series_decompose_anomalies` instead — a
different, arguably more idiomatic construct for "is this unusual vs.
a baseline," which the template's single-row fixture can't exercise
correctly. At n=3 this is sample noise as much as signal (a later run
scored 100% with the same fixture) — logged as a known limitation, not
patched a third time this round. The construct-substitution pattern
itself, recurring 3 times this round across 3 different templates, is
the auto-fixture generator's main remaining risk at further scale, not
any one fixed instance of it.

### Per-construct-template numbers, including the new combination templates

Final numbers after the fixes above, n=60 (37 combination, 23
single-construct draws from `generate_mixed_batch`):

**Overall: 98.3% completion, 84.2% fire (48/57), 96.2% nofire (51/53),
2/60 field_mismatch** (both attributable to the field-to-field
comparison gap above, not fixture brittleness). Cost, logged for the
first time this round via `langchain_community`'s OpenAI-compatible
token-usage callback (works against `azure_foundry` since both ride
`ChatOpenAI`): avg 21,489 tokens and 5.6s per query; combination
templates cost noticeably more (`arg_max_in_join`: ~24.7K tokens/7.3s)
than single-construct ones (~18.1K tokens/~4s) — the honest claim is
now "N% supported at M tokens/seconds per rule," not accuracy alone.
Full per-template table in `CONSTRUCT_COVERAGE.md` §4AA.

### The synthetic-vs-real NL gap, measured

§4Z flagged but did not measure this. Two concrete moves, per the
critique: (1) ran this project's existing hand-built real-ground-truth
NL descriptions (the 5 cases now anchoring the regression gate, each
repeated 5× since the system is not fully deterministic at temperature
0) through the SAME execution-validated metric the synthesis eval
uses — `src/synthesis/run_real_eval.py`, new this round. Result: 100%
completion, 100% fire (20/20), 100% nofire (25/25), avg ~18.8K
tokens/query, ~4.1s/query. Stated plainly: these 5 cases are NOT a
representative real-world difficulty sample — they're cases this
project has already iterated on and fixed bugs for across many prior
rounds, so 100% partly reflects "we already fixed the bugs these cases
exposed." This is a regression floor, not a generalization claim.

(2) Added a "terse" back-translation style to `BackTranslator`
(`src/synthesis/back_translate.py`) — no rationale clause, no "this
rule detects" framing, matched to the real example that prompted the
gap finding (`bd89c7a0`: six words, no rationale) — and re-ran the
SAME 24 generated IRs (same seed, confirmed via matching
`generated_kql`) through it for a controlled before/after. Result:
fire dropped from 90.9% (20/22, rich) to **54.5%** (12/22, terse) on
the IDENTICAL underlying detection logic, nothing else changed; nofire
dropped less (95.2% → 85.7%). This is real and causal, but NOT a flat
"synthetic NL inflates accuracy by 36 points" tax — pairing each terse
case against its rich counterpart shows the drop is concentrated almost
entirely in `parse_then_summarize` (7/8 occurrences flipped from
fire=True to fire=False); `simple_filter`, `make_series_anomaly`,
`arg_max_in_join`, and `parse_extract` were largely unaffected by style
on the same pairs. Likely mechanism: `parse_then_summarize`'s detection
concept depends on the NL naming a specific literal pattern
(`jndi:ldap://`); terse strips exactly that detail, while simpler
filter/threshold logic survives without it. **The gap is real and
construct-dependent — concentrated where correct implementation needs
literal/structural specificity the terse style strips out — not a flat
discount applicable to every number in this file.**

### Institutionalizing the regression gate

§4Z's critique was explicit: 2 anchors is a start, but the discipline
that prevents silent regression is running them on every prompt
change automatically, not when someone remembers — and this project
already has one documented instance (§4T's c6608467) of a fixed bug
regressing silently on the exact prompt that had fixed it. Concretely:
added `pytest.ini` registering a `regression_gate` marker, tagged all 5
anchors in `test_live_e2e_execution_validation.py` with
`@pytest.mark.regression_gate` so they run as one named command
(`pytest -m regression_gate`, confirmed at the time: 5 selected, all
passing — since grown to 6 with the field_ref anchor added later this
same round, see below), and added a project-root `CLAUDE.md` — read automatically
by every future Claude Code session in this repo — stating the rule
directly: run the gate after any edit to `extraction_agent.py`,
`ir_builder_agent.py`, or `ir_interpreter.py`, before considering that
edit complete. This is the most credible enforcement mechanism actually
available in this environment (no CI/branch-protection exists here) —
weaker than a real merge gate, honestly reported as such, not
oversold.

### What's still open after this round

- The field-to-field comparison gap is fixed and live-verified
  (`Filter.field_ref`) — no longer open.
- `arg_max_in_join`'s broader accuracy at the same n=15 scale as the
  rest of this round's table, re-measured after the field_ref fix (the
  5/5 live check confirms the fix works, but isn't the same as a fresh
  batch-scale number).
- RAG remains correctly deferred, per the critique's own sequencing: it
  changes the system rather than measuring it, and is only honestly
  testable against a frozen held-out slice this project doesn't have.
- Cost/latency is now logged per query (`run_synthesis_eval.py`,
  `run_real_eval.py`) but only over these two batches — not yet a
  stable, citable number.
- The Azure AI Foundry key rotation remains unconfirmed.

---

## 4AB. Two real operator gaps closed, a field_ref-regression validator
     check generalized from a one-off fix, and a 40%-fire-rate anomaly
     finally traced to its actual cause (a fixture bug, not a model gap)

A frequency check against this project's own verified+held-out corpus
(not the broader uncounted raw corpus) found `=~`/`!~` (case-insensitive
equality) at **13 occurrences** — more than several constructs already
treated as core (e.g. `make-series`, 9) — and never counted by the
§4X/§4Y audit at all. Found while chasing a real ground-truth case (a
base64-encoded PowerShell payload detection) that also uses
`has_cs`/`contains_cs`. Both closed together: `FilterOperator.EQ_CI`/
`NEQ_CI` (`=~`/`!~`) and the full `_cs` family (`contains_cs`/
`startswith_cs`/`endswith_cs`/`has_cs`, + negated) added to
`ir_schema.py`, with compiler support free (the existing generic
`f"{field} {operator.value} {rhs}"` template already handles any new
enum value), validator tautology-detection sets extended symmetrically
(`_NEGATED_OPERATORS`/`_COMPLEMENTARY_OPERATORS`), and interpreter
semantics added (`_eval_single_filter`, a `case_sensitive` parameter on
`_has_term`). Live-verified per this file's own >=5-fresh-cases rule:
9/10 across two independently-phrased fresh NL cases chose `=~`
correctly with no explicit case-insensitivity cue (matching how the
real ground-truth case itself gives none either); 10/10 chose
`contains_cs` correctly for a case-sensitive base64 fragment, never
confusing it with the case-insensitive forms. End-to-end fire/no-fire
confirmed directly against the interpreter on captured live IRs.

**A real, reproducible prompt bug was found WHILE verifying this same
change**: the model wrote `!=~` (not a real KQL operator) instead of
the real negated form `!~`, by analogy with every OTHER negated
operator in this schema being formed by prepending `!` to its positive
spelling (`contains`->`!contains`, `in~`->`!in~`) — `=~`/`!~` is its
own irregular pair, the same way `==`/`!=` is, and nothing in the
original prompt addition said so. Pydantic's enum validation already
rejects it (a hard parse failure, not a silent miscompile), so this
cost wasted repair attempts rather than shipping wrong, but it would
have kept costing them on every NEQ_CI case indefinitely. Fixed with an
explicit non-example in `ir_builder_agent.py` ("If you need a NEGATED
case-insensitive equality check, write operator="!~", never "!=~"").
The lesson this project has stated before, recurring exactly on
schedule: adding a new operator pair without an explicit warning
against the most predictable wrong-by-analogy spelling is asking for
this specific failure, the same way `_COMMON_MISTAKES` exists at all.

**The §4AA `field_ref` fix was independently re-confirmed still
shipping and still passing its regression anchor** (raised externally
as a concern this round) — `Filter.field_ref`, its compiler/validator/
interpreter support, and
`test_process_time_bracketed_by_joined_auth_window_uses_field_ref_not_literal`
are all present and green. What WASN'T built until now: a check for the
model REVERTING to the old broken pattern (writing a real column's name
as a quoted `value` instead of `field_ref`) on a FRESH filter, not just
the one case the regression anchor pins. New validator check
`LITERAL_MATCHES_SCHEMA_FIELD`: a comparison-operator filter (`==`/`!=`/
`=~`/`!~`/`>`/`<`/`>=`/`<=` — deliberately NOT `contains`/`has`/
`startswith`, where a literal coincidentally spelled like a column name
is far more likely to be a real, unusual literal than a mistake) whose
`value` is itself a real in-scope column name is almost certainly a
field_ref expressed the wrong way. This generalizes the literal-
provenance principle from §4P (a literal that should have been
something else, caught by what it actually is) to a second instance of
the same underlying mistake-shape. Covered by
`test_validator_inventory.py` and two dedicated tests (the hard error,
and a confirmation that legitimate `field_ref` usage and non-comparison
operators are never flagged).

**A live audit of every fixture in `test_live_e2e_execution_validation.py`
and `fixture_generator.py`** (prompted by this project's own recurring
"a fixture that over-specifies marks a correct answer wrong" lesson,
now treated as something to actively hunt for rather than wait to
trip over) found and fixed three more instances, all the same shape:

1. **The DGA anomaly test crashed (`KeyError`) instead of failing
   cleanly** whenever the model's "new IP address ... outlier" reading
   led it to group/aggregate on a geo/IP-enrichment field (e.g.
   `DnsResponseIpCity`) the hardcoded fixture never anticipated. Fixed
   by merging `src/synthesis/fixture_generator.py`'s `_placeholder_fields(ir)`
   helper into the fixture's `base_fields` — the SAME decoupling
   mechanism already built for the synthesis eval, just never applied
   to this hand-written integration test. 3/3 clean after the fix.
2. **The OR-list test had the identical crash mode** whenever the model
   wrapped the filter in a `SummarizeStage` (a breakdown-style reading
   of "detects ... requests", computing e.g. `min/max(TimeGenerated)`
   as a "first/last seen" column) — same fix, plus an explicit
   `TimeGenerated` default (`_placeholder_fields` deliberately excludes
   it, assuming the caller provides it, which this fixture didn't).
   4/4 clean after the fix.
3. **`has_all_evasion`'s previously-unexplained ~40% fire rate
   (CONSTRUCT_COVERAGE.md §4Z, flagged as "worth a closer look,
   not chased further") was traced to its actual cause and fixed —
   it was never a real construct weakness.** Three compounding fixture
   bugs, found and fixed in sequence, each one revealing the next:
   (a) the exclusion field is pinned to `"ActingProcessName"` in the
   generator, but the live system varies between
   `Process`/`ActingProcessName`/`TargetProcessName`/`ParentProcessName`
   — confirmed directly against this round's own probing; (b) once
   fixed by reading the field from the system's own NEGATED filter, a
   second bug surfaced: when the model ALSO adds a positive
   confirmation filter first (e.g. `ActingProcessName =~
   "powershell.exe"`), an unrestricted version of the field-finder
   grabbed THAT field instead of the real exclusion field — fixed by
   restricting the match to negated operators specifically
   (`_NEGATED_EXCLUSION_OPERATORS`); (c) the deepest bug, found only
   after (a)/(b): back-translation does not faithfully preserve the
   generator's randomly-drawn flag LIST, and the model correctly
   substitutes a named tool's REAL documented flags instead (existing,
   intentional §4N behavior) — sometimes adding flags, dropping one, or
   respelling one (`"-w hidden"` -> `"-windowstyle hidden"`). The
   fixture was checking `has_all` against the GENERATOR's flags, not
   the SYSTEM's own — the literal-value version of the same field-
   identity-coupling lesson, one layer deeper. Fixed by reading the
   has_all filter's own value list from the system's IR
   (`_has_all_flags_for`), falling back to the generator's draw only
   when the system has no has_all filter at all. **Re-measured after
   all three fixes, n=15 fresh draws: fire 14/15 (93.3%), nofire 14/15
   (93.3%), 0 field_mismatch — up from the 40% this round started
   with**, and the 1 remaining fire miss and 1 nofire miss were not
   re-investigated this round (diminishing returns past three
   compounding fixes on one template).

**Net effect**: every fixture audited this round either already had no
gap, or had one found and fixed — zero remaining unexplained anomalies
in this file's own per-construct accuracy claims as of this round. The
discipline this enforces going forward: an unexplained or flat-looking
per-construct number is now a fixture-audit prompt before it's reported
as a real ceiling, not after.

**One genuine, previously-uncharacterized mechanism behind the
`5b6ae038` sdelete case's long-standing flakiness (§4K's single most
persistent unresolved item, a different broken variant every round) was
found and fixed**: the model sometimes wrote the renamed-binary
exclusion's `!endswith` value as the BARE tool name (`"sdelete"`)
instead of the full filename with extension (`"sdelete.exe"`) — and
`"sdelete.exe"` does not, in fact, end with the substring `"sdelete"`
(it ends with `".exe"`), so the truncated value silently fails to
exclude the literal-name case it exists to exclude. Fixed with an
explicit worked-example clarification + non-example. **10/10 trials
after the fix never reproduced this specific mechanism again** (was
reproducing roughly every other run before), but **1/10 trials still
failed via the separately-known, pre-existing mechanism** (the model
inventing a different/incomplete flag set than the one a hand-written
synthetic test fixture expects) — confirming this case has multiple
INDEPENDENT failure mechanisms compounding, exactly as every prior §4K
round suspected but never isolated this specifically. One mechanism
closed, one honestly still open; this case remains the project's
single hardest-to-fully-stabilize live test.

### Scaling combination-first to n=100 found a real, fixed bug — exactly the seam-failure pattern this sampling strategy exists to surface

Per the explicit critique that "the field_ref gap proves chains are
where the real failures are," the synthesis eval was re-run at
combination_fraction=0.65 (up from 0.5), n=100 (up from 60) —
`run_synthesis_eval.py` gained a `--combo-fraction` flag for this.
**Overall: 100% completion across every template, 0 crashes, 25,403
avg tokens / 6.3s per query, 627s total** — the cost/latency claim is
now anchored at this larger n, not just §4AA's 60.

**A real, previously-unknown field-confusion bug was found in this
run, not a fixture artifact**: `make_set_mv_expand_filter` scored only
50% fire (n=26) — reading the raw output directly (not just the
aggregate number) showed the model sometimes applying a URL-extension
suffix check (`.ps1`/`.scr`/`.vbs`) to **`SrcIpAddr`** instead of
**`Url`** — e.g. `where SrcIpAddr has ".ps1"`, which is never
meaningful (an IP address has no file extension). Root cause: NL
phrasings like "a source IP address accesses web URLs ending with
.ps1" put the actor (source IP) as the sentence's grammatical subject
and the actual property-bearing entity (the URL) later and less
prominently — an easy but wrong pattern-match onto whichever field is
mentioned first/most. Fixed with an explicit worked-example in
`ir_builder_agent.py` naming this exact mechanism ("a property belongs
to the field of the THING it's actually a property of, not the field
of whichever entity is the sentence's grammatical subject"). Verified
directly against the two exact failing NL patterns: all trials after
the fix correctly filter `Url endswith ".ps1"`/`".vbs"` (the earlier
incorrect `SrcIpAddr has "..."` checks present in some trials' output
were re-examined and are a SEPARATE, benign near-universal-true
sanity check on a different value — not the same bug recurring).

**One anomaly found but not chased this round**: `parse_then_summarize`
scored 64% nofire (n=25); a sample of the raw failures showed two sub-
cases — most are the already-understood "the model finds a different,
equally valid grouping that a single nofire fixture doesn't anticipate"
pattern, but 2/9 show a fully EMPTY pipeline (`stages: []`,
`source_table: WebSessionEvent` only) on a specific NL pairing two
distinguishing entities together ("the same LDAP host... more than
three times"). Logged, not investigated further this round — flagged
here so it isn't silently lost.

### A local, three-corpus retrieval-augmented (RAG) capability, built and wired in behind an opt-in flag

The single largest unstarted item across §4Z/§4Y/§4AA's own "what's
still open" lists. Built exactly as scoped: three SEPARATE,
independently-routed indexes (not one pooled index — mixing "how do I
phrase this" queries against a dry operator-syntax page, or vice
versa, was the explicit failure mode to avoid), using local TF-IDF +
cosine similarity (`scikit-learn`) rather than embeddings — this
project's corpus sizes (669 KQL operator/function doc pages, 14 ASIM
schema pages, 66 worked examples) don't need a managed vector service,
and TF-IDF is a deterministic, zero-API-cost, well-suited match for a
fundamentally lexical retrieval task (operator name -> doc page, event
type -> schema page) on a small technical-vocabulary corpus — no new
embedding deployment or vector-DB binary dependency required.

**Corpora**, all real, officially-sourced, sparse-checked-out locally
(`.rag_corpora/`, gitignored):
1. **Construct syntax/semantics** — `MicrosoftDocs/dataexplorer-docs`,
   `data-explorer/kusto/query/` subtree (669 files, one per operator/
   function) — the exact official source the §4X `has_all` bug (the
   prompt claimed a real operator "doesn't exist") would have been
   grounded against.
2. **ASIM field definitions** — `MicrosoftDocs/defender-docs`
   (`public` branch — Sentinel docs moved out of `azure-docs` into this
   unified repo since this project's own ASIM extraction was last run;
   confirmed live, not assumed, after an initial wrong guess at the
   old `azure-docs` location came back empty), `sentinel/
   normalization-schema-*.md` (14 files, matching this IR's 7 event
   types plus 7 more). Field-level descriptions this project's
   existing `data/schema/asim_field_reference.json` deliberately
   doesn't carry (a bare name list for the validator, not
   documentation).
3. **Worked NL->KQL examples** — this project's OWN train-split
   verified pairs (`data/processed/pairs_verified.jsonl`, filtered to
   `data/splits/train_ids.json`, 66 of 81) — never the test split,
   never the held-out set, so a held-out A/B stays honest. The
   original ask was mining Hunting Queries/Solutions fresh; this
   project already did exactly that extraction for dataset
   construction (`src/data/pull_detections.py`) — reusing the verified
   result here is not skipping the work, it's not redoing already-done
   work.

**Built**: `src/retrieval/retriever.py` (`TfidfRetriever` — build/
save/load/query, ~60 lines), `src/retrieval/build_indexes.py` (one-time
offline preprocessing, strips Microsoft Learn boilerplate — YAML
frontmatter, version-applicability admonitions, moniker blocks, encoded
deep-link buttons — that otherwise dilutes both TF-IDF term weighting
and prompt token budget). Wired into `ir_builder_agent.py` via a new
`{retrieved_context}` prompt section and an `IRBuilderAgent(use_rag=...)`
constructor flag, defaulting to reading `USE_RAG_RETRIEVAL` from the
environment — **off by default**; this is an additive experiment being
measured against the existing, already-measured default path, not a
silent replacement of it. Confirmed the off-by-default path is
byte-for-byte unaffected: full regression gate green with RAG untouched.

**A real bug was found and fixed while verifying retrieval quality,
before trusting any of it**: querying the ASIM schema index with the
bare enum value (`"ProcessEvent"`) returned ZERO hits, every time —
TF-IDF's tokenizer splits on word boundaries, not casing, so
`"processevent"` as one token shares no vocabulary with the doc's
"process event" as two. Fixed with `_split_camel_case`
(`"ProcessEvent"` -> `"Process Event"`) applied to the query before
retrieval; confirmed live this single fix took ASIM schema retrieval
from 0/3 to 3/3 on the project's own event types. Construct-doc
retrieval quality is honestly mixed on inspection (exact-vocabulary
queries like "mv-expand array to rows" retrieve the right page; vaguer
ones miss) — a disclosed, known limitation of lexical vs. semantic
matching, not silently asserted as solved.

**The A/B measurement this needs before any accuracy claim**: per this
project's own standing rule ("RAG built without a frozen comparison
has nothing honest to prove against"), `eval/run_rag_ab.py` runs the
full, frozen 18-rule held-out set (`eval/held_out_test.json` — already
real, fresh, and excluded from the worked-examples index by
construction) through System B with RAG off, then on, measuring
completion and FVR for both — directly satisfying this round's other
two open asks at once ("a fresh, never-debugged real sample" and "a
frozen slice to A/B RAG against") with one run, since this held-out set
already IS both: real (not synthetic), never used to build the RAG
index, the prompt's worked examples, or any tuning round.

**First result looked like a real, negative finding — and was actually
a THIRD instance of a bug this project has now found three times**:
SVR identical both conditions (94.4%, 17/18), but FVR measured 88.2%
(base) vs. 82.4% (RAG) — RAG apparently HURTING field validity.
Tracing the one differing case (not just trusting the aggregate, this
project's own standing discipline) found the cause immediately:
`eval/metrics.py`'s FVR heuristic doesn't recognize `make-series`/
`series_decompose_anomalies` syntax at all — `make-series` tokenizes
as "make"/"series" (the hyphen breaks word-boundary tokenization) and
neither word was in the keyword list; `series_decompose_anomalies`'s
own tuple-destructuring output shape (`"(A, B, C) = ..."`) isn't a
single-name assignment `_ASSIGNMENT_TARGET`'s pattern matches, so its
3 alias names were wrongly counted as unresolved schema fields too.
**The exact same bug class already found and fixed once for
"percentile"** (this file's own §1 methodology notes) — `eval/metrics.py`
was last updated before `make-series`/`series_decompose_anomalies`
were added to the IR (§4X) and never re-synced, undercounting FVR on
every query using either since. Fixed (`_KQL_KEYWORDS` +
`from`/`to`/`make`/`series`/`series_decompose_anomalies`; a new
`_TUPLE_ASSIGNMENT_TARGETS` regex for the destructuring-assignment
shape), with a dedicated regression test. **Re-scored after the fix:
base and RAG are IDENTICAL — SVR 94.4%/94.4%, FVR 94.1%/94.1%.** The
honest finding is therefore not "RAG hurts FVR" (an artifact) but "no
measurable SVR/FVR difference detected at n=18" — RAG (off by
default) neither helped nor hurt on these two automated metrics at
this sample size. 13/18 cases produced textually different KQL between
conditions (expected baseline temperature=0 variance alone, per this
project's own extensively-documented non-determinism finding,
accounts for some of this) without moving either aggregate metric.
**This result does NOT measure Logic Correctness** — only completion
and field validity. That read was done immediately after, in §4AC
below, since SVR/FVR structurally cannot see the difference RAG is
predicted to make.

---

## 4AC. The Logic Correctness read on the RAG A/B, an independent
     second rater with a measured Cohen's κ, and three more live-found
     bugs traced and fixed

Direct continuation of §4AB. Per the explicit critique that SVR/FVR
"can't move" on the axis RAG is supposed to help (literal/structural
specificity, the exact thing the terse-NL experiment showed mattered),
all 18×2=36 saved outputs in `eval/results/rag_ab_raw.json` were scored
on this project's standard 3-point rubric (event type/table correct;
comparison/direction not inverted; aggregation/grouping matches
intent) against each case's `ground_truth_kql`, with abstentions on
genuinely out-of-scope cases (external watchlists, ThreatIntelligence
joins, `externaldata()` CSV feeds — present in roughly half this
held-out set) scored as a pass when the table is right and nothing
invented is wrong, consistent with this project's standing "omit,
don't invent" policy (§1.8/§4U).

**Rater 1 (this session) result: base 39/54, RAG 45/54 — RAG ahead.**
Then, per the standing top open item (§5), an independent second rater
— a fresh agent given only the raw NL/ground-truth/generated-KQL data,
with zero visibility into Rater 1's scores or reasoning — scored the
identical 36 outputs from scratch. **Rater 2 result: base 48/54, RAG
45/54 — base ahead.** The two raters disagree on which condition wins.

**Computed properly (`sklearn.metrics.cohen_kappa_score`), not just
eyeballed**: raw agreement 61.1%; unweighted Cohen's κ = 0.253 ("fair"
per Landis-Koch); quadratic-weighted κ = 0.702 ("substantial") — the
weighted figure is the right one to lead with since these are ordinal
0-3 scores, not unordered categories, and the raters' disagreements
are mostly off-by-one, not polar-opposite. **The honest summary: the
two raters substantially agree on individual query quality, but that
agreement is not strong enough to make the aggregate "RAG wins" vs
"base wins" comparison robust at n=18** — exactly the second-rater
check this project has needed since §4B, now actually run instead of
deferred again, and it produced a real, non-trivial answer: don't cite
a directional RAG claim from this sample size with this rubric.

**What IS robust — every case where both raters independently agreed
on direction, regardless of magnitude:**
- **RAG meaningfully worse**, both raters agree, on `dedb8fb9`
  (SonicWall outbound SSH/SCP): RAG's retrieved context led it to AND
  `EventVendor`/`EventProduct` fields with the port check, dropping the
  NL's actual OR-structure ("port 22 **or** SonicWall DPI services")
  into a narrower AND, and dropped the `NetworkDirection == Outbound`
  filter entirely — a real, attributable RAG regression, not noise.
  Plausible mechanism: the retrieved ASIM `NetworkSessionEvent` schema
  page surfaces `EventVendor`/`EventProduct` prominently, and the model
  anchored on them at the expense of logic already correct in the
  baseline path.
- **RAG meaningfully better**, both raters agree, on `01191239` (NXDOMAIN
  DGA anomaly) and `f82c89fa` (IFEO registry persistence) and
  `9b72769e` (ZOHO ManageEngine file drop). The first two share a
  precise mechanism: base computed an aggregation (`NXDomainCount`,
  `EventCount`) that never actually filtered to the specific sub-
  condition its own name claimed (NXDOMAIN responses; created+deleted
  registry events) — a real, silent metric-mislabeling bug independent
  of RAG — while RAG's retrieved worked examples and schema context led
  it to add the correct filter first. `9b72769e` is the construct-
  selection finding already flagged in §4AB: RAG avoided inventing an
  unrequested aggregation a hunting-style "find these events" NL never
  asked for.
- **Not robust** (raters disagree on direction): `50f0cdfb`, `70e2a349`,
  `c6608467`, `2d1a3e86` — each hinges on a judgment call (how strictly
  to enforce "increase" vs. any anomaly direction; whether a watchlist-
  driven port-threshold abstention's substitute aggregation counts as
  "matching intent"; whether adding a report-style summarize to an
  NL phrased as "this rule detects X" counts as inventing structure)
  that the rubric itself doesn't pin down precisely enough for two
  raters to convergently apply. This is itself a finding: the rubric's
  treatment of "reasonable reinterpretation vs. invented structure" is
  the next thing to tighten, not the raters' competence.

**Net assessment**: RAG is not validated by this experiment, and it
is not ruled out either — both would overclaim. The single robust,
attributable regression (`dedb8fb9`) is real and worth fixing (the
retrieved-schema-anchoring mechanism is now named and falsifiable: test
whether suppressing `EventVendor`/`EventProduct` from the retrieved
ASIM chunk when a more specific filter is already present in the NL
fixes it). The two robust wins are real but their root cause (silent
metric-mislabeling in the IR Builder, independent of RAG) suggests the
fix belongs in `ir_builder_agent.py`'s prompt guidance regardless of
RAG, not as a RAG-specific capability — confirmed by checking: neither
case's win depended on anything in the retrieved chunks beyond what a
sharper worked example could also teach. **RAG's case rests on the
non-robust cases, which is the same conclusion as not having a case
yet** — more data (a larger frozen slice, run through this same
independently-double-rated process) is the honest next step before
RAG either ships on by default or gets shelved, not a coin-flip on
n=18.

Full per-case data: `eval/results/rag_ab_logic_correctness_scoring.json`.

### A real, independent-of-RAG bug found and fixed while tracing the robust wins

Both robust RAG wins (`01191239`, and the analogous case in the n=100
scale-up) shared one mechanism: a `SummarizeStage` aggregation whose
`result_alias` NAMED a specific subset of events ("NXDomainCount",
"EventCount" for "creation and deletion") but whose aggregation
function never actually filtered to that subset first — the alias lied
about what the number measured, invisible to every check except a
literal logic read. Fixed with new `_COMMON_MISTAKES` guidance in
`ir_builder_agent.py`: a result_alias naming a subset is a promise that
a WhereStage filtered to exactly that subset before the aggregation;
this IR has no `countif`-equivalent, so filter-then-count is the only
correct shape. **Live-verified 5/5** on the exact NL that exposed the
bug — every trial now correctly adds `where DnsResponseCodeName ==
"NXDOMAIN"` before the make-series stage. Full regression gate
re-confirmed green (5/6 — the one residual is the sdelete case, traced
further immediately below).

### The two logged-but-unchased anomalies, investigated

**`5b6ae038` sdelete flag-set failure, mechanism now pinned precisely
(not just "still happens")**: instrumented the Extraction Agent's own
output directly. It correctly extracts the real flags
(`["accepteula", "-s", "-r", "-q"]`) into `candidate_fields` on every
trial, 5/5 — extraction is not the problem. The IR Builder ignores that
already-correct list 1/5 times and invents `-p` instead — the EXACT
wrong flag the prompt's own worked example already explicitly warns
against by name ("never invent a plausible-sounding flag (e.g. `-p`)").
This is not a missing-guidance gap — the guidance exists, names this
exact failure, and the model still produces it on a fifth of trials.
Re-classified from "unfixed" to "not fixable by more prompting" — a
raw model-reliability residual, the same category this project's own
non-determinism findings have always allowed for, now confirmed rather
than assumed for this specific case after one more genuine attempt.

### Checking whether the property-on-wrong-entity fix generalizes, or just patched one case

The §4AB fix (`SrcIpAddr`/`Url` confusion) was a single worked example
naming the principle ("a property belongs to the entity it's actually
a property of, not the grammatical subject"). Per the `field_ref`
precedent — where a fix for one case turned out to generalize across
an entire construct family — two FRESH entity/property pairs never
targeted by that worked example were live-probed, 5 trials each:
**"ports on connections, not users"** ("a user account establishes a
connection to a destination port ending in 89") and **"hashes on
files, not processes"** ("a process writes a file whose SHA256 hash
starts with..."). **Neither reproduced the bug class — 10/10 trials
correctly filtered the port/hash fields, never the user/process
fields.** This is a smaller check than the originally-scoped 3-4
synthesis templates (time-boxed to 2 live-probed pairs instead), but it
is a real, live result, not an assumption: the single worked example's
stated PRINCIPLE generalized to two pairs it was never written for,
the same pattern `field_ref` showed. Not exhaustive — a fuller
synthesis-template version of this check (matching the rigor of the
construct-coverage work) remains a reasonable next step, not done here.

**`parse_then_summarize` empty-pipeline anomaly, NOT reproducible in
isolation**: the exact NL that produced an empty `stages: []` pipeline
in the n=100 batch run ("...that host is contacted more than three
times within an hour...") was re-run 4/4 clean (proper 3-stage
pipelines, correct `Url contains "ldap://"` filter, correct grouping
and threshold) when issued standalone, outside the original seeded
batch. Could not reproduce the empty-pipeline failure on demand after
a genuine attempt — consistent with rare temperature=0 stochastic
output rather than a deterministic phrasing trigger. Logged as
investigated-and-not-reproduced rather than silently dropped; if it
recurs at scale again, the next step is capturing the exact failing
trial's raw LLM completion (not just the parsed IR) to see whether the
model returned a genuinely empty `stages` array or a repair-loop
exhaustion that happened to leave one behind.

---

## 4AD. The alias-implies-filter validator (two rejected designs before
     a working one), regression-gate policy fix, RAG simplification,
     and a newly-confirmed severe finding: empty pipelines don't fail
     safely

Direct continuation of §4AC, working through the prioritized list that
round's findings produced.

### Generalizing the NXDomainCount bug into a validator check — two false starts, measured and rejected, before the one that shipped

The NXDomainCount bug (§4AC) is the same meta-shape as the `field_ref`
bug and the property-on-wrong-entity bug: an artifact (here, an
aggregation's `result_alias`) claims something its own structure
doesn't deliver. Built `LITERAL_MATCHES_SCHEMA_FIELD`'s natural next
instance, `_collect_alias_implies_filter_warnings`, calibrated live
against fresh train-split queries before shipping (this project's
standing §4P discipline) — **two designs were tried and rejected on
measured false-positive rate**:

- **v1 (stoplist)**: flag any camelCase token in a `result_alias` not
  in a generic-words list. 4/12 fired, **4/4 false positives** —
  "DistinctProcesses", "QueriedDomains", "SubdomainCount",
  "AdFindHashes" all name the KIND of thing aggregated (a content
  descriptor), not a condition filtered to; no stoplist can tell that
  apart from a real example like "NXDomain."
- **v2 (curated allowlist)**: narrow the check to real ASIM status/
  outcome vocabulary ("failed", "error", "nxdomain", ...). Re-
  calibrated on a fresh 15-query sample — **still 2/2 false
  positives**. Both had a perfectly correct upstream filter
  (`HttpStatusCode >= 400` for "ErrorCount"; `EventResult != "Success"`
  for "FailedConnectionCount") that substring matching couldn't
  recognize, because a correct filter almost always uses SCHEMA
  vocabulary (field names, enum values, numeric thresholds), not the
  natural-language word the alias happens to use. NXDomainCount's
  original bug was only substring-checkable because DNS response
  codes are a rare case where the schema's own enum value IS the
  natural-language word — not the general case.
- **v3 (shipped)**: stopped trying to match WHICH filter corresponds
  to WHICH word — instead check WHETHER any `WhereStage` filter exists
  upstream AT ALL before an aggregation whose alias implies a
  condition. The original bug's actual shape was zero preceding
  filters of any kind, not almost-right vocabulary. Re-calibrated on a
  fresh 20-query sample: **0/20 false positives**. Lower recall (a
  real wrong-vocabulary mismatch wouldn't be caught) but the only one
  of the three with an acceptable precision, confirmed rather than
  assumed. Advisory, not a hard error, same as every other warning at
  this calibration tier.

### Regression-gate policy: 3/5, not a fixed annotation

The sdelete anchor's single-build pass/fail was correctly flagged as
training the gate's signal into noise — re-measuring the assumed "~1/5"
failure rate directly (this round) found more variance than one
session's worth of anecdotes suggested: one batch of 5 scored 3/5, a
second scored 5/5. Rebuilt the anchor to run the build 5 times and
require >=3/5 (60%, the more conservative of the two measurements) on
the fire-check specifically — the two no-fire checks, which have never
been flaky in this project's own measurement, stay at the strict 5/5
bar, so a regression in THOSE is never masked by the relaxed threshold
on the one specific, named, characterized residual.

### RAG simplified: construct-doc retrieval dropped, ASIM-schema and worked-examples kept

Per the measured evidence (§4AB's "honestly mixed" construct-retrieval
quality spot-check, §4AC's full A/B finding no credit-worthy Logic
Correctness benefit): `build_construct_index()` and its
`MicrosoftDocs/dataexplorer-docs` corpus removed from
`src/retrieval/build_indexes.py`; `_retrieved_context()` in
`ir_builder_agent.py` no longer queries it. The two indexes that
measured real value (`asim_schema.pkl`, 3/3 correct retrieval;
`worked_examples.pkl`, used in every robust win traced in §4AC) are
kept. Re-adding construct retrieval is explicitly scoped as future work
*if* testing semantic embeddings instead of TF-IDF — the wash result
is specific to lexical retrieval, not a verdict on RAG in general.

### A newly-confirmed, severe finding: an abstaining pipeline doesn't fail safely — it fires on everything

Re-running the full regression gate after the above changes hit a
**different** anchor failure than the known sdelete residual:
`test_cve_id_is_not_used_as_literal_command_line_content` failed with
`stages=[]` — the IR Builder, unable to ground any concrete filter for
an under-specified CVE exploit description, produced a `KqlPipeline`
with a `source_table` and a caveat but **zero stages at all**. Re-run
3 times: **1/3 reproduced the same empty-pipeline shape.** This is not
a new bug in the mechanism that produces it (the "omit, don't invent"
caveats design, §4U, has always allowed full abstention when nothing
is groundable) — it is a newly-confirmed, more severe consequence of
that design than previously stated: a pipeline with no `WhereStage` at
all does not fail closed, it fails *open* — `pipeline_fires()` returns
`True` for literally any input row, because there is no filter to
reject anything. In real KQL, `imProcessCreate` with no `where` clause
matches every process-creation event in the table. Checking back
against §4AC's own Logic Correctness scoring: **3 of the 18 RAG A/B
cases** (`e2559891`, `6a4dbcf8`, `67775878` — all scored as "honest
abstention, 3/3 pass" at the time) have exactly this shape and were
credited as correct without this consequence being weighed. That
scoring is not retracted — an honest abstention is still better than
an invented filter — but "honest" and "safe to deploy as-is" are not
the same property, and this round is the first time that distinction
has been named explicitly rather than collapsed into one. **Not fixed
this round** (changing the abstention mechanism's behavior — e.g.
refusing to emit a rule at all below some grounding threshold, versus
emitting a structurally-disabled placeholder, versus accepting the
current behavior with a louder caveat — is a real design decision, not
a bug fix, and deserves a deliberate choice, not one made implicitly
while finishing an unrelated punch list). Flagged as the single most
important newly-found item for next steps, ranked above all of §7's
existing items below.

### κ-bounding the main headline number, not just the RAG question

The RAG A/B's "base" condition (no RAG) is System B run on exactly the
same 18-rule held-out set this project's headline generalization
figure (median 82.4%, IQR 5.9, N=5) is built from — so the same two
independent-rater data already collected in §4AC bounds THAT number
too, not just the RAG comparison, with no new scoring run needed.

**Base-only, both raters, 3-point rubric**: rater1 39/54 (72.2%
average), rater2 48/54 (88.9% average). Raw agreement 55.6%.
**Quadratic-weighted κ = 0.645** ("substantial," Landis-Koch). Recast
into this project's own historical BINARY pass/fail convention (>=2/3
counts as a pass, the closest equivalent to how 82.4% was originally
computed): rater1 72.2% pass rate, rater2 **94.4%** pass rate, **κ =
0.265 ("fair")** — markedly weaker than the ordinal figure.

**This is the headline methodological finding from applying κ to the
main number**: forcing Logic Correctness into a single binary pass/
fail, as every prior round in this project's history has done, hides
exactly the kind of inter-rater disagreement the ordinal scoring
surfaces. The two raters substantially agree on relative QUALITY
(κ=0.645) but diverge sharply on where the pass/fail LINE falls for
borderline cases — both raters call the same case "B-minus," but one
rounds it to "pass" and the other to "fail." The project's own
historical 82.4% sits, reassuringly, almost exactly between this
round's two fresh raters (72.2%, 88.9%) — some evidence the headline
figure isn't systematically biased — but the spread itself (16.7 points
between two simultaneous raters on the identical 18 outputs, before
any model non-determinism enters at all) is now a measured, citable
number, and it is wider than this project's own N=5 replication's
IQR (5.9 points, §4V) captured, because that replication only varied
the MODEL's output across runs, never the RATER. **The honest combined
claim**: held-out Logic Correctness is best reported as 82.4% (model
run-to-run IQR 5.9, N=5) ± a separately-measured inter-rater spread of
order 15-20 points (N=1 rater-pair) — two different, both real,
sources of uncertainty that have never previously been combined into
one statement.

### Assembling the synthetic-vs-real gap into one number

Every piece existed across separate rounds; never assembled into one
comparative statement:

- **Synthetic, n=100, combination-weighted (§4AB)**: 100% completion,
  84.2% fire / 96.2% nofire execution-validated accuracy.
- **Terse-NL degradation, identical underlying IRs (§4AA)**: fire
  accuracy 90.9% (rich) -> 54.5% (terse), concentrated almost entirely
  in `parse_then_summarize` (the one construct whose correct
  implementation depends on the NL naming a specific literal pattern).
- **Real held-out, n=18, two independent raters (§4AC/§4AD)**: 72.2%
  / 88.9% (3-point rubric average), median-equivalent close to this
  project's existing 82.4% headline.

**The one sentence**: synthetic Logic Correctness is ~84-96% (execution-
validated fire/nofire) on a uniform, literal-rich back-translation
style; real held-out Logic Correctness is ~72-89% (two-rater range) on
genuinely varied real phrasing; the gap is not flat across the system
but concentrated in the same place the terse-NL experiment already
named — constructs whose correct implementation depends on the NL
naming a specific literal or structural detail (`parse`-shaped
extraction, exact threshold/window values) survive real-world phrasing
variance far worse than constructs whose structure follows from intent
alone (`arg_max`, `join`, `simple_filter`). This is the difference
between "looks good on data we generated" and "works on what a real
analyst would actually write," named in one place for the first time.

---

## 4AE. Refuse-to-emit shipped and verified; the abstention story
     re-validated; Logic Correctness re-reported in its reliable
     ordinal form; the RAG decision pre-committed

Direct response to the critique that §4AD's abstention finding was
"a correctness emergency," not a weak point — and that it was correct
to rank it above everything else.

### Refuse-to-emit: live-verified, not just unit-tested

`KqlPipeline.abstained: bool` added. `generate_kql()` refuses to emit
a runnable query when `abstained=True` (renders only the caveat
explaining why); `pipeline_fires()` always returns `False` for it,
regardless of what (if anything) ended up in `stages`; the validator
hard-rejects an empty `stages` list that isn't explicitly marked
`abstained` (`EMPTY_PIPELINE_NOT_MARKED_ABSTAINED`); `ir_builder_agent.py`
gained explicit guidance teaching when to set it, preferring a real
partial filter over abstaining whenever even one concrete condition is
groundable. **A real downstream bug was found while verifying this,
before trusting it**: `repair_loop.py`'s syntax validator ran
`validate_kql_syntax()` on the abstained `// ABSTAINED ...` comment
output and correctly found "no table reference," misclassifying every
legitimate abstention as a `TEMPLATE_BUG` — fixed by skipping syntax
validation specifically when `ir.abstained`. **Live-verified 5/5** on
the exact case that originally exposed the bug (a bare "known IoC"
reference with zero concrete values): every trial now produces
`abstained=True`, zero stages, and the compiler's refusal — confirmed
it never fires on arbitrary input. A new permanent regression anchor,
`test_total_abstention_never_fires_on_anything`, was added — confirmed
stable across 4 consecutive runs. Full regression gate: 7/7 anchors
green (was 6).

### The abstention story, re-validated, not just patched

Re-ran the three RAG A/B held-out cases that had scored "3/3, honest
abstention, correct" under the OLD silent-empty-pipeline shape
(`e2559891`, `6a4dbcf8`, `67775878`) through the fixed system. **All
three now correctly produce `abstained=True` and are confirmed to fire
on nothing**, where before they would have silently fired on
everything if deployed. The Logic Correctness scores themselves are
NOT retracted — these cases correctly identified the right table and
invented nothing, which is what the rubric's 3rd criterion measures —
but the deployment-safety property the project had been implicitly
assuming alongside that score is now actually true instead of merely
unexamined. This is the honest correction: the SCORES were right, the
unstated ASSUMPTION behind them was not, and now it is.

### Logic Correctness re-reported in its reliable ordinal form

Per the finding that κ=0.265 (binary pass/fail) is markedly weaker
than κ=0.645 (ordinal) on the identical 36 scores — the pass/fail LINE
is where the raters diverge, not the underlying quality judgment —
the held-out base-condition scores are re-reported as a distribution
instead of a single cutoff percentage:

| Score | Rater 1 | Rater 2 |
|---|---|---|
| 3/3 | 50.0% (9/18) | 77.8% (14/18) |
| 2/3 | 22.2% (4/18) | 16.7% (3/18) |
| 1/3 | 22.2% (4/18) | 0.0% (0/18) |
| 0/3 | 5.6% (1/18) | 5.6% (1/18) |
| **Median** | **2.5/3** | **3.0/3** |
| **Mean** | **2.17/3 (72.2%)** | **2.67/3 (88.9%)** |

This is now this project's standard Logic Correctness reporting
format going forward — replacing the single binary percentage
("82.4% pass") that every prior round used, which inherits the
unreliable κ=0.265 cutoff instability this distribution does not.
Both raters agree the 0/3 case is the same single case (`83e70a34`,
the structurally-unsupported top-1M-exclusion pattern) — full
agreement at the extremes, with the spread concentrated in the
middle of the scale, exactly where a binary cutoff is most sensitive
to which side of the line a 2-vs-3 judgment call lands on.

### The RAG decision: a pre-committed threshold, not another slice

Per the explicit request to define a stopping rule before spending
more measurement on RAG rather than relitigating the same wash: **the
threshold is that RAG-on-by-default would need to move Logic
Correctness by more than this project's own measured binary-cutoff
noise band (κ=0.265, meaning a large fraction of individual case
judgments are rater-dependent at the pass/fail line)**. §4AC's A/B
already measured an effect (45-39 vs 48-45 depending on rater) smaller
than that noise band in both directions. **This is not an inconclusive
result — it is a conclusion: RAG's Logic Correctness effect, at this
sample size and with this rubric, is provably smaller than the metric's
own measurement noise.** The decision: RAG stays off by default; the
ASIM-schema retrieval index (independently measured 3/3 correct,
kept for its own merit) stays; construct-syntax retrieval stays
removed (§4AD); a larger frozen slice is only worth running if a
future change (semantic embeddings instead of TF-IDF, or a
substantially larger n that could move the binary cutoff outside its
own noise band) is specifically what's being tested — not as a repeat
of the same measurement hoping for a clearer signal.

### Outstanding: the human rater

A tool was built (`eval/score_logic_correctness.py`) to make this cheap
to actually do: presents each held-out case's NL, ground-truth KQL, and
generated KQL one at a time, collects a 0-3 score, and computes a third
Cohen's κ against both existing AI raters once run. **This requires an
actual human** — neither rater so far has been one, and that remains
the ceiling on this entire Logic Correctness story exactly as named.
Not run this round; see `eval/score_logic_correctness.py`'s own
instructions to run it.

---

## 4AF. A clarification loop, built on the gap-checker the abstention
     mechanism already implied, live-verified end to end

Direct response to the explicit critique that the system should ask
about under-specified input rather than guess or silently abstain —
defeating the §4C "missing information, not a style problem" wall the
only way actually possible: by asking, not by re-engineering NL
understanding.

**Correction to the request's own status assumptions, stated up
front**: several Tier-2/4 items in that message were already done
earlier this session — `RESULTS_DRAFT.md` is fully current (not
"§4J flat-IR with a staleness banner"); the synthetic-vs-real gap is
already assembled into one sentence (RESULTS_DRAFT.md §5); the
limitations section already states the sdelete floor, the κ=0.265
binary-cutoff instability, and the abstention boundary; the alias-
implies-filter class is already built out via the v3 allowlist
(`failed`, `external`, `admin`, `nxdomain`, and ~35 other curated
terms) plus the "any filter upstream at all" structural check; the
shelved RAG construct-index code is already removed, not just
status-noted; the regression-gate policy fix (3/5 threshold) is
already shipped. Re-verified against actual code/docs before writing
this, not asserted from memory.

### Architecture: gap-checker first, clarification as a thin layer on top — exactly as scoped

`src/clarification/gap_checker.py`: `find_gaps(ir) -> List[Gap]` walks
`KqlPipeline.caveats` (recursing through any join's `right_pipeline`,
mirroring the compiler's own `_collect_caveats`) and turns each into a
structured `Gap` (caveat text, a generated question, a real-data
default where one exists, the affected field, a `kind` classification).
**Why this sits on `caveats`, not a fresh NL-level analysis**: the IR
Builder already detects "missing" at the only point where it's
concrete and typed; re-deriving it from the NL would duplicate that
work and risk disagreeing with the model's own account of what it
omitted. **Why no separate frequency x logic-impact filter is needed
here**: that filtering already happened upstream, at the point the IR
Builder decided whether a given omission was worth a caveat at all —
cosmetic decisions never get one.

Three `kind`s, classified by keyword match on the caveat text:
`missing_time_window`, `missing_threshold`, `missing_value` (the
generic case, with the affected field extracted via a small regex
when the caveat names one). **The time-window default is computed
from real data, not invented**: scanning `data/processed/pairs_verified.jsonl`'s
66 train-split ground-truth queries for `bin(TimeGenerated, X)` bucket
widths gives a real frequency table (1h: 9, 5m: 5, 1m: 3, 15m: 2, 1d: 2,
others: 1 each) — 1 hour, the most common real value, is the offered
default. Threshold gaps deliberately get NO auto-default (no sensible
single number generalizes across event types and aggregation
functions); the user is asked directly.

`src/clarification/clarify.py`: `resolve_clarification(...)` merges
answers back by reusing the EXISTING repair-loop plumbing
(`_build_ir` with a `CLARIFICATION_ANSWERS_PROVIDED` structured
message, the same mechanism every ordinary validation-error repair
already uses) rather than hand-writing AST mutation code. This was a
deliberate engineering choice, not a shortcut: a hand-written mutator
needs separate, bespoke logic for every gap shape (add a WhereStage
filter vs. set `time_window` vs. un-abstain a totally-abstained
pipeline and build a real one from scratch); routing through one more
LLM-mediated rebuild reuses logic this project has already hardened
over ~30 rounds and handles new gap shapes for free.

### Live-verified, not just unit-tested

Two new permanent integration tests, `tests/integration/test_clarification_loop.py`
(its own file, not added to `test_live_e2e_execution_validation.py`,
since that file's own docstring scopes it to one anchor per
historically-fixed bug — this is a fresh capability, not a bug fix):

1. **Total abstention -> real firing pipeline.** The maximally under-
   specified "known IoC" NL (the same one `test_total_abstention_never_fires_on_anything`
   uses to trigger abstention) — answering the gap-checker's one
   question with concrete IP values produces `abstained=False` and a
   real `imWebSession | where SrcIpAddr in (...)` pipeline that
   correctly fires on a listed IP and correctly does not fire on an
   unrelated one. **6/6 clean across 3 repeated runs.**
2. **A different gap kind generalizes.** A watchlist-driven port-
   threshold case (`missing_threshold`, no default offered) —
   answering "500" produces `... | where ConnectionCount > 500`,
   confirming the classifier and resolver both generalize beyond the
   one case they were built against, not just pattern-matched to it.

Both tests pass on a fresh, unmodified codebase with no special-casing
for either NL — the gap-checker found the real caveat each model run
actually wrote, and the resolver's rebuild produced a real, correctly-
scoped filter each time.

### Wired into the Streamlit demo, not left as a backend-only capability

`app.py` now renders the clarification questions (pre-filled with any
real-data default) as a form beneath the System B result whenever
`find_gaps()` finds anything, with a "Resolve" button that calls
`resolve_clarification` and shows the updated query plus any still-
unanswered questions. Verified: imports resolve cleanly, the module
parses, the session-state wiring across Streamlit's rerun-on-submit
model is structurally correct. **Not interactively browser-tested this
round** (the underlying `find_gaps`/`resolve_clarification` logic is
the part actually live-verified, via the pytest integration tests
above) — stated plainly rather than implied.

### Scope, stated honestly — what this does NOT do

Per the gap-checker's own module docstring: this finds **missing**
gaps (a concrete value that isn't groundable at all — the `caveats`
mechanism's entire reason for existing). It does **not** find
**ambiguous** gaps (multiple valid readings of information that IS
present — the §4Q stdev-vs-baseline fork, or count-vs-distinct_count
for "DGA query volume"). Closed-option disambiguation for that second
case needs the model to recognize and report multiple candidate
readings, which neither `caveats` nor this checker do yet. Scoped out
deliberately this round, not silently assumed solved — the missing-
information case is both the more common one (every abstention this
project has ever measured is a missing-information case, not an
ambiguous-reading one) and the one the existing `caveats` mechanism
already detects for free, which is why it came first.

One clarification round only, by explicit design: the resolver is
called once with whatever answers are given; anything still
unresolved afterward is reported back as remaining gaps for the
caller to decide on, not looped into a second automatic round.

---

## 4AG. The real-data before/after measurement, and an honest negative
     result on closed-option disambiguation

Direct continuation of §4AF: clarification was built but its value was
untested at scale. This round measures it on real data and builds the
disambiguation half §4AF scoped out.

### Phase A: 50 fresh real cases, complexity-stratified, clarification OFF — fully automated, no human needed

`src/data/pull_clarification_eval_set.py` pulled from the 93 fresh,
never-tuned-against ASIM-normalized candidates already sitting locally
(`detections_raw.jsonl`/`solutions_raw.jsonl`/`hunting_raw.jsonl` —
confirmed via web search that `Azure/Azure-Sentinel` is still the
active, canonical, MIT-licensed source, so no new clone was needed),
reusing `src/data/tag_complexity.py`'s EXISTING heuristic rather than
inventing a new one. **A real data-quality bug was found and fixed
before trusting the pull**: 24/93 candidates (26%) were "this query has
been deprecated, IoCs are outdated" boilerplate — identical text across
many rule_ids, a degenerate test case either way (a stale-IoC rule's
"correct" behavior is arguably to abstain, testing nothing new) —
filtered out explicitly. Final set: 50 cases (2 simple, 7 moderate, 41
complex — the natural pool skew this project's own §2.1 finding already
documented, not retuned toward an even split the real pool doesn't
support), saved to `eval/clarification_eval_set.json`.

`eval/run_clarification_eval.py` ran all 50 through the system with
clarification OFF (the existing, already-measured default path) and
measured:

| | |
|---|---|
| Completion | 98.0% (49/50) |
| SVR / FVR (non-abstained completions only) | **100% / 100%** |
| Total abstention rate | **60.0%** (30/50) |
| Under-specification rate (>=1 gap found) | **80.0%** (40/50) |
| Gap-checker questions generated | 55 |

**A measurement bug was found and fixed before trusting the headline
SVR/FVR**: the first pass scored SVR at 38.8% by running syntax
validation over EVERY completion's KQL, including abstained ones —
but an abstained pipeline's `// ABSTAINED ...` comment is intentionally
not valid KQL (§4AE's whole point). Restricted to the 19 non-abstained
completions: **SVR and FVR are both 100%**, consistent with this
project's entire history — the deterministic compiler does not
silently degrade on fresh real input. The corrected, real headline is
the **80% under-specification rate**, not a depressed syntax number.

**This is the single most important number this round produced**: on
fresh, real, never-tuned-against Azure-Sentinel detection rule
descriptions, **4 out of 5 genuinely lack enough concrete information
to build the exact intended detection without either inventing values
or asking** — confirming, at real scale for the first time, the §4C
finding that started this entire abstention/clarification line of
work ("the `sop`/`original` gap is missing information, not a style
problem"). This was previously a documented but small-sample
observation; it is now a measured, citable property of this dataset.

**A cheap automatic false-positive pre-screen** (does the NL already
contain a number, for threshold/time-window gaps specifically — not a
substitute for the human precision read item 3 below still owes, but
needs no answers at all) flagged 3/55 questions (5.5%). Inspecting
those 3 by hand: all three are the pre-screen's OWN false positive
(matching a digit inside an actor name like "Dev-0322" or a CVE-style
identifier, not a real omitted threshold) — zero confirmed bad
questions among the 55 after this check, a reassuring if partial
signal pending the real precision measurement.

### Phase B (mechanical half): the question set is generated, answers are not — by design

All 55 questions are saved in `eval/results/clarification_eval_raw.json`,
one `human_answer: null` slot per gap. This is the explicit handoff
point: per this project's own "missing vs. ambiguous" framing, answers
must come from a human (the user, or a separate rater) — answering from
this project's own ground truth would leak the test. Re-run
`eval/run_clarification_eval.py --resolve` after filling in answers to
complete Phase C's automatable half (the resolution-rate measurement —
does answering actually fix the query — still needs the answers to
exist first).

### Closed-option disambiguation: built, schema-sound, and an honest negative result on auto-detection

Per the explicit scoping request, built the second half of "the input
doesn't fully determine the query": `Ambiguity` (description, >=2
`options`, `picked_option`) added to `KqlPipeline`; `find_ambiguities`/
`resolve_ambiguity` added to `src/clarification/`, sharing the same
rebuild plumbing as `resolve_clarification` via a new
`_rebuild_with_instruction` helper. Prompt guidance added with this
project's own two documented real ambiguous cases as worked examples
(recycle-bin ProcessEvent-vs-FileEvent, §4T; DGA count-vs-dcount,
§4N) — the two clearest, cleanly-two-option forks already in this
project's history; the murkier §4Q stdev-vs-join case was not used as
a worked example since it was characterized as a verifier false-
positive pattern, not a clean structural fork.

**Live-verified, with a real negative finding**: run on its own two
documented worked-example NLs, 3 trials each, BEFORE shipping —
**0/6 populated `ambiguities`, even on the exact cases the worked
examples were written about.** Strengthened the prompt with an
explicit, mandatory pre-finalization self-check ("could a different,
equally reasonable analyst land on a different reading, with no
further detail to break the tie?") and re-ran — **still 0/6.** This is
reported as a genuine, measured negative result, not silently
papered over: **the schema and resolution mechanism are sound** (4/4
unit tests pass on manually-constructed `Ambiguity` objects, including
join recursion and the `min_length=2` constraint; `resolve_ambiguity`
live-verified 3/3 correctly switching `source_table` and rebuilding a
valid pipeline once an ambiguity IS supplied) — **the open problem is
specifically getting the model to self-trigger detection**, not the
infrastructure around it. Plausible mechanism, not yet tested: every
other instruction in this prompt reinforces decisive, single-
interpretation construction; asking the SAME generative call to also
actively monitor itself for forks it's busy resolving may need a
structurally different approach (e.g. a dedicated second call whose
only job is ambiguity-scanning) rather than one more bullet point in
an already-long instruction list. Next step, not done this round.

**A real, separate bug was found and fixed while live-testing the
resolver**: `resolve_ambiguity`/`resolve_clarification` originally
called the IR Builder exactly once with no repair attempt, unlike the
normal pipeline's up-to-3-attempt loop — found live when un-abstaining
the recycle-bin case into `ProcessEvent` produced an ordinary
`FIELD_NOT_FOUND` (`ProcessPath` instead of `Process`) that the
NORMAL repair loop would have simply self-corrected, but the bare
single-shot rebuild had no chance to. Fixed with a small bounded retry
(`_MAX_REBUILD_ATTEMPTS = 2`) inside `_rebuild_with_instruction` —
there's no principled reason a clarification rebuild should be more
fragile than an ordinary build just because it's one call instead of
the full loop. Re-verified 3/3 clean after the fix.

---

## 4AH. The dedicated ambiguity-scan call — §4AG's negative result
     closed, with the exact mechanism it predicted

§4AG ended with a measured negative result (0/6 self-report auto-
trigger, even on the IR Builder's own worked-example NLs, even after a
second round of prompt strengthening) and a named, untested hypothesis:
the IR Builder's prompt trains decisive single-interpretation
construction so thoroughly that asking the SAME call to monitor itself
for forks is structurally self-defeating — a dedicated second call
whose ONLY job is ambiguity-scanning might work where one more bullet
point could not. This round built and measured that call.

### `AmbiguityScanAgent` — post-build, additive-only, fails to "empty"

`src/agents/ambiguity_scan_agent.py` — runs AFTER System B completes,
given the original NL plus the committed reading (source table + the
compiled KQL), and returns `List[Ambiguity]` (usually empty). Three
deliberate design properties:

- **It has no stake in the pipeline** — it never built anything, so
  "a different analyst could defensibly have read this differently" is
  a review question, not self-criticism of work it just committed to.
- **Additive-only**: it can only ADD closed-option questions for the
  clarification UI; it never edits the pipeline, never blocks a
  result, and every failure mode (parse error, LLM error, unrenderable
  IR) degrades to `[]` — exactly the pre-scanner behavior.
- **Precision-first prompt**: the structural-fork definition (event
  type / aggregation function / filter target — the same three §4AG
  used), four explicit NOT-an-ambiguity classes (missing info is a
  caveat not a fork; convention-covered choices; readings the text
  rules out; stylistic no-ops), an explicit "empty is a successful
  scan" calibration line, and both §4AG worked examples plus two
  worked NON-examples.

`scan_ambiguities(nl, ir, scanner)` in `gap_checker.py` merges the
scanner's findings with any self-reported `ir.ambiguities` (kept — a
free signal if the model ever does self-report), deduped on normalized
description text, self-report winning duplicates. This is the
"structural detection pass" slot `find_ambiguities`' docstring
reserved in §4AG.

### Live measurement — same protocol as the §4AG baseline, for comparability

Same two documented ambiguous NLs (recycle-bin event-type fork, DGA
count-vs-dcount fork), 3 scan trials each, plus a false-positive check
(3 clearly single-reading NLs × 2 trials):

| | self-report (§4AG) | dedicated scan (this round) |
|---|---|---|
| Fork detection (2 ambiguous NLs, 3 trials each) | **0/6** | **6/6** |
| False positives (3 single-reading NLs, 2 trials each) | n/a | **0/6** |
| `picked_option` correctly matches the committed reading | n/a | 6/6 |
| resolve_ambiguity round-trip on a scanner-found fork | n/a | ✅ FileEvent → ProcessEvent, valid compiled KQL |

**It took one honest iteration to get there, and the miss was
instructive**: the first prompt version scored 3/6 — the event-type
fork 3/3, the aggregation fork 0/3. Tracing the DGA miss: the built
pipeline had committed to `dcount(DnsQuery)` (the smarter, DGA-
specific reading) while the description's own words say "NXDomain
response *count*" (the literal raw-volume reading) — and the scanner
was silently accepting the smarter reading as settled, exactly the
disclosure failure the scan exists to catch. Fixed with one targeted
instruction ("the committed reading being arguably better resolves the
fork in the analyst's head, not in the text — report it", explicitly
covering aggregations living inside `make-series`, not just
`summarize`). Re-measured: 6/6, negatives still 0/6.

**Honest scope**: this measurement is against this project's own two
documented forks and three of its own demo NLs — the right baseline
for comparability with §4AG's 0/6, but not yet a fresh-data precision/
recall number (no labeled ambiguity corpus exists to run one against;
the §4AG real-data set's 55 questions are missing-info gaps, a
different class). The mechanism is confirmed; its fresh-data hit rate
is not yet measured.

### Wiring, tests, and a small resolver fix

- **Streamlit demo** (`app.py`): scan runs once at generation time
  (not in the form section, which reruns per widget interaction);
  each fork renders as a closed-option radio in the same clarification
  form, committed reading preselected (submitting unchanged = explicit
  confirmation, no rebuild). A changed choice routes through
  `resolve_ambiguity` first, then any gap answers through
  `resolve_clarification` on the resulting IR. ON by default
  (`USE_AMBIGUITY_SCAN=0` to disable) — unlike RAG (off after
  measuring a wash, §4AE), this measured a clean win.
- **Tests**: 3 new unit tests on the merge/dedupe (`test_ambiguity.py`,
  now 7), and 2 new live anchors in `test_clarification_loop.py` —
  the recycle-bin fork must be found AND resolving to the other option
  must actually switch tables, and the fully-specified password-spray
  NL must scan clean (the precision guard). Both pass live.
- **Resolver fix found in review**: `_rebuild_with_instruction`
  hardcoded `attempts_used=1` even when its bounded retry used 2 —
  now reports the real count.
- A live-verification pitfall worth recording: a scratchpad script
  calling bare `load_dotenv()` silently found no `.env` (dotenv
  searches from the SCRIPT's directory), fell back to
  `LLM_PROVIDER=ollama`/qwen3.5:4b, and every pipeline build failed
  with degenerate 4B-model output — initially indistinguishable from
  a real regression. Any out-of-repo runner must pass the .env path
  explicitly.

None of the three regression-gated files were touched this round.

---

## 5. What you have to do (irreducibly human) — narrowed, not eliminated

**Rewritten in §4AC** — this section had not been touched since roughly
§4K/§4L and was citing numbers (9/15=60% through 15/20=75%, seven
scorings) and open items (percentile-of-aggregates, join support) that
were resolved over a dozen rounds ago. The items below reflect actual
current state as of §4AC. See §6/§7 immediately following for the
parallel rewrite of the working-state table and future-plans list —
all three sections had gone stale together and are fixed together.

1. **Rotate the Azure AI Foundry API key** — pasted into a chat session
   during setup on 2026-06-22, must be treated as compromised regardless
   of whether it's been misused. Still not done as of §4AC; this is the
   single oldest open item in this entire document and is purely
   operational (requires Azure portal access no agent session has).
2. **Logic Correctness needs independent verification before any number
   is cited externally — still the top *analytical* open item, now
   addressed for the first time with an actual second rater (§4AC),
   not just the `VerifierAgent` proxy (§4T, 0.65 raw agreement / 0.86
   recall).** A second, independent reading (no visibility into the
   first rater's scores or reasoning) was done on the 18-case RAG A/B
   set (§4AB) — see §4AC for the full Cohen's κ result and what it
   does/doesn't establish. This is real progress but still N=1
   independent-rater dataset (18 cases, one comparison context); the
   original ask (a dedicated 20-case overlap across the broader tuned
   set) is still open if a *second* independent check is wanted before
   any headline number is published externally.
3. **Spot-check the AI-assisted manual verification** (`manual_verdicts.json`,
   81 keeps / 114 discards) and **the 15 paraphrases**
   (`paraphrases_test.json`) — unchanged from the original ask, still
   not done. Lower urgency than items 1-2 but still nobody's checked it.
4. **Human review of the AI-assisted Logic Correctness scoring
   methodology itself** — every number in this document (tuned-set
   87.2%, held-out median 82.4%, and now the RAG A/B's base/RAG split)
   was scored by Claude under the same 3-point rubric, never by a human.
   Item 2's second-rater check is AI-vs-AI agreement, not AI-vs-human —
   stated plainly so it isn't mistaken for the human check that's still
   actually outstanding.

All items from the original numbered list (model capability, paraphrase
normalization, percentile-of-aggregates, join/multi-stage-aggregation,
the `61988db3` FilterGroup confusion, the No-Schema-Grounding ablation
leak, the repair-loop off-by-one, scaling past 45 records, and
`RESULTS_DRAFT.md` reconciliation) were resolved between §4E and §4AA —
see the chronological log for each. None remain open; they are not
repeated here to avoid this section going stale in the same way again.

---

## 6. What's confirmed working vs. not, right now

**Rewritten in §4AC** — this table had not been updated since §4K
(over 15 rounds ago) and was describing 84.4% completion / 64.7% Logic
Correctness with no RAG, no construct coverage beyond the original
7-stage AST, and the sdelete case as completely untraced. None of that
is current. This is the actual state as of §4AC.

| | Status |
|---|---|
| `KqlPipeline` AST schema | ✅ Now 11 stage types (`Where`/`Summarize`/`Extend`/`Join`/`Union`/`Project`/`Top`/`MvExpand`/`MakeSeries`/`SeriesAnomaly`/`Parse`), `AndGroup`, `ArgMaxMin`, `Filter.field_ref` (§4AA), the full 9-member `JoinKind`, `caveats`, and the `EQ_CI`/`NEQ_CI`/`_cs` operator family (§4AB) — see `architecture_v2_ast.md`'s schema section, resynced §4AB |
| Schema Validator | ✅ 15+ hard-error checks, exhaustively inventoried by `tests/unit/test_validator_inventory.py` so a check silently vanishing (the original §4K failure mode) fails CI immediately. Newest: `LITERAL_MATCHES_SCHEMA_FIELD` (§4AB) — generalizes the `field_ref` fix into a standing guard against the model reverting to the old broken literal-as-column-name pattern |
| Repair loop / compiler / interpreter | ✅ Stable; `src/execution/ir_interpreter.py` (§4Y) provides execution-validated should-fire/should-not-fire checking independent of manual KQL reading |
| Construct coverage | ✅ 72.7% of constructs at ≥5 real-corpus occurrences are Supported/Partial (§4AB headline), up from 59.4% at first measurement (§4X) — `CONSTRUCT_COVERAGE.md` is the living scorecard |
| Clarification + disambiguation | ✅ Missing-info gaps: `find_gaps`/`resolve_clarification` (§4AF), live-verified. Ambiguous-reading forks: dedicated `AmbiguityScanAgent` post-build scan (§4AH) — 6/6 detection on the documented fork cases vs. the 0/6 self-report baseline, 0/6 false positives, resolution round-trip live-verified. Fresh-data precision/recall not yet measured (no labeled ambiguity corpus) |
| RAG retrieval | ✅ Built (§4AB): 3 routed local TF-IDF indexes (KQL operator docs, ASIM schema, train-split worked examples), wired behind `USE_RAG_RETRIEVAL`, off by default. **Logic Correctness effect: NOT established either way** (§4AC) — two independent raters disagree on aggregate direction at n=18 despite substantial item-level agreement (quadratic-weighted κ=0.70). One robust, attributable regression found and named (retrieved-schema field anchoring, `dedb8fb9`); two robust wins traced to a RAG-independent IR Builder bug, now fixed regardless of RAG |
| Logic Correctness scoring | ⚠️ Tuned-set peak 87.2% (N=1, §4S); held-out median 82.4%, IQR 5.9 (N=5 replicated, §4V) — both still single-AI-rater. **First independent second-rater check now done** (§4AC, RAG A/B set, 18 cases): quadratic-weighted κ=0.70 (substantial item-level agreement), but the two raters disagreed on which of two conditions scored higher in aggregate — the headline finding is that a single-rater directional claim at this sample size is not yet safe to publish, not a pass/fail on the rubric itself |
| The `5b6ae038` sdelete renamed-binary-evasion case | ⚠️ → 🔍 No longer "untraced" (§4AC): the `.exe`-suffix-truncation mechanism is found and fixed (10/10 clean after); a SEPARATE mechanism remains (the IR Builder ignoring the Extraction Agent's own correctly-extracted flags 1/5 times, inventing `-p`) and is now understood to be a raw model-reliability residual the prompt already explicitly warns against — not a prompting gap, the first time this distinction has been confirmed rather than assumed for this case |
| Construct-substitution / fixture-coupling discipline | ✅ Institutionalized, not just fixed reactively (§4AB) — audited every hand-written fixture in `test_live_e2e_execution_validation.py` and `fixture_generator.py`, found and fixed 2 crash bugs and a 3-layer compounding bug that had been silently misreporting `has_all_evasion`'s real accuracy as 40% instead of 93% |
| Documentation sync | ✅ → ⚠️ `architecture_v2_ast.md`'s schema section resynced §4AB; this file's own §5/§6/§7 (this section) resynced §4AC after going stale since ~§4K — the exact failure mode §4K itself warns about (spec drifting from shipped code), now caught and fixed in this document about itself. `MASTER_PLAN_v2_ast.md` and `RESULTS_DRAFT.md` remain only partially reconciled — see §7 |
| Azure AI Foundry key rotation | ❌ Still not done — flagged compromised since 2026-06-22, repeated in every round's human-items list since, still operational/out-of-band for any agent session |

---

## 7. Future plans

**Rewritten in §4AC, re-ordered in §4AD** — the previous version of
this section was framed entirely around "closing the gap back to the
pre-migration peak (95.6%/75%)," a goal that is now stale and slightly
wrong: the system is past that peak on capability (construct coverage,
RAG groundwork, execution-validated testing, an independently-checked
Logic Correctness process). What's actually left, in priority order:

0. **Decide what an abstaining pipeline should actually do** (§4AD —
   newly found, ranked above everything below it). A `KqlPipeline`
   with zero `WhereStage`s fires on every row of the source table when
   deployed — confirmed reproducible (~1/3 of trials on the hardest
   such case), not a one-off. This is a real design decision (refuse
   to emit a rule at all below some grounding threshold? emit a
   structurally-disabled placeholder? keep current behavior with a
   much louder warning?), not a bug fix, and it affects how several
   already-scored "honest abstention = correct" Logic Correctness
   cases should be weighted going forward.
1. **Decide RAG's fate with more data, not more building.** §4AC's
   n=18 A/B is the honest current state: not validated, not ruled out.
   The next move is a LARGER frozen slice (the original ask was 20-30
   fresh real rules) run through the SAME independently-double-rated
   process, not another round of indexing or prompt tuning on the RAG
   side — the retrieval mechanism itself is not the open question
   anymore, the sample size is.
2. **Fix the one robust, attributable RAG regression** (`dedb8fb9` —
   retrieved-schema fields anchoring the model away from logic already
   correct in the baseline path) — a named, falsifiable mechanism, not
   a vague "RAG sometimes hurts." Test suppressing the most schema-
   prominent fields from a retrieved chunk when the NL already supplies
   a more specific filter.
3. **A real human Logic Correctness check remains the single highest-
   priority item this document has carried since §4B.** §4AC's
   independent second rater is AI-vs-AI agreement, not AI-vs-human —
   stated plainly so it is never mistaken for the human check. A
   KQL-literate human scoring even a 15-20 case overlap against the
   existing rubric would be the first genuine validation of the rubric
   itself, not just of one rater's consistency.
4. **Reconcile `MASTER_PLAN_v2_ast.md` and `RESULTS_DRAFT.md`** — both
   remain stale relative to the shipped code in ways `architecture_v2_ast.md`'s
   schema section no longer is (§4AB). `RESULTS_DRAFT.md` specifically
   needs its headline numbers, RAG section, and Logic Correctness
   methodology notes brought current; this is mechanical reconciliation
   work, not analysis, and should not require new live testing.
5. **Generalize beyond the single property-on-wrong-entity fix**
   (`SrcIpAddr`-vs-`Url`, §4AB) — confirm whether "a property belongs to
   the entity it's actually a property of, not the grammatical subject"
   holds across other entity/property pairs (ports on connections vs.
   users, hashes on files vs. processes) the way the `field_ref` fix
   turned out to generalize across constructs, or whether each instance
   needs its own worked example.
6. Rotate the exposed Azure key — unchanged, still purely operational,
   still not done.
7. Human spot-check of the AI-assisted dataset verification and
   paraphrasing (`manual_verdicts.json`, `paraphrases_test.json`) —
   unchanged from the original ask, still not done.

**Ruled out, not pending:** NL-phrasing normalization (§4C) — investigated
and found to be a missing-information problem, not a style problem; a
normalization step cannot fix it.
