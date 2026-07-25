"""Clarification before/after on real data (PROJECT_STATUS.md §4AG) —
Phase A (fully automated, no human needed) + the mechanical half of
Phase B (deterministic question generation + an automatic false-
positive pre-screen), run against eval/clarification_eval_set.json
(50 fresh, complexity-stratified, never-tuned-against real rules).

What this measures WITHOUT a human in the loop:
  - Baseline completion/FVR/abstention rate on real under-specified
    input (clarification OFF) -- the question "how often does the
    system under-deliver on real input" needs no human at all, since
    abstention/caveats ARE the system's own signal that something was
    missing.
  - The gap-checker's questions for every case that has one (Phase B's
    deterministic half) -- generating a question needs no answer.
  - An automatic clarification-PRECISION pre-screen: for each gap, does
    the NL text already contain the kind of value being asked about
    (a number for a threshold/time-window gap)? If so, the gap is very
    likely a false positive (the IR Builder already had the info and
    didn't use it) -- a real, if partial, automatic check, not a
    substitute for the full precision measurement a human read would
    give, but a meaningful one that needs no answers at all.

What this does NOT measure (needs the human step from here):
  - Resolution rate: does ANSWERING a gap actually produce a correct
    query? Answers must come from a human (PROJECT_STATUS.md's own
    "missing vs. ambiguous" framing) or this project's own ground-
    truth would leak into the test. The output file's `clarification`
    block has a `human_answer: null` slot for exactly this -- fill it
    in and re-run with --resolve to complete the measurement.

Usage:
    python eval/run_clarification_eval.py              # Phase A + gap generation
    python eval/run_clarification_eval.py --resolve     # Phase C: after answers are filled in
"""
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, ".")

from eval.metrics import field_validity_rate, syntax_validity_rate
from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.clarification import find_gaps, resolve_clarification
from src.pipeline.system_b import run_system_b

ASIM_SCHEMA = json.loads(open("data/schema/asim_field_reference.json", encoding="utf-8").read())
_KNOWN_FIELDS = {f for event in ASIM_SCHEMA.values() for f in event["fields"]}
_CASES_PATH = Path("eval/clarification_eval_set.json")
_OUT_PATH = Path("eval/results/clarification_eval_raw.json")


def _looks_already_grounded(gap, nl: str) -> bool:
    """A cheap, automatic false-positive pre-screen: a threshold/time-
    window gap is suspicious if the NL already contains a number (the
    IR Builder had something to work with and still asked/omitted).
    Not a substitute for a human precision read -- a number in the NL
    doesn't guarantee it's THE right number for THIS gap -- but a real
    signal needing no answers."""
    if gap.kind in ("missing_threshold", "missing_time_window"):
        return any(ch.isdigit() for ch in nl)
    return False


def phase_a_and_b():
    cases = json.loads(_CASES_PATH.read_text(encoding="utf-8"))
    extraction_agent = ExtractionAgent()
    ir_builder = IRBuilderAgent(use_rag=False)

    results = []
    for i, case in enumerate(cases):
        nl = case["nl_description"]
        r = run_system_b(nl, ASIM_SCHEMA, extraction_agent, ir_builder, max_attempts=3)
        record = {
            "rule_id": case["rule_id"],
            "complexity_tier": case["complexity_tier"],
            "nl": nl,
            "ground_truth_kql": case["ground_truth_kql"],
            "baseline_success": r.success,
            "baseline_kql": r.kql,
            "baseline_abstained": bool(r.ir and r.ir.abstained),
            "baseline_caveats": list(r.ir.caveats) if r.ir else [],
        }
        if r.success and r.ir is not None:
            gaps = find_gaps(r.ir)
            record["gaps"] = [
                {
                    "caveat_text": g.caveat_text,
                    "question": g.question,
                    "kind": g.kind,
                    "default": g.default,
                    "affected_field": g.affected_field,
                    "looks_already_grounded_in_nl": _looks_already_grounded(g, nl),
                    "human_answer": None,  # <-- fill this in, then re-run with --resolve
                }
                for g in gaps
            ]
        else:
            record["gaps"] = []
        results.append(record)
        print(f"[{i+1}/{len(cases)}] {case['rule_id']} ({case['complexity_tier']}): "
              f"success={r.success} abstained={record['baseline_abstained']} gaps={len(record['gaps'])}")

    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    _summarize(results)


