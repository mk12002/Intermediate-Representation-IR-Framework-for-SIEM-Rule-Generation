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

## 5. What you have to do (irreducibly human) — narrowed, not eliminated

Phases 1–5 below were all run end-to-end this session, AI-assisted
throughout. What remains is verification of that work, plus the decisions
only a human can actually make:

1. **Spot-check the AI-assisted manual verification** — read a sample of
   the 81 keeps and 114 discards in `manual_verdicts.json` and confirm the
   judgment calls hold up. This is now a *check*, not a from-scratch review.
2. **Spot-check the 15 paraphrases** in `paraphrases_test.json`.
3. **Rotate the Azure AI Foundry API key** used for the gpt-4.1-mini run —
   it was pasted into a chat session during setup on 2026-06-22 and must be
   treated as compromised regardless of whether it's been misused. `.env` is
   gitignored and not committed, but the key still needs replacing in Azure
   AI Foundry and in `.env` locally.
4. **The model-capability question from the old §5 item 3 is now resolved**:
   yes, model capability was real (Qwen3.5 MVP re-test: 1/10 vs
   gpt-4.1-mini's 8/10, same fix, same cases) — but it was entangled with a
   much larger bug (§1.4 item 14) that had been silently defeating schema
   grounding for the entire study. Both are now documented; no further
   model-selection decision is pending.
5. **Logic Correctness needs a second reviewer before any number is cited
   externally — still the top open item, unchanged across seven rounds.**
   Scored seven times now: 9/15 = 60% (§4B/§4C,
   `data/processed/logic_scoring_data_v2.json`), 10/19 ≈ 52.6% (§4E),
   12/20 = 60% (§4F), 14/20 = 70% (§4G), 15/20 = 75% (§4H), 15/20 = 75%
   again (§4I), and 15/20 = 75% a third time (§4J, different composition
   each time) — all by the same single AI rater. The trend has a clear
   causal story (named, fixed bugs each round) but with one rater there is
   still no independent verification that the rubric itself is applied
   consistently. Three consecutive rounds landing on 75% via different
   underlying failures is itself a signal worth a second opinion on: is
   this dataset/rater/architecture combination converging on a real
   ceiling, or is it coincidence?
6. ~~Test the paraphrase-normalization hypothesis~~ — **investigated and
   ruled out (§4C)**. The `sop`/`original` gap is missing information, not
   phrasing style; a normalization step cannot recover information that was
   never in the input. Not pursuing this further.
7. **Build a second aggregation pass for percentile-of-aggregates and
   derived/computed fields** — narrower than originally scoped: §4H added
   a real, working `percentile()` aggregation (Nth percentile of a field
   *within* a group), and §4I added `additional_aggregations`/`make_set`/
   `make_list` (multiple summarize columns together), but the one
   confirmed live need (`4e3af8e3`) is percentile computed *across*
   groups' own aggregate results, used as a scalar threshold — a second
   aggregation pass the IR has no construct for, compounded by
   `extend`-style derived fields the IR also can't express. Still not
   started; still the largest confirmed architectural gap.
8. ~~Build join/multi-stage-aggregation support~~ — **baseline-vs-current is
   done (§4E)**, and join usage roughly doubled in §4F (2/20→4/20
   out-of-scope successes use a real join) after the prompt fixes. Exclusion-
   lookup (`leftanti`) and enrichment (`leftouter`) joins are still
   unconfirmed live, only on synthetic unit-test IRs.
9. **Account for gpt-4.1-mini's run-to-run non-determinism in any future
   eval** (§4C/§4E–§4J) — completion has ranged 84.4–95.6% across
   §4H–§4J's six runs combined, with two swings traced to real bugs (the
   `has_all` confusion §4H; the repair-loop off-by-one §4I) rather than
   pure model noise — worth remembering that not every run-to-run swing is
   irreducible non-determinism; some are bugs that look like noise until
   traced. §4J reached the highest completion/FVR/RRR of the entire study
   (95.6%/93.3%/91.7%) on one run — not yet confirmed by a repeat.
