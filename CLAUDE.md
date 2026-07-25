# Project rules for Claude Code sessions

Full project history and architecture: `docs/NL-KQL/PROJECT_STATUS.md`
(read this for context before making non-trivial changes — it has
~30 rounds of prior findings, including bug classes that have been
fixed and re-broken before).

## Mandatory regression gate

After ANY edit to `src/agents/extraction_agent.py`,
`src/agents/ir_builder_agent.py`, or `src/execution/ir_interpreter.py`,
run:

```
pytest -m regression_gate
```

before considering the edit complete. This runs the permanent
should-pass anchors in `tests/integration/test_live_e2e_execution_validation.py`
— real LLM calls, one anchor per historically-fixed bug class. §4T
found a previously-fixed bug (c6608467) regress silently on the exact
prompt that had already fixed it; this gate exists because prompt
churn makes that more likely over time, not less, without something
automated checking for it.

When a new bug class is found and fixed in one of those three files,
add a new permanent anchor to that test file (marked
`@pytest.mark.regression_gate`) rather than only fixing the immediate
case — the gate is only as good as its coverage of this project's
actual fix history.

## Clarification loop (§4AF) + disambiguation scan (§4AH)

`src/clarification/` — when a pipeline has `caveats` (omitted
filters) or `abstained=True`, `find_gaps(ir)` turns each caveat into
an askable `Gap` (question + real-data default where one exists), and
`resolve_clarification(...)` merges a user's answers back into the IR
by reusing the existing repair-loop rebuild path. Wired into `app.py`'s
Streamlit demo as a question form. Live-verified:
`tests/integration/test_clarification_loop.py`.

The AMBIGUOUS-reading half (present information supporting multiple
structurally different readings) is handled by a DEDICATED post-build
scan call, `src/agents/ambiguity_scan_agent.py` +
`scan_ambiguities(nl, ir, scanner)` — NOT by the IR Builder
self-reporting `ir.ambiguities` in its own build call. That
self-report path was measured at 0/6 auto-trigger even on its own
worked examples across two rounds of prompt strengthening (§4AG); the
dedicated scan measured 6/6 on the same protocol with 0/6 false
positives (§4AH). Do not move ambiguity detection back into the IR
Builder's prompt — the failure mode is structural (a call optimized
for decisive construction cannot also monitor itself for forks), not
a wording problem. The scanner is additive-only: every failure mode
degrades to "no ambiguities found", and it never edits or blocks a
result. Closed choices resolve via `resolve_ambiguity(...)` (same
rebuild path as clarification). Demo: ON by default, disable with
`USE_AMBIGUITY_SCAN=0`.

## Abstaining pipelines must never fire on anything (§4AE)

`KqlPipeline.abstained: bool` (default `False`) — set this to `True`
when NO concrete detection logic can be grounded for a description at
all (the IR Builder's job; see `_COMMON_MISTAKES` in
`ir_builder_agent.py`). This is load-bearing, not cosmetic:

- An empty `stages` list with `abstained=False` is a **hard validator
  error** (`EMPTY_PIPELINE_NOT_MARKED_ABSTAINED`) — never construct one
  without the flag. The reason: a pipeline with no `WhereStage` fires
  on EVERY row of `source_table` when actually deployed. That is not a
  safe no-op, it is an alert storm worse than shipping no rule at all.
- `generate_kql()` refuses to emit a runnable query when
  `abstained=True` — it renders only the caveat explaining why.
- `pipeline_fires()` always returns `False` for an abstained pipeline,
  regardless of what (if anything) ended up in `stages`.
- Permanent regression anchor:
  `test_total_abstention_never_fires_on_anything` in
  `test_live_e2e_execution_validation.py` — checks this property holds
  live, not just in unit tests.

If you touch abstention-adjacent logic in any of the three files in
the mandatory gate above, re-run the gate — this property was found
broken in production-shaped output (confirmed reproducible ~1/3 rate
on the hardest case) before being fixed, and is exactly the kind of
thing that regresses silently under prompt churn.

