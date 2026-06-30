# KQL Construct Coverage Scorecard

**Last updated:** 2026-06-30 (§4X/§4Y/§4Z/§4AB)

This is a living artifact, not a one-time audit. Every construct found
in the dataset (81 verified pairs + 97 never-tuned-against fresh
candidates, 178 real ASIM-normalized queries total) is enumerated here
with three columns: how often it appears in real ground truth, whether
the IR can express it, and what evidence exists that the IR Builder
actually produces it correctly when it should.

**The rule going forward** (per the critique that prompted this file):
no new stage type or operator is added to this table as "Supported"
without (a) live verification against ≥5 fresh, never-tuned-against
ground-truth cases, and (b) a row here recording the result. Construct
coverage and tested accuracy must grow together, or the scorecard
becomes the same kind of unverified claim it exists to prevent.

**Headline coverage number** (the actual point of this file, counted
directly from the tables below, not estimated): of the **33** distinct
constructs appearing in **≥5** real ground-truth queries, **22 (66.7%)
are fully Supported**, **2 (6.1%) are Partial**, and **9 (27.3%) are
Not Supported**. Supported-or-Partial combined: 24/33 (72.7%). Up from
59.4%/68.8% at this file's first writing (§4X/§4Y) after closing
`arg_max`/`arg_min` and `parse` (§4Z), and up again this round (§4AB)
after closing `=~`/`!~` (case-insensitive equality) — a construct the
original frequency sweep never even counted, found only while chasing
a *different*, lower-priority gap (the `_cs` case-sensitive variants
row, which stays outside this ratio: confirmed real but at 0 measured
occurrences in the verified+held-out corpus, so it doesn't clear this
file's own >=5 bar). This number should go up every round that closes
a gap, and is the number to cite for "how much of real-world KQL does
this cover" — not an unbounded or implied 100% claim. (An initial draft
of this file asserted 76.7% without recomputing it from the actual
table — caught and corrected before publishing; the discipline this
file exists to enforce applies to writing it, too.)

## How to read "IR support status"

- **Supported** — a typed `Stage`/`FilterOperator`/`AggregationFunction`
  exists, or the construct is a real KQL function on
  `_KNOWN_KQL_FUNCTIONS` usable inside `ExtendStage` (validated, not a
  hallucination risk).
- **Partial** — some real use is expressible, but a common variant or
  semantic detail isn't (named in the note).
- **Not Supported** — no IR construct exists; the IR Builder is
  expected to either omit the affected part (disclosed via `caveats`)
  or fall back to the broadest correct simplification.

## How to read "tested accuracy"

- A specific `n/m` ratio means: live-verified this many times against
  real or representative cases, this session, with the result recorded
  in PROJECT_STATUS.md (linked).
- "Aggregate only" means the construct is exercised somewhere in the
  tuned (87.2%) or held-out (82.4% median, IQR 5.9) Logic Correctness
  figures, but was never isolated and measured on its own — the
  aggregate number is real but not a per-construct signal.
- "Untested" means no live evidence exists either way yet.

---

## Filter operators

