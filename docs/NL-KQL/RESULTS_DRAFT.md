# Results — Draft (2026-06-22 evaluation run)

**Status: draft, from a single evaluation run.** Numbers are real and
reproducible (`eval/results/`), not illustrative — but the dataset
verification, paraphrase review, and Logic Correctness scoring below were
all done by Claude at the user's explicit instruction, not independently
human-reviewed. Treat this as a strong first draft of the Results and
Discussion sections, not a final, publication-ready write-up. See
`PROJECT_STATUS.md` for the full provenance trail and caveats.

---

## Abstract (draft)

Direct LLM generation of KQL from natural-language detection descriptions is
known to hallucinate syntax and fields. This project tests whether an
explicit, ASIM-schema-validated Intermediate Representation (IR), combined
with a 2-agent extraction pipeline and a bounded repair loop, reduces that
hallucination relative to direct generation — at a specific, fixed model
scale (Qwen3.5, 4B for IR construction and baseline generation, 2B for
extraction, run locally at temperature 0).

On a 45-record held-out test set (15 NL→KQL pairs × 3 paraphrase styles,
drawn from 81 manually-verified pairs sourced from Microsoft's
Azure-Sentinel repository), the result **does not support the central
hypothesis at this model scale**: the IR-mediated pipeline (System B)
produces *any* usable output for only 20% of cases (repair-loop exhaustion
on the remaining 80%), versus 100% for direct generation (System A). Counting
non-completion as failure — the only fair comparison, since an analyst needs
*a* query — System A's overall syntax validity (95.6%) and field/table
validity (20.0%) both exceed System B's (20.0% and 13.3% respectively),
inverting the predicted direction of H1. The repair loop recovers only
20.0% of initial failures (RRR), well below the project's own 50%
falsification threshold for H3, falsifying it cleanly: 0/45 cases converged
on the first attempt, and the dominant failure mode (`filter.value: null`)
is deterministic at temperature 0, not a transient slip a re-prompt fixes.
Three ablations attribute these results precisely: removing the repair loop
drops System B's success to exactly 0% (100% of its yield comes from
repair); removing schema grounding also craters success to 0% with the
highest crash rate observed (strong, clean support for the IR's schema-
grounding *mechanism*, decoupled from whether it's sufficient); merging the
two-agent decomposition into one call performs statistically indistinguishably
from the decomposed pipeline (a clean null for RQ2 at this scale). Most
severely: of the queries that pass *both* automated validity checks, only
13.3% (2/15) are manually judged logically correct — confirming that
syntax/field validity, even after fixing a real measurement bug that let
System A's completely fabricated table names slip through automated
checking, is far from sufficient evidence of usability.

---

## 1. Results

### 1.1 Primary comparison (H1, H2)

| Metric | System A | System B | McNemar p | 95% CI (A / B) |
|---|---|---|---|---|
| SVR | 95.6% (43/45) | 20.0% (9/45) | 1.5×10⁻⁸ | [89,100]% / [9,33]% |
| FVR (table-aware) | 20.0% (9/45) | 13.3% (6/45) | 0.58 | [9,33]% / [4,24]% |

SVR difference is highly significant and *opposite* H1's predicted
direction when measured as overall usable-output rate. The SVR mechanism
itself is confirmed conditionally — System B is 100% syntactically valid
*given that it produces output* — but that condition holds only 20% of the
time.

FVR difference is not statistically significant at n=45 (overlapping CIs),
though System B's structural guarantee against table hallucination (its
table name is read deterministically from the validated IR's `event_type`,
never freely generated) is a real, qualitative advantage not fully captured
by the point estimate at this sample size.

### 1.2 Repair Recovery Rate (H3)

0/45 cases converged on attempt 1. RRR = 9/45 = **20.0%**, against
MASTER_PLAN's pre-registered falsification criterion of <50%. **H3 is
falsified.** Inspection of the raw logs shows the dominant failure
(`filters[i].value: null` — the model omitting a literal value it isn't
confident about) reproduces identically across repair attempts 2 and 3 in
multiple cases, consistent with a structural model limitation rather than
noise a second attempt would fix.

### 1.3 Complexity scaling (H4)

| Tier | n | System B success |
|---|---|---|
| Simple | 9 | 22% (2/9) |
| Moderate | 9 | 22% (2/9) |
| Complex | 27 | 19% (5/27) |

Flat, not widening — **H4 is not supported** in this sample. Tier sizes are
small enough (9/9/27) that this should be treated as suggestive rather than
conclusive; a larger test set is needed to resolve this with any power.

### 1.4 Ablations (RQ2, H1-mechanism, H2-mechanism)

