# Results — Draft (2026-06-23, gpt-4.1-mini, post §4J)

**Status: draft, current.** This supersedes every earlier version of this
document — the original 2026-06-22 draft (Qwen3.5 4B/2B) measured an
infrastructure bug more than model capability, and four intermediate
rewrites (after §4C, §4E, §4G, §4H) were each superseded by further
bugfixes and architecture work in the same session. Full causal history:
`PROJECT_STATUS.md` §1.4 and §4–§4I. Numbers below are from `gpt-4.1-mini`
via Azure AI Foundry, after the schema-grounding fix, eight validator
fixes, three IR schema extensions (`FilterGroup`, `JoinStage` +
`compare_to_join_field`, `percentile`, `additional_aggregations` +
`make_set`/`make_list`), a self-inflicted prompt bug found and fixed
mid-session (§4H), and a repair-loop off-by-one bug found and fixed in the
same session (§4I — the loop's final rebuild was never itself validated
before giving up, silently discarding valid IRs). Dataset verification,
paraphrasing, and Logic Correctness scoring were done by Claude at the
user's explicit instruction, not independently human-reviewed — see
Limitations.

---

## Abstract (draft)

Direct LLM generation of KQL from natural-language detection descriptions
is known to hallucinate syntax and fields. This project tests whether an
explicit, ASIM-schema-validated Intermediate Representation (IR), combined
with a 2-agent extraction pipeline and a bounded repair loop, reduces that
hallucination relative to direct generation.

A first evaluation round (Qwen3.5 4B/2B, local) appeared to falsify the
hypothesis — but was found to be measuring a bug: the repair loop was
silently handing the IR Builder an empty field list on nearly every call,
for both systems, defeating schema grounding by accident. After fixing
this, eight further validator/compiler defects across the session, moving
to a more capable model (`gpt-4.1-mini`), and three rounds of IR
architecture extension, the result is unambiguous: on the same 45-record
held-out test set, System B (IR-mediated) reaches **95.6% completion** and
**93.3% field/table validity**, against System A's (direct generation)
100% completion but only **11.1% field/table validity** (McNemar
p≈3.3e-9) — an 8x gap. The repair loop recovers **91.7%** of attempt-1
failures, well clear of the pre-registered 50% threshold — and, as of this
session's last two rounds, actually validates every attempt it makes; a
previously-undetected off-by-one in the loop had been silently discarding
the final, often-valid, repair attempt on any sequence that used its full
budget. A second, separate bug — a specific sentence-shape ambiguity that
was causing the model to misjudge the scope of an "or" in an enumerated
list — was traced and fixed in the most recent round, the same way the
off-by-one was: by reading the actual ground truth and natural-language
text side by side until the mechanism, not just the symptom, was visible. Three IR schema extensions built during this session —
`FilterGroup` (OR-composition), `JoinStage` with `compare_to_join_field`
(correlation, baseline-vs-current, exclusion lookups), and
`additional_aggregations` with `make_set`/`make_list` (multiple summarize
columns computed together — count plus evidence plus activity-window
timestamps, the shape most real ASIM analytic rules actually take) —
close most, not all, of a separately identified expressiveness gap: 53.3%
of the test set's ground truth needs constructs (joins, multi-stage
aggregation, or boolean OR) beyond a flat AND-only IR. Restricting Logic
Correctness scoring to the IR-expressible subset (the only fair
comparison, since the rest is architecturally out-of-scope) gives
**15/20 = 75%** — the highest of six re-scoring rounds in this session
(reached twice, in consecutive rounds, on the same 5 named failure
causes), and not yet independently verified by a second reviewer.

A secondary finding, confirmed and then partly *explained* this session:
`gpt-4.1-mini` via Azure AI Foundry is **not** perfectly deterministic at
temperature=0 — repeated runs on identical code and input have differed
by up to 7 points. Tracing two such spreads to ground found neither was
*purely* model noise: one was a self-inflicted prompt-wording bug (an
analogy the model was misreading as an invented operator name); the other
was the repair-loop off-by-one above, which made completion *look* noisier
than it really was by occasionally discarding a valid result outright. The
lesson generalizes: not every run-to-run swing in this kind of evaluation
is irreducible non-determinism — some are real, traceable, fixable bugs
that happen to look like noise until investigated.