| Construct | Frequency (of 178) | IR support status | Tested accuracy |
|---|---|---|---|
| `where` (general) | 174 | Supported (`WhereStage`) | Aggregate only |
| `has_any` | 77 | Supported (`FilterOperator.HAS_ANY`) | Aggregate only |
| `in` (case-sensitive) | ~30 | Supported (`FilterOperator.IN`) | Aggregate only |
| `in~` (case-insensitive) | 30 | Supported (`FilterOperator.IN_CI`) — added §4X | 5/5 live (§4X, `5b6ae038`-adjacent checks) |
| `has_all` | 9 | Supported (`FilterOperator.HAS_ALL`) — added §4X, fixing a prompt bug that claimed it didn't exist | 5/5 live on its ground-truth source case (`5b6ae038`) (§4X). The §4Z finding below this row ("2/5 evasion fire rate... worth a closer look") was re-investigated in §4AB and traced to three compounding FIXTURE bugs, not a construct weakness: the exclusion field name, and the has_all value list itself, were both pinned to the generator's arbitrary draw instead of the system's own (the system correctly substitutes a named tool's real flags over the back-translation's paraphrase — existing, intentional §4N behavior the fixture wasn't accounting for). Re-measured after the fix, n=15 fresh draws: **fire 14/15 (93.3%), nofire 14/15 (93.3%), 0 field_mismatch** — the construct's real accuracy, not the fixture artifact this row previously reported. |
| `!in~` | 5 | Supported (`FilterOperator.NOT_IN_CI`) — added §4X | Untested in isolation (same code path as `in~`) |
| `matches regex` | 7 | Supported (`FilterOperator.MATCHES_REGEX`) | Aggregate only |
| `contains`/`startswith`/`endswith` (+ negated) | high, uncounted individually | Supported | Aggregate only |
| `==`/`!=`/`>`/`<`/`>=`/`<=` | high, uncounted individually | Supported | Aggregate only |
| `=~`/`!~` (case-insensitive equality) | **13** (9 in the 81 verified pairs, 3 in the held-out 18, 1 in the construct-coverage test set) — not in any prior frequency audit; found while closing the `_cs`-variant gap below, not by the original §4X/§4Y sweep, which means that sweep's "32 constructs at >=5 occurrences" universe itself undercounted by at least one real construct | Supported (`FilterOperator.EQ_CI`/`NEQ_CI`) — added this round, alongside the `_cs` row below, after a real ground-truth case (a base64-encoded PowerShell payload detection) was found using both `=~` and `has_cs`/`contains_cs` in the same query | 9/10 live across two independently-phrased fresh NL cases (neither copied from ground truth) chose `=~` correctly with NO explicit "case-insensitive" cue in the NL — matching how the real ground-truth case itself gives no such cue either; the 1/10 outlier used an NL phrase ("is exactly X") that itself cues case-SENSITIVE intent, arguably a correct reading, not a miss. End-to-end fire/no-fire confirmed directly against the interpreter on a captured live IR: fires across a case-varied process name, does not fire on a different process or an internal-IP row. See PROJECT_STATUS.md §4AB. |
| `contains_cs`/`startswith_cs`/`endswith_cs`/`has_cs` (+ negated) (case-sensitive variants) | 0 in the verified+held-out corpus directly, but confirmed real in the broader raw corpus (a base64-payload detection using `has_cs`/`contains_cs` together) — does not clear this file's >=5 bar on its own and is NOT counted in the headline ratio below for that reason | Supported (`FilterOperator.CONTAINS_CS`/`NOT_CONTAINS_CS`/`STARTSWITH_CS`/`NOT_STARTSWITH_CS`/`ENDSWITH_CS`/`NOT_ENDSWITH_CS`/`HAS_CS`/`NOT_HAS_CS`) — added this round | 10/10 live across two trials of a fresh, paraphrased (not copied) base64-PowerShell-payload NL case: the model correctly chose `contains_cs` for the case-sensitive base64 fragment and plain `has`/`=~` for the case-insensitive launcher-flag/process-name parts, every trial, never confusing the two directions. 3/10 end-to-end fire/no-fire trials were fully clean (right field names AND right flag spelling guessed by both the model and this round's synthetic fixture); the other 7/10 "misses" were the fixture's own field-name/flag-spelling assumptions not covering an equally valid model choice (e.g. `-EncodedCommand` vs. `-enc`, `ActingProcessName` vs. `Process`) — the same fixture-coupling lesson §4Z/§4AA already document, encountered firsthand while verifying this row, not a defect in the operator. Case-sensitivity itself (the actual thing being tested) was confirmed correct in every trial that ran far enough to check it: a different-case base64 fragment never matched. See PROJECT_STATUS.md §4AB. |

## Aggregation functions (inside `SummarizeStage`/`MakeSeriesStage`)

| Construct | Frequency | IR support status | Tested accuracy |
|---|---|---|---|
| `count()` | high, uncounted individually | Supported | Aggregate only |
| `dcount()` | 26 | Supported (`DISTINCT_COUNT`) | Aggregate only |
| `make_set()` | 47 | Supported (`MAKE_SET`) | Aggregate only |
| `make_list()` | 9 | Supported (`MAKE_LIST`) | Aggregate only |
| `sum`/`avg`/`min`/`max` | not separately counted | Supported | Aggregate only |
| `percentile()` | not separately counted | Supported (needs `percentile` param) | Aggregate only |
| `stdev()`/`variance()` | not separately counted | Supported | Aggregate only |
| `arg_max`/`arg_min` | 36 | Supported (`SummarizeStage.arg_max`/`arg_min`, an `ArgMaxMin` model with `order_field`/`carry_fields`/optional `result_alias`) — promoted from Partial §4Z | 2/2 synthetic "most recent"/"first seen" cases, 6/6 trials clean after fixing a real, 100%-reproducible bug (the model assumed `result_alias` prefixes every carried field's name too — it only renames `order_field`'s own column; fixed via explicit worked-example correction, §4Z). Reverse-generation synthesis eval (§4Z, n=2, too small to read much into): 1/2 failed to complete at all (a separate, unexamined repair-budget exhaustion — worth a closer look at scale); the 1 that completed fired correctly. |