10. ~~Fix the remaining named Logic Correctness gaps~~ — **§4G's two gaps
    fixed in §4H** (`b35f6633-casual`'s DNS filter, `43c2832e-sop`'s
    Src/Dst mix-up), confirmed still holding through §4J. **The §4H/§4I
    residual `61988db3` FilterGroup/OR confusion traced and fixed in
    §4J** — the actual mechanism was a specific sentence shape, "(X1, X2,
    ..., or Xn) is/does Y," where the model was extending the enumerated
    list's "or" scope to swallow the unrelated AND-condition after it.
    Confirmed via 6/6 clean standalone re-runs and live: `61988db3-casual`
    now passes cleanly. `61988db3-sop` still fails, but for a new, smaller
    reason (a truncated LOLBin enumeration, 2/7 names) — not yet itself
    investigated, and only seen once so far.
11. **Decide whether to genericize the worked examples accumulating
    real field names in static prompt text** (§4H, §4I) — the
    No-Schema-Grounding ablation's leak has grown twice now (0%→6.7%→13.3%)
    as a second worked example (evidence-collection,
    `additional_aggregations`) added its own literal field names on top
    of §4H's DNS example. Currently left as-is each time since the
    real-system fix each example enabled outweighs the ablation-purity
    cost, but flagging this trend for a second opinion before a third
    worked example is added, and before any of these ablation numbers are
    cited externally as a clean isolation.
12. **Found and fixed a real repair-loop bug while investigating a
    completion-rate dip (§4I)**: `run_with_repair`'s `range(max_attempts)`
    loop bound meant the *last* rebuild on any repair sequence was never
    itself validated before giving up — confirmed live, a fully valid IR
    was discarded as `MAX_REPAIR_ATTEMPTS_EXCEEDED`. Fixed to
    `range(max_attempts + 1)`; all existing call-count-asserting tests
    still pass unchanged, plus one new regression test. A second-order
    fix followed: `eval/run_ablations.py`'s No-Repair ablation had been
    relying on the *old, buggy* semantics of `max_attempts=1` to
    approximate zero-repair; changed to `max_attempts=0`, which the fixed
    loop now correctly treats as "exactly one build, never rebuilt."
13. **Scale up**: this run covered only the 15-pair test split (45 records
    with paraphrases). The 66-pair train split was never run through
    `eval/run_comparison.py` — MASTER_PLAN's full Phase 4 is the held-out
    *test* split only, so this isn't strictly required, but a larger test
    set (the original 100–150 pair target was never reached after
    verification cut 195→81) would tighten the wide CIs seen throughout
    §4B/§4C/§4E–§4I.