---

## 1. Results

### 1.1 Methodology notes (read before the numbers)

- **IR-expressiveness stratification.** Checking the ground truth directly:
  **24/45 (53.3%)** of the test set needs a join, multi-stage aggregation,
  or genuine boolean OR that the *original* flat AND-only IR could not
  represent at all. Three constructs added during this session —
  `FilterGroup` (§4C, OR-composition), `JoinStage` + 
  `compare_to_join_field` (§4E, correlation/baseline/exclusion), and
  `additional_aggregations` (§4I, multi-column summarize) — now cover part
  of that 24 (the third mainly improves *how completely* in-scope records
  match ground truth, not the in/out-of-scope boundary itself, since it
  doesn't add a new control-flow construct). Completion rate below is
  reported for all 45 records (the fair comparison against System A, which
  always produces *something*), but **Logic Correctness is scored only on
  the 21 GT-structurally-in-scope records** — scoring the other 24 against
  a rubric the IR cannot structurally satisfy for them would measure how
  gracefully the system degrades, not whether it's correct. **Known
  staleness in this boundary**: the exclusion criteria were written before
  `FilterGroup`/`JoinStage` existed and have not been revisited since; some
  of the 24 excluded records may now be expressible with the constructs
  this session added. Not yet re-audited — see Limitations.
- **Model non-determinism, now partly explained, not just measured.** Seven+
  full 45-record runs of `eval/run_comparison.py` were executed against
  `gpt-4.1-mini` across this session; completion has ranged from 62% to
  93.3%. Most of that range reflects genuine session-over-session
  improvement (bugs fixed, architecture added), but within single rounds,
  two separate variance spreads turned out to be *partly* real, traceable
  bugs rather than pure model noise: a self-inflicted prompt-wording bug
  (§4H) and a repair-loop off-by-one that silently discarded valid results
  (§4I). The honest position: some variance is genuine model
  non-determinism, but treat any single number as provisional until a
  same-code re-run confirms it, because some of what looks like noise is a
  bug waiting to be found.
- **Six rounds of Logic Correctness re-scoring, same rubric, same single
  rater:** 60% (§4B/§4C, n=15) → 52.6% (§4E, n=19) → 60% (§4F, n=20) → 70%
  (§4G, n=20) → 75% (§4H, n=20) → 75% (§4I, n=20, same 5 named failure
  causes) → **75% (§4J, n=20, current — same number a third time, but a
  different composition: the §4H/§4I residual bug is now fixed, and a
  new, smaller, different issue appeared in its place)**. Each increase
  after §4C has a named, traceable cause (a specific bug fixed, confirmed
  by re-checking the exact case) rather than being a re-roll of the same
  dice — this distinguishes the upward trend from simple non-determinism,
  but it is still one AI rater throughout.

### 1.2 Primary comparison (n=45, no-output counted as failure)

| Metric | System A (direct) | System B (IR-mediated) | McNemar p |
|---|---|---|---|
| SVR / completion | 100.0% | **95.6% — highest of the study** | p≈0.5 (not significant) |
| FVR | 11.1% | **93.3% — highest of the study** | p≈3.3e-9 |

For System B, SVR and FVR sit close together (95.6% vs 93.3%) — most
syntactically-valid completions are also fully field-valid; the small gap
is the residual field/output-projection issues the schema validator
doesn't catch before compilation.

**H1 (SVR) is not a meaningful distinguisher**, as in every round since
§4F. McNemar's test on completion rate is not significant (p≈0.5) —
System B's completion rate is statistically indistinguishable from System
A's unconditional 100%. This is a qualitatively different result from the
session's early rounds, where System B's completion rate was
significantly *below* System A's.

**H2 (IR-mediation → higher FVR) is supported, decisively.** System B's
FVR is 8x System A's, with the McNemar contingency almost entirely
one-directional. System A is never wrong about whether it *produced*
something (100% completion) but is wrong about whether that something
references real fields/tables nearly 9 times out of 10; System B is
occasionally silent (4.4% non-completion) but correct essentially every
time it isn't.

### 1.3 Repair Recovery Rate (H3)

**RRR = 91.7%** in the current run — well clear of MASTER_PLAN's
pre-registered 50% threshold (prior: 46.9%/56.8% in §4C, 70.3–72.5% in
§4E, 80.8–88.5% across §4F–§4H, 82.6% in §4I). The repair loop now also
actually validates every build it makes, including the final one on any
sequence that uses its full repair budget — a previously-undetected off-by-one
(§4I) had been silently discarding that last attempt's output unchecked,
even when it was fully valid. The trend across the session is not noise:
each jump corresponds to a named fix that either reduced first-attempt
failures, improved the repair prompt's own guidance, or — this round —
fixed the loop itself.

### 1.4 Complexity scaling (H4)

| Tier | n | System B success (current run) |
|---|---|---|
| Simple | 9 | 88.9% (8/9) |
| Moderate | 9 | 88.9% (8/9) |
| Complex | 27 | 92.6% (25/27) |

Closer to monotonic-by-difficulty than the session's early rounds (which
saw the moderate tier swing 0–44% across repeated runs), though the
ordering across tiers is still not cleanly monotonic. **H4 remains not
cleanly supported**, but the per-tier gap has narrowed substantially as
completion rate overall rose — at n=9 per tier, some of the remaining
non-monotonicity is plausibly just small-sample noise rather than a real
effect.