## Stages / pipe operators

| Construct | Frequency | IR support status | Tested accuracy |
|---|---|---|---|
| `extend` | 164 | Supported (`ExtendStage`) | Aggregate only |
| `summarize` | 123 | Supported (`SummarizeStage`) | Aggregate only |
| `project` (select-only) | 92 | Supported (`ProjectStage`) | Aggregate only |
| `join` (all 9 kinds) | 61 | Supported (`JoinStage`) | Aggregate only |
| `union` (plain) | 63 | Supported (`UnionStage`) | Aggregate only |
| `union isfuzzy=true` | 56 | **Partial** — `UnionStage` exists but doesn't model the `isfuzzy` flag specifically (compiler never emits it) | Untested |
| `top` (with `by`) | 5 | Supported (`TopStage`) | Aggregate only |
| `mv-expand` | 35 | Supported (`MvExpandStage`, multi-field lockstep) — added §4X | 4/4 live (cross-field mismatch bug found and fixed, §4X) + 4 fresh-case validations (§4X/§4Y) |
| `make-series` | 9 | Supported (`MakeSeriesStage`) — added §4X | **≥5 fresh/representative cases, the scorecard's own bar, satisfied**: `01191239` (documented gap case) 5/5; `02f23312` 3/3; `cf687598` 3/3 (structurally correct, missing an "errors" qualifier — noted residual); `5965d3e7` 2/3 correct, 1/3 a different, incomplete (no final filter) approach; `cbf07406` correctly abstains entirely rather than exercising the construct (no concrete signal beyond an unsupported watchlist) — itself a valid outcome, not a failure. Reverse-generation synthesis eval (§4Z) initially found a *measurement* limitation, not a system failure — all 3 cases hit a field-name mismatch between the auto-fixture's hardcoded names and the system's own (also reasonable) choice of names for the same columns. Fixed by decoupling fixtures from field identity (deriving expected field names from the system's own regenerated IR instead of assuming they match the generator's): re-run after the fix, n=3, **completion 100%, fire 100%, nofire 100%, field_mismatch 0** — the construct's real execution-validated accuracy, not a fixture artifact. |
| `series_decompose_anomalies` (as `extend (a,b,c) = ...`) | 10 | Supported (`SeriesAnomalyStage`) — added §4X | Same evidence as `make-series` above (always paired) |
| `let` (constant binding) | 138 | Supported via inline literal/threshold substitution — no dedicated stage needed for this case | Aggregate only |
| `let` (subquery binding) | included in the 138 | **Not Supported** as a distinct construct — `JoinStage.right_pipeline` achieves the equivalent effect for the join-relevant subset, but a `let`-bound subquery referenced multiple times or outside a join has no IR equivalent | Untested |
| `parse` (pipe operator) | 21 | Supported (`ParseStage`, simple/positional mode — `kind=regex`/`kind=relaxed` out of scope, tail policy) — added §4Z | 5/5 fresh synthetic cases tested, 4/5 fully clean (firewall log-line extraction, JNDI host extraction, "net user" username extraction, and a case where the model correctly determined parse wasn't needed since a clean ASIM field already held the value); 1/5 (`syslog_severity_extract`) schema-valid but semantically weak — a complex multi-field literal structure collapsed to a single bare wildcard-column-wildcard, losing positional precision. Real, narrower residual, not chased further this round. Reverse-generation synthesis eval (§4Z, n=1 — too small to add signal beyond the above): completion 100%, fire 100%, nofire 100%. |
| `project-away` | 26 | Not Supported (cosmetic — doesn't change which rows fire) | Untested |
| `project-rename` | 8 | Not Supported (cosmetic) | Untested |
| `project-reorder` | 18 | Not Supported (cosmetic) | Untested |
| `order by`/`sort by` | 28 (combined) | **Partial** — `TopStage` covers the dominant "top N by field" detection-rule pattern; a bare unlimited sort has no IR equivalent | Untested |
| `distinct` | 5 | Not Supported | Untested |
| `take`/`sample` | 10 (combined) | Not Supported | Untested |
| `toscalar` | 56 | Not Supported | Untested |
| `materialize` | 25 | Not Supported (a performance hint; the compiler doesn't need it structurally) | Untested |
| `externaldata` | 28 | Not Supported — deliberate (see §4Y coverage-boundary policy below) | Untested |
| `datatable` | 13 | Not Supported | Untested |
| `print` | 12 | Not Supported (debugging/scalar-output, no detection-logic role) | Untested |
| `bag_unpack` | 3 | Not Supported | Untested |
| `evaluate` (plugin invocation) | 3 | Not Supported | Untested |
| `pivot` | 3 | Not Supported | Untested |
| `range` | 1 | Not Supported | Untested |
| `find` | 1 | Not Supported | Untested |
| `lookup` | 4 | Not Supported | Untested |

## String / time / array functions (inside `ExtendStage` expressions)

All of the following are on `_KNOWN_KQL_FUNCTIONS` (`ir_validator.py`)
and usable inside any `ExtendStage` expression today — Supported, not a
gap this round needed to touch:

`tostring`, `split`, `strcat`, `strcat_array`, `substring`, `replace`,
`trim`, `tolower`/`toupper`, `parse_json`, `parse_url`, `parse_urlquery`,
`parse_csv`, `parse_path`, `extract`, `extract_all`, `ago`, `now`,
`datetime_diff`, `datetime_add`, `startofday`/`endofday` (+ week/month/
year variants), `format_datetime`, `iff`/`case`/`coalesce`,
`array_length`, `array_slice`, `ipv4_is_private`, `ipv4_is_match`,
`ipv4_is_in_range`, `hash`/`hash_sha256`, `todynamic`.

Frequency for these individually wasn't separately tabulated this
round (`tostring` alone: 107; `split`: 81; `ago`: 86 — all comfortably
above the ≥5 threshold and already counted in the headline number).

---

## §4Z reverse-generation synthesis eval — converting "Aggregate only" into measured numbers

The execution-validation oracle (§4Y's `ir_interpreter.py`) plus a
template-based IR generator (`src/synthesis/`) closes the loop the
critique asked for: generate a valid IR directly from the schema →
compile to KQL (valid by construction) → back-translate to NL via an
LLM → feed the NL through the real system → execution-validate the
system's OWN regenerated IR against auto-generated should-fire/
should-not-fire fixtures derived from the same generation metadata.
This is the first per-construct-TEMPLATE execution-validated accuracy
this project has produced, replacing several "Aggregate only" cells'
implicit assumption with an actual number — on a small batch (n=24
across 8 templates), not yet the "hundreds" scale that would let these
numbers generalize with confidence.

**A real measurement bug was found and fixed before trusting these
numbers**: the first run showed `threshold_summarize` and
`make_series_anomaly` apparently failing almost completely
(field_mismatch 4/5 and 3/3) — not because the system was wrong, but
because the auto-fixture's hardcoded field names didn't track when the
system reasonably chose a *different* field for the same semantic role
(e.g. grouping by `Process` instead of the generator's
`ActingProcessName`; using `dcount(DnsQuery)` instead of `count()`).
Fixed by decoupling fixtures from field identity for templates where
the field's name carries no semantic weight of its own — the fixture
is now built around whatever field the **system's own regenerated IR**
actually references, not the generator's original choice (see
`src/synthesis/fixture_generator.py`'s module docstring for the
template-by-template reasoning on which side of that line each one
falls). After the fix, re-running the same 24-example batch:

| Template | n | completion | fire | nofire | field_mismatch |
|---|---|---|---|---|---|
| `threshold_summarize` | 5 | 100% | 100% | 100% | 0 |
| `make_series_anomaly` | 3 | 100% | 100% | 100% | 0 |
| `has_all_evasion` | 5 | 100% | 40% | 100% | 0 |
| `arg_max_latest` | 2 | 100% | 100% | n/a | 0 |
| `join_baseline` | 2 | 100% | 100% | n/a | 0 |
| `parse_extract` | 1 | 100% | 100% | 100% | 0 |
| `simple_filter` | 3 | 100% | 66.7% | 100% | 0 |
| `or_list` | 3 | 100% | 33.3% | 50% | 1 |

`threshold_summarize` and `make_series_anomaly` went from
unmeasurable (drowned in fixture brittleness) to a clean 100% once the
fixture itself was fixed — these are now genuinely trustworthy numbers,
not just unblocked ones. `has_all_evasion`'s 40% fire rate (it never
fails to correctly NOT fire on the literal-tool-name exclusion case,
100% nofire) and `or_list`'s mixed numbers are real signals at n=2-5 —
too small to generalize from, flagged for a larger batch, not chased
further this round. `simple_filter`'s 66.7% reflects a single observed
miss in 3 trials, also too small to read into.

**A second, orthogonal finding from the same work**: comparing this
round's LLM-back-translated descriptions against real ground-truth
descriptions side by side shows a real, visible style gap — every
synthetic description follows a rigid "this rule detects X, which may
indicate Y" template, while real descriptions vary far more (one real
example, `bd89c7a0`, is six words with no rationale clause at all:
"breakdown of scripts running in the environment"). This means
synthetic accuracy numbers likely run somewhat optimistic relative to
real-world input variety and should not be cited as equivalent to a
held-out real-data number — flagged honestly, not corrected this round
(correcting it would mean deliberately writing messier, more varied
back-translations, which risks then under-specifying the test).

**The honest, bounded coverage claim this file now supports**: 71.9%
of constructs appearing in ≥5 real detection rules are Supported or
Partial, with explicit, deliberate abstention beyond that boundary —
not an unbounded "covers KQL" claim.

### What's still open after this round

- Scale: 24 examples is enough to prove the loop works and to validate
  the fixture-decoupling fix; it is not enough to trust any single
  template's percentage as a stable estimate, and it tests constructs
  in isolation, never combinations (parse feeding a later summarize,
  arg_max inside a join, mv-expand feeding a make-series) — exactly
  where real, unseen rules are most likely to break in ways isolated
  per-construct testing structurally cannot surface.
- `has_all_evasion`'s 40% fire rate and `or_list`'s mixed numbers are
  real, small-sample signals worth a closer look at scale, not
  explained away.
- A permanent regression gate was started, not completed: 2 new
  `tests/integration/test_live_e2e_execution_validation.py` anchors
  (the §4U OR-list-as-AND-chain regression; the §4V CVE-ID-as-literal
  bug) join the 3 already there, each targeting one specific,
  previously-fixed bug class rather than a fresh capability — but this
  is 5 anchors against an unbounded number of bug classes fixed across
  this project's history, not yet comprehensive.
- Retrieval-augmented few-shot is **no longer unstarted** (§4AB) — three
  routed local TF-IDF indexes (construct syntax, ASIM field
  definitions, worked examples), wired into `ir_builder_agent.py`
  behind an opt-in `use_rag`/`USE_RAG_RETRIEVAL` flag, off by default.
  A frozen-held-out-set A/B (`eval/run_rag_ab.py`) found no measurable
  SVR/FVR difference at n=18 — see PROJECT_STATUS.md §4AB for the full
  result, including a real `eval/metrics.py` FVR-undercounting bug
  (the third instance of this exact bug class, after "percentile") the
  A/B's first run surfaced and this round fixed. Logic Correctness
  under RAG was not measured this round — the open item going forward.

---

## §4AA construct combinations, scaled to n=60, plus the measured (not
     just flagged) synthetic-vs-real NL gap

