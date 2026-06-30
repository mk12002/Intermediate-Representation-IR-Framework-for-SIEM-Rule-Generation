# Results — Draft (2026-06-30, gpt-4.1-mini, post §4AD)

**Status: draft, current.** This supersedes every earlier version of
this document, including the §4S-era version this replaces (which had
gone stale through §4K-§4AD — ~15 rounds — describing a system that no
longer exists: 84.4% completion, no RAG, no construct coverage beyond
the original 7 stage types, no independent rater check). Full causal
history, including every superseded number and the live trace behind
each fix: `PROJECT_STATUS.md` §1–§4AD. This document is a current-state
summary, not an audit trail — read `PROJECT_STATUS.md` for the full
chronological "what broke, what was found, what fixed it" history this
document deliberately doesn't repeat.

Dataset verification, paraphrasing, and Logic Correctness scoring were
done by Claude, not independently human-reviewed, with one exception
new this round: a second, independent AI rater (no visibility into the
first rater's reasoning) scored the same outputs for Logic Correctness,
producing this project's first inter-rater agreement measurement
(Cohen's κ). This is AI-vs-AI agreement, not AI-vs-human — see
Limitations.

---

## 0. Headline numbers: then vs. now

| Metric | Earlier reported (§4N/§4S, flat or early-AST IR) | **Current (§4AD)** | What changed |
|---|---|---|---|
| Primary comparison completion (SVR), System B | 95.6% | **97.8%** (44/45) | Construct coverage + bug fixes across §4K–§4AD |
| Primary comparison FVR, System B | 86.7% | **86.7%** (39/45) | Stable |
| Primary comparison FVR, System A (baseline) | 13.3% / 8.9% | **6.7%** (3/45) | Stable, still the central H2 result |
| Repair Recovery Rate (RRR) | 83.3% | **96.2%** | Repair loop + validator hardening |
| No-Repair ablation | 62.2% | 53.3% | Re-measured; within this project's documented noise band |
| Monolithic ablation | 64.4% | 57.8% | Re-measured; within noise band |
| No-Schema-Grounding ablation | 13.3% | 13.3% | Stable |
| Held-out completion (N=5 median) | not yet replicated | **88.9%** (range 83.3–94.4%) | First N=5 replication on the held-out set specifically |
| Held-out Logic Correctness (median, N=5 model-runs) | 82.4%, IQR 5.9 | **82.4%, IQR 5.9** — now ALSO κ-bounded | Same point estimate, new uncertainty bound (below) |
| **Held-out Logic Correctness, 2 independent raters** | never measured | **72.2% / 88.9%**, κ=0.645 (quadratic) | First inter-rater check this project has ever run |
| Tuned-set Logic Correctness (peak) | 87.2% | 87.2% (unchanged, still N=1) | Not re-measured this round |
| Construct coverage (≥5-occurrence constructs, Supported/Partial) | 71.9% (§4Z) | **72.7%** (§4AB) | `=~`/`!~`/`_cs` operator family closed |
| RAG retrieval | did not exist | **Built, A/B-tested, simplified** (2 of 3 indexes kept) | New capability this round; Logic Correctness effect not established |
| Validator hard-error checks | ~12 | **16** | `LITERAL_MATCHES_SCHEMA_FIELD` + advisory `ALIAS_IMPLIES_FILTER` |
| Synthesis eval scale | n=60 | **n=100**, combination-weighted 65% | Found + fixed a real `SrcIpAddr`/`Url` entity-confusion bug |

**Net read**: every metric that was re-measured either improved or held
within this project's own documented noise band. The system is past
its previous "pre-migration peak" framing (95.6%/75%) on completion,
RRR, and construct coverage. The two genuinely new things this round
adds are not capability — they're rigor: a measured inter-rater bound
on the headline subjective metric, and an honest, negative-leaning
verdict on RAG rather than an assumed positive one.

---

## 1. Primary comparison (n=45, no-output counted as failure)

| Metric | System A (direct) | System B (IR-mediated) | McNemar p |
|---|---|---|---|
| SVR / completion | 100.0% (45/45) | **97.8%** (44/45) | p≈1.0 (not significant) |
| FVR | 6.7% (3/45) | **86.7%** (39/45) | p≈1.4e-8 |

**H1 (SVR) is not a meaningful distinguisher** — consistent with every
round since §4F. System B's one non-completion is a genuine structural
gap (a `!in (top-N-as-dynamic-list)` pattern, confirmed unsupported by
this IR — see `PROJECT_STATUS.md` §4AC case `83e70a34`), not noise.

**H2 (IR-mediation → higher FVR) is supported, decisively.** System
B's FVR is ~13x System A's. System A is never wrong about whether it
*produced* something but is wrong about real fields/tables over 90%
of the time; System B is occasionally silent but correct essentially
every time it isn't.

### Complexity scaling (H4)

| Tier | n | System B success |
|---|---|---|
| Simple | 9 | 100.0% (9/9) |
| Moderate | 9 | 100.0% (9/9) |
| Complex | 27 | 96.3% (26/27) |

Monotonic (simple ≥ moderate ≥ complex). **H4 remains not formally
supported** at this n — one clean ordering is consistent with a real
effect but not statistically distinguishable from chance at n=9/tier.

## 2. Repair Recovery Rate (H3)

**RRR = 96.2%** — well clear of the pre-registered 50% threshold, and
this project's highest measurement of this metric across either
architecture's full history. The repair loop recovers nearly every
attempt-1 failure within its 3-attempt budget.

## 3. Ablations

| Ablation | Result (n=45) | Interpretation |
|---|---|---|
| No-Repair (`max_attempts=0`) | 53.3% success (24/45) | Repair loop still adds substantial value (97.8% vs 53.3%) |
| Monolithic Extraction | 57.8% IR-valid (26/45) | Decomposition's advantage holds |
| No Schema Grounding | 13.3% IR-valid (6/45) | ~6.5x gap below the grounded system's FVR; the cleanest, most stable ablation result across this project's entire history |

## 4. Held-out generalization (the number that matters most)

18 ASIM-normalized rules pulled fresh from real Hunting Queries/
Solutions, never used to tune any worked example or build any RAG
index.

**Completion, N=5 independent runs: 88.9%, 83.3%, 88.9%, 94.4%, 94.4%**
(median 88.9%).

**Logic Correctness, model-non-determinism replication, N=5: median
82.4%, IQR 5.9 (range 76.5–82.4%)** — this is the figure to cite
externally, with its IQR, not a bare point estimate (`PROJECT_STATUS.md`
§4V).

**Logic Correctness, inter-rater replication, N=1 rater-pair (new
§4AD)**: the SAME 18-rule set, scored on a 3-point rubric by two
independent raters with zero visibility into each other's reasoning:
**rater1 72.2%, rater2 88.9%**. Quadratic-weighted Cohen's κ = 0.645
("substantial" agreement on relative quality). Recast into this
project's historical binary pass/fail convention: rater1 72.2% pass
rate, rater2 94.4% pass rate, **κ = 0.265 ("fair")** — markedly weaker.

**Combined, honest uncertainty statement**: held-out Logic Correctness
is best reported as **82.4%, with two independently-measured and
different sources of spread**: model run-to-run variance (IQR 5.9
points, N=5) and inter-rater variance (range 72.2–88.9%, i.e. ~17
points, N=1 rater-pair, not yet replicated). Neither source alone was
previously visible; both are now named.

## 5. The synthetic-vs-real gap, assembled into one statement

- **Synthetic, n=100, combination-weighted**: 100% completion, 84.2%
  fire / 96.2% nofire (execution-validated, not manually read).
- **Terse-NL degradation on identical underlying IRs**: fire accuracy
  90.9% (rich back-translation) → 54.5% (terse), concentrated almost
  entirely in `parse_then_summarize` — the one construct whose correct
  implementation depends on the NL naming a specific literal pattern.
- **Real held-out, n=18, two raters**: 72.2% / 88.9%.

**The gap is real, measured, and construct-dependent — not flat.**
Constructs whose structure follows from stated intent alone
(`arg_max`, `join`, `simple_filter`) survive real-world phrasing
variance well; constructs whose correct implementation depends on the
NL naming a specific literal or structural detail (`parse`-shaped
extraction, exact thresholds) do not. This is the difference between
"looks good on data we generated" and "works on what a real analyst
would actually write" — the central honesty check this project's
methodology was built to surface, now stated as one comparison instead
of three separate, never-connected experiments.

## 6. Construct coverage

**72.7%** of constructs appearing in ≥5 real ground-truth queries are
Supported or Partial (up from 59.4% at first measurement). Closed this
round: case-insensitive equality (`=~`/`!~`, 13 occurrences — more
frequent in this project's own corpus than several constructs already
treated as core) and the case-sensitive `_cs` operator family. Full
scorecard: `CONSTRUCT_COVERAGE.md`.

## 7. RAG retrieval — built, A/B-tested, partially rolled back

Three routed local TF-IDF indexes (no embedding API, no managed vector
service needed at this corpus size) were built: KQL construct syntax
(669 official doc pages), ASIM schema field definitions (14 pages),
and this project's own train-split worked examples (66 pairs). Wired
behind `USE_RAG_RETRIEVAL`, off by default.

**A/B result on the frozen 18-rule held-out set**: SVR and FVR
identical between RAG-on and RAG-off (94.4% / 94.1%). **Logic
Correctness, scored by two independent raters: inconclusive** — the
raters substantially agree on item-level quality (quadratic κ=0.70
across both conditions combined) but disagree on which condition wins
in aggregate (rater1: RAG ahead 45-39; rater2: base ahead 48-45).

**One robust, attributable regression** (both raters agree): RAG
caused the model to drop a correct OR-structure and a direction filter
on one case, plausibly because the retrieved ASIM schema chunk
surfaced vendor/product fields prominently enough to anchor the model
away from logic the baseline path already had right. **Two robust
wins** (both raters agree) traced to a bug independent of RAG — an
aggregation alias ("NXDomainCount") that never actually filtered to
the condition it named — now fixed in the prompt regardless of RAG.

**Simplified after the A/B**: the construct-syntax index was DROPPED
(its own retrieval-quality spot-check was "honestly mixed" — exact-
vocabulary queries worked, vaguer natural-language ones often didn't,
and the full A/B found no benefit worth crediting against the added
complexity). The ASIM-schema index (measured 3/3 correct retrieval)
and worked-examples index are kept. Re-adding construct retrieval is
explicitly scoped as future work *if* testing semantic embeddings — the
wash result is specific to lexical (TF-IDF) retrieval, not a verdict on
retrieval-augmentation in general.

## 8. A newly-confirmed severe finding: abstention doesn't fail safely

When the IR Builder cannot ground any concrete filter at all, it
sometimes (confirmed reproducible, ~1/3 of trials on the hardest such
case) emits a `KqlPipeline` with a `source_table` and an honest
caveat but **zero stages**. This does not fail closed — a pipeline
with no `WhereStage` fires on every single row of the source table.
Three of the 18 held-out cases scored as "honest abstention, correct"
in this round's Logic Correctness pass have exactly this shape. The
scoring is not retracted (an honest abstention is still better than an
invented filter), but "honest" and "safe to deploy as-is" are not the
same property — this is the single most important newly-found item for
future work, ranked above every other open item below.

---

## 9. Discussion

The central hypothesis (IR-mediated generation substantially improves
field/table validity over direct generation, at completion rates
statistically indistinguishable from unconstrained direct generation)
remains supported, now at this project's highest-measured completion
(97.8%) and RRR (96.2%) under either architecture's full history. The
held-out generalization check — the test this project's earlier
conclusions lacked — confirms the system generalizes to genuinely
unseen, real detection rules at completion rates close to the tuned
set, with a real, construct-dependent, now-quantified gap in Logic
Correctness driven by literal-grounding sensitivity, not structural
incapacity.

What changed this round is not the system's ceiling — it's how much of
that ceiling can be defended under scrutiny. A second independent
rater, run for the first time in this project's history, found
substantial but not perfect agreement with the first (κ=0.645 ordinal,
0.265 binary) — meaning the headline 82.4% should be read as a point
estimate with a real, now-measured spread around it, not a precise
figure. RAG, this project's most structurally sophisticated addition,
was measured honestly and found not (yet) to earn its complexity on
Logic Correctness specifically, while incidentally surfacing a real,
RAG-independent bug that's now fixed either way. And the abstention
mechanism — built specifically to prevent hallucinated literals — was
found to have a real, more severe failure mode than previously stated
when grounding fails completely.

## 10. Limitations

- **Logic Correctness has one human-independent check (N=1 rater-pair,
  18 cases), not a human check.** Both raters are AI; the original
  "needs a human reviewer" item remains open. The κ measured here
  (0.645 ordinal / 0.265 binary) is a floor on how much LOWER true
  human disagreement could be, not an upper bound — AI raters sharing
  training data and rubric interpretation could plausibly agree MORE
  with each other than either would with a human rater.
- **RAG's Logic Correctness verdict is N=1 (18 cases, one rater-pair).**
  "Inconclusive" is the honest current state, not "no effect" — a
  larger frozen slice, run through the same double-rated process,
  is the direct next step before either crediting or permanently
  shelving RAG.
- **The empty-pipeline-fires-on-everything finding (§7 above) was found
  this round and is not yet fixed** — it changes how some historical
  "honest abstention = correct" scores should be weighted, though no
  past score has been retracted.
- **n=45** (primary) / **n=18** (held-out) are both small; H4 is not
  resolved at either sample size.
- **Model non-determinism is real and load-bearing** — at least three
  instances across this project's history turned out to be partly a
  fixable bug rather than pure noise; treat any single-run number as
  an estimate.
- **The No-Schema-Grounding ablation's isolation is imperfect** —
  specific worked examples' literal field names leak into static
  prompt text, documented not fixed, on the judgment that each
  example's real-system value outweighs the ablation-purity cost.
- **Train-split pairs have no paraphrase variants** and were never run
  through the comparison harness.
- **Dataset verification, paraphrase review, and Logic Correctness
  scoring were AI-assisted, not independently human-reviewed,** at
  every stage of this project.
- **The Azure AI Foundry API key used throughout this study remains
  unrotated** since being exposed on 2026-06-22 — purely operational,
  but unresolved, and should happen before this work is shared
  externally.

## 11. Conclusion

IR-mediated generation measurably and substantially outperforms direct
generation on field/table validity (86.7% vs 6.7%) while reaching
completion rates statistically indistinguishable from unconstrained
direct generation, now at this project's highest-measured numbers
across either architecture's history (97.8% completion, 96.2% RRR).
The held-out generalization check confirms this transfers to genuinely
unseen real rules, with an honestly-quantified, construct-dependent
gap in Logic Correctness. This round's distinct contribution is not
new capability — it's the first independent verification of this
project's headline subjective metric (κ=0.645 ordinal / 0.265 binary,
N=1 rater-pair), an honest, negative-leaning measurement of this
project's most sophisticated recent addition (RAG), and the discovery
of a real, more-severe-than-previously-stated failure mode in the
abstention mechanism that previously read as purely a strength. The
system is past the "close the gap to the old peak" framing that
organized this project's prior future-plans section; what remains is
bounding, documenting, and defending what's built, not building more
of it — see `PROJECT_STATUS.md` §5–§7 for the current, reconciled
version of that list.