### 1.5 Ablations

| Ablation | Result (n=45) | Interpretation |
|---|---|---|
| 1. No-Repair (`max_attempts=0`) | 48.9% success (22/45) | Repair loop still adds substantial value (95.6% vs 48.9%) — roughly half of completions still need at least one repair attempt even at this prompt-quality level. **Note on this number's own history**: this ablation calls the same repair-loop function with a reduced budget; after the §1.3 off-by-one fix, the call had to change from `max_attempts=1` to `max_attempts=0` to keep measuring true zero-repair performance — the loop's old bug had been making `max_attempts=1` silently behave like a zero-repair measurement by accident, so this number is unchanged in spirit, just now correctly isolated. |
| 2. Monolithic Extraction | 64.4% IR-valid (29/45) | Below the full two-agent pipeline (95.6%) — decomposition's advantage has held, and grown, across every round this session. |
| 3. No Schema Grounding | **11.1% IR-valid (5/45)** | Grown from the first-ever non-zero result (6.7%, §4H) to 11.1–13.3% (§4I/§4J, within noise of each other, both worth treating as the same reading). Traced directly: a worked example introduced in §4I (`additional_aggregations`/`make_set`) put more literal field names — `Url`, `TimeGenerated`, and the aliases `EventStartTime`/`EventEndTime` — into the *static* system prompt, on top of §4H's `DnsResponseCodeName`. This round's own fix (a sentence-shape disambiguation) added no new field names, so the leak is unchanged in kind, just at this round's measured rate. Both leaks share the same mechanism: a worked example's concrete field names are present even when the dynamic schema field list is stripped by this ablation. Still an 8x gap vs. the grounded system's 93.3% FVR — schema grounding's necessity is not in question, but this ablation's isolation has now degraded twice, tracking directly with the session's two most effective prompt-engineering techniques. Flagged for a decision before a third worked example compounds it further (see Limitations). |

### 1.6 Logic Correctness — the binding result, scored on the IR-expressible subset

Of 43 System B successes on the scored run, 20 sit in the 21
GT-structurally-in-scope records (the ground truth needs no join, no real
OR, no multi-stage aggregation `SecurityIR` cannot represent); the other
23 successes are schema-valid *simplifications* of detections the IR
cannot fully represent and are excluded from this rubric for the reason
given in §1.1. All 20 were scored against the 3-point rubric (event
type/table correct; comparison direction not inverted; aggregation/
grouping matches intent — all three required): **15/20 = 75% — the same
number as the prior two rounds, but with a different, smaller residual
failure than either**.