14. Rotate the exposed Azure key (item 3, repeated here since it's the only
    item that's purely operational, not analytical) before sharing any of
    this work externally.
15. ~~Rewrite `RESULTS_DRAFT.md` to match the current numbers~~ — **done,
    fully reconciled through §4I** (number-by-number and section-by-section
    pass, not just the headline). Still needs one more pass for §4J's
    numbers (95.6%/93.3%/91.7%, the residual-bug trace and fix).

---

## 6. What's confirmed working vs. not, right now

| | Status |
|---|---|
| `generate_kql()` / template compiler | ✅ Verified against worked example |
| Schema Validator (`validate_ir`) | ✅ Working, all rules implemented |
| KQL Syntax Validator | ✅ Working after comment/string-literal/verbatim-string fixes |
| FVR/SVR metrics (`eval/metrics.py`) | ✅ Working — including the table-hallucination fix found via manual scoring |
| Extraction Agent (live model call) | ✅ Runs, valid structured output (after schema-echo fix) |
| IR Builder Agent (live model call) | ✅ Runs without crashing or echoing the schema; gpt-4.1-mini reaches **95.6% completion in §4J, highest of the study**; Qwen3.5 4B/2B reaches only 1/10 on the round-1 fix |
| Schema-grounding field list | ⚠️ → ✅ Was silently empty almost always (§1.4 item 14) — fixed 2026-06-23; this was the dominant cause of the original §4 result, more than model choice |
| Degenerate-threshold check | ⚠️ → ✅ `count`/`distinct_count` thresholds like `> 0`/`>= 1` passed validation while filtering nothing (§1.4 item 16) — fixed 2026-06-23 |
| `output_fields` validation | ⚠️ → ✅ Never checked against the schema (item 18), then didn't recognize an aggregation's own alias as legitimate (item 26, §4E) — both fixed |
| OR-composition (`FilterGroup`) | ✅ New construct, §4C — confirmed working live every round since |
| Baseline-vs-current joins (`JoinStage` + `compare_to_join_field`) | ✅ New construct, §4E — confirmed live and semantically correct (`8717e498`: `CurrentCount > BaselineAvg + 50`); usage roughly doubled in §4F (2/20→4/20) after prompt fixes. Exclusion/enrichment join kinds still unconfirmed live |
| `kql_literal` string escaping | ⚠️ → ✅ Zero escaping before §4C — backslash in a filter value broke KQL string syntax — fixed |
| `avg`/`sum`/`min`/`max`/`dcount` with no field | ⚠️ → ✅ Passed validation, rendered invalid KQL like `avg()` (§4E item 29) — fixed, only `count()` may omit a field now |
| `percentile` aggregation function | ✅ New construct, §4H — `AggregationFunction.PERCENTILE` + `Aggregation.percentile`. Confirmed live-reached-for; insufficient alone for percentile-of-aggregates patterns (see IR expressiveness ceiling row) |
| `additional_aggregations` (`make_set`/`make_list` + multi-column summarize) | ✅ New construct, §4I — most real ASIM rules compute several summarize columns together (count + evidence + timestamps), which the IR could not express before this. Confirmed live, generalizing far beyond its one worked-example target case to 4 other ground-truth pairs unprompted, still holding in §4J |
| Constraint traceability (extracted threshold language vs. final IR) | ✅ New check, §4F — catches schema-valid-but-drifted threshold values; deliberately conservative (single unambiguous number only), real-world hit rate still not separately measured |
| Few-shot example + event-type disambiguation | ✅ New prompt content, §4F — 2 of 3 specifically-targeted wrong-event-type confusions measurably resolved |
| Disguised/renamed-tool evasion worked example | ✅ New prompt content, §4G — the sdelete inverted-logic bug (present since §4B) is now **fully resolved, 3/3 paraphrases correct**, confirmed stable since |
| Src/Dst directional guidance + DNS outcome-field guidance | ✅ New prompt content, §4H — fixed both named §4G gaps: `43c2832e-sop`'s actual bug (Src/Dst mix-up, not over-grouping) and `b35f6633-casual`'s missing DNS error filter; both confirmed still holding through §4J |
| FilterGroup-vs-AND clarification | ✅ Fixed a self-inflicted bug, §4H (the `has_all` confusion) — recurred in a new variant in §4I (`61988db3`), **traced to its actual mechanism and fixed in §4J**: a sentence shape, "(X1, ..., or Xn) is/does Y," where the model extended the list's "or" scope onto an unrelated AND-condition. Confirmed via 6/6 clean standalone re-runs |
| Repair loop | ✅ Mechanically correct *and*, since §4I, actually validates every build it makes — found and fixed an off-by-one where the final rebuild on any repair sequence was silently discarded unchecked, even when valid. RRR climbed 82.6%→91.7% across §4I→§4J |
| System A baseline | ✅ Ran end-to-end on all 45 test records (Qwen3.5 run + multiple gpt-4.1-mini re-runs, most recently §4J) |
| `eval/run_comparison.py` | ✅ Ran clean — re-run 15 times total for gpt-4.1-mini at `eval/results/primary/comparison_raw.jsonl`; fixed a relative-import bug (item 28) that broke direct-script invocation |
| `eval/run_ablations.py` | ✅ The No-Repair ablation's `max_attempts=1` call was silently relying on the now-fixed repair-loop bug to approximate zero-repair semantics — corrected to `max_attempts=0` (§4I); stable at 46.7–48.9% since. Monolithic stable in the low-to-mid 60s. **No Schema Grounding sits at 11.1–13.3%** since the §4I worked-example leak (unchanged this round — §4J's fix was prompt-text-only, no new field names) (§5 item 11) |
| Dataset (81 verified pairs) | ✅ AI-assisted manual review complete, all 4 rubric items applied |
| Complexity tagging | ✅ Fixed and re-validated (58/21/21) |
| Train/test split | ✅ Generated and committed (66/15) |
| Paraphrasing | ✅ Done for test split (15×2 styles); ❌ not done for train split |
| Full evaluation / ablations | ✅ Complete for gpt-4.1-mini, current state — see §4J for the current numbers; §4/§4B/§4C/§4E–§4I superseded |
| Logic Correctness scoring | ⚠️ Scored seven times (60%, 52.6%, 60%, 70%, 75%, 75%, 75%) — three consecutive rounds at 75% via different underlying compositions; still one rater, no second reviewer (§5 item 5, top open item) |
| IR expressiveness ceiling | ⚠️ OR-composition (§4C), baseline-vs-current joins (§4E/§4F), per-group percentile (§4H), and multi-column aggregation (§4I) fixed; percentile-of-aggregates + derived/computed fields still unsupported (§5 item 7); exclusion/enrichment joins unconfirmed live |
| Statistical analysis | ✅ Bootstrap CI + McNemar computed for SVR/FVR, all runs — SVR McNemar no longer significant from §4F onward (System B's completion is statistically indistinguishable from System A's) |
| Write-up draft | ✅ `RESULTS_DRAFT.md` fully reconciled through §4I, section-by-section — still needs a final pass for §4J's numbers (95.6%/93.3%/91.7%) and the residual-bug trace |