def _summarize(results):
    n = len(results)
    by_tier = {}
    for r in results:
        by_tier.setdefault(r["complexity_tier"], []).append(r)

    print("\n=== Phase A: baseline (clarification OFF), real data ===")
    completed = [r for r in results if r["baseline_success"]]
    # SVR/FVR computed on NON-ABSTAINED completions only -- an abstained
    # pipeline's "// ABSTAINED ..." comment is intentionally not valid
    # KQL (compiler.py refuses to emit a runnable query on purpose,
    # §4AE), so scoring it as a syntax failure would conflate "working
    # as designed" with a real defect.
    non_abstained = [r for r in completed if not r["baseline_abstained"] and r["baseline_kql"]]
    print(f"overall: n={n}  completion={len(completed)/n*100:.1f}%  "
          f"abstained={sum(1 for r in completed if r['baseline_abstained'])}/{len(completed)}  "
          f"SVR(non-abstained)={syntax_validity_rate([r['baseline_kql'] for r in non_abstained])*100:.1f}%  "
          f"FVR(non-abstained)={field_validity_rate([r['baseline_kql'] for r in non_abstained], _KNOWN_FIELDS)*100:.1f}%")

    has_gap = [r for r in results if r["gaps"]]
    print(f"under-specification rate (>=1 gap found): {len(has_gap)}/{n} = {len(has_gap)/n*100:.1f}%")
    fully_abstained = [r for r in results if r["baseline_abstained"]]
    print(f"total abstention rate: {len(fully_abstained)}/{n} = {len(fully_abstained)/n*100:.1f}%")

    all_gaps = [g for r in results for g in r["gaps"]]
    suspicious = [g for g in all_gaps if g["looks_already_grounded_in_nl"]]
    print(f"\ngap-checker questions generated: {len(all_gaps)}")
    print(f"automatic false-positive pre-screen flagged: {len(suspicious)}/{len(all_gaps)} "
          f"({len(suspicious)/len(all_gaps)*100:.1f}% if any)" if all_gaps else "")

    print("\nstratified by complexity tier:")
    for tier, rows in sorted(by_tier.items()):
        tn = len(rows)
        tc = sum(1 for r in rows if r["baseline_success"])
        tg = sum(1 for r in rows if r["gaps"])
        print(f"  {tier:10s} n={tn:3d}  completion={tc/tn*100:5.1f}%  under-specified={tg/tn*100:5.1f}%")

    print(f"\nFull per-case data + questions saved to {_OUT_PATH}.")
    print("Fill in 'human_answer' for each gap, then run with --resolve to complete Phase C's automatable half.")


def phase_resolve():
    if not _OUT_PATH.exists():
        print("Run without --resolve first to generate the question set.")
        sys.exit(1)
    results = json.loads(_OUT_PATH.read_text(encoding="utf-8"))
    cases_by_id = {c["rule_id"]: c for c in json.loads(_CASES_PATH.read_text(encoding="utf-8"))}
    extraction_agent = ExtractionAgent()
    ir_builder = IRBuilderAgent(use_rag=False)

    resolved_count = answered_any_count = 0
    for r in results:
        answers = {g["caveat_text"]: g["human_answer"] for g in r["gaps"] if g.get("human_answer")}
        if not answers:
            r["clarified"] = None
            continue
        answered_any_count += 1
        nl = r["nl"]
        rebuild = run_system_b(nl, ASIM_SCHEMA, extraction_agent, ir_builder, max_attempts=3)
        if not rebuild.success:
            r["clarified"] = {"success": False, "reason": rebuild.reason}
            continue
        extraction = extraction_agent.extract(nl)
        gaps_for_case = find_gaps(rebuild.ir)
        clarified = resolve_clarification(extraction, rebuild.ir, gaps_for_case, answers, ir_builder, ASIM_SCHEMA)
        r["clarified"] = {
            "success": clarified.success,
            "kql": clarified.kql,
            "still_abstained": bool(clarified.ir and clarified.ir.abstained),
            "remaining_gaps": len(find_gaps(clarified.ir)) if clarified.ir else None,
        }
        if clarified.success and not (clarified.ir and clarified.ir.abstained):
            resolved_count += 1
        print(f"{r['rule_id']}: resolved={clarified.success and not (clarified.ir and clarified.ir.abstained)}")

    _OUT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n{answered_any_count} cases had at least one answer supplied.")
    print(f"{resolved_count}/{answered_any_count} resolved to a non-abstained, successful query "
          f"({resolved_count/answered_any_count*100:.1f}% conversion rate)" if answered_any_count else "no answers supplied yet.")
    print("Logic Correctness on the resolved queries still needs a human/AI rating pass -- see eval/score_logic_correctness.py.")


if __name__ == "__main__":
    if "--resolve" in sys.argv:
        phase_resolve()
    else:
        phase_a_and_b()