Of the 5 that failed:
- **4 are a confirmed information ceiling, not a model or architecture
  failure** — unchanged from the prior two rounds. Checking the actual NL
  text behind each: the `-original` paraphrase variant for `61988db3`
  ("malware hidden in the recycle bin"), `b35f6633` ("the top 25 noisiest
  clients"), `a59ba76c` ("multiple server errors from a single source"),
  and `813ccf3b` ("requests... that exhibit multiple user agents") all
  genuinely omit the technical detail or threshold number the ground
  truth specifies — no prompt or architecture change can recover
  information that was never in the input. This mirrors the
  `sop`/`original` gap investigated and ruled out in §4C.
- **1 is a real, addressable residual, but a different one than the prior
  two rounds.** The FilterGroup/OR confusion that had been recurring on
  `61988db3-sop` across §4H/§4I was traced this round to its actual
  mechanism — a sentence shape, "(X1, X2, ..., or Xn) is/does Y," where
  the enumerated list's "or" was being read as scoping the unrelated
  AND-condition that follows it too — and fixed; `61988db3-casual` now
  passes cleanly, confirmed by 6/6 standalone re-runs both before the
  full comparison and within it. `61988db3-sop` still fails, but for a
  new and narrower reason: a truncated LOLBin enumeration (2 of 7 names
  present). The AND/OR structure itself is correct this time — this is a
  list-completeness issue, not a logic-inversion one, and has only been
  observed once so far.

**This 75% reflects five fixed, named bugs since the 60% reported earlier
in this session**, each independently confirmed live before and after: an
inverted-logic detection (`sdelete` evasion, §4G), a missing
outcome-condition filter on a correctly-typed DNS detection (§4H), a
Src/Dst directional field mix-up that an earlier draft had misdiagnosed as
"over-grouping" (§4H), a self-inflicted prompt-wording bug that was
causing intermittent AND→OR logic corruption across several cases (§4H),
and a specific sentence-shape ambiguity that was causing a related but
distinct AND→OR confusion on one case across two further rounds (§4J).
It is not yet 90%, it is not yet independently verified, and it still
excludes 53.3% of the dataset that needs correlation/multi-stage logic —
but the trajectory is no longer flat, and each increment has a specific,
checkable cause rather than being attributable to re-rolling the same
single-rater dice. Landing at 75% three rounds in a row, each time via a
different residual cause, is itself worth noting: it may mean this
dataset/architecture/rater combination is converging on a real ceiling
near 75%, not just stalling.

---

## 2. Discussion

**The central hypothesis is supported at this model scale, and the margin
has grown every round this session, not just once.** Three things were
true simultaneously at the start of this work and are easy to conflate:
the original Qwen3.5 result was dominated by an infrastructure bug, not
model capability; fixing that bug and moving to a more capable model both
mattered (a Qwen3.5 re-test with the same bug fix reached only 1/10 on a
10-case sample, vs. gpt-4.1-mini's 8/10); and even after every fix,
**IR-expressiveness and model non-determinism remain real, separate
constraints — though both have narrowed substantially since the
session began.**

### What was found and fixed this session, in causal order

1. **Schema-grounding empty-list fallback** (the dominant original bug) —
   `extraction.likely_event_type` is free text and almost never matches a
   schema key, so the IR Builder got zero fields almost every call, for
   both systems, throughout the original run.
2. **Threshold-without-aggregation, degenerate-threshold, and three
   `output_fields`/aggregation-field validator gaps** — each let
   schema-valid-looking IRs through that were either meaningless (a
   threshold with no left-hand side) or silently hallucinated (an
   unchecked `project` field, an unchecked aggregation field).
3. **Paraphrase-style hypothesis, investigated and ruled out (§4C).** The
   apparent "imperative phrasing scores better" pattern was actually a
   missing-information problem: `sop`-style paraphrases inject technical
   specifics absent from terser `original`-style ground-truth descriptions.
   No phrasing transformation can recover information never in the input.
4. **`SecurityIR` extended with `FilterGroup`** (§4C, OR-composition) and
   **`JoinStage` + `compare_to_join_field`** (§4E, correlation/
   baseline-vs-current/exclusion) — the two largest architecture additions
   of the session, each confirmed working on a live, previously-impossible
   case.
5. **A constraint-traceability check** (§4F) catching schema-valid
   threshold values that silently drift from what the description
   specifies — deliberately conservative (fires only on an unambiguous
   single number) to avoid false positives.
6. **Targeted prompt fixes for specific, named confusions** (§4F–§4H):
   event-type disambiguation (DNS/HTTP/process surface-wording traps),
   a disguised-tool-evasion worked example (fixed the recurring `sdelete`
   inverted-logic bug), Src/Dst directional field selection, and tying
   vague outcome words ("error", "failure") to the event type's actual
   result-encoding field.
7. **A genuine new aggregation primitive — `percentile`** (§4H) — and, in
   the same investigation, a precise re-scoping of what's *still* missing
   for percentile-of-aggregates patterns (a second aggregation pass plus
   derived/computed fields, confirmed by live evidence, not yet built).
8. **A self-inflicted prompt bug, found and fixed mid-session (§4H)**: an
   earlier worked example's "has_all-style" phrasing was being read by the
   model as a literal, invented operator name, causing intermittent parse
   failures and logic corruption. The single highest-leverage fix of the
   session by completion-rate impact — confirmed by 6/6 clean re-runs of
   the two previously flakiest cases afterward.
9. **`additional_aggregations` + `make_set`/`make_list`** (§4I) — most
   real ASIM rules compute several summarize columns together (a count to
   threshold on, plus evidence, plus an activity-window timestamp), which
   the IR had no way to express until this round. Confirmed live to
   generalize well beyond its one worked-example target case to four other
   ground-truth pairs, unprompted, each rendering output close to its
   actual ground truth's shape.
10. **A repair-loop off-by-one, found while investigating a completion-rate
    dip (§4I)**: `run_with_repair`'s loop bound meant the *final* rebuild
    on any repair sequence that used its full budget was never itself
    validated before giving up — a fully valid IR was confirmed live to
    have been silently discarded this way. Fixed without changing total
    model-call counts (verified against every pre-existing test's exact
    call-count assertions). A second-order fix followed: the No-Repair
    ablation had been unknowingly relying on this exact bug to approximate
    zero-repair semantics, and needed its own correction once the loop
    itself was fixed correctly.
11. **The §4H/§4I residual `61988db3` confusion, traced to an actual
    mechanism and fixed (§4J)**: a specific sentence shape, "(X1, X2, ...,
    or Xn) is/does Y," where the model was extending an enumerated list's
    "or" scope onto an unrelated AND-condition written right after it.
    The existing FilterGroup-vs-AND guidance (§4H) addressed the general
    "don't wrap required-together conditions in an OR" rule but not this
    specific grammatical trap. Confirmed via 6/6 clean standalone re-runs.

### What this means for the central claim

Schema grounding has a real, but increasingly imperfectly isolated, effect
(Ablation 3: 0.0% in every round through §4G, 6.7% in §4H, 11.1–13.3% since
— both non-zero readings traced directly to literal field names in worked
examples living in static prompt text, not to a breakdown of the grounding
mechanism itself). The deterministic template compiler genuinely
eliminates syntax and field hallucination conditional on the IR validating.
The repair loop now recovers the large majority of attempt-1 failures
(91.7%, after the loop itself was confirmed to actually validate
everything it builds), comfortably past the pre-registered threshold. And
Logic Correctness, scored honestly on only the cases the architecture can
represent, has risen from 60% to 75% across seven traced, bug-by-bug
rounds, landing at 75% three times in a row — twice on the same 5 named
causes, then a third time after fixing one of those causes and surfacing a
smaller one in its place — real, cumulative progress, not a single lucky
run, though still short of a number that would support unsupervised
deployment, and the dataset's other half (correlation-style and
multi-stage detections) is only partially represented by this IR even now.

