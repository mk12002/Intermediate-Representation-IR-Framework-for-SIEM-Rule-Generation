# Evaluation Methodology — Deep Dive

The [README](../README.md) covers evaluation at landing-page depth. This document specifies exact metric definitions, the ablation protocol, statistical methodology, and the logic-correctness rubric in full.

## Table of Contents

- [Metrics — Exact Definitions](#metrics-exact-definitions)
- [Primary Comparison](#primary-comparison)
- [Ablations](#ablations)
- [Stratified Analysis](#stratified-analysis)
- [Statistical Treatment](#statistical-treatment)
- [Logic Correctness — Manual Scoring Rubric](#logic-correctness-manual-scoring-rubric)
- [Baseline Fairness](#baseline-fairness)
- [Reporting Format](#reporting-format)
- [What Would Falsify Each Hypothesis](#what-would-falsify-each-hypothesis)

---

## Metrics — Exact Definitions

### Syntax Validity Rate (SVR)

$$\text{SVR} = \frac{\text{\# generated queries that parse successfully}}{\text{\# total queries generated}}$$

A query "parses successfully" if it passes the [KQL Syntax Validator](architecture.md#kql-syntax-validator-specification) with no error. Computed independently per system (System A, System B) and per ablation configuration. For System B, this is measured **after** the repair loop completes (i.e., on the final output, whether reached on attempt 1 or attempt 3) — a separate metric, [Repair Recovery Rate](#repair-recovery-rate), measures the repair loop's contribution specifically.

### Field Validity Rate (FVR)

$$\text{FVR} = \frac{\text{\# generated queries where every referenced table/field exists in the ASIM schema}}{\text{\# total queries generated}}$$

Computed by parsing field/table references out of the generated KQL string (regardless of which system produced it) and checking each against the [extracted ASIM schema reference](dataset.md#schema-reference-extraction) — **not** by trusting the IR's internal validation status for System B, since the point of this metric is to verify the *final KQL output*, independent of which pipeline produced it. This symmetry is what makes FVR comparable across System A and System B at all.

Field extraction from a raw KQL string uses a lightweight regex/AST-walk over `where`, `summarize ... by`, `project`, and `join` clauses — implemented once in `eval/metrics.py` and shared across both systems, so any extraction quirks affect both systems identically rather than favoring one.

### Logic Correctness (Manual)

$$\text{Logic Correctness} = \frac{\text{\# syntax-valid AND field-valid queries scored as logically correct}}{\text{\# syntax-valid AND field-valid queries}}$$

Note the denominator: this metric is conditional on passing SVR and FVR first — it answers "given that a query is mechanically sound, does it mean the right thing," not "what fraction of all attempts are perfect." This separation is deliberate; conflating mechanical and semantic failure into one number would make it impossible to tell which problem dominates. See the [full rubric](#logic-correctness-manual-scoring-rubric) below.

### CodeBLEU

A weighted combination of n-gram match, weighted n-gram match (keyword-aware), AST match, and data-flow match, as defined in the original [CodeBLEU paper](https://arxiv.org/abs/2009.10297), adapted here with a KQL-specific keyword list (operator names: `where`, `summarize`, `extend`, `join`, `bin`, etc.) substituted for the original's language-specific keyword sets. Reported as a continuous score in $[0, 1]$ against `ground_truth_kql`, independent of SVR/FVR pass/fail status — i.e., computed for every generated query, including ones that fail to parse, since CodeBLEU's token/AST-level comparison can still be informative even on a malformed query (how *close* was it, even if not fully valid).

### Repair Recovery Rate

$$\text{Repair Recovery Rate} = \frac{\text{\# cases failing on attempt 1 that pass by attempt} \le 3}{\text{\# cases failing on attempt 1}}$$

Reported alongside the **mean and median number of attempts used** among recovered cases, and a breakdown of recovery rate by attempt number (recovered on attempt 2 vs. attempt 3 specifically) — this finer breakdown is what lets the write-up say something concrete about diminishing returns (the second half of H3), not just an aggregate recovery percentage.

### Pipeline Latency / Token Cost

Recorded per case, per system: wall-clock seconds and total input+output tokens across all LLM calls in the pipeline (1 call for System A; 2 to 8 calls for System B depending on repair attempts used). Reported as **median and 90th percentile**, not mean — latency distributions for LLM pipelines are typically right-skewed (occasional slow repair chains), and the median better represents the typical case while the 90th percentile honestly represents the cost tail.

---

## Primary Comparison

System A vs. System B, run once each on the full held-out test split (see [Train/Test Split Discipline](dataset.md#traintest-split-discipline)), same underlying LLM, same decoding temperature for both.

**On determinism:** System B's final KQL output is deterministic given a fixed IR (template substitution has no randomness), but the *path* to that IR (extraction, IR construction, repair) involves LLM calls that may vary run-to-run at nonzero temperature. System A's single LLM call is the more variable component. To keep the comparison fair without inflating cost:

- If temperature is set near 0 for both systems (recommended), a single run per case is acceptable, since variance is expected to be minimal.
- If a non-trivial temperature is used (e.g. to better reflect realistic usage), System A should be run 3x per case with majority-vote scoring on SVR/FVR (does the *majority* of 3 attempts pass), since a single unlucky sample would otherwise unfairly penalize System A relative to System B's repair-loop-smoothed output. This asymmetry is intentional and should be stated plainly in the write-up as a fairness accommodation, not hidden.

---

## Ablations

Each ablation isolates exactly one of System B's three design decisions, so the final result can be attributed to a specific mechanism rather than reported as one entangled "our system is better" delta.

### Ablation 1 — No-Repair IR

**Configuration:** System B with `max_attempts=1` in the [repair loop](architecture.md#the-repair-loop) — i.e., the IR Builder Agent gets exactly one attempt, no re-prompting on validator failure.

**Isolates:** how much of System B's overall advantage comes from schema-grounded IR construction itself, independent of the repair mechanism. **Tests:** H1 and H2 in a repair-free setting.

**Expected pattern if H1/H2 hold independent of repair:** No-Repair IR should still outperform System A on SVR/FVR, just by a smaller margin than full System B — if No-Repair IR performs no better than System A, that would suggest the IR's apparent advantage in the primary comparison is actually coming entirely from the repair loop, not from schema grounding, which would be an important (and currently unanticipated) finding worth its own discussion.

### Ablation 2 — Monolithic Extraction

**Configuration:** Merge the [Extraction Agent](architecture.md#extraction-agent-specification) and [IR Builder Agent](architecture.md#ir-builder-agent-specification) into a single prompt that goes directly from NL input to a `SecurityIR` object, skipping the intermediate `ExtractionOutput` structure.

**Isolates:** whether agent decomposition itself helps, independent of schema grounding (both configurations have schema grounding; only the decomposition differs). **Tests:** RQ2 directly.

**Expected pattern if RQ2 resolves "yes, decomposition helps":** Monolithic Extraction should underperform full System B on FVR and Logic Correctness specifically — the hypothesis is that decomposition helps most with *understanding* the threat correctly (a Logic Correctness concern) more than with *syntax* mechanics (already handled by the deterministic generator either way), so this ablation's results should be read primarily against Logic Correctness, not SVR.

### Ablation 3 — No Schema Grounding

**Configuration:** IR Builder Agent receives no ASIM field reference and must select field names from its own training knowledge / inference, same as a vanilla LLM would.

**Isolates:** the specific contribution of explicit schema grounding, separated from the general benefit of producing structured intermediate output. **Tests:** H2 directly, and partially H1 (since hallucinated field names sometimes correlate with knock-on syntax issues if the template compiler encounters an unexpected field shape).

**Expected pattern if H2 holds:** No Schema Grounding should show FVR much closer to System A's FVR than to full System B's FVR — if FVR stays high even without grounding, that would suggest the benefit is coming from IR *structure* itself (forcing the model to commit to a typed object) rather than from schema access specifically, which would be a meaningfully different conclusion worth highlighting rather than burying.

---

## Stratified Analysis

All of the above (primary comparison and all three ablations) are additionally broken down by [complexity tier](dataset.md#complexity-tagging-criteria) — Simple / Moderate / Complex — not just reported in aggregate. This directly tests **H4**.

**Reporting format for stratified results:**

| | Simple | Moderate | Complex |
|---|---|---|---|
| System A — SVR | x% | x% | x% |
| System B — SVR | x% | x% | x% |
| **Δ (B − A)** | **x pts** | **x pts** | **x pts** |

The Δ row across tiers is the single most interesting empirical claim the study can produce — a result like *"the gap widens from 8 points on Simple to 35 points on Complex"* is a substantially stronger and more citable finding than a single aggregate delta, and it is the direct, falsifiable test of H4. This table (for SVR, FVR, and Logic Correctness each) should be treated as a primary results table, not a secondary appendix breakdown.

---

## Statistical Treatment

At a dataset size of 100–150 pairs (after the 20% test split, roughly 20–30 test cases — small enough that point estimates alone would overstate precision):

- **Confidence intervals via bootstrap resampling** (e.g. 10,000 resamples) for every aggregate metric (SVR, FVR, Logic Correctness, CodeBLEU mean), reported as `[lower, upper]` at the 95% level alongside the point estimate.
- **Paired significance testing** for binary outcome metrics (SVR, FVR) using **McNemar's test**, since System A and System B are run on the *same* underlying NL inputs (paired design) — this is more statistically appropriate and more powerful than an unpaired test (e.g. chi-squared) given the paired structure, and using an unpaired test here would be a methodological error worth avoiding explicitly.
- **CodeBLEU**, being continuous, uses a paired t-test or Wilcoxon signed-rank test (prefer Wilcoxon if the score distribution is non-normal, which is plausible given the small sample and likely skew toward high scores for well-handled cases) rather than McNemar's.
- All p-values reported alongside effect sizes, not as the sole basis for a claim — at this sample size, statistical significance and practical significance can diverge, and the write-up should discuss both.

```python
# eval/stats.py (sketch)
from statsmodels.stats.contingency_tables import mcnemar
import numpy as np

def mcnemar_svr_test(system_a_results: list[bool], system_b_results: list[bool]) -> dict:
    # paired: same index = same underlying NL input
    both_pass = sum(a and b for a, b in zip(system_a_results, system_b_results))
    a_only = sum(a and not b for a, b in zip(system_a_results, system_b_results))
    b_only = sum(b and not a for a, b in zip(system_a_results, system_b_results))
    both_fail = sum(not a and not b for a, b in zip(system_a_results, system_b_results))

    table = [[both_pass, a_only], [b_only, both_fail]]
    result = mcnemar(table, exact=(a_only + b_only < 25))  # exact test for small discordant counts
    return {"statistic": result.statistic, "p_value": result.pvalue,
            "a_only": a_only, "b_only": b_only}

def bootstrap_ci(values: list[float], n_resamples: int = 10000, ci: float = 0.95) -> tuple[float, float]:
    resampled_means = [
        np.mean(np.random.choice(values, size=len(values), replace=True))
        for _ in range(n_resamples)
    ]
    lower = np.percentile(resampled_means, (1 - ci) / 2 * 100)
    upper = np.percentile(resampled_means, (1 + ci) / 2 * 100)
    return lower, upper
```

---

## Logic Correctness — Manual Scoring Rubric

A 3-point checklist, scored independently for each syntax-valid and field-valid query against its `ground_truth_kql`:

1. **Event type / table correct** — does the query target the same ASIM event type the ground truth does?
2. **Comparison direction correct** — are filter operators and threshold comparisons pointed the right way (e.g. not inverted: `==  "Success"` when the ground truth filters on `"Failure"`)?
3. **Aggregation/grouping correct** — does the aggregation function, field, and `group_by` set match the ground truth's intent (allowing for trivially equivalent reformulations, e.g. `dcount` vs `distinct_count` syntax differences that mean the same thing)?

**Scoring:** a query passes Logic Correctness only if **all three** checklist items pass — this is a conjunctive, not averaged, score, because a query that gets the event type and grouping right but inverts the comparison direction is not "67% correct," it's wrong in a way that would produce the opposite alerting behavior in production, which is a binary-consequence error, not a partial-credit one.

**Inter-rater reliability:** if a second reviewer familiar with KQL is available (e.g. a colleague), independently score a 20-case sample and report Cohen's κ. This is explicitly optional given the project is primarily single-researcher, but should be attempted if feasible — even a small inter-rater sample meaningfully strengthens the credibility of the manual metric, and its absence should be listed as a limitation if not done (see the [README's Limitations section](../README.md#limitations)).

---

## Baseline Fairness

Restated here in full, since it's load-bearing for the entire comparison's validity:

- **Same schema access.** System A receives the same ASIM field reference in its prompt that System B's IR Builder Agent receives. The comparison being tested is IR-mediation vs. direct generation, not "who has schema access" — giving System B exclusive schema access would confound the two.
- **Same underlying LLM, same provider, same decoding settings** (model identity and temperature) across both systems for the primary comparison. A version/provider mismatch would make any observed difference impossible to attribute cleanly to the architectural difference under test.
- **Few-shot, not zero-shot.** System A's prompt includes 2–3 worked NL→KQL examples (the [prompt sketch in `architecture.md`](architecture.md#system-a-baseline-pipeline)), matching how a reasonably careful real-world user would actually prompt a general-purpose assistant — a zero-shot baseline would be a weaker, less realistic comparison point and would risk the paper reading as having beaten a strawman.
- **System A's failures are qualitatively reviewed, not just counted.** The [failure taxonomy](../README.md#the-problem) (syntax / field / table / temporal / logic) is applied to a sample of System A's specific failures and reported with examples — turning the taxonomy from an assertion into something empirically demonstrated on real baseline output, which is itself one of the paper's secondary contributions.

---

## Reporting Format

The final results section (see the [proposed paper structure](../README.md), Results) should present, in this order:

1. **Primary comparison table** — SVR, FVR, Logic Correctness, CodeBLEU, Latency/Cost — System A vs. System B, aggregate, with 95% CIs and McNemar/Wilcoxon p-values.
2. **Stratified comparison table** (the Simple/Moderate/Complex breakdown above) for SVR, FVR, and Logic Correctness — this is where H4 is directly addressed.
3. **Ablation results table** — all three ablations against the same metrics, aggregate only (stratified ablation results can go in an appendix if space-constrained, since the primary stratified table already carries the main complexity-related claim).
4. **Repair Recovery Rate breakdown** — recovery by attempt number, mean/median attempts used.
5. **Qualitative error analysis** — a small number (4–6) of representative failure examples from System A, annotated against the failure taxonomy, plus 1–2 examples of System B's template-bug failures if any occurred (see [`architecture.md`](architecture.md#the-repair-loop) on why template bugs are logged separately from IR-builder failures).

---

## What Would Falsify Each Hypothesis

Stated explicitly so the evaluation is a genuine test, not a foregone conclusion dressed up as one:

| Hypothesis | Would Be Falsified By |
|---|---|
| **H1** | System B's SVR is not meaningfully higher than System A's SVR (overlapping CIs, non-significant McNemar result), or No-Repair IR (Ablation 1) performs no better than System A on SVR |
| **H2** | System B's FVR is not meaningfully higher than System A's FVR, or No Schema Grounding (Ablation 3) performs comparably to full System B on FVR |
| **H3** | Repair Recovery Rate is well below 50%, or recovery does not show diminishing returns (e.g. attempt 3 recovers as many cases as attempt 2) |
| **H4** | The System B − System A gap on SVR/FVR/Logic Correctness is flat or shrinking across Simple → Moderate → Complex tiers, rather than widening |

A scoped project that finds one or two of these hypotheses *not* supported is still a valid, publishable result — a clean negative or mixed finding on a well-instrumented study (e.g., "schema grounding helps, but agent decomposition specifically does not") is more useful to the field than an uncritical confirmation of all four, and should be written up as such rather than reframed to appear as a clean win.