## Logic Correctness: report as a distribution, not a binary cutoff (§4AE)

Cohen's κ between two independent raters on the held-out set measured
0.645 (quadratic-weighted, ordinal 0-3 scores) but only 0.265 when the
same scores are collapsed to a binary pass/fail (this project's
historical convention through §4AC). The raters substantially agree
on relative quality; they diverge on where the pass/fail LINE falls.
**Report Logic Correctness as a score distribution (X% scoring 3/3, Y%
scoring 2/3, ...) going forward, not a single "N% passed" percentage**
— the distribution inherits the reliable κ=0.645 measurement, the
single cutoff inherits the unreliable κ=0.265 one. See
`PROJECT_STATUS.md` §4AE for the actual numbers and
`eval/score_logic_correctness.py` for the (still unrun) human-rater
check that would add a third, independent κ.

## RAG retrieval (§4AB, simplified §4AD, decision finalized §4AE)

Two local TF-IDF indexes ground the IR Builder's prompt in ASIM schema
field definitions and worked NL→KQL examples. A third index (KQL
construct syntax, 669 `dataexplorer-docs` operator pages) was built in
§4AB and DROPPED in §4AD — its retrieval quality was "honestly mixed"
(lexical TF-IDF has no real semantic understanding) and the full A/B
found no measurable benefit to credit against the added complexity.
See `src/retrieval/build_indexes.py`'s module docstring to re-add it
for a semantic-embeddings experiment.

**Indexes are pre-built and committed** (`data/rag_indexes/*.pkl`).
You do NOT need to rebuild them unless the train-split pairs change
or you want to pick up new upstream doc content.

**To enable RAG at runtime**, set in `.env`:

```
USE_RAG_RETRIEVAL=1
```

The IR Builder reads this at construction time. Off by default — the
existing, already-measured baseline path is unchanged when not set.

**To rebuild indexes from scratch** (requires the source corpus):

1. Clone the ASIM schema doc corpus into `.rag_corpora/` (gitignored):
   see the full commands in `src/retrieval/build_indexes.py`'s module
   docstring.
2. Run the build script (no LLM calls, pure offline TF-IDF):
   ```
   PYTHONPATH=. python src/retrieval/build_indexes.py
   ```

**What the two indexes contain:**
- `asim_schema.pkl` — 14 ASIM normalization schema pages from
  `MicrosoftDocs/defender-docs` (branch: `public` — Sentinel docs
  moved here from `azure-docs`), queried by event type for field
  definitions beyond the bare name list in `asim_field_reference.json`.
  Measured 3/3 correct retrieval after the camelCase-query fix (§4AB).
- `worked_examples.pkl` — 66 train-split verified NL→KQL pairs from
  `data/processed/pairs_verified.jsonl`, queried by description
  similarity. **Never** includes the test split or held-out set.

**Key source files:**
- `src/retrieval/retriever.py` — `TfidfRetriever` class (build/save/load/query)
- `src/retrieval/build_indexes.py` — offline index build script + corpus setup instructions
- `src/agents/ir_builder_agent.py` — `_retrieved_context()`, `IRBuilderAgent(use_rag=...)`

**A/B result (§4AC) and final decision (§4AE):** n=18 frozen held-out
set, SVR and FVR identical (94.4% / 94.1%) for both conditions. Logic
Correctness scored by two independent raters: quadratic-weighted
κ=0.70 (substantial item-level agreement) but the raters disagreed on
which condition won in aggregate (rater1: RAG ahead 45-39; rater2:
base ahead 48-45). **Decision, not left open**: the pre-committed
threshold was that RAG-on-by-default needed to move Logic Correctness
by more than this project's own measured binary-cutoff noise band
(κ=0.265) — the measured effect is smaller than that band in both
directions, which is a conclusion (RAG's effect here is provably
smaller than the metric's own noise), not an inconclusive result. RAG
stays off by default; only re-open this if testing semantic embeddings
instead of TF-IDF, not by re-running the same measurement. Full
detail: `PROJECT_STATUS.md` §4AC–§4AE.