---

## 3. Limitations

- **n=45** is small; per-tier CIs are wide and H4 is not cleanly resolved
  at this sample size, though the spread has narrowed materially since
  earlier rounds (0–44% on the moderate tier → 88.9% across the lower tier
  this round).
- **Model non-determinism is real but partly conflated with bugs.** This
  session's most important methodological lesson, confirmed three times: a
  3-run spread that looked like ordinary model noise (91.1%/84.4%/86.7%)
  turned out to be caused, in part, by a specific, fixable prompt-wording
  bug (§4H); a separate completion dip after the next round's changes
  turned out to be partly explained by a repair-loop bug that was
  discarding valid results (§4I); and a recurring single-case failure that
  looked like ordinary model flakiness turned out to be a specific,
  traceable sentence-shape ambiguity (§4J). Future evaluators of this kind
  of system should not assume run-to-run variance is irreducible before
  checking for a root cause.
- **Logic Correctness (75%, n=20) is scored by one rater (Claude), with
  no second reviewer and no inter-rater reliability check across any of
  the seven rounds this session.** This is still the single most important
  verification gap before this number should be cited externally — the
  trend is well-evidenced and traceable (75% reached three rounds in a
  row, via three different underlying compositions), but trend-with-one-rater
  is not the same claim as a verified absolute number.