| Ablation | Result | Interpretation |
|---|---|---|
| No-Repair (`max_attempts=1`) | 0.0% success | 100% of System B's yield comes from repair; IR-mediation has *no* advantage independent of repair at this scale |
| Monolithic Extraction | 22.2% IR-valid | Statistically indistinguishable from full System B (20.0%) — clean null for RQ2 (decomposition doesn't measurably help here) |
| No Schema Grounding | 0.0% IR-valid, highest crash rate | Strongest single result: removing grounding craters success to zero — schema grounding's *mechanism* is real and necessary, even though grounding alone is far from sufficient |

### 1.5 Logic Correctness — the most severe result

Restricted to the 15 records (9 System A + 6 System B) that pass *both* SVR
and table-aware FVR, manually scored against the 3-point rubric (event
type/table correct, comparison direction not inverted, aggregation/grouping
matches intent — all three required):

**Logic Correctness = 2/15 = 13.3%.**

Representative failure modes among nominally "valid" queries: averaging a
port *number* instead of a connection count (semantically meaningless,
syntactically and field-wise fine); a `dcount()` call with no argument
(would not execute); silently narrowing "all DNS error codes" to
"NXDOMAIN only." This is exactly the gap the Logic Correctness metric exists
to catch, and the result shows it catching a lot — automated SVR/FVR
checking, even fully corrected, materially overstates usable output quality.

---

## 2. Discussion

**The central hypothesis is not supported at this model scale.** Schema
grounding has a real, mechanistically-confirmed effect (Ablation 3), and
the deterministic template compiler genuinely eliminates syntax/table
hallucination *conditional on the IR validating* — but at Qwen3.5
4B/2B, IR construction itself fails to converge often enough (80% repair
exhaustion, 0% first-attempt success) that the net effect, measured as
overall usable-output rate, favors the naive single-shot baseline. The
repair loop — the mechanism meant to close that gap — recovers only 1 in 5
initial failures, because the dominant failure mode reflects the model not
knowing a value, which targeted re-prompting cannot supply if the model
genuinely doesn't have it.

This is consistent with, not contradictory to, the project's own
methodology: MASTER_PLAN explicitly designs the ablations to attribute
results to specific mechanisms rather than producing one entangled
before/after number, and explicitly states that "a clean negative or mixed
finding... is a valid, reportable, and useful result." That is what this
run produced. The open question the data raises directly: **is this a
finding about IR-mediation as an approach, or about Qwen3.5 4B/2B's
capability ceiling for structured extraction?** Ablation 1 (no-repair = 0%)
and the MVP's identical-completion-on-repair observation both point toward
the latter — but distinguishing the two definitively requires re-running
this exact evaluation with a stronger model, which this report does not
do.

### What changed during this analysis (worth disclosing, not burying)

- Found and fixed a measurement bug in `field_validity_rate` that excluded
  table-name validation entirely, despite MASTER_PLAN's own FVR definition
  including it. Caught via manual Logic Correctness scoring, which is a
  methodological point worth keeping in any write-up: the manual metric
  caught an automated-metric bug, not just a model failure.
- Found and fixed a critical eval-harness robustness gap (one uncaught
  exception silently discarded an entire 45-record run with zero saved
  output) before any usable results existed.
- Found and fixed a prompt-clarity bug (schema echoed back instead of an
  instance) during the Phase 2 MVP, before it could contaminate Phase 4.
- Proceeded to Phase 4 despite the MVP not meeting MASTER_PLAN's literal
  "sensible IRs on all 10 cases" gate — a judgment call, flagged explicitly
  in `PROJECT_STATUS.md`, made because the *infrastructure* bugs that gate
  exists to catch were fixed, and a low success rate honestly measured is
  itself the valid result MASTER_PLAN's hypothesis-testing framework
  anticipates.

---

## 3. Limitations specific to this run

- **n=45** (15 unique cases × 3 paraphrases) is small; CIs are wide and
  several comparisons (FVR, H4) are not statistically significant at
  conventional thresholds. This is a pilot-scale result, not the full
  100–150-pair evaluation MASTER_PLAN's Phase 4 specifies — the train split
  (66 pairs, no paraphrases) was not run through the comparison at all.
- **Single model, single temperature.** All conclusions are scoped to
  Qwen3.5 4B (IR Builder + baseline) / 2B (Extraction) at temperature 0,
  local Ollama. Nothing here generalizes to larger or hosted models without
  re-running.
- **Dataset verification, paraphrase review, and Logic Correctness scoring
  were AI-assisted, not independently human-reviewed.** A second pass by a
  KQL-familiar human (the inter-rater reliability check MASTER_PLAN
  recommends) has not been done.
- **Logic Correctness denominator is small (n=15)** — 2/15 passing is a
  severe result, but with this few data points a couple of different
  judgment calls on borderline cases would move the percentage substantially.
- **Train-split pairs have no paraphrase variants** — paraphrasing was
  scoped to the test split only, given time/volume constraints.

---

## 4. Conclusion (draft)

At the model scale tested, IR-mediated generation does not outperform
direct generation on overall usable-output rate, despite confirming its
core mechanisms (deterministic syntax validity, schema-grounding's
necessity) conditionally. The repair loop, intended to close the gap
between "IR mechanism is sound" and "small models reliably use it,"
recovers too few cases to do so. Whether this reflects a fundamental limit
of small local models for this task, or a prompt/repair-strategy
improvement not yet found, is the open question this report surfaces but
does not resolve — re-running with a stronger model is the natural next
step before drawing conclusions about the IR-mediation approach itself
rather than about Qwen3.5 4B/2B specifically.