Direct continuation of §4Z. Three new generator templates were added,
each a 2-3-construct CHAIN rather than an isolated construct, and the
batch was scaled from 24 to 60 with a mixed sampler (`generate_mixed_batch`,
default 50% combination / 50% single-construct draws). Final, clean
numbers after fixing the bugs the scaling itself surfaced (below):

| Template | n | completion | fire | nofire | field_mismatch |
|---|---|---|---|---|---|
| `parse_then_summarize` (parse → summarize on the EXTRACTED field) | 14 | 100% | 92.9% | 85.7% | 0 |
| `arg_max_in_join` (arg_max inside a join's right_pipeline) | 15 | 100% | 46.7%¹ | 100% | 2¹ |
| `make_set_mv_expand_filter` (make_set → mv-expand → filter the expanded item) | 8 | 100% | 87.5% | 100% | 0 |
| `parse_extract` | 5 | 100% | 80.0% | 100% | 0 |
| `or_list` | 3 | 100% | 100% | 100% | 0 |
| `join_baseline` | 3 | 100% | 100% | n/a | 0 |
| `make_series_anomaly` | 3 | 100% | 100% | 100% | 0 |
| `simple_filter` | 3 | 100% | 100% | 100% | 0 |
| `threshold_summarize` | 3 | 100% | 100% | 100% | 0 |
| `arg_max_latest` | 2 | 50% | 100% | n/a | 0 |
| `has_all_evasion` | 1 | 100% | 100% | 100% | 0 |
| **overall** | **60** (37 combination, 23 single-construct) | **98.3%** | **84.2%** (48/57) | **96.2%** (51/53) | **2/60** |

¹ Measured BEFORE the field-to-field comparison fix below — both the
46.7% fire rate and the 2 field_mismatch cases trace to that one gap.
Re-measured AFTER the fix, same n=15: **completion 15/15, fire 15/15,
nofire 15/15, field_mismatch 0** — now the cleanest-scoring template in
this table. Row left as originally measured rather than overwritten,
since the before/after contrast is itself the evidence that the fix
worked, not just an assertion that it did.

Cost/latency, logged for the first time this round (`run_synthesis_eval.py`,
via `langchain_community`'s OpenAI-compatible token-usage callback —
works against `azure_foundry` since both ride `ChatOpenAI` under the
hood): **avg 21,489 tokens and 5.6s per query** across the 60-example
batch (combination templates cost more: `arg_max_in_join` averaged
24,738 tokens/7.3s vs. single-construct templates' ~18,100 tokens/~4s).
The honest product claim is now "N% supported at M tokens/seconds per
rule," not accuracy alone.

**Three real bugs were found and fixed while scaling, each the SAME
underlying lesson recurring at a different layer**: a fixture that
over-specifies how a construct must be solved marks a correct,
differently-shaped answer wrong.
1. `parse_then_summarize` hit 100% (14/14) field_mismatch on first
   contact: the system commonly solves "count repeated JNDI lookups"
   via `where Url contains "jndi"` grouped on an EXISTING ASIM field,
   never invoking `parse` at all — a valid alternative the fixture
   didn't anticipate (it only populated `Url`, and initially didn't
   even include `TimeGenerated`). Fixed by deriving every relevant
   field — group-by, `TimeGenerated`, and any other aggregation
   operand — from the system's own IR. Result: 0/14 field_mismatch,
   92.9% fire, 85.7% nofire.
2. `make_set_mv_expand_filter` regressed to 0% fire (0/8) once
   `min`/`max(TimeGenerated)` aggregations started appearing alongside
   `make_set(Url)` in the system's typical answer: the fixture helper
   grabbed the FIRST aggregation with any field at all, which was
   `min(TimeGenerated)`, not `make_set(Url)` — leaving the actually-
   aggregated column entirely unpopulated. Fixed by specifically
   targeting a `make_set`/`make_list` aggregation. Result: 87.5% fire.
3. `arg_max_in_join`'s fixture only populated the FIRST join key; the
   system reasonably correlating on two keys (`Dvc`, `ActorUsername`)
   left the second entirely missing — fixed to populate every key in
   `JoinStage.join_on`. A separate, genuine interpreter gap was also
   found and fixed: `datetime_diff` wasn't in the safe-expression
   evaluator's function whitelist at all, so the interpreter couldn't
   assess any case using it, independent of whether the system's
   answer was otherwise correct.

**A new genuine IR expressivity gap was found — and then fixed and
live-verified** — the single most important finding from combination
testing, exactly the kind of seam failure isolated per-construct
testing cannot surface. `arg_max_in_join`'s remaining 2/15
field_mismatch and a chunk of its 46.7% fire rate traced to the same
root cause: `arg_max_in_join`'s NL (bracketing a process event's time
against a joined authentication event's time window) needs a
FIELD-TO-FIELD comparison (`ProcessTime` between the joined row's
`FirstAuthTime` and `LastAuthTime`). `Filter.value`'s type
(`Union[str, int, float, bool, List[...]]`, `ir_schema.py`) had no way
to express "compare against another column" — the compiler always
rendered `value` as a literal. The model correctly recognized the
detection needed this and produced KQL like:

```
| extend ProcessTime = TimeGenerated
| where ProcessTime >= "FirstAuthTime"
| where ProcessTime <= "LastAuthTime"
```

— syntactically valid, silently wrong (`"FirstAuthTime"` is a quoted
STRING LITERAL, not the column). More dangerous than an outright parse
failure because nothing flags it.

**Fixed this round**: added `Filter.field_ref: Optional[str]`
(mutually exclusive with `value`, enforced by a `model_validator`) —
compiler renders it as a bare, unquoted column reference; validator
checks it against the running `available_schema` the same way `field`
is checked (it already tracks join/extend-produced columns by the
point a later WhereStage runs, so this isn't exempted); interpreter's
`_eval_single_filter` reads `row[field_ref]` instead of treating it as
a literal, with a datetime-comparison fallback added to GT/LT/GTE/LTE
for when the values aren't numeric. Taught via a new worked example in
`ir_builder_agent.py` (with an explicit non-example of the old, broken
quoted-literal shape). **Live-verified 5/5 clean** on the exact NL
shape that originally exposed the gap — every trial now renders
`ProcessTime >= FirstAuthTime` unquoted. Added as a new permanent
regression anchor (`test_process_time_bracketed_by_joined_auth_window_uses_field_ref_not_literal`,
6/6 clean across repeated runs after two earlier fixture-design
iterations — see that test's docstring for why a naive "vary only the
timestamp" or "vary only the host" fixture design is unreliable against
the interpreter's table-agnostic join model, independent of whether
field_ref itself works).

**A third pattern was found and deliberately NOT chased**: in a
smaller sample, `join_baseline` (intended to exercise a literal
join-based baseline ratio) was sometimes answered via `make-series` +
`series_decompose_anomalies` instead — a different, arguably more
idiomatic construct for "is this unusual vs. a baseline." The single-row
fixture this template uses can't exercise a real anomaly pipeline
correctly, the same class of issue as the three bugs above, but at n=3
this is sample noise as much as it is signal (a later n=3 batch scored
100% with the same fixture). Logged as a known limitation rather than
patched a third time this round — the construct-substitution pattern
itself (not any one instance of it) is the project's main remaining
auto-fixture risk at scale.

### The synthetic-vs-real NL gap: measured, not just flagged

§4Z flagged a style gap (synthetic descriptions read as more uniform
than real ones) but did not measure its effect on accuracy. Two moves:

**(1) Real ground truth through the same metric.** Ran this project's
5 existing hand-built regression-anchor cases (now the regression
gate) through the SAME execution-validated loop, 5 reps each
(`src/synthesis/run_real_eval.py`, new this round): **100% completion,
100% fire (20/20), 100% nofire (25/25)**, avg ~18.8K tokens, ~4.1s/query.
Important caveat, stated plainly: these 5 cases are not a representative
real-world difficulty sample — they are cases this project has already
iterated on and fixed bugs for across many prior rounds, so their 100%
partly reflects "we already fixed the bugs these specific cases
exposed," not "real descriptions are inherently easier than synthetic
ones." This number is a regression floor, not a generalization claim.

**(2) A controlled rich-vs-terse comparison on IDENTICAL underlying
IRs.** Added a "terse" back-translation style to `BackTranslator`
(no rationale clause, no "this rule detects" framing, matched to a real
example: `bd89c7a0`, six words, no rationale) and re-ran the SAME 24
generated IRs (same seed, confirmed via matching `generated_kql`)
through it. Result: fire dropped from 90.9% (20/22, rich) to **54.5%**
(12/22, terse) — a 36.4-point drop on the exact same detection logic,
nothing else changed. nofire dropped less (95.2% → 85.7%).

This is a real, controlled, causal finding — but it is NOT a uniform
"synthetic NL inflates accuracy by 36 points" tax. Pairing each terse
case against its rich counterpart shows the drop is concentrated almost
entirely in `parse_then_summarize` (7 of 8 occurrences flipped from
fire=True to fire=False); `simple_filter`, `make_series_anomaly`,
`arg_max_in_join`, and `parse_extract` were largely unaffected by style
across the same pairs. The likely mechanism: `parse_then_summarize`'s
detection concept (JNDI lookup pattern counting) depends on the NL
naming a specific literal/structural pattern (`jndi:ldap://`); a terse
description omits exactly that detail, while the model can still infer
simpler filter/threshold logic without it. **The gap is real and
construct-dependent, concentrated where correct implementation depends
on literal/structural specificity the terse style strips out** — not a
flat discount applicable to every accuracy number in this file.

### What's still open after this round

- The field-to-field comparison gap (`Filter.field_ref`) is fixed and
  live-verified — no longer open. Re-measured at the same n=15 scale as
  the rest of this round's table: **completion 15/15, fire 15/15,
  nofire 15/15, field_mismatch 0** — up from 46.7% fire and 2/15
  field_mismatch before the fix. `arg_max_in_join` is now the
  cleanest-scoring template in this round's table.
- The construct-substitution pattern (a model solving a template's
  intended construct via a different, equally valid one) recurred 3
  times this round; the auto-fixture generator's biggest remaining risk
  at further scale is this pattern recurring in templates not yet hit
  by it, not any one fixed instance.
- The real-vs-synthetic gap is now measured for one mechanism (NL
  terseness) on one construct profile; a broader, FRESH (not
  previously-debugged) sample of real ground truth would be needed for
  a cleaner real-vs-synthetic comparison than the existing 5
  regression-anchor cases allow.
- RAG remains correctly deferred: it changes the system rather than
  measuring it, and is only honestly testable against a frozen held-out
  slice this project does not have yet.
- The Azure AI Foundry key rotation remains unconfirmed.

---

## §4Y coverage-boundary policy (the explicit decision this file exists to support)

Per the critique that prompted this scorecard: extending the typed IR
has a real cost (every new stage is one more thing the IR Builder must
get right, not just one more thing the validator can check), so where
it stops has to be a decision, not something discovered case-by-case.

**Decision: extend typed stages through the detection-common core;
rely on `caveats` abstention for the genuinely rare tail.**

- **Core (typed-stage investment justified)**: everything marked
  Supported or Partial above (`parse`, `arg_max`/`arg_min` closed §4Z).
  The single most common case of `let`-bound reuse — a named subquery
  used ONCE as a join's right side — is already covered by
  `JoinStage.right_pipeline`, which is itself just that pattern modeled
  directly.
- **Tail (abstention, not typed modeling)**: `externaldata`,
  `toscalar`, `datatable`, `print`, `bag_unpack`, `evaluate`, `pivot`,
  `range`, `find`, `lookup`, and **`let`-bound subqueries beyond the
  single-use-as-a-join case** — moved here after actually checking,
  not assuming, whether the auto-fixture generator could fixture it
  (per the critique's own caution: "check whether the generator can
  even fixture it... before you build it"). Sampling real ground truth
  found this is NOT just "a reusable tabular expression" — it includes
  parameterized, named FUNCTIONS (`let f = (stime, etime) { ... }`,
  found live in `983a6922`) and DAGs of mutually-referencing named
  results (`24e66452`'s `Include`/`Exclude`/`AllSecEvents`, each
  referencing the others). Both are genuinely a different IR shape — a
  graph of named sub-pipelines, not the tree `KqlPipeline` already is —
  not "one more stage type." Building a typed stage the fixture
  generator structurally cannot validate would violate this file's own
  ≥5-fresh-cases rule by construction, so this is correctly tail, not
  core, confirmed rather than assumed. The rest of the tail list is
  either genuinely rare, externally-dependent (a live feed/workspace
  the IR has no business modeling), or primarily debugging/presentation
  constructs with no detection-logic weight. When a description needs
  one of these, the IR Builder is
  expected to do what it already does for any other ungroundable
  reference — implement what it concretely can, and disclose the gap
  via `caveats` rather than force a fragile, expensive typed model of a
  rare construct. This is the same honesty mechanism already built and
  validated (§4T/§4U) for missing literal values, applied here as the
  explicit, permanent boundary for rare constructs instead of a
  case-by-case judgment call.
- **Cosmetic (deliberately deprioritized, not in scope to abstain
  about either)**: `project-away`/`project-rename`/`project-reorder`,
  `order by`/`sort by` beyond what `TopStage` covers, `distinct`,
  `take`/`sample`. These don't change which rows a detection fires on —
  lower logic-correctness priority than anything else in this document,
  per the frequency × logic-impact sort the critique asked for.