---

## 7. Future plans

**Everything in MASTER_PLAN's Phases 1–5 ran this session, ten times** —
contaminated by the schema-grounding bug (§4, Qwen3.5); after fixing it
(§4B round 1); after the degenerate-threshold fix and prompt guidance (§4B
round 2); after the `FilterGroup`/`output_fields`/escaping fixes (§4C);
after the `JoinStage`/`compare_to_join_field` architecture fix (§4E); after
the few-shot/disambiguation/constraint-traceability prompt fixes (§4F);
after the disguised-tool-evasion and anti-over-grouping worked examples
(§4G); after the Src/Dst, DNS-outcome, percentile, and `has_all`-bug fixes
(§4H); after `additional_aggregations`/`make_set`/`make_list` and the
repair-loop off-by-one fix (§4I); after tracing and fixing the residual
`61988db3` sentence-shape confusion (§4J, current — completion 95.6%,
FVR 93.3%, RRR 91.7%, all study highs; Logic Correctness 75%). What's
left:

1. **Get a second reviewer on the 75% Logic Correctness figure**
   (§5 item 5) — the single highest-priority remaining item, now reached
   on three consecutive rounds (75%, 75%, 75%) via three different
   underlying case compositions; everything else this session built
   toward this number being measured honestly, but it's still one AI
   rater's judgment.
2. **Build the percentile-of-aggregates + derived-field construct**
   (§5 item 7) — the largest remaining confirmed architectural gap,
   untouched since §4H, confirmed by live evidence on `4e3af8e3`.
3. **Decide on the worked-examples-vs-ablation-purity tradeoff**
   (§5 item 11) — kept as-is twice now (§4H, §4I), flagged for a second
   opinion before a third worked example compounds it further.
4. **Investigate the new `61988db3-sop` LOLBin-list-truncation issue**
   (§4J) — first observed this round, after the original FilterGroup/OR
   confusion was fixed; only one occurrence so far, not yet enough to
   tell if it's a real pattern or non-determinism on a 7-item enumeration.
5. Rotate the exposed Azure key (§5 items 3/14) — operational, not
   analytical, but should happen before this work is shared anywhere.
6. Re-run the full comparison 1-2 more times and average, given the
   measured run-to-run non-determinism (§5 item 9) — §4J's 95.6% is one
   run, the highest of the study, not yet confirmed by a repeat.
7. Human spot-check of the AI-assisted verification and paraphrasing
   (§5 items 1-2).
8. Measure the constraint-traceability check's real hit rate directly
   (false positives vs. true catches) — built and live-tested in §4F,
   but its actual reliability across the full dataset hasn't been
   separately quantified.
9. Fold §4J's delta (the sentence-shape fix and the new study-high
   numbers) into `RESULTS_DRAFT.md`'s own narrative — the document was
   fully reconciled through §4I this round, but §4J happened after.

**Ruled out, not pending:** NL-phrasing normalization (§4C) — investigated
and found to be a missing-information problem, not a style problem; a
normalization step cannot fix it.
