"""A human scoring pass for Logic Correctness, on the same 18 base-
condition outputs the two AI raters already scored (PROJECT_STATUS.md
§4AC/§4AE) — the one check this project has never run. Two AI raters
agreeing (κ=0.645 ordinal) is real evidence, but they can share a
systematic bias a human wouldn't; this script makes it cheap to find
out whether they do.

Rubric (the same 3-point scale used throughout this project):
  1. Event type/table correct — right ASIM table for what the NL describes?
  2. Comparison/direction not inverted — any filter/threshold/join
     direction that matters is correct, not backwards?
  3. Aggregation/grouping matches intent — if the NL implies counting/
     grouping/a report, does the query's aggregation (or its deliberate
     absence) match what was actually asked?
Score each as met (1) or not (0), sum to 0-3. An honest, correctly-
abstained query (right table, invents nothing, caveats explain the
gap) scores 3/3 even when it's far simpler than ground_truth_kql —
judge against what the NL actually says, not against reproducing
ground truth's exact mechanism.

Usage:
    python eval/score_logic_correctness.py            # score interactively
    python eval/score_logic_correctness.py --kappa     # compute 3-way kappa
                                                        # (after scoring)

Output: eval/results/human_logic_correctness_scores.json
"""
import json
import sys
from pathlib import Path

_RAW = Path("eval/results/rag_ab_raw.json")
_AI_SCORES = Path("eval/results/rag_ab_logic_correctness_scoring.json")
_OUT = Path("eval/results/human_logic_correctness_scores.json")


def score_interactively():
    data = json.loads(_RAW.read_text(encoding="utf-8"))
    cases = data["base"]  # the no-RAG condition — this project's main held-out number

    existing = {}
    if _OUT.exists():
        existing = json.loads(_OUT.read_text(encoding="utf-8"))
        print(f"Resuming — {len(existing)}/{len(cases)} already scored.\n")

    for case in cases:
        rid = case["rule_id"]
        if rid in existing:
            continue
        print("=" * 70)
        print(f"CASE {rid}")
        print("-" * 70)
        print("NL:", case["nl"])
        print("-" * 70)
        print("GROUND TRUTH KQL (often far more sophisticated than needed — judge")
        print("against the NL above, not against reproducing this exactly):")
        print(case["ground_truth_kql"][:1500])
        print("-" * 70)
        print("GENERATED KQL:")
        print(case["kql"] if case["success"] else f"(build failed: {case.get('reason', 'unknown')})")
        print("-" * 70)
        while True:
            raw = input("Score 0-3 (or 's' to skip, 'q' to save+quit): ").strip().lower()
            if raw == "q":
                _OUT.write_text(json.dumps(existing, indent=2), encoding="utf-8")
                print(f"Saved {len(existing)}/{len(cases)} to {_OUT}. Resume any time.")
                return
            if raw == "s":
                break
            if raw in ("0", "1", "2", "3"):
                existing[rid] = int(raw)
                break
            print("  enter 0, 1, 2, 3, 's' to skip, or 'q' to save and quit")
        print()

    _OUT.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"Done — {len(existing)}/{len(cases)} scored. Saved to {_OUT}.")
    print("Run with --kappa to compute the three-way inter-rater agreement.")


def compute_kappa():
    from sklearn.metrics import cohen_kappa_score

    if not _OUT.exists():
        print(f"No human scores yet — run without --kappa first to score cases.")
        sys.exit(1)

    human = json.loads(_OUT.read_text(encoding="utf-8"))
    ai = json.loads(_AI_SCORES.read_text(encoding="utf-8"))["per_case"]

    common_ids = [rid for rid in human if rid in ai]
    if len(common_ids) < 5:
        print(f"Only {len(common_ids)} cases scored by all three raters — score more before computing kappa.")
        return

    h = [human[rid] for rid in common_ids]
    r1 = [ai[rid]["rater1"]["base"] for rid in common_ids]
    r2 = [ai[rid]["rater2"]["base"] for rid in common_ids]

    print(f"n cases scored by all three raters: {len(common_ids)}\n")
    for name, scores in [("human", h), ("rater1 (AI)", r1), ("rater2 (AI)", r2)]:
        print(f"{name:14s}: mean {sum(scores)/len(scores):.2f}/3")
    print()
    for (name_a, a), (name_b, b) in [
        (("human", h), ("rater1", r1)),
        (("human", h), ("rater2", r2)),
        (("rater1", r1), ("rater2", r2)),
    ]:
        print(f"{name_a} vs {name_b}: quadratic-weighted kappa = {cohen_kappa_score(a, b, weights='quadratic'):.3f}, "
              f"raw agreement = {sum(1 for x, y in zip(a, b) if x == y) / len(a):.3f}")


if __name__ == "__main__":
    if "--kappa" in sys.argv:
        compute_kappa()
    else:
        score_interactively()