- **53.3% of the dataset is excluded from the Logic Correctness
  denominator** because the IR cannot represent it at all (joins beyond a
  single correlation/baseline pattern, true multi-stage aggregation,
  percentile-of-aggregates). This is an honest scoping choice, not a
  hidden one, but it means this draft makes no claim about overall
  dataset-wide correctness — only about the subset the architecture is
  designed to handle. **This boundary itself is now slightly stale**: the
  exclusion criteria predate `FilterGroup` and `JoinStage`'s existence and
  have not been re-audited against what those constructs can now express;
  some of the 24 excluded records may be reclassifiable as in-scope.
- **The No-Schema-Grounding ablation's isolation has degraded twice now,
  not once** (§1.5) — two worked examples' literal field names leak into
  the static prompt text regardless of the dynamic field list the
  ablation strips, growing the ablation's reading from 0.0% to 6.7% to
  11.1–13.3% across §4G→§4H→§4I/§4J (§4J's own fix added no new field
  names, so this round's reading is unchanged in kind from §4I's).
  Documented, not fixed, on the judgment that the real-system fix each
  example enabled outweighs the ablation-purity cost; flagged for a
  second opinion in `PROJECT_STATUS.md` §5 before a third worked example
  compounds it further.
- **Train-split pairs have no paraphrase variants** and were never run
  through the comparison harness — this evaluation covers the 15-pair test
  split only, per MASTER_PLAN's Phase 4 scope.
- **Dataset verification, paraphrase review, and Logic Correctness scoring
  were AI-assisted, not independently human-reviewed,** at every stage of
  this project to date.

---

## 4. Conclusion

At this model scale, after fixing every bug found across this session and
extending the IR three times (OR-composition, then correlation/baseline
joins and a percentile primitive, then multi-column summarize for
evidence-collection patterns), IR-mediated generation measurably and
substantially outperforms direct generation on field/table validity (93.3%
vs 11.1%, an 8x gap) while reaching a completion rate statistically
indistinguishable from unconstrained direct generation (95.6% vs 100%,
p≈0.5) — both the highest readings of the entire study, and a
qualitatively different result from the session's early rounds. The
repair loop clears its pre-registered recovery threshold by a wide margin
(91.7% vs. the 50% bar), and — since the prior round — actually checks
every attempt it makes, after a previously-undetected bug was found
silently discarding valid results. Restricted to the subset of detections
the IR can structurally represent, 75% are judged logically correct on
inspection, up from 60% at the start of this session's bugfixing, via
independently-traced fixes rather than one lucky run, and landing at 75%
three rounds in a row — twice on the same named causes, then a third time
after fixing one of those causes (a specific sentence-shape ambiguity
that had been causing a model to misjudge an "or"'s grammatical scope)
and surfacing a smaller, different residual in its place — the clearest
sign yet that this number reflects real progress and a possible
architectural ceiling, not re-rolled noise. The honest next steps are, in
order: get independent verification of the Logic Correctness figure (now
arguably more urgent given the trend's clarity, not less); build the
percentile-of-aggregates and derived-field construct that the current
architecture confirmedly cannot express; investigate the newly-surfaced
LOLBin-list-truncation issue on `61988db3-sop` (one occurrence so far, not
yet enough to characterize); decide how to handle the No-Schema-Grounding
ablation's now-twice-degraded isolation before a third worked example
compounds it; re-audit the IR-expressiveness exclusion boundary against
the constructs added since it was first drawn; and re-run the full
comparison enough times to replace this session's still-single-run
headline (95.6%) with a stable multi-run average, given that not every
past run-to-run swing has turned out to be irreducible model noise.
