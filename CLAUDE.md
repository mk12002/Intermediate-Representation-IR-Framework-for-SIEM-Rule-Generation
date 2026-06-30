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

## RAG retrieval (§4AB, simplified §4AD)

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

**A/B result (§4AC):** n=18 frozen held-out set, SVR and FVR identical
(94.4% / 94.1%) for both conditions. Logic Correctness scored by two
independent raters: quadratic-weighted κ=0.70 (substantial item-level
agreement) but the raters disagreed on which condition won in
aggregate (rater1: RAG ahead 45-39; rater2: base ahead 48-45) — RAG's
Logic Correctness effect is not established either way at this sample
size. Full detail: `PROJECT_STATUS.md` §4AC/§4AD.
